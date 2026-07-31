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


def _main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw memo", description="Generate a v4 research memo.")
    p.add_argument("ticker", nargs="?", default=None,
                   help="positional: legacy signal memo for a scored ticker")
    p.add_argument("--ticker", dest="evidence_ticker", metavar="TICKER",
                   help="EVIDENCE MEMO (usefulness build): what changed in this "
                        "name's filings evidence — deterministic table + grounded, "
                        "citation-verified narrative. Works for evidence-tier names.")
    p.add_argument("--days", type=int, default=30,
                   help="evidence-memo window in days (default 30)")
    p.add_argument("--as-of", help="YYYY-MM-DD (or ISO-8601) point-in-time replay")
    p.add_argument("--include-score", action="store_true",
                   help="surface numeric scores (default off — memos are score-free prose)")
    p.add_argument("--n-evidence", type=int, default=MEMO_N_EVIDENCE,
                   help=f"evidence items (default {MEMO_N_EVIDENCE}, max {MEMO_N_EVIDENCE_MAX})")
    p.add_argument("--json", action="store_true", help="emit MemoOutput JSON instead of Markdown")
    a = p.parse_args(argv)

    if a.evidence_ticker:
        # Evidence memo — on-demand only; the one GPU touchpoint, via gpu-lock.
        from v4.memo.evidence_memo import MemoGenerationError, generate_evidence_memo
        try:
            print(generate_evidence_memo(a.evidence_ticker, days=a.days))
        except MemoGenerationError as e:
            print(f"[memo] generation FAILED (memo not produced): {e}", file=sys.stderr)
            return 1
        return 0

    if not a.ticker:
        p.error("provide a positional TICKER (legacy signal memo) or --ticker (evidence memo)")

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


def main(argv: list[str] | None = None) -> int:
    """5.1.0: friendly no-backend path (exit 3) — the evidence-memo mode
    needs the research backend + box services; the bundled demo path
    (positional ticker) keeps working offline."""
    try:
        return _main(argv)
    except SystemExit:
        raise
    except Exception as exc:                     # noqa: BLE001
        import sys as _s
        try:
            import psycopg2
            db_err = isinstance(exc, psycopg2.OperationalError)
        except Exception:
            db_err = False
        if db_err or isinstance(exc, (FileNotFoundError, ImportError,
                                      RuntimeError)):
            print("backend unavailable: `memo --ticker` builds a "
                  "citation-verified evidence memo from the local research "
                  "backend, which is not present on this machine.\n"
                  f"  detail: {type(exc).__name__}: {str(exc)[:140]}\n"
                  "  offline instead: `yuclaw memo AMD` (bundled demo memo) "
                  "or `yuclaw demo`.", file=_s.stderr)
            return 3
        raise
