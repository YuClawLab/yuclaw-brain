#!/usr/bin/env python3
"""
Weekly-note reconciliation gate (P0.4, 2026-08-01). Recomputes every count
in the published weekly note from the registry and the evidence store for
the note's own window (parsed from the page) and FAILS THE CHAIN on any
mismatch — the note can never disagree with the chain again.
Exit 0 = reconciled; 1 = mismatch; 0 with note "absent" when no note exists.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

NOTE = _REPO / "docs" / "weekly_note.html"


def main() -> int:
    if not NOTE.exists():
        print("[note-gate] no weekly note present — nothing to reconcile")
        return 0
    h = NOTE.read_text()
    mw = re.search(r"week of (\d{4}-\d{2}-\d{2}) → (\d{4}-\d{2}-\d{2})", h)
    if not mw:
        print("[note-gate] FAIL: cannot parse the note's window")
        return 1
    start, end = date.fromisoformat(mw.group(1)), date.fromisoformat(mw.group(2))

    m = re.search(r"(\d+) events accepted into the evidence store in the "
                  r"window\s*\((\d+) on scoring-universe names, (\d+) on "
                  r"evidence-tier", h)
    mr = re.search(r"(\d+) recorded runs this week", h)
    if not m or not mr:
        print("[note-gate] FAIL: cannot parse the note's counts")
        return 1
    note_total, note_canon, note_tier = map(int, m.groups())
    note_runs = int(mr.group(1))
    note_protos = len(re.findall(r"<li>(?!none)[^<]*</li>",
                     h.split("New protocols:")[1].split("Supersessions:")[0])) \
        if "New protocols:" in h else -1
    note_sups = len(re.findall(r"<li><code>", h))

    import psycopg2
    from v3.lab.cohort_engine import DSN
    from v3.universe_tiers import evidence_tier_tickers, scoring_universe
    ev_canon = ev_tier = 0
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("""SELECT ticker, count(*) FROM events
                WHERE event_status='accepted'
                  AND created_at::date BETWEEN %s AND %s GROUP BY 1""",
                        (start, end))
            tier, canon = evidence_tier_tickers(), scoring_universe()
            for tk, n in cur.fetchall():
                if tk in tier:
                    ev_tier += n
                elif tk in canon:
                    ev_canon += n
    from yuclaw_protocol_registry import Registry
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    s, e = start.isoformat(), end.isoformat()
    chk_protos = sum(1 for l in reg._lines if l["kind"] == "protocol"
                     and s <= l["payload"]["lock_date"] <= e)
    chk_runs = sum(1 for l in reg._lines if l["kind"] == "run"
                   and s <= l["payload"]["run_date"] <= e)
    chk_sups = sum(1 for l in reg._lines if l["kind"] == "supersede_notice"
                   and s <= l["payload"]["date"] <= e)

    problems = []
    if (ev_canon, ev_tier, ev_canon + ev_tier) != (note_canon, note_tier,
                                                   note_total):
        problems.append(f"events: note {note_canon}+{note_tier}={note_total} "
                        f"vs store {ev_canon}+{ev_tier}={ev_canon + ev_tier}")
    if note_runs != chk_runs:
        problems.append(f"runs: note {note_runs} vs registry {chk_runs}")
    if note_protos >= 0 and note_protos != chk_protos:
        problems.append(f"protocols: note {note_protos} vs registry {chk_protos}")
    if note_sups != chk_sups:
        problems.append(f"supersessions: note {note_sups} vs registry {chk_sups}")
    if problems:
        print("[note-gate] FAIL — note disagrees with the chain:")
        for pr in problems:
            print(f"  · {pr}")
        return 1
    print(f"[note-gate] reconciled: {note_total} events "
          f"({note_canon}/{note_tier}), {chk_protos} protocols, "
          f"{chk_runs} runs, {chk_sups} supersessions for {start}..{end}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
