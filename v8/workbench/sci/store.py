"""Replay and report over a hash-chained science event journal (adapted from the preview; V8-005).

Adaptation notes: the preview's SQLite `Journal` (local database file, append-only triggers) and its clock are NOT
adapted — the workbench never opens caller-supplied database files and persists its replays in the workspace's own
append-only journal instead. `replay()` and the report (`certificate()` in the preview; `report()` here, same content
except the not-advice sentence names a report rather than a certificate) are unchanged in semantics. `build_events()`
is a pure in-memory builder that applies exactly the reducer rules the preview's `Journal.append` applied, so fixtures
and tests can construct valid journals without a database file.
"""
from __future__ import annotations

import math

from . import SCHEMA_VERSION
from .contracts import canonical, exact_keys, reduce_event, sha256, timestamp

GENESIS = sha256({"schema": SCHEMA_VERSION, "genesis": "local-science-journal"})
EVENT_KEYS = ("sequence", "kind", "payload", "recorded_at", "previous_hash", "event_hash")


def replay(events, expected_root=None):
    state, tip, previous_time = None, GENESIS, None
    for seq, event in enumerate(events, start=1):
        exact_keys(event, EVENT_KEYS)
        body = {k: v for k, v in event.items() if k != "event_hash"}
        if type(event["sequence"]) is not int or event["sequence"] != seq or event["previous_hash"] != tip or sha256(body) != event["event_hash"]:
            raise ValueError(f"journal integrity failure at event {seq}")
        now = timestamp(event["recorded_at"])
        if previous_time is not None and now < previous_time:
            raise ValueError("journal clock moved backwards")
        state = reduce_event(state, event["kind"], event["payload"], event["recorded_at"])
        previous_time, tip = now, event["event_hash"]
    if state is None:
        raise ValueError("empty journal is not a registered experiment")
    if expected_root is not None and tip != expected_root:
        raise ValueError("journal root differs from expected checkpoint (including possible truncation)")
    return state, tip


def report(events, expected_root=None):
    state, tip = replay(events, expected_root)
    manifest = state["manifest"]
    claims = []
    for cid, c in state["claims"].items():
        contract = c["contract"]
        passed = c["max_log_e"] >= -math.log(contract["alpha"])
        pending = [uid for uid, u in c["units"].items() if "outcome" not in u]
        ready = passed and c["n"] >= contract["min_units"] and not pending
        if c["invalidated"]:
            status = "INVALIDATED"
        elif manifest["mode"] == "exploratory":
            status = "EXPLORATORY_ONLY"
        elif ready:
            status = "CONDITIONAL_EVIDENCE"
        elif c["n"] == contract["max_units"]:
            status = "BUDGET_EXHAUSTED_INCONCLUSIVE"
        else:
            status = "AWAITING_OUTCOME" if pending else "ACCUMULATING"
        claims.append({"claim_id": cid, "question": contract["question"], "status": status,
                       "contract": contract, "resolved_units": c["n"], "pending_units": pending,
                       "mean_brier_improvement": c["total"] / c["n"] if c["n"] else None,
                       "current_log_e": c["current_log_e"], "max_log_e": c["max_log_e"],
                       "anytime_p_bound": math.exp(-c["max_log_e"]),
                       "threshold_crossed": passed, "invalidated_reason": c["invalidated"],
                       "permission": "RESEARCH_REVIEW_ONLY"})
    return {"schema": SCHEMA_VERSION, "family_id": manifest["family_id"], "mode": manifest["mode"],
            "registered_at": state["registered_at"], "family_alpha": manifest["family_alpha"],
            "claims": claims, "event_count": len(events), "root_hash": tip,
            "checkpoint_matches": expected_root is not None,
            "anchor_status": "LOCAL_ONLY_EXTERNAL_TIMESTAMP_NOT_VERIFIED",
            "scope": "Familywise error control for this frozen family only, conditional on valid prospective data and conditional-mean nulls. Independent families/reruns are not automatically covered.",
            "limitations": ["Hashes establish record consistency, not source truth or timestamp authenticity.",
                            "A valid-looking hash does not authenticate an adjudicator or establish that an outcome was unknown when the prediction was recorded.",
                            "Repeated source hashes are blocked; hidden dependence or renamed copies require external audit.",
                            "Conditional evidence is not a probability the claim is true, a causal effect, or forward alpha.",
                            "Deleting/rebuilding a whole local journal is detectable only against a separately retained checkpoint."],
            "not_advice": "Research and education only — not investment advice. No trade or deployment is authorized by this report."}



def build_events(steps, clock):
    """Pure in-memory journal builder: steps = [(kind, payload), ...]; clock() returns the recorded_at for each event.
    Applies exactly the reducer rules (validate before append; NaN refused by canonical()); returns the event list."""
    events, state, tip = [], None, GENESIS
    for kind, payload in steps:
        at = clock()
        now = timestamp(at)
        if events and now < timestamp(events[-1]["recorded_at"]):
            raise ValueError("journal clock moved backwards")
        payload = __import__("json").loads(canonical(payload))
        state = reduce_event(state, kind, payload, at)
        body = {"sequence": len(events) + 1, "kind": kind, "payload": payload, "recorded_at": at, "previous_hash": tip}
        event = dict(body, event_hash=sha256(body)); events.append(event); tip = event["event_hash"]
    return events
