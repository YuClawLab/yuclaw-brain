"""
YUCLAW Dual-Source Price Verifier.
Primary: Finnhub (real-time). Backup: yfinance.
Cross-validates prices between sources.
"""
import yfinance as yf
import requests
import json
import os
from datetime import datetime

FINNHUB_KEY = os.environ.get('FINNHUB_KEY', '')


def get_finnhub_price(ticker: str) -> float:
    if not FINNHUB_KEY:
        return 0.0
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        price = data.get('c', 0)
        return round(float(price), 2) if price else 0.0
    except Exception:
        return 0.0


def get_yfinance_price(ticker: str) -> float:
    try:
        stock = yf.Ticker(ticker)
        fi = stock.fast_info
        price = getattr(fi, 'last_price', None) or getattr(fi, 'previous_close', None) or 0
        return round(float(price), 2) if price else 0.0
    except Exception:
        return 0.0


def verify_price(ticker: str) -> dict:
    primary = get_finnhub_price(ticker)
    backup = get_yfinance_price(ticker)

    if primary > 0 and backup > 0:
        diff_pct = abs(primary - backup) / backup
        verified = diff_pct < 0.02
        final_price = primary
        status = 'VERIFIED' if verified else 'MISMATCH'
    elif primary > 0:
        final_price = primary
        verified = True
        status = 'Finnhub'
    elif backup > 0:
        final_price = backup
        verified = False
        status = 'yfinance only'
    else:
        final_price = 0.0
        verified = False
        status = 'NO DATA'

    return {
        'ticker': ticker, 'price': final_price,
        'finnhub': primary, 'yfinance': backup,
        'verified': verified, 'status': status,
        'timestamp': datetime.utcnow().isoformat()
    }


def update_dashboard_state():
    try:
        signals = json.load(open('output/aggregated_signals.json'))
    except Exception:
        print("No signals")
        return

    print(f"=== Dual-source verification {datetime.utcnow().strftime('%H:%M')} UTC ===")

    for s in signals:
        result = verify_price(s['ticker'])
        s['price'] = result['price']
        s['verified'] = result['verified']
        s['price_status'] = result['status']
        s['price_updated'] = result['timestamp']
        print(f"  {s['ticker']:6} ${result['price']:8.2f} {result['status']}")

    valid = [s for s in signals if s.get('price', 0) > 0]

    with open('output/aggregated_signals.json', 'w') as f:
        json.dump(valid, f, indent=2)

    try:
        regime = json.load(open('output/macro_regime.json'))
    except Exception:
        regime = {}
    try:
        risk = json.load(open('output/risk_analysis.json'))
    except Exception:
        risk = []

    state = {
        'last_updated': datetime.utcnow().isoformat(),
        'signals': valid[:20],
        'regime': regime,
        'risk': risk[:4] if isinstance(risk, list) else [],
        'stats': {
            'total_signals': len(valid),
            'verified_prices': sum(1 for s in valid if s.get('verified')),
            'buy_signals': len([s for s in valid if 'BUY' in s.get('signal', '')]),
            'sell_signals': len([s for s in valid if 'SELL' in s.get('signal', '')])
        }
    }

    # Save to both locations
    with open('output/dashboard_state.json', 'w') as f:
        json.dump(state, f, indent=2)

    docs_data = os.path.expanduser('~/yuclaw/docs/data')
    os.makedirs(docs_data, exist_ok=True)
    with open(f'{docs_data}/dashboard_state.json', 'w') as f:
        json.dump(state, f, indent=2)

    verified = sum(1 for s in valid if s.get('verified'))
    print(f"\nVerified: {verified}/{len(valid)}")


if __name__ == '__main__':
    update_dashboard_state()
