"""
Cascade engine — propagate qualifying root events to supply-chain neighbors.

For each unprocessed root event on ticker T:
  - depth-1 children: every out-edge (T → N), child_magnitude
      = parent.magnitude × edge.weight × CASCADE_D1_DECAY (0.20)
  - depth-2 children: every 2-hop path (T → mid → N2), child_magnitude
      = parent.magnitude × w1 × w2 × CASCADE_D2_DECAY (0.04)
  - depth 3+ dropped.

Child events get:
  source_type:    parent.source_type + '-cascade'
  llm_model:      'cascade-engine-v1'
  cascade_depth:  1 or 2
  parent_event_id: parent at depth 1; depth-1-child at depth 2
  content_hash:   sha256(parent_event_id || depth || child_ticker)
                  → re-running is a no-op (idempotency by ON CONFLICT)
  direction:      parent.direction × edge.sign     (peer edges flip sign)
  magnitude:      clamped to (0, 1]; <CASCADE_DE_MINIMIS drops the child

CLI:
    python3 -m v3.signal.cascade_engine
    python3 -m v3.signal.cascade_engine --dry-run
    python3 -m v3.signal.cascade_engine --since 2026-05-01
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.signal.supply_chain import Edge, neighbors, two_hop
from v3.sources.edgar_poll import DB_DSN

# Cascade-eligible event types — anything that has a real supply-chain
# transmission story. Insider trades, exec changes, dividends, buybacks
# don't cascade.
CASCADE_ELIGIBLE_TYPES = {
    "EARNINGS_BEAT", "EARNINGS_MISS",
    "GUIDANCE_RAISE", "GUIDANCE_CUT",
    "M_AND_A_ANNOUNCE", "M_AND_A_CLOSE",
    "REGULATORY_ACTION",
    "CAPACITY_CHANGE",
    "CONTRACT_WIN",
    "PRODUCT_LAUNCH",
    "LAWSUIT",
}

# Locked decay constants.
CASCADE_D1_DECAY = 0.20         # depth-1 children carry 20% × edge.weight
CASCADE_D2_DECAY = 0.04         # depth-2 carries 4% × w1 × w2
CASCADE_CONF_DECAY_PER_HOP = 0.7
CASCADE_DE_MINIMIS = 0.02       # drop depth-2 children below this magnitude
ROOT_MIN_MAGNITUDE = 0.5        # only propagate events with magnitude ≥ 0.5


def _cascade_event_id(parent_event_id: str, depth: int, child_ticker: str) -> str:
    """Deterministic, idempotent event id for cascade children."""
    payload = f"{parent_event_id}|d{depth}|{child_ticker}"
    h = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"CASCADE_{child_ticker}_d{depth}_{h}"


def _cascade_content_hash(parent_event_id: str, depth: int, child_ticker: str) -> str:
    payload = f"cascade|{parent_event_id}|{depth}|{child_ticker}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _clip_magnitude(m: float) -> float:
    return max(0.0, min(1.0, m))


def fetch_roots(conn, since: Optional[datetime] = None) -> list[dict[str, Any]]:
    """Pull cascade-eligible root events that don't yet have children.

    A root is:
      - parent_event_id IS NULL (not itself a cascade child)
      - cascade_depth = 0
      - event_type in CASCADE_ELIGIBLE_TYPES
      - magnitude >= ROOT_MIN_MAGNITUDE
      - has no children yet (event_id not in any other row's parent_event_id)
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT event_id, ticker, event_type, magnitude, direction,
                   event_time, source_publish_time, available_as_of,
                   source_type, source_url, raw_excerpt, llm_confidence
            FROM events
            WHERE parent_event_id IS NULL
              AND cascade_depth = 0
              AND event_type = ANY(%s)
              AND magnitude >= %s
              AND event_status = 'accepted'
              AND (%s::timestamptz IS NULL OR available_as_of >= %s::timestamptz)
              AND event_id NOT IN (
                  SELECT DISTINCT parent_event_id
                  FROM events
                  WHERE parent_event_id IS NOT NULL
              )
            ORDER BY available_as_of DESC
            """,
            (list(CASCADE_ELIGIBLE_TYPES), ROOT_MIN_MAGNITUDE, since, since),
        )
        return list(cur.fetchall())


def _insert_cascade_child(
    cur, parent: dict[str, Any], child_ticker: str, depth: int,
    parent_event_id_for_link: str, magnitude: float, direction: int,
    chain_description: str,
) -> Optional[str]:
    """INSERT one cascade child. Returns event_id if inserted, None on conflict."""
    eid = _cascade_event_id(parent["event_id"], depth, child_ticker)
    ch = _cascade_content_hash(parent["event_id"], depth, child_ticker)

    raw_excerpt = (
        f"CASCADE d{depth} via {chain_description} from "
        f"{parent['ticker']}: {(parent['raw_excerpt'] or '')[:200]}"
    )[:600]
    llm_conf = float(parent.get("llm_confidence") or 0.0) * (
        CASCADE_CONF_DECAY_PER_HOP ** depth
    )

    cur.execute(
        """
        INSERT INTO events (
            event_id, ticker, event_type, magnitude, direction,
            event_time, source_publish_time, source_ingested_time,
            available_as_of, source_type, source_url, raw_excerpt,
            llm_model, llm_confidence, llm_reasoning,
            content_hash, prompt_version, event_status,
            parent_event_id, cascade_depth
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, now(),
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, 'accepted',
            %s, %s
        )
        ON CONFLICT (content_hash, ticker,
                     (date_trunc('day', available_as_of AT TIME ZONE 'UTC')))
        DO NOTHING
        RETURNING event_id
        """,
        (
            eid, child_ticker, parent["event_type"], magnitude, direction,
            parent["event_time"], parent["source_publish_time"],
            parent["available_as_of"],
            (parent["source_type"] or "") + "-cascade",
            parent["source_url"], raw_excerpt,
            "cascade-engine-v1", llm_conf,
            f"Cascade depth {depth} via {chain_description}",
            ch, "cascade-v1",
            parent_event_id_for_link, depth,
        ),
    )
    row = cur.fetchone()
    return row[0] if row else None


def process_root(conn, root: dict[str, Any], dry_run: bool) -> dict[str, int]:
    """Cascade one root. Returns per-root stats."""
    stats = {"d1_created": 0, "d1_existing": 0, "d2_created": 0, "d2_de_minimis": 0}

    parent_mag = float(root["magnitude"])
    parent_dir = int(root["direction"])
    root_ticker = root["ticker"]

    # Map child_ticker → event_id (we link depth-2 children to depth-1 child of mid)
    depth1_event_ids: dict[str, str] = {}

    if dry_run:
        with conn.cursor() as cur:
            pass  # cursor unused in dry-run
    cur = None
    if not dry_run:
        cur = conn.cursor()

    # --- depth 1 ---
    for e1 in neighbors(root_ticker):
        child_mag = _clip_magnitude(parent_mag * e1.weight * CASCADE_D1_DECAY)
        if child_mag <= 0:
            continue
        child_dir = parent_dir * e1.sign
        if dry_run:
            stats["d1_created"] += 1
            depth1_event_ids[e1.target] = "DRY"
            continue
        eid = _insert_cascade_child(
            cur, root, e1.target, depth=1,
            parent_event_id_for_link=root["event_id"],
            magnitude=child_mag, direction=child_dir,
            chain_description=f"{root_ticker}→{e1.target}({e1.kind},w={e1.weight:.2f})",
        )
        if eid is not None:
            stats["d1_created"] += 1
            depth1_event_ids[e1.target] = eid
        else:
            stats["d1_existing"] += 1
            depth1_event_ids[e1.target] = None  # already-existing child; depth-2 links to it via lookup below

    # In the non-dry-run path, fill in event_ids for the already-existing
    # depth-1 children — depth-2 children need a foreign key to *something*.
    if not dry_run and depth1_event_ids:
        missing = [k for k, v in depth1_event_ids.items() if v is None]
        if missing:
            with conn.cursor() as look:
                look.execute(
                    """SELECT ticker, event_id FROM events
                       WHERE parent_event_id = %s AND cascade_depth = 1
                         AND ticker = ANY(%s)""",
                    (root["event_id"], missing),
                )
                for tkr, eid in look.fetchall():
                    depth1_event_ids[tkr] = eid

    # --- depth 2 ---
    for e1, e2 in two_hop(root_ticker):
        if e2.target == root_ticker:
            continue
        child_mag = _clip_magnitude(parent_mag * e1.weight * e2.weight * CASCADE_D2_DECAY)
        if child_mag < CASCADE_DE_MINIMIS:
            stats["d2_de_minimis"] += 1
            continue
        child_dir = parent_dir * e1.sign * e2.sign
        if dry_run:
            stats["d2_created"] += 1
            continue
        # Link depth-2 to its depth-1 ancestor (the child on e1.target)
        parent_link = depth1_event_ids.get(e1.target)
        if parent_link is None or parent_link == "DRY":
            # depth-1 child was conflict-skipped AND we couldn't locate it →
            # fall back to linking directly to the root rather than dropping.
            parent_link = root["event_id"]
        eid = _insert_cascade_child(
            cur, root, e2.target, depth=2,
            parent_event_id_for_link=parent_link,
            magnitude=child_mag, direction=child_dir,
            chain_description=f"{root_ticker}→{e1.target}→{e2.target}",
        )
        if eid is not None:
            stats["d2_created"] += 1

    if cur is not None:
        cur.close()
    return stats


def run(since: Optional[datetime], dry_run: bool) -> dict[str, int]:
    conn = psycopg2.connect(DB_DSN)
    conn.autocommit = False
    grand = {
        "roots_seen": 0, "roots_processed": 0,
        "d1_created": 0, "d1_existing": 0,
        "d2_created": 0, "d2_de_minimis": 0,
    }
    try:
        roots = fetch_roots(conn, since)
        grand["roots_seen"] = len(roots)
        print(f"[cascade] found {len(roots)} cascade-eligible root events"
              f"{' (DRY RUN)' if dry_run else ''}", flush=True)

        for r in roots:
            s = process_root(conn, r, dry_run)
            grand["roots_processed"] += 1
            for k in ("d1_created", "d1_existing", "d2_created", "d2_de_minimis"):
                grand[k] += s[k]
            print(f"[cascade] root {r['event_id']} ({r['ticker']} {r['event_type']} "
                  f"mag={r['magnitude']:.2f} dir={r['direction']:+d}) → "
                  f"d1={s['d1_created']}+{s['d1_existing']}exist  "
                  f"d2={s['d2_created']} (skipped {s['d2_de_minimis']} de minimis)",
                  flush=True)
            if not dry_run:
                conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return grand


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="v3.0 cascade engine")
    p.add_argument("--dry-run", action="store_true",
                   help="show counts, write nothing")
    p.add_argument("--since", help="only process roots with available_as_of >= this date (YYYY-MM-DD)")
    args = p.parse_args(argv)

    since: Optional[datetime] = None
    if args.since:
        try:
            since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"invalid --since: {args.since}", file=sys.stderr)
            return 2

    grand = run(since, args.dry_run)
    print(f"[cascade] DONE: {grand}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
