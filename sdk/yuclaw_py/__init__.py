"""
yuclaw-py — Python SDK for the YUCLAW research platform.

Public surface:
    Client(source="postgres"|"api", dsn=..., base_url=...)
        .signal(ticker)
        .why(ticker)
        .replay(ticker, date)
        .backtest()
        .events(ticker, since=None)
        .universe()

All signal-bearing returns include a `compliance` dict:
    {"not_advice": True, "research_only": True, "not_registered_adviser": True}

The vocabulary is locked: STRONG_BUY / BUY / HOLD / WATCH / WEAKENING /
NEGATIVE_EVENT / DOWNSIDE_WATCH / RISK_ALERT. There is no SELL or SHORT.
"""
from yuclaw_py._client import Client
from yuclaw_py._compliance import COMPLIANCE, COMPLIANCE_NOTICE, PUBLIC_LABELS

__version__ = "3.0.0"
__all__ = ["Client", "COMPLIANCE", "COMPLIANCE_NOTICE", "PUBLIC_LABELS"]
