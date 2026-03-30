"""
YUCLAW Sector Rotation — where money is moving. Finnhub quotes.
"""
import requests
import json
import os
from datetime import date

FINNHUB_KEY = os.environ.get('FINNHUB_KEY', '')

SECTORS = {
    'XLK': 'Technology', 'XLF': 'Financials', 'XLE': 'Energy',
    'XLV': 'Healthcare', 'XLI': 'Industrials', 'XLP': 'Consumer Staples',
    'XLY': 'Consumer Disc', 'XLU': 'Utilities', 'XLB': 'Materials',
    'XLRE': 'Real Estate', 'XLC': 'Communication',
    'GLD': 'Gold', 'TLT': 'Bonds', 'UUP': 'Dollar'
}


def get_quote(ticker: str) -> dict:
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
        resp = requests.get(url, timeout=5)
        return resp.json()
    except Exception:
        return {}


def detect_sector_rotation() -> dict:
    print("=== Sector Rotation — Finnhub ===")
    rotation = []

    for etf, name in SECTORS.items():
        quote = get_quote(etf)
        if not quote or not quote.get('c'):
            continue
        price = quote['c']
        change_pct = quote.get('dp', 0)
        signal = 'INFLOW' if change_pct > 0.5 else 'OUTFLOW' if change_pct < -0.5 else 'NEUTRAL'
        rotation.append({
            'etf': etf, 'sector': name, 'price': round(float(price), 2),
            'change_pct': round(float(change_pct), 2), 'signal': signal
        })
        icon = 'IN ' if signal == 'INFLOW' else 'OUT' if signal == 'OUTFLOW' else '---'
        print(f"  [{icon}] {etf:5} {name:22} {change_pct:+.2f}% {signal}")

    rotation.sort(key=lambda x: x['change_pct'], reverse=True)
    result = {
        'date': date.today().isoformat(), 'rotation': rotation,
        'top_inflows': [r for r in rotation if r['signal'] == 'INFLOW'][:3],
        'top_outflows': [r for r in rotation if r['signal'] == 'OUTFLOW'][:3]
    }
    os.makedirs('output', exist_ok=True)
    with open('output/sector_rotation.json', 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nInflows: {[r['sector'] for r in result['top_inflows']]}")
    print(f"Outflows: {[r['sector'] for r in result['top_outflows']]}")
    return result


if __name__ == '__main__':
    detect_sector_rotation()
