"""
YCT — YUCLAW Governance Token (ERC-20 compatible).
Earned by: contributing signals, validating strategies, building skills.
Used for: governance votes, premium features, staking.
"""
import json, os, time, hashlib
from datetime import date

YCT_TOKENOMICS = {
    'name': 'YUCLAW Governance Token', 'symbol': 'YCT',
    'total_supply': 100_000_000, 'decimals': 18,
    'distribution': {'community_rewards': 0.40, 'team': 0.20, 'ecosystem': 0.25, 'reserve': 0.15},
    'earning_rates': {
        'signal_correct': 10, 'strategy_approved': 100,
        'skill_installed_10x': 50, 'data_contribution': 5, 'governance_vote': 1
    }
}


class YCTToken:

    LEDGER_FILE = 'output/token/yct_ledger.json'

    def __init__(self):
        os.makedirs('output/token', exist_ok=True)
        self.ledger = self._load()

    def _load(self):
        if os.path.exists(self.LEDGER_FILE):
            return json.load(open(self.LEDGER_FILE))
        return {
            'balances': {}, 'transactions': [], 'total_minted': 0,
            'total_supply': YCT_TOKENOMICS['total_supply'], 'governance_proposals': []
        }

    def _save(self):
        with open(self.LEDGER_FILE, 'w') as f:
            json.dump(self.ledger, f, indent=2)

    def _tx_hash(self, f, t, amt, reason):
        return f"0x{hashlib.sha256(f'{f}{t}{amt}{reason}{time.time()}'.encode()).hexdigest()}"

    def mint(self, address, amount, reason):
        if self.ledger['total_minted'] + amount > YCT_TOKENOMICS['total_supply']:
            return {'error': 'Exceeds total supply'}
        self.ledger['balances'].setdefault(address, 0)
        self.ledger['balances'][address] += amount
        self.ledger['total_minted'] += amount
        tx = {'hash': self._tx_hash('MINT', address, amount, reason), 'type': 'MINT',
              'to': address, 'amount': amount, 'reason': reason, 'date': date.today().isoformat()}
        self.ledger['transactions'].append(tx)
        self._save()
        print(f"Minted {amount} YCT to {address[:12]}... | {reason}")
        return tx

    def reward_signal(self, address, ticker, correct):
        if correct:
            return self.mint(address, YCT_TOKENOMICS['earning_rates']['signal_correct'], f"Correct signal: {ticker}")
        return {'amount': 0}

    def reward_strategy(self, address, strategy):
        return self.mint(address, YCT_TOKENOMICS['earning_rates']['strategy_approved'], f"Strategy approved: {strategy}")

    def create_proposal(self, title, description, proposer):
        proposal = {
            'id': len(self.ledger['governance_proposals']) + 1, 'title': title,
            'description': description, 'proposer': proposer,
            'created': date.today().isoformat(), 'votes_for': 0,
            'votes_against': 0, 'status': 'ACTIVE', 'quorum': 1000
        }
        self.ledger['governance_proposals'].append(proposal)
        self._save()
        print(f"Proposal #{proposal['id']}: {title}")
        return proposal

    def vote(self, proposal_id, voter, support, yct_amount):
        p = next((p for p in self.ledger['governance_proposals'] if p['id'] == proposal_id), None)
        if not p: return {'error': 'Not found'}
        if self.ledger['balances'].get(voter, 0) < yct_amount:
            return {'error': 'Insufficient YCT'}
        if support: p['votes_for'] += yct_amount
        else: p['votes_against'] += yct_amount
        if p['votes_for'] + p['votes_against'] >= p['quorum']:
            p['status'] = 'PASSED' if p['votes_for'] > p['votes_against'] else 'FAILED'
        self._save()
        self.mint(voter, YCT_TOKENOMICS['earning_rates']['governance_vote'], f"Vote #{proposal_id}")
        return p

    def show_stats(self):
        print(f"\nYCT — YUCLAW Governance Token")
        print(f"{'=' * 50}")
        print(f"Supply: {YCT_TOKENOMICS['total_supply']:,} | Minted: {self.ledger['total_minted']:,}")
        print(f"Holders: {len(self.ledger['balances'])} | Txns: {len(self.ledger['transactions'])}")
        top = sorted(self.ledger['balances'].items(), key=lambda x: x[1], reverse=True)[:5]
        print(f"\nTop Holders:")
        for addr, bal in top:
            print(f"  {addr[:16]}... {bal:,} YCT")
        print(f"Proposals: {len(self.ledger['governance_proposals'])}")


if __name__ == '__main__':
    token = YCTToken()
    addrs = {
        'YuClawLab': '0xYuClawLab00000000', 'User1': '0xEarlyUser10000001',
        'User2': '0xEarlyUser20000002', 'Community': '0xCommunity00000003',
    }
    token.mint(addrs['YuClawLab'], 20_000_000, 'Team allocation')
    token.mint(addrs['Community'], 5_000_000, 'Community pool')
    token.reward_signal(addrs['User1'], 'LUNR', True)
    token.reward_signal(addrs['User1'], 'ASTS', True)
    token.reward_signal(addrs['User2'], 'DELL', True)
    token.reward_strategy(addrs['YuClawLab'], 'mom_1m_tight')
    p = token.create_proposal('Expand universe to 500 tickers', 'Expand from 167 to 500', addrs['User1'])
    token.vote(p['id'], addrs['YuClawLab'], True, 100)
    token.show_stats()
