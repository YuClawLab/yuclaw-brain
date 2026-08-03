#!/usr/bin/env python3
"""
U350 Phase-A admission engine (Part 4) — executes the registered
"U350 Selection Rule v1" (05c59feb8120) and "Universe Admission Protocol
v1" (406a0462bb1f) exactly as locked. Deterministic given (rule version,
as-of): every external input is cached box-local or persisted in the u350
schema, tie-breaks are by CIK ascending, and re-runs from the caches
reproduce the same report byte-for-byte.

Subcommands:
  resolve   build the candidate pool (coverage ∪ 13 SPDR fund
            constituents as-of 2026-07-29), resolve against the SEC
            ticker file; cache to internal/u350/candidates.json
  enrich    fetch data.sec.gov submissions per candidate CIK (SIC +
            recent form types for the substrate gate); resumable cache
            internal/u350/subs_cache/CIK*.json
  prices    fetch trailing price/volume history (as-of 2026-08-01) for
            all candidates via yfinance; persist into u350.price_history
            THROUGH u350_connection (the role that cannot write public)
  select    rank per the Selection Rule, run the six admission gates,
            write internal/u350/admission_report_phaseA.md, insert
            identity rows (tier='shadow') + lineage, lock the Phase-A
            manifest hash into u350.manifest

HARD RULES honored here:
  - no write touches any U79/public record table; candidate prices and
    the manifest live in the u350 schema via u350_connection()
  - identity rows are the P2 spine (built for exactly this), tier='shadow'
  - current evidence-tier names are EXCLUDED from Phase-A additions:
    the standing Canada-resources stop condition says scoring those names
    stops the line; shadow-scoring them is deferred to Phase B with an
    explicit owner decision, and each exclusion is printed with this
    reason
  - liquidity verdicts are issued ONLY if the versioned liquidity
    addendum registration exists (registry-first); otherwise gate 3
    reports NOT_EVALUATED and admission does not complete
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

AS_OF = "2026-08-01"            # registered Phase-A as-of (Selection Rule v1)
PHASE_A_TOTAL = 150             # 79 U79 + 71 additions
UA = "YuClawLab vzhang2199@gmail.com"
OUT = _REPO / "internal" / "u350"
SUBS = OUT / "subs_cache"

# SIC division mapping (standard ranges) — the "SIC sector grouping" of
# the Selection Rule; deterministic and published in the report header.
SIC_DIVISIONS = [
    (100, 999, "A: Agriculture"), (1000, 1499, "B: Mining"),
    (1500, 1799, "C: Construction"), (2000, 3999, "D: Manufacturing"),
    (4000, 4999, "E: Transport/Utilities"), (5000, 5199, "F: Wholesale"),
    (5200, 5999, "G: Retail"), (6000, 6799, "H: Finance/RE"),
    (7000, 8999, "I: Services"), (9100, 9999, "J: Public Admin"),
]


def sic_division(sic) -> str:
    try:
        s = int(sic)
    except (TypeError, ValueError):
        return "UNKNOWN"
    for lo, hi, name in SIC_DIVISIONS:
        if lo <= s <= hi:
            return name
    return "UNKNOWN"


def _fetch_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def cmd_resolve() -> int:
    u = json.loads((_REPO / "v3" / "universe.json").read_text())
    coverage = set()
    for k in ("equities", "sector_etfs", "broad_etfs", "macro"):
        coverage |= set(u.get(k, []))
    evidence = {r["ticker"] for r in u["evidence_tier"]}
    scoring = coverage.copy()

    constituents = set()
    for f in sorted((_REPO / "data" / "holdings").glob("*.json")):
        if f.name == "manifest.json":
            continue
        d = json.loads(f.read_text())
        assert d["as_of"] == "2026-07-29", f"{f.name} as_of {d['as_of']}"
        constituents |= set(d["holdings"])

    sec = {}
    for row in _fetch_json(
            "https://www.sec.gov/files/company_tickers_exchange.json")["data"]:
        cik, name, ticker, exch = row
        sec[ticker] = {"cik": f"{cik:010d}", "name": name, "exchange": exch}

    pool, dropped = [], []
    for tk in sorted(coverage | evidence | constituents):
        tk_sec = tk.replace(".", "-")
        meta = sec.get(tk) or sec.get(tk_sec)
        status = ("u79_scoring" if tk in scoring else
                  "evidence_tier" if tk in evidence else "candidate")
        if meta is None:
            dropped.append({"ticker": tk, "status": status,
                            "reason": "not in SEC ticker file "
                                      "(identity unresolvable)"})
            continue
        pool.append({"ticker": tk, "status": status, **meta})

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "candidates.json").write_text(json.dumps(
        {"as_of": AS_OF, "holdings_as_of": "2026-07-29",
         "pool": pool, "dropped": dropped}, indent=1))
    from collections import Counter
    c = Counter(p["status"] for p in pool)
    print(f"[resolve] pool={len(pool)} {dict(c)} · dropped(no SEC "
          f"identity)={len(dropped)}")
    return 0


def cmd_enrich() -> int:
    d = json.loads((OUT / "candidates.json").read_text())
    SUBS.mkdir(parents=True, exist_ok=True)
    todo = [p for p in d["pool"]
            if not (SUBS / f"CIK{p['cik']}.json").exists()]
    print(f"[enrich] {len(todo)} submissions to fetch "
          f"({len(d['pool']) - len(todo)} cached)")
    for i, p in enumerate(todo):
        try:
            s = _fetch_json(
                f"https://data.sec.gov/submissions/CIK{p['cik']}.json")
            forms = set((s.get("filings", {}).get("recent", {})
                         or {}).get("form", []))
            keep = {"cik": p["cik"], "sic": s.get("sic"),
                    "sicDescription": s.get("sicDescription"),
                    "country": (s.get("addresses", {}).get("business", {})
                                or {}).get("stateOrCountryDescription"),
                    "recent_forms": sorted(forms)[:60]}
            (SUBS / f"CIK{p['cik']}.json").write_text(json.dumps(keep))
        except Exception as exc:                  # noqa: BLE001
            print(f"  ! {p['ticker']} CIK{p['cik']}: {exc}")
        time.sleep(0.15)
        if i and i % 100 == 0:
            print(f"  … {i}/{len(todo)}")
    done = len(list(SUBS.glob("CIK*.json")))
    print(f"[enrich] cache now holds {done} submissions")
    return 0


def cmd_prices() -> int:
    import pandas as pd
    import yfinance as yf
    from v3.u350 import u350_connection

    d = json.loads((OUT / "candidates.json").read_text())
    tickers = sorted({p["ticker"] for p in d["pool"]})
    with u350_connection() as cn:
        with cn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS u350.price_history (
                ticker text NOT NULL, trade_date date NOT NULL,
                close real, volume bigint,
                PRIMARY KEY (ticker, trade_date))""")
            cur.execute("SELECT ticker, count(*) FROM u350.price_history "
                        "GROUP BY 1")
            have = dict(cur.fetchall())
        cn.commit()
    todo = [t for t in tickers if have.get(t, 0) < 252]
    print(f"[prices] {len(todo)} tickers to fetch "
          f"({len(tickers) - len(todo)} already have >=252 rows)")
    CH = 100
    for i in range(0, len(todo), CH):
        chunk = todo[i:i + CH]
        yft = [t.replace(".", "-") for t in chunk]
        df = yf.download(yft, start="2025-07-01", end="2026-08-02",
                         progress=False, auto_adjust=False,
                         group_by="ticker", threads=True)
        rows = []
        for t, yt in zip(chunk, yft):
            try:
                sub = df[yt][["Close", "Volume"]].dropna(subset=["Close"])
            except KeyError:
                continue
            for dt, r in sub.iterrows():
                rows.append((t, dt.date(), float(r["Close"]),
                             int(r["Volume"]) if pd.notna(r["Volume"])
                             else None))
        with u350_connection() as cn:
            with cn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO u350.price_history
                       (ticker, trade_date, close, volume)
                       VALUES (%s,%s,%s,%s)
                       ON CONFLICT (ticker, trade_date) DO UPDATE
                       SET close=EXCLUDED.close, volume=EXCLUDED.volume""",
                    rows)
            cn.commit()
        print(f"  … {min(i + CH, len(todo))}/{len(todo)} "
              f"(+{len(rows)} rows)")
    with u350_connection() as cn:
        with cn.cursor() as cur:
            cur.execute("SELECT count(*), count(DISTINCT ticker) "
                        "FROM u350.price_history")
            n, nt = cur.fetchone()
    print(f"[prices] u350.price_history: {n:,} rows / {nt} tickers")
    return 0


def _liquidity_addendum():
    """Return {'protocol_id', 'params'} for the registered liquidity
    addendum, or None. Numbers live in the HASHED spec text; the box-local
    mirror internal/u350/liquidity_addendum_v1.json must reproduce the
    registered method hash, else we refuse (tamper evidence)."""
    entry = None
    for line in (_REPO / "registry" / "protocols.jsonl").read_text(
            ).splitlines():
        e = json.loads(line)
        p = e.get("payload", e)
        if (e.get("kind") == "protocol" and "Liquidity Thresholds Addendum"
                in p.get("name", "") and p.get("status") == "LOCKED"):
            entry = p
    if entry is None:
        return None
    mirror = json.loads((OUT / "liquidity_addendum_v1.json").read_text())
    got = hashlib.sha256(mirror["spec"].encode()).hexdigest()[:16]
    if got != entry["method_hash"]:
        raise SystemExit(
            f"liquidity addendum mirror hash {got} != registered "
            f"method_hash {entry['method_hash']} — refusing to issue "
            f"liquidity verdicts")
    return {"protocol_id": entry["protocol_id"],
            "params": mirror["params"]}


def _metrics(cur, ticker):
    """Trailing-252d metrics as-of AS_OF from u350.price_history."""
    cur.execute("""SELECT trade_date, close, volume
                   FROM u350.price_history
                   WHERE ticker=%s AND trade_date <= %s
                   ORDER BY trade_date DESC LIMIT 252""",
                (ticker, AS_OF))
    rows = cur.fetchall()
    if len(rows) < 252:
        return {"n_days": len(rows)}
    import statistics
    dv = [c * (v or 0) for _d, c, v in rows]
    zero_vol = sum(1 for _d, _c, v in rows if not v)
    dates = [r[0] for r in rows][::-1]
    # gap rule: > 5 consecutive missing trading days inside the trailing
    # window, measured against the union trading calendar in the store
    cur.execute("""SELECT count(DISTINCT trade_date) FROM u350.price_history
                   WHERE trade_date BETWEEN %s AND %s""",
                (dates[0], dates[-1]))
    cal = cur.fetchone()[0]
    max_gap = 0
    if cal > len(dates):
        cur.execute("""SELECT DISTINCT trade_date FROM u350.price_history
                       WHERE trade_date BETWEEN %s AND %s ORDER BY 1""",
                    (dates[0], dates[-1]))
        cal_dates = [r[0] for r in cur.fetchall()]
        have = set(dates)
        run = 0
        for cd in cal_dates:
            run = 0 if cd in have else run + 1
            max_gap = max(max_gap, run)
    return {"n_days": 252, "median_dollar_vol": statistics.median(dv),
            "zero_vol_rate": zero_vol / 252, "max_gap": max_gap}


def cmd_select() -> int:
    from v3.u350 import u350_connection
    from v3.universe_tiers import scoring_universe

    add = _liquidity_addendum()
    d = json.loads((OUT / "candidates.json").read_text())
    pool = d["pool"]

    # enrich from caches
    for p in pool:
        f = SUBS / f"CIK{p['cik']}.json"
        s = json.loads(f.read_text()) if f.exists() else {}
        p["sic"] = s.get("sic")
        p["division"] = sic_division(s.get("sic"))
        p["country"] = s.get("country")
        forms = set(s.get("recent_forms", []))
        if forms & {"8-K", "10-Q", "10-K"}:
            p["substrate"], p["filer_class"] = "8-K/10-Q/10-K", "domestic"
        elif forms & {"6-K", "40-F"} and "40-F" in forms:
            p["substrate"], p["filer_class"] = "6-K/40-F", "MJDS"
        elif forms & {"6-K", "20-F"}:
            p["substrate"], p["filer_class"] = "6-K/20-F", "FPI"
        else:
            p["substrate"], p["filer_class"] = None, "unknown"

    with u350_connection() as cn:
        with cn.cursor() as cur:
            for p in pool:
                p["m"] = _metrics(cur, p["ticker"])

    # measured pool distribution for the liquidity addendum numbers
    cands = [p for p in pool if p["status"] == "candidate"
             and p["m"].get("n_days") == 252]
    dvs = sorted(p["m"]["median_dollar_vol"] for p in cands)
    import statistics
    pctl = {q: dvs[int(q / 100 * (len(dvs) - 1))] for q in (5, 10, 25, 50)}
    if add is None:
        print("[select] LIQUIDITY ADDENDUM NOT REGISTERED — measured pool "
              "distribution (candidates with full 252d):")
        for q, v in pctl.items():
            print(f"   p{q}: ${v:,.0f} median daily dollar volume")
        print(f"   pool n={len(dvs)}; zero-volume-day rates: "
              f"max={max(p['m']['zero_vol_rate'] for p in cands):.3f}")
        print("[select] register the addendum, then re-run select. "
              "No admission verdicts issued.")
        return 3

    floor = add["params"]["floor_dollar_vol"]
    zcap = add["params"]["zero_vol_day_cap"]

    existing = sorted(scoring_universe())
    evidence = {p["ticker"] for p in pool if p["status"] == "evidence_tier"}
    u = json.loads((_REPO / "v3" / "universe.json").read_text())
    existing_equities = set(u["equities"])

    # existing division counts (U79 operating companies only)
    div_count = {}
    for p in pool:
        if p["ticker"] in existing_equities:
            div_count[p["division"]] = div_count.get(p["division"], 0) + 1

    # gates per candidate
    report, admitted = [], []
    ranked = sorted(
        cands, key=lambda p: (-p["m"]["median_dollar_vol"], p["cik"]))
    CAP = int(0.22 * PHASE_A_TOTAL)          # 33
    for p in ranked:
        g, reasons = {}, []
        g["G1_identity"] = "PASS" if (p["cik"] and p["name"] and
                                      p["exchange"] and p["sic"]) else "FAIL"
        if g["G1_identity"] == "FAIL":
            reasons.append("identity incomplete (missing CIK/name/"
                           "exchange/SIC)")
        m = p["m"]
        g["G2_price"] = ("PASS" if m.get("n_days") == 252 and
                         m.get("max_gap", 99) <= 5 else "FAIL")
        if g["G2_price"] == "FAIL":
            reasons.append(f"price history {m.get('n_days')}d / max gap "
                           f"{m.get('max_gap', 'n/a')}")
        liq_ok = (m.get("median_dollar_vol", 0) >= floor and
                  m.get("zero_vol_rate", 1) <= zcap)
        g["G3_liquidity"] = "PASS" if liq_ok else "FAIL"
        if not liq_ok:
            reasons.append(f"median $vol {m.get('median_dollar_vol', 0):,.0f}"
                           f" < floor {floor:,.0f} or zero-vol rate "
                           f"{m.get('zero_vol_rate', 1):.3f} > {zcap}")
        g["G4_substrate"] = ("PASS" if p["substrate"] else
                             "NO_CURRENT_EVENT_SUBSTRATE")
        if not p["substrate"]:
            reasons.append("no mapped filing substrate; would carry "
                           "PRICE_ONLY_COMPONENTS_ACTIVE")
        g["G5_completeness"] = "PENDING_SHADOW (guard installed)"
        # standing stop condition: evidence-tier names never enter shadow
        # scoring in Phase A
        if p["ticker"] in evidence:
            g["excluded"] = ("evidence-tier stop condition — shadow "
                             "scoring deferred to Phase B owner decision")
        hard_ok = all(g[k] == "PASS" for k in
                      ("G1_identity", "G2_price", "G3_liquidity",
                       "G4_substrate")) and "excluded" not in g
        at_cap = div_count.get(p["division"], 0) >= CAP
        if hard_ok and at_cap:
            g["excluded"] = (f"sector cap — {p['division']} at 22% cap "
                             f"({CAP})")
            hard_ok = False
        verdict = "ADMITTED" if hard_ok and len(admitted) < (
            PHASE_A_TOTAL - len(existing)) else (
            "NOT_ADMITTED" if not hard_ok else "RANK_CUT")
        if verdict == "ADMITTED":
            admitted.append(p)
            div_count[p["division"]] = div_count.get(p["division"], 0) + 1
        report.append({"ticker": p["ticker"], "cik": p["cik"],
                       "division": p["division"], "gates": g,
                       "median_dollar_vol": m.get("median_dollar_vol"),
                       "verdict": verdict,
                       "reasons": reasons if verdict != "ADMITTED" else []})

    # G6 cross-sectional fit disclosures (never blocking)
    fit = []
    for dv, n in sorted(div_count.items()):
        share = n / PHASE_A_TOTAL          # cap denominator = the universe
        line = f"{dv}: {n} names ({share:.0%} of {PHASE_A_TOTAL})"
        if n > CAP:
            line += f" — OVER 22% CAP ({CAP})"
        elif n == CAP:
            line += f" — AT 22% CAP ({CAP}); further names excluded by cap"
        if n < 15:
            line += " — SECTOR_THIN (<15 floor)"
        fit.append(line)

    manifest_members = (
        [{"ticker": t, "origin": "u79"} for t in existing] +
        [{"ticker": p["ticker"], "cik": p["cik"], "origin": "shadow",
          "division": p["division"]} for p in
         sorted(admitted, key=lambda x: x["ticker"])])
    mhash = hashlib.sha256(json.dumps(
        manifest_members, sort_keys=True).encode()).hexdigest()

    # write report
    L = [f"# U350 Phase-A admission report — as-of {AS_OF} "
         f"(rule 05c59feb8120, protocol 406a0462bb1f)",
         f"Deterministic inputs: candidates.json (holdings as-of "
         f"2026-07-29), subs_cache, u350.price_history as-of {AS_OF}. "
         f"Ties by CIK ascending. Liquidity addendum: "
         f"{add['protocol_id']} (floor ${floor:,.0f}, zero-vol cap "
         f"{zcap}).",
         "", f"U79 members: {len(existing)} (untouched). Admitted shadow "
         f"additions: {len(admitted)}. Phase-A universe: "
         f"{len(existing) + len(admitted)}.",
         f"Manifest hash: {mhash}", "",
         "## Cross-sectional fit (G6 — disclosure-triggering, never "
         "blocking; operating companies only)"]
    L += [f"- {x}" for x in fit]
    L.append("")
    L.append("## Admitted (71 target)")
    for p in admitted:
        L.append(f"- {p['ticker']} ({p['division']}, "
                 f"${p['m']['median_dollar_vol']:,.0f}/day)")
    L.append("")
    L.append("## Not admitted / cut (with reasons)")
    for r in report:
        if r["verdict"] == "ADMITTED":
            continue
        why = "; ".join(r["reasons"]) or r["gates"].get(
            "excluded", r["verdict"])
        L.append(f"- {r['ticker']}: {r['verdict']} — {why}")
    (OUT / "admission_report_phaseA.md").write_text("\n".join(L) + "\n")
    (OUT / "admission_detail_phaseA.json").write_text(json.dumps(
        {"as_of": AS_OF, "manifest_hash": mhash, "report": report},
        indent=1, default=str))

    # identity rows (tier='shadow') + lineage via the P2 spine path
    import psycopg2
    from yuclaw_identity_spine import DDL, _iid, _sid  # noqa: F401
    with psycopg2.connect("dbname=yuclaw_events") as cn:
        with cn.cursor() as cur:
            for p in admitted:
                iid = _iid(p["cik"], p["ticker"])
                cur.execute("""INSERT INTO issuer_identity (issuer_id, cik,
                    legal_name, country, filer_class, sic_code, sic_desc,
                    source) VALUES (%s,%s,%s,%s,%s,%s,%s,
                    'u350_phaseA_admission')
                    ON CONFLICT (issuer_id) DO NOTHING""",
                            (iid, p["cik"], p["name"], p.get("country"),
                             p["filer_class"], p.get("sic"), None))
                sid = _sid(p["ticker"], p["exchange"])
                cur.execute("""INSERT INTO security_identity (security_id,
                    issuer_id, ticker, exchange, security_type, tier)
                    VALUES (%s,%s,%s,%s,'common_stock','shadow')
                    ON CONFLICT (security_id) DO NOTHING""",
                            (sid, iid, p["ticker"], p["exchange"]))
                cur.execute("""INSERT INTO corporate_action_lineage
                    (security_id, action_type, effective_date, detail,
                     note_path) VALUES (%s,'shadow_admission',%s,
                    'U350 Phase-A admission per 406a0462bb1f',
                    'internal/u350/admission_report_phaseA.md')""",
                            (sid, AS_OF))
        cn.commit()

    # lock manifest in the u350 namespace
    with u350_connection() as cn:
        with cn.cursor() as cur:
            cur.execute("""INSERT INTO u350.manifest (phase, manifest_hash,
                members) VALUES ('A', %s, %s)
                ON CONFLICT (phase, manifest_hash) DO NOTHING""",
                        (mhash, json.dumps(manifest_members)))
        cn.commit()

    print(f"[select] admitted={len(admitted)} · manifest {mhash[:16]} "
          f"locked in u350.manifest (phase A) · report: "
          f"internal/u350/admission_report_phaseA.md")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit({"resolve": cmd_resolve, "enrich": cmd_enrich,
              "prices": cmd_prices, "select": cmd_select}.get(
        cmd, lambda: (print("usage: resolve|enrich|prices|select"), 2)[1])())
