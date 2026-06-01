"""
yuclaw/modules/scenario_shock.py

Scenario Shock Engine — event → complete impact cascade.
Input:  "Hormuz Strait blocked"
Output: full transmission graph, beneficiary/casualty assets, portfolio sensitivity.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from ..core.router import get_router


SHOCK_SYSTEM = """You are the YUCLAW Scenario Shock Engine.
Model the complete impact cascade of a macro shock event.
Output JSON only:
{
  "event": str,
  "event_type": "geopolitical|monetary|fiscal|credit|commodity|regulatory|natural",
  "probability": "low|medium|high",
  "transmission_chain": [
    {"step": int, "mechanism": str, "affected_markets": [str], "direction": "positive|negative", "magnitude": "small|medium|large|extreme"}
  ],
  "asset_impacts": {
    "direct_beneficiaries": [{"asset": str, "reason": str, "magnitude": str, "timeframe": str}],
    "indirect_beneficiaries": [{"asset": str, "reason": str}],
    "direct_casualties": [{"asset": str, "reason": str, "magnitude": str, "timeframe": str}],
    "indirect_casualties": [{"asset": str, "reason": str}]
  },
  "sector_rotation": {"into": [str], "out_of": [str]},
  "portfolio_hedges": [{"instrument": str, "rationale": str}],
  "time_horizons": {
    "immediate_1_5_days": str,
    "short_term_1_4_weeks": str,
    "medium_term_1_3_months": str
  },
  "historical_analogues": [{"event": str, "year": int, "outcome": str}],
  "adversarial_scenario": str,
  "watchlist_additions": [str]
}
JSON only. No preamble."""


class ScenarioShockEngine:
    def __init__(self):
        self._router = get_router()

    async def analyze(self, event: str) -> dict:
        print(f"\n[Shock Engine] Modeling: {event}")

        response = await self._router.complete(
            prompt=f"Model the complete macro shock cascade for: {event}",
            system=SHOCK_SYSTEM,
            max_tokens=5000
        )

        try:
            result = json.loads(response)
        except Exception:
            result = {"event": event, "raw_analysis": response, "error": "parse_failed"}

        result["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        return result

    def format_output(self, result: dict) -> str:
        lines = [
            f"\n{'═'*60}",
            f"  SCENARIO SHOCK ENGINE",
            f"  Event: {result.get('event','')}",
            f"  Type: {result.get('event_type','').upper()}  |  Probability: {result.get('probability','').upper()}",
            f"{'═'*60}",
        ]

        # Transmission chain
        chain = result.get("transmission_chain", [])
        if chain:
            lines.append("\n  TRANSMISSION CHAIN:")
            for step in chain[:5]:
                icon = "↗" if step.get("direction") == "positive" else "↘"
                lines.append(f"  {step.get('step','?')}. {icon} {step.get('mechanism','')} → {', '.join(step.get('affected_markets',[]))[:60]}")

        # Impact
        impacts = result.get("asset_impacts", {})
        if impacts.get("direct_casualties"):
            lines.append("\n  CASUALTIES:")
            for c in impacts["direct_casualties"][:4]:
                lines.append(f"    ❌  {c.get('asset',''):15}  {c.get('reason','')[:50]}  [{c.get('magnitude','')}]")

        if impacts.get("direct_beneficiaries"):
            lines.append("\n  BENEFICIARIES:")
            for b in impacts["direct_beneficiaries"][:4]:
                lines.append(f"    ✅  {b.get('asset',''):15}  {b.get('reason','')[:50]}  [{b.get('magnitude','')}]")

        # Sector rotation
        sr = result.get("sector_rotation", {})
        if sr:
            lines.append(f"\n  ROTATE INTO: {', '.join(sr.get('into',[])[:4])}")
            lines.append(f"  ROTATE OUT:  {', '.join(sr.get('out_of',[])[:4])}")

        # Time horizons
        horizons = result.get("time_horizons", {})
        if horizons:
            lines.append("\n  TIME HORIZONS:")
            lines.append(f"  1-5d:   {horizons.get('immediate_1_5_days','')[:70]}")
            lines.append(f"  1-4wk:  {horizons.get('short_term_1_4_weeks','')[:70]}")
            lines.append(f"  1-3mo:  {horizons.get('medium_term_1_3_months','')[:70]}")

        # Analogues
        analogues = result.get("historical_analogues", [])
        if analogues:
            lines.append("\n  HISTORICAL ANALOGUES:")
            for a in analogues[:2]:
                lines.append(f"    {a.get('year','?')} — {a.get('event','')}: {a.get('outcome','')[:60]}")

        # Watchlist
        wl = result.get("watchlist_additions", [])
        if wl:
            lines.append(f"\n  ADD TO WATCHLIST: {', '.join(wl[:6])}")

        lines.append("═"*60)
        return "\n".join(lines)
