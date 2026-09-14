"""Deterministic Gate #15 study evaluator and gate-evidence adapter (V5). Input: reviewer decision FORMS
(private JSON). Output: per-session results, per-mode aggregates over the fixed denominator, and — only when
every prerequisite record is present — a gate input. Nothing here creates results; it scores forms."""
from __future__ import annotations

from v3.study import gate15_schema as S


class FormError(ValueError):
    pass


def score_task(t: dict) -> dict:
    task = t.get("task")
    if task not in S.TASKS:
        raise FormError("unknown task")
    spec = S.TASKS[task]
    for k in S.TASK_FORM_FIELDS:
        if k not in t:
            raise FormError(f"task {task}: missing form field {k}")
    if not isinstance(t["completed"], bool) or not isinstance(t["minutes"], (int, float)) or isinstance(t["minutes"], bool):
        raise FormError(f"task {task}: completed/minutes types")
    el, cr = t["elements"], t["critical"]
    if set(el) != set(spec["elements"]) or set(cr) != set(spec["critical"]) or not all(isinstance(v, bool) for v in list(el.values()) + list(cr.values())):
        raise FormError(f"task {task}: every element and critical error must be ticked true/false")
    if not t["completed"] or t["minutes"] > S.TASK_MINUTES:
        result = "INCOMPLETE"                                   # timeout/incomplete never slips through because no critical error was ticked
    elif any(cr.values()):
        result = "FAIL_CRITICAL"
    elif not all(el.values()):
        result = "FAIL_INCOMPLETE"
    else:
        result = "PASS"
    return {"task": task, "result": result, "missing_elements": sorted(k for k, v in el.items() if not v), "critical_errors": sorted(k for k, v in cr.items() if v), "minutes": t["minutes"]}


def score_session(form: dict) -> dict:
    for k in S.FORM_FIELDS:
        if k not in form:
            raise FormError(f"missing form field {k}")
    if form["mode"] not in S.MODES or form["assistance"] not in S.ASSISTANCE or form["wheel_label"] not in S.WHEEL_LABELS or form["relationship"] not in S.RELATIONSHIPS:
        raise FormError("mode/assistance/wheel_label/relationship not registered")
    if form["mode"] == "EXECUTION" and form["wheel_label"] == "NONE":
        raise FormError("EXECUTION mode requires a declared wheel label")
    tasks = form["tasks"]
    if not isinstance(tasks, list):
        raise FormError("tasks: list required")
    if tasks == [] :
        decision = "MISSING"; scored = []
    else:
        scored = [score_task(t) for t in tasks]
        if sorted(s["task"] for s in scored) != sorted(S.TASKS):
            raise FormError("a completed session form carries exactly the five tasks")
        if form["assistance"] == "LIVE_HELP":
            decision = "ASSISTED"                               # assistance precedence
        else:
            decision = "PASS" if all(s["result"] == "PASS" for s in scored) else "FAIL"
    return {"session_code": form["session_code"], "mode": form["mode"], "wheel_label": form["wheel_label"], "materials_manifest_sha256": form["materials_manifest_sha256"],
            "decision": decision, "tasks": scored, "assistance": form["assistance"]}


def aggregate(sessions: list[dict]) -> dict:
    """Per-mode aggregates over the FIXED denominator; modes are never pooled; a shortfall counts as MISSING."""
    out = {}
    for mode in S.MODES:
        rows = [s for s in sessions if s["mode"] == mode]
        if len(rows) > S.DENOMINATOR:
            raise FormError(f"more than {S.DENOMINATOR} sessions in mode {mode} (the denominator is fixed; extra sessions are a protocol violation)")
        manifests = {s["materials_manifest_sha256"] for s in rows}; wheels = {s["wheel_label"] for s in rows}
        counts = {d: sum(1 for s in rows if s["decision"] == d) for d in S.SESSION_DECISIONS}
        counts["MISSING"] += S.DENOMINATOR - len(rows)
        out[mode] = {"n_pass": counts["PASS"], "denominator": S.DENOMINATOR, "counts": counts, "sessions_recorded": len(rows),
                     "materials_manifests": sorted(manifests), "wheel_labels": sorted(wheels), "primary": mode == S.PRIMARY_MODE,
                     "candidate_threshold_met": counts["PASS"] >= S.CANDIDATE_THRESHOLD["pass_sessions"], "threshold_status": S.CANDIDATE_THRESHOLD["status"]}
    return {"protocol_id": S.PROTOCOL_ID, "protocol_status": S.PROTOCOL_STATUS, "by_mode": out, "pooled": "NEVER", "note": "aggregate counts only; no per-session labels are published"}


def gate_evidence(evaluation: dict, *, protocol_adoption: dict | None, applicability: dict | None, reviewer_appointment: dict | None, human_records: bool) -> dict:
    """Gate-evidence adapter: a REAL gate input exists only with an adopted protocol, a documented applicability
    determination, a designated reviewer/actor and actual human records. Otherwise NOT_A_GATE_INPUT with the
    missing prerequisites; the evaluation still describes the tested materials, never an unbuilt future wheel."""
    missing = []
    if not protocol_adoption or protocol_adoption.get("protocol_id") != S.PROTOCOL_ID or protocol_adoption.get("adopted") is not True:
        missing.append("adopted protocol record")
    if not applicability or applicability.get("determination") not in ("no_review_required", "exempt", "approved"):
        missing.append("documented privacy/ethics applicability determination")
    if not reviewer_appointment or reviewer_appointment.get("status") != "DESIGNATED":
        missing.append("designated study reviewer appointment")
    if not human_records:
        missing.append("actual human session records")
    prim = evaluation["by_mode"][S.PRIMARY_MODE]
    coverage = {"materials_manifests": prim["materials_manifests"], "wheel_labels": prim["wheel_labels"], "note": "the result covers exactly the materials/wheel the sessions tested; it does not transfer to a differently hashed artifact"}
    if missing:
        return {"gate_input": "NOT_A_GATE_INPUT", "missing_prerequisites": missing, "gate_15": "MANUAL_REVIEW (unchanged)", "coverage": coverage, "evaluation": evaluation}
    return {"gate_input": "CANDIDATE_GATE_INPUT", "gate_15_proposed": ("GREEN" if prim["candidate_threshold_met"] else "RED"),
            "note": "proposed value only; the release-policy actor records the gate; the candidate threshold is unadopted", "coverage": coverage, "evaluation": evaluation}
