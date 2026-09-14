"""Deterministic Gate #15 study evaluator and gate-evidence adapter (V5 closure). Input: reviewer decision FORMS
(private JSON). Output: per-session results, per-COHORT aggregates over the fixed denominator, and — only when
every prerequisite RECORD validates — a gate input. The software checks records; it never invents a determination,
never pools cohorts, never turns synthetic sessions into real evidence, and never substitutes for a human reviewer."""
from __future__ import annotations

import math
import re

from v3.study import gate15_schema as S

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class FormError(ValueError):
    pass


def _finite_minutes(v) -> bool:
    return not isinstance(v, bool) and isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= S.MAX_TASK_MINUTES_RECORDED


def validate_wheel(w) -> dict:
    if not isinstance(w, dict) or set(w) != set(S.WHEEL_FIELDS):
        raise FormError("wheel: {label, artifact_type, sha256, size_bytes} required")
    if w["label"] not in S.WHEEL_LABELS or w["artifact_type"] not in ("wheel", "none"):
        raise FormError("wheel: label/artifact_type not registered")
    if w["label"] == "NONE":
        if w["artifact_type"] != "none" or w["sha256"] is not None or w["size_bytes"] is not None:
            raise FormError("wheel NONE: artifact_type none with null sha256/size")
        return {"label": "NONE", "artifact_type": "none", "sha256": None, "size_bytes": None}
    if not (isinstance(w["sha256"], str) and _HEX64.match(w["sha256"])) or isinstance(w["size_bytes"], bool) or not isinstance(w["size_bytes"], int) or w["size_bytes"] <= 0:
        raise FormError("wheel: full sha256 and positive byte length required (the label is descriptive, not a binding)")
    return {"label": w["label"], "artifact_type": w["artifact_type"], "sha256": w["sha256"], "size_bytes": w["size_bytes"]}


def score_task(t: dict) -> dict:
    task = t.get("task")
    if task not in S.TASKS:
        raise FormError("unknown task")
    spec = S.TASKS[task]
    for k in S.TASK_FORM_FIELDS:
        if k not in t:
            raise FormError(f"task {task}: missing form field {k}")
    if not isinstance(t["completed"], bool) or not _finite_minutes(t["minutes"]):
        raise FormError(f"task {task}: completed must be bool; minutes must be a finite number in 0..{S.MAX_TASK_MINUTES_RECORDED} (NaN/inf/bool rejected)")
    if not isinstance(t["note"], str):
        raise FormError(f"task {task}: note must be a string")
    el, cr = t["elements"], t["critical"]
    if not isinstance(el, dict) or not isinstance(cr, dict) or set(el) != set(spec["elements"]) or set(cr) != set(spec["critical"]) or not all(isinstance(v, bool) for v in list(el.values()) + list(cr.values())):
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
    if not isinstance(form, dict):
        raise FormError("form: object required")
    for k in S.FORM_FIELDS:
        if k not in form:
            raise FormError(f"missing form field {k}")
    if set(form) - set(S.FORM_FIELDS):
        raise FormError("unexpected form fields")
    if not isinstance(form["session_code"], str) or not re.match(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$", form["session_code"]):
        raise FormError("session_code shape")
    if form["mode"] not in S.MODES or form["assistance"] not in S.ASSISTANCE or form["relationship"] not in S.RELATIONSHIPS:
        raise FormError("mode/assistance/relationship not registered")
    if form["protocol_id"] != S.PROTOCOL_ID:
        raise FormError("protocol_id does not match the candidate protocol version")
    if not (isinstance(form["materials_manifest_sha256"], str) and _HEX64.match(form["materials_manifest_sha256"])):
        raise FormError("materials_manifest_sha256: full sha256 required")
    if not isinstance(form["synthetic"], bool):
        raise FormError("synthetic: bool required")
    wheel = validate_wheel(form["wheel"])
    if form["mode"] == "EXECUTION" and wheel["label"] == "NONE":
        raise FormError("EXECUTION mode requires a bound wheel (sha256 + length)")
    tasks = form["tasks"]
    if not isinstance(tasks, list):
        raise FormError("tasks: list required")
    if tasks == []:
        decision = "MISSING"; scored = []
    else:
        scored = [score_task(t) for t in tasks]
        if sorted(s["task"] for s in scored) != sorted(S.TASKS):
            raise FormError("a completed session form carries exactly the five tasks")
        if form["assistance"] == "LIVE_HELP":
            decision = "ASSISTED"                               # assistance precedence
        else:
            decision = "PASS" if all(s["result"] == "PASS" for s in scored) else "FAIL"
    return {"session_code": form["session_code"], "mode": form["mode"], "protocol_id": form["protocol_id"], "materials_manifest_sha256": form["materials_manifest_sha256"],
            "wheel": wheel, "decision": decision, "tasks": scored, "assistance": form["assistance"], "synthetic": form["synthetic"], "reviewer_role": form["reviewer_role"], "decided_at": form["decided_at"]}


def cohort_key(s: dict) -> tuple:
    return (s["mode"], s["protocol_id"], s["materials_manifest_sha256"], s["wheel"]["sha256"], s["wheel"]["size_bytes"])


def aggregate(sessions: list[dict]) -> dict:
    """Per-COHORT aggregates over the FIXED denominator. Duplicate session codes are rejected (a copied session
    is not a distinct participant); cohorts with different materials/wheel bindings are reported separately and
    never pooled; synthetic provenance is carried through."""
    codes = [s["session_code"] for s in sessions]
    if len(set(codes)) != len(codes):
        raise FormError("duplicated session codes: each eligible participant is one distinct session (copies are rejected)")
    cohorts = {}
    for s in sessions:
        cohorts.setdefault(cohort_key(s), []).append(s)
    out = []
    for key, rows in cohorts.items():
        mode, pid, man, wsha, wlen = key
        if len(rows) > S.DENOMINATOR:
            raise FormError(f"more than {S.DENOMINATOR} sessions in one cohort (the denominator is fixed; extra sessions are a protocol violation)")
        counts = {d: sum(1 for s in rows if s["decision"] == d) for d in S.SESSION_DECISIONS}
        counts["MISSING"] += S.DENOMINATOR - len(rows)
        out.append({"cohort": {"mode": mode, "protocol_id": pid, "materials_manifest_sha256": man, "wheel_sha256": wsha, "wheel_size_bytes": wlen, "wheel_labels": sorted({s["wheel"]["label"] for s in rows})},
                    "n_pass": counts["PASS"], "denominator": S.DENOMINATOR, "counts": counts, "sessions_recorded": len(rows), "distinct_participants": len(rows),
                    "synthetic": any(s["synthetic"] for s in rows), "primary": mode == S.PRIMARY_MODE,
                    "candidate_threshold_met": counts["PASS"] >= S.CANDIDATE_THRESHOLD["pass_sessions"], "threshold_status": S.CANDIDATE_THRESHOLD["status"]})
    return {"protocol_id": S.PROTOCOL_ID, "protocol_status": S.PROTOCOL_STATUS, "cohorts": out, "pooled": "NEVER",
            "note": "aggregate counts only, per cohort (mode + protocol + materials manifest + wheel bytes); no per-session labels are published"}


# ---- trusted-record validation for the gate-evidence adapter (records are checked, never self-declared)
def _appointment_record(appointments: list[dict], appointment_id: str) -> dict | None:
    for r in appointments:
        if r.get("kind") == "appointment" and r.get("appointment_id") == appointment_id:
            return r
    return None


def validate_prerequisites(*, protocol_adoption, applicability, reviewer_appointment, appointments: list[dict], human_records, sessions: list[dict], cohort: dict) -> list[str]:
    missing = []
    man = cohort["cohort"]["materials_manifest_sha256"]
    if not isinstance(protocol_adoption, dict) or protocol_adoption.get("protocol_id") != S.PROTOCOL_ID or protocol_adoption.get("adopted") is not True \
            or not protocol_adoption.get("adopted_by") or not protocol_adoption.get("adopted_at") or not (isinstance(protocol_adoption.get("kit_sha256"), str) and _HEX64.match(protocol_adoption["kit_sha256"])) \
            or protocol_adoption.get("materials_manifest_sha256") != man:
        missing.append("adopted protocol record bound to this protocol id and this materials manifest (adopted_by, adopted_at, kit_sha256)")
    if not isinstance(applicability, dict) or applicability.get("determination") not in ("no_review_required", "exempt", "approved") or not applicability.get("reference") or not applicability.get("issued_by") \
            or not applicability.get("date") or applicability.get("protocol_id") != S.PROTOCOL_ID:
        missing.append("documented privacy/ethics applicability determination (determination, reference, issued_by, date) bound to this protocol")
    appt = None
    if isinstance(reviewer_appointment, dict) and reviewer_appointment.get("appointment_id"):
        appt = _appointment_record(appointments or [], reviewer_appointment["appointment_id"])
    if appt is None or appt.get("status") != "DESIGNATED" or appt.get("designated") is not True or appt.get("role") != reviewer_appointment.get("role"):
        missing.append("designated study reviewer appointment resolved from the trusted appointment record (self-declared DESIGNATED is not authority)")
    if any(s["synthetic"] for s in sessions):
        missing.append("real sessions (synthetic sessions never form a gate input)")
    recs = human_records if isinstance(human_records, list) else None
    if not recs:
        missing.append("actual human session records (a flag is not a record)")
    else:
        by_code = {r.get("session_code"): r for r in recs if isinstance(r, dict)}
        for s in sessions:
            r = by_code.get(s["session_code"])
            if r is None or r.get("reviewer_role") != s["reviewer_role"] or r.get("appointment_id") != (reviewer_appointment or {}).get("appointment_id") or not r.get("decided_at"):
                missing.append(f"human session record for {s['session_code']} signed by the designated reviewer"); break
    return missing


def gate_evidence(evaluation: dict, *, protocol_adoption=None, applicability=None, reviewer_appointment=None, appointments=None, human_records=None, sessions=None) -> dict:
    """Gate-evidence adapter over the PRIMARY cohort. A REAL gate input exists only when every prerequisite record
    validates. The result covers exactly the tested materials and wheel bytes; it never transfers to another artifact."""
    prim = [c for c in evaluation["cohorts"] if c["primary"]]
    if len(prim) != 1:
        return {"gate_input": "NOT_A_GATE_INPUT", "missing_prerequisites": [f"exactly one primary cohort required (found {len(prim)}); cohorts are never pooled"], "gate_15": "MANUAL_REVIEW (unchanged)", "evaluation": evaluation}
    cohort = prim[0]; sess = [s for s in (sessions or []) if cohort_key(s) == (cohort["cohort"]["mode"], cohort["cohort"]["protocol_id"], cohort["cohort"]["materials_manifest_sha256"], cohort["cohort"]["wheel_sha256"], cohort["cohort"]["wheel_size_bytes"])]
    coverage = {"materials_manifest_sha256": cohort["cohort"]["materials_manifest_sha256"], "wheel_sha256": cohort["cohort"]["wheel_sha256"], "wheel_size_bytes": cohort["cohort"]["wheel_size_bytes"], "wheel_labels": cohort["cohort"]["wheel_labels"],
                "note": "covers exactly these material and wheel bytes; it does not transfer to a differently hashed artifact"}
    missing = validate_prerequisites(protocol_adoption=protocol_adoption, applicability=applicability, reviewer_appointment=reviewer_appointment, appointments=appointments, human_records=human_records, sessions=sess, cohort=cohort)
    if cohort["synthetic"]:
        missing = ["synthetic cohort: never a gate input"] + [m for m in missing if not m.startswith("real sessions")]
    if cohort["distinct_participants"] < S.DENOMINATOR:
        missing.append(f"only {cohort['distinct_participants']} distinct participants recorded of {S.DENOMINATOR}")
    if missing:
        return {"gate_input": "NOT_A_GATE_INPUT", "missing_prerequisites": missing, "gate_15": "MANUAL_REVIEW (unchanged)", "coverage": coverage, "evaluation": evaluation}
    return {"gate_input": "CANDIDATE_GATE_INPUT", "gate_15_proposed": ("GREEN" if cohort["candidate_threshold_met"] else "RED"),
            "note": "proposed value only; the release-policy actor records the gate; the candidate threshold is unadopted", "coverage": coverage, "evaluation": evaluation}
