"""
Signal Aggregator (v2.4) — 6-component per-ticker composite.

Replaces the prior universe-wide-tie math where every STRONG_BUY ticker ended
up at an identical composite because all three legacy components (factor_score,
universe-wide best Calmar, portfolio VaR) were constants across the top tier.

This version pulls per-ticker mom_1m / calmar_90d / rsi straight from
factor_scan_full.json (which has been computing them all along but the
aggregator was ignoring them).

Revert path: set YUCLAW_AGGREGATOR=legacy in env to dispatch the previous
implementation in signal_aggregator_legacy.py instead.

Composite weights (sum to 1.0):
    factor          0.05   per-ticker factor score (kept, low weight, saturates at 1.0)
    momentum        0.40   per-ticker 1-month return / 1.0, clipped [0,1]    NEW
    ticker_calmar   0.30   per-ticker 90-day Calmar / 20.0, clipped [0,1]    CHANGED from universe-wide
    rsi_health      0.15   1 - |rsi - 60| / 30, clipped [0,1]                NEW
    universe_calmar 0.05   best-strategy Calmar / 5.0, clipped [0,1]         kept as regime anchor
    portfolio_risk  0.05   1 - portfolio_var * 10, clipped [0,1]             kept as macro anchor

Signal labels: composite-based for BUY tiers; factor-score override for
SELL/STRONG_SELL so bearish factor still surfaces even if other components
are neutral.

Output JSON schema is identical to legacy (same 6 keys: ticker, signal, score,
confidence, action, reasoning). price_verifier.py adds 4 more keys after.
"""
import json, os, sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


WEIGHTS = {
    'factor':          0.05,
    'momentum':        0.40,
    'ticker_calmar':   0.30,
    'rsi_health':      0.15,
    'universe_calmar': 0.05,
    'portfolio_risk':  0.05,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, 'weights must sum to 1.0'


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


def _clip(x, lo, hi):
    return max(lo, min(hi, x))


def _rsi_health(rsi):
    """RSI sweet spot ~60. 1.0 at 60; drops to 0 below 30 or above 90."""
    return _clip(1 - abs(rsi - 60) / 30, 0, 1)


class SignalAggregator:
    """v2.4 differentiated aggregator. Backwards-compatible JSON output."""

    WEIGHTS = WEIGHTS  # exposed for introspection

    def __init__(self):
        self._factors   = self._safe_load('output/factor_scan_full.json', [])
        self._backtests = self._safe_load('output/backtest_all.json', [])
        self._risks     = self._safe_load('output/risk_analysis.json', [])
        self._macro     = self._safe_load('output/macro_sector_latest.json', {})
        # Universe anchors precomputed once
        self._universe_calmar  = self._compute_universe_calmar()
        self._portfolio_risk   = self._compute_portfolio_risk()

    @staticmethod
    def _safe_load(path, default):
        try:
            return json.load(open(path))
        except Exception:
            return default

    def _compute_universe_calmar(self) -> float:
        if not self._backtests:
            return 0.0
        try:
            best = max(self._backtests, key=lambda x: x.get('calmar', 0))
            return _clip(best.get('calmar', 0) / 5.0, 0, 1)
        except Exception:
            return 0.0

    def _compute_portfolio_risk(self) -> float:
        try:
            for r in self._risks:
                if r.get('portfolio') == 'balanced':
                    var = abs(r.get('var_95', -0.02))
                    return _clip(1 - var * 10, 0, 1)
            if self._risks:
                vars_ = [abs(r.get('var_95', -0.02)) for r in self._risks]
                return _clip(1 - (sum(vars_) / len(vars_)) * 10, 0, 1)
        except Exception:
            pass
        return 0.5

    def aggregate(self, ticker: str) -> Optional[AggregatedSignal]:
        match = next((f for f in self._factors if f.get('ticker') == ticker), None)
        if not match:
            return None

        factor_score = match.get('score', 0)
        mom_1m       = match.get('mom_1m', 0)
        calmar_90d   = match.get('calmar_90d', 0)
        rsi          = match.get('rsi', 50)

        # Components
        c_factor    = factor_score
        c_momentum  = _clip(mom_1m / 1.0, 0, 1)
        c_tcalmar   = _clip(calmar_90d / 20.0, 0, 1)
        c_rsih      = _rsi_health(rsi)
        c_universe  = self._universe_calmar
        c_portfolio = self._portfolio_risk

        composite = (
            WEIGHTS['factor']          * c_factor +
            WEIGHTS['momentum']        * c_momentum +
            WEIGHTS['ticker_calmar']   * c_tcalmar +
            WEIGHTS['rsi_health']      * c_rsih +
            WEIGHTS['universe_calmar'] * c_universe +
            WEIGHTS['portfolio_risk']  * c_portfolio
        )

        reasoning = [
            f"Factor: {factor_score:+.3f} ({match.get('signal', '?')})",
            f"Per-ticker: mom_1m={mom_1m:+.2%}, calmar_90d={calmar_90d:.2f}, rsi={rsi:.1f}",
            f"Components: f={c_factor:+.3f} m={c_momentum:.3f} tc={c_tcalmar:.3f} "
            f"rsi_h={c_rsih:.3f} u={c_universe:.3f} pr={c_portfolio:.3f}",
        ]

        # Macro alignment kept for reasoning text (not part of score; regime is baked
        # into universe_calmar + portfolio_risk anchors above).
        macro_aligned = False
        try:
            regime = self._macro.get('macro', {}).get('regime', '')
            sig_label = match.get('signal') or ''
            if regime in ('RISK_ON', 'GOLDILOCKS') and sig_label in ('STRONG_BUY', 'BUY'):
                macro_aligned = True
            elif regime in ('CRISIS', 'RISK_OFF') and sig_label in ('STRONG_SELL', 'SELL'):
                macro_aligned = True
            if regime:
                reasoning.append(f"Macro: {regime} | Aligned: {macro_aligned}")
        except Exception:
            pass

        # Signal label: factor-based bearish override; composite-based bullish tiers.
        if c_factor < -0.5:
            signal, action, confidence = 'STRONG_SELL', 'EXIT — strong bearish factor', 0.85
        elif c_factor < -0.2:
            signal, action, confidence = 'SELL', 'REDUCE — bearish factor', 0.70
        elif composite > 0.55:
            signal, action, confidence = 'STRONG_BUY', 'BUY — high conviction', 0.85
        elif composite > 0.35:
            signal, action, confidence = 'BUY', 'BUY — moderate conviction', 0.70
        else:
            signal, action, confidence = 'HOLD', 'HOLD — neutral', 0.60

        return AggregatedSignal(
            ticker=ticker,
            composite_score=round(composite, 3),
            factor_score=factor_score,
            calmar_score=round(c_tcalmar, 3),
            risk_score=round(c_portfolio, 3),
            macro_aligned=macro_aligned,
            final_signal=signal,
            confidence=confidence,
            action=action,
            reasoning=reasoning,
        )

    def scan_all(self, tickers: list) -> list:
        results = []
        for t in tickers:
            s = self.aggregate(t)
            if s:
                results.append(s)
        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results


if __name__ == '__main__':
    # Revert path: YUCLAW_AGGREGATOR=legacy → run legacy aggregator instead.
    if os.environ.get('YUCLAW_AGGREGATOR') == 'legacy':
        import runpy
        print('[YUCLAW_AGGREGATOR=legacy] dispatching to signal_aggregator_legacy.py')
        runpy.run_module('yuclaw.modules.signal_aggregator_legacy', run_name='__main__')
        sys.exit(0)

    sys.path.insert(0, '.')
    from yuclaw.universe import DAILY_CORE
    agg = SignalAggregator()
    results = agg.scan_all(DAILY_CORE)
    print(f'Signal Aggregator (v2.4 differentiated) — {len(results)} tickers')
    buys  = [r for r in results if r.final_signal in ('STRONG_BUY', 'BUY')]
    sells = [r for r in results if r.final_signal in ('STRONG_SELL', 'SELL')]
    print(f'BUY: {len(buys)} | SELL: {len(sells)}')
    print('\nTop 5:')
    for r in results[:5]:
        print(f'  {r.ticker:6} {r.final_signal:12} score:{r.composite_score:+.3f} conf:{r.confidence:.0%}')
        for reason in r.reasoning[:3]:
            print(f'    {reason}')

    os.makedirs('output', exist_ok=True)
    with open('output/aggregated_signals.json', 'w') as f:
        json.dump([{
            'ticker':     r.ticker,
            'signal':     r.final_signal,
            'score':      r.composite_score,
            'confidence': r.confidence,
            'action':     r.action,
            'reasoning':  r.reasoning,
        } for r in results], f, indent=2)
    print('Saved to output/aggregated_signals.json')
