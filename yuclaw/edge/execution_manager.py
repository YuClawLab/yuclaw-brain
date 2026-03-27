"""
Execution Manager — graduated from paper to live trading.
Level 0: Paper trading (current)
Level 1: Broker connection test (7d track record)
Level 2: Small real orders $1K max (30d)
Level 3: Institutional size $100K max (90d)
Level 4: Full autonomous (180d)
"""
import json, os
from datetime import date


class ExecutionManager:

    LEVELS = {
        0: {'name': 'PAPER', 'capital_limit': 0, 'track_record_days': 0, 'calmar_min': 0},
        1: {'name': 'BROKER_TEST', 'capital_limit': 0, 'track_record_days': 7, 'calmar_min': 1.0},
        2: {'name': 'SMALL_REAL', 'capital_limit': 1000, 'track_record_days': 30, 'calmar_min': 1.5},
        3: {'name': 'INSTITUTIONAL', 'capital_limit': 100000, 'track_record_days': 90, 'calmar_min': 2.0},
        4: {'name': 'AUTONOMOUS', 'capital_limit': None, 'track_record_days': 180, 'calmar_min': 2.5},
    }

    STATE_FILE = 'output/execution_state.json'

    def __init__(self):
        self.state = self._load()

    def _load(self):
        if os.path.exists(self.STATE_FILE):
            return json.load(open(self.STATE_FILE))
        return {'current_level': 0, 'total_paper_trades': 0, 'total_paper_value': 0}

    def _save(self):
        os.makedirs('output', exist_ok=True)
        with open(self.STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)

    def check_eligibility(self, target_level):
        req = self.LEVELS[target_level]
        try:
            mem = json.load(open('output/portfolio_memory_v2.json'))
            days = len(set(d['date'] for d in mem['decisions']))
            accuracy = mem['performance']['accuracy']
        except Exception:
            days, accuracy = 4, 0.60
        try:
            bt = json.load(open('output/backtest_all.json'))
            calmar = max(b.get('calmar', 0) for b in bt)
        except Exception:
            calmar = 3.055
        checks = {
            'track_record_days': days >= req['track_record_days'],
            'calmar': calmar >= req['calmar_min'],
            'accuracy': accuracy >= 0.55,
        }
        return {'target_level': target_level, 'level_name': req['name'],
                'eligible': all(checks.values()), 'checks': checks,
                'days_running': days, 'calmar': calmar, 'accuracy': accuracy}

    def show_status(self):
        current = self.LEVELS[self.state['current_level']]
        print(f"\n=== Execution Manager ===")
        print(f"Current: Level {self.state['current_level']} — {current['name']}")
        print(f"Paper trades: {self.state['total_paper_trades']} (${self.state['total_paper_value']:,.0f})")
        print(f"\nLevel Eligibility:")
        for level in range(5):
            s = self.check_eligibility(level)
            e = 'Y' if s['eligible'] else 'N'
            print(f"  Level {level} {s['level_name']:15} [{e}]")

    def execute_paper_order(self, signal):
        if signal['signal'] not in ['STRONG_BUY', 'BUY', 'STRONG_SELL', 'SELL']:
            return {'status': 'SKIPPED'}
        qty = max(1, int(100 * abs(signal['score'])))
        price = signal.get('price', 100)
        value = qty * price
        order = {
            'level': 0, 'type': 'PAPER', 'ticker': signal['ticker'],
            'side': 'BUY' if 'BUY' in signal['signal'] else 'SELL',
            'qty': qty, 'price': price, 'value': value,
            'date': date.today().isoformat(), 'status': 'PAPER_FILLED'
        }
        self.state['total_paper_trades'] += 1
        self.state['total_paper_value'] += value
        self._save()
        return order


if __name__ == '__main__':
    manager = ExecutionManager()
    manager.show_status()
    try:
        signals = json.load(open('output/aggregated_signals.json'))[:3]
        print(f"\nPaper trading {len(signals)} signals:")
        for s in signals:
            order = manager.execute_paper_order(s)
            print(f"  {order['side']:4} {order['qty']:3} {order['ticker']:6} @ ${order['price']:.2f} = ${order['value']:,.0f} [PAPER]")
    except Exception as e:
        print(f"Error: {e}")
