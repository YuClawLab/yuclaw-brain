"""
`yuclaw verify TICKER --date YYYY-MM-DD` — confirm a published signal
hasn't been edited since the Verified Research Ledger entry was committed.

This checks RECORD INTEGRITY and TIMING — it does NOT validate that the
signal was correct or profitable.

CLI:
    python3 -m v3.cli verify NVDA --date 2026-05-20
    python3 -m v3.cli verify NVDA --date 2026-05-20 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from v3.proof.verify import verify


STATUS_DISPLAY = {
    "VERIFIED":           "OK  VERIFIED: signal unaltered since ledger commit",
    "INTEGRITY_FAILURE":  "FAIL INTEGRITY: snapshot differs from ledger record",
    "NOT_FOUND":          "WARN no ledger entry",
    "INVALID_DATE":       "ERR  invalid date",
}


def _format_text(r: dict) -> str:
    head = STATUS_DISPLAY.get(r["status"], r["status"])
    lines = [f"{head}   {r['ticker']} @ {r['date']}"]
    if r["status"] == "VERIFIED":
        commit = r.get("commit") or {}
        if commit.get("commit"):
            lines.append(f"  ledger commit:   {commit['commit']}  ({commit['committed_at']})")
        lines.append(f"  ledger label:    {r.get('ledger_label')}  "
                     f"(current: {r.get('current_label')})")
        lines.append(f"  content_hash:    {r.get('ledger_hash')}")
    elif r["status"] == "INTEGRITY_FAILURE":
        lines.append(f"  ledger label:    {r.get('ledger_label')}  "
                     f"vs current: {r.get('current_label')}")
        if r.get("ledger_hash") and r.get("recomputed_hash"):
            lines.append(f"  ledger_hash:     {r['ledger_hash']}")
            lines.append(f"  recomputed_hash: {r['recomputed_hash']}")
        if r.get("detail"):
            lines.append(f"  detail:          {r['detail']}")
    else:
        if r.get("detail"):
            lines.append(f"  {r['detail']}")
    lines.append("")
    lines.append(r["note"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw verify",
                                description="Check a signal against the Verified Research Ledger")
    p.add_argument("ticker")
    p.add_argument("--date", required=True, help="YYYY-MM-DD (UTC)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    result = verify(args.ticker, args.date)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(_format_text(result))
    return 0 if result["status"] == "VERIFIED" else 1


if __name__ == "__main__":
    sys.exit(main())
