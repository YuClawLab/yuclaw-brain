"""
YUCLAW Campus Paper Trading Sandbox.
Virtual $100K portfolio against real market data.
"""
import json, os
from datetime import date, datetime

PORTFOLIO_DIR = os.path.expanduser('~/.yuclaw/campus')


def get_live_price(ticker: str) -> float:
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        fi = stock.fast_info
        price = getattr(fi, 'last_price', None) or getattr(fi, 'previous_close', None)
        if price and price > 0:
            return round(float(price), 2)
        data = stock.history(period='1d')
        if not data.empty:
            close = data['Close']
            if hasattr(close, 'columns'):
                close = close.iloc[:, 0]
            return round(float(close.iloc[-1]), 2)
    except Exception:
        pass
    return 0.0


class PaperTrader:
    def __init__(self, username: str = 'Student'):
        os.makedirs(PORTFOLIO_DIR, exist_ok=True)
        self.username = username
        self.portfolio_file = os.path.join(PORTFOLIO_DIR, f"{username}_portfolio.json")
        self.portfolio = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.portfolio_file):
            with open(self.portfolio_file, 'r') as f:
                return json.load(f)
        return {
            'username': self.username, 'cash': 100000.0, 'positions': {},
            'trades': [], 'created': date.today().isoformat(),
            'total_value': 100000.0, 'return_pct': 0.0
        }

    def _save(self):
        with open(self.portfolio_file, 'w') as f:
            json.dump(self.portfolio, f, indent=2)

    def buy(self, ticker: str, shares: int) -> dict:
        ticker = ticker.upper()
        price = get_live_price(ticker)
        if price <= 0:
            return {'error': f'Could not fetch price for {ticker}'}
        cost = shares * price
        if cost > self.portfolio['cash']:
            return {'error': f'Insufficient funds. Cost: ${cost:,.2f}, Cash: ${self.portfolio["cash"]:,.2f}'}

        self.portfolio['cash'] -= cost
        if ticker not in self.portfolio['positions']:
            self.portfolio['positions'][ticker] = {'shares': 0, 'avg_price': 0}

        pos = self.portfolio['positions'][ticker]
        total_shares = pos['shares'] + shares
        pos['avg_price'] = ((pos['shares'] * pos['avg_price']) + cost) / total_shares
        pos['shares'] = total_shares

        self.portfolio['trades'].append({
            'action': 'BUY', 'ticker': ticker, 'shares': shares,
            'price': round(price, 2), 'cost': round(cost, 2),
            'date': datetime.now().isoformat()
        })
        self._update_values()
        return {'status': 'FILLED', 'ticker': ticker, 'shares': shares, 'price': price}

    def sell(self, ticker: str, shares: int) -> dict:
        ticker = ticker.upper()
        if ticker not in self.portfolio['positions']:
            return {'error': f'No position in {ticker}'}
        pos = self.portfolio['positions'][ticker]
        if shares > pos['shares']:
            return {'error': f'Only own {pos["shares"]} shares of {ticker}'}

        price = get_live_price(ticker)
        if price <= 0:
            return {'error': f'Could not fetch price for {ticker}'}

        revenue = shares * price
        pnl = (price - pos['avg_price']) * shares
        self.portfolio['cash'] += revenue
        pos['shares'] -= shares
        if pos['shares'] == 0:
            del self.portfolio['positions'][ticker]

        self.portfolio['trades'].append({
            'action': 'SELL', 'ticker': ticker, 'shares': shares,
            'price': round(price, 2), 'revenue': round(revenue, 2),
            'pnl': round(pnl, 2), 'date': datetime.now().isoformat()
        })
        self._update_values()
        return {'status': 'FILLED', 'ticker': ticker, 'shares': shares, 'pnl': pnl}

    def _update_values(self):
        total = self.portfolio['cash']
        for ticker, pos in self.portfolio['positions'].items():
            price = get_live_price(ticker) or pos['avg_price']
            total += pos['shares'] * price
        self.portfolio['total_value'] = round(total, 2)
        self.portfolio['return_pct'] = round(((total - 100000) / 100000) * 100, 2)
        self._save()

    def show(self) -> str:
        self._update_values()
        p = self.portfolio
        out = f"\nYUCLAW Paper Portfolio: {p['username']}"
        out += f"\n{'=' * 45}"
        out += f"\n  Cash:        ${p['cash']:,.2f}"
        out += f"\n  Total Value: ${p['total_value']:,.2f}"
        out += f"\n  Return:      {p['return_pct']:+.2f}%\n"
        if p['positions']:
            out += f"\n  Positions:"
            for t, pos in p['positions'].items():
                out += f"\n    {t:6} | {pos['shares']:4} shares @ ${pos['avg_price']:,.2f}"
        else:
            out += "\n  No positions. Use: yuclaw trade BUY AAPL 10"
        return out
