"""
YUCLAW Swarm: Async Red/Blue/Oracle debate engine.
Bull and Bear argue in parallel, Oracle delivers final verdict.
"""
import json, os, requests, time, concurrent.futures
from datetime import datetime

MODEL = os.environ.get('YUCLAW_SUPER_MODEL', '/home/zhangd2/aimo/models/Nemotron-Cascade-2-30B-A3B')
ENDPOINT = os.environ.get('YUCLAW_SUPER_ENDPOINT', 'http://localhost:8001/v1')

BULL_SYSTEM = "You are Agent Alpha (Bull). Argue FORCEFULLY why this trade will succeed. Be specific. Max 3 sentences."
BEAR_SYSTEM = "You are Agent Omega (Bear). Destroy the Bull's thesis. Find every reason this trade will FAIL. Max 3 sentences."
ORACLE_SYSTEM = "You are The Oracle. Weigh Bull and Bear. Output EXACTLY:\nVERDICT: [EXECUTE/REDUCE/REJECT]\nCONVICTION: [0.0-1.0]\nKELLY: [0-50%]\nREASONING: [1 sentence]"


def query_nemotron(system_prompt: str, user_prompt: str) -> str:
    try:
        resp = requests.post(
            f'{ENDPOINT}/chat/completions',
            json={
                'model': MODEL,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                'max_tokens': 200,
                'temperature': 0.7
            },
            timeout=120
        )
        msg = resp.json()['choices'][0]['message']
        return (msg.get('content') or msg.get('reasoning_content') or '').strip()
    except Exception as e:
        return f"[Agent offline: {e}]"


def debate_signal(s: dict) -> dict:
    context = f"Ticker: {s['ticker']}, Signal: {s.get('signal')}, Score: {s.get('score', 0):+.3f}, Price: ${s.get('price', 0):.2f}"
    start = time.time()

    # Sequential — llama-server handles one request at a time
    bull_case = query_nemotron(BULL_SYSTEM, f"Defend this trade: {context}")
    bear_case = query_nemotron(BEAR_SYSTEM, f"Attack this trade: {context}")

    oracle_prompt = f"Trade: {context}\nBULL: {bull_case}\nBEAR: {bear_case}\nDeliver final verdict."
    oracle_verdict = query_nemotron(ORACLE_SYSTEM, oracle_prompt)

    verdict, conviction = 'REJECT', 0.5
    for line in oracle_verdict.split('\n'):
        if 'VERDICT:' in line:
            verdict = line.split(':', 1)[1].strip()
        elif 'CONVICTION:' in line:
            try:
                conviction = float(line.split(':', 1)[1].strip())
            except Exception:
                pass

    elapsed = time.time() - start
    print(f"\n  {s['ticker']} ORACLE: {verdict} | Conviction: {conviction:.2f} ({elapsed:.1f}s)")

    return {
        'ticker': s['ticker'], 'signal': s.get('signal'), 'score': s.get('score', 0),
        'bull': bull_case[:200], 'bear': bear_case[:200],
        'oracle_verdict': verdict, 'conviction': conviction,
        'timestamp': datetime.now().isoformat(), 'elapsed_s': round(elapsed, 1)
    }


def run_swarm(top_n=3):
    print("=== YUCLAW Swarm: Bull vs Bear vs Oracle ===")
    try:
        signals = json.load(open('output/aggregated_signals.json'))
    except Exception:
        print("No signals file")
        return []

    valid = sorted(
        [s for s in signals if s.get('price', 0) > 0],
        key=lambda x: abs(x.get('score', 0)), reverse=True
    )[:top_n]

    results = []
    for s in valid:
        result = debate_signal(s)
        results.append(result)

    os.makedirs('output/swarm', exist_ok=True)
    with open('output/swarm/latest_debate.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nSwarm complete: {len(results)} signals debated")
    return results


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    run_swarm()
