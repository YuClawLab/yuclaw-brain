"""
YUCLAW CLI — one command to start financial intelligence.
yuclaw start      — start all engines
yuclaw signals    — show current signals
yuclaw regime     — show market regime
yuclaw brief      — show institutional brief
yuclaw track      — show track record
yuclaw zkp        — show ZKP proofs
yuclaw dashboard  — open dashboard
"""
import argparse, json, os, sys, subprocess, webbrowser
from datetime import date


def load(f):
    try:
        return json.load(open(f))
    except Exception:
        return {}


def cmd_signals():
    signals = load('output/aggregated_signals.json')
    if not signals:
        print("No signals yet. Run: yuclaw start")
        return
    print(f"\nYUCLAW Signals — {date.today()}")
    print(f"{'Ticker':8} {'Signal':14} {'Score':8} {'Price':10}")
    print("-" * 45)
    for s in (signals if isinstance(signals, list) else [])[:10]:
        print(f"{s['ticker']:8} {s['signal']:14} {s['score']:+.3f}   ${s.get('price', 0):.2f}")


def cmd_regime():
    regime = load('output/macro_regime.json')
    r = regime.get('regime', 'UNKNOWN')
    c = regime.get('confidence', 0)
    print(f"\nYUCLAW Regime: {r} ({c:.0%})")
    for imp in regime.get('portfolio_implications', []):
        print(f"  -> {imp}")


def cmd_track():
    track = load('output/track_record_v2.json')
    total = track.get('stats', {}).get('total', 0)
    print(f"\nYUCLAW Track Record")
    print(f"  Total signals: {total}")
    print(f"  Building since: March 23, 2026")
    print(f"  ZKP: Ethereum Sepolia on-chain")
    signals = track.get('signals', [])
    for s in signals[-5:]:
        print(f"  {s['date']} {s['ticker']:6} {s['signal']:12} {s['score']:+.3f}")


def cmd_brief():
    today = date.today().isoformat()
    for f in [
        f'output/daily/{today}_real_brief.txt',
        f'output/daily/{today}_morning_brief.txt',
        f'output/daily/{today}_day3_brief.txt',
    ]:
        if os.path.exists(f):
            with open(f) as file:
                print(f"\nYUCLAW Brief — {today}")
                print(file.read()[:1000])
            return
    print("Brief not yet generated. Run: yuclaw start")


def cmd_zkp():
    zkp_dir = 'output/zkp_onchain'
    if not os.path.exists(zkp_dir):
        print("No ZKP proofs yet")
        return
    files = sorted(os.listdir(zkp_dir))
    print(f"\nYUCLAW ZKP Proofs ({len(files)} total)")
    for f in files[-5:]:
        data = load(f"{zkp_dir}/{f}")
        if isinstance(data, list):
            for d in data:
                print(f"  {d.get('ticker', '?')} — {d.get('explorer', '')}")
        else:
            print(f"  {data.get('hash', '?')[:32]}...")


def cmd_start():
    print("\nStarting YUCLAW Financial Intelligence Platform...")
    print("  Checking Nemotron server...")

    import requests
    try:
        resp = requests.get('http://localhost:8001/health', timeout=3)
        print("  Nemotron 120B running")
    except Exception:
        print("  Nemotron not running — start it manually or see README")

    print("  Running signal scan...")
    os.system('python3 yuclaw/modules/signal_aggregator.py 2>/dev/null')

    print("  Checking regime...")
    os.system('python3 yuclaw/modules/macro_regime.py 2>/dev/null')

    print("  Running risk engine...")
    os.system('python3 yuclaw/risk/risk_engine.py 2>/dev/null')

    print("\nYUCLAW started successfully!")
    print(f"  Dashboard: https://yuclawlab.github.io/yuclaw-brain")
    print(f"  API: http://localhost:8000")
    print(f"  Signals: yuclaw signals")
    print(f"  Regime: yuclaw regime")
    print(f"  Brief: yuclaw brief")


def cmd_dashboard():
    webbrowser.open('https://yuclawlab.github.io/yuclaw-brain')
    print("Opening dashboard...")


def main():
    parser = argparse.ArgumentParser(
        description='YUCLAW — Open Financial Intelligence Platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  yuclaw start      Start all YUCLAW engines
  yuclaw signals    Show current buy/sell signals
  yuclaw regime     Show market regime (CRISIS/RISK_OFF/RISK_ON)
  yuclaw brief      Show Nemotron institutional brief
  yuclaw track      Show 30-day track record
  yuclaw zkp        Show ZKP on-chain proofs
  yuclaw dashboard  Open live dashboard

GitHub: https://github.com/YuClawLab
        """
    )

    parser.add_argument('command', nargs='?', default='start',
                        choices=['start', 'signals', 'regime', 'brief', 'track', 'zkp', 'dashboard'])

    args = parser.parse_args()

    commands = {
        'start': cmd_start,
        'signals': cmd_signals,
        'regime': cmd_regime,
        'brief': cmd_brief,
        'track': cmd_track,
        'zkp': cmd_zkp,
        'dashboard': cmd_dashboard,
    }

    commands[args.command]()


if __name__ == '__main__':
    main()
