"""
Time Machine Replay engine.

Calls compose_at() with a historical as_of, then persists the result via
snapshot_writer.write_snapshot (which already stamps is_backfill=True for
as_ofs older than 24h). The function returns the same dict shape that
the CLI / dashboard expect.

Why this exists separately from compose_at:
  - compose_at is the pure computation.
  - replay() also persists, applies the look-ahead-bias check on the date
    boundary, and is the single seam the CLI uses.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2

from v3.signal.composite import compose_at
from v3.signal.snapshot_writer import write_snapshot
from v3.sources.edgar_poll import DB_DSN

# Llama 3.1 70B training cutoff ≈ mid-2024. Replays for dates before this
# are NOT out-of-sample for the LLM, even if our deterministic Form 4
# parser + cascade engine are still point-in-time correct. The CLI surfaces
# this caveat explicitly.
LLAMA_31_TRAINING_CUTOFF = datetime(2024, 7, 1, tzinfo=timezone.utc)


def _ensure_aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def replay(ticker: str, as_of: datetime, conn: Optional[Any] = None) -> dict[str, Any]:
    """Run a point-in-time replay for `ticker` at `as_of`.

    1. compose_at(ticker, as_of) — components filter by as_of
    2. write_snapshot(ticker, as_of) — persists with is_backfill flag
    3. enrich the result with a look_ahead_bias flag if as_of pre-dates the
       Llama training cutoff.

    `conn` is currently unused (compose_at + write_snapshot open their own
    connections via DB_DSN); the parameter is kept for API symmetry so
    future callers can thread a connection through without a signature
    change.

    Returns a dict combining the composite output + replay metadata.
    """
    as_of = _ensure_aware(as_of)
    result = compose_at(ticker, as_of, conn=conn)

    # Persist so this replay is queryable by `yuclaw why TICKER --as-of`.
    # write_snapshot sets is_backfill=True automatically when as_of is
    # older than 24 hours; for very-recent replays it's False.
    persisted = write_snapshot(ticker, as_of)
    result["snapshot_id"] = persisted["snapshot_id"]

    # Look-ahead bias marker — LLM training cutoff awareness.
    in_llm_training = as_of < LLAMA_31_TRAINING_CUTOFF
    result["replay_metadata"] = {
        "in_llm_training_window": in_llm_training,
        "llm_training_cutoff": LLAMA_31_TRAINING_CUTOFF.isoformat(),
        "note": (
            "WARNING: as_of pre-dates Llama 3.1 70B training cutoff — "
            "extracted events on this date may be in-sample for the LLM."
            if in_llm_training else
            "as_of is out-of-sample relative to LLM training cutoff."
        ),
    }
    return result
