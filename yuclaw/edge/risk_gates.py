"""
YUCLAW risk gates: drawdown-based kill switch.

Intraday drawdown is measured against Alpaca's account.last_equity (yesterday's
close), so the gate auto-resets each day at market open.
"""
from typing import Any


class RiskGate:
    """Drawdown-based halt/liquidate decisions for paper trading."""

    HALT_THRESHOLD      = -0.03   # -3% intraday drawdown halts new orders
    LIQUIDATE_THRESHOLD = -0.08   # -8% triggers emergency-liquidate suggestion

    def check(self, current_equity: float, baseline_equity: float) -> dict[str, Any]:
        """
        Return one of three actions based on intraday drawdown.

        ALLOW     drawdown within limits; new orders may proceed
        HALT      drawdown <= HALT_THRESHOLD; reject new orders (existing positions kept)
        LIQUIDATE drawdown <= LIQUIDATE_THRESHOLD; refuse new order and warn user to
                  run `yuclaw paper liquidate` manually
        """
        if baseline_equity <= 0:
            return {'action': 'HALT', 'drawdown_pct': 0.0,
                    'reason': 'Invalid baseline equity (<=0); cannot compute drawdown'}

        drawdown = (current_equity - baseline_equity) / baseline_equity
        if drawdown <= self.LIQUIDATE_THRESHOLD:
            return {'action': 'LIQUIDATE', 'drawdown_pct': drawdown,
                    'reason': f'Drawdown {drawdown:+.2%} <= {self.LIQUIDATE_THRESHOLD:+.0%}'}
        if drawdown <= self.HALT_THRESHOLD:
            return {'action': 'HALT', 'drawdown_pct': drawdown,
                    'reason': f'Drawdown {drawdown:+.2%} <= {self.HALT_THRESHOLD:+.0%}'}
        return {'action': 'ALLOW', 'drawdown_pct': drawdown,
                'reason': f'Drawdown {drawdown:+.2%} within limits'}
