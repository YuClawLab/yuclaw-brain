"""Portfolio Memory v2 — deep thesis storage with cross-referencing and conviction tracking."""
import json, sqlite3, hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Thesis:
    thesis_id: str
    ticker: str
    summary: str
    key_assumptions: list
    target_price: Optional[float]
    conviction: str  # HIGH, MEDIUM, LOW
    model: str
    created_at: str
    times_reinforced: int = 0
    times_weakened: int = 0
    times_falsified: int = 0
    is_active: bool = True


class PortfolioMemoryV2:
    def __init__(self, db_path: str = "data/portfolio_memory_v2.db"):
        self.db_path = db_path
        Path("data").mkdir(exist_ok=True)
        with sqlite3.connect(db_path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS theses
                (thesis_id TEXT PRIMARY KEY, ticker TEXT, summary TEXT,
                 key_assumptions TEXT, target_price REAL, conviction TEXT,
                 model TEXT, created_at TEXT, times_reinforced INTEGER,
                 times_weakened INTEGER, times_falsified INTEGER, is_active INTEGER)""")
            db.execute("""CREATE TABLE IF NOT EXISTS thesis_updates
                (thesis_id TEXT, update_type TEXT, evidence TEXT,
                 price REAL, updated_at TEXT)""")

    def store(self, t: Thesis):
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT OR REPLACE INTO theses VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                       (t.thesis_id, t.ticker, t.summary, json.dumps(t.key_assumptions),
                        t.target_price, t.conviction, t.model, t.created_at,
                        t.times_reinforced, t.times_weakened, t.times_falsified, int(t.is_active)))

    def update(self, ticker: str, update_type: str, evidence: str, price: float):
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT thesis_id,times_reinforced,times_weakened,times_falsified FROM theses WHERE ticker=? AND is_active=1 ORDER BY created_at DESC LIMIT 1",
                             (ticker,)).fetchone()
            if not row:
                return
            tid, r, w, f = row
            col = {"REINFORCED": "times_reinforced", "WEAKENED": "times_weakened", "FALSIFIED": "times_falsified"}.get(update_type)
            if col:
                val = {"REINFORCED": r + 1, "WEAKENED": w + 1, "FALSIFIED": f + 1}[update_type]
                extra = ",is_active=0" if update_type == "FALSIFIED" else ""
                db.execute(f"UPDATE theses SET {col}=?{extra} WHERE thesis_id=?", (val, tid))
            db.execute("INSERT INTO thesis_updates VALUES (?,?,?,?,?)",
                       (tid, update_type, evidence, price, datetime.now().isoformat()))

    def get_history(self, ticker: str) -> list[Thesis]:
        with sqlite3.connect(self.db_path) as db:
            rows = db.execute("SELECT * FROM theses WHERE ticker=? ORDER BY created_at DESC", (ticker,)).fetchall()
            return [Thesis(thesis_id=r[0], ticker=r[1], summary=r[2],
                           key_assumptions=json.loads(r[3]), target_price=r[4],
                           conviction=r[5], model=r[6], created_at=r[7],
                           times_reinforced=r[8], times_weakened=r[9],
                           times_falsified=r[10], is_active=bool(r[11])) for r in rows]

    def conviction_summary(self, ticker: str) -> str:
        h = self.get_history(ticker)
        if not h:
            return f"No thesis for {ticker}"
        t = h[0]
        return (f"{ticker}: {t.conviction} conviction | "
                f"R:{t.times_reinforced} W:{t.times_weakened} F:{t.times_falsified} | "
                f"{t.summary[:80]}")
