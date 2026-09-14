"""ETF class membership — candidate schema/admission validation (v7). NOT an addendum: the registered
completeness method's `etf` class exists with ETF_SET empty in-hash; membership requires a registered
addendum. This module validates a PROPOSED addendum payload and classifies names without touching the
registered set or historical statuses. NOT_APPLICABLE (family not expected for the class) and
BLOCKED_BY_REGISTRATION (membership needs a registered addendum) remain distinct outcomes."""
from __future__ import annotations

import re

STATUSES = ("NOT_APPLICABLE", "BLOCKED_BY_REGISTRATION", "MEMBER", "NOT_MEMBER")
_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
ETF_SET_AT_REGISTRATION: frozenset = frozenset()          # in-hash value; never mutated here


def validate_addendum(payload: dict) -> list[str]:
    """Return problems for a proposed ETF-class addendum (registered addendum text is the authority)."""
    problems = []
    for k in ("addendum_id", "parent_protocol_id", "class", "members", "rationale", "families_expected"):
        if k not in payload:
            problems.append(f"missing {k}")
    if payload.get("class") != "etf":
        problems.append("class must be 'etf'")
    members = payload.get("members", [])
    if not isinstance(members, list) or not members:
        problems.append("members: non-empty list required")
    else:
        bad = [m for m in members if not isinstance(m, str) or not _TICKER.match(m)]
        if bad: problems.append(f"members: malformed tickers {bad}")
        if len(set(members)) != len(members): problems.append("members: duplicates")
    fam = payload.get("families_expected", None)
    if not isinstance(fam, dict) or not fam:
        problems.append("families_expected: {family: bool} required (NOT_APPLICABLE derives from it)")
    return problems


def classify(ticker: str, family: str, *, registered_members: frozenset = ETF_SET_AT_REGISTRATION, families_expected: dict | None = None) -> str:
    """Membership/family status for one name under the REGISTERED set (empty today)."""
    if families_expected is not None and families_expected.get(family) is False:
        return "NOT_APPLICABLE"
    if not registered_members:
        return "BLOCKED_BY_REGISTRATION"
    return "MEMBER" if ticker in registered_members else "NOT_MEMBER"
