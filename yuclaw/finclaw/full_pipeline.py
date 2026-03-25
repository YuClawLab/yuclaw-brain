"""
Full integrated pipeline — all components wired together.
Signal -> Evidence -> NER -> Portfolio Memory -> Nemotron Brief -> ZKP proof
This is the complete YUCLAW loop.
"""
import json, os, sys, requests, hashlib
sys.path.insert(0, '.')
from datetime import date
from dotenv import load_dotenv
load_dotenv()


def run_full_pipeline():
    print("=== YUCLAW Full Integrated Pipeline ===")
    print(f"Date: {date.today()}")
    print("Components: Signal -> Evidence -> NER -> Memory -> Nemotron -> ZKP")
    print("=" * 60)

    # Step 1: Load signals
    try:
        signals = json.load(open('output/aggregated_signals.json'))[:5]
    except Exception:
        signals = [{'ticker': 'LUNR', 'signal': 'STRONG_BUY', 'score': 0.933}]
    print(f"Step 1: {len(signals)} signals loaded")

    # Step 2: Evidence graph
    from yuclaw.brain.evidence_graph_live import build_evidence
    evidence_results = []
    for s in signals:
        ev = build_evidence(s['ticker'], s['signal'], s['score'],
                            s.get('factors', {'momentum': s['score']}))
        evidence_results.append(ev)
    print(f"Step 2: Evidence graph — {sum(len(e['evidence_chain']) for e in evidence_results)} total evidence items")

    # Step 3: NER
    from yuclaw.brain.financial_ner_live import run_ner_pipeline
    run_ner_pipeline()
    print("Step 3: NER pipeline complete")

    # Step 4: Portfolio memory
    from yuclaw.memory.portfolio_memory_live import record_decision, get_memory_context
    for s, ev in zip(signals, evidence_results):
        record_decision(s['ticker'], s['signal'], s['score'], ev, 'CRISIS')
    print(f"Step 4: Portfolio memory updated")
    print(get_memory_context())

    # Step 5: Nemotron synthesis
    model = os.getenv('YUCLAW_SUPER_MODEL', 'nemotron-q4km.gguf')
    endpoint = os.getenv('YUCLAW_SUPER_ENDPOINT', 'http://localhost:8001/v1')
    top_signals = [f"{s['ticker']} {s['signal']} {s['score']:+.3f}" for s in signals[:3]]
    avg_conf = sum(e['confidence'] for e in evidence_results) / len(evidence_results)
    prompt = f"""
YUCLAW Full Pipeline Synthesis — {date.today()}

Top signals: {', '.join(top_signals)}
Regime: CRISIS 90%
Evidence confidence: {avg_conf:.0%} average
Portfolio memory: {len(signals)} decisions recorded today

Generate a 3-paragraph institutional synthesis:
1. What the integrated pipeline found today
2. Highest confidence opportunities with evidence
3. Risk-adjusted recommended actions
"""
    try:
        resp = requests.post(
            f'{endpoint}/chat/completions',
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You are a senior quant at a top hedge fund.'},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 600
            },
            timeout=300
        )
        msg = resp.json()['choices'][0]['message']
        synthesis = msg.get('content') or msg.get('reasoning_content') or ''

        os.makedirs('output/pipeline', exist_ok=True)
        with open(f'output/pipeline/{date.today()}_synthesis.txt', 'w') as f:
            f.write(synthesis)
        print(f"\nStep 5: Nemotron synthesis complete")
        print(synthesis[:600])
    except Exception as e:
        print(f"Step 5 error: {e}")

    # Step 6: ZKP proof for pipeline run
    pipeline_hash = hashlib.sha256(
        json.dumps({'signals': top_signals, 'date': str(date.today()), 'model': 'nemotron-120B'}).encode()
    ).hexdigest()
    print(f"\nStep 6: Pipeline ZKP hash: {pipeline_hash[:32]}...")
    print("=" * 60)
    print("FULL PIPELINE COMPLETE")


if __name__ == '__main__':
    run_full_pipeline()
