"""
FinSkills Marketplace — community financial intelligence.
Anyone submits a strategy. Community validates it. Best earn YCT tokens.
"""
import json, os, hashlib, time
from datetime import date


class FinSkillsMarketplace:

    MARKETPLACE_FILE = 'output/marketplace/finskills.json'
    CATEGORIES = ['momentum', 'mean_reversion', 'arbitrage', 'macro', 'earnings',
                  'sentiment', 'technical', 'fundamental', 'alternative_data', 'ml_model']

    def __init__(self):
        os.makedirs('output/marketplace', exist_ok=True)
        self.skills = self._load()

    def _load(self):
        if os.path.exists(self.MARKETPLACE_FILE):
            return json.load(open(self.MARKETPLACE_FILE))
        return []

    def _save(self):
        with open(self.MARKETPLACE_FILE, 'w') as f:
            json.dump(self.skills, f, indent=2)

    def submit_skill(self, name, description, category, author, calmar, sharpe):
        skill_id = hashlib.sha256(f"{name}{author}{time.time()}".encode()).hexdigest()[:16]
        skill = {
            'id': skill_id, 'name': name, 'description': description,
            'category': category, 'author': author,
            'submitted': date.today().isoformat(),
            'performance': {'calmar': calmar, 'sharpe': sharpe},
            'votes': 0, 'installs': 0, 'yct_earned': 0,
            'status': 'PENDING_REVIEW', 'validated': False,
            'install_command': f"yuclaw skills install {name}"
        }
        self.skills.append(skill)
        self._save()
        print(f"Submitted: {name} by {author}")
        return skill

    def validate_skill(self, skill_id, approved, validator='YUCLAW_RED_TEAM'):
        skill = next((s for s in self.skills if s['id'] == skill_id), None)
        if not skill: return {}
        skill['status'] = 'APPROVED' if approved else 'REJECTED'
        skill['validated'] = approved
        skill['validated_by'] = validator
        skill['validated_date'] = date.today().isoformat()
        if approved:
            skill['yct_earned'] = int(skill['performance']['calmar'] * 100)
            print(f"Approved: {skill['name']} — {skill['yct_earned']} YCT")
        self._save()
        return skill

    def show_marketplace(self):
        print(f"\nFinSkills Marketplace")
        print(f"{'=' * 60}")
        for cat in self.CATEGORIES:
            skills = [s for s in self.skills if s['category'] == cat and s['validated']]
            if skills:
                print(f"\n{cat.upper()}:")
                for s in skills:
                    print(f"  {s['name']:25} Calmar:{s['performance']['calmar']:.3f} "
                          f"Installs:{s['installs']:3} YCT:{s['yct_earned']}")
        total = len([s for s in self.skills if s['validated']])
        print(f"\nTotal approved: {total}")


if __name__ == '__main__':
    market = FinSkillsMarketplace()
    for name, desc, cat, author, c, sh in [
        ('mom_1m_tight', 'Momentum 1-month tight stops', 'momentum', 'YuClawLab', 3.055, 1.89),
        ('mom_6m_tight', 'Momentum 6-month tight stops', 'momentum', 'YuClawLab', 1.763, 1.45),
        ('crisis_hedge', 'Crisis regime hedge strategy', 'macro', 'YuClawLab', 2.1, 1.6),
        ('earnings_vol', 'Earnings volatility play', 'earnings', 'YuClawLab', 1.8, 1.3),
        ('sector_rotation', 'Macro sector rotation', 'macro', 'YuClawLab', 1.5, 1.2),
        ('zkp_momentum', 'ZKP-verified momentum', 'momentum', 'YuClawLab', 2.3, 1.7),
    ]:
        s = market.submit_skill(name, desc, cat, author, c, sh)
        market.validate_skill(s['id'], True)
    market.show_marketplace()
