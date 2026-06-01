"""yuclaw/memory/thesis_tracker.py — Cross-reference current analysis against thesis history.

Detects thesis drift, assumption falsification, and conviction changes over time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from .portfolio_memory import PortfolioMemory, ThesisRecord


@dataclass
class ThesisComparison:
    """Result of comparing current analysis against historical thesis."""
    ticker: str
    current_thesis: str
    prior_count: int
    drift_detected: bool
    drift_description: str
    assumptions_changed: list[str] = field(default_factory=list)
    conviction_trend: str = "stable"  # "increasing", "decreasing", "stable", "new"
    prior_theses: list[str] = field(default_factory=list)

    def to_context(self) -> str:
        """Format as context for the LLM prompt."""
        if self.prior_count == 0:
            return f"\n[Thesis Tracker] First analysis for {self.ticker}. No prior history.\n"

        lines = [
            f"\n=== THESIS TRACKER: {self.ticker} ===",
            f"Prior analyses: {self.prior_count}",
            f"Conviction trend: {self.conviction_trend}",
        ]
        if self.drift_detected:
            lines.append(f"DRIFT DETECTED: {self.drift_description}")
        if self.assumptions_changed:
            lines.append("Assumptions changed:")
            for a in self.assumptions_changed:
                lines.append(f"  - {a}")
        if self.prior_theses:
            lines.append("Recent thesis history:")
            for t in self.prior_theses[:3]:
                lines.append(f"  - {t[:120]}")
        lines.append("=== END THESIS TRACKER ===\n")
        return "\n".join(lines)


class ThesisTracker:
    """Track thesis evolution across research sessions."""

    def __init__(self, memory: PortfolioMemory):
        self._memory = memory

    async def compare_against_history(
        self, ticker: str, current_thesis: str, current_assumptions: list[str]
    ) -> ThesisComparison:
        """Compare the current analysis against all prior theses for this ticker.

        Detects:
        - Thesis drift (fundamental change in investment thesis)
        - Assumption changes (new or removed key assumptions)
        - Conviction trend (are conclusions getting more/less bullish?)
        """
        history = await self._memory.get_history(ticker)

        if not history:
            return ThesisComparison(
                ticker=ticker,
                current_thesis=current_thesis,
                prior_count=0,
                drift_detected=False,
                drift_description="",
                conviction_trend="new",
            )

        prior_theses = [h.thesis for h in history]
        prior_assumptions_flat = set()
        for h in history:
            prior_assumptions_flat.update(h.key_assumptions)

        # Detect assumption changes
        current_set = set(current_assumptions)
        new_assumptions = current_set - prior_assumptions_flat
        removed_assumptions = prior_assumptions_flat - current_set
        assumptions_changed = []
        for a in new_assumptions:
            assumptions_changed.append(f"NEW: {a}")
        for a in removed_assumptions:
            assumptions_changed.append(f"REMOVED: {a}")

        # Simple drift detection via keyword overlap
        latest = history[0]
        latest_words = set(latest.thesis.lower().split())
        current_words = set(current_thesis.lower().split())
        overlap = len(latest_words & current_words) / max(len(latest_words | current_words), 1)
        drift_detected = overlap < 0.3  # Less than 30% word overlap = drift

        drift_description = ""
        if drift_detected:
            drift_description = (
                f"Thesis has shifted significantly since {latest.created_at[:10]}. "
                f"Word overlap: {overlap:.0%}. Review whether prior assumptions still hold."
            )

        # Conviction trend (simple: count bull/bear keywords)
        bull_words = {"growth", "strong", "bullish", "expansion", "upside", "outperform"}
        bear_words = {"risk", "decline", "bearish", "contraction", "downside", "underperform"}

        def sentiment_score(text: str) -> float:
            words = set(text.lower().split())
            return len(words & bull_words) - len(words & bear_words)

        current_score = sentiment_score(current_thesis)
        prior_scores = [sentiment_score(t) for t in prior_theses[:3]]
        avg_prior = sum(prior_scores) / max(len(prior_scores), 1)

        if current_score > avg_prior + 0.5:
            conviction_trend = "increasing"
        elif current_score < avg_prior - 0.5:
            conviction_trend = "decreasing"
        else:
            conviction_trend = "stable"

        return ThesisComparison(
            ticker=ticker,
            current_thesis=current_thesis,
            prior_count=len(history),
            drift_detected=drift_detected,
            drift_description=drift_description,
            assumptions_changed=assumptions_changed[:10],
            conviction_trend=conviction_trend,
            prior_theses=prior_theses[:3],
        )
