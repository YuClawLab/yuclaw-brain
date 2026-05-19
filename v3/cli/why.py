"""
`yuclaw why TICKER` — explain why we said what we said.

Reads the most recent signal_snapshots row for the ticker and renders a
locked output format showing per-component contributions and the top
contributing events. Designed for the public `yuclaw why` user surface.

Output contract (don't change without bumping a public version):

    {TICKER} composite score: ±0.XXX  (signal label: LABEL)

    Components (score × weight × confidence):
    C1 Momentum:     ±0.XX  (confidence X.XX, weight 0.12)
                     {one-line rationale}
    ... C2 through C9 ...

    Top contributing events (last 7 days):
      ↑/↓  ±0.XX  YYYY-MM-DD  EVENT_TYPE
                  {raw_excerpt first 80 chars}
                  source: {url}
      ... up to 5 events ...

    Compliance: Research only. Not financial advice. Not a registered
    investment advisor.

CLI:
    python3 -m v3.cli why AMD
    python3 -m v3.cli why AMD --as-of 2026-05-19   # historical snapshot
    python3 -m v3.cli why AMD --json               # machine-readable
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.signal.base import COMPONENT_WEIGHTS
from v3.sources.edgar_poll import DB_DSN

# Display order + human-readable component names (locked).
COMPONENT_NAMES: list[tuple[str, str]] = [
    ("c1", "C1 Momentum"),
    ("c2", "C2 Volume"),
    ("c3", "C3 Sector"),
    ("c4", "C4 Macro"),
    ("c5", "C5 Oil/Rates/FX"),
    ("c6", "C6 Event Impact"),
    ("c7", "C7 Peer Corr"),
    ("c8", "C8 Cascade"),
    ("c9", "C9 Model Trust"),
]

COMPONENT_COLS = {
    "c1": "c1_price_momentum",
    "c2": "c2_volume_confirm",
    "c3": "c3_sector_velocity",
    "c4": "c4_macro_regime",
    "c5": "c5_oil_rates_fx",
    "c6": "c6_event_impact",
    "c7": "c7_peer_correlation",
    "c8": "c8_cascade_effect",
    "c9": "c9_model_trust",
}

COMPLIANCE_FOOTER = (
    "Compliance: Research only. Not financial advice. "
    "Not a registered investment advisor."
)


def _fetch_latest_snapshot(ticker: str, as_of: Optional[datetime]) -> Optional[dict[str, Any]]:
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if as_of:
                cur.execute(
                    """SELECT * FROM signal_snapshots
                       WHERE ticker = %s AND signal_time <= %s
                       ORDER BY signal_time DESC
                       LIMIT 1""",
                    (ticker.upper(), as_of),
                )
            else:
                cur.execute(
                    """SELECT * FROM signal_snapshots
                       WHERE ticker = %s
                       ORDER BY signal_time DESC
                       LIMIT 1""",
                    (ticker.upper(),),
                )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def _fetch_top_events(ticker: str, event_ids: Optional[list[str]], as_of: datetime) -> list[dict[str, Any]]:
    """If we have specific evidence_event_ids, fetch those. Otherwise fall
    back to the highest magnitude*confidence events in the last 7 days."""
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if event_ids:
                cur.execute(
                    """SELECT event_id, event_type, magnitude, direction,
                              available_as_of, raw_excerpt, source_url,
                              llm_confidence, cascade_depth
                       FROM events
                       WHERE event_id = ANY(%s)
                       ORDER BY magnitude * llm_confidence DESC
                       LIMIT 5""",
                    (event_ids,),
                )
            else:
                cur.execute(
                    """SELECT event_id, event_type, magnitude, direction,
                              available_as_of, raw_excerpt, source_url,
                              llm_confidence, cascade_depth
                       FROM events
                       WHERE ticker = %s
                         AND event_status = 'accepted'
                         AND available_as_of <= %s
                         AND available_as_of > %s - INTERVAL '7 days'
                       ORDER BY magnitude * llm_confidence DESC
                       LIMIT 5""",
                    (ticker.upper(), as_of, as_of),
                )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _component_rationale(ticker: str, as_of: datetime, cid: str) -> str:
    """signal_snapshots only stores the score; we need to re-derive rationale.
    Cheap to call compute() lazily ONCE on cache miss; here we just return a
    canned hint based on the score sign + magnitude. Day 5+: persist
    rationale alongside scores in signal_snapshots so this is exact.
    """
    # Placeholder — kept minimal so the output stays stable even if
    # composite logic evolves. The score itself carries the meaning.
    return ""


def render_text(snap: dict[str, Any], events: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    lines.append(f"{snap['ticker']} composite score: {snap['total_score']:+.3f}  "
                 f"(signal label: {snap['signal_label']})")
    lines.append("")
    lines.append("Components (score × weight × confidence):")
    for cid, name in COMPONENT_NAMES:
        score = snap.get(COMPONENT_COLS[cid])
        weight = COMPONENT_WEIGHTS[cid]
        score_disp = f"{score:+.2f}" if score is not None else "  n/a"
        lines.append(f"  {name:<18s} {score_disp}   (weight {weight:.2f})")
    lines.append("")
    if events:
        lines.append("Top contributing events (last 7 days):")
        for ev in events:
            direction = ev.get("direction") or 0
            arrow = "↑" if direction > 0 else ("↓" if direction < 0 else "·")
            mag = float(ev.get("magnitude") or 0.0) * (1 if direction >= 0 else -1)
            dt = ev["available_as_of"]
            dstr = dt.strftime("%Y-%m-%d") if isinstance(dt, datetime) else str(dt)
            type_label = ev.get("event_type", "?")
            if ev.get("cascade_depth"):
                type_label += f" (d{ev['cascade_depth']} cascade)"
            excerpt = (ev.get("raw_excerpt") or "")[:80].replace("\n", " ")
            url = ev.get("source_url") or ""
            lines.append(f"  {arrow}  {mag:+.2f}  {dstr}  {type_label}")
            if excerpt:
                lines.append(f"              {excerpt}")
            if url:
                lines.append(f"              source: {url}")
    else:
        lines.append("Top contributing events: (none in 7-day window)")
    lines.append("")
    lines.append(COMPLIANCE_FOOTER)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw why",
                                description="Explain the latest composite signal")
    p.add_argument("ticker", help="ticker (e.g. NVDA, AMD)")
    p.add_argument("--as-of", help="explain the snapshot ≤ this time (YYYY-MM-DD or ISO)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)

    as_of: Optional[datetime] = None
    if args.as_of:
        try:
            if "T" in args.as_of:
                as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
            else:
                as_of = datetime.strptime(args.as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"invalid --as-of: {args.as_of}", file=sys.stderr)
            return 2

    snap = _fetch_latest_snapshot(args.ticker, as_of)
    if snap is None:
        print(f"no snapshot for {args.ticker.upper()}"
              f"{' ≤ ' + args.as_of if args.as_of else ''}", file=sys.stderr)
        print("(run `python3 -m v3.signal.snapshot_writer` to materialize one)",
              file=sys.stderr)
        return 1

    event_ids = snap.get("evidence_event_ids") or []
    events = _fetch_top_events(args.ticker.upper(), event_ids, snap["signal_time"])

    if args.json:
        out = {**{k: v for k, v in snap.items() if k != "compliance_payload"},
               "compliance_payload": (snap.get("compliance_payload") if isinstance(
                   snap.get("compliance_payload"), dict) else None),
               "evidence": [{
                   "event_id": e["event_id"], "type": e["event_type"],
                   "magnitude": e["magnitude"], "direction": e["direction"],
                   "available_as_of": str(e["available_as_of"]),
                   "raw_excerpt": e.get("raw_excerpt"),
                   "source_url": e.get("source_url"),
                   "cascade_depth": e.get("cascade_depth"),
               } for e in events]}
        print(json.dumps(out, indent=2, default=str))
    else:
        print(render_text(snap, events))

    return 0


if __name__ == "__main__":
    sys.exit(main())
