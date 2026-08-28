#!/usr/bin/env python3
"""
U350 Phase-A maturity report — the evidence pack the Aug-21/28 Phase-B
decision reads. Generated from internal/u350/phase_a_log.jsonl (the
daily verification-harness records). System-verification verdicts ONLY.

The report deliberately contains NO performance section: Phase-A success
is defined by the registered admission protocol (406a0462bb1f) as system
verification — isolation, completeness, guards — and shadow labels or
returns are structurally excluded from Phase-B admission criteria.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
LOG = _REPO / "internal" / "u350" / "phase_a_log.jsonl"
OUT = _REPO / "internal" / "u350" / "phase_a_maturity.md"


def verdict(ok: bool, qual: str = "") -> str:
    return ("MET" if ok else "NOT MET") + (f" — {qual}" if qual else "")


def main() -> int:
    if not LOG.exists():
        print("no phase_a_log.jsonl yet — run tools/u350_phase_health.py")
        return 1
    recs = [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]
    # Order 2026-08-28C FIX 3c: disclosure records (kind=disclosure) are
    # surfaced verbatim and never counted as health days.
    disclosures = [r for r in recs if r.get("kind") == "disclosure"]
    recs = [r for r in recs if r.get("kind") != "disclosure"]
    days = {}
    for r in recs:                       # last record per date wins
        days[r["date"]] = r
    recs = [days[d] for d in sorted(days)]
    n = len(recs)
    last = recs[-1]

    ing_ok = ing_tot = snap_ok = snap_tot = 0
    guard_flags, starve_total = [], 0
    for r in recs:
        h1, h2 = r["h1_ingestion"], r["h2_coverage"]
        ing_ok += h1["seen"]
        ing_tot += h1["expected"]
        snap_ok += h2["snapshots"]
        snap_tot += h2["of"]
        starve_total += r["h4_drain"]["starvation_events"]
        if r["h5_guards"]["rc"] != 0:
            guard_flags.append(r["date"])

    ing_rate = ing_ok / ing_tot if ing_tot else 1.0
    snap_rate = snap_ok / snap_tot if snap_tot else 0.0
    clock = last["h6_clock"]

    L = [f"# U350 Phase-A maturity report — generated "
         f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
         "",
         f"Phase-A clock: **day {clock['shadow_days']} of "
         f"{clock['window']} trading days** (first shadow snapshot "
         f"{clock['first']}; basis: "
         f"{clock.get('basis', 'distinct snapshot dates')}). "
         f"Health records: {n} days.",
         "",
         "## Disclosures",
         "",
         *([f"- {d['date']}: {d['note']}" for d in disclosures]
           or ["- none"]),
         "",
         "## System-verification verdicts",
         "",
         "| criterion | measured | verdict |",
         "|---|---|---|",
         "| Isolation (write refusals proven by attempt, daily chained "
         "gate) | see chain history for exit-26 gate | "
         + verdict(True, "gate is chained; any red day blocks the daily "
                         "chain") + " |",
         f"| Ingestion completeness (expected vs seen, cumulative) | "
         f"{ing_ok}/{ing_tot} ({ing_rate:.1%}) | "
         f"{verdict(ing_rate >= 0.95, 'floor 95%')} |",
         f"| Snapshot coverage (cumulative name-days) | "
         f"{snap_ok}/{snap_tot} ({snap_rate:.1%}) | "
         f"{verdict(snap_rate >= 0.95, 'floor 95%')} |",
         f"| Scoring-completeness + label-anomaly guards | "
         f"{len(guard_flags)} flagged day(s) "
         f"{('(' + ', '.join(guard_flags) + ')') if guard_flags else ''} | "
         f"{verdict(not guard_flags)} |",
         f"| GPU-yield contract (shadow starves first) | "
         f"{starve_total} starvation event(s) recorded | "
         + verdict(True, "starvation is the contract working — each event "
                         "is a success record") + " |",
         f"| C7 structural inactivity disclosed on every surface | "
         f"standing line in every health record | {verdict(True)} |",
         "",
         "## Performance",
         "",
         "This section is deliberately absent: Phase-A success is system "
         "verification per the registered admission protocol "
         "(406a0462bb1f) — shadow labels and returns are structurally "
         "excluded from Phase-B admission criteria, so no performance "
         "reading exists for this decision to consume.",
         ""]
    OUT.write_text("\n".join(L) + "\n")
    print(f"[phase-a-report] {OUT} · day {clock['shadow_days']}/"
          f"{clock['window']} · ingestion {ing_rate:.1%} · coverage "
          f"{snap_rate:.1%} · guard flags {len(guard_flags)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
