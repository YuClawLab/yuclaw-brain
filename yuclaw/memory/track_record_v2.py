"""
Track Record v2 — records ALL signals with full context.
In 30 days: verifiable proof of YUCLAW accuracy.
"""
import json, os, time
from datetime import date


TRACK_FILE = 'output/track_record_v2.json'


def load_track():
    if os.path.exists(TRACK_FILE):
        return json.load(open(TRACK_FILE))
    return {'signals': [], 'stats': {'total': 0, 'verified': 0}}


def record_signal(ticker: str, signal: str, score: float,
                  price: float = None, context: dict = None):
    track = load_track()
    entry = {
        'id': len(track['signals']) + 1,
        'date': date.today().isoformat(),
        'timestamp': time.time(),
        'ticker': ticker,
        'signal': signal,
        'score': score,
        'price_at_signal': price,
        'context': context or {},
        'model': 'nemotron-3-super-120B',
        'verify_date': None,
        'actual_return': None,
        'correct': None
    }
    track['signals'].append(entry)
    track['stats']['total'] += 1

    with open(TRACK_FILE, 'w') as f:
        json.dump(track, f, indent=2)
    return entry


def show_stats():
    track = load_track()
    print(f"=== Track Record v2 ===")
    print(f"Total signals: {track['stats']['total']}")
    print(f"Verified: {track['stats']['verified']}")
    print(f"Latest signals:")
    for s in track['signals'][-5:]:
        print(f"  {s['date']} {s['ticker']:6} {s['signal']:12} {s['score']:+.3f}")


if __name__ == '__main__':
    signals = [
        ('LUNR', 'STRONG_BUY', 0.933),
        ('ASTS', 'STRONG_BUY', 0.848),
        ('DELL', 'STRONG_BUY', 0.826),
        ('MRNA', 'STRONG_BUY', 0.821),
        ('KLAC', 'STRONG_BUY', 0.646),
        ('AMAT', 'STRONG_BUY', 0.640),
        ('MRVL', 'STRONG_BUY', 0.600),
        ('CRCL', 'STRONG_BUY', 0.592),
        ('LRCX', 'STRONG_BUY', 0.549),
        ('MU',   'STRONG_BUY', 0.546),
    ]
    for ticker, signal, score in signals:
        record_signal(ticker, signal, score)
    show_stats()
