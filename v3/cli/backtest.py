"""
`yuclaw backtest` — print both panels (in-sample + forward) with locked
headers, footers, and disclaimer.

CLI:
    python3 -m v3.cli backtest
    python3 -m v3.cli backtest --json
"""
from __future__ import annotations

import argparse
import json
import sys

from v3.track.panels import build_panels, format_text

# Footer text is locked — same string in CLI, HTML, methodology doc, so it's
# trivially auditable that we say the same thing everywhere.
COMPLIANCE_FOOTER = (
    "Research / education only. Not investment advice. Past results — "
    "backtested or forward-tracked — do not predict future performance. "
    "YUCLAW is not a registered investment adviser."
)

POINT_IN_TIME_NOTE = (
    "Note on the in-sample panel: market-data components C1 / C3 / C4 / C5 / C7 "
    "ran at 0.3 confidence because the upstream dashboard cache holds only the "
    "latest snapshot. Evidence components C6 (events), C8 (cascade), C9 (model "
    "trust) are point-in-time exact. The in-sample backtest therefore primarily "
    "reflects the evidence layer."
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw backtest",
                                description="Two-panel backtest + forward-tracking report")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    panels = build_panels()
    if args.json:
        out = {
            "panels": panels,
            "point_in_time_note": POINT_IN_TIME_NOTE,
            "compliance_footer": COMPLIANCE_FOOTER,
        }
        print(json.dumps(out, indent=2, default=str))
        return 0

    print(format_text(panels))
    print()
    print(POINT_IN_TIME_NOTE)
    print()
    print(COMPLIANCE_FOOTER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
