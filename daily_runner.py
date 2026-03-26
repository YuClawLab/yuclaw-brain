"""
YUCLAW Daily Runner — runs every day automatically.
Master orchestrator for all daily tasks.
"""
import json, os, sys, time, subprocess
from datetime import date, datetime
sys.path.insert(0, '.')


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def run(cmd):
    try:
        result = subprocess.run(
            ['python3', cmd], capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            log(f"OK {cmd}")
        else:
            log(f"FAIL {cmd}: {result.stderr[:100]}")
        return result.returncode == 0
    except Exception as e:
        log(f"ERR {cmd}: {e}")
        return False


def run_daily():
    log(f"=== YUCLAW Daily Run {date.today()} ===")

    tasks = [
        ('yuclaw/modules/signal_aggregator.py', 'Signal aggregation'),
        ('yuclaw/modules/macro_regime.py', 'Macro regime'),
        ('yuclaw/risk/risk_engine.py', 'Risk engine'),
        ('yuclaw/factors/factor_library.py', 'Factor library'),
        ('yuclaw/memory/track_record_v2.py', 'Track record'),
        ('yuclaw/trust/zkp_vault.py', 'ZKP vault'),
        ('yuclaw/finclaw/institutional_brief.py', 'Institutional brief'),
        ('yuclaw/edge/fix/fix_gateway_real.py', 'FIX gateway'),
    ]

    results = []
    for script, name in tasks:
        if os.path.exists(script):
            success = run(script)
            results.append({'task': name, 'success': success})
            time.sleep(2)

    passed = sum(1 for r in results if r['success'])
    log(f"Daily run: {passed}/{len(results)} tasks completed")

    os.makedirs('output', exist_ok=True)
    with open(f'output/daily_run_{date.today()}.json', 'w') as f:
        json.dump({
            'date': date.today().isoformat(),
            'results': results, 'passed': passed, 'total': len(results)
        }, f, indent=2)

    return passed == len(results)


if __name__ == '__main__':
    run_daily()
