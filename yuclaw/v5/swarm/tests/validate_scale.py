"""YUCLAW v5 Layer 1 Day 5B — at-scale Layer-1 validation (measure, don't just run).

Runs the full specialized swarm (base + 10 specialists + C6 risk channel) across the largest
clean real-data batch the corpus supports, and MEASURES (Validation-Lab discipline):
  - grounding-rate distribution (base vs specialists, incl. the now-unblocked earnings/guidance);
  - citation fidelity;
  - spawn accuracy on the CORRECTED event-type layer;
  - whether the C6 RISK channel DISCRIMINATES — do elevated-risk flags concentrate where higher
    realized forward volatility follows (vs normal)?  (in-sample, point-in-time price_history).

Agent-only (synthesize=False) by default so the at-scale metrics are cheap; the 70B synthesis is
not under test here (its separation is validated on a small subset by batch_specialists2). READ-
ONLY on public.*; persist=False (Day-3 baseline intact). Text acquisition chain per filing:
existing swarm_inputs -> Exhibit 99.x (earnings/guidance) -> MD&A narrative (10-K/10-Q) ->
events_raw.raw_text cover.

Usage: python3 -m yuclaw.v5.swarm.tests.validate_scale [LIMIT] [out.json]
"""

from __future__ import annotations

import json
import statistics as stats
import subprocess
import sys
import time

import psycopg2

from yuclaw.v5.extract.exhibit import extract_exhibit
from yuclaw.v5.extract.narrative import extract_and_store, sanity_ok
from yuclaw.v5.extract.reclassify import corrected_event_types
from yuclaw.v5.swarm.specialized import run_specialized, ROLES
from yuclaw.v5.swarm.specialists import RISK_NATURED
from yuclaw.v5.swarm.worker import WORKER_MODEL

EARNINGS_TYPES = {"EARNINGS_RESULT", "EARNINGS_BEAT", "GUIDANCE_RAISE", "GUIDANCE_CUT"}
FWD_WINDOW = 20  # trading days for realized-vol outcome


def _preflight() -> None:
    ps = subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True).stdout
    bad = [l for l in ps.splitlines() if any(t in l for t in ("llama-server", "vllm")) and "ollama" not in l.lower()]
    if bad:
        print("PREFLIGHT FAIL:", bad[:2]); sys.exit(3)
    with open("/proc/meminfo") as f:
        mi = {k.strip(): v for k, v in (l.split(":", 1) for l in f)}
    print(f"PREFLIGHT OK; MemAvailable={int(mi['MemAvailable'].split()[0])/1024/1024:.0f} GiB "
          f"WORKER_MODEL={WORKER_MODEL}\n")


def _filings() -> list[dict]:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); cur = cn.cursor()
    cur.execute("""
        WITH f AS (
          SELECT DISTINCT er.accession_number AS acc, er.ticker, er.source_type AS form,
                 e.event_time::date AS evdate,
                 COALESCE(c.corrected_event_type, e.event_type) AS et
          FROM public.events e JOIN public.events_raw er ON er.source_url=e.source_url
          LEFT JOIN yuclaw_v5.event_type_corrected c ON c.event_id=e.event_id
          WHERE e.event_id NOT LIKE 'CASCADE%%'
            AND COALESCE(c.corrected_event_type,e.event_type) IN
              ('EARNINGS_RESULT','EARNINGS_BEAT','GUIDANCE_RAISE','GUIDANCE_CUT',
               'M_AND_A','FINANCING','GOVERNANCE','REGULATORY_ACTION'))
        SELECT acc, ticker, form, evdate, et FROM f ORDER BY et, ticker""")
    rows = [{"acc": a, "ticker": t, "form": fm, "evdate": d, "et": et} for a, t, fm, d, et in cur.fetchall()]
    cn.close()
    return rows


def _existing_narrative(acc: str) -> str | None:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); cur = cn.cursor()
    cur.execute("SELECT narrative_text FROM yuclaw_v5.swarm_inputs WHERE accession_number=%s", (acc,))
    r = cur.fetchone(); cn.close()
    return r[0] if r else None


def _raw_text(acc: str) -> str | None:
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); cur = cn.cursor()
    cur.execute("SELECT raw_text FROM public.events_raw WHERE accession_number=%s", (acc,))
    r = cur.fetchone(); cn.close()
    return r[0] if r else None


def _acquire_text(f: dict) -> tuple[str | None, str]:
    """Robust chain. Returns (text, source_label)."""
    n = _existing_narrative(f["acc"])
    if n:
        return n, "existing"
    et = f["et"]
    # PROSE-FIRST (Order B): try the exhibit extractor for ANY 8-K, not just earnings types —
    # FINANCING/M&A/governance 8-Ks also carry prose exhibits (press releases, indentures,
    # credit agreements). raw_cover (XBRL/cover soup, grounds ~0.34) stays the fallback when no
    # usable exhibit exists (e.g. M&A 8-Ks whose substance is in the body, not an exhibit).
    try:
        if f["form"] == "8-K" or et in EARNINGS_TYPES:
            rec = extract_exhibit(f["acc"], persist=False)
            if sanity_ok(rec)[0]:
                return rec["narrative_text"], "exhibit"
        if f["form"] in ("10-K", "10-Q"):
            rec = extract_and_store(f["acc"], persist=False)
            if sanity_ok(rec)[0]:
                return rec["narrative_text"], "mdna"
    except Exception as e:
        pass
    raw = _raw_text(f["acc"])
    return (raw, "raw_cover") if raw else (None, "none")


def _fwd_vol(ticker: str, evdate, window: int = FWD_WINDOW) -> float | None:
    """Realized daily-return volatility over the next `window` trading days after evdate."""
    cn = psycopg2.connect("dbname=yuclaw_events"); cn.set_session(readonly=True); cur = cn.cursor()
    cur.execute("""
        WITH px AS (
          SELECT trade_date, close FROM public.price_history
          WHERE ticker=%s AND trade_date > %s ORDER BY trade_date LIMIT %s),
        r AS (SELECT ln(close::float8 / lag(close) OVER (ORDER BY trade_date)) ret FROM px)
        SELECT count(*) , stddev_samp(ret) FROM r WHERE ret IS NOT NULL""", (ticker, evdate, window))
    n, vol = cur.fetchone(); cn.close()
    return float(vol) if (vol is not None and n and n >= 5) else None


def main() -> int:
    _preflight()
    filings = _filings()
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(filings)
    out_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/d5b_scale.json"
    filings = filings[:limit]
    print(f"=== AT-SCALE VALIDATION: {len(filings)} filings ===")
    by_et = {}
    for f in filings:
        by_et[f["et"]] = by_et.get(f["et"], 0) + 1
    print("event-type coverage:", by_et, "\n")

    results = []
    t0 = time.perf_counter()
    for i, f in enumerate(filings, 1):
        text, src = _acquire_text(f)
        if not text:
            print(f"[{i}/{len(filings)}] {f['ticker']} {f['et']}: NO TEXT"); continue
        try:
            res = run_specialized(f["acc"], text, synthesize=False)
        except Exception as e:
            print(f"[{i}/{len(filings)}] {f['ticker']} {f['et']}: FAIL {type(e).__name__}: {e}"); continue
        rc = res["risk_channel"]
        base_gr = {r: res["base"][r]["grounding"]["grounding_rate"] for r in ROLES}
        spec = {k: {"gr": v["grounding"]["grounding_rate"],
                    "dir": (v["output"].get("return_view") or {}).get("direction"),
                    "cv": v["grounding"]["citations_verified"], "ct": v["grounding"]["citations_total"]}
                for k, v in res["specialists"].items()}
        base_cv = sum(res["base"][r]["grounding"]["citations_verified"] for r in ROLES)
        base_ct = sum(res["base"][r]["grounding"]["citations_total"] for r in ROLES)
        fwd = _fwd_vol(f["ticker"], f["evdate"])
        c6_viol = [k for k in spec if k in RISK_NATURED and (spec[k]["dir"] or "").lower() not in ("neutral", "mixed", "")]
        rec = {"acc": f["acc"], "ticker": f["ticker"], "et": f["et"], "text_src": src,
               "spawned": res["spawn_keys"], "base_gr": base_gr, "spec_gr": {k: v["gr"] for k, v in spec.items()},
               "base_cite_fid": (base_cv / base_ct) if base_ct else None,
               "risk_level": rc["level"], "risk_flag": rc["flag"], "insider_gate": rc["insider_gate"],
               "fwd_vol": fwd, "c6_viol": c6_viol}
        results.append(rec)
        print(f"[{i}/{len(filings)}] {f['ticker']:5} {f['et']:16} src={src:9} spawn={res['spawn_keys']} "
              f"risk={rc['flag']:8} fwd_vol={fwd if fwd is None else round(fwd,4)}"
              + ("  C6_VIOL!" if c6_viol else ""))

    wall = time.perf_counter() - t0
    json.dump({"results": results, "wall_s": wall}, open(out_path, "w"), indent=2, default=str)

    # ---- MEASUREMENTS ----
    print("\n" + "=" * 64)
    print(f"=== MEASUREMENTS (N={len(results)}, in-sample, {wall:.0f}s, "
          f"{wall/max(1,len(results)):.1f}s/filing) ===")

    def gflat(sel):
        v = []
        for r in results:
            v += sel(r)
        return v
    base_rates = gflat(lambda r: list(r["base_gr"].values()))
    spec_rates = gflat(lambda r: list(r["spec_gr"].values()))
    print("\n-- grounding-rate distribution --")
    for label, v in [("base agents", base_rates), ("specialists", spec_rates)]:
        if v:
            print(f"  {label:12}: n={len(v)} mean={stats.mean(v):.2f} median={stats.median(v):.2f} "
                  f">=0.5: {sum(x>=0.5 for x in v)}/{len(v)}")
    fid = [r["base_cite_fid"] for r in results if r["base_cite_fid"] is not None]
    if fid:
        print(f"  base citation fidelity: mean={stats.mean(fid):.2f} (n={len(fid)})")

    print("\n-- spawn accuracy (deterministic from corrected tags) --")
    fin = [r for r in results if r["et"] == "FINANCING"]
    fin_no_ma = sum("ma" not in r["spawned"] for r in fin)
    print(f"  FINANCING filings spawning NO M&A specialist: {fin_no_ma}/{len(fin)} "
          f"(Day-4 mis-spawn fixed)")
    eq = [r for r in results if r["et"] in EARNINGS_TYPES]
    eq_spawn = sum("earningsquality" in r["spawned"] for r in eq)
    print(f"  earnings/guidance spawning earningsquality: {eq_spawn}/{len(eq)}")

    print("\n-- C6 risk/direction separation --")
    viol = [r for r in results if r["c6_viol"]]
    print(f"  risk-natured specialists emitting a direction: {len(viol)} "
          f"{'<<< FAIL' if viol else '(none — PASS)'}")

    print("\n-- DOES THE RISK CHANNEL DISCRIMINATE? (elevated flag -> higher forward vol?) --")
    ev = [r for r in results if r["fwd_vol"] is not None]
    elev = [r["fwd_vol"] for r in ev if r["risk_flag"] == "elevated"]
    norm = [r["fwd_vol"] for r in ev if r["risk_flag"] != "elevated"]
    print(f"  flag distribution: elevated={sum(r['risk_flag']=='elevated' for r in results)} "
          f"normal={sum(r['risk_flag']!='elevated' for r in results)} (of {len(results)})")
    print(f"  with forward-vol outcome: elevated n={len(elev)} normal n={len(norm)}")
    if elev:
        print(f"    mean fwd 20d vol | elevated = {stats.mean(elev):.4f}")
    if norm:
        print(f"    mean fwd 20d vol | normal   = {stats.mean(norm):.4f}")
    if elev and norm:
        sep = stats.mean(elev) - stats.mean(norm)
        print(f"    separation (elev - normal) = {sep:+.4f}  "
              f"({'discriminates (elevated->higher vol)' if sep > 0 else 'NO discrimination / wrong sign'})")
    elif not norm:
        print("    NOTE: risk flag is SATURATED at 'elevated' — cannot discriminate. Real finding.")
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
