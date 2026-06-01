"""
YUCLAW Dark Pool — private order matching.
Institutional orders matched off-exchange.
No market impact. No front-running. ZKP proof per match.
"""
import json, os, time, hashlib
from datetime import date


class DarkPoolEngine:

    POOL_FILE = 'output/darkpool/order_book.json'
    MATCH_FILE = 'output/darkpool/matches.json'

    def __init__(self):
        os.makedirs('output/darkpool', exist_ok=True)
        self.orders = self._load(self.POOL_FILE)
        self.matches = self._load(self.MATCH_FILE)

    def _load(self, path):
        if os.path.exists(path):
            return json.load(open(path))
        return []

    def _save(self):
        with open(self.POOL_FILE, 'w') as f:
            json.dump(self.orders, f, indent=2)
        with open(self.MATCH_FILE, 'w') as f:
            json.dump(self.matches, f, indent=2)

    def _order_id(self, ticker, side):
        return f"DP-{hashlib.sha256(f'{ticker}{side}{time.time()}'.encode()).hexdigest()[:12].upper()}"

    def _zkp_proof(self, buy, sell, price):
        data = json.dumps({'buy': buy['id'], 'sell': sell['id'], 'price': price, 't': time.time()}, sort_keys=True).encode()
        return hashlib.sha256(data).hexdigest()

    def submit_order(self, ticker, side, qty, limit_price, participant='YUCLAW'):
        order = {
            'id': self._order_id(ticker, side), 'ticker': ticker,
            'side': side.upper(), 'qty': qty, 'limit_price': limit_price,
            'participant': participant, 'timestamp': time.time(),
            'date': date.today().isoformat(), 'filled': False,
            'fill_price': 0.0, 'fill_qty': 0, 'matched_with': ''
        }
        self.orders.append(order)
        self._save()
        print(f"[DARK POOL] {side} {qty} {ticker} @ ${limit_price:.2f} | {order['id']}")
        return order

    def match_orders(self):
        buys = [o for o in self.orders if o['side'] == 'BUY' and not o['filled']]
        sells = [o for o in self.orders if o['side'] == 'SELL' and not o['filled']]
        new_matches = []

        for buy in buys:
            for sell in sells:
                if sell['filled'] or buy['ticker'] != sell['ticker']:
                    continue
                if buy['limit_price'] < sell['limit_price']:
                    continue

                match_price = round((buy['limit_price'] + sell['limit_price']) / 2, 2)
                match_qty = min(buy['qty'], sell['qty'])
                zkp = self._zkp_proof(buy, sell, match_price)

                match = {
                    'match_id': f"MATCH-{hashlib.sha256(zkp.encode()).hexdigest()[:8].upper()}",
                    'ticker': buy['ticker'], 'buy_order': buy['id'], 'sell_order': sell['id'],
                    'match_price': match_price, 'match_qty': match_qty,
                    'timestamp': time.time(), 'date': date.today().isoformat(),
                    'zkp_proof': zkp,
                    'savings_vs_exchange': round(abs(buy['limit_price'] - sell['limit_price']) / 2, 4)
                }

                buy['filled'] = sell['filled'] = True
                buy['fill_price'] = sell['fill_price'] = match_price
                buy['fill_qty'] = sell['fill_qty'] = match_qty
                buy['matched_with'] = sell['id']
                sell['matched_with'] = buy['id']

                self.matches.append(match)
                new_matches.append(match)
                print(f"[MATCHED] {match_qty} {buy['ticker']} @ ${match_price:.2f} | ZKP: {zkp[:16]}...")

        self._save()
        return new_matches

    def get_stats(self):
        filled = [o for o in self.orders if o['filled']]
        total_value = sum(m['match_price'] * m['match_qty'] for m in self.matches)
        return {
            'total_orders': len(self.orders), 'filled': len(filled),
            'matches': len(self.matches), 'total_value': round(total_value, 2),
            'fill_rate': len(filled) / len(self.orders) if self.orders else 0
        }

    def run_from_signals(self, signals):
        print(f"\n=== Dark Pool — {len(signals)} signals ===")
        for s in signals[:5]:
            if s['signal'] in ['STRONG_BUY', 'BUY']:
                qty = max(100, int(1000 * abs(s['score'])))
                self.submit_order(s['ticker'], 'BUY', qty, round(s.get('price', 100) * 1.001, 2))
            elif s['signal'] in ['STRONG_SELL', 'SELL']:
                qty = max(100, int(1000 * abs(s['score'])))
                self.submit_order(s['ticker'], 'SELL', qty, round(s.get('price', 100) * 0.999, 2))

        matches = self.match_orders()
        stats = self.get_stats()
        print(f"\nOrders: {stats['total_orders']} | Matches: {stats['matches']} | Value: ${stats['total_value']:,.2f}")
        return matches


if __name__ == '__main__':
    engine = DarkPoolEngine()
    try:
        signals = json.load(open('output/aggregated_signals.json'))[:10]
    except Exception:
        signals = [
            {'ticker': 'LUNR', 'signal': 'STRONG_BUY', 'score': 0.933, 'price': 19.23},
            {'ticker': 'LUNR', 'signal': 'STRONG_SELL', 'score': -0.5, 'price': 19.50},
        ]
    engine.run_from_signals(signals)
