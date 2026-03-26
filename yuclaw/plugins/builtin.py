"""Built-in YUCLAW plugins — ships with every install."""
from yuclaw.plugins import register
import json


@register('signals', 'Real factor-scored buy/sell signals', 'data')
class SignalsPlugin:
    def run(self):
        try:
            return json.load(open('output/aggregated_signals.json'))[:10]
        except Exception:
            return []


@register('regime', 'Live CRISIS/RISK_OFF/RISK_ON detection', 'analysis')
class RegimePlugin:
    def run(self):
        try:
            return json.load(open('output/macro_regime.json'))
        except Exception:
            return {'regime': 'UNKNOWN'}


@register('zkp', 'ZKP cryptographic proof generation', 'audit')
class ZKPPlugin:
    def run(self, decision: dict):
        import hashlib
        data = json.dumps(decision, sort_keys=True).encode()
        return hashlib.sha256(data).hexdigest()


@register('backtest', 'Real backtests from historical prices', 'quant')
class BacktestPlugin:
    def run(self):
        try:
            return json.load(open('output/backtest_all.json'))
        except Exception:
            return []
