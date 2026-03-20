"""yuclaw/memory/evidence_graph.py — Every claim anchored to its source."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
import networkx as nx
import aiosqlite
from ..core.ontology.models import EvidenceNode


class EvidenceGraph:
    """
    Every financial claim MUST have an EvidenceNode.
    No EvidenceNode = invalid output = ValueError.
    """

    def __init__(self, db_path: str = "data/evidence.db"):
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._graph = nx.DiGraph()
        self._db    = db_path
        self._nodes: dict[str, EvidenceNode] = {}

    async def initialize(self):
        async with aiosqlite.connect(self._db) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY, claim TEXT, source_doc_id TEXT,
                    page_number INTEGER, paragraph_hash TEXT,
                    extraction_timestamp TEXT, model_version TEXT,
                    confidence REAL, ontology_tags TEXT
                );
                CREATE TABLE IF NOT EXISTS edges (
                    from_id TEXT, to_id TEXT, edge_type TEXT,
                    PRIMARY KEY(from_id, to_id)
                );
            """)
            await db.commit()

    def _make_id(self, node: EvidenceNode) -> str:
        raw = f"{node.source_doc_id}:{node.page_number}:{node.paragraph_hash}:{node.claim[:40]}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def add_node(self, node: EvidenceNode) -> str:
        if not node.source_doc_id:
            raise ValueError(f"EvidenceNode missing source_doc_id: {node.claim[:50]}")
        nid = self._make_id(node)
        self._graph.add_node(nid, data=node)
        self._nodes[nid] = node
        async with aiosqlite.connect(self._db) as db:
            await db.execute(
                "INSERT OR REPLACE INTO nodes VALUES (?,?,?,?,?,?,?,?,?)",
                (nid, node.claim, node.source_doc_id, node.page_number,
                 node.paragraph_hash, node.extraction_timestamp,
                 node.model_version, node.confidence,
                 json.dumps(node.ontology_tags))
            )
            await db.commit()
        return nid

    async def add_dependency(self, conclusion_id: str, evidence_ids: list[str]):
        for eid in evidence_ids:
            self._graph.add_edge(conclusion_id, eid, type="supported_by")
        async with aiosqlite.connect(self._db) as db:
            await db.executemany(
                "INSERT OR REPLACE INTO edges VALUES (?,?,?)",
                [(conclusion_id, eid, "supported_by") for eid in evidence_ids]
            )
            await db.commit()

    async def get_audit_trail(self, node_id: str) -> dict:
        sources = []
        if node_id in self._graph:
            for desc in nx.descendants(self._graph, node_id):
                if desc in self._nodes:
                    s = self._nodes[desc]
                    sources.append({
                        "doc_id": s.source_doc_id, "page": s.page_number,
                        "claim": s.claim[:80], "confidence": s.confidence,
                        "model": s.model_version, "timestamp": s.extraction_timestamp,
                        "tags": s.ontology_tags
                    })
        node = self._nodes.get(node_id)
        return {
            "claim": node.claim if node else "unknown",
            "node_id": node_id,
            "evidence_count": len(sources),
            "sources": sources,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

    def orphan_check(self) -> list[str]:
        """Return node IDs with no evidence backing — these are violations."""
        return [n for n in self._graph.nodes if self._graph.out_degree(n) == 0]
