"""
yuclaw-evidence — Python SDK for the YUCLAW research platform.

Distribution name on PyPI is `yuclaw-evidence`; import name is `yuclaw_py`.

Public surface:
    Client(source="postgres"|"api", dsn=..., base_url=...)
        .signal(ticker)
        .why(ticker)
        .replay(ticker, date)
        .validation()
        .events(ticker, since=None)
        .universe()

All signal-bearing returns include a `compliance` dict:
    {"not_advice": True, "research_only": True, "not_registered_adviser": True}

The vocabulary is locked: STRONG_BULLISH / BULLISH / NEUTRAL / WATCH / WEAKENING /
NEGATIVE_EVENT / BEARISH_WATCH / RISK_ALERT. There is no SELL or SHORT.
"""
from yuclaw_py._client import Client
from yuclaw_py._compliance import COMPLIANCE, COMPLIANCE_NOTICE, PUBLIC_LABELS

__version__ = "3.0.0"
__all__ = ["Client", "COMPLIANCE", "COMPLIANCE_NOTICE", "PUBLIC_LABELS"]
