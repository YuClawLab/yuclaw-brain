"""yuclaw/memory/portfolio_memory.py — Persistent thesis history and style accumulation."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
import aiosqlite


@dataclass
class ThesisRecord:
    ticker: str
    thesis: str
    key_assumptions: list[str]
    target_price: float | None
    created_at: str
    status: str = "active"
    falsified_by: list[dict] = field(default_factory=list)


class PortfolioMemory:
    def __init__(self, db_path: str = "data/portfolio.db"):
        import os; os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db = db_path

    async def initialize(self):
        async with aiosqlite.connect(self._db) as db:
            await db.executescript("""
                CREATE TABLE IF NOT EXISTS thesis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT, thesis TEXT, assumptions TEXT,
                    target_price REAL, created_at TEXT,
                    status TEXT DEFAULT 'active', falsified_by TEXT DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS watchlist (
                    ticker TEXT PRIMARY KEY, added_at TEXT, notes TEXT
                );
            """)
            await db.commit()

    async def save_thesis(self, record: ThesisRecord) -> int:
        async with aiosqlite.connect(self._db) as db:
            cur = await db.execute(
                "INSERT INTO thesis (ticker,thesis,assumptions,target_price,created_at) VALUES (?,?,?,?,?)",
                (record.ticker, record.thesis, json.dumps(record.key_assumptions),
                 record.target_price, record.created_at)
            )
            await db.commit()
            return cur.lastrowid

    async def get_history(self, ticker: str) -> list[ThesisRecord]:
        async with aiosqlite.connect(self._db) as db:
            async with db.execute(
                "SELECT ticker,thesis,assumptions,target_price,created_at,status,falsified_by "
                "FROM thesis WHERE ticker=? ORDER BY created_at DESC", (ticker.upper(),)
            ) as cur:
                return [
                    ThesisRecord(
                        ticker=r[0], thesis=r[1],
                        key_assumptions=json.loads(r[2]),
                        target_price=r[3], created_at=r[4],
                        status=r[5], falsified_by=json.loads(r[6] or "[]")
                    )
                    for r in await cur.fetchall()
                ]

    async def flag_falsified(self, ticker: str, assumption: str, new_evidence: str):
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._db) as db:
            async with db.execute(
                "SELECT id, falsified_by FROM thesis WHERE ticker=? AND status='active'",
                (ticker.upper(),)
            ) as cur:
                for row_id, fb_json in await cur.fetchall():
                    fb = json.loads(fb_json or "[]")
                    fb.append({"assumption": assumption, "evidence": new_evidence, "flagged_at": now})
                    await db.execute(
                        "UPDATE thesis SET falsified_by=?,status='under_review' WHERE id=?",
                        (json.dumps(fb), row_id)
                    )
            await db.commit()

    async def add_to_watchlist(self, ticker: str, notes: str = ""):
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._db) as db:
            await db.execute(
                "INSERT OR REPLACE INTO watchlist VALUES (?,?,?)",
                (ticker.upper(), now, notes)
            )
            await db.commit()

    async def get_watchlist(self) -> list[dict]:
        async with aiosqlite.connect(self._db) as db:
            async with db.execute("SELECT ticker, added_at, notes FROM watchlist ORDER BY added_at DESC") as cur:
                return [{"ticker": r[0], "added_at": r[1], "notes": r[2]} for r in await cur.fetchall()]
