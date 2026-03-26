"""
YUCLAW Earnings Calendar — know what moves markets.
Combines earnings dates with YUCLAW signals.
"""
import yfinance as yf
import json, os
from datetime import date


class EarningsCalendar:

    WATCHLIST = [
        'NVDA', 'AMD', 'AAPL', 'MSFT', 'GOOGL', 'META', 'AMZN', 'TSLA',
        'LUNR', 'ASTS', 'MRNA', 'KLAC', 'AMAT', 'MRVL', 'DELL', 'MU'
    ]

    def get_upcoming_earnings(self, tickers: list = None) -> list:
        tickers = tickers or self.WATCHLIST
        upcoming = []

        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                cal = stock.calendar
                if cal is not None and hasattr(cal, 'empty') and not cal.empty:
                    earnings_date = cal.iloc[0].get('Earnings Date')
                    if earnings_date:
                        days_until = (earnings_date.date() - date.today()).days
                        if 0 <= days_until <= 30:
                            info = stock.info
                            upcoming.append({
                                'ticker': ticker,
                                'earnings_date': str(earnings_date.date()),
                                'days_until': days_until,
                                'company': info.get('shortName', ticker),
                                'sector': info.get('sector', 'Unknown'),
                            })
            except Exception:
                pass

        upcoming.sort(key=lambda x: x['days_until'])

        os.makedirs('output', exist_ok=True)
        with open('output/earnings_calendar.json', 'w') as f:
            json.dump(upcoming, f, indent=2)

        return upcoming


if __name__ == '__main__':
    calendar = EarningsCalendar()
    print("YUCLAW Earnings Calendar — Next 30 Days")
    print("=" * 50)
    upcoming = calendar.get_upcoming_earnings()
    if upcoming:
        for e in upcoming[:10]:
            print(f"  {e['ticker']:6} {e['earnings_date']} "
                  f"({e['days_until']}d) {e['company'][:25]}")
    else:
        print("  No upcoming earnings found in next 30 days")
    print(f"\nTotal upcoming: {len(upcoming)}")
