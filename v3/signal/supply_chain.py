"""
Supply-chain / influence graph for the v3.0 cascade engine.

v2.3.0 ships an unweighted causal graph at ~/yuclaw/data/causal_graph.json
(73 nodes, 92 edges) — usable for discovery but lacks edge weights, which
the cascade engine needs to scale magnitude across hops. v3.0 carries its
own weighted edge table here, locked at design-doc values. The two graphs
should agree on which edges exist; cross-reference helpers are below.

Edge weights are *transmission strengths* in [0, 1] — what fraction of a
shock to the source ticker should propagate to the target. Anchor cases:
    TSM → NVDA  0.45 — NVDA's leading-edge GPUs are exclusively TSMC 4N/3N
    AMAT → TSM  0.40 — AMAT supplies a major share of TSM's fab equipment
    SPY → any   0.05 — market beta floor; broad sentiment leak only

Directionality:
    "out" — source's news affects target (TSM down → NVDA worse)
    "in"  — target's news affects source (covered as separate edge in
             the opposite direction; we never store reverse direction
             implicitly)
    "peer" — bidirectional competitive coupling (good news for one is
             priced as bad for the other, with the *opposite* sign)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_V2_CAUSAL_GRAPH_PATH = Path("/home/zhangd2/yuclaw/data/causal_graph.json")
_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    weight: float
    kind: str  # "supply" | "peer" | "etf" | "macro"
    sign: int  # +1: news flows same-sign; -1: peer-competition flip

    def __post_init__(self) -> None:
        assert 0.0 < self.weight <= 1.0, f"weight out of range: {self.weight}"
        assert self.sign in (-1, +1), f"sign must be ±1, got {self.sign}"


def _supply(src: str, tgt: str, w: float) -> Edge:
    """One-way supply / influence edge — news on src propagates same-sign to tgt."""
    return Edge(source=src, target=tgt, weight=w, kind="supply", sign=+1)


def _peer(a: str, b: str, w: float) -> tuple[Edge, Edge]:
    """Two competitive peers — good news for one is bad for the other."""
    return (
        Edge(source=a, target=b, weight=w, kind="peer", sign=-1),
        Edge(source=b, target=a, weight=w, kind="peer", sign=-1),
    )


def _etf_member(etf: str, ticker: str, w: float = 0.15) -> Edge:
    """ETF → member: sector ETF moves drag members along same-sign."""
    return Edge(source=etf, target=ticker, weight=w, kind="etf", sign=+1)


def _market_beta(broad: str, ticker: str, w: float = 0.05) -> Edge:
    """Broad ETF → ticker: market-beta floor."""
    return Edge(source=broad, target=ticker, weight=w, kind="macro", sign=+1)


# ---------------------------------------------------------------------------
# Locked edge table (v3.0 design-doc weights)
# ---------------------------------------------------------------------------
_EDGES: list[Edge] = []

# Semi foundry
_EDGES += [
    _supply("TSM", "NVDA", 0.45),
    _supply("TSM", "AMD", 0.40),
    _supply("TSM", "ARM", 0.25),
    _supply("TSM", "INTC", 0.15),
    _supply("TSM", "MRVL", 0.30),
]
# Semicap → foundries / chipmakers
_EDGES += [
    _supply("AMAT", "TSM", 0.40),
    _supply("AMAT", "INTC", 0.35),
    _supply("LRCX", "TSM", 0.40),
    _supply("LRCX", "AMAT", 0.30),
]
# Memory
_EDGES += [
    _supply("MU", "NVDA", 0.25),
    _supply("MU", "AMD", 0.20),
]
# Peer competition
_EDGES += list(_peer("AMD", "NVDA", 0.35))
_EDGES += list(_peer("AMD", "INTC", 0.30))
# ARM IP licensing
_EDGES += [
    _supply("ARM", "AAPL", 0.20),
    _supply("ARM", "NVDA", 0.20),
    _supply("ARM", "QCOM", 0.20),
]

# Sector ETF → member equities (locked 0.15 unless noted)
_XLK_MEMBERS = ["NVDA", "MSFT", "AAPL", "GOOGL", "META", "AMD", "INTC",
                "MU", "MRVL", "ARM", "AMAT", "LRCX", "AMZN"]
_EDGES += [_etf_member("XLK", t) for t in _XLK_MEMBERS]

_XLF_MEMBERS = ["JPM", "BAC", "GS", "MS", "WFC", "C", "AXP", "V", "MA", "PYPL"]
_EDGES += [_etf_member("XLF", t) for t in _XLF_MEMBERS]

_XLE_MEMBERS = ["XOM", "CVX", "COP", "SLB", "PSX"]
_EDGES += [_etf_member("XLE", t, 0.20) for t in _XLE_MEMBERS]

_XLV_MEMBERS = ["UNH", "JNJ", "PFE", "MRK", "ABBV", "LLY", "TMO", "DHR", "ABT", "BMY"]
_EDGES += [_etf_member("XLV", t) for t in _XLV_MEMBERS]

_XLP_MEMBERS = ["PG", "KO", "PEP", "WMT", "COST"]
_EDGES += [_etf_member("XLP", t, 0.18) for t in _XLP_MEMBERS]

# SMH (semis-only ETF) — tighter coupling than XLK
_SMH_MEMBERS = ["NVDA", "AMD", "INTC", "MU", "MRVL", "ARM", "AMAT", "LRCX"]
_EDGES += [_etf_member("SMH", t, 0.22) for t in _SMH_MEMBERS]

# Broad ETF → market-beta floor
_ALL_EQUITIES = set(_XLK_MEMBERS) | set(_XLF_MEMBERS) | set(_XLE_MEMBERS) \
    | set(_XLV_MEMBERS) | set(_XLP_MEMBERS) | set(_SMH_MEMBERS) \
    | {"TSLA", "PSX", "BMY", "QCOM"}
_EDGES += [_market_beta("SPY", t, 0.05) for t in sorted(_ALL_EQUITIES)]

_QQQ_MEMBERS = sorted(set(_XLK_MEMBERS + _SMH_MEMBERS + ["TSLA"]))
_EDGES += [_market_beta("QQQ", t, 0.10) for t in _QQQ_MEMBERS]


# ---------------------------------------------------------------------------
# Adjacency index — one-shot build, then read-only.
# ---------------------------------------------------------------------------
_OUT: dict[str, list[Edge]] = {}
for _e in _EDGES:
    _OUT.setdefault(_e.source, []).append(_e)


def neighbors(ticker: str) -> list[Edge]:
    """All outgoing edges from `ticker`."""
    return list(_OUT.get(ticker.upper(), ()))


def two_hop(ticker: str, max_depth2_paths: int = 200) -> list[tuple[Edge, Edge]]:
    """All (edge_d1, edge_d2) pairs where edge_d2 starts where edge_d1 ends.

    Cap is a safety valve against pathological ETF→member→ETF loops; we
    don't expect to hit it in practice.
    """
    out: list[tuple[Edge, Edge]] = []
    for e1 in neighbors(ticker):
        for e2 in neighbors(e1.target):
            if e2.target == ticker:
                continue  # never propagate back to the root
            out.append((e1, e2))
            if len(out) >= max_depth2_paths:
                return out
    return out


def all_edges() -> list[Edge]:
    return list(_EDGES)


def stats() -> dict:
    """Self-report — useful for `python3 -m v3.signal.supply_chain --stats`."""
    nodes = set()
    for e in _EDGES:
        nodes.add(e.source)
        nodes.add(e.target)
    kinds: dict[str, int] = {}
    for e in _EDGES:
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    return {
        "nodes": len(nodes),
        "edges": len(_EDGES),
        "edges_by_kind": kinds,
        "max_out_degree": max((len(v) for v in _OUT.values()), default=0),
    }


# ---------------------------------------------------------------------------
# Optional cross-reference with v2.3.0 causal_graph.json
# ---------------------------------------------------------------------------
def load_v2_causal() -> Optional[dict]:
    """Returns v2.3.0 causal graph (unweighted), or None if not available."""
    if not _V2_CAUSAL_GRAPH_PATH.exists():
        return None
    try:
        return json.loads(_V2_CAUSAL_GRAPH_PATH.read_text())
    except Exception as exc:
        _log.warning("could not load v2 causal graph: %s", exc)
        return None


if __name__ == "__main__":
    import json as _json
    print(_json.dumps(stats(), indent=2))
