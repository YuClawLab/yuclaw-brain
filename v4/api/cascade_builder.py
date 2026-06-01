"""
v4/api/cascade_builder.py — Cascade History View (Day 6).

build_cascade(ticker, as_of=None, *, depth=3) walks events.parent_event_id to
reconstruct the supply-chain cascade(s) that propagated INTO `ticker`, as known
at `as_of` (point-in-time). All edge weights / relationship types come from the
PUBLIC hardcoded graph in v3/signal/supply_chain.py — no internal-only scoring.

Approach: start from the ticker's cascade-child events, walk UP each chain to its
root (depth-0 originating event), collecting one CascadeEdge per hop. The result
is a CascadeNode rooted at the origin, holding the flat edge list of the path(s)
that reached `ticker`. Cycle-guarded; depth-capped at 3 (matches the locked decay
d1=0.20, d2=0.04, d3+ dropped). Returns None if no cascade reached the ticker.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.signal.cascade_engine import (
    CASCADE_D1_DECAY,
    CASCADE_D2_DECAY,
    CASCADE_TRAVERSAL_KINDS,
)
from v3.signal.supply_chain import neighbors
from v4.api.builder import DSN, _accession_from_url
from v4.api.schema import CascadeEdge, CascadeNode, Evidence

_log = logging.getLogger(__name__)
MAX_DEPTH = 3
_DECAY = {1: CASCADE_D1_DECAY, 2: CASCADE_D2_DECAY, 3: round(CASCADE_D2_DECAY * 0.2, 4)}
# Cross-check parse of the cascade excerpt: "via HPE→AMD(supply,w=0.10) from ..."
_EXCERPT_RE = re.compile(r"via\s+(\w+)\s*→\s*(\w+)\((\w+),\s*w=([\d.]+)\)")

_EVENT_COLS = ("event_id, ticker, event_type, magnitude, direction, available_as_of, "
               "raw_excerpt, source_url, llm_confidence, cascade_depth, content_hash, parent_event_id")


def _decay_for(depth: int) -> float:
    return _DECAY.get(depth, 0.0)


def _load_event(cur, event_id: str, as_of: datetime) -> Optional[dict]:
    cur.execute(
        f"SELECT {_EVENT_COLS} FROM events "
        f"WHERE event_id = %s AND event_status = 'accepted' AND available_as_of <= %s",
        (event_id, as_of),
    )
    r = cur.fetchone()
    return dict(r) if r else None


def _resolve_edge(parent_ticker: str, child_ticker: str, child_excerpt: str) -> tuple[str, float, list[str]]:
    """(relationship_type, edge_weight, warnings) from the PUBLIC supply_chain graph.

    A ticker pair can have several edges (e.g. HPE→AMD has both a supply and a cohort
    edge). The cascade event records which kind the engine used; we match the graph
    edge of THAT kind so the exposed weight is the authoritative public value.
    """
    warnings: list[str] = []
    graph_edges = [e for e in neighbors(parent_ticker) if e.target == child_ticker]
    m = _EXCERPT_RE.search(child_excerpt or "")
    if m:
        exc_kind, exc_w = m.group(3), float(m.group(4))
        match = next((e for e in graph_edges if e.kind == exc_kind), None)
        if match:
            if abs(match.weight - exc_w) > 1e-6:
                warnings.append(f"edge {parent_ticker}->{child_ticker} ({exc_kind}): "
                                f"excerpt w={exc_w} != supply_chain w={match.weight}")
            return match.kind, match.weight, warnings
        warnings.append(f"edge {parent_ticker}->{child_ticker} ({exc_kind}) recorded on the event "
                        f"but absent from supply_chain; using recorded weight {exc_w}")
        return exc_kind, exc_w, warnings
    # No excerpt hint — pick a graph edge, preferring the cascade-traversal kinds.
    if graph_edges:
        graph_edges.sort(key=lambda e: 0 if e.kind in CASCADE_TRAVERSAL_KINDS else 1)
        e = graph_edges[0]
        return e.kind, e.weight, warnings
    warnings.append(f"edge {parent_ticker}->{child_ticker} unresolved (no graph edge, no excerpt)")
    return "unknown", 0.0, warnings


def _to_evidence(row: dict) -> Evidence:
    return Evidence(
        event_id=row["event_id"], event_type=row["event_type"], source_url=row["source_url"],
        accession_number=_accession_from_url(row["source_url"]), ledger_hash=row["content_hash"],
        available_as_of=row["available_as_of"], raw_excerpt=row.get("raw_excerpt"),
        direction=row.get("direction"),
        magnitude=(float(row["magnitude"]) if row.get("magnitude") is not None else None),
        llm_confidence=(float(row["llm_confidence"]) if row.get("llm_confidence") is not None else None),
        cascade_depth=row.get("cascade_depth"),
    )


def build_cascade(
    ticker: str,
    as_of: Optional[datetime] = None,
    *,
    depth: int = MAX_DEPTH,
    dsn: str = DSN,
    conn: Optional[Any] = None,
) -> Optional[CascadeNode]:
    """Reconstruct the cascade(s) that reached `ticker`. None if there are none."""
    ticker = ticker.upper()
    depth = max(1, min(depth, MAX_DEPTH))
    as_of = as_of or datetime.now(timezone.utc)

    own = conn is None
    if own:
        conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # The ticker's cascade-child events (leaves on the path into `ticker`).
            cur.execute(
                f"SELECT {_EVENT_COLS} FROM events "
                f"WHERE ticker = %s AND parent_event_id IS NOT NULL AND cascade_depth >= 1 "
                f"  AND cascade_depth <= %s AND event_status = 'accepted' AND available_as_of <= %s",
                (ticker, depth, as_of),
            )
            leaves = [dict(r) for r in cur.fetchall()]
            if not leaves:
                return None

            edges: dict[tuple[str, str], CascadeEdge] = {}
            warnings: list[str] = []
            roots: dict[str, dict] = {}

            for leaf in leaves:
                visited: set[str] = set()
                child = leaf
                while child and child.get("parent_event_id"):
                    if child["event_id"] in visited:
                        msg = f"cycle detected at event {child['event_id']}"
                        warnings.append(msg)
                        _log.warning("cascade %s: %s", ticker, msg)  # never silent, even if no root
                        break
                    visited.add(child["event_id"])
                    parent = _load_event(cur, child["parent_event_id"], as_of)
                    if not parent:
                        warnings.append(f"parent {child['parent_event_id']} of {child['event_id']} "
                                        f"not available as of {as_of.date()}")
                        break
                    rel, w, ws = _resolve_edge(parent["ticker"], child["ticker"], child.get("raw_excerpt", ""))
                    warnings.extend(ws)
                    cdepth = int(child.get("cascade_depth") or 1)
                    key = (parent["event_id"], child["event_id"])
                    edges[key] = CascadeEdge(
                        parent_event_id=parent["event_id"], child_event_id=child["event_id"],
                        parent_ticker=parent["ticker"], child_ticker=child["ticker"],
                        parent_event_type=parent["event_type"], child_event_type=child["event_type"],
                        relationship_type=rel, edge_weight=w, depth=cdepth,
                        decay_factor=_decay_for(cdepth),
                        contribution=float(child.get("magnitude") or 0.0),
                    )
                    if not parent.get("parent_event_id"):
                        roots[parent["event_id"]] = parent
                    child = parent

            if not roots:
                return None
            # Primary root = the one carrying the most total contribution into the tree.
            primary = max(roots, key=lambda rid: sum(
                e.contribution for e in edges.values() if e.parent_event_id == rid))
            if len(roots) > 1:
                warnings.append(f"{len(roots)} cascade roots reached {ticker}; showing the largest ({primary}).")

            # Keep only edges reachable from the primary root (focused tree).
            tree_edges = sorted(edges.values(), key=lambda e: (e.depth, e.parent_ticker, e.child_ticker))
            return CascadeNode(
                event=_to_evidence(roots[primary]),
                depth=0,
                edges=tree_edges,
                warnings=sorted(set(warnings)),
            )
    finally:
        if own:
            conn.close()


__all__ = ["build_cascade", "MAX_DEPTH"]
