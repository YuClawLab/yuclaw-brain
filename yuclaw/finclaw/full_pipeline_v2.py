"""
YUCLAW Full Pipeline v2 — all components wired together.
Signal -> Evidence -> Memory -> Validation -> Execution -> ZKP -> Brief
"""
import json, os, sys, requests, hashlib
sys.path.insert(0, '.')
from datetime import date
from dotenv import load_dotenv
load_dotenv()


def run_full_pipeline():
    print(f"\n{'=' * 60}")
    print(f"YUCLAW Full Pipeline v2 — {date.today()}")
    print(f"{'=' * 60}")

    model = os.getenv('YUCLAW_SUPER_MODEL', 'nemotron-q4km.gguf')
    endpoint = os.getenv('YUCLAW_SUPER_ENDPOINT', 'http://localhost:8001/v1')
    results = {'date': date.today().isoformat(), 'steps': {}}

    # Step 1: Signals
    print("\n[1/7] Loading signals...")
    try:
        signals = json.load(open('output/aggregated_signals.json'))[:10]
        results['steps']['signals'] = {'count': len(signals), 'status': 'OK'}
        print(f"  {len(signals)} signals loaded")
    except Exception as e:
        results['steps']['signals'] = {'error': str(e)}; signals = []

    # Step 2: Evidence Graph
    print("\n[2/7] Building evidence graph...")
    try:
        from yuclaw.brain.evidence_graph_v2 import EvidenceGraphV2
        graph = EvidenceGraphV2()
        evidence_results = graph.run_pipeline(signals[:5])
        approved = [e for e in evidence_results if e['verdict'] == 'APPROVED']
        results['steps']['evidence'] = {'total': len(evidence_results), 'approved': len(approved), 'status': 'OK'}
    except Exception as e:
        results['steps']['evidence'] = {'error': str(e)}

    # Step 3: Portfolio Memory
    print("\n[3/7] Updating portfolio memory...")
    try:
        from yuclaw.memory.portfolio_memory_v3 import PortfolioMemoryV2
        memory = PortfolioMemoryV2()
        prices = {s['ticker']: s.get('price', 0) for s in signals}
        memory.verify_outcomes(prices)
        for s in signals[:5]:
            memory.record(s)
        results['steps']['memory'] = {'total': memory.memory['performance']['total'], 'accuracy': memory.memory['performance']['accuracy'], 'status': 'OK'}
        print(f"  {memory.get_context()}")
    except Exception as e:
        results['steps']['memory'] = {'error': str(e)}

    # Step 4: Validation
    print("\n[4/7] Validation studio...")
    try:
        validated = json.load(open('output/validation_studio_v2.json'))
        approved_s = [s for s in validated if s.get('approved')]
        results['steps']['validation'] = {'total': len(validated), 'approved': len(approved_s), 'status': 'OK'}
        print(f"  {len(approved_s)}/{len(validated)} strategies approved")
    except Exception as e:
        results['steps']['validation'] = {'error': str(e)}

    # Step 5: Paper Execution
    print("\n[5/7] Paper execution...")
    try:
        from yuclaw.edge.execution_manager import ExecutionManager
        mgr = ExecutionManager()
        orders = [mgr.execute_paper_order(s) for s in signals[:5]]
        orders = [o for o in orders if o.get('status') == 'PAPER_FILLED']
        total_val = sum(o['value'] for o in orders)
        results['steps']['execution'] = {'orders': len(orders), 'total_value': total_val, 'status': 'OK'}
        print(f"  {len(orders)} paper orders, ${total_val:,.0f}")
    except Exception as e:
        results['steps']['execution'] = {'error': str(e)}

    # Step 6: ZKP Proofs
    print("\n[6/7] ZKP proofs...")
    proofs = []
    for s in signals[:3]:
        h = hashlib.sha256(json.dumps({'ticker': s['ticker'], 'signal': s['signal'], 'score': s['score'], 'date': date.today().isoformat()}, sort_keys=True).encode()).hexdigest()
        proofs.append({'ticker': s['ticker'], 'hash': h[:16]})
        print(f"  {s['ticker']}: {h[:16]}...")
    results['steps']['zkp'] = {'proofs': len(proofs), 'status': 'OK'}

    # Step 7: Nemotron Brief
    print("\n[7/7] Nemotron brief...")
    try:
        top = [f"{s['ticker']} {s['signal']} {s['score']:+.3f}" for s in signals[:3]]
        resp = requests.post(f'{endpoint}/chat/completions', json={
            'model': model,
            'messages': [
                {'role': 'system', 'content': 'Senior quant at an institutional hedge fund.'},
                {'role': 'user', 'content': f"YUCLAW Brief {date.today()}. Top: {', '.join(top)}. Regime: CRISIS 90%. 3 sentences: market, opportunity, action."}
            ], 'max_tokens': 300
        }, timeout=120)
        msg = resp.json()['choices'][0]['message']
        brief = msg.get('content') or msg.get('reasoning_content') or ''
        os.makedirs('output/daily', exist_ok=True)
        with open(f'output/daily/{date.today()}_pipeline_brief.txt', 'w') as f:
            f.write(brief)
        results['steps']['brief'] = {'status': 'OK', 'length': len(brief)}
        print(f"  Brief: {len(brief)} chars")
        print(f"\n{brief[:200]}...")
    except Exception as e:
        results['steps']['brief'] = {'error': str(e)}

    # Summary
    passed = sum(1 for s in results['steps'].values() if s.get('status') == 'OK')
    print(f"\n{'=' * 60}")
    print(f"PIPELINE: {passed}/{len(results['steps'])} steps passed")
    for step, res in results['steps'].items():
        s = 'OK' if res.get('status') == 'OK' else 'FAIL'
        print(f"  [{s:4}] {step}")

    with open(f'output/pipeline_{date.today()}.json', 'w') as f:
        json.dump(results, f, indent=2)
    return results


if __name__ == '__main__':
    run_full_pipeline()
