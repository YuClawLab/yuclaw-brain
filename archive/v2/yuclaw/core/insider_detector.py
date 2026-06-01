"""
YUCLAW Insider Trading Detector.
SEC Form 4 filings — when insiders buy, pay attention.
"""
import requests, json, os
from datetime import date, timedelta


class InsiderDetector:

    def get_insider_trades(self, ticker: str) -> list:
        try:
            headers = {'User-Agent': 'YUCLAW yuclaw@github.com'}
            search_url = (
                f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22"
                f"&dateRange=custom"
                f"&startdt={(date.today() - timedelta(days=30)).isoformat()}"
                f"&enddt={date.today().isoformat()}&forms=4"
            )
            resp = requests.get(search_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                filings = data.get('hits', {}).get('hits', [])
                trades = []
                for f in filings[:5]:
                    source = f.get('_source', {})
                    trades.append({
                        'ticker': ticker,
                        'filed': source.get('file_date', ''),
                        'form': source.get('form_type', '4'),
                        'entity': source.get('entity_name', ''),
                        'signal': 'INSIDER_ACTIVITY'
                    })
                return trades
        except Exception:
            pass
        return []

    def scan_universe(self, tickers: list) -> list:
        print("Scanning insider trading activity...")
        all_trades = []
        for ticker in tickers[:10]:
            trades = self.get_insider_trades(ticker)
            if trades:
                all_trades.extend(trades)
                print(f"  {ticker}: {len(trades)} insider filings")
        os.makedirs('output', exist_ok=True)
        with open('output/insider_trades.json', 'w') as f:
            json.dump(all_trades, f, indent=2)
        return all_trades


if __name__ == '__main__':
    detector = InsiderDetector()
    trades = detector.scan_universe([
        'NVDA', 'AMD', 'LUNR', 'ASTS', 'MRNA', 'DELL', 'MSFT', 'AAPL'
    ])
    print(f"\nInsider activity found: {len(trades)} filings")
