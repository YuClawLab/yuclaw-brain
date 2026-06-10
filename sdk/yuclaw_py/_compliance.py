"""
Locked compliance constants — keep this file boring and the wording
audit-able. Anyone trying to weaken the not-advice posture has to edit
exactly one place.
"""

COMPLIANCE: dict[str, bool] = {
    "not_advice": True,
    "research_only": True,
    "not_registered_adviser": True,
}

COMPLIANCE_NOTICE: str = (
    # Must match v4/api/schema.py::COMPLIANCE_NOTICE verbatim (the SDK is standalone,
    # so the canonical text is duplicated rather than imported). Day 9.
    "YUCLAW research output. Not investment advice. "
    "Past performance does not guarantee future results. "
    "Signal labels are research classifications, not buy/sell recommendations."
)

# Public signal vocabulary — anything outside this set returned by the SDK
# is a bug.
PUBLIC_LABELS: tuple[str, ...] = (
    "STRONG_BULLISH", "BULLISH", "NEUTRAL", "WATCH",
    "WEAKENING", "NEGATIVE_EVENT", "BEARISH_WATCH", "RISK_ALERT",
)
