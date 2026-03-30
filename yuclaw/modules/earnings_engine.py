"""
YUCLAW Earnings Engine — Finnhub institutional feed.
"""
import requests
import json
import os
from datetime import date, timedelta

FINNHUB_KEY = os.environ.get('FINNHUB_KEY', '')


def get_earnings_this_week(tickers: list) -> dict:
    print("=== Earnings Calendar — Finnhub ===")
    results = {}
    today = date.today()
    week_end = today + timedelta(days=7)

    try:
        url = "https://finnhub.io/api/v1/calendar/earnings"
        params = {'from': str(today), 'to': str(week_end), 'token': FINNHUB_KEY}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        earnings_list = data.get('earningsCalendar', [])

        ticker_set = set(tickers)
        for item in earnings_list:
            symbol = item.get('symbol', '')
            if symbol not in ticker_set:
                continue
            earn_date = item.get('date', '')
            days_until = (date.fromisoformat(earn_date) - today).days
            results[symbol] = {
                'earnings_date': earn_date,
                'days_until': days_until,
                'eps_estimate': item.get('epsEstimate', 0),
                'action': 'REDUCE_POSITION' if days_until <= 2 else 'WATCH'
            }
            print(f"  {symbol:6} earnings {earn_date} ({days_until}d) — {results[symbol]['action']}")
    except Exception as e:
        print(f"Error: {e}")

    os.makedirs('output', exist_ok=True)
    with open('output/earnings_this_week.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Earnings this week: {len(results)} tickers")
    return results


if __name__ == '__main__':
    try:
        signals = json.load(open('output/aggregated_signals.json'))
        tickers = [s['ticker'] for s in signals[:50]]
    except Exception:
        tickers = ['LUNR', 'ASTS', 'NVDA', 'AAPL', 'TSLA', 'DELL', 'MRNA']
    get_earnings_this_week(tickers)
