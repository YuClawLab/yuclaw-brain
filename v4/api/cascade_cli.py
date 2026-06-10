"""CLI: python3 -m v3.cli cascade TICKER [--as-of DATE] [--depth N] [--json]

Cascade History View — the supply-chain chain(s) that propagated INTO a ticker,
as known at a point in time. Edge weights are the public supply_chain.py values.
"""
from __future__ import annotations

import argparse
import html
import sys
from datetime import datetime, timezone
from typing import Optional

import click

from v4.api.cascade_builder import MAX_DEPTH, build_cascade
from v4.api.schema import CascadeNode


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


def render(node: CascadeNode, ticker: str) -> str:
    e = node.event
    out = [click.style(f"  Cascade into {ticker.upper()}", fg="cyan", bold=True)]
    out.append(click.style(f"  Root: {e.event_type.replace('_',' ').title()} "
                           f"({e.event_id.split('_')[0]}, {e.available_as_of.date()})", bold=True))
    if e.raw_excerpt:
        ex = html.unescape(e.raw_excerpt).strip()
        out.append(f"    > {ex[:140]}")
    prov = f"    [source]({e.source_url})"
    if e.accession_number:
        prov += f" · accession {e.accession_number}"
    prov += f" · ledger {e.ledger_hash[:12]}…"
    out.append(prov)
    out.append("")
    out.append(click.style("  Propagation (depth · edge · weight × decay → contribution):", bold=True))
    for edge in node.edges:
        sign = "−" if edge.relationship_type == "peer" else "+"
        line = (f"   d{edge.depth}  "
                + click.style(f"{edge.parent_ticker} → {edge.child_ticker}", fg="green")
                + f"   {edge.relationship_type} (sign {sign})  "
                + f"w={edge.edge_weight:g} × decay {edge.decay_factor:g} "
                + click.style(f"→ contribution {edge.contribution:.4f}", fg="magenta"))
        out.append(line)
    if node.warnings:
        out.append("")
        for w in node.warnings:
            out.append(click.style(f"  ! {w}", fg="yellow"))
    out.append(click.style("  Edge weights are the public supply_chain.py graph. Research only — not advice.", dim=True))
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw cascade", description="Supply-chain cascade history for a ticker.")
    p.add_argument("ticker")
    p.add_argument("--as-of", help="YYYY-MM-DD (or ISO-8601) point-in-time")
    p.add_argument("--depth", type=int, default=MAX_DEPTH, help=f"max hops 1..{MAX_DEPTH} (default {MAX_DEPTH})")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    node = build_cascade(a.ticker, as_of=_parse_as_of(a.as_of), depth=a.depth)
    if a.json:
        print(node.model_dump_json(indent=2) if node else "null")
    elif node is None:
        click.secho(f"  No supply-chain cascade reached {a.ticker.upper()} "
                    f"{'as of ' + a.as_of if a.as_of else ''}.", fg="yellow")
    else:
        print(render(node, a.ticker))
    return 0


if __name__ == "__main__":
    sys.exit(main())
