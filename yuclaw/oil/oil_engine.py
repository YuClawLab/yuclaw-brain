"""
YUCLAW Oil Intelligence — Nemotron 120B + EIA + Finnhub.
Daily 6:30 AM ET brief + Wednesday 10:35 AM EIA drop analysis.
"""
import requests
import json
import os
from datetime import date, datetime

FINNHUB_KEY = os.environ.get('FINNHUB_KEY', '')
EIA_API_KEY = os.environ.get('EIA_KEY', '')
MODEL = os.environ.get('YUCLAW_SUPER_MODEL', 'nemotron-q4km.gguf')
ENDPOINT = os.environ.get('YUCLAW_SUPER_ENDPOINT', 'http://localhost:8001/v1')


def get_eia_inventory() -> dict:
    print("=== Fetching EIA inventory ===")
    if not EIA_API_KEY:
        print("  ERROR: EIA_KEY missing. Add to ~/.yuclaw_env")
        return {'inventory_mb': 0, 'change_mb': 0, 'direction': 'UNKNOWN', 'source': 'unavailable'}
    try:
        url = "https://api.eia.gov/v2/petroleum/sum/sndw/data/"
        params = {
            'frequency': 'weekly',
            'data[0]': 'value',
            'sort[0][column]': 'period',
            'sort[0][direction]': 'desc',
            'offset': 0,
            'length': 2,
            'api_key': EIA_API_KEY
        }
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"  EIA API Error: {resp.status_code}")
            return {'inventory_mb': 0, 'change_mb': 0, 'direction': 'UNKNOWN', 'source': 'unavailable'}
        data = resp.json()
        records = data.get('response', {}).get('data', [])
        if records:
            latest = records[0]
            prev = records[1] if len(records) > 1 else latest
            change = float(latest.get('value', 0)) - float(prev.get('value', 0))
            result = {
                'period': latest.get('period', ''),
                'inventory_mb': round(float(latest.get('value', 0)) / 1000, 1),
                'change_mb': round(change / 1000, 1),
                'direction': 'BUILD' if change > 0 else 'DRAW',
                'source': 'EIA'
            }
            print(f"  EIA: {result['direction']} {abs(result['change_mb']):.1f}M barrels")
            return result
    except Exception as e:
        print(f"  EIA error: {e}")
    return {'inventory_mb': 0, 'change_mb': 0, 'direction': 'UNKNOWN', 'source': 'unavailable'}


def get_oil_prices() -> dict:
    print("=== Fetching oil prices ===")
    prices = {}
    tickers = {'CL=F': 'WTI', 'BZ=F': 'Brent', 'XOM': 'ExxonMobil', 'CVX': 'Chevron',
               'COP': 'ConocoPhillips', 'SLB': 'Schlumberger', 'XLE': 'Energy ETF'}
    for ticker, name in tickers.items():
        try:
            if FINNHUB_KEY and '=' not in ticker:
                url = f"https://finnhub.io/api/v1/quote?symbol={ticker}&token={FINNHUB_KEY}"
                resp = requests.get(url, timeout=5)
                q = resp.json()
                prices[name] = {'price': round(q.get('c', 0), 2), 'change_pct': round(q.get('dp', 0), 2)}
            else:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                fi = stock.fast_info
                p = getattr(fi, 'last_price', None) or getattr(fi, 'previous_close', None) or 0
                prices[name] = {'price': round(float(p), 2), 'change_pct': 0}
            print(f"  {name}: ${prices[name]['price']:.2f} ({prices[name]['change_pct']:+.2f}%)")
        except Exception:
            pass
    return prices


def generate_oil_brief(eia: dict, prices: dict) -> str:
    print("=== Generating Nemotron oil brief ===")
    prompt = f"""YUCLAW Oil Intelligence Brief — {date.today()}

EIA Inventory: {eia.get('direction','UNKNOWN')} {abs(eia.get('change_mb',0)):.1f}M barrels (period: {eia.get('period','')})
Total inventory: {eia.get('inventory_mb',0):.1f}M barrels

Oil Prices:
{json.dumps(prices, indent=2)}

Generate institutional oil brief:
1. Supply/demand assessment from EIA data
2. Price outlook for WTI and Brent
3. Energy equity positioning (XOM, CVX, COP, SLB)
4. Risk factors
5. Specific trade recommendation

Use only the data provided. Be specific."""

    try:
        resp = requests.post(
            f'{ENDPOINT}/chat/completions',
            json={
                'model': MODEL,
                'messages': [
                    {'role': 'system', 'content': 'Senior energy sector analyst. Data-driven, specific.'},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 600
            },
            timeout=120
        )
        msg = resp.json()['choices'][0]['message']
        return msg.get('content') or msg.get('reasoning_content') or ''
    except Exception as e:
        return f"Nemotron unavailable: {e}"


def run_oil_pipeline():
    print(f"\n{'=' * 60}")
    print(f"YUCLAW Oil Intelligence — {date.today()}")
    print(f"{'=' * 60}")

    eia = get_eia_inventory()
    prices = get_oil_prices()
    brief = generate_oil_brief(eia, prices)

    result = {
        'date': date.today().isoformat(),
        'timestamp': datetime.now().isoformat(),
        'eia': eia,
        'prices': prices,
        'brief': brief[:1000],
    }

    os.makedirs('output/oil', exist_ok=True)
    with open(f'output/oil/{date.today()}_brief.json', 'w') as f:
        json.dump(result, f, indent=2)
    with open(f'output/oil/{date.today()}_brief.txt', 'w') as f:
        f.write(brief)

    print(f"\nBrief ({len(brief)} chars):")
    print(brief[:500])
    return result


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    run_oil_pipeline()
