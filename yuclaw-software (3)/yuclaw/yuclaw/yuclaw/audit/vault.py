"""yuclaw/audit/vault.py — Cryptographic audit trail."""
from __future__ import annotations
import hashlib, json, time
from datetime import datetime, timezone
from dataclasses import dataclass
import aiosqlite


@dataclass
class AuditReceipt:
    receipt_id: str
    local_hash: str
    stage: str
    timestamp: str
    strategy_id: str
    verdict: str
    calmar: float


class AuditVault:
    def __init__(self, db_path: str = "data/audit.db"):
        import os; os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db = db_path

    async def initialize(self):
        async with aiosqlite.connect(self._db) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS records (
                    receipt_id TEXT PRIMARY KEY,
                    strategy_id TEXT, verdict TEXT, calmar REAL,
                    context_hash TEXT, reasoning TEXT,
                    agent_signature TEXT, timestamp_ns INTEGER,
                    validation_status TEXT, local_hash TEXT,
                    stage TEXT DEFAULT 'A', created TEXT
                )
            """)
            await db.commit()

    @staticmethod
    def hash_context(prompt: str, context: str = "") -> str:
        """One-way SHA256 hash. Cannot be reverse-engineered."""
        return hashlib.sha256(f"{prompt}|||{context}".encode()).hexdigest()

    async def record(self, strategy_id: str, verdict: str, calmar: float,
                     reasoning: str, validation_status: str) -> AuditReceipt:
        now_ns  = time.time_ns()
        now_iso = datetime.now(timezone.utc).isoformat()
        context_hash = self.hash_context(strategy_id, reasoning)
        payload = json.dumps({
            "strategy_id": strategy_id, "verdict": verdict,
            "calmar": calmar, "context_hash": context_hash,
            "timestamp_ns": now_ns, "status": validation_status
        }, sort_keys=True)
        local_hash  = hashlib.sha256(payload.encode()).hexdigest()
        receipt_id  = f"rcpt_{now_ns}_{local_hash[:8]}"

        async with aiosqlite.connect(self._db) as db:
            await db.execute(
                "INSERT OR REPLACE INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (receipt_id, strategy_id, verdict, calmar, context_hash,
                 reasoning[:500], "validation_agent:v1", now_ns,
                 validation_status, local_hash, "A", now_iso)
            )
            await db.commit()

        return AuditReceipt(
            receipt_id=receipt_id, local_hash=local_hash,
            stage="A", timestamp=now_iso,
            strategy_id=strategy_id, verdict=verdict, calmar=calmar
        )

    async def get_all(self) -> list[dict]:
        async with aiosqlite.connect(self._db) as db:
            async with db.execute(
                "SELECT receipt_id, strategy_id, verdict, calmar, local_hash, created FROM records ORDER BY created DESC"
            ) as cur:
                return [
                    {"receipt_id": r[0], "strategy_id": r[1], "verdict": r[2],
                     "calmar": r[3], "hash": r[4][:16]+"...", "at": r[5]}
                    for r in await cur.fetchall()
                ]
