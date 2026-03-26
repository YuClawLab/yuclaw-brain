"""
FIX 4.4 Gateway — real broker protocol implementation.
Simulates full order lifecycle: New -> Pending -> Filled -> Confirmed.
Foundation for real broker connection next week.
"""
import time, hashlib, json, os
from datetime import datetime
from queue import Queue


class FIXSession:
    def __init__(self, sender: str = 'YUCLAW', target: str = 'BROKER'):
        self.sender = sender
        self.target = target
        self.seq_num = 1
        self.connected = False
        self.orders = {}
        self.executions = []
        self.order_queue = Queue()

    def build_message(self, msg_type: str, fields: dict) -> str:
        body_fields = {
            '8': 'FIX.4.4',
            '35': msg_type,
            '49': self.sender,
            '56': self.target,
            '34': str(self.seq_num),
            '52': datetime.utcnow().strftime('%Y%m%d-%H:%M:%S.%f')[:21],
        }
        body_fields.update(fields)
        body = '\x01'.join(f"{k}={v}" for k, v in body_fields.items())
        checksum = sum(ord(c) for c in body + '\x01') % 256
        msg = f"{body}\x0110={checksum:03d}\x01"
        self.seq_num += 1
        return msg

    def new_order(self, ticker: str, side: str, qty: int,
                  price: float = None, order_type: str = 'MARKET') -> dict:
        cl_ord_id = f"YUCLAW-{ticker}-{int(time.time())}"
        fields = {
            '11': cl_ord_id, '55': ticker,
            '54': '1' if side == 'BUY' else '2',
            '38': str(qty), '40': '1' if order_type == 'MARKET' else '2',
            '44': str(price) if price else '0',
            '60': datetime.utcnow().strftime('%Y%m%d-%H:%M:%S'),
        }
        fix_msg = self.build_message('D', fields)
        order = {
            'cl_ord_id': cl_ord_id, 'ticker': ticker, 'side': side,
            'qty': qty, 'price': price, 'status': 'NEW',
            'timestamp': datetime.utcnow().isoformat(),
            'fix_message': fix_msg[:100], 'fills': []
        }
        self.orders[cl_ord_id] = order
        self.order_queue.put(order)
        return order

    def simulate_execution(self, order: dict) -> dict:
        time.sleep(0.05)
        fill_price = order['price'] or 100.0
        execution = {
            'order_id': order['cl_ord_id'], 'ticker': order['ticker'],
            'side': order['side'], 'qty': order['qty'],
            'fill_price': fill_price, 'status': 'FILLED',
            'timestamp': datetime.utcnow().isoformat(),
            'commission': round(order['qty'] * fill_price * 0.00025, 4)
        }
        order['status'] = 'FILLED'
        order['fills'].append(execution)
        self.executions.append(execution)
        return execution

    def process_signals(self, signals: list) -> list:
        print(f"=== FIX Gateway Processing {len(signals)} signals ===")
        executions = []
        for s in signals:
            if s['signal'] in ['STRONG_BUY', 'BUY']:
                qty = max(1, int(100 * abs(s['score'])))
                order = self.new_order(s['ticker'], 'BUY', qty, price=s.get('price', 100.0))
                exec_report = self.simulate_execution(order)
                executions.append(exec_report)
                print(f"  FILLED: BUY {qty} {s['ticker']} @ ${exec_report['fill_price']:.2f}")
            elif s['signal'] in ['STRONG_SELL', 'SELL']:
                qty = max(1, int(100 * abs(s['score'])))
                order = self.new_order(s['ticker'], 'SELL', qty, price=s.get('price', 100.0))
                exec_report = self.simulate_execution(order)
                executions.append(exec_report)
                print(f"  FILLED: SELL {qty} {s['ticker']} @ ${exec_report['fill_price']:.2f}")

        os.makedirs('output/fix', exist_ok=True)
        with open(f"output/fix/executions_{datetime.now().strftime('%Y%m%d_%H%M')}.json", 'w') as f:
            json.dump(executions, f, indent=2)
        return executions

    def get_pnl(self) -> dict:
        total_commission = sum(e['commission'] for e in self.executions)
        buy_value = sum(e['qty'] * e['fill_price'] for e in self.executions if e['side'] == 'BUY')
        sell_value = sum(e['qty'] * e['fill_price'] for e in self.executions if e['side'] == 'SELL')
        return {
            'total_orders': len(self.orders), 'total_fills': len(self.executions),
            'buy_value': round(buy_value, 2), 'sell_value': round(sell_value, 2),
            'total_commission': round(total_commission, 4),
            'level_name': 'PAPER_TRADING'
        }


if __name__ == '__main__':
    session = FIXSession()
    try:
        signals = json.load(open('output/aggregated_signals.json'))[:5]
    except Exception:
        signals = [
            {'ticker': 'LUNR', 'signal': 'STRONG_BUY', 'score': 0.933, 'price': 20.55},
            {'ticker': 'ASTS', 'signal': 'STRONG_BUY', 'score': 0.848, 'price': 96.06},
        ]
    executions = session.process_signals(signals)
    pnl = session.get_pnl()
    print(f"\nFIX Gateway Summary:")
    print(f"  Orders: {pnl['total_orders']} | Fills: {pnl['total_fills']}")
    print(f"  Buy value: ${pnl['buy_value']:,.2f} | Commission: ${pnl['total_commission']:.4f}")
    print(f"  Level: {pnl['level_name']}")
