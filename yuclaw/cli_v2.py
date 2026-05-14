import argparse, json, os, sys, glob, requests
from datetime import date, datetime, timezone


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
        print(f"\nMARKET: {r} ({c:.0%})")
        for imp in regime.get('portfolio_implications', [])[:2]:
            print(f"   {imp}")
    signals = load('output/aggregated_signals.json')
    if isinstance(signals, list):
        buys = [s for s in signals if 'BUY' in s.get('signal', '') and s.get('price', 0) > 0][:5]
        print(f"\nTOP BUY SIGNALS:")
        for s in buys:
            v = 'V' if s.get('verified') else '?'
            print(f"   {s['ticker']:6} {s['signal']:12} {s['score']:+.3f} ${s['price']:.2f} [{v}]")
    sector = load('output/sector_rotation.json')
    if sector:
        inflows = sector.get('top_inflows', [])
        if inflows:
            print(f"\nSECTOR INFLOWS: {', '.join([r['sector'] for r in inflows[:3]])}")
    earnings = load('output/earnings_this_week.json')
    if earnings:
        print(f"\nEARNINGS THIS WEEK: {', '.join(list(earnings.keys())[:5])}")
    track = load('output/track_record_verified.json')
    if track:
        print(f"\nBACKTEST RESULTS: Day {track.get('day', 0)} accuracy {track.get('accuracy', 0):.0%}")
    print(f"\nPORTFOLIO ACTION:")
    if regime and regime.get('regime') == 'CRISIS':
        print(f"   Hold 80%+ cash. Max position 5%.")
    elif regime and regime.get('regime') == 'RISK_OFF':
        print(f"   Hold 50% cash. Max position 8%.")
    else:
        print(f"   Deploy capital. Max position 10%.")
    print(f"\nDashboard: yuclawlab.github.io/yuclaw-brain")


def cmd_sector():
    print(f"\nSector Rotation")
    print("=" * 50)
    data = load('output/sector_rotation.json')
    if not data:
        print("No data. Run sector rotation first.")
        return
    print(f"\n{'ETF':5} {'Sector':22} {'Change':8} Signal")
    print("-" * 50)
    for r in data.get('rotation', []):
        icon = 'IN ' if r['signal'] == 'INFLOW' else 'OUT' if r['signal'] == 'OUTFLOW' else '---'
        print(f"[{icon}] {r['etf']:5} {r['sector']:22} {r['change_pct']:+.2f}%  {r['signal']}")


def cmd_news():
    print(f"\nNews Sentiment — Nemotron 120B")
    print("=" * 50)
    data = load('output/news_sentiment.json')
    if not data:
        print("No data.")
        return
    for r in (data if isinstance(data, list) else [])[:10]:
        s = r.get('sentiment', 'NEUTRAL')
        icon = 'BULL' if s == 'BULLISH' else 'BEAR' if s == 'BEARISH' else 'NEUT'
        print(f"[{icon}] {r['ticker']:6} {s:8} {r.get('score', 0):+.2f} — {r.get('reason', '')[:60]}")


def cmd_earnings():
    print(f"\nEarnings This Week — Finnhub")
    print("=" * 50)
    data = load('output/earnings_this_week.json')
    if not data:
        print("No earnings this week for tracked tickers.")
        return
    for ticker, info in data.items():
        print(f"  {ticker:6} {info['earnings_date']} in {info['days_until']}d — {info['action']}")


def cmd_track():
    print(f"\nYUCLAW Backtest Results")
    print("=" * 50)
    verified = load('output/track_record_verified.json')
    memory = load('output/portfolio_memory_v2.json')
    if verified:
        results = verified.get('results', [])
        correct = [r for r in results if r.get('aligned')]
        wrong = [r for r in results if not r.get('aligned')]
        print(f"\nDay {verified.get('day', 0)} of 30")
        print(f"Accuracy: {verified.get('accuracy', 0):.0%} ({len(correct)}/{len(results)})")
        if correct:
            print(f"\nCORRECT:")
            for r in correct:
                print(f"   {r['ticker']:6} {r['signal']:12} {r['change_pct']:+.2f}%")
        if wrong:
            print(f"\nWRONG:")
            for r in wrong:
                print(f"   {r['ticker']:6} {r['signal']:12} {r['change_pct']:+.2f}%")
    if memory:
        perf = memory.get('performance', {})
        print(f"\nTotal: {perf.get('total', 0)} decisions, {perf.get('accuracy', 0):.0%} accuracy")
    print(f"\nZKP: Every signal on Ethereum Sepolia")


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
    sector = load('output/sector_rotation.json')
    if sector:
        context_parts.append(f"Sector inflows: {[r['sector'] for r in sector.get('top_inflows', [])]}")
    news = load('output/news_sentiment.json')
    if isinstance(news, list):
        bullish = [r['ticker'] for r in news if r.get('sentiment') == 'BULLISH'][:3]
        if bullish:
            context_parts.append(f"Bullish news: {bullish}")
    earnings = load('output/earnings_this_week.json')
    if earnings:
        context_parts.append(f"Earnings this week: {list(earnings.keys())}")
    context = "\n".join(context_parts)
    model = os.getenv('YUCLAW_SUPER_MODEL', 'nemotron-3-super-local')
    endpoint = os.getenv('YUCLAW_SUPER_ENDPOINT', 'http://localhost:11434/v1')
    try:
        resp = requests.post(
            f'{endpoint}/chat/completions',
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': 'You are YUCLAW AI. Be specific, data-driven, honest.'},
                    {'role': 'user', 'content': f"Context:\n{context}\n\nQuestion: {question}"}
                ],
                'max_tokens': 400
            },
            timeout=120
        )
        msg = resp.json()['choices'][0]['message']
        text = msg.get('content') or msg.get('reasoning_content') or ''
        print(f"\n{text}")
    except Exception as e:
        print(f"Nemotron error: {e}")


def cmd_verify(ticker: str):
    print(f"\nVerifying {ticker.upper()}...")
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
                                print(f"  On-chain: Ethereum Sepolia")
                                print(f"  Block: {item.get('block', '')}")
                                print(f"  Explorer: {item.get('explorer', '')}")
                            found = True
                            break
                except Exception:
                    pass
            if found:
                break
    if not found:
        print(f"  No proof for {ticker.upper()}")


def cmd_portfolio():
    print(f"\nPortfolio Optimizer")
    print("=" * 50)
    signals = load('output/aggregated_signals.json')
    regime = load('output/macro_regime.json')
    earnings = load('output/earnings_this_week.json') or {}
    if not isinstance(signals, list) or not signals:
        print("No signals.")
        return
    buys = [s for s in signals if 'BUY' in s.get('signal', '') and s.get('price', 0) > 0][:8]
    if not buys:
        print("No buy signals.")
        return
    regime_name = regime.get('regime', 'UNKNOWN') if regime else 'UNKNOWN'
    cash_reserve = {'CRISIS': 0.80, 'RISK_OFF': 0.50, 'RISK_ON': 0.20}.get(regime_name, 0.50)
    equity = 1 - cash_reserve
    total_score = sum(abs(s['score']) for s in buys)
    print(f"\nRegime: {regime_name} -> {cash_reserve:.0%} cash")
    print(f"\n   {'CASH':8} {cash_reserve:6.1%}  Reserve")
    print(f"   {'-' * 40}")
    for s in buys:
        weight = (abs(s['score']) / total_score) * equity if total_score > 0 else 0
        warn = ' EARNINGS!' if s['ticker'] in earnings else ''
        print(f"   {s['ticker']:8} {weight:6.1%}  ${s['price']:.2f}{warn}")
    print(f"\n   Not financial advice.")


def cmd_watchlist():
    print(f"\nWatchlist — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    signals = load('output/aggregated_signals.json')
    if not isinstance(signals, list) or not signals:
        print("No signals.")
        return
    print(f"\n{'Ticker':8} {'Signal':14} {'Score':8} {'Price':10} {'Verified'}")
    print("-" * 55)
    for s in signals[:20]:
        if s.get('price', 0) <= 0:
            continue
        v = 'V' if s.get('verified') else '?'
        print(f"{s['ticker']:8} {s.get('signal', ''):14} {s.get('score', 0):+.3f}   ${s.get('price', 0):8.2f}  [{v}]")


def _paper_dir():
    d = os.path.expanduser('~/.yuclaw')
    os.makedirs(d, exist_ok=True)
    return d


def _paper_consent_check() -> bool:
    """First-run consent for yuclaw paper. Saves accept to ~/.yuclaw/paper_consent.json."""
    path = os.path.join(_paper_dir(), 'paper_consent.json')
    if os.path.exists(path):
        try:
            if json.load(open(path)).get('accepted'):
                return True
        except Exception:
            pass
    print()
    print("YUCLAW will place real paper orders against your Alpaca account.")
    print("Endpoint: paper-api.alpaca.markets (PAPER, not live).")
    try:
        ans = input("Continue? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ''
    if ans != 'y':
        print("Declined. Run again when ready.")
        return False
    with open(path, 'w') as f:
        json.dump({
            'accepted': True,
            'accepted_at': datetime.now().isoformat(),
            'endpoint': 'paper-api.alpaca.markets',
        }, f, indent=2)
    print(f"Consent saved to {path}. This prompt will not appear again.")
    return True


def _paper_audit(record: dict):
    """Append-only JSONL audit log."""
    record.setdefault('ts', datetime.now(timezone.utc).isoformat())
    with open(os.path.join(_paper_dir(), 'orders.jsonl'), 'a') as f:
        f.write(json.dumps(record) + '\n')


def _fmt_et(iso_str: str) -> str:
    if not iso_str:
        return 'unknown'
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime('%H:%M ET (%a %b %d)')
    except Exception:
        return iso_str[:16].replace('T', ' ')


def _paper_show_status(gateway):
    acct = gateway.get_account()
    clock = gateway.get_clock()
    positions = gateway.get_positions()
    eq, base = acct['equity'], acct['last_equity']
    pnl = eq - base
    pnl_pct = (pnl / base * 100) if base > 0 else 0
    print(f"\nYUCLAW Paper — Alpaca")
    print("=" * 50)
    print(f"  Equity:      ${eq:>12,.2f}")
    print(f"  Last close:  ${base:>12,.2f}")
    print(f"  Today P&L:   ${pnl:>+12,.2f}  ({pnl_pct:+.2f}%)")
    print(f"  Cash:        ${acct['cash']:>12,.2f}")
    print(f"  Buying pwr:  ${acct['buying_power']:>12,.2f}")
    print()
    if clock['is_open']:
        print(f"  Market:      OPEN  (next close: {_fmt_et(clock['next_close'])})")
    else:
        print(f"  Market:      CLOSED (next open: {_fmt_et(clock['next_open'])})")
    print()
    if positions:
        print(f"  Positions ({len(positions)}):")
        for p in positions:
            print(f"    {p['ticker']:6}  qty={p['qty']:>5}  entry=${p['avg_entry']:7.2f}  "
                  f"now=${p['current_price']:7.2f}  P&L ${p['unrealized_pl']:+,.2f}")
    else:
        print("  Positions:   none")


def _paper_handle_order(gateway, action: str, ticker: str, qty: int, force: bool):
    """Order pipeline: market hours -> risk gate -> size cap -> submit. Audit at every stop."""
    from yuclaw.edge.risk_gates import RiskGate

    ticker = ticker.upper()
    action = action.upper()
    audit = {
        'ts':            datetime.now(timezone.utc).isoformat(),
        'action':        action,
        'ticker':        ticker,
        'qty':           qty,
        'force':         bool(force),
        'status':        None,
        'drawdown_pct':  None,
        'fill_price':    None,
        'order_id':      None,
    }

    # 1. Market hours
    clock = gateway.get_clock()
    if not clock['is_open']:
        next_open = _fmt_et(clock['next_open'])
        print(f"  Market closed. Opens {next_open}.")
        audit['status'] = 'REJECTED_MARKET_CLOSED'
        _paper_audit(audit)
        return

    # 2. Risk gate (drawdown halt / liquidate)
    acct = gateway.get_account()
    gate = RiskGate().check(acct['equity'], acct['last_equity'])
    audit['drawdown_pct'] = gate['drawdown_pct']
    if gate['action'] == 'HALT':
        print(f"  HALTED: {gate['reason']}.")
        print(f"  No new orders accepted until drawdown recovers.")
        audit['status'] = 'REJECTED_HALT'
        _paper_audit(audit)
        return
    if gate['action'] == 'LIQUIDATE':
        print(f"  EMERGENCY: {gate['reason']}.")
        print(f"  Refusing new order. To exit positions manually, run:")
        print(f"    yuclaw paper liquidate")
        audit['status'] = 'REJECTED_LIQUIDATE'
        _paper_audit(audit)
        return

    # 3. Size cap ($10k notional)
    try:
        price = gateway.get_latest_price(ticker)
    except Exception as e:
        print(f"  Could not fetch price for {ticker}: {e}")
        audit['status'] = 'REJECTED_PRICE_LOOKUP'
        audit['error'] = str(e)[:200]
        _paper_audit(audit)
        return
    notional = price * qty
    audit['estimated_notional'] = round(notional, 2)
    if notional > 10000 and not force:
        print(f"  Order exceeds $10k cap (~${notional:,.2f}). Use --force to override.")
        audit['status'] = 'REJECTED_SIZE_CAP'
        _paper_audit(audit)
        return

    # 4. Submit
    try:
        order = gateway.submit_market_order(ticker, action.lower(), qty)
        print(f"  {action} {qty} {ticker} submitted "
              f"(id: {(order.get('id') or '')[:8]}..., status: {order.get('status')})")
        audit['status']   = 'SUBMITTED'
        audit['order_id'] = order.get('id')
        _paper_audit(audit)
    except Exception as e:
        print(f"  FAILED: {e}")
        audit['status'] = 'FAILED'
        audit['error']  = str(e)[:200]
        _paper_audit(audit)


def cmd_paper(extra_argv):
    """Live Alpaca paper trading. Separate code path from campus simulation."""
    if not _paper_consent_check():
        return
    try:
        from yuclaw.edge.alpaca_gateway import AlpacaGateway
        gateway = AlpacaGateway()
    except RuntimeError as e:
        print(f"  Alpaca gateway init failed: {e}")
        return

    force = '--force' in extra_argv
    args = [a for a in extra_argv if a != '--force']

    if not args:
        _paper_show_status(gateway)
        return

    sub = args[0].lower()
    if sub == 'orders':
        orders = gateway.get_orders(status='all', limit=10)
        print(f"\nRecent Alpaca orders ({len(orders)}):")
        for o in orders:
            print(f"  {o['submitted_at'][:19]}  {o['side']:4}  {o['qty']:>4} {o['ticker']:6}  "
                  f"{o['status']:10}  fill ${o['filled_avg_price']:.2f}")
        return
    if sub == 'liquidate':
        try:
            ans = input("Liquidate ALL open positions? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = ''
        if ans != 'y':
            print("  Aborted.")
            return
        closes = gateway.liquidate_all()
        print(f"  {len(closes)} close orders submitted.")
        return
    if sub.upper() in ('BUY', 'SELL'):
        if len(args) != 3:
            print("Usage: yuclaw paper BUY|SELL TICKER QTY [--force]")
            return
        try:
            qty = int(args[2])
        except ValueError:
            print(f"  Invalid qty: {args[2]!r}")
            return
        if qty <= 0:
            print("  qty must be positive")
            return
        _paper_handle_order(gateway, sub.upper(), args[1], qty, force)
        return

    print(f"Unknown paper subcommand: {sub!r}")
    print("Usage: yuclaw paper [BUY|SELL TICKER QTY [--force] | orders | liquidate]")


def cmd_brief():
    files = sorted(glob.glob('output/daily/*.txt'))
    if files:
        with open(files[-1]) as f:
            content = f.read()
        print(f"\nInstitutional Brief")
        print("=" * 50)
        print(content[:1000])
    else:
        print("No brief yet.")


def main():
    parser = argparse.ArgumentParser(
        description='YUCLAW — Open Financial Intelligence Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  yuclaw today          What to do RIGHT NOW
  yuclaw sector         Sector rotation — where money moves
  yuclaw news           News sentiment via Nemotron 120B
  yuclaw earnings       Earnings this week — Finnhub
  yuclaw watchlist      All signals with prices
  yuclaw portfolio      Kelly allocation + earnings warnings
  yuclaw track          30-day backtest verification
  yuclaw ask "..."      Ask Nemotron 120B
  yuclaw verify LUNR    Ethereum proof
  yuclaw brief          Institutional brief
        """
    )
    parser.add_argument('command', nargs='?', default='today',
                        choices=['today', 'sector', 'news', 'earnings', 'watchlist',
                                 'portfolio', 'track', 'ask', 'verify', 'brief',
                                 'signals', 'regime', 'risk', 'dashboard', 'start',
                                 'learn', 'trade', 'l2', 'audio', 'chain', 'swarm',
                                 'paper'])
    parser.add_argument('arg', nargs='*', default=[])
    # parse_known_args (not parse_args) so subcommand-specific flags like
    # `yuclaw paper BUY NVDA 10 --force` reach cmd_paper via sys.argv[2:]
    # instead of being rejected at the top-level argparse layer.
    args, _unknown = parser.parse_known_args()
    args.arg = ' '.join(args.arg) if args.arg else ''

    cmds = {
        'today': cmd_today, 'start': cmd_today, 'sector': cmd_sector,
        'news': cmd_news, 'earnings': cmd_earnings, 'watchlist': cmd_watchlist,
        'portfolio': cmd_portfolio, 'track': cmd_track, 'brief': cmd_brief,
    }

    if args.command == 'l2':
        from yuclaw.orderbook.microstructure import OrderBookAnalyzer
        analyzer = OrderBookAnalyzer()
        if len(sys.argv) > 2:
            print(analyzer.show(sys.argv[2].upper()))
        else:
            try:
                signals = json.load(open('output/aggregated_signals.json'))
                tickers = [s['ticker'] for s in signals[:10] if s.get('price', 0) > 0]
            except:
                tickers = ['LUNR', 'ASTS', 'DELL', 'NVDA', 'MRNA']
            analyzer.scan_universe(tickers)
    elif args.command == 'audio':
        from yuclaw.audio.audio_intel import analyze_audio
        extra = sys.argv[2:]
        if not extra:
            print("Usage: yuclaw audio <file_or_url> [context]")
            print("  yuclaw audio /tmp/fomc.mp3 'FOMC meeting'")
        else:
            source = extra[0]
            context = ' '.join(extra[1:]) if len(extra) > 1 else 'financial speech'
            analyze_audio(source, context)
    elif args.command == 'chain':
        from yuclaw.graph.causal_graph import CausalGraph
        event = args.arg.upper() if args.arg else 'TSMC'
        graph = CausalGraph()
        print(graph.explain_chain(event))
        trades = graph.get_second_order_trades(event)
        if trades:
            print(f"\n  Second-order trade ideas:")
            for t in trades[:5]:
                print(f"    {t['ticker']:6} ({t['order']}) -- {t['chain']}")
    elif args.command == 'swarm':
        from yuclaw.swarm.debate import run_swarm
        run_swarm()
    elif args.command == 'learn':
        from yuclaw.campus.learn import explain, list_concepts
        if args.arg:
            print(explain(args.arg))
        else:
            list_concepts()
    elif args.command == 'trade':
        from yuclaw.campus.paper_trading import PaperTrader
        trader = PaperTrader(os.environ.get('USER', 'Student'))
        extra = sys.argv[2:]
        if not extra:
            print(trader.show())
        elif len(extra) == 3:
            action, ticker, shares = extra[0].upper(), extra[1].upper(), int(extra[2])
            if action == 'BUY':
                res = trader.buy(ticker, shares)
                if 'error' in res:
                    print(f"  Error: {res['error']}")
                else:
                    print(f"  Bought {shares} {ticker} @ ${res['price']:,.2f}")
            elif action == 'SELL':
                res = trader.sell(ticker, shares)
                if 'error' in res:
                    print(f"  Error: {res['error']}")
                else:
                    print(f"  Sold {shares} {ticker}. PnL: ${res['pnl']:+,.2f}")
        else:
            print("Usage: yuclaw trade [BUY/SELL] [TICKER] [SHARES]")
    elif args.command == 'paper':
        cmd_paper(sys.argv[2:])
    elif args.command == 'ask':
        question = args.arg or ' '.join(sys.argv[2:]) or "What is best trade today?"
        cmd_ask(question)
    elif args.command == 'verify':
        cmd_verify(args.arg or 'LUNR')
    elif args.command == 'dashboard':
        import webbrowser
        webbrowser.open('https://yuclawlab.github.io/yuclaw-brain')
    elif args.command == 'signals':
        signals = load('output/aggregated_signals.json')
        if isinstance(signals, list):
            for s in signals[:15]:
                if s.get('price', 0) > 0:
                    print(f"  {s['ticker']:6} {s['signal']:12} {s['score']:+.3f} ${s['price']:.2f}")
    elif args.command == 'regime':
        r = load('output/macro_regime.json')
        if r:
            print(f"\nRegime: {r.get('regime')} ({r.get('confidence', 0):.0%})")
    elif args.command == 'risk':
        risk = load('output/risk_analysis.json')
        if isinstance(risk, list) and risk:
            r = risk[0]
            print(f"\nVaR:{r.get('var_95', 0):.2%} Sharpe:{r.get('sharpe', 0):.2f} Kelly:{r.get('kelly', 0):.2%}")
    elif args.command in cmds:
        cmds[args.command]()


if __name__ == '__main__':
    main()
