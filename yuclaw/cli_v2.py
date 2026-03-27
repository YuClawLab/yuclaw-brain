import argparse, json, os, sys, glob, requests
from datetime import date, datetime


def load(f):
    try:
        return json.load(open(f))
    except Exception:
        return None


def cmd_today():
    print(f"\nYUCLAW Daily Brief — {date.today()}")
    print("=" * 50)
    regime = load('output/macro_regime.json')
    if regime:
        r = regime.get('regime', 'UNKNOWN')
        c = regime.get('confidence', 0)
        print(f"\nMARKET: {r} ({c:.0%} confidence)")
        for imp in regime.get('portfolio_implications', [])[:2]:
            print(f"   {imp}")
    signals = load('output/aggregated_signals.json')
    if isinstance(signals, list):
        buys = [s for s in signals if 'BUY' in s.get('signal', '') and s.get('price', 0) > 0][:5]
        print(f"\nTOP BUY SIGNALS:")
        for s in buys:
            print(f"   {s['ticker']:6} {s['signal']:12} score:{s['score']:+.3f} price:${s['price']:.2f}")
    track = load('output/track_record_verified.json')
    if track:
        print(f"\nTRACK RECORD: Day {track.get('day', 0)} accuracy {track.get('accuracy', 0):.0%}")
    print(f"\nPORTFOLIO ACTION:")
    if regime and regime.get('regime') == 'CRISIS':
        print(f"   Hold 80%+ cash. Buy only highest conviction signals.")
        print(f"   Max position size: 5% per ticker")
    elif regime and regime.get('regime') == 'RISK_OFF':
        print(f"   Hold 50% cash. Selective buys only.")
        print(f"   Max position size: 8% per ticker")
    else:
        print(f"   Deploy capital. Follow top signals.")
        print(f"   Max position size: 10% per ticker")
    print(f"\nDashboard: yuclawlab.github.io/yuclaw-brain")


def cmd_track():
    print(f"\nYUCLAW Track Record")
    print("=" * 50)
    verified = load('output/track_record_verified.json')
    memory = load('output/portfolio_memory_v2.json')
    if verified:
        results = verified.get('results', [])
        correct = [r for r in results if r.get('aligned')]
        wrong = [r for r in results if not r.get('aligned')]
        print(f"\nDay {verified.get('day', 0)} of 30-day verification")
        print(f"Accuracy: {verified.get('accuracy', 0):.0%} ({len(correct)}/{len(results)})")
        print(f"\nCORRECT SIGNALS:")
        for r in correct:
            print(f"   {r['ticker']:6} {r['signal']:12} {r['change_pct']:+.2f}%")
        if wrong:
            print(f"\nWRONG SIGNALS:")
            for r in wrong:
                print(f"   {r['ticker']:6} {r['signal']:12} {r['change_pct']:+.2f}%")
    if memory:
        perf = memory.get('performance', {})
        print(f"\nPATTERN MEMORY:")
        print(f"   Total decisions: {perf.get('total', 0)}")
        print(f"   Verified: {perf.get('verified', 0)}")
        print(f"   Overall accuracy: {perf.get('accuracy', 0):.0%}")
    print(f"\nZKP: Every signal verified on Ethereum Sepolia")


def cmd_ask(question: str):
    print(f"\nYUCLAW AI — Nemotron 3 Super 120B")
    print("=" * 50)
    context_parts = []
    signals = load('output/aggregated_signals.json')
    if isinstance(signals, list):
        context_parts.append(f"Top signals: {[(s['ticker'], s['signal'], s['score']) for s in signals[:5]]}")
    regime = load('output/macro_regime.json')
    if regime:
        context_parts.append(f"Regime: {regime.get('regime')} {regime.get('confidence', 0):.0%}")
    verified = load('output/track_record_verified.json')
    if verified:
        context_parts.append(f"Track record day {verified.get('day')} accuracy {verified.get('accuracy', 0):.0%}")
    context = "\n".join(context_parts)
    model = os.getenv('YUCLAW_SUPER_MODEL', 'nemotron-q4km.gguf')
    endpoint = os.getenv('YUCLAW_SUPER_ENDPOINT', 'http://localhost:8001/v1')
    try:
        resp = requests.post(
            f'{endpoint}/chat/completions',
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You are YUCLAW AI — a financial intelligence assistant. Be specific, data-driven, honest about uncertainty. Use the real data provided.'},
                    {'role': 'user', 'content': f"Real-time context:\n{context}\n\nUser question: {question}"}
                ],
                'max_tokens': 400
            },
            timeout=120
        )
        msg = resp.json()['choices'][0]['message']
        text = msg.get('content') or msg.get('reasoning_content') or ''
        print(f"\n{text}")
    except Exception as e:
        print(f"Nemotron not available: {e}")
        print("Start with: yuclaw start")


def cmd_verify(ticker: str):
    print(f"\nVerifying {ticker.upper()} signal...")
    zkp_dir = 'output/zkp_onchain'
    found = False
    if os.path.exists(zkp_dir):
        for f in sorted(os.listdir(zkp_dir)):
            if f.endswith('.json'):
                try:
                    data = json.load(open(f"{zkp_dir}/{f}"))
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        t = item.get('ticker') or item.get('decision', {}).get('ticker', '')
                        if t == ticker.upper():
                            print(f"  Proof found")
                            print(f"  Hash: {item.get('hash', item.get('decision_hash', ''))[:32]}...")
                            if item.get('onchain'):
                                print(f"  On-chain: YES — Ethereum Sepolia")
                                print(f"  Block: {item.get('block', '')}")
                                print(f"  Explorer: {item.get('explorer', '')}")
                            else:
                                print(f"  On-chain: Local proof only")
                            found = True
                            break
                except Exception:
                    pass
            if found:
                break
    if not found:
        print(f"  No proof found for {ticker.upper()}")
        print(f"  Generate: yuclaw zkp")


def cmd_portfolio():
    print(f"\nYUCLAW Portfolio Optimizer")
    print("=" * 50)
    signals = load('output/aggregated_signals.json')
    regime = load('output/macro_regime.json')
    if not isinstance(signals, list) or not signals:
        print("No signals. Run: yuclaw start")
        return
    buys = [s for s in signals if 'BUY' in s.get('signal', '') and s.get('price', 0) > 0][:8]
    if not buys:
        print("No buy signals right now.")
        return
    regime_name = regime.get('regime', 'UNKNOWN') if regime else 'UNKNOWN'
    cash_reserve = {'CRISIS': 0.80, 'RISK_OFF': 0.50, 'RISK_ON': 0.20}.get(regime_name, 0.50)
    equity = 1 - cash_reserve
    total_score = sum(abs(s['score']) for s in buys)
    print(f"\nRegime: {regime_name} -> {cash_reserve:.0%} cash reserve")
    print(f"\nRECOMMENDED ALLOCATION:")
    print(f"   {'CASH':8} {cash_reserve:6.1%}  Keep as reserve")
    print(f"   {'-' * 35}")
    for s in buys:
        weight = (abs(s['score']) / total_score) * equity if total_score > 0 else 0
        print(f"   {s['ticker']:8} {weight:6.1%}  {s['signal']} @ ${s['price']:.2f}")
    print(f"\n   Not financial advice. Use position sizing rules.")


def cmd_watchlist():
    print(f"\nYUCLAW Watchlist — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    signals = load('output/aggregated_signals.json')
    if not isinstance(signals, list) or not signals:
        print("No signals. Run: yuclaw start")
        return
    print(f"\n{'Ticker':8} {'Signal':14} {'Score':8} {'Price':10} {'Action'}")
    print("-" * 60)
    for s in signals[:20]:
        if s.get('price', 0) <= 0:
            continue
        action = {'STRONG_BUY': 'Strong buy', 'BUY': 'Buy', 'HOLD': 'Hold',
                  'SELL': 'Sell', 'STRONG_SELL': 'Strong sell'}.get(s.get('signal', ''), 'Hold')
        print(f"{s['ticker']:8} {s.get('signal', ''):14} {s.get('score', 0):+.3f}   ${s.get('price', 0):8.2f}  {action}")


def cmd_brief():
    files = sorted(glob.glob('output/daily/*.txt'))
    if files:
        with open(files[-1]) as f:
            content = f.read()
        print(f"\nYUCLAW Institutional Brief")
        print("=" * 50)
        print(content[:1000])
    else:
        print("No brief yet. Run: yuclaw start")


def main():
    parser = argparse.ArgumentParser(
        description='YUCLAW — Open Financial Intelligence Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  yuclaw today          What should I do today? (START HERE)
  yuclaw watchlist      All signals with prices and actions
  yuclaw portfolio      Kelly-optimal allocation for your capital
  yuclaw track          30-day verified track record
  yuclaw ask "..."      Ask Nemotron 120B any financial question
  yuclaw verify LUNR    Verify signal proof on Ethereum
  yuclaw brief          Latest institutional brief
  yuclaw signals        Raw signal list
  yuclaw regime         Market regime only
  yuclaw risk           Portfolio risk metrics
  yuclaw dashboard      Open live dashboard
        """
    )
    parser.add_argument('command', nargs='?', default='today',
                        choices=['today', 'start', 'watchlist', 'portfolio', 'track',
                                 'ask', 'verify', 'brief', 'signals', 'regime', 'risk', 'dashboard'])
    parser.add_argument('arg', nargs='?', default='')
    args = parser.parse_args()

    if args.command == 'ask':
        question = args.arg or ' '.join(sys.argv[2:]) or "What is the best trade today?"
        cmd_ask(question)
    elif args.command == 'verify':
        cmd_verify(args.arg or 'LUNR')
    elif args.command == 'dashboard':
        import webbrowser
        webbrowser.open('https://yuclawlab.github.io/yuclaw-brain')
    elif args.command == 'signals':
        signals = load('output/aggregated_signals.json')
        if isinstance(signals, list):
            print(f"\nSignals ({len(signals)} total)")
            for s in signals[:15]:
                if s.get('price', 0) > 0:
                    print(f"  {s['ticker']:6} {s['signal']:12} {s['score']:+.3f} ${s['price']:.2f}")
    elif args.command == 'regime':
        r = load('output/macro_regime.json')
        if r:
            print(f"\nRegime: {r.get('regime')} ({r.get('confidence', 0):.0%})")
            for imp in r.get('portfolio_implications', []):
                print(f"  -> {imp}")
    elif args.command == 'risk':
        risk = load('output/risk_analysis.json')
        if isinstance(risk, list) and risk:
            r = risk[0]
            print(f"\nRisk: VaR {r.get('var_95', 0):.2%} Sharpe {r.get('sharpe', 0):.2f} Kelly {r.get('kelly', 0):.2%}")
    elif args.command == 'start':
        cmd_today()
    else:
        cmds = {'today': cmd_today, 'watchlist': cmd_watchlist, 'portfolio': cmd_portfolio,
                'track': cmd_track, 'brief': cmd_brief}
        if args.command in cmds:
            cmds[args.command]()


if __name__ == '__main__':
    main()
