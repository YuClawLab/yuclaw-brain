"""
Snapshot writer — materializes a signal_snapshots row per (ticker, as_of).

Walks the v3.0 universe, calls the composite orchestrator for each ticker,
and INSERTs one row into signal_snapshots. Each ticker is its own
transaction so a single failure doesn't poison the run.

CLI:
    python3 -m v3.signal.snapshot_writer
    python3 -m v3.signal.snapshot_writer --ticker NVDA
    python3 -m v3.signal.snapshot_writer --as-of 2026-05-19T13:00:00Z
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg2

from v3.signal.composite import compute
from v3.sources.edgar_poll import DB_DSN

UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "universe.json"

COMPLIANCE_PAYLOAD = {
    "not_financial_advice": True,
    "research_only": True,
    "no_execution_recommendation": True,
    "version": "v3.0",
}

# A snapshot is "backfill" if its as_of is older than this — purely for
# distinguishing live cron writes vs. historical re-runs in analytics.
LIVE_WINDOW_HOURS = 24


def _load_universe() -> list[str]:
    u = json.loads(UNIVERSE_PATH.read_text())
    return sorted(set(u["equities"] + u["sector_etfs"] + u["broad_etfs"] + u["macro"]))


def _snapshot_id(ticker: str, as_of_iso: str) -> str:
    payload = f"{ticker}|{as_of_iso}|v3.0"
    return f"snap_{ticker}_{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _content_hash(snapshot_id: str, total: float, component_scores: dict[str, float]) -> str:
    parts = [snapshot_id, f"{total:.6f}"]
    for cid in sorted(component_scores):
        parts.append(f"{cid}={component_scores[cid]:.6f}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _evidence_event_ids(components: dict[str, Any]) -> list[str]:
    """Collect event_ids that fed C6 and C8 (the event-driven components).

    These are what `yuclaw why` will surface as the evidence trail. C8 events
    are cascade children — their parent_event_id is the upstream root.
    """
    ids: list[str] = []
    for cid in ("c6", "c8"):
        comp = components.get(cid)
        if not comp:
            continue
        details = comp.get("details", {}) or {}
        for key in ("top_contributors", "top_cascades"):
            for c in details.get(key, []) or []:
                if isinstance(c, dict) and c.get("event_id"):
                    ids.append(c["event_id"])
    # de-dupe but preserve order
    seen = set()
    return [x for x in ids if not (x in seen or seen.add(x))]


def write_snapshot(ticker: str, as_of: datetime) -> dict[str, Any]:
    """Compute composite + INSERT one row. Returns the result dict + status."""
    result = compute(ticker, as_of)
    as_of_iso = as_of.isoformat()
    snap_id = _snapshot_id(ticker, as_of_iso)

    components_scores = {cid: c["score"] for cid, c in result["components"].items()}
    ch = _content_hash(snap_id, result["total_score"], components_scores)
    evidence_ids = _evidence_event_ids(result["components"])

    is_backfill = as_of < (datetime.now(timezone.utc) - timedelta(hours=LIVE_WINDOW_HOURS))

    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO signal_snapshots (
                       snapshot_id, ticker, signal_time, available_as_of,
                       signal_label, total_score,
                       c1_price_momentum, c2_volume_confirm, c3_sector_velocity,
                       c4_macro_regime, c5_oil_rates_fx, c6_event_impact,
                       c7_peer_correlation, c8_cascade_effect, c9_model_trust,
                       evidence_event_ids, content_hash, compliance_payload,
                       is_backfill
                   ) VALUES (
                       %s, %s, %s, %s,
                       %s, %s,
                       %s, %s, %s,
                       %s, %s, %s,
                       %s, %s, %s,
                       %s, %s, %s,
                       %s
                   )
                   ON CONFLICT (snapshot_id) DO NOTHING""",
                (
                    snap_id, ticker.upper(), as_of, as_of,
                    result["label"], result["total_score"],
                    components_scores["c1"], components_scores["c2"], components_scores["c3"],
                    components_scores["c4"], components_scores["c5"], components_scores["c6"],
                    components_scores["c7"], components_scores["c8"], components_scores["c9"],
                    evidence_ids if evidence_ids else None,
                    ch, json.dumps(COMPLIANCE_PAYLOAD),
                    is_backfill,
                ),
            )
            conn.commit()
    finally:
        conn.close()
    return {
        "snapshot_id": snap_id,
        "ticker": ticker.upper(),
        "label": result["label"],
        "total_score": result["total_score"],
        "n_evidence_ids": len(evidence_ids),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="v3.0 signal snapshot writer")
    p.add_argument("--ticker", help="single ticker (default: full universe)")
    p.add_argument("--as-of", help="YYYY-MM-DD or ISO (default: now)")
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
    if as_of is None:
        as_of = datetime.now(timezone.utc)

    tickers = [args.ticker.upper()] if args.ticker else _load_universe()
    print(f"[snapshot_writer] {len(tickers)} ticker(s) at {as_of.isoformat()}", flush=True)

    grand = {"ok": 0, "errors": 0, "by_label": {}}
    for t in tickers:
        try:
            r = write_snapshot(t, as_of)
            grand["ok"] += 1
            grand["by_label"][r["label"]] = grand["by_label"].get(r["label"], 0) + 1
            print(f"  {t}: {r['label']:>15s}  score={r['total_score']:+.4f}  "
                  f"evidence_ids={r['n_evidence_ids']}", flush=True)
        except Exception as e:
            grand["errors"] += 1
            print(f"  {t}: ERROR  {type(e).__name__}: {str(e)[:120]}",
                  file=sys.stderr, flush=True)

    print(f"[snapshot_writer] DONE: {grand}", flush=True)
    return 0 if grand["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
