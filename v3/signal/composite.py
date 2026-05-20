"""
Composite signal orchestrator.

Runs all nine components (C1–C9) and combines them via the locked
confidence-weighted formula:

    total_score = sum(weight[i] * score[i] * confidence[i])
                / sum(weight[i] * confidence[i])

Stubs return ComponentResult(not_implemented=True, confidence=0.0). They
contribute 0 to numerator and 0 to denominator, so they vanish from the
average rather than dragging it toward zero. As long as ONE non-stub
component has non-zero confidence the composite is well-defined; if every
component has zero confidence the result is total_score=0.0 with
composite_confidence=0.0 (and we mark it explicitly).

CLI:
    python3 -m v3.signal.composite --ticker NVDA
    python3 -m v3.signal.composite --ticker NVDA --as-of 2026-05-19
    python3 -m v3.signal.composite --ticker NVDA --json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

_log = logging.getLogger("yuclaw.composite")

from v3.signal.base import (
    COMPONENT_WEIGHTS,
    ComponentResult,
    SignalComponent,
    signal_label,
)
from v3.signal.components.c1_momentum import C1Momentum
from v3.signal.components.c2_volume import C2VolumeConfirmation
from v3.signal.components.c3_sector_velocity import C3SectorVelocity
from v3.signal.components.c4_macro import C4MacroRegime
from v3.signal.components.c5_oil_rates_fx import C5OilRatesFX
from v3.signal.components.c6_event_impact import C6EventImpact
from v3.signal.components.c7_peer_correlation import C7PeerCorrelation
from v3.signal.components.c8_cascade_impact import C8CascadeEffect
from v3.signal.components.c9_model_trust import C9ModelTrust
from v3.signal.data_loader import fetch_events, load_v2_state


def _build_components() -> dict[str, SignalComponent]:
    """Instantiate one of each component, keyed by component_id."""
    return {
        "c1": C1Momentum(),
        "c2": C2VolumeConfirmation(),
        "c3": C3SectorVelocity(),
        "c4": C4MacroRegime(),
        "c5": C5OilRatesFX(),
        "c6": C6EventImpact(),
        "c7": C7PeerCorrelation(),
        "c8": C8CascadeEffect(),
        "c9": C9ModelTrust(),
    }


def compose_at(ticker: str, as_of: datetime, conn: Any = None) -> dict[str, Any]:
    """Run all nine components AT a specific point in time.

    Every component receives `as_of` and is responsible for filtering its
    inputs by it. C6 / C8 / C9 are genuinely point-in-time (they query the
    events / signal_snapshots / track_record tables with `available_as_of
    <= as_of` filters). C1 / C3 / C4 / C5 / C7 read v2.3.0 dashboard_state
    which has no history — they detect a historical as_of via
    data_loader.is_historical() and self-degrade to confidence 0.3 with a
    "point-in-time approximation" warning.

    `conn` is accepted for API symmetry with replay/snapshot writers — the
    individual components open their own short-lived connections via DB_DSN
    so this argument is currently informational. Day 5+ optimization will
    thread it through to avoid the open/close-per-component cost.

    Result shape:
        {
            "ticker":               "NVDA",
            "as_of":                "2026-05-19T13:30:00+00:00",
            "total_score":          0.213,
            "composite_confidence": 0.547,
            "label":                "NEUTRAL",
            "n_implemented":        9,
            "n_stubs":              0,
            "components": { ... }
        }
    """
    ctx: dict[str, Any] = {
        "v2_state": load_v2_state(),
        "events": fetch_events(ticker, as_of),
        "conn": conn,
    }

    components = _build_components()
    results: dict[str, ComponentResult] = {}
    errored: list[str] = []
    for cid, comp in components.items():
        try:
            results[cid] = comp.score(ticker, as_of, ctx)
        except Exception as e:
            # A broken component should NOT poison the composite — but we
            # must NOT swallow the error silently either. Day-7→13b: C9
            # raised UndefinedColumn for six days and nobody noticed because
            # the rationale string was the only surface. Now we also:
            #   1. Log via the standard logger with a traceback.
            #   2. Mark the ComponentResult with `errored=True` in details
            #      so downstream surfaces (healthcheck, why CLI, MCP) can
            #      distinguish a real error from a legitimate confidence=0.
            _log.error(
                "component %s raised on (%s, %s): %s\n%s",
                cid, ticker, as_of, e, traceback.format_exc(),
            )
            errored.append(cid)
            results[cid] = ComponentResult(
                component=cid,
                score=0.0,
                confidence=0.0,
                rationale=f"component error: {type(e).__name__}: {str(e)[:120]}",
                not_implemented=False,
                details={"errored": True, "error_type": type(e).__name__,
                         "error_msg": str(e)[:200]},
            )

    # Confidence-weighted average
    num = 0.0
    den = 0.0
    for cid, r in results.items():
        if r.not_implemented:
            continue
        w = COMPONENT_WEIGHTS[cid]
        num += w * r.score * r.confidence
        den += w * r.confidence

    total = num / den if den > 0 else 0.0
    composite_conf = den

    n_impl = sum(1 for r in results.values() if not r.not_implemented)
    n_stub = sum(1 for r in results.values() if r.not_implemented)

    return {
        "ticker": ticker.upper(),
        "as_of": as_of.isoformat(),
        "total_score": round(total, 4),
        "composite_confidence": round(composite_conf, 4),
        "label": signal_label(total),
        "n_implemented": n_impl,
        "n_stubs": n_stub,
        "errored_components": errored,
        "components": {cid: r.to_dict() for cid, r in results.items()},
    }


def compute(ticker: str, as_of: datetime | None = None) -> dict[str, Any]:
    """Back-compat alias. Day 4 callers (snapshot_writer) keep working
    unchanged. New code should use compose_at()."""
    if as_of is None:
        as_of = datetime.now(timezone.utc)
    return compose_at(ticker, as_of)


def _format_human(out: dict[str, Any]) -> str:
    lines = [
        f"ticker:               {out['ticker']}",
        f"as_of:                {out['as_of']}",
        f"label:                {out['label']}",
        f"total_score:          {out['total_score']:+.4f}",
        f"composite_confidence: {out['composite_confidence']:.4f}",
        f"implemented:          {out['n_implemented']} / 9  (stubs: {out['n_stubs']})",
        "",
        "components:",
    ]
    for cid in ("c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9"):
        c = out["components"][cid]
        flag = "STUB" if c["not_implemented"] else "    "
        lines.append(
            f"  {flag} {cid}  score={c['score']:+.3f}  conf={c['confidence']:.2f}  "
            f"weight={COMPONENT_WEIGHTS[cid]:.2f}  — {c['rationale']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="v3.0 composite signal (C1–C9)")
    p.add_argument("--ticker", required=True)
    p.add_argument("--as-of", help="YYYY-MM-DD or ISO timestamp (default: now)")
    p.add_argument("--json", action="store_true", help="emit JSON instead of human-readable")
    args = p.parse_args(argv)

    as_of: datetime | None = None
    if args.as_of:
        try:
            if "T" in args.as_of:
                as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
            else:
                as_of = datetime.strptime(args.as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"invalid --as-of: {args.as_of}", file=sys.stderr)
            return 2

    out = compute(args.ticker.upper(), as_of)
    if args.json:
        print(json.dumps(out, indent=2, default=str))
    else:
        print(_format_human(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
