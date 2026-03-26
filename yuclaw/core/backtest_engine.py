"""
YUCLAW Backtest Engine — anyone can backtest any strategy.
Real prices. Real math. No LLM estimation.
"""
import yfinance as yf
import numpy as np
import json, os
from datetime import date, datetime, timedelta


class BacktestEngine:

    def __init__(self):
        self.results = {}

    def fetch_history(self, ticker: str, years: int = 3) -> np.ndarray:
        try:
            data = yf.download(
                ticker,
                start=(datetime.now() - timedelta(days=365 * years)).strftime('%Y-%m-%d'),
                end=datetime.now().strftime('%Y-%m-%d'),
                interval='1d', progress=False
            )
            close = data['Close']
            if hasattr(close, 'columns'):
                close = close.iloc[:, 0]
            return close.dropna().values
        except Exception:
            return np.array([])

    def momentum_strategy(self, prices: np.ndarray, lookback: int = 20) -> dict:
        if len(prices) < lookback + 10:
            return {}

        returns = np.diff(np.log(prices))
        portfolio_returns = []

        for i in range(lookback, len(prices) - 1):
            momentum = (prices[i] - prices[i - lookback]) / prices[i - lookback]
            position = 1 if momentum > 0 else -1
            portfolio_returns.append(position * returns[i])

        portfolio_returns = np.array(portfolio_returns)

        annual_return = np.mean(portfolio_returns) * 252
        annual_vol = np.std(portfolio_returns) * np.sqrt(252)
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0

        cumulative = np.cumprod(1 + portfolio_returns)
        rolling_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - rolling_max) / rolling_max
        max_drawdown = abs(drawdowns.min())

        calmar = annual_return / max_drawdown if max_drawdown > 0 else 0
        win_rate = np.sum(portfolio_returns > 0) / len(portfolio_returns)

        return {
            'annual_return': round(float(annual_return), 4),
            'annual_vol': round(float(annual_vol), 4),
            'sharpe': round(float(sharpe), 3),
            'max_drawdown': round(float(max_drawdown), 4),
            'calmar': round(float(calmar), 3),
            'win_rate': round(float(win_rate), 3),
            'total_trades': len(portfolio_returns),
            'lookback': lookback
        }

    def backtest_ticker(self, ticker: str, years: int = 3) -> dict:
        prices = self.fetch_history(ticker, years)
        if len(prices) < 60:
            return {'ticker': ticker, 'error': 'insufficient data'}

        results = {
            'ticker': ticker, 'years': years,
            'date': date.today().isoformat(), 'strategies': {}
        }

        for lookback in [10, 20, 60]:
            name = f"momentum_{lookback}d"
            result = self.momentum_strategy(prices, lookback)
            if result:
                results['strategies'][name] = result

        if results['strategies']:
            best = max(results['strategies'].items(), key=lambda x: x[1]['calmar'])
            results['best_strategy'] = best[0]
            results['best_calmar'] = best[1]['calmar']
            results['best_sharpe'] = best[1]['sharpe']
            results['best_annual_return'] = best[1]['annual_return']

        return results

    def run_universe(self, tickers: list) -> list:
        print(f"Backtesting {len(tickers)} tickers...")
        all_results = []

        for ticker in tickers:
            result = self.backtest_ticker(ticker)
            if 'best_calmar' in result and result['best_calmar'] > 0.5:
                all_results.append(result)
                print(f"  {ticker:6} Calmar:{result['best_calmar']:.3f} "
                      f"Ret:{result['best_annual_return']:.1%} "
                      f"Sharpe:{result['best_sharpe']:.2f}")

        all_results.sort(key=lambda x: x.get('best_calmar', 0), reverse=True)

        os.makedirs('output', exist_ok=True)
        with open('output/backtest_results.json', 'w') as f:
            json.dump(all_results, f, indent=2)

        return all_results


if __name__ == '__main__':
    engine = BacktestEngine()
    tickers = [
        'NVDA', 'AMD', 'AAPL', 'MSFT', 'GOOGL',
        'LUNR', 'ASTS', 'DELL', 'MRNA', 'KLAC',
        'TSLA', 'META', 'AMZN', 'JPM', 'GS'
    ]
    results = engine.run_universe(tickers)
    print(f"\n=== Top Strategies by Calmar ===")
    for r in results[:5]:
        print(f"  {r['ticker']:6} Calmar:{r['best_calmar']:.3f} "
              f"Ann.Ret:{r['best_annual_return']:.1%} Sharpe:{r['best_sharpe']:.2f}")
    print(f"\nBacktest complete: {len(results)} profitable strategies found")
