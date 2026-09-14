"""Phase-C prospective protocol — SCHEMA and DEPENDENCY checks on synthetic protocol fixtures (v7 P2).

A runnable Phase-C read requires an explicitly DESIGNATED and REGISTERED protocol record. This module validates
the shape and dependencies of a protocol fixture; it carries NO default scientific threshold constant — the
numeric decision rule is a field of the fixture and may be marked UNRESOLVED. It never shortens a window, tunes on
observed outcomes or performs a read."""
from __future__ import annotations

REQUIRED = ("protocol_id", "status", "populations", "window", "endpoints", "denominator", "missing_session_rule", "statistic", "decision_rule", "stopping_rule", "controls", "prior_observation_disclosure")
STATUSES = ("DRAFT", "DESIGNATED", "REGISTERED")
INTEGRITY_REFERENCES = ("registry-chain-verified", "ledger-continuity-verified")     # replaces the ambiguous "integrity threshold" reference


class PhaseCError(ValueError):
    pass


def validate_protocol(p: dict) -> dict:
    """Returns {'status', 'unresolved': [...], 'runnable': bool, 'problems': [...]}. `runnable` is True only for a
    REGISTERED protocol whose decision rule is fully specified (never a default)."""
    if not isinstance(p, dict):
        raise PhaseCError("protocol: object required")
    problems, unresolved = [], []
    for k in REQUIRED:
        if k not in p:
            problems.append(f"missing {k}")
    if problems:
        return {"status": p.get("status"), "unresolved": [], "runnable": False, "problems": problems}
    if p["status"] not in STATUSES:
        problems.append("status must be DRAFT, DESIGNATED or REGISTERED")
    pops = p["populations"]
    if not isinstance(pops, dict) or not {"phase_c_names", "phase_b_names"} <= set(pops) or not isinstance(pops["phase_c_names"], int) or pops["phase_c_names"] <= 0:
        problems.append("populations: {phase_c_names: positive int, phase_b_names: int} required")
    w = p["window"]
    if not isinstance(w, dict) or w.get("start_rule") != "fresh-after-registration" or not isinstance(w.get("sessions"), int) or w["sessions"] <= 0:
        problems.append("window: {start_rule: 'fresh-after-registration', sessions: positive int} required (no window shortening)")
    if not isinstance(p["endpoints"], list) or not p["endpoints"] or any(not isinstance(e, dict) or not e.get("id") or e.get("kind") not in ("primary", "secondary") for e in p["endpoints"]):
        problems.append("endpoints: non-empty list of {id, kind: primary|secondary}")
    d = p["denominator"]
    if not isinstance(d, dict) or d.get("basis") not in ("enrolled-sessions", "completed-sessions") or not isinstance(d.get("fixed_n"), int) or d["fixed_n"] <= 0:
        problems.append("denominator: {basis, fixed_n: positive int} required")
    if p["missing_session_rule"] not in ("count-as-failure", "report-separately"):
        problems.append("missing_session_rule: count-as-failure | report-separately")
    st = p["statistic"]
    if not isinstance(st, dict) or not st.get("id") or not st.get("definition"):
        problems.append("statistic: {id, definition} required")
    dr = p["decision_rule"]
    if dr == "UNRESOLVED":
        unresolved.append("decision_rule (needs architectural input; no default is supplied by the software)")
    elif not isinstance(dr, dict) or not isinstance(dr.get("threshold"), (int, float)) or isinstance(dr.get("threshold"), bool) or not dr.get("comparison") in (">=", "<=") or not dr.get("rationale"):
        problems.append("decision_rule: UNRESOLVED or {threshold: number, comparison: >=|<=, rationale: text}")
    sr = p["stopping_rule"]
    if not isinstance(sr, dict) or sr.get("kind") not in ("fixed-window", "sequential-registered") or not sr.get("text"):
        problems.append("stopping_rule: {kind: fixed-window|sequential-registered, text}")
    if not isinstance(p["controls"], list) or not p["controls"]:
        problems.append("controls: non-empty list")
    pod = p["prior_observation_disclosure"]
    if not isinstance(pod, dict) or pod.get("disclosed") is not True or not pod.get("text"):
        problems.append("prior_observation_disclosure: {disclosed: true, text}")
    ir = p.get("integrity_reference")
    if ir is not None and ir not in INTEGRITY_REFERENCES:
        problems.append(f"integrity_reference must be one of {list(INTEGRITY_REFERENCES)} (the former 'integrity threshold' wording is ambiguous)")
    runnable = not problems and not unresolved and p["status"] == "REGISTERED" and p.get("registration", {}).get("registered_at") is not None
    return {"status": p["status"], "unresolved": unresolved, "runnable": runnable, "problems": problems,
            "note": "runnable only when REGISTERED with a fully specified decision rule; drafts and designations never run a read"}
