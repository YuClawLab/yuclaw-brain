"""ETF class membership — candidate schema/admission validation and an ADDENDUM-DRIVEN classification path (v7).
NOT an addendum: the registered completeness method's `etf` class exists with ETF_SET empty in-hash; membership
requires a registered addendum. This module validates a PROPOSED addendum payload (with provenance and a
correction chain), derives a PROPOSED classification from it without touching the registered set or historical
statuses, and keeps NOT_APPLICABLE (family not expected for the class) distinct from BLOCKED_BY_REGISTRATION
(membership needs a registered addendum) and from PROPOSED_MEMBER (proposed by an unregistered addendum)."""
from __future__ import annotations

import hashlib
import json
import re

STATUSES = ("NOT_APPLICABLE", "BLOCKED_BY_REGISTRATION", "MEMBER", "NOT_MEMBER", "PROPOSED_MEMBER", "PROPOSED_NOT_MEMBER")
_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
ETF_SET_AT_REGISTRATION: frozenset = frozenset()          # in-hash value; never mutated here


def validate_addendum(payload: dict) -> list[str]:
    """Return problems for a proposed ETF-class addendum (registered addendum text is the authority)."""
    problems = []
    if not isinstance(payload, dict):
        return ["payload: object required"]
    for k in ("addendum_id", "parent_protocol_id", "class", "members", "rationale", "families_expected"):
        if k not in payload:
            problems.append(f"missing {k}")
    if payload.get("class") != "etf":
        problems.append("class must be 'etf'")
    for k in ("addendum_id", "parent_protocol_id"):
        if k in payload and not (isinstance(payload[k], str) and _ID.match(payload[k])):
            problems.append(f"{k}: registered id shape required")
    members = payload.get("members", [])
    if not isinstance(members, list) or not members:
        problems.append("members: non-empty list required")
    else:
        bad = [m for m in members if not isinstance(m, str) or not _TICKER.match(m)]
        if bad: problems.append(f"members: malformed tickers {bad}")
        if len(set(members)) != len(members): problems.append("members: duplicates")
    fam = payload.get("families_expected", None)
    if not isinstance(fam, dict) or not fam or not all(isinstance(v, bool) for v in fam.values()):
        problems.append("families_expected: {family: bool} required (NOT_APPLICABLE derives from it)")
    if not isinstance(payload.get("rationale", ""), str) or not str(payload.get("rationale", "")).strip():
        problems.append("rationale: non-empty text required")
    sup = payload.get("supersedes")
    if sup is not None:
        if not isinstance(sup, dict) or not (isinstance(sup.get("addendum_sha256"), str) and _HEX64.match(sup["addendum_sha256"])) or not isinstance(sup.get("reason"), str) or not sup["reason"].strip():
            problems.append("supersedes: {addendum_sha256, reason} required for a correction")
    extra = set(payload) - {"addendum_id", "parent_protocol_id", "class", "members", "rationale", "families_expected", "supersedes", "status"}
    if extra:
        problems.append(f"unexpected keys {sorted(extra)}")
    if payload.get("status") not in (None, "PROPOSED"):
        problems.append("status: only PROPOSED is accepted from a payload (REGISTERED is set by registration, never by a payload)")
    return problems


def addendum_sha256(payload: dict) -> str:
    return hashlib.sha256(json.dumps({k: payload[k] for k in sorted(payload) if k != "status"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def apply_addendum(payload: dict, *, prior: dict | None = None) -> dict:
    """Derive a PROPOSED classification set from a validated addendum payload. `prior` = the classification it
    corrects (its `supersedes.addendum_sha256` must equal the prior payload digest); the prior is retained in the
    chain, never erased. Status is PROPOSED — registration is a separate act and never happens here."""
    problems = validate_addendum(payload)
    if problems:
        raise ValueError("addendum invalid: " + "; ".join(problems))
    digest = addendum_sha256(payload)
    chain = []
    if payload.get("supersedes") is not None:
        if prior is None or prior["addendum_sha256"] != payload["supersedes"]["addendum_sha256"]:
            raise ValueError("correction must supersede the exact prior addendum (digest mismatch or prior missing)")
        chain = prior["chain"] + [prior["addendum_sha256"]]
    elif prior is not None:
        raise ValueError("a new addendum for the same class must state supersedes when a prior proposal exists")
    return {"status": "PROPOSED", "addendum_id": payload["addendum_id"], "parent_protocol_id": payload["parent_protocol_id"], "addendum_sha256": digest,
            "members": frozenset(payload["members"]), "families_expected": dict(payload["families_expected"]), "chain": chain,
            "provenance": {"source": "proposed addendum payload", "registered": False, "registered_set_in_hash": sorted(ETF_SET_AT_REGISTRATION)}}


def classify(ticker: str, family: str, *, registered_members: frozenset = ETF_SET_AT_REGISTRATION, families_expected: dict | None = None, proposed: dict | None = None) -> str:
    """Membership/family status for one name. Registered set (empty today) governs MEMBER/NOT_MEMBER; a proposed
    addendum yields PROPOSED_* only; NOT_APPLICABLE and BLOCKED_BY_REGISTRATION stay distinct."""
    fe = families_expected if families_expected is not None else (proposed or {}).get("families_expected")
    if fe is not None and fe.get(family) is False:
        return "NOT_APPLICABLE"
    if registered_members:
        return "MEMBER" if ticker in registered_members else "NOT_MEMBER"
    if proposed is not None:
        return "PROPOSED_MEMBER" if ticker in proposed["members"] else "PROPOSED_NOT_MEMBER"
    return "BLOCKED_BY_REGISTRATION"


def classify_all(names: list[tuple[str, str]], **kw) -> dict:
    out = {}
    for t, fam in names:
        out.setdefault(classify(t, fam, **kw), []).append(t)
    return {k: sorted(v) for k, v in sorted(out.items())}
