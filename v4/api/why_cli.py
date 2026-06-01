"""CLI: python3 -m v3.cli why TICKER [--as-of DATE] [--include-score] [--n-evidence N] [--json]

v4 structured research signal renderer (ResearchResponse). Score is OFF by default
(Q2/Q4); pass --include-score to surface the composite. Missing data prints a
status='no_data' note, never an error.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from typing import Optional

import click

from v4.api.builder import build_response
from v4.memo.generator import _qual, _signal_human  # reuse the same language


def _parse_as_of(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    # A bare date means "as of the END of that day" so it captures that day's
    # snapshot (signals are stamped intraday), matching `yuclaw verify <date>`.
    if len(raw) == 10 and raw.count("-") == 2:
        raw = f"{raw}T23:59:59-06:00"
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise SystemExit(f"--as-of must be YYYY-MM-DD or ISO-8601: {raw!r}")
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


_GRADE = {"A": "Grade A (strong, corroborated)", "B": "Grade B (adequate)",
          "C": "Grade C (thin / single-source)", "Insufficient": "Insufficient evidence"}


def render(resp, include_score: bool) -> str:
    out: list[str] = []
    sig = _signal_human(resp.signal)
    out.append(click.style(f"  {resp.ticker} — {sig}", fg="cyan", bold=True))
    if resp.status == "no_data":
        out.append(click.style("  status: no_data — " + resp.limitations[0], fg="yellow"))
        out.append(click.style("  " + resp.compliance.notice, fg="white", dim=True))
        return "\n".join(out)
    out.append(f"  Evidence Quality: {_GRADE.get(resp.confidence.grade.value)}")
    if resp.signal_overlay:
        out.append(click.style(f"  ⚠️  {resp.signal_overlay}", fg="red", bold=True))
    if include_score and resp.score is not None:
        out.append(f"  Composite score: {resp.score:+.3f}")
    out.append(click.style(f"  As of {resp.as_of.isoformat()} (point-in-time)", dim=True))
    out.append("")
    out.append(click.style("  Signal anatomy (top drivers):", bold=True))
    impl = sorted([c for c in resp.components if c.implemented and abs(c.score) > 1e-9],
                  key=lambda c: abs(c.score) * c.weight, reverse=True)
    for c in impl[:4]:
        arrow = "↑" if c.score > 0 else "↓"
        col = "green" if c.score > 0 else "red"
        out.append("   " + click.style(f"{arrow} {c.name}", fg=col) + f" — {_qual(c.score)}")
    out.append("")
    out.append(f"  Evidence: {len(resp.evidence)} source events — each with source_url + accession + ledger_hash")
    if resp.ledger_anchor_url:
        out.append("  Ledger: " + click.style(resp.ledger_anchor_url, fg="blue"))
    out.append(click.style("  Research only — not investment advice.", dim=True))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw why", description="v4 structured research signal.")
    p.add_argument("ticker")
    p.add_argument("--as-of", help="YYYY-MM-DD (or ISO-8601) point-in-time replay")
    p.add_argument("--include-score", action="store_true",
                   help="show the composite score (default off — research, not a number)")
    p.add_argument("--n-evidence", type=int, default=10)
    p.add_argument("--json", action="store_true", help="emit the ResearchResponse JSON")
    a = p.parse_args(argv)

    resp = build_response(a.ticker, as_of=_parse_as_of(a.as_of),
                          include_score=a.include_score, n_evidence=a.n_evidence)
    if a.json:
        print(resp.model_dump_json(indent=2))
    else:
        print(render(resp, a.include_score))
    return 0


if __name__ == "__main__":
    sys.exit(main())
