"""
YUCLAW CLI — real financial intelligence on any machine.
"""
import argparse, json, os, sys
from datetime import date


def _load(f):
    try:
        return json.load(open(f))
    except Exception:
        return {}


def cmd_start():
    print("\nYUCLAW Financial Intelligence Platform")
    print("Real backtests. ZKP audit. No LLM estimation.\n")

    print("  Running signal scan...")
    os.system('python3 yuclaw/modules/signal_aggregator.py 2>/dev/null')

    print("  Detecting regime...")
    os.system('python3 yuclaw/modules/macro_regime.py 2>/dev/null')

    print("  Running risk engine...")
    os.system('python3 yuclaw/risk/risk_engine.py 2>/dev/null')

    signals = _load('output/aggregated_signals.json')
    if isinstance(signals, list) and signals:
        print(f"\n=== TOP SIGNALS ===")
        for s in signals[:5]:
            print(f"  {s['ticker']:8} {s['signal']:14} {s['score']:+.3f}")

    from yuclaw.core.portfolio_optimizer import PortfolioOptimizer
    opt = PortfolioOptimizer()
    portfolio = opt.optimize(signals if isinstance(signals, list) else [])
    if 'allocations' in portfolio:
        print(f"\n=== PORTFOLIO OPTIMIZATION ===")
        for ticker, pct in list(portfolio['allocations'].items())[:6]:
            print(f"  {ticker:6} {pct:.1%}")

    print(f"\nYUCLAW started. Dashboard: https://yuclawlab.github.io/yuclaw-brain")


def cmd_signals():
    signals = _load('output/aggregated_signals.json')
    if not isinstance(signals, list) or not signals:
        print("No signals yet. Run: yuclaw start")
        return
    print(f"\nYUCLAW Signals — {date.today()}")
    print(f"{'Ticker':8} {'Signal':14} {'Score':8} {'Price':10}")
    print("-" * 45)
    for s in signals[:10]:
        print(f"{s['ticker']:8} {s['signal']:14} {s['score']:+.3f}   ${s.get('price', 0):.2f}")


def cmd_backtest():
    print("Running real backtests...")
    from yuclaw.core.backtest_engine import BacktestEngine
    engine = BacktestEngine()
    results = engine.run_universe([
        'NVDA', 'AMD', 'AAPL', 'MSFT', 'LUNR', 'ASTS', 'MRNA', 'TSLA', 'META', 'GOOGL'
    ])
    print(f"\nYUCLAW Backtests — Top by Calmar")
    print(f"{'Ticker':8} {'Calmar':8} {'Ann.Ret':10} {'Sharpe':8}")
    print("-" * 40)
    for r in results[:5]:
        print(f"{r['ticker']:8} {r['best_calmar']:.3f}    "
              f"{r['best_annual_return']:.1%}      {r['best_sharpe']:.2f}")


def cmd_portfolio():
    print("Optimizing portfolio...")
    signals = _load('output/aggregated_signals.json')
    if not isinstance(signals, list):
        signals = []
    from yuclaw.core.portfolio_optimizer import PortfolioOptimizer
    opt = PortfolioOptimizer()
    result = opt.optimize(signals)
    print(f"\nYUCLAW Portfolio Optimization")
    print(f"Method: {result.get('method')}")
    print(f"\nRecommended Allocations:")
    for ticker, pct in result.get('allocations', {}).items():
        bar = '#' * int(pct * 40)
        print(f"  {ticker:6} {pct:6.1%} {bar}")
    print(f"\n{result.get('note', '')}")


def cmd_regime():
    regime = _load('output/macro_regime.json')
    r = regime.get('regime', 'UNKNOWN')
    c = regime.get('confidence', 0)
    print(f"\nYUCLAW Regime: {r} ({c:.0%})")
    for imp in regime.get('portfolio_implications', []):
        print(f"  -> {imp}")


def cmd_earnings():
    print("Fetching earnings calendar...")
    from yuclaw.core.earnings_calendar import EarningsCalendar
    cal = EarningsCalendar()
    upcoming = cal.get_upcoming_earnings()
    print(f"\nUpcoming Earnings — Next 30 Days")
    if upcoming:
        for e in upcoming[:10]:
            print(f"  {e['ticker']:6} {e['earnings_date']} ({e['days_until']}d) {e['company'][:30]}")
    else:
        print("  No upcoming earnings found")


def cmd_risk():
    risk = _load('output/risk_analysis.json')
    if isinstance(risk, list) and risk:
        r = risk[0]
        print(f"\nYUCLAW Portfolio Risk")
        print(f"  Portfolio: {r.get('portfolio', '')}")
        print(f"  VaR 95%:  {r.get('var_95', 0):.2%}")
        print(f"  Sharpe:   {r.get('sharpe', 0):.2f}")
        print(f"  MaxDD:    {r.get('maxdd', 0):.1%}")
        print(f"  Kelly:    {r.get('kelly', 0):.2%}")
    else:
        print("No risk data yet. Run: yuclaw start")


def cmd_insider():
    print("Scanning insider trading activity...")
    from yuclaw.core.insider_detector import InsiderDetector
    detector = InsiderDetector()
    trades = detector.scan_universe(['NVDA', 'AMD', 'LUNR', 'ASTS', 'MRNA', 'DELL'])
    print(f"\nInsider Activity: {len(trades)} recent filings")
    for t in trades[:5]:
        print(f"  {t['ticker']:6} {t['filed']} {t['entity'][:30]}")


def cmd_track():
    track = _load('output/track_record_v2.json')
    total = track.get('stats', {}).get('total', 0)
    print(f"\nYUCLAW Track Record")
    print(f"  Total signals: {total}")
    print(f"  ZKP: Ethereum Sepolia on-chain")
    for s in track.get('signals', [])[-5:]:
        print(f"  {s['date']} {s['ticker']:6} {s['signal']:12} {s['score']:+.3f}")


def cmd_zkp():
    zkp_dir = 'output/zkp_onchain'
    if not os.path.exists(zkp_dir):
        print("No ZKP proofs yet")
        return
    files = sorted(os.listdir(zkp_dir))
    print(f"\nYUCLAW ZKP Proofs ({len(files)} total)")
    for f in files[-5:]:
        data = _load(f"{zkp_dir}/{f}")
        if isinstance(data, list):
            for d in data:
                print(f"  {d.get('ticker', '?')} block {d.get('block', '?')} — {d.get('explorer', '')}")
        elif isinstance(data, dict):
            print(f"  {data.get('hash', '?')[:32]}...")


def cmd_dashboard():
    import webbrowser
    webbrowser.open('https://yuclawlab.github.io/yuclaw-brain')
    print("Opening YUCLAW live dashboard...")


def main():
    parser = argparse.ArgumentParser(
        description='YUCLAW — Open Financial Intelligence Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  yuclaw start      Full analysis (signals + regime + portfolio)
  yuclaw signals    Real-time buy/sell signals
  yuclaw backtest   Backtest strategies with real prices
  yuclaw portfolio  Kelly-optimized portfolio allocation
  yuclaw regime     Market regime (CRISIS/RISK_OFF/RISK_ON)
  yuclaw earnings   Upcoming earnings calendar
  yuclaw risk       Portfolio risk (VaR/Sharpe/Kelly)
  yuclaw insider    SEC insider trading activity
  yuclaw track      30-day verifiable track record
  yuclaw zkp        ZKP on-chain proofs
  yuclaw dashboard  Open live dashboard
        """
    )

    parser.add_argument('command', nargs='?', default='start',
                        choices=['start', 'signals', 'backtest', 'portfolio',
                                 'regime', 'earnings', 'risk', 'insider',
                                 'track', 'zkp', 'dashboard'])

    args = parser.parse_args()

    commands = {
        'start': cmd_start, 'signals': cmd_signals, 'backtest': cmd_backtest,
        'portfolio': cmd_portfolio, 'regime': cmd_regime, 'earnings': cmd_earnings,
        'risk': cmd_risk, 'insider': cmd_insider, 'track': cmd_track,
        'zkp': cmd_zkp, 'dashboard': cmd_dashboard,
    }

    commands[args.command]()


if __name__ == '__main__':
    main()
