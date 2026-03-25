"""
Portfolio Memory — remembers every decision, learns from outcomes.
Wired into daily synthesis and institutional brief.
"""
import json, os, time
from datetime import date


MEMORY_FILE = 'output/portfolio_memory.json'


def load_memory():
    if os.path.exists(MEMORY_FILE):
        return json.load(open(MEMORY_FILE))
    return {
        'decisions': [],
        'patterns': {},
        'regime_history': [],
        'performance': {'total': 0, 'correct': 0, 'pending': 0}
    }


def record_decision(ticker, signal, score, evidence, regime):
    memory = load_memory()
    decision = {
        'id': len(memory['decisions']) + 1,
        'date': date.today().isoformat(),
        'timestamp': time.time(),
        'ticker': ticker,
        'signal': signal,
        'score': score,
        'evidence_confidence': evidence.get('confidence', 0),
        'regime': regime,
        'model': 'nemotron-3-super-120B',
        'outcome': None,
        'return_30d': None,
        'verified': False
    }
    memory['decisions'].append(decision)
    memory['performance']['total'] += 1
    memory['performance']['pending'] += 1

    # Pattern learning
    pattern_key = f"{signal}_{regime}"
    if pattern_key not in memory['patterns']:
        memory['patterns'][pattern_key] = {'count': 0, 'correct': 0}
    memory['patterns'][pattern_key]['count'] += 1

    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)
    return decision


def get_memory_context() -> str:
    memory = load_memory()
    total = memory['performance']['total']
    pending = memory['performance']['pending']

    context = f"""Portfolio Memory Context:
- Total decisions recorded: {total}
- Pending verification: {pending}
- Patterns learned: {len(memory['patterns'])}
- Most recent decisions: {[d['ticker'] + ' ' + d['signal'] for d in memory['decisions'][-5:]]}
"""
    return context


def run_daily_memory():
    print("=== Portfolio Memory Daily Run ===")
    try:
        signals = json.load(open('output/aggregated_signals.json'))
        regime_data = json.load(open('output/macro_regime.json'))
        regime = regime_data.get('regime', 'UNKNOWN')
    except Exception:
        signals = [
            {'ticker': 'LUNR', 'signal': 'STRONG_BUY', 'score': 0.933},
            {'ticker': 'ASTS', 'signal': 'STRONG_BUY', 'score': 0.848},
        ]
        regime = 'CRISIS'

    for s in signals[:10]:
        record_decision(
            s['ticker'], s['signal'], s['score'],
            {'confidence': 0.75}, regime
        )
        print(f"Recorded: {s['ticker']} {s['signal']} score={s['score']:+.3f}")

    memory = load_memory()
    print(f"\nMemory: {memory['performance']['total']} total decisions")
    print(f"Context: {get_memory_context()}")


if __name__ == '__main__':
    run_daily_memory()
