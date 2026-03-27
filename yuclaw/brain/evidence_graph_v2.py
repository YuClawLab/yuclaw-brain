"""
Evidence Graph v2 — fully wired into daily pipeline.
Layer 1: Factor scores (RSI, MACD, Bollinger, Momentum)
Layer 2: Macro regime confirmation
Layer 3: Risk confirmation (VaR, Sharpe)
Layer 4: Nemotron 120B analysis
"""
import json, os, requests
from datetime import date


class EvidenceGraphV2:

    def __init__(self):
        model = os.getenv('YUCLAW_SUPER_MODEL', 'nemotron-q4km.gguf')
        endpoint = os.getenv('YUCLAW_SUPER_ENDPOINT', 'http://localhost:8001/v1')
        self.nemotron_url = f'{endpoint}/chat/completions'
        self.model = model

    def build_evidence(self, signal: dict) -> dict:
        ticker = signal['ticker']
        score = signal['score']

        evidence = {
            'ticker': ticker, 'signal': signal['signal'], 'score': score,
            'date': date.today().isoformat(), 'layers': [],
            'confidence': 0.0, 'verdict': 'PENDING'
        }

        # Layer 1: Factor confirmation
        evidence['layers'].append({
            'layer': 1, 'name': 'Factor Analysis', 'score': score,
            'supports': abs(score) > 0.5,
            'detail': f"Factor composite score: {score:+.3f}"
        })

        # Layer 2: Regime confirmation
        try:
            regime = json.load(open('output/macro_regime.json'))
            regime_name = regime.get('regime', 'UNKNOWN')
            supports = (
                (signal['signal'] in ['STRONG_BUY', 'BUY'] and regime_name == 'RISK_ON') or
                (signal['signal'] in ['STRONG_SELL', 'SELL'] and regime_name in ['CRISIS', 'RISK_OFF']) or
                regime_name == 'RISK_OFF'
            )
            evidence['layers'].append({
                'layer': 2, 'name': 'Macro Regime', 'regime': regime_name,
                'confidence': regime.get('confidence', 0), 'supports': supports,
                'detail': f"Regime {regime_name} ({regime.get('confidence', 0):.0%})"
            })
        except Exception:
            pass

        # Layer 3: Risk confirmation
        try:
            risk = json.load(open('output/risk_analysis.json'))
            if isinstance(risk, list) and risk:
                sharpe = risk[0].get('sharpe', 0)
                evidence['layers'].append({
                    'layer': 3, 'name': 'Risk Analysis',
                    'var_95': risk[0].get('var_95', 0), 'sharpe': sharpe,
                    'supports': sharpe > 1.0,
                    'detail': f"Sharpe {sharpe:.2f} VaR {risk[0].get('var_95', 0):.2%}"
                })
        except Exception:
            pass

        # Layer 4: Nemotron analysis
        try:
            resp = requests.post(
                self.nemotron_url,
                json={
                    'model': self.model,
                    'messages': [{'role': 'user',
                                  'content': f"In one sentence, is {ticker} signal {signal['signal']} score {score:+.3f} supported? Answer SUPPORTS or CONTRADICTS then reason."}],
                    'max_tokens': 150
                }, timeout=120
            )
            msg = resp.json()['choices'][0]['message']
            analysis = msg.get('content') or msg.get('reasoning_content') or ''
            supports = 'SUPPORTS' in analysis.upper() or 'SUPPORT' in analysis.upper()
            evidence['layers'].append({
                'layer': 4, 'name': 'Nemotron Analysis',
                'analysis': analysis[:200], 'supports': supports,
                'model': 'nemotron-3-super-120B'
            })
        except Exception:
            pass

        total = len(evidence['layers'])
        supporting = sum(1 for l in evidence['layers'] if l.get('supports', False))
        evidence['confidence'] = supporting / total if total > 0 else 0
        evidence['verdict'] = 'APPROVED' if evidence['confidence'] >= 0.6 else 'CAUTION'

        return evidence

    def run_pipeline(self, signals: list) -> list:
        print(f"=== Evidence Graph v2 — {len(signals)} signals ===")
        results = []
        os.makedirs('output/evidence_v2', exist_ok=True)

        for s in signals[:10]:
            ev = self.build_evidence(s)
            results.append(ev)
            with open(f"output/evidence_v2/{s['ticker']}_{date.today()}.json", 'w') as f:
                json.dump(ev, f, indent=2)
            print(f"  {s['ticker']:6} {ev['verdict']:8} confidence:{ev['confidence']:.0%} layers:{len(ev['layers'])}")

        return results


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    try:
        signals = json.load(open('output/aggregated_signals.json'))[:10]
    except Exception:
        signals = [{'ticker': 'LUNR', 'signal': 'STRONG_BUY', 'score': 0.933}]

    graph = EvidenceGraphV2()
    results = graph.run_pipeline(signals)
    approved = [r for r in results if r['verdict'] == 'APPROVED']
    print(f"\nApproved: {len(approved)}/{len(results)}")
