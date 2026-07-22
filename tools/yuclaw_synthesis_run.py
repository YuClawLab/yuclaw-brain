#!/usr/bin/env python3
"""
Synthesis-layer REAL-DATA runner (owner-directed activation, 2026-07-22).

Builds a LensSnapshot per Canada lens (XEG/ZEO/GDX/URNM) from the SAME live
substrate the public lens cards render (canada_posture / canada_event_maturity
/ output/swarm/canada C6 artifacts / the Lab's event-study internals), then
runs ResearchBrief + ClusteredCAR (+5/+10/+20) + TensionEngine +
DecisionCanvas and renders PREVIEW pages to docs/preview/<lens>_synthesis.html.

Every number is queried — nothing typed by hand. The only hand-authored
mapping is EVENT-TYPE VOCABULARY (DB names -> module tension vocabulary),
which maps categories, not values.

Modes:
    python3 tools/yuclaw_synthesis_run.py                 # full run + previews
    python3 tools/yuclaw_synthesis_run.py --archive-only  # daily-chain snapshot dump

Archives: output/synthesis/<data_through>_<lens>_snapshot.json — tomorrow's
delta baseline. Today (first run) there is no prior archive, so ResearchBrief
runs in current-state-only mode (prev = cur; all deltas render as zero).

The public canada_resources.html is NOT touched by this script.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import psycopg2

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "tools"))

from yuclaw_research_brief import (CarPoint, Funnel, IssuerRow, LensSnapshot,
                                   ResearchBrief)
from yuclaw_evidence_canvas import (ClusteredCAR, DecisionCanvas, TensionEngine,
                                    METHOD_HASH)

from v3.lab.etf_evidence import (CANADA_LENS_KEYS, CAR_POST, CAR_PRE, EST_GAP,
                                 EST_MIN, EST_WIN, MARKET, canada_lens_holdings,
                                 canada_posture, canada_event_maturity,
                                 _daily_returns)
from v3.lab.cohort_engine import DSN, load_prices
from v3.lab.stats import ols

ARCHIVE_DIR = _REPO / "output" / "synthesis"
PREVIEW_DIR = _REPO / "docs" / "preview"
HORIZONS = (5, 10, 20)
RECENT_DAYS = 30  # window for TensionEngine "recent_event_types"

# DB event-type names -> module tension vocabulary (categories, not values).
TYPE_MAP = {
    "DIVIDEND_CHANGE": "DIVIDEND",
    "BUYBACK_ANNOUNCE": "BUYBACK",
    "GUIDANCE_RAISE": "GUIDANCE_RAISE",
    "GUIDANCE_CUT": "GUIDANCE_CUT",
    "REGULATORY_ACTION": "REGULATORY",
    "LITIGATION": "LITIGATION",
}

BANNER = (
    '<div style="background:#3D2B00;border:2px solid #FBA94B;border-radius:10px;'
    'padding:14px 18px;margin-bottom:18px;font-size:13px;color:#FBA94B;font-weight:700">'
    'PREVIEW — real data, not yet part of the daily build. Unlinked page; '
    'delta baseline starts with the next daily snapshot archive.</div>')


def _build_id() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                       capture_output=True, text=True)
    return r.stdout.strip()[:8] if r.returncode == 0 else "unknown"


def _data_through() -> str:
    """Latest Verified Research Ledger block date (queried, not typed)."""
    last = (Path.home() / "yuclaw-trust" / "verified_research_ledger.jsonl"
            ).read_text().strip().rsplit("\n", 1)[-1]
    return json.loads(last)["date"]


def _c6_state() -> dict[str, dict]:
    """ticker -> latest C6 risk-channel posture (same artifacts the public
    page reads). No rarity percentile exists in the artifacts -> None."""
    out: dict[str, dict] = {}
    for f in sorted((_REPO / "output" / "swarm" / "canada").glob("*.json")):
        d = json.loads(f.read_text())
        rc = d.get("risk_channel") or {}
        if d.get("ticker") and rc:
            out[d["ticker"]] = {"flag": rc.get("flag")}
    return out


def _db_issuer_facts(tickers: list[str], data_through: str) -> dict[str, dict]:
    """last event type/date + recent (30d) mapped types + candidate counts."""
    facts: dict[str, dict] = {t: {"recent": set(), "last_type": None,
                                  "last_date": None} for t in tickers}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ON (ticker) ticker, event_type, event_time::date
                   FROM events WHERE event_status='accepted' AND ticker = ANY(%s)
                   ORDER BY ticker, event_time DESC""", (tickers,))
            for tk, et, d in cur.fetchall():
                facts[tk]["last_type"] = et
                facts[tk]["last_date"] = d.isoformat()
            cur.execute(
                """SELECT ticker, event_type FROM events
                   WHERE event_status='accepted' AND ticker = ANY(%s)
                     AND event_time::date > (%s::date - %s * interval '1 day')
                   GROUP BY 1, 2""", (tickers, data_through, RECENT_DAYS))
            for tk, et in cur.fetchall():
                mapped = TYPE_MAP.get(et)
                if mapped:
                    facts[tk]["recent"].add(mapped)
    return facts


def _funnel_counts(tickers: list[str], posture: dict, matured: int) -> Funnel:
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT count(*) FROM events
                   WHERE ticker = ANY(%s) AND event_status IN ('accepted','rejected')""",
                (tickers,))
            candidates = cur.fetchone()[0]
            cur.execute(
                """SELECT count(*) FROM (
                     SELECT DISTINCT ticker, event_type, direction, event_time::date
                     FROM events WHERE event_status='accepted' AND ticker = ANY(%s)) t""",
                (tickers,))
            after_dedup = cur.fetchone()[0]
            cur.execute(
                """SELECT count(*) FROM (
                     SELECT DISTINCT ticker, event_type, direction, event_time::date
                     FROM events WHERE event_status='accepted' AND ticker = ANY(%s)
                       AND direction <> 0) t""", (tickers,))
            directional_dedup = cur.fetchone()[0]
    return Funnel(
        filings_ingested=int(posture["filings_total"]),
        with_usable_prose=int(posture["prose_total"]),
        candidate_events=int(candidates),
        accepted=int(posture["events_total"]),
        after_dedup=int(after_dedup),
        matured=int(matured),
        direction_eligible=int(min(directional_dedup, matured)),
    )


def _lens_grade(members: list[dict]) -> str:
    """Modal member grade letter (ties -> better-coverage letter). Derived,
    not typed."""
    counts: dict[str, int] = {}
    for m in members:
        g = str(m.get("grade", ""))[:1] or "D"
        counts[g] = counts.get(g, 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def per_event_cars(lens: str) -> dict[int, list[tuple[str, float]]]:
    """(issuer, signed peer-model CAR %) per deduped directional event at each
    horizon — the SAME estimation/window/dedup methodology as the Lab's
    event_study (imported constants), reproduced per-event so ClusteredCAR
    can group by issuer."""
    covered = sorted(canada_lens_holdings()[lens])
    prices, trade_dates = load_prices()
    spy_ret = _daily_returns(prices.get(MARKET, {}), trade_dates)
    tk_ret = {tk: _daily_returns(prices.get(tk, {}), trade_dates) for tk in covered}
    td_index = {d: i for i, d in enumerate(trade_dates)}

    def peer_ret(tk):
        others = [o for o in covered if o != tk]
        out = {}
        for d in trade_dates:
            vals = [tk_ret[o].get(d) for o in others]
            vals = [v for v in vals if v is not None]
            if vals:
                out[d] = sum(vals) / len(vals)
        return out

    peer_by_tk = {tk: peer_ret(tk) for tk in covered}
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT ticker, event_type, direction, event_time::date
                   FROM events WHERE event_status='accepted' AND ticker = ANY(%s)
                     AND direction <> 0 ORDER BY 4""", (covered,))
            events = cur.fetchall()

    out: dict[int, list[tuple[str, float]]] = {h: [] for h in HORIZONS}
    for tk, _et, direction, ev_date in events:
        day0 = next((d for d in trade_dates if d >= ev_date), None)
        if day0 is None:
            continue
        i0 = td_index[day0]
        est_days = trade_dates[max(0, i0 - EST_GAP - EST_WIN): max(0, i0 - EST_GAP)]
        pairs = [(tk_ret[tk].get(d), peer_by_tk[tk].get(d)) for d in est_days]
        pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
        if len(pairs) < EST_MIN:
            continue
        reg = ols([a for a, _ in pairs], [b for _, b in pairs])
        if reg is None:
            continue
        cum = 0.0
        car_at: dict[int, float] = {}
        for tau in range(-CAR_PRE, CAR_POST + 1):
            j = i0 + tau
            if not (0 <= j < len(trade_dates)):
                break
            d = trade_dates[j]
            r, m = tk_ret[tk].get(d), peer_by_tk[tk].get(d)
            if r is None or m is None:
                continue
            cum += (r - (reg["alpha"] + reg["beta"] * m)) * int(direction)
            if tau in HORIZONS:
                car_at[tau] = cum
        for h, v in car_at.items():
            out[h].append((tk, round(v * 100.0, 4)))
    return out


def build_snapshot(lens: str, build_id: str, data_through: str,
                   pooled: dict[int, list[tuple[str, float]]]) -> LensSnapshot:
    p = canada_posture(lens)
    mat = canada_event_maturity(lens)
    c6 = _c6_state()
    tickers = sorted(canada_lens_holdings()[lens])
    facts = _db_issuer_facts(tickers, data_through)

    issuers = []
    for m in sorted(p["members"], key=lambda x: -x["weight_pct"]):
        tk = m["ticker"]
        st = c6.get(tk, {}).get("flag")
        issuers.append(IssuerRow(
            ticker=tk, weight_pct=float(m["weight_pct"]),
            events_accepted=int(m["n_events"]),
            c6_state=st if st in ("elevated", "normal") else st,
            c6_rarity_pctile=None,
            last_event_type=facts[tk]["last_type"],
            last_event_date=facts[tk]["last_date"],
            new_events_since_prev=0,       # current-state-only mode today
            form4_eligible=("Form 4" in str(m.get("insider_scope", ""))),
        ))

    # CarPoints from the SAME per-event pool ClusteredCAR uses (naive stats
    # computed by the module later; here we store mean/naive CI/n per horizon).
    import math as _math
    car_points = []
    for h in HORIZONS:
        ev = pooled[h]
        if not ev:
            continue
        xs = [c for _, c in ev]
        n = len(xs)
        mean = sum(xs) / n
        sd = (_math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1))
              if n > 1 else 0.0)
        half = 1.959964 * sd / _math.sqrt(n) if n else 0.0
        car_points.append(CarPoint(
            day=h, peer_car_pct=round(mean, 2), spy_car_pct=round(mean, 2),
            ci_lo_pct=round(mean - half, 2), ci_hi_pct=round(mean + half, 2),
            n=n))

    return LensSnapshot(
        lens=lens, build_id=build_id, data_through=data_through,
        coverage_weight_pct=float(p["sec_filer_weight_pct"]),
        filers_covered=int(p["n_covered_names"]),
        filers_total=int(p["n_names_total"]),
        grade=_lens_grade(p["members"]),
        funnel=_funnel_counts(tickers, p, mat["n_matured"]),
        issuers=issuers, car=car_points)


def archive_snapshot(snap: LensSnapshot) -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    out = ARCHIVE_DIR / f"{snap.data_through}_{snap.lens}_snapshot.json"
    out.write_text(json.dumps(asdict(snap), indent=1, default=str))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-only", action="store_true",
                    help="daily-chain mode: dump LensSnapshot JSONs, no previews")
    a = ap.parse_args(argv)

    build_id, thru = _build_id(), _data_through()
    print(f"[synthesis] build {build_id} · data through {thru} · method {METHOD_HASH}")

    for lens in CANADA_LENS_KEYS:
        pooled = per_event_cars(lens)
        snap = build_snapshot(lens, build_id, thru, pooled)
        path = archive_snapshot(snap)
        print(f"[synthesis] {lens}: archived {path.name} "
              f"(events@+20: {len(pooled[20])})")
        if a.archive_only:
            continue

        brief = ResearchBrief(snap, snap).build()   # current-state-only today
        infs = [ClusteredCAR(pooled[h], h).run() for h in HORIZONS if pooled[h]]
        rows = [{"ticker": i.ticker, "c6_state": i.c6_state,
                 "form4_eligible": i.form4_eligible,
                 "recent_event_types":
                     sorted(_db_issuer_facts([i.ticker], thru)[i.ticker]["recent"])}
                for i in snap.issuers]
        tensions = TensionEngine().detect(rows)
        canvas = DecisionCanvas(lens, build_id, thru, infs, tensions, rows)

        PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        out = PREVIEW_DIR / f"{lens.lower()}_synthesis.html"
        out.write_text(
            "<!doctype html><meta charset='utf-8'>"
            f"<title>PREVIEW — {lens} synthesis</title>"
            "<body style='background:#0b0f14;color:#E2E8F0;"
            "font-family:Inter,sans-serif;padding:30px;max-width:900px;margin:0 auto'>"
            + BANNER + brief.to_html() + "<hr style='border-color:#1E232D;margin:26px 0'>"
            + canvas.to_html() + "</body>")
        print(f"[synthesis] {lens}: preview -> {out.relative_to(_REPO)}")
        print("\n" + "=" * 74)
        print(brief.to_text())
        print("-" * 74)
        print(canvas.to_text())
        print("=" * 74 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
