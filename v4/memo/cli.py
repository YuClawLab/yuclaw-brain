"""CLI: python3 -m v3.cli memo TICKER [--as-of DATE] [--include-score] [--n-evidence N] [--json]

Score is OFF by default for memos (Q5 — memos read as research prose, not data dumps);
pass --include-score to surface numeric scores.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from typing import Optional

from v4.memo.generator import MEMO_N_EVIDENCE, MEMO_N_EVIDENCE_MAX, generate_memo


def _parse_as_of(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    # Bare date → end of that day (captures that day's intraday snapshot).
    if len(raw) == 10 and raw.count("-") == 2:
        raw = f"{raw}T23:59:59-06:00"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise SystemExit(f"--as-of must be YYYY-MM-DD or ISO-8601: {raw!r}")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="yuclaw memo", description="Generate a v4 research memo.",
        epilog="pip 5.0.x ships this earlier memo interface (positional TICKER, "
               "--as-of). The evidence-memo CLI (--ticker/--days, "
               "citation-verified) ships in v5.1.")
    p.add_argument("ticker")
    p.add_argument("--as-of", help="YYYY-MM-DD (or ISO-8601) point-in-time replay")
    p.add_argument("--include-score", action="store_true",
                   help="surface numeric scores (default off — memos are score-free prose)")
    p.add_argument("--n-evidence", type=int, default=MEMO_N_EVIDENCE,
                   help=f"evidence items (default {MEMO_N_EVIDENCE}, max {MEMO_N_EVIDENCE_MAX})")
    p.add_argument("--json", action="store_true", help="emit MemoOutput JSON instead of Markdown")
    a = p.parse_args(argv)

    try:
        m = generate_memo(a.ticker, as_of=_parse_as_of(a.as_of),
                          include_score=a.include_score, n_evidence=a.n_evidence)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(m.model_dump_json(indent=2) if a.json else m.markdown)
    return 0


if __name__ == "__main__":
    sys.exit(main())
