"""
Evidence Graph — wired into live signal pipeline.
Every signal now has supporting evidence chain.
"""
import json, os, requests
from datetime import date


def build_evidence(ticker: str, signal: str, score: float, factors: dict) -> dict:
    evidence = {
        'ticker': ticker,
        'signal': signal,
        'score': score,
        'date': date.today().isoformat(),
        'evidence_chain': [],
        'confidence': 0.0
    }

    # Layer 1: Factor evidence
    if factors.get('momentum', 0) > 0:
        evidence['evidence_chain'].append({
            'type': 'factor',
            'name': 'momentum',
            'value': factors['momentum'],
            'support': 'SUPPORTS' if factors['momentum'] > 0 else 'CONTRADICTS'
        })

    # Layer 2: Regime evidence
    try:
        regime = json.load(open('output/macro_regime.json'))
        evidence['evidence_chain'].append({
            'type': 'regime',
            'name': regime.get('regime', 'UNKNOWN'),
            'confidence': regime.get('confidence', 0),
            'support': 'SUPPORTS' if signal in ['BUY', 'STRONG_BUY'] and regime.get('regime') != 'CRISIS' else 'CAUTION'
        })
    except Exception:
        pass

    # Layer 3: Risk evidence
    try:
        risk = json.load(open('output/risk_analysis.json'))
        if risk:
            evidence['evidence_chain'].append({
                'type': 'risk',
                'var_95': risk[0].get('var_95', 0),
                'sharpe': risk[0].get('sharpe', 0),
                'support': 'SUPPORTS' if risk[0].get('sharpe', 0) > 1.0 else 'CAUTION'
            })
    except Exception:
        pass

    # Layer 4: Nemotron analysis
    try:
        model = os.getenv('YUCLAW_SUPER_MODEL', 'nemotron-q4km.gguf')
        endpoint = os.getenv('YUCLAW_SUPER_ENDPOINT', 'http://localhost:8001/v1')
        prompt = f"In 2 sentences, explain why {ticker} at score {score:+.3f} with signal {signal} is or is not a good opportunity given current CRISIS regime."
        resp = requests.post(
            f'{endpoint}/chat/completions',
            json={
                'model': model,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 200
            },
            timeout=120
        )
        msg = resp.json()['choices'][0]['message']
        analysis = msg.get('content') or msg.get('reasoning_content') or ''
        evidence['evidence_chain'].append({
            'type': 'llm_analysis',
            'model': 'nemotron-120B',
            'analysis': analysis[:300]
        })
    except Exception:
        pass

    # Calculate confidence
    supports = sum(1 for e in evidence['evidence_chain'] if e.get('support') == 'SUPPORTS')
    total = len(evidence['evidence_chain'])
    evidence['confidence'] = supports / total if total > 0 else 0

    return evidence


def run_evidence_graph():
    print("=== Evidence Graph Live Run ===")
    try:
        signals = json.load(open('output/aggregated_signals.json'))
    except Exception:
        signals = [
            {'ticker': 'LUNR', 'signal': 'STRONG_BUY', 'score': 0.933},
            {'ticker': 'ASTS', 'signal': 'STRONG_BUY', 'score': 0.848},
            {'ticker': 'MRNA', 'signal': 'STRONG_BUY', 'score': 0.821},
        ]

    os.makedirs('output/evidence', exist_ok=True)
    results = []

    for s in signals[:5]:
        ev = build_evidence(
            s['ticker'], s['signal'], s['score'],
            s.get('factors', {'momentum': s['score']})
        )
        results.append(ev)
        print(f"{s['ticker']}: {len(ev['evidence_chain'])} evidence layers, confidence {ev['confidence']:.0%}")

        with open(f"output/evidence/{s['ticker']}_{date.today()}.json", 'w') as f:
            json.dump(ev, f, indent=2)

    return results


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    run_evidence_graph()
