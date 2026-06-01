"""yuclaw/validation/engine.py — Adversarial validation engine."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
import aiosqlite
from ..core.ontology.models import ValidationStatus
from ..core.router import get_router


# ─────────────────────────────────────────────────────────
#  VALIDATION STUDIO
# ─────────────────────────────────────────────────────────

ALLOWED_TRANSITIONS = {
    ValidationStatus.IDEA:               [ValidationStatus.EVIDENCE_EXTRACTED, ValidationStatus.REJECTED],
    ValidationStatus.EVIDENCE_EXTRACTED: [ValidationStatus.RED_TEAM_TESTED, ValidationStatus.REJECTED],
    ValidationStatus.RED_TEAM_TESTED:    [ValidationStatus.REGIME_VALIDATED, ValidationStatus.REJECTED],
    ValidationStatus.REGIME_VALIDATED:   [ValidationStatus.POLICY_CLEARED, ValidationStatus.REJECTED],
    ValidationStatus.POLICY_CLEARED:     [ValidationStatus.APPROVED, ValidationStatus.REJECTED],
    ValidationStatus.APPROVED:           [ValidationStatus.SEALED],
}


class ValidationStudio:
    def __init__(self, db_path: str = "data/studio.db"):
        import os; os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db = db_path

    async def initialize(self):
        async with aiosqlite.connect(self._db) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS objects (
                    id TEXT PRIMARY KEY, name TEXT,
                    status TEXT DEFAULT 'Idea',
                    created TEXT, updated TEXT,
                    history TEXT DEFAULT '[]'
                )
            """)
            await db.commit()

    async def register(self, obj_id: str, name: str):
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._db) as db:
            await db.execute(
                "INSERT OR IGNORE INTO objects (id,name,created,updated) VALUES (?,?,?,?)",
                (obj_id, name, now, now)
            )
            await db.commit()

    async def advance(self, obj_id: str, new_status: ValidationStatus,
                      agent: str, evidence: str = "") -> bool:
        now = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self._db) as db:
            async with db.execute(
                "SELECT status, history FROM objects WHERE id=?", (obj_id,)
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return False
                current = ValidationStatus(row[0])
                history = json.loads(row[1])

            if new_status not in ALLOWED_TRANSITIONS.get(current, []):
                return False

            history.append({
                "from": current.value, "to": new_status.value,
                "agent": agent, "at": now, "evidence": evidence
            })
            await db.execute(
                "UPDATE objects SET status=?,updated=?,history=? WHERE id=?",
                (new_status.value, now, json.dumps(history), obj_id)
            )
            await db.commit()
        return True

    async def get_status(self, obj_id: str) -> dict:
        async with aiosqlite.connect(self._db) as db:
            async with db.execute(
                "SELECT id,name,status,created,updated,history FROM objects WHERE id=?", (obj_id,)
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return {}
                return {
                    "id": row[0], "name": row[1], "status": row[2],
                    "created": row[3], "updated": row[4],
                    "history": json.loads(row[5])
                }


# ─────────────────────────────────────────────────────────
#  DARWINIAN SANDBOX
# ─────────────────────────────────────────────────────────

BASE_ATTACK_SCENARIOS = [
    "Flash crash: market drops 15% in 30 minutes, bid-ask spreads widen 10x, all liquidity vanishes",
    "Factor crowding reversal: momentum factor unwinds sharply as hedge funds de-gross simultaneously",
    "Regime break: overnight shift from risk-on to crisis, all correlations spike to 0.95",
    "Liquidity freeze: 3-month Treasury market freezes, no buyers for any risky asset",
    "Central bank surprise: emergency 100bps rate cut, all rate-sensitive positions reverse violently",
    "Earnings shock: 30% of portfolio names miss estimates in the same week",
    "Regulatory shock: key sector pricing power eliminated overnight by emergency decree",
    "Correlation breakdown: all previously uncorrelated assets suddenly move together at +0.9",
]

ATTACK_SYSTEM = """You are a hostile adversarial agent. Your ONLY job is to DESTROY this strategy.
Find the 5 most devastating, realistic market scenarios in which this strategy fails catastrophically.
For each: describe the exact conditions, the mechanism of failure, and the estimated max drawdown.
Output JSON array only: [{"scenario": str, "failure_mechanism": str, "estimated_max_drawdown": float}]
Be ruthless. Be specific. No preamble. JSON only."""

EVAL_SYSTEM = """Evaluate whether this strategy survives this specific market scenario.
Output JSON only: {"survived": bool, "max_drawdown": float, "failure_mechanism": str}
No preamble. JSON only."""


@dataclass
class StressResult:
    scenario: str
    survived: bool
    max_drawdown: float
    failure_mechanism: str = ""


@dataclass
class SandboxResult:
    strategy_id: str
    total: int
    survived_count: int
    killed_count: int
    survival_rate: float
    worst_drawdown: float
    calmar_ratio: float
    passed: bool
    stress_results: list[StressResult] = field(default_factory=list)
    ai_scenarios: list[str] = field(default_factory=list)
    fatal_scenarios: list[str] = field(default_factory=list)


class DarwinianSandbox:
    def __init__(self, calmar_threshold: float = 1.0):
        self._router   = get_router()
        self._threshold = calmar_threshold
        # Wire in real backtester for actual Calmar computation
        try:
            from ..validation.real_backtest import RealBacktester
            self._real_bt = RealBacktester()
        except ImportError:
            self._real_bt = None

    async def attack(self, strategy: str, strategy_id: str) -> SandboxResult:
        # Step 1: AI generates strategy-specific attack scenarios
        try:
            ai_resp = await self._router.complete(
                prompt=f"Strategy to destroy:\n{strategy}",
                system=ATTACK_SYSTEM,
                max_tokens=2048
            )
            ai_data = json.loads(ai_resp)
            ai_scenarios = [s.get("scenario", str(s)) for s in ai_data if isinstance(s, dict)]
        except Exception:
            ai_scenarios = []

        all_scenarios = BASE_ATTACK_SCENARIOS + ai_scenarios[:5]

        # Step 2: Evaluate each scenario
        results: list[StressResult] = []
        for scenario in all_scenarios:
            r = await self._eval(strategy, scenario)
            results.append(r)

        # Step 3: Calculate survival stats
        killed    = [r for r in results if not r.survived]
        survived  = len(results) - len(killed)
        worst_dd  = max((abs(r.max_drawdown) for r in killed), default=0.05)

        # Use REAL Calmar from actual price data — strategy-specific parameters
        calmar = 0.15 / worst_dd if worst_dd > 0 else 0.0
        if self._real_bt:
            try:
                import re
                # Extract lookback from strategy text
                lb_match = re.search(r'(\d+)\s*-?\s*(?:month|mo|m)\b', strategy, re.I)
                lookback = int(lb_match.group(1)) if lb_match else 6
                # Extract top_n
                top_match = re.search(r'top\s*(\d+)', strategy, re.I)
                top_n = int(top_match.group(1)) if top_match else 3
                # Extract stop loss
                stop_match = re.search(r'(\d+)\s*%?\s*stop', strategy, re.I)
                stop_loss = int(stop_match.group(1)) / 100 if stop_match else 0.05
                # Extract tickers for custom universe
                ticker_match = re.findall(r'\b([A-Z]{2,5})\b', strategy)
                known_etfs = {'SPY','QQQ','IWM','EFA','EEM','XLK','XLF','XLE','XLV','XLI',
                              'XLP','XLU','XLY','XLB','XLRE','TLT','GLD','SLV','VNQ','HYG',
                              'ARKK','SOXL','XBI','TQQQ','UVXY','SVXY','TAN','ICLN','IBIT',
                              'COIN','MSTR','HOOD','NVDA','AMD','SMCI','PLTR','TSLA','AAPL',
                              'MSFT','META','AMZN','GOOGL','ARM','NNE','OKLO','RKLB','ASTS',
                              'LUNR','CCJ','SMR','URA','EEM','INDA','LLY','NVO','IEF','TIPS'}
                custom_tickers = [t for t in ticker_match if t in known_etfs]

                from ..validation.real_backtest import RealBacktester
                if len(custom_tickers) >= 3:
                    bt = RealBacktester(universe=custom_tickers)
                else:
                    bt = self._real_bt

                real_result = bt.run_momentum(
                    start="2010-01-01",
                    lookback_months=max(1, min(lookback, 24)),
                    top_n=max(1, min(top_n, 10)),
                    stop_loss=max(0.01, min(stop_loss, 0.20)),
                )
                if real_result and real_result.calmar_ratio > 0:
                    calmar = real_result.calmar_ratio
                    worst_dd = real_result.max_drawdown
            except Exception:
                pass  # Fall back to LLM-estimated Calmar

        passed = (calmar >= self._threshold) and (survived / len(results) >= 0.5)

        return SandboxResult(
            strategy_id   = strategy_id,
            total         = len(results),
            survived_count = survived,
            killed_count  = len(killed),
            survival_rate = survived / len(results),
            worst_drawdown = worst_dd,
            calmar_ratio  = calmar,
            passed        = passed,
            stress_results = results,
            ai_scenarios  = ai_scenarios[:5],
            fatal_scenarios = [r.scenario[:80] for r in killed[:5]],
        )

    async def _eval(self, strategy: str, scenario: str) -> StressResult:
        try:
            resp = await self._router.complete(
                prompt=f"Strategy: {strategy}\n\nScenario: {scenario}",
                system=EVAL_SYSTEM,
                max_tokens=256
            )
            d = json.loads(resp)
            return StressResult(
                scenario=scenario,
                survived=bool(d.get("survived", False)),
                max_drawdown=abs(float(d.get("max_drawdown", 0.35))),
                failure_mechanism=str(d.get("failure_mechanism", ""))
            )
        except Exception:
            return StressResult(scenario=scenario, survived=False,
                                max_drawdown=0.4, failure_mechanism="eval_error")


# ─────────────────────────────────────────────────────────
#  VALIDATION AGENT (ties it all together)
# ─────────────────────────────────────────────────────────

class ValidationAgent:
    """
    The Red Team. Attacks strategies. MUST reject some.
    If it never rejects, it is broken.
    """

    def __init__(self, calmar_threshold: float = 1.0):
        self._sandbox = DarwinianSandbox(calmar_threshold=calmar_threshold)
        self._studio  = ValidationStudio()

    async def initialize(self):
        await self._studio.initialize()

    async def validate(self, strategy_id: str, strategy_description: str) -> dict:
        await self._studio.register(strategy_id, strategy_description[:100])

        result = await self._sandbox.attack(strategy_description, strategy_id)

        new_status = ValidationStatus.RED_TEAM_TESTED if result.passed else ValidationStatus.REJECTED
        await self._studio.advance(
            strategy_id, new_status,
            agent="validation_agent",
            evidence=f"Calmar:{result.calmar_ratio:.2f} Survival:{result.survival_rate:.0%}"
        )

        return {
            "strategy_id":       strategy_id,
            "passed":            result.passed,
            "verdict":           "APPROVED — passed Red Team" if result.passed else "REJECTED — failed Red Team",
            "calmar_ratio":      round(result.calmar_ratio, 3),
            "survival_rate":     f"{result.survival_rate:.0%}",
            "scenarios_tested":  result.total,
            "scenarios_survived": result.survived_count,
            "scenarios_killed":  result.killed_count,
            "worst_drawdown":    f"{result.worst_drawdown:.0%}",
            "status":            new_status.value,
            "fatal_scenarios":   result.fatal_scenarios,
            "ai_attack_scenarios": result.ai_scenarios[:3],
        }
