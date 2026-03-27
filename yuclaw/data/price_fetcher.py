"""
YUCLAW Price Fetcher — real-time prices.
Uses yfinance fast_info with fallbacks.
"""
import yfinance as yf
import json, os


def get_price(ticker: str) -> float:
    try:
        stock = yf.Ticker(ticker)

        # Method 1: fast_info — handles market closed via previous_close
        info = stock.fast_info
        price = getattr(info, 'last_price', None) or getattr(info, 'previous_close', None)

        if price and price > 0:
            return round(float(price), 2)

        # Method 2: history fallback
        hist = stock.history(period='1d')
        if not hist.empty:
            close = hist['Close']
            if hasattr(close, 'columns'):
                close = close.iloc[:, 0]
            return round(float(close.iloc[-1]), 2)

    except Exception as e:
        print(f"Error fetching {ticker}: {e}")

    return 0.0


def update_all_prices():
    try:
        signals = json.load(open('output/aggregated_signals.json'))
    except Exception:
        print("No signals file")
        return []

    print(f"=== Fetching prices for {len(signals)} tickers ===")

    for s in signals:
        ticker = s['ticker']
        price = get_price(ticker)
        s['price'] = price
        status = f"${price:.2f}" if price > 0 else "no data"
        print(f"  {ticker:6} {status}")

    valid = [s for s in signals if s['price'] > 0]

    with open('output/aggregated_signals.json', 'w') as f:
        json.dump(valid, f, indent=2)

    print(f"\nValid: {len(valid)} | Removed: {len(signals) - len(valid)}")
    return valid


if __name__ == '__main__':
    signals = update_all_prices()
    print("\n=== Top 10 ===")
    for s in signals[:10]:
        print(f"  {s['ticker']:6} {s['signal']:12} {s['score']:+.3f} ${s['price']:.2f}")
