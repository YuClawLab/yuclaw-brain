"""Strict contracts and a pure event-state reducer shared by replay and report (adapted from the preview; V8-005).

Adaptation notes: identical validation rules and reducer semantics; error messages are unchanged so the adapted core
tests still match them. `canonical()` refuses NaN/Infinity (allow_nan=False) exactly as the preview did.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from . import SCHEMA_VERSION
from .statistics import brier_improvement, finite, log_e_value


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha256(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string with timezone")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("timestamp must be an ISO string with timezone") from None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamp requires an explicit timezone")
    return dt.astimezone(timezone.utc)


def exact_keys(doc, required):
    if not isinstance(doc, dict) or set(doc) != set(required):
        raise ValueError(f"expected exactly these fields: {', '.join(sorted(required))}")


def text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 10000:
        raise ValueError(f"{name} must be a nonempty string of at most 10000 characters")
    return value


def content_hash(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("artifact hashes must be lowercase SHA-256 (64 hex characters)")
    return value


def validate_manifest(doc):
    exact_keys(doc, ("schema", "family_id", "mode", "family_alpha", "claims"))
    if doc["schema"] != SCHEMA_VERSION or doc["mode"] not in ("prospective", "exploratory"):
        raise ValueError("unsupported schema or mode")
    text(doc["family_id"], "family_id")
    alpha = finite(doc["family_alpha"], "family_alpha", 0, 0.1)
    if alpha <= 0 or not isinstance(doc["claims"], list) or not 1 <= len(doc["claims"]) <= 100:
        raise ValueError("positive alpha and 1..100 claims required")
    ids = set()
    for c in doc["claims"]:
        exact_keys(c, ("claim_id", "question", "population", "unit_definition", "assumptions", "metric",
                       "baseline_hash", "candidate_hash", "alpha", "minimum_effect", "min_units", "max_units"))
        for name in ("claim_id", "question", "population", "unit_definition"):
            text(c[name], name)
        if c["claim_id"] in ids:
            raise ValueError("duplicate claim_id")
        ids.add(c["claim_id"])
        if c["metric"] != "paired_brier_improvement":
            raise ValueError("v8 supports paired_brier_improvement only; scores/returns are not probabilities")
        for name in ("baseline_hash", "candidate_hash"):
            content_hash(c[name])
        if c["baseline_hash"] == c["candidate_hash"]:
            raise ValueError("baseline and candidate artifacts must differ")
        finite(c["minimum_effect"], "minimum_effect", 0, 0.99)
        value = finite(c["alpha"], "claim alpha", 0, alpha)
        if value <= 0:
            raise ValueError("claim alpha must be positive")
        if not isinstance(c["assumptions"], list) or not c["assumptions"]:
            raise ValueError("explicit statistical and adjudication assumptions required")
        for assumption in c["assumptions"]:
            text(assumption, "assumption")
        if any(type(c[k]) is not int for k in ("min_units", "max_units")) or not 1 <= c["min_units"] <= c["max_units"] <= 100000:
            raise ValueError("require 1 <= min_units <= max_units <= 100000")
    # No tolerance that silently overspends a family budget.
    from decimal import Decimal
    if sum(Decimal(str(c["alpha"])) for c in doc["claims"]) > Decimal(str(alpha)):
        raise ValueError("claim allocations exceed family_alpha")
    return doc


def initial_state(manifest, registered_at):
    validate_manifest(manifest)
    timestamp(registered_at)
    return {"manifest": manifest, "registered_at": registered_at, "claims": {
        c["claim_id"]: {"contract": c, "units": {}, "resolved": [], "source_hashes": [],
                         "invalidated": None, "n": 0, "total": 0.0, "max_log_e": 0.0,
                         "current_log_e": 0.0, "last_resolved_at": registered_at}
        for c in manifest["claims"]}}


def reduce_event(state, kind, p, recorded_at):
    """Validate an event before mutation; replay uses exactly the same rules."""
    now = timestamp(recorded_at)
    if kind == "register":
        if state is not None:
            raise ValueError("family already registered")
        return initial_state(p, recorded_at)
    if state is None or kind not in ("predict", "resolve", "invalidate"):
        raise ValueError("unknown event or unregistered family")
    if not isinstance(p, dict) or p.get("claim_id") not in state["claims"]:
        raise ValueError("unknown claim_id")
    c = state["claims"][p["claim_id"]]
    if c["invalidated"] is not None:
        raise ValueError("claim invalidated; retain it and register a new experiment")
    if now < timestamp(c["last_resolved_at"]):
        raise ValueError("event time moved backwards")
    if kind == "invalidate":
        exact_keys(p, ("claim_id", "reason"))
        text(p["reason"], "reason")
        c["invalidated"] = p["reason"]
        return state
    if kind == "predict":
        exact_keys(p, ("claim_id", "unit_id", "baseline_probability", "candidate_probability",
                       "source_hashes", "outcome_not_before"))
        text(p["unit_id"], "unit_id")
        if p["unit_id"] in c["units"] or len(c["units"]) >= c["contract"]["max_units"]:
            raise ValueError("duplicate unit or preregistered sample budget exhausted")
        if any("outcome" not in u for u in c["units"].values()):
            raise ValueError("resolve the pending unit first; outcome-based skipping is forbidden")
        if timestamp(p["outcome_not_before"]) <= now:
            raise ValueError("outcome_not_before must be strictly after prediction registration")
        finite(p["baseline_probability"], "baseline_probability", 0, 1)
        finite(p["candidate_probability"], "candidate_probability", 0, 1)
        hashes = p["source_hashes"]
        if not isinstance(hashes, list) or not 1 <= len(hashes) <= 100:
            raise ValueError("1..100 source hashes required")
        for h in hashes:
            content_hash(h)
        if len(set(hashes)) != len(hashes) or set(hashes).intersection(c["source_hashes"]):
            raise ValueError("reused source evidence within the claim; group dependent copies into one unit")
        c["source_hashes"].extend(hashes)
        c["units"][p["unit_id"]] = dict(p, predicted_at=recorded_at)
    elif kind == "resolve":
        exact_keys(p, ("claim_id", "unit_id", "outcome", "adjudication_hash"))
        content_hash(p["adjudication_hash"])
        u = c["units"].get(p["unit_id"])
        if u is None or "outcome" in u:
            raise ValueError("unknown or already resolved unit")
        if now < timestamp(u["outcome_not_before"]):
            raise ValueError("outcome has not matured")
        gain = brier_improvement(u["baseline_probability"], u["candidate_probability"], p["outcome"])
        u.update(p, resolved_at=recorded_at, improvement=gain)
        c["resolved"].append(p["unit_id"])
        c["n"] += 1
        c["total"] += gain
        c["current_log_e"] = log_e_value(c["n"], c["total"], c["contract"]["minimum_effect"])
        c["max_log_e"] = max(c["max_log_e"], c["current_log_e"])
        c["last_resolved_at"] = recorded_at
    return state
