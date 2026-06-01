"""
Track Record Engine — records every signal with timestamp.
After 30 days verifies if signal was correct.
This is the proof institutional investors need.
YUCLAW builds its own verifiable track record automatically.
"""
import sqlite3, json, yfinance as yf
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

@dataclass
class SignalRecord:
    record_id: str
    ticker: str
    signal: str
    score: float
    price_at_signal: float
    timestamp: str
    verified: bool = False
    price_at_verification: float = 0.0
    actual_return: float = 0.0
    was_correct: bool = False
    days_to_verify: int = 30

class TrackRecordEngine:
    """
    Records every signal. Verifies after 30 days.
    Builds YUCLAW's verifiable performance history.
    """

    def __init__(self, db_path='data/track_record.db'):
        Path('data').mkdir(exist_ok=True)
        self.db = db_path
        self._init()

    def _init(self):
        with sqlite3.connect(self.db) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS signals
                (id TEXT PRIMARY KEY, ticker TEXT, signal TEXT,
                 score REAL, price_at_signal REAL, timestamp TEXT,
                 verified INTEGER, price_at_verify REAL,
                 actual_return REAL, was_correct INTEGER,
                 days_to_verify INTEGER)''')

    def record(self, ticker: str, signal: str, score: float):
        try:
            price = float(yf.Ticker(ticker).fast_info.last_price or 0)
            if price == 0: return None
            rid = f'{ticker}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            with sqlite3.connect(self.db) as db:
                db.execute('INSERT OR IGNORE INTO signals VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (rid,ticker,signal,score,price,
                     datetime.now().isoformat(),0,0,0,0,30))
            return rid
        except: return None

    def verify_pending(self):
        """Check all unverified signals older than 30 days."""
        verified = []
        with sqlite3.connect(self.db) as db:
            rows = db.execute(
                'SELECT id,ticker,signal,price_at_signal,timestamp FROM signals WHERE verified=0'
            ).fetchall()
            for row in rows:
                rid,ticker,signal,orig_price,ts = row
                try:
                    signal_date = datetime.fromisoformat(ts)
                    days_elapsed = (datetime.now() - signal_date).days
                    if days_elapsed >= 30:
                        current = float(yf.Ticker(ticker).fast_info.last_price or 0)
                        if current > 0:
                            ret = (current - orig_price) / orig_price
                            correct = (signal in ('STRONG_BUY','BUY') and ret > 0) or \
                                     (signal in ('STRONG_SELL','SELL') and ret < 0)
                            db.execute('''UPDATE signals SET verified=1,
                                price_at_verify=?,actual_return=?,was_correct=?
                                WHERE id=?''', (current,ret,int(correct),rid))
                            verified.append({'ticker':ticker,'signal':signal,'return':ret,'correct':correct})
                except: pass
        return verified

    def get_accuracy(self) -> dict:
        with sqlite3.connect(self.db) as db:
            total = db.execute('SELECT COUNT(*) FROM signals WHERE verified=1').fetchone()[0]
            correct = db.execute('SELECT COUNT(*) FROM signals WHERE verified=1 AND was_correct=1').fetchone()[0]
            pending = db.execute('SELECT COUNT(*) FROM signals WHERE verified=0').fetchone()[0]
            avg_ret = db.execute('SELECT AVG(actual_return) FROM signals WHERE verified=1').fetchone()[0]
        accuracy = correct/total if total > 0 else 0
        return {
            'total_verified': total,
            'correct': correct,
            'accuracy': round(accuracy, 3),
            'pending': pending,
            'avg_return': round(avg_ret or 0, 4),
            'is_real': True
        }

    def record_all_signals(self):
        """Record today's signals from aggregated output."""
        try:
            signals = json.load(open('output/aggregated_signals.json'))
            recorded = 0
            for s in signals:
                rid = self.record(s['ticker'], s['signal'], s['score'])
                if rid: recorded += 1
            print(f'Recorded {recorded} signals to track record')
            return recorded
        except Exception as e:
            print(f'Error: {e}')
            return 0

if __name__=='__main__':
    engine = TrackRecordEngine()
    count = engine.record_all_signals()
    verified = engine.verify_pending()
    accuracy = engine.get_accuracy()
    print(f'Track Record Status:')
    print(f'  Signals recorded today: {count}')
    print(f'  Pending verification: {accuracy["pending"]}')
    print(f'  Verified: {accuracy["total_verified"]}')
    print(f'  Accuracy: {accuracy["accuracy"]:.0%}')
    print(f'  Avg return: {accuracy["avg_return"]:.2%}')
    if verified:
        print(f'  Newly verified: {len(verified)}')
