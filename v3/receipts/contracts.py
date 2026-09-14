"""Typed, validated contracts for the receipt engine (v7, contract `receipt-1`).

Four record kinds stay distinct even though they share this module:
  * SUBMISSION   — what a participant sent (an attempt). It may DESCRIBE an outcome; it can never
                   award itself qualification, verification, relationship approval or authority.
  * OBSERVATION  — what the verifier established from ACTUAL bytes (type, sha256, byte length).
  * REVIEW       — a decision by a separately authorized reviewer, bound to an exact receipt digest
                   and policy version (see store.py; never accepted from a submission).
  * PUBLIC       — a fresh object built from an explicit typed shape (export.py); never a filtered
                   copy of the input.
Registered vocabularies are closed. Unknown values are errors, never defaults.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta, timezone

SCHEMA_VERSION = "receipt-1"
LEGACY_VERSION = "legacy-0"
POLICY_VERSION = "receipt-policy-candidate-2026-09"      # candidate; adoption pending (owner)
WINDOW_DAYS = 28                                         # candidate fixed window, UTC days

ARTIFACT_TYPES = ("wheel", "sdist", "bundle", "site-page", "chain-line", "json-endpoint")
PACKAGE_ARTIFACTS = ("wheel", "sdist")                   # only these are package reproductions
RELATIONSHIPS = ("OWNER-AFFILIATED", "RELATED-DISCLOSED", "UNRELATED", "UNKNOWN")
EXEC_CONTROL = ("SELF", "ASSISTED", "OPERATOR-RUN")
ASSISTANCE = ("NONE", "PUBLIC-DOCS-ONLY", "DOCUMENTED-FALLBACK", "LIVE-HELP", "OTHER-DISCLOSED")
OUTCOMES = ("REPRODUCED", "FAILED", "INCONCLUSIVE")
REVIEW_STATES = ("RECEIVED", "HELD", "QUALIFIED", "DISQUALIFIED")
BINDING = ("FULL", "PREFIX_ONLY", "UNVERIFIED", "NONE")
REVIEW_AUTHORITIES = ("DESIGNATED", "SYNTHETIC", "HELD", "NONE")   # HELD = legacy/ambiguous appointment awaiting explicit designation
OBSERVATION_SOURCES = ("bytes", "path", "unavailable")
NON_QUALIFYING_RELATIONSHIPS = ("OWNER-AFFILIATED", "UNKNOWN")
ENV_OS_MAX, ENV_PY_MAX, ID_MAX, TAG_MAX = 64, 32, 128, 64

# Fields a submission may carry but which are NEVER trusted: stripped at import with a diagnostic.
FORGEABLE = ("review", "binding_completeness", "qualified", "successful", "verified", "relationship_approved",
             "reviewer", "reviewer_authority", "synthetic", "provenance", "pseudonym", "derived", "window_index")

_TS = "%Y-%m-%dT%H:%M:%S.%fZ"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_PRINTABLE = re.compile(r"^[\x20-\x7e]*$")


class ContractError(ValueError):
    """Explicit contract violation. Never a silent default."""


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(obj) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def parse_ts(s, field: str) -> datetime:
    if not isinstance(s, str):
        raise ContractError(f"{field}: RFC3339 UTC timestamp with microseconds required")
    try:
        return datetime.strptime(s, _TS).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ContractError(f"{field}: not '{_TS}' UTC: {s!r}") from exc


def format_ts(dt: datetime) -> str:
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ContractError("timestamps must be aware UTC")
    return dt.strftime(_TS)


def _str(v, field, maxlen, pat=None):
    if not isinstance(v, str) or not v or len(v) > maxlen:
        raise ContractError(f"{field}: string of 1..{maxlen} chars required")
    if pat and not pat.match(v):
        raise ContractError(f"{field}: value has an unregistered shape: {v!r}")
    return v


def _enum(v, field, allowed):
    if v not in allowed:
        raise ContractError(f"{field}: {v!r} not in {list(allowed)}")
    return v


def _bool(v, field):
    if not isinstance(v, bool):
        raise ContractError(f"{field}: bool required")
    return v


def _nonneg_int(v, field):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ContractError(f"{field}: nonnegative integer required (booleans rejected)")
    return v


def validate_binding_claim(b, field="artifact_binding") -> dict:
    """The participant's CLAIM about the artifact (type, sha256, size). Structural only — not verification."""
    if not isinstance(b, dict):
        raise ContractError(f"{field}: object required")
    extra = set(b) - {"artifact_type", "sha256", "size_bytes"}
    if extra:
        raise ContractError(f"{field}: unexpected keys {sorted(extra)}")
    t = _enum(b.get("artifact_type"), f"{field}.artifact_type", ARTIFACT_TYPES)
    h = b.get("sha256")
    if not isinstance(h, str) or not _HEX64.match(h):
        raise ContractError(f"{field}.sha256: 64 lowercase hex required (prefixes/uppercase rejected)")
    n = _nonneg_int(b.get("size_bytes"), f"{field}.size_bytes")
    return {"artifact_type": t, "sha256": h, "size_bytes": n}


def validate_release_identity(r) -> dict | None:
    if r is None:
        return None
    if not isinstance(r, dict) or set(r) - {"tag", "source_sha"}:
        raise ContractError("release_identity: {tag, source_sha} or null")
    tag = _str(r.get("tag"), "release_identity.tag", TAG_MAX, _TAG)
    sha = r.get("source_sha")
    if not isinstance(sha, str) or not _SHA40.match(sha):
        raise ContractError("release_identity.source_sha: 40 lowercase hex required")
    return {"tag": tag, "source_sha": sha}


def validate_environment(e) -> dict:
    """Permitted environment fields are bounded printable scalars. Nested values are errors."""
    if e is None:
        return {}
    if not isinstance(e, dict):
        raise ContractError("environment: object required")
    out = {}
    for k in ("os", "python"):
        if k in e:
            v = e[k]
            if not isinstance(v, str):
                raise ContractError(f"environment.{k}: string required (nested/non-scalar values rejected)")
            if not _PRINTABLE.match(v) or len(v) > (ENV_OS_MAX if k == "os" else ENV_PY_MAX) or not v.strip():
                raise ContractError(f"environment.{k}: bounded printable ASCII required")
            out[k] = v.strip()
    extra = set(e) - {"os", "python", "arch"}
    if extra:
        raise ContractError(f"environment: unexpected keys {sorted(extra)} (only os, python, arch)")
    if "arch" in e and not (isinstance(e["arch"], str) and _PRINTABLE.match(e["arch"]) and len(e["arch"]) <= 32):
        raise ContractError("environment.arch: bounded printable ASCII required")
    if "arch" in e:
        out["arch"] = e["arch"]          # private (not exported)
    return out


def validate_submission(raw: dict) -> tuple[dict, list[str]]:
    """Validate a SUBMISSION. Returns (clean_submission, diagnostics). Forgeable/derived assertions are
    stripped and reported — they never become state. Raises ContractError on any invalid field."""
    if not isinstance(raw, dict):
        raise ContractError("submission: object required")
    diagnostics = []
    src = dict(raw)
    for f in FORGEABLE:
        if f in src:
            diagnostics.append(f"ignored forgeable field {f!r} (participant assertions are not state)")
            src.pop(f)
    if src.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"schema_version must be {SCHEMA_VERSION!r}")
    sub = {"schema_version": SCHEMA_VERSION}
    for k in ("attempt_id", "activity_id", "participant_id", "protocol_id"):
        sub[k] = _str(src.get(k), k, ID_MAX, _ID)
    g = src.get("group_id")
    sub["group_id"] = None if g is None else _str(g, "group_id", ID_MAX, _ID)
    sub["relationship"] = _enum(src.get("relationship"), "relationship", RELATIONSHIPS)
    sub["execution_control"] = _enum(src.get("execution_control"), "execution_control", EXEC_CONTROL)
    sub["assistance"] = _enum(src.get("assistance"), "assistance", ASSISTANCE)
    if sub["execution_control"] == "ASSISTED" and sub["assistance"] == "NONE":
        raise ContractError("execution_control ASSISTED requires disclosed assistance")
    sub["incentive_outcome_dependent"] = _bool(src.get("incentive_outcome_dependent"), "incentive_outcome_dependent")
    sub["outcome"] = _enum(src.get("outcome"), "outcome", OUTCOMES)
    obs = parse_ts(src.get("observed_at"), "observed_at")
    sub["observed_at"] = format_ts(obs)
    sub["artifact_binding"] = validate_binding_claim(src.get("artifact_binding"))
    sub["release_identity"] = validate_release_identity(src.get("release_identity"))
    sub["environment"] = validate_environment(src.get("environment"))
    lim = src.get("limitations", [])
    if not isinstance(lim, list) or any(not isinstance(x, str) or len(x) > 500 for x in lim) or len(lim) > 20:
        raise ContractError("limitations: list of ≤20 strings (≤500 chars)")
    sub["limitations"] = list(lim)                  # private by default
    priv = src.get("private", {})
    if priv is not None and not isinstance(priv, dict):
        raise ContractError("private: object or null")
    sub["private"] = dict(priv or {})               # never exported
    sup = src.get("supersedes")
    if sup is not None:
        if not isinstance(sup, dict) or not (isinstance(sup.get("digest"), str) and _HEX64.match(sup["digest"])) or not isinstance(sup.get("reason"), str) or not sup["reason"].strip():
            raise ContractError("supersedes: {digest: sha256, reason: text} required for a correction")
        sub["supersedes"] = {"digest": sup["digest"], "reason": sup["reason"][:500]}
    else:
        sub["supersedes"] = None
    note = src.get("public_note")
    if note is not None and (not isinstance(note, str) or len(note) > 280 or not _PRINTABLE.match(note)):
        raise ContractError("public_note: ≤280 printable ASCII chars or null")
    sub["public_note"] = note
    sub["disclosure_permitted"] = _bool(src.get("disclosure_permitted", False), "disclosure_permitted")
    known = {"schema_version", "attempt_id", "activity_id", "participant_id", "protocol_id", "group_id", "relationship", "execution_control",
             "assistance", "incentive_outcome_dependent", "outcome", "observed_at", "artifact_binding", "release_identity", "environment",
             "limitations", "private", "supersedes", "public_note", "disclosure_permitted"}
    unknown = set(src) - known
    if unknown:
        raise ContractError(f"submission: unexpected fields {sorted(unknown)}")
    return sub, diagnostics


def window_index(observed: datetime, anchor: date) -> int:
    d = (observed.date() - anchor).days
    if d < 0:
        raise ContractError(f"observed_at {observed.date()} precedes registration anchor {anchor}")
    return d // WINDOW_DAYS


def finite_number(v, field):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (isinstance(v, float) and not math.isfinite(v)):
        raise ContractError(f"{field}: finite number required")
    return v


def validate_observation(obs, claim: dict) -> dict:
    """An OBSERVATION as stored must (a) concern exactly the receipt's claimed artifact, (b) carry
    observed values of the right types, and (c) have `verified` equal to the recomputed equality of
    observed and claimed sha256 + length. Anything else is rejected — a caller cannot mark FULL."""
    if not isinstance(obs, dict):
        raise ContractError("observation: object required")
    want = {"artifact_type", "claimed_sha256", "claimed_size_bytes", "observed_sha256", "observed_size_bytes", "verified", "source", "observed_at"}
    if set(obs) != want:
        raise ContractError(f"observation: keys must be exactly {sorted(want)}")
    c = validate_binding_claim(claim)
    if (obs["artifact_type"], obs["claimed_sha256"], obs["claimed_size_bytes"]) != (c["artifact_type"], c["sha256"], c["size_bytes"]):
        raise ContractError("observation is for a different artifact than the receipt's binding")
    oh, on = obs["observed_sha256"], obs["observed_size_bytes"]
    if oh is not None and (not isinstance(oh, str) or not _HEX64.match(oh)):
        raise ContractError("observation.observed_sha256: 64 lowercase hex or null")
    if on is not None:
        _nonneg_int(on, "observation.observed_size_bytes")
    if (oh is None) != (on is None):
        raise ContractError("observation: observed sha256 and size must both be present or both null")
    _enum(obs["source"], "observation.source", OBSERVATION_SOURCES)
    if obs["source"] == "unavailable" and oh is not None:
        raise ContractError("observation: source 'unavailable' cannot carry observed values")
    parse_ts(obs["observed_at"], "observation.observed_at")
    recomputed = oh is not None and oh == c["sha256"] and on == c["size_bytes"]
    if not isinstance(obs["verified"], bool) or obs["verified"] != recomputed:
        raise ContractError("observation.verified is inconsistent with the observed values (forged or corrupted observation)")
    return {k: obs[k] for k in sorted(want)}


def validate_registration(reg) -> dict:
    """A registration record is the OWNER's adoption of a prospective program: protocol id, the window
    anchor (UTC date), the actual registration instant (RFC3339 UTC, microseconds) and the policy
    version it binds. A supplied anchor alone is never evidence of adoption. The anchor may not precede
    the registration instant's UTC date (no retrospective windows)."""
    if not isinstance(reg, dict):
        raise ContractError("registration: object required")
    want = {"protocol_id", "anchor", "registered_at", "policy_version"}
    if set(reg) - want:
        raise ContractError(f"registration: unexpected keys {sorted(set(reg) - want)}")
    if set(reg) != want:
        raise ContractError(f"registration: keys must be exactly {sorted(want)} (a supplied anchor alone is not evidence of adoption)")
    pid = _str(reg["protocol_id"], "registration.protocol_id", ID_MAX, _ID)
    try:
        anchor = date.fromisoformat(reg["anchor"]) if isinstance(reg["anchor"], str) else None
    except ValueError:
        anchor = None
    if anchor is None:
        raise ContractError("registration.anchor: YYYY-MM-DD UTC date required")
    registered_at = parse_ts(reg["registered_at"], "registration.registered_at")
    if anchor < registered_at.date():
        raise ContractError("registration.anchor precedes the registration instant (retrospective windows are refused)")
    if reg["policy_version"] != POLICY_VERSION:
        raise ContractError(f"registration.policy_version {reg['policy_version']!r} != engine policy {POLICY_VERSION!r}")
    return {"protocol_id": pid, "anchor": anchor.isoformat(), "registered_at": format_ts(registered_at), "policy_version": POLICY_VERSION}
