"""
Competitive Intelligence — compares YUCLAW signals vs market consensus.
When YUCLAW disagrees with consensus — that is where alpha lives.
Real consensus from analyst ratings via yfinance.
"""
import yfinance as yf, json, os
from dataclasses import dataclass
from typing import Optional

@dataclass
class CompetitiveSignal:
    ticker: str
    yuclaw_signal: str
    yuclaw_score: float
    analyst_consensus: str
    analyst_target: Optional[float]
    current_price: Optional[float]
    upside_to_target: Optional[float]
    agreement: bool
    alpha_opportunity: bool
    notes: str
    is_real: bool = True

class CompetitiveIntelScanner:
    def scan(self, ticker: str, yuclaw_score: float, yuclaw_signal: str) -> CompetitiveSignal:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            current = float(info.get('currentPrice') or info.get('regularMarketPrice') or 0)
            target = float(info.get('targetMeanPrice') or 0)
            rec = info.get('recommendationKey', 'none').upper()
            upside = (target - current) / current if current > 0 and target > 0 else None

            consensus_map = {
                'STRONG_BUY': 'BUY', 'BUY': 'BUY',
                'HOLD': 'HOLD', 'UNDERPERFORM': 'SELL',
                'SELL': 'SELL', 'STRONG_SELL': 'SELL',
                'NONE': 'UNKNOWN'
            }
            analyst_signal = consensus_map.get(rec, 'UNKNOWN')
            yuclaw_dir = 'BUY' if yuclaw_signal in ('STRONG_BUY','BUY') else 'SELL' if yuclaw_signal in ('STRONG_SELL','SELL') else 'HOLD'
            agreement = analyst_signal == yuclaw_dir

            alpha_opportunity = (
                not agreement and
                abs(yuclaw_score) > 0.3 and
                analyst_signal != 'UNKNOWN'
            )

            notes = ''
            if alpha_opportunity:
                if yuclaw_dir == 'BUY' and analyst_signal == 'SELL':
                    notes = 'CONTRARIAN BUY — YUCLAW bullish vs analyst sell'
                elif yuclaw_dir == 'SELL' and analyst_signal == 'BUY':
                    notes = 'CONTRARIAN SELL — YUCLAW bearish vs analyst buy'
            elif agreement:
                notes = f'Consensus agreement — {yuclaw_dir}'

            return CompetitiveSignal(
                ticker=ticker, yuclaw_signal=yuclaw_signal,
                yuclaw_score=yuclaw_score, analyst_consensus=analyst_signal,
                analyst_target=target if target > 0 else None,
                current_price=current if current > 0 else None,
                upside_to_target=round(upside,3) if upside else None,
                agreement=agreement, alpha_opportunity=alpha_opportunity,
                notes=notes
            )
        except:
            return CompetitiveSignal(ticker=ticker, yuclaw_signal=yuclaw_signal,
                yuclaw_score=yuclaw_score, analyst_consensus='UNKNOWN',
                analyst_target=None, current_price=None, upside_to_target=None,
                agreement=False, alpha_opportunity=False, notes='Data unavailable')

if __name__=='__main__':
    import sys; sys.path.insert(0,'.')
    os.makedirs('output', exist_ok=True)
    try:
        signals = json.load(open('output/aggregated_signals.json'))
        scanner = CompetitiveIntelScanner()
        results = []
        alpha_ops = []
        for s in signals[:20]:
            r = scanner.scan(s['ticker'], s['score'], s['signal'])
            results.append({'ticker':r.ticker,'yuclaw':r.yuclaw_signal,'analyst':r.analyst_consensus,'agreement':r.agreement,'alpha':r.alpha_opportunity,'notes':r.notes,'upside':r.upside_to_target})
            if r.alpha_opportunity:
                alpha_ops.append(r)
                print(f'ALPHA: {r.ticker:6} YUCLAW:{r.yuclaw_signal:12} vs Analyst:{r.analyst_consensus:8} — {r.notes}')
        with open('output/competitive_intel.json','w') as f:
            json.dump(results, f, indent=2)
        print(f'\n{len(alpha_ops)} alpha opportunities found')
        print(f'Saved to output/competitive_intel.json')
    except Exception as e:
        print(f'Run signal aggregator first: {e}')
