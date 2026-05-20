"""Signal Radar — detect material signal changes and broadcast to enabled channels.

Architecture:
  detector.py       — finds changes between consecutive OOS snapshots
  notifier.py       — abstract Notifier + shared formatting / footer
  adapters/         — telegram, email, slack — each self-disables when
                      credentials are absent so a partial setup never errors
  run.py            — orchestrator + audit log
"""

# Locked compliance footer for v3.0. Identical wording in every channel
# so a reader pasting one message into another medium can't strip it.
COMPLIANCE_FOOTER = (
    "Research and education only. Not investment advice. "
    "Signal labels are research classifications, not buy/sell recommendations. "
    "YUCLAW is not a registered investment adviser."
)

# Locked public vocabulary — anything outside this set is a bug.
PUBLIC_LABELS = (
    "STRONG_BUY", "BUY", "HOLD", "WATCH",
    "WEAKENING", "NEGATIVE_EVENT", "DOWNSIDE_WATCH", "RISK_ALERT",
)
