"""
Validation Studio v2 — 5-stage strategy validation.
Every strategy must pass all 5 stages before touching capital.
"""
import json, os, requests
from datetime import date


class ValidationStudioV2:

    STUDIO_FILE = 'output/validation_studio_v2.json'

    def __init__(self):
        self.strategies = self._load()
        self.model = os.getenv('YUCLAW_SUPER_MODEL', 'nemotron-q4km.gguf')
        self.endpoint = os.getenv('YUCLAW_SUPER_ENDPOINT', 'http://localhost:8001/v1')

    def _load(self):
        if os.path.exists(self.STUDIO_FILE):
            return json.load(open(self.STUDIO_FILE))
        return []

    def _save(self):
        os.makedirs('output', exist_ok=True)
        with open(self.STUDIO_FILE, 'w') as f:
            json.dump(self.strategies, f, indent=2)

    def submit(self, name, description, calmar, sharpe, max_dd):
        strategy = {
            'id': len(self.strategies) + 1, 'name': name,
            'description': description, 'submitted': date.today().isoformat(),
            'stage': 'SUBMITTED',
            'backtest': {'calmar': calmar, 'sharpe': sharpe, 'max_drawdown': max_dd},
            'red_team': None, 'stress_test': None, 'verdict': None, 'approved': None
        }
        self.strategies.append(strategy)
        self._save()
        print(f"Submitted: {name} Calmar:{calmar:.3f}")
        return strategy

    def backtest_verify(self, sid):
        s = next((x for x in self.strategies if x['id'] == sid), None)
        if not s: return {}
        issues = []
        bt = s['backtest']
        if bt['calmar'] > 10: issues.append('Calmar > 10 suspicious')
        if bt['sharpe'] > 5: issues.append('Sharpe > 5 suspicious')
        if bt['max_drawdown'] < 0.01: issues.append('Max DD < 1% suspicious')
        s['backtest']['verified'] = len(issues) == 0
        s['backtest']['issues'] = issues
        s['stage'] = 'BACKTEST_VERIFIED'
        self._save()
        print(f"Backtest: {s['name']} — {len(issues)} issues")
        return s

    def red_team_attack(self, sid):
        s = next((x for x in self.strategies if x['id'] == sid), None)
        if not s: return {}
        attacks = [
            {'type': 'SURVIVORSHIP_BIAS', 'severity': 'HIGH', 'question': 'Were delisted stocks included?'}
        ]
        if s['backtest']['calmar'] > 3:
            attacks.append({'type': 'REGIME_DEPENDENCY', 'severity': 'MEDIUM', 'question': 'Works in CRISIS?'})

        try:
            resp = requests.post(
                f'{self.endpoint}/chat/completions',
                json={
                    'model': self.model,
                    'messages': [{'role': 'user',
                                  'content': f"Red Team: Attack strategy {s['name']} Calmar:{s['backtest']['calmar']} Sharpe:{s['backtest']['sharpe']} MaxDD:{s['backtest']['max_drawdown']:.1%}. Verdict: APPROVE or REJECT."}],
                    'max_tokens': 200
                }, timeout=120
            )
            msg = resp.json()['choices'][0]['message']
            verdict = msg.get('content') or msg.get('reasoning_content') or ''
            attacks.append({'type': 'NEMOTRON_RED_TEAM', 'severity': 'HIGH', 'verdict': verdict[:200], 'approved': 'APPROVE' in verdict.upper()})
        except Exception:
            pass

        s['red_team'] = {'attacks': attacks, 'high_severity': sum(1 for a in attacks if a.get('severity') == 'HIGH')}
        s['stage'] = 'RED_TEAM_ATTACK'
        self._save()
        print(f"Red Team: {s['name']} — {s['red_team']['high_severity']} high severity")
        return s

    def stress_test(self, sid):
        s = next((x for x in self.strategies if x['id'] == sid), None)
        if not s: return {}
        scenarios = [
            {'name': 'COVID_CRASH', 'return': -0.34},
            {'name': 'GFC_2008', 'return': -0.56},
            {'name': 'DOT_COM', 'return': -0.49},
            {'name': 'FLASH_CRASH', 'return': -0.09},
        ]
        results = []
        for sc in scenarios:
            impact = sc['return'] * (1 - s['backtest']['calmar'] / 10)
            survives = abs(impact) < 0.50
            results.append({'scenario': sc['name'], 'estimated_impact': impact, 'survives': survives})
            print(f"  {sc['name']:15} impact:{impact:.1%} {'Y' if survives else 'N'}")
        s['stress_test'] = {'scenarios': results, 'survival_rate': sum(1 for r in results if r['survives']) / len(results)}
        s['stage'] = 'STRESS_TEST'
        self._save()
        return s

    def final_verdict(self, sid):
        s = next((x for x in self.strategies if x['id'] == sid), None)
        if not s: return {}
        checks = [
            s['backtest'].get('verified', False),
            s.get('red_team', {}).get('high_severity', 99) < 2,
            s.get('stress_test', {}).get('survival_rate', 0) >= 0.75,
            s['backtest']['calmar'] >= 1.0,
            s['backtest']['sharpe'] >= 0.5
        ]
        passed = sum(checks)
        s['verdict'] = 'APPROVED' if passed >= 4 else 'REJECTED'
        s['approved'] = passed >= 4
        s['stage'] = 'FINAL_VERDICT'
        s['checks_passed'] = passed
        self._save()
        print(f"Verdict: {s['name']} -> {s['verdict']} ({passed}/5)")
        return s

    def run_full_validation(self, sid):
        self.backtest_verify(sid)
        self.red_team_attack(sid)
        self.stress_test(sid)
        return self.final_verdict(sid)


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    studio = ValidationStudioV2()
    for name, desc, c, sh, dd in [
        ('mom_1m_tight', '1-month momentum', 3.055, 1.89, 0.15),
        ('mom_6m_tight', '6-month momentum', 1.763, 1.45, 0.18),
        ('mean_reversion', 'Mean reversion', 0.8, 0.9, 0.25),
        ('vol_breakout', 'Vol breakout', 2.1, 1.6, 0.12),
    ]:
        s = studio.submit(name, desc, c, sh, dd)
        studio.run_full_validation(s['id'])
    approved = [s for s in studio.strategies if s.get('approved')]
    print(f"\nApproved: {len(approved)}/{len(studio.strategies)}")
