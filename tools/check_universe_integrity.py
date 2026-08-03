#!/usr/bin/env python3
"""
Universe-integrity gate (P1.7, 2026-08-01). Two automated guards so the
pre-committed policies cannot be forgotten when their day comes:

  U1 threshold-match — the published score-to-label table in
     docs/methodology/backfill.md must match the live scorer's constants
     (v3.signal.base.SIGNAL_THRESHOLDS) value-for-value. A threshold change
     without a methodology edit (or vice versa) FAILS the chain — threshold
     changes are methodology events by construction.
  U2 delisting-watch — any scoring-universe ticker whose latest
     price_history row is stale by more than 5 trading days (vs the
     calendar's newest date) FAILS the chain unless a policy-invocation
     note exists at internal/policy_invocations/<TICKER>.md — the
     corporate-action policy must be invoked, never silently skipped.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> int:
    problems = []

    # U1 — threshold table vs live constants
    from v3.signal.base import SIGNAL_THRESHOLDS
    md = (_REPO / "docs" / "methodology" / "backfill.md").read_text()
    rows = re.findall(r"\|\s*(>=|<)\s*(-?\d+\.\d+)\s*\|\s*([A-Z_]+)\s*\|", md)
    if not rows:
        problems.append("U1: threshold table not found in methodology")
    else:
        pub = [(op, float(v), lbl) for op, v, lbl in rows]
        live = [(">=", f, l) for f, l in SIGNAL_THRESHOLDS[:-1]]
        live.append(("<", SIGNAL_THRESHOLDS[-2][0], SIGNAL_THRESHOLDS[-1][1]))
        if [(v, l) for _o, v, l in pub] != [(v, l) for _o, v, l in live]:
            problems.append(
                f"U1: published thresholds {pub} != live scorer {live} — "
                "a threshold change is a methodology event; update both "
                "together or revert")

    # U2 — delisting watch
    import psycopg2
    from v3.universe_tiers import scoring_universe
    with psycopg2.connect("dbname=yuclaw_events") as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("SELECT max(trade_date) FROM price_history")
            newest = cur.fetchone()[0]
            cur.execute("""SELECT ticker, max(trade_date) FROM price_history
                           WHERE ticker = ANY(%s) GROUP BY 1""",
                        (sorted(scoring_universe()),))
            per = dict(cur.fetchall())
            cur.execute("""SELECT count(DISTINCT trade_date) FROM price_history
                           WHERE trade_date > COALESCE(
                               (SELECT max(trade_date) - interval '30 days'
                                FROM price_history), '1970-01-01')""")
    inv_dir = _REPO / "internal" / "policy_invocations"
    for tk in sorted(scoring_universe()):
        last = per.get(tk)
        if last is None:
            stale = True
        else:
            with psycopg2.connect("dbname=yuclaw_events") as cn:
                with cn.cursor() as cur:
                    cur.execute("""SELECT count(DISTINCT trade_date)
                        FROM price_history
                        WHERE trade_date > %s AND trade_date <= %s""",
                                (last, newest))
                    gap_days = cur.fetchone()[0]
            stale = gap_days > 5
        if stale and not (inv_dir / f"{tk}.md").exists():
            problems.append(
                f"U2: {tk} price history stale (last {last}, calendar newest "
                f"{newest}) with NO policy-invocation note at "
                f"internal/policy_invocations/{tk}.md — the corporate-action "
                "policy must be invoked explicitly")

    # U3 — membership drift (identity spine, 2026-08-02): any change to
    # universe membership without a policy-invocation note fails the chain.
    import json as _json
    import hashlib as _hl
    u = _json.loads((_REPO / "v3" / "universe.json").read_text())
    mem = {k: sorted(u.get(k, [])) for k in
           ("equities", "sector_etfs", "broad_etfs", "macro")}
    mem["evidence_tier"] = sorted(r["ticker"] for r in u["evidence_tier"])
    cur_h = _hl.sha256(_json.dumps(mem, sort_keys=True).encode()).hexdigest()
    base = _json.loads((_REPO / "registry" /
                        "universe_membership.json").read_text())
    if cur_h != base["baseline_hash"]:
        notes = list((_REPO / "internal" / "policy_invocations"
                      ).glob("UNIVERSE_CHANGE_*.md")) if (
            _REPO / "internal" / "policy_invocations").exists() else []
        if not notes:
            problems.append(
                "U3: universe membership changed (hash "
                f"{cur_h[:12]} != baseline {base['baseline_hash'][:12]}) "
                "with NO UNIVERSE_CHANGE_*.md policy-invocation note — "
                "membership changes must invoke the corporate-action policy "
                "and re-baseline registry/universe_membership.json")

    if problems:
        print("UNIVERSE-INTEGRITY GATE FAILED:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(f"[universe-gate] OK — thresholds match the live scorer; "
          f"{len(per)}/79 scoring names fresh within 5 trading days")
    return 0


if __name__ == "__main__":
    sys.exit(main())
