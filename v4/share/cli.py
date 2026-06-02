"""CLI: python3 -m v3.cli share TICKER [--as-of DATE] [--include-score] [--include-cascade] [--output PATH]

Generates a self-contained, point-in-time-frozen HTML card you can host anywhere.
The card embeds the ledger_hash + ledger_anchor_url + SEC accession numbers, so any
recipient can independently verify the signal. Score and cascade are off by default.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from typing import Optional

from v4.share.generator import generate_share_card


def _parse_as_of(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    if len(raw) == 10 and raw.count("-") == 2:
        raw = f"{raw}T23:59:59-06:00"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise SystemExit(f"--as-of must be YYYY-MM-DD or ISO-8601: {raw!r}")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw share", description="Generate a shareable HTML signal card.")
    p.add_argument("ticker")
    p.add_argument("--as-of", help="YYYY-MM-DD (or ISO-8601) point-in-time freeze")
    p.add_argument("--include-score", action="store_true", help="show the composite score (default off)")
    p.add_argument("--include-cascade", action="store_true", help="include the supply-chain cascade tree")
    p.add_argument("--output", help="output path (default ./share-{TICKER}-{date}.html)")
    a = p.parse_args(argv)

    try:
        path = generate_share_card(
            a.ticker, as_of=_parse_as_of(a.as_of),
            include_score=a.include_score, include_cascade=a.include_cascade,
            output_path=a.output,
        )
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"Card saved to {path}.")
    print("Upload to GitHub Pages, share on X/Reddit, or open locally — "
          "anyone can re-verify the signal at the embedded ledger URL.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
