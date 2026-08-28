#!/usr/bin/env python3
"""
U350 Phase-A verification harness (daily, after the shadow pass).
System-verification instrumentation only — no performance measurement
exists anywhere in this file by design.

Checks per run:
  H1 ingestion completeness — filings EXPECTED per shadow CIK (SEC
     submissions, prose forms + Form 4, 2-day lookback — the ingest
     window) vs SEEN in u350.events_raw (by accession number); named
     misses.
  H2 snapshot coverage — today's snapshots x/71 with named misses and a
     best-effort reason (stale shadow price vs scorer failure).
  H3 per-component missingness — today's cross-section; C7 reported on
     its standing STRUCTURALLY_INACTIVE disclosed line, never as a miss.
  H4 drain cost — GPU-minutes estimated from today's extracted events at
     the measured per-form costs, vs the bounded budget (DRAIN_CAP x
     240s); starvation events counted from the shadow log — a starved
     shadow drain is the yield contract WORKING and is recorded as
     success.
  H5 guard statuses — completeness + label-anomaly guard rc.
  H6 Phase-A clock — cumulative distinct shadow days toward 15/20.

Outputs: one JSON line appended to internal/u350/phase_a_log.jsonl and a
dated markdown board section internal/u350/health_<date>.md; prints the
health line. Exit 0 unless a NON-structural failure is present.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import psycopg2

from v3.u350 import SCHEMA, u350_connection
from v3.u350.shadow_ops import (DRAIN_CAP, PROSE_FORMS, UA, shadow_members,
                                sessions_with_rows)
from v3.u350.market_calendar import (latest_completed_session,
                                     session_window_utc)

LOG = _REPO / "internal" / "u350" / "phase_a_log.jsonl"
SHADOW_LOG = _REPO / "services" / "u350_shadow.log"
# measured per-form GPU cost (capacity audit 2026-08-02), seconds
FORM_COST = {"6-K": 242, "8-K": 91, "10-K": 150, "40-F": 244,
             "10-Q": 150, "20-F": 150}


def h1_ingestion(members):
    expected, seen, missing = 0, 0, []
    cutoff = date.fromordinal(date.today().toordinal() - 2).isoformat()
    with u350_connection() as cn:
        with cn.cursor() as cur:
            cur.execute(f"SELECT accession_number FROM {SCHEMA}.events_raw")
            have = {r[0] for r in cur.fetchall()}
    for m in members:
        cik = m.get("cik")
        if not cik:
            continue
        try:
            req = urllib.request.Request(
                f"https://data.sec.gov/submissions/CIK{cik}.json",
                headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                s = json.load(r)
        except Exception as exc:                      # noqa: BLE001
            missing.append({"ticker": m["ticker"],
                            "reason": f"submissions fetch: {exc}"})
            continue
        rec = s.get("filings", {}).get("recent", {})
        for form, acc, fdate in zip(rec.get("form", []),
                                    rec.get("accessionNumber", []),
                                    rec.get("filingDate", [])):
            if fdate < cutoff:
                break
            if form not in PROSE_FORMS:
                continue
            expected += 1
            if acc in have:
                seen += 1
            else:
                missing.append({"ticker": m["ticker"], "form": form,
                                "accession": acc,
                                "reason": "expected filing not in "
                                          "u350.events_raw"})
        time.sleep(0.15)
    return {"expected": expected, "seen": seen, "missing": missing}


def h2_coverage(members):
    tickers = {m["ticker"] for m in members}
    with u350_connection() as cn:
        with cn.cursor() as cur:
            lo, hi = session_window_utc(latest_completed_session())
            cur.execute(f"""SELECT ticker FROM {SCHEMA}.shadow_snapshots
                            WHERE signal_time >= %s AND signal_time < %s""",
                        (lo, hi))
            got = {r[0] for r in cur.fetchall()}
            misses = []
            for tk in sorted(tickers - got):
                cur.execute(f"""SELECT max(trade_date) FROM
                    {SCHEMA}.price_history WHERE ticker=%s""", (tk,))
                last = cur.fetchone()[0]
                stale = (last is None or
                         (date.today() - last).days > 5)
                misses.append({"ticker": tk, "reason":
                               f"shadow price stale (last {last})" if stale
                               else "scorer failure (see shadow log)"})
    return {"snapshots": len(got & tickers), "of": len(tickers),
            "misses": misses}


def h3_components(members):
    with u350_connection() as cn:
        with cn.cursor() as cur:
            lo, hi = session_window_utc(latest_completed_session())
            cur.execute(f"""SELECT components FROM
                {SCHEMA}.shadow_snapshots
                WHERE signal_time >= %s AND signal_time < %s""", (lo, hi))
            rows = [r[0] for r in cur.fetchall()]
    out, n = {}, len(rows)
    for cid in ("c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9"):
        computed = sum(1 for c in rows
                       if (c.get(cid) or {}).get("confidence", 0) > 0)
        out[cid] = {"computed": computed, "of": n}
    out["c7_note"] = ("STRUCTURALLY_INACTIVE for shadow names (cohort map "
                      "is U79-only; extending it would alter U79 scores) — "
                      "disclosed, not a miss")
    return out


def h4_drain():
    with u350_connection() as cn:
        with cn.cursor() as cur:
            cur.execute(f"""SELECT source_type, count(*) FROM
                {SCHEMA}.events WHERE created_at::date = current_date
                GROUP BY 1""")
            per_form = dict(cur.fetchall())
    gpu_s = sum(FORM_COST.get(f, 150) * n for f, n in per_form.items())
    budget_s = DRAIN_CAP * 240
    starved = 0
    if SHADOW_LOG.exists():
        today = date.today().isoformat()
        block = ""
        for chunk in SHADOW_LOG.read_text().split("=== u350 shadow pass "):
            if chunk.startswith(today):
                block = chunk
        starved = len(re.findall(r"yielding to U79", block))
    return {"events_today": per_form, "gpu_minutes": round(gpu_s / 60, 1),
            "budget_minutes": round(budget_s / 60, 1),
            "starvation_events": starved,
            "note": "starvation = the yield contract working (success)"}


def h5_guards():
    r = subprocess.run([sys.executable, "v3/u350/shadow_ops.py", "guards"],
                       cwd=str(_REPO), capture_output=True, text=True)
    return {"rc": r.returncode,
            "tail": (r.stdout or "").strip().splitlines()[-1:]}


def h6_clock():
    # Order 2026-08-28C FIX 3c: distinct NYSE sessions with committed rows;
    # zero-row sessions (2026-08-03) are disclosed, never counted.
    sessions = sessions_with_rows()
    return {"first": str(sessions[0]) if sessions else "None",
            "shadow_days": len(sessions), "window": "15-20",
            "session": str(latest_completed_session()),
            "basis": "distinct trading sessions with committed rows"}


def main() -> int:
    members = shadow_members()
    rec = {"date": date.today().isoformat(),
           "generated": datetime.now(timezone.utc).isoformat(),
           "h1_ingestion": h1_ingestion(members),
           "h2_coverage": h2_coverage(members),
           "h3_components": h3_components(members),
           "h4_drain": h4_drain(),
           "h5_guards": h5_guards(),
           "h6_clock": h6_clock()}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(rec) + "\n")

    h1, h2 = rec["h1_ingestion"], rec["h2_coverage"]
    h4, h5, h6 = rec["h4_drain"], rec["h5_guards"], rec["h6_clock"]
    line = (f"[phase-a-health] day {h6['shadow_days']}/{h6['window']} · "
            f"ingestion {h1['seen']}/{h1['expected']} · snapshots "
            f"{h2['snapshots']}/{h2['of']} · drain "
            f"{h4['gpu_minutes']}min/{h4['budget_minutes']}min budget · "
            f"starvation {h4['starvation_events']} (=yield working) · "
            f"guards {'green' if h5['rc'] == 0 else 'FLAGGED'}")
    print(line)

    md = [f"## U350 Phase-A health — {rec['date']}", "", f"{line}", ""]
    if h1["missing"]:
        md.append(f"Ingestion misses ({len(h1['missing'])}):")
        md += [f"- {m['ticker']}: {m.get('form', '')} {m['reason']}"
               for m in h1["missing"][:20]]
    if h2["misses"]:
        md.append(f"Snapshot misses ({len(h2['misses'])}):")
        md += [f"- {m['ticker']}: {m['reason']}" for m in h2["misses"]]
    md.append(f"- {rec['h3_components']['c7_note']}")
    (_REPO / "internal" / "u350" / f"health_{rec['date']}.md"
     ).write_text("\n".join(md) + "\n")

    hard_fail = (h5["rc"] != 0 or
                 (h2["of"] and h2["snapshots"] / h2["of"] < 0.9))
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
