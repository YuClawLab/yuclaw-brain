"""
Portfolio Memory v2 — learns from every decision.
Tracks: what was decided, what happened, what to learn.
"""
import json, os, time
from datetime import date


class PortfolioMemoryV2:

    MEMORY_FILE = 'output/portfolio_memory_v2.json'

    def __init__(self):
        self.memory = self._load()

    def _load(self):
        if os.path.exists(self.MEMORY_FILE):
            return json.load(open(self.MEMORY_FILE))
        return {
            'decisions': [], 'patterns': {}, 'lessons': [],
            'performance': {'total': 0, 'verified': 0, 'correct': 0, 'accuracy': 0.0}
        }

    def _save(self):
        os.makedirs('output', exist_ok=True)
        with open(self.MEMORY_FILE, 'w') as f:
            json.dump(self.memory, f, indent=2)

    def record(self, signal: dict, evidence: dict = None) -> dict:
        decision = {
            'id': len(self.memory['decisions']) + 1,
            'date': date.today().isoformat(), 'timestamp': time.time(),
            'ticker': signal['ticker'], 'signal': signal['signal'],
            'score': signal['score'], 'price_at_signal': signal.get('price', 0),
            'evidence_confidence': evidence.get('confidence', 0) if evidence else 0,
            'verdict': evidence.get('verdict', 'PENDING') if evidence else 'PENDING',
            'model': 'nemotron-3-super-120B',
            'verified': False, 'outcome': None, 'return_pct': None
        }
        self.memory['decisions'].append(decision)
        self.memory['performance']['total'] += 1

        pattern = f"{signal['signal']}_{signal['score'] > 0.7}"
        if pattern not in self.memory['patterns']:
            self.memory['patterns'][pattern] = {'count': 0, 'correct': 0, 'accuracy': 0}
        self.memory['patterns'][pattern]['count'] += 1

        self._save()
        return decision

    def verify_outcomes(self, current_prices: dict) -> list:
        verified = []
        for d in self.memory['decisions']:
            if d.get('verified'):
                continue
            ticker = d['ticker']
            if ticker not in current_prices:
                continue
            signal_price = d.get('price_at_signal', 0)
            if signal_price <= 0:
                continue

            current_price = current_prices[ticker]
            return_pct = (current_price - signal_price) / signal_price
            correct = (
                (d['signal'] in ['STRONG_BUY', 'BUY'] and return_pct > 0) or
                (d['signal'] in ['STRONG_SELL', 'SELL'] and return_pct < 0)
            )
            d['verified'] = True
            d['outcome'] = 'CORRECT' if correct else 'WRONG'
            d['return_pct'] = round(return_pct * 100, 2)
            if correct:
                self.memory['performance']['correct'] += 1
            self.memory['performance']['verified'] += 1
            verified.append(d)

        total_v = self.memory['performance']['verified']
        if total_v > 0:
            self.memory['performance']['accuracy'] = self.memory['performance']['correct'] / total_v
        self._save()
        return verified

    def get_context(self) -> str:
        perf = self.memory['performance']
        recent = self.memory['decisions'][-5:]
        return f"Memory: {perf['total']} decisions, {perf['accuracy']:.0%} accuracy, {len(self.memory['patterns'])} patterns"

    def run_daily(self):
        print("=== Portfolio Memory v2 Daily Run ===")
        try:
            signals = json.load(open('output/aggregated_signals.json'))
        except Exception:
            print("No signals"); return

        prices = {s['ticker']: s['price'] for s in signals if s.get('price', 0) > 0}
        verified = self.verify_outcomes(prices)
        print(f"Verified: {len(verified)} decisions")

        for s in signals[:10]:
            self.record(s)
        print(f"Total: {self.memory['performance']['total']} decisions")
        print(f"Accuracy: {self.memory['performance']['accuracy']:.0%}")


if __name__ == '__main__':
    memory = PortfolioMemoryV2()
    memory.run_daily()
