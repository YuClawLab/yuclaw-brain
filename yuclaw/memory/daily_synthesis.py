"""
Daily synthesis — Portfolio Memory + Nemotron + all signals in one output.
This is what institutional investors see every morning.
"""
import json, os, sys, requests
sys.path.insert(0, '.')


def generate_daily_synthesis():
    context = {}

    for f, key in [
        ('output/aggregated_signals.json', 'signals'),
        ('output/backtest_all.json', 'backtests'),
        ('output/risk_analysis.json', 'risk'),
    ]:
        try:
            context[key] = json.load(open(f))
        except Exception:
            context[key] = []

    prompt = f"""
YUCLAW Daily Institutional Synthesis — {__import__('datetime').date.today()}

Signals: {json.dumps(context.get('signals', [])[:5])}
Best Strategy Calmar: {max([b.get('calmar', 0) for b in context.get('backtests', [{}])], default=0):.3f}
Risk: {json.dumps(context.get('risk', [{}])[0] if context.get('risk') else {})}

Generate a 5-section institutional brief:
1. Executive Summary (2 sentences)
2. Top 3 Opportunities with thesis
3. Risk Factors
4. Recommended Actions
5. 30-Day Track Record Status

Use only the data provided. No estimation.
"""
    try:
        model = os.getenv('YUCLAW_SUPER_MODEL', 'nemotron-q4km.gguf')
        endpoint = os.getenv('YUCLAW_SUPER_ENDPOINT', 'http://localhost:8001/v1')
        resp = requests.post(
            f'{endpoint}/chat/completions',
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You are an institutional quantitative analyst. Use only provided data.'},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 800
            },
            timeout=300
        )
        msg = resp.json()['choices'][0]['message']
        brief = msg.get('content') or msg.get('reasoning_content') or ''

        os.makedirs('output/daily', exist_ok=True)
        date = __import__('datetime').date.today().isoformat()
        with open(f'output/daily/{date}_brief.txt', 'w') as f:
            f.write(brief)
        print(brief)
        return brief
    except Exception as e:
        print(f"Error: {e}")
        return None


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    generate_daily_synthesis()
