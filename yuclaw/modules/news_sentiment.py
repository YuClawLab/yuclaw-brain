"""
YUCLAW News Sentiment — Finnhub news + Nemotron 120B scoring.
"""
import requests
import json
import os
import re
from datetime import date, timedelta

FINNHUB_KEY = os.environ.get('FINNHUB_KEY', '')
MODEL = os.environ.get('YUCLAW_SUPER_MODEL', 'nemotron-3-super-local')
ENDPOINT = os.environ.get('YUCLAW_SUPER_ENDPOINT', 'http://localhost:11434/v1')


def get_news(ticker: str) -> list:
    try:
        today = date.today()
        week_ago = today - timedelta(days=7)
        url = "https://finnhub.io/api/v1/company-news"
        params = {'symbol': ticker, 'from': str(week_ago), 'to': str(today), 'token': FINNHUB_KEY}
        resp = requests.get(url, params=params, timeout=5)
        return resp.json()[:5]
    except Exception:
        return []


def score_with_nemotron(ticker: str, headlines: list) -> dict:
    if not headlines:
        return {'sentiment': 'NEUTRAL', 'score': 0.0, 'reason': 'No news'}

    headlines_text = '\n'.join([
        f"- {h.get('headline', '')} {h.get('summary', '')[:100]}"
        for h in headlines
    ])

    try:
        resp = requests.post(
            f'{ENDPOINT}/chat/completions',
            json={
                'model': MODEL,
                'messages': [
                    {'role': 'system', 'content': 'Analyze news. Respond ONLY with JSON: {"sentiment":"BULLISH|BEARISH|NEUTRAL","score":-1.0 to 1.0,"reason":"one sentence"}'},
                    {'role': 'user', 'content': f"Ticker: {ticker}\nNews:\n{headlines_text}\n\nJSON only."}
                ],
                'max_tokens': 300
            },
            timeout=120
        )
        msg = resp.json()['choices'][0]['message']
        # Prefer parsed content; reasoning_content holds raw thinking that often
        # leaks "We need to output JSON..." text instead of structured output.
        # Try both fields, return first that contains a parseable JSON object.
        for field in ('content', 'reasoning_content'):
            text = (msg.get(field) or '').strip()
            if not text:
                continue
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    continue
        return {'sentiment': 'NEUTRAL', 'score': 0.0, 'reason': 'Unable to parse model response'}
    except Exception as e:
        return {'sentiment': 'NEUTRAL', 'score': 0.0, 'reason': str(e)[:80]}


def scan_all_sentiment(tickers: list) -> list:
    print("=== News Sentiment — Nemotron 120B ===")
    results = []

    for ticker in tickers:
        news = get_news(ticker)
        scoring = score_with_nemotron(ticker, news)
        result = {
            'ticker': ticker,
            'sentiment': scoring.get('sentiment', 'NEUTRAL'),
            'score': scoring.get('score', 0.0),
            'reason': scoring.get('reason', ''),
            'news_count': len(news),
            'latest_headline': news[0].get('headline', '')[:100] if news else '',
            'date': date.today().isoformat()
        }
        results.append(result)
        s = result['sentiment']
        icon = 'BULL' if s == 'BULLISH' else 'BEAR' if s == 'BEARISH' else 'NEUT'
        print(f"  [{icon}] {ticker:6} {s:8} {result['score']:+.2f} — {result['reason'][:60]}")

    results.sort(key=lambda x: x.get('score', 0), reverse=True)
    os.makedirs('output', exist_ok=True)
    with open('output/news_sentiment.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nBullish: {len([r for r in results if r['sentiment'] == 'BULLISH'])}")
    print(f"Bearish: {len([r for r in results if r['sentiment'] == 'BEARISH'])}")
    return results


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    try:
        signals = json.load(open('output/aggregated_signals.json'))
        tickers = [s['ticker'] for s in signals[:10]]
    except Exception:
        tickers = ['LUNR', 'ASTS', 'NVDA', 'AAPL', 'TSLA']
    scan_all_sentiment(tickers)
