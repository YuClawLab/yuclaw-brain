"""
YUCLAW Portfolio Optimizer — Kelly criterion + mean-variance.
Tells users exactly: buy X% of portfolio in each ticker.
"""
import yfinance as yf
import numpy as np
import json, os
from datetime import date


class PortfolioOptimizer:

    def fetch_returns(self, tickers: list, period: str = '1y') -> dict:
        returns = {}
        for t in tickers:
            try:
                data = yf.download(t, period=period, interval='1d', progress=False)
                close = data['Close']
                if hasattr(close, 'columns'):
                    close = close.iloc[:, 0]
                prices = close.dropna().values
                if len(prices) > 20:
                    returns[t] = np.diff(np.log(prices))
            except Exception:
                pass
        return returns

    def kelly_sizing(self, returns: np.ndarray) -> float:
        mean = np.mean(returns)
        var = np.var(returns)
        if var == 0:
            return 0
        kelly = mean / var
        return float(np.clip(kelly * 252, 0, 0.5))

    def optimize(self, signals: list) -> dict:
        buy_signals = [s for s in signals if 'BUY' in s.get('signal', '')][:8]
        if not buy_signals:
            return {'error': 'No buy signals to optimize'}

        tickers = [s['ticker'] for s in buy_signals]
        returns_data = self.fetch_returns(tickers)
        if not returns_data:
            return {'error': 'Could not fetch returns'}

        allocations = {}
        total_kelly = 0

        for ticker in tickers:
            if ticker in returns_data:
                kelly = self.kelly_sizing(returns_data[ticker])
                signal_score = next(
                    (s['score'] for s in buy_signals if s['ticker'] == ticker), 0.5)
                adjusted_kelly = kelly * abs(signal_score)
                allocations[ticker] = adjusted_kelly
                total_kelly += adjusted_kelly

        if total_kelly > 0:
            allocations = {t: round(v / total_kelly, 3) for t, v in allocations.items()}

        cash_reserve = 0.20
        equity_allocation = 1 - cash_reserve
        final_allocations = {t: round(v * equity_allocation, 3) for t, v in allocations.items()}
        final_allocations['CASH'] = cash_reserve

        result = {
            'date': date.today().isoformat(),
            'allocations': final_allocations,
            'method': 'Kelly + Signal Score',
            'cash_reserve': cash_reserve,
            'note': 'These are suggestions only. Not financial advice.'
        }

        os.makedirs('output', exist_ok=True)
        with open('output/portfolio_optimization.json', 'w') as f:
            json.dump(result, f, indent=2)

        return result


if __name__ == '__main__':
    optimizer = PortfolioOptimizer()
    signals = [
        {'ticker': 'NVDA', 'signal': 'STRONG_BUY', 'score': 0.85},
        {'ticker': 'LUNR', 'signal': 'STRONG_BUY', 'score': 0.933},
        {'ticker': 'ASTS', 'signal': 'STRONG_BUY', 'score': 0.848},
        {'ticker': 'DELL', 'signal': 'BUY', 'score': 0.826},
        {'ticker': 'MRNA', 'signal': 'BUY', 'score': 0.821},
    ]
    result = optimizer.optimize(signals)
    print("\nYUCLAW Portfolio Optimization")
    print("=" * 40)
    print(f"Method: {result.get('method')}")
    print(f"\nRecommended Allocations:")
    for ticker, pct in result.get('allocations', {}).items():
        bar = '#' * int(pct * 30)
        print(f"  {ticker:6} {pct:6.1%} {bar}")
    print(f"\n{result.get('note')}")
