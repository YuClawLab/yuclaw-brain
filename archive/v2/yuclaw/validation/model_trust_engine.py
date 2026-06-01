"""Model Trust Engine — tracks LLM prediction accuracy. Self-improving."""
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class Prediction:
    prediction_id: str
    ticker: str
    metric: str
    predicted_value: float
    predicted_direction: str  # UP, DOWN, FLAT
    confidence: float
    model: str
    timestamp: str


class ModelTrustEngine:
    def __init__(self, db_path: str = "data/model_trust.db"):
        self.db_path = db_path
        Path("data").mkdir(exist_ok=True)
        with sqlite3.connect(db_path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS predictions
                (id TEXT PRIMARY KEY, ticker TEXT, metric TEXT,
                 predicted_value REAL, predicted_direction TEXT,
                 confidence REAL, model TEXT, timestamp TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS trust_scores
                (model TEXT PRIMARY KEY, correct INTEGER,
                 total INTEGER, trust_score REAL, last_updated TEXT)""")

    def record_prediction(self, p: Prediction):
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT OR REPLACE INTO predictions VALUES (?,?,?,?,?,?,?,?)",
                       (p.prediction_id, p.ticker, p.metric, p.predicted_value,
                        p.predicted_direction, p.confidence, p.model, p.timestamp))

    def resolve(self, prediction_id: str, actual_value: float):
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT predicted_value,predicted_direction,model FROM predictions WHERE id=?",
                             (prediction_id,)).fetchone()
            if not row:
                return
            predicted, pred_dir, model = row
            actual_dir = "UP" if actual_value > predicted else "DOWN" if actual_value < predicted else "FLAT"
            correct = pred_dir == actual_dir
            # Update trust score
            existing = db.execute("SELECT correct,total FROM trust_scores WHERE model=?", (model,)).fetchone()
            if existing:
                c, t = existing[0] + int(correct), existing[1] + 1
                db.execute("UPDATE trust_scores SET correct=?,total=?,trust_score=?,last_updated=? WHERE model=?",
                           (c, t, c / t, datetime.now().isoformat(), model))
            else:
                db.execute("INSERT INTO trust_scores VALUES (?,?,?,?,?)",
                           (model, int(correct), 1, float(correct), datetime.now().isoformat()))

    def get_trust(self, model: str) -> float:
        with sqlite3.connect(self.db_path) as db:
            row = db.execute("SELECT trust_score,correct,total FROM trust_scores WHERE model=?",
                             (model,)).fetchone()
            return row[0] if row else 0.70
