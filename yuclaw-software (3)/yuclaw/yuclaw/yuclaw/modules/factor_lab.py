"""
yuclaw/modules/factor_lab.py

Adversarial Factor Lab — natural language → strategy → Red Team → conditional execution.
This is YUCLAW's most powerful exclusive capability.
No other system closes this loop.
"""
from __future__ import annotations
import json
import asyncio
from datetime import datetime, timezone
from ..core.router import get_router
from ..validation.engine import ValidationAgent, DarwinianSandbox


FACTOR_SYSTEM = """You are the YUCLAW Quant Factor Engineer.
Given a natural language factor request, generate a complete quantitative factor specification.
Output JSON only:
{
  "factor_name": str,
  "factor_type": "momentum|value|quality|volatility|sentiment|macro|technical",
  "universe": str,
  "signal_definition": str,
  "lookback_period_days": int,
  "rebalance_frequency": "daily|weekly|monthly|quarterly",
  "long_short": bool,
  "position_sizing": str,
  "stop_loss_pct": float,
  "expected_annual_return_pct": float,
  "expected_volatility_pct": float,
  "expected_calmar_ratio": float,
  "known_failure_regimes": [str],
  "data_requirements": [str],
  "python_pseudocode": str,
  "risk_controls": [str]
}
JSON only. No preamble."""

BACKTEST_SUMMARY_SYSTEM = """You are a quantitative analyst evaluating a factor strategy.
Given factor specification and market data, estimate historical performance.
Output JSON only:
{
  "period": str,
  "annualized_return_pct": float,
  "annualized_volatility_pct": float,
  "sharpe_ratio": float,
  "max_drawdown_pct": float,
  "calmar_ratio": float,
  "win_rate_pct": float,
  "best_month_pct": float,
  "worst_month_pct": float,
  "regime_performance": {"risk_on": str, "risk_off": str, "crisis": str},
  "factor_decay_days": int,
  "capacity_estimate_usd": str
}
JSON only. No preamble."""


class FactorLab:
    """
    Natural language → factor spec → adversarial validation → conditional paper trading.
    
    The closed loop that no competitor has:
    User: "Find best momentum ETF factor from last 90 days"
    System: generates factor → attacks it with Red Team → if Calmar > threshold → paper trading
    """

    def __init__(self, validation_agent: ValidationAgent):
        self._router    = get_router()
        self._validator = validation_agent

    async def build_and_validate(
        self,
        instruction: str,
        calmar_threshold: float = 1.0,
        auto_paper_trade: bool = False,
    ) -> dict:
        """
        Full Factor Lab pipeline.
        Returns factor spec + validation result + paper trading recommendation.
        """
        print(f"\n[Factor Lab] Processing: {instruction}")

        # Step 1: Generate factor specification
        print("  Step 1/3: Generating factor specification...")
        factor_resp = await self._router.complete(
            prompt=f"Generate a quantitative factor for: {instruction}",
            system=FACTOR_SYSTEM,
            max_tokens=3000
        )
        try:
            factor = json.loads(factor_resp)
        except Exception:
            factor = {"factor_name": "custom_factor", "signal_definition": factor_resp,
                      "expected_calmar_ratio": 1.0}

        factor_name = factor.get("factor_name", "unnamed_factor")
        print(f"  Factor: {factor_name}")

        # Step 2: Estimate backtest performance
        print("  Step 2/3: Estimating historical performance...")
        backtest_resp = await self._router.complete(
            prompt=(f"Factor specification:\n{json.dumps(factor, indent=2)}\n\n"
                    f"Estimate historical performance characteristics for this factor "
                    f"over the past 5 years across US equity ETF universe."),
            system=BACKTEST_SUMMARY_SYSTEM,
            max_tokens=1500
        )
        try:
            backtest = json.loads(backtest_resp)
        except Exception:
            backtest = {"error": "parse_failed", "raw": backtest_resp[:300]}

        # Step 3: Adversarial validation (Red Team attack)
        print("  Step 3/3: Red Team adversarial attack...")
        strategy_id = f"factor_{factor_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        strategy_description = (
            f"Factor: {factor_name}\n"
            f"Type: {factor.get('factor_type', 'unknown')}\n"
            f"Universe: {factor.get('universe', 'unknown')}\n"
            f"Signal: {factor.get('signal_definition', '')}\n"
            f"Lookback: {factor.get('lookback_period_days', '?')} days\n"
            f"Rebalance: {factor.get('rebalance_frequency', 'monthly')}\n"
            f"Known failure regimes: {factor.get('known_failure_regimes', [])}\n"
            f"Risk controls: {factor.get('risk_controls', [])}"
        )
        validation = await self._validator.validate(strategy_id, strategy_description)

        passed    = validation["passed"]
        calmar_ok = float(validation.get("calmar_ratio", 0)) >= calmar_threshold

        # Determine execution recommendation
        if passed and calmar_ok:
            execution_rec = "ADVANCE TO PAPER TRADING"
            exec_level    = 2
        elif not passed:
            execution_rec = "REJECTED — failed adversarial validation"
            exec_level    = 0
        else:
            execution_rec = "CONDITIONAL — review failure modes before proceeding"
            exec_level    = 0

        result = {
            "factor":              factor,
            "backtest_estimate":   backtest,
            "validation":          validation,
            "execution_recommendation": execution_rec,
            "execution_level":     exec_level,
            "ready_for_paper_trade": passed and calmar_ok,
            "strategy_id":         strategy_id,
            "timestamp":           datetime.now(timezone.utc).isoformat(),
        }

        # Console summary
        icon = "✅" if passed else "❌"
        print(f"\n  {icon} Factor: {factor_name}")
        print(f"  Calmar: {validation.get('calmar_ratio')}  |  Survival: {validation.get('survival_rate')}")
        print(f"  Killed by: {validation.get('scenarios_killed')}/{validation.get('scenarios_tested')} scenarios")
        print(f"  Recommendation: {execution_rec}")

        return result
