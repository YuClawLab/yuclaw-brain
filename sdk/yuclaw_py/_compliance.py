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
    "Research and education only. Not investment advice. "
    "Signal labels are research classifications, not buy/sell recommendations. "
    "YUCLAW is not a registered investment adviser."
)

# Public signal vocabulary — anything outside this set returned by the SDK
# is a bug.
PUBLIC_LABELS: tuple[str, ...] = (
    "STRONG_BUY", "BUY", "HOLD", "WATCH",
    "WEAKENING", "NEGATIVE_EVENT", "DOWNSIDE_WATCH", "RISK_ALERT",
)
