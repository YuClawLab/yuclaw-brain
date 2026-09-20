"""PRC — Independent Practice: commit a judgment before seeing a comparison, then reflect.

CONFIDENTIALITY BOUNDARY (exact). The comparison lives only in the server's private vault as a SALTED object; the journal
holds the sha256 of that object, which a low-entropy answer cannot be enumerated from. No route serves it to the
`practice` capability before that practitioner's attempt is committed in the journal; when principals are configured a
practice-only principal is confined to the practice routes, so no claim page, journal page, export or other view is an
alternate path. Outside this boundary, plainly: the host administrator (file access), the curator, an administrator
principal, any outside assistance, and an answer already public elsewhere. A packaged example answer is a demonstration,
not a confidential assessment. The records show which local credential acted and in what order; they cannot prove human
authorship, the absence of outside help, comprehension, or that ability improved.

ORDER. Task frozen (question, claim version, source scope and comparison commitment) → session opened with TRUTHFUL
declarations (assisted and already-exposed sessions are accepted and labelled; nobody must claim not to have seen an
answer) → evidence opened (access, not comprehension) → attempt committed atomically (vault first, the journal event is
the commit; one attempt per session, never replaced; a retry with the same operation id is the same event) → only then
may the comparison be revealed, with its provenance (an unadjudicated reference or a model answer is not ground truth) →
reflection and reviewer feedback as separate later records → optional follow-up tasks as local due-states (nobody is
contacted, no study is run). A later source correction, claim amendment or EVO change is shown as an annotation on the
CURRENT interpretation; the frozen session and the original attempt are never rewritten."""
from __future__ import annotations

import hashlib
import secrets

from v3.receipts.contracts import canonical_json
from v8.workbench.modkinds import PRC_KINDS
from v8.workbench.modules import authz, commons, core, envelope, shield
from v8.workbench.modules.core import ModuleError
from v8.workbench.store import Workspace

ASSISTANCE = ("NONE", "AI_ASSISTED", "HUMAN_ASSISTED", "OTHER")
EXPOSURE = ("NOT_SEEN", "SEEN_ANSWER", "UNSURE")
PROVENANCE = {"UNADJUDICATED_REFERENCE": "a curator's reference that nobody independently reviewed — not ground truth", "MODEL_ANSWER": "an answer produced by a model — not ground truth",
              "REVIEWED_REFERENCE": "a reference the curator DECLARES was reviewed; the declaration is recorded, not verified"}
DEFAULT_SESSION_MINUTES = 20


def state(ws: Workspace, as_of: str | None = None, evs: list | None = None) -> dict:
    s = {"tasks": {}, "sessions": {}, "followups": [], "checkpoints": []}
    for e in core.events(ws, PRC_KINDS, as_of=as_of, evs=evs):
        k, p, at = e["kind"], e["payload"], e["time"]["recorded_at"]
        if k == "PRC_TASK_FROZEN":
            s["tasks"][p["task_id"]] = {**p, "frozen_at": at}
        elif k == "PRC_SESSION_OPENED":
            s["sessions"][p["session_id"]] = {**p, "opened_at": at, "reads": [], "attempt": None, "revealed_at": None, "reflections": [], "feedback": []}
        elif k == "PRC_FOLLOWUP_SCHEDULED":
            s["followups"].append({**p, "at": at})
        elif k == "PRC_CHECKPOINT_ISSUED":
            s["checkpoints"].append({**p, "at": at})
        elif p.get("session_id") in s["sessions"]:
            ss = s["sessions"][p["session_id"]]
            if k == "PRC_EVIDENCE_READ":
                ss["reads"].append({"source_id": p["source_id"], "at": at})
            elif k == "PRC_ATTEMPT_COMMITTED":
                ss["attempt"] = {**p, "at": at, "event_hash": e["event_hash"]}
            elif k == "PRC_COMPARISON_REVEALED":
                ss["revealed_at"] = at
            elif k == "PRC_REFLECTION_RECORDED":
                ss["reflections"].append({**p, "at": at})
            elif k == "PRC_FEEDBACK_RECORDED":
                ss["feedback"].append({**p, "at": at})
    return s


# ------------------------------------------------------------------ curation (review capability)
def freeze_task(ws: Workspace, principal, *, title: str, question: str, claim_id: str | None, source_ids: list, labels: list, reference_label: str, reference_answer: str, rationale: str,
                provenance: str, declared_curator_qualification: str, public_example: bool, session_minutes: int, evo_version_id: str | None, op_id: str) -> dict:
    authz.require(principal, "review")
    if provenance not in PROVENANCE:
        raise ModuleError("E_PROVENANCE", "comparison provenance: " + ", ".join(PROVENANCE))
    labels = [core.text(x, "label", maxlen=40) for x in labels][:8]
    if len(set(labels)) < 2 or "UNRESOLVED" in labels:
        raise ModuleError("E_LABELS", "give at least two distinct judgment labels; UNRESOLVED is always offered and is not listed")
    if reference_label not in labels + ["UNRESOLVED"]:
        raise ModuleError("E_LABELS", "the reference label is one of the task's labels (or UNRESOLVED)")
    if isinstance(session_minutes, bool) or not isinstance(session_minutes, int) or not 5 <= session_minutes <= 240:
        raise ModuleError("E_MINUTES", "session minutes: 5 to 240")
    known = core.source_ids(ws); scope = []
    for sid in dict.fromkeys(source_ids):
        if sid not in known:
            raise ModuleError("E_UNKNOWN_SOURCE", f"source {sid!r} is not registered in this workspace")
        src = known[sid]["payload"]
        scope.append({"source_id": sid, "source_hash": src.get("source", {}).get("source_hash") or src.get("source_hash"), "registered_event": known[sid]["event_hash"]})
    if not scope:
        raise ModuleError("E_SCOPE", "a task names at least one registered source the practitioner may read")
    ref = core.claim_ref(ws, claim_id) if claim_id else None
    if evo_version_id:
        from v8.workbench.modules import evolution
        if core.ident(evo_version_id, "EVO version") not in evolution.state(ws)["versions"]:
            raise ModuleError("E_UNKNOWN", f"EVO version {evo_version_id!r} is not registered in this workspace")
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "PRC_TASK_FROZEN":
            return done
        comparison = {"salt": secrets.token_hex(32), "reference_label": reference_label, "reference_answer": core.text(reference_answer, "reference answer", maxlen=4000), "rationale": core.text(rationale, "rationale", maxlen=4000, required=False),
                      "provenance": provenance, "curator": principal["principal_id"]}
        commitment = core.Vault(ws).put(comparison)                           # vault first; the event below is the commit point
        payload = {"task_id": core.next_id(evs, "PRC_TASK_FROZEN", "TK", "task_id"), "title": core.text(title, "title", maxlen=160), "question": core.text(question, "question", maxlen=2000),
                   "claim": None if ref is None else {k: ref[k] for k in ("claim_id", "version", "version_digest", "contract_digest")}, "source_scope": scope, "labels": labels, "comparison_commitment": commitment,
                   "comparison_provenance": provenance, "curator": principal["principal_id"], "declared_curator_qualification": core.text(declared_curator_qualification, "declared qualification", maxlen=300, required=False),
                   "qualification_status": "DECLARED — recorded as stated; not verified by this software", "public_example": bool(public_example), "session_minutes": session_minutes,
                   "evo_version_id": core.ident(evo_version_id, "EVO version") if evo_version_id else None,
                   "frozen_meaning": "question, claim version, source scope and comparison commitment are fixed from this event on; a changed reference needs a new task"}
        ev, _ = ws._append_unlocked("PRC_TASK_FROZEN", None, payload, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


# ------------------------------------------------------------------ the practitioner's path (practice capability)
def category(assistance: str, exposure: str) -> str:
    if exposure == "SEEN_ANSWER":
        return "ALREADY_EXPOSED"
    if assistance != "NONE":
        return "ASSISTED"
    return "UNAIDED_DECLARED" if exposure == "NOT_SEEN" else "UNAIDED_DECLARED_EXPOSURE_UNSURE"


def open_session(ws: Workspace, principal, *, task_id: str, assistance: str, assistance_note: str, prior_exposure: str, op_id: str) -> dict:
    authz.require(principal, "practice")
    if assistance not in ASSISTANCE or prior_exposure not in EXPOSURE:
        raise ModuleError("E_DECLARATION", f"assistance: {', '.join(ASSISTANCE)}; prior exposure: {', '.join(EXPOSURE)} — declare what is true; every combination is accepted and labelled")
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "PRC_SESSION_OPENED":
            return done
        s = state(ws, evs=evs); t = s["tasks"].get(task_id)
        if t is None:
            raise ModuleError("E_UNKNOWN", "no such task")
        authz.conflict(principal, [t["curator"]], "curated this task (and knows its comparison) and cannot practise on it")
        if any(x["task_id"] == task_id and x["practitioner"] == principal["principal_id"] for x in s["sessions"].values()):
            raise ModuleError("E_SESSION_EXISTS", "this principal already has a session on this task; a second look would not be a first attempt")
        cap = commons.capacity(commons.state(ws, evs=evs))
        if not cap["configured"]:
            raise ModuleError("E_NOT_CONFIGURED", "an administrator sets the COM budget with its separate practice reserve first (COM → Budget)")
        if t["session_minutes"] > cap["practice_remaining"]:
            raise ModuleError("E_NO_PRACTICE_CAPACITY", f"the practice reserve for period {cap['period_id']} has {cap['practice_remaining']} minutes left; this task needs {t['session_minutes']}. Review capacity is never borrowed for practice")
        payload = {"session_id": core.next_id(evs, "PRC_SESSION_OPENED", "SS", "session_id"), "task_id": task_id, "practitioner": principal["principal_id"],
                   "declarations": {"assistance": assistance, "assistance_note": core.text(assistance_note, "assistance note", maxlen=500, required=False), "prior_exposure": prior_exposure},
                   "category": category(assistance, prior_exposure), "period_id": cap["period_id"], "practice_minutes_reserved": t["session_minutes"],
                   "confinement": ("PRACTICE_ONLY — this principal is confined to the practice routes" if set(principal["caps"]) == {"practice"} else
                                   "NOT_CONFINED — this principal also holds " + ", ".join(c for c in principal["caps"] if c != "practice") + ", so claim pages, the journal and exports are open to it; the comparison itself stays server-held, "
                                   "but anything those pages show about the question is not withheld from this practitioner"),
                   "declaration_meaning": "declarations are the practitioner's own statements; this software cannot observe outside help or earlier exposure"}
        ev, _ = ws._append_unlocked("PRC_SESSION_OPENED", None, payload, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


def _own_session(s: dict, principal, session_id: str) -> tuple[dict, dict]:
    ss = s["sessions"].get(session_id)
    if principal is None or ss is None or ss["practitioner"] != principal["principal_id"]:
        raise ModuleError("E_NOT_FOUND", "no such session for this principal")            # one message for "missing" and "someone else's"
    return ss, s["tasks"][ss["task_id"]]


def read_evidence(ws: Workspace, principal, session_id: str, source_id: str) -> dict:
    """The frozen evidence text of one in-scope source, and an access record (idempotent per source). Access, not comprehension."""
    authz.require(principal, "practice")
    s = state(ws); ss, t = _own_session(s, principal, session_id)
    if source_id not in [x["source_id"] for x in t["source_scope"]]:
        raise ModuleError("E_OUT_OF_SCOPE", "that source is not in this task's frozen scope")
    src = core.source_ids(ws)[source_id]["payload"]; body = src.get("source", src)
    core.append(ws, "PRC_EVIDENCE_READ", {"session_id": session_id, "source_id": source_id, "meaning": "the page was served; not evidence of reading or comprehension"},
                op_id="prc:read:" + hashlib.sha256(f"{session_id}|{source_id}".encode()).hexdigest()[:24], principal=principal)
    return {"source_id": source_id, "excerpt": body.get("excerpt", ""), "available_as_of": body.get("available_as_of"), "kind": body.get("kind"), "form": body.get("form"), "fictional": body.get("fictional")}


def commit_attempt(ws: Workspace, principal, session_id: str, *, judgment: str, reasoning: str, source_refs: list, unresolved_note: str, op_id: str) -> dict:
    authz.require(principal, "practice")
    with ws._locked():
        evs = ws.load()["events"]; s = state(ws, evs=evs); ss, t = _own_session(s, principal, session_id)
        if judgment not in t["labels"] + ["UNRESOLVED"]:
            raise ModuleError("E_JUDGMENT", "choose one of the task's labels, or UNRESOLVED")
        scope = [x["source_id"] for x in t["source_scope"]]; refs = [r for r in dict.fromkeys(source_refs) if r in scope]
        if not refs:
            raise ModuleError("E_SOURCE_REFS", "name at least one source from the task's scope that the judgment rests on")
        content = {"session_id": session_id, "judgment": judgment, "reasoning": core.text(reasoning, "reasoning", maxlen=6000), "source_refs": refs,
                   "unresolved_note": core.text(unresolved_note, "what would resolve it", maxlen=1000, required=judgment == "UNRESOLVED")}
        digest = hashlib.sha256(canonical_json(content)).hexdigest()
        if ss["attempt"] is not None:
            if ss["attempt"]["attempt_sha256"] == digest:
                return next(e for e in evs if e["kind"] == "PRC_ATTEMPT_COMMITTED" and e["payload"]["session_id"] == session_id)
            raise ModuleError("E_ALREADY_COMMITTED", "this session's attempt is committed and is never replaced; later thoughts are recorded as a reflection")
        core.Vault(ws).put(content)                                            # content first (content-addressed: never overwrites another object)
        ev, _ = ws._append_unlocked("PRC_ATTEMPT_COMMITTED", None, {"session_id": session_id, "task_id": t["task_id"], "attempt_sha256": digest, "judgment": judgment, "source_refs": refs,
                                    "category": ss["category"], "reads_before_attempt": len(ss["reads"]), "meaning": "the original attempt; preserved as committed"},
                                    op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


def _may_reveal(ss: dict) -> bool:
    """THE confidentiality rule, in one place: a comparison opens only for a session whose attempt is committed in the journal."""
    return ss["attempt"] is not None


def reveal(ws: Workspace, principal, session_id: str) -> dict:
    """The comparison — ONLY after this session's attempt is committed in the journal. Checked and recorded under the lock."""
    authz.require(principal, "practice")
    with ws._locked():
        evs = ws.load()["events"]; s = state(ws, evs=evs); ss, t = _own_session(s, principal, session_id)
        if not _may_reveal(ss):
            raise ModuleError("E_ATTEMPT_FIRST", "the comparison stays closed until this session's attempt is committed")
        ws._append_unlocked("PRC_COMPARISON_REVEALED", None, {"session_id": session_id, "task_id": t["task_id"], "after_attempt_event": (ss["attempt"] or {}).get("event_hash"), "comparison_commitment": t["comparison_commitment"]},
                            op_id="prc:reveal:" + hashlib.sha256(session_id.encode()).hexdigest()[:24], observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        c = core.Vault(ws).get(t["comparison_commitment"])
    return {"reference_label": c["reference_label"], "reference_answer": c["reference_answer"], "rationale": c["rationale"], "provenance": c["provenance"], "provenance_meaning": PROVENANCE[c["provenance"]],
            "curator": c["curator"], "agrees_with_attempt": c["reference_label"] == (ss["attempt"] or {}).get("judgment"),
            "note": "agreement with a reference is not correctness, and neither is evidence of learning"}


def reflect(ws: Workspace, principal, session_id: str, *, text_: str, op_id: str) -> dict:
    authz.require(principal, "practice")
    with ws._locked():
        s = state(ws); ss, _ = _own_session(s, principal, session_id)
        if ss["revealed_at"] is None:
            raise ModuleError("E_REVEAL_FIRST", "a reflection follows the comparison")
        d = core.Vault(ws).put({"session_id": session_id, "reflection": core.text(text_, "reflection", maxlen=6000)})
        return ws._append_unlocked("PRC_REFLECTION_RECORDED", None, {"session_id": session_id, "reflection_sha256": d, "meaning": "a separate later record; the attempt is unchanged"},
                                   op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))[0]


def feedback(ws: Workspace, principal, session_id: str, *, text_: str, op_id: str) -> dict:
    authz.require(principal, "review")
    with ws._locked():
        s = state(ws); ss = s["sessions"].get(session_id)
        if ss is None or ss["attempt"] is None:
            raise ModuleError("E_NOT_FOUND", "feedback is given on a committed attempt")
        authz.conflict(principal, [ss["practitioner"]], "is this session's practitioner and cannot give reviewer feedback on it")
        d = core.Vault(ws).put({"session_id": session_id, "feedback": core.text(text_, "feedback", maxlen=6000), "reviewer": principal["principal_id"]})
        return ws._append_unlocked("PRC_FEEDBACK_RECORDED", None, {"session_id": session_id, "feedback_sha256": d, "reviewer": principal["principal_id"],
                                   "meaning": "formative feedback on one attempt; not a capability ranking of a person"}, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))[0]


def schedule_followup(ws: Workspace, principal, *, session_id: str, followup_task_id: str, due_at: str, op_id: str) -> dict:
    authz.require(principal, "review")
    s = state(ws)
    if session_id not in s["sessions"] or followup_task_id not in s["tasks"]:
        raise ModuleError("E_UNKNOWN", "unknown session or follow-up task")
    return core.append(ws, "PRC_FOLLOWUP_SCHEDULED", {"session_id": session_id, "practitioner": s["sessions"][session_id]["practitioner"], "followup_task_id": followup_task_id, "due_at": core.norm_time(due_at, "due time"),
                       "meaning": "a local due-state shown to the practitioner after signing in; nobody is contacted and no study is run"}, op_id=op_id, principal=principal)[0]


def due_state(s: dict, practitioner: str, now=None) -> list:
    now = now or core.now(); out = []
    for f in s["followups"]:
        if f["practitioner"] != practitioner:
            continue
        done = any(x["task_id"] == f["followup_task_id"] and x["practitioner"] == practitioner for x in s["sessions"].values())
        out.append({**f, "state": "COMPLETED" if done else ("DUE" if core.parse_time(f["due_at"]) <= now else "NOT_YET_DUE")})
    return out


# ------------------------------------------------------------------ what a principal may see
def session_view(ws: Workspace, principal, session_id: str) -> dict:
    """Own session (practitioner), or any session for an administrator; a reviewer sees a session only once its attempt is
    committed. Another practitioner gets E_NOT_FOUND. The comparison appears only after the reveal event."""
    s = state(ws); ss = s["sessions"].get(session_id)
    if principal is None or ss is None:
        raise ModuleError("E_NOT_FOUND", "no such session for this principal")
    mine = ss["practitioner"] == principal["principal_id"]
    if not (mine or "admin" in principal["caps"] or ("review" in principal["caps"] and ss["attempt"] is not None)):
        raise ModuleError("E_NOT_FOUND", "no such session for this principal")
    t = s["tasks"][ss["task_id"]]; v = core.Vault(ws)
    out = {"session": {**{k: ss[k] for k in ("session_id", "task_id", "practitioner", "declarations", "category", "opened_at", "reads", "revealed_at")}, "confinement": ss.get("confinement", "not recorded (session opened before this field existed)")},
           "task": {k: t[k] for k in ("task_id", "title", "question", "claim", "source_scope", "labels", "comparison_provenance", "curator", "declared_curator_qualification", "qualification_status", "public_example", "session_minutes")},
           "attempt": None, "comparison": None, "reflections": [], "feedback": [], "current_interpretation": annotations(ws, t, ss)}
    if ss["attempt"] is not None:
        out["attempt"] = {**v.get(ss["attempt"]["attempt_sha256"]), "committed_at": ss["attempt"]["at"], "attempt_sha256": ss["attempt"]["attempt_sha256"]}
    if ss["revealed_at"] is not None or (not mine and _may_reveal(ss)):
        c = v.get(t["comparison_commitment"]); out["comparison"] = {k: c[k] for k in ("reference_label", "reference_answer", "rationale", "provenance", "curator")}; out["comparison"]["provenance_meaning"] = PROVENANCE[c["provenance"]]
    if ss["revealed_at"] is not None or not mine:
        out["reflections"] = [{**v.get(r["reflection_sha256"]), "at": r["at"]} for r in ss["reflections"]]
        out["feedback"] = [{**v.get(f["feedback_sha256"]), "at": f["at"]} for f in ss["feedback"]]
    return out


def annotations(ws: Workspace, t: dict, ss: dict) -> list:
    """What changed AFTER the task was frozen, as notes on the current interpretation. Nothing frozen is rewritten."""
    notes = []; evs = ws.load()["events"]; frozen = core.parse_time(t["frozen_at"]); scope = {x["source_id"] for x in t["source_scope"]}
    for e in evs:
        if core.recorded_at(e) <= frozen:
            continue
        if e["kind"] == "SOURCE_AVAILABILITY_CORRECTED" and e["payload"].get("source_id") in scope:
            notes.append(f"source {e['payload']['source_id']}: its availability time was corrected at {e['time']['recorded_at']} — the session's frozen evidence and attempt are unchanged; check whether the correction affects today's reading")
        if t["claim"] and e["claim_id"] == t["claim"]["claim_id"] and e["kind"] in ("CLAIM_REVISED", "SOURCE_CORRECTED", "CLAIM_WITHDRAWN"):
            notes.append(f"claim {t['claim']['claim_id']}: {e['kind']} recorded at {e['time']['recorded_at']} — the task still names version {t['claim']['version']}; the original attempt and comparison are not re-scored")
        if t["evo_version_id"] and e["kind"] == "EVO_VERSION_REGISTERED" and e["payload"].get("parent_version_id") == t["evo_version_id"]:
            notes.append(f"EVO: version {e['payload']['version_id']} succeeded {t['evo_version_id']} at {e['time']['recorded_at']} (changed: {', '.join(e['payload']['changed_components']) or 'nothing measured'}); a retrospective result is not upgraded")
    return notes


# ------------------------------------------------------------------ independently held checkpoints
def issue_checkpoint(ws: Workspace, principal, *, op_id: str) -> dict:
    """A signed statement of the journal's tip. The OWNER keeps the returned envelope somewhere else; an export is later checked
    against the separately held copy — a checkpoint shipped inside the same bundle proves nothing about truncation."""
    authz.require(principal, "admin")
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "PRC_CHECKPOINT_ISSUED":
            return done
        st = shield.state(ws, evs=evs); kid, pem = shield._signing_key(ws, st)
        body = {"workspace_id": ws.meta["workspace_id"], "journal_seq": len(evs), "journal_tip": evs[-1]["event_hash"] if evs else "0" * 64, "issued_at": core.now().strftime("%Y-%m-%dT%H:%M:%SZ"), "key_id": kid}
        return ws._append_unlocked("PRC_CHECKPOINT_ISSUED", None, {"checkpoint": envelope.sign("prc.checkpoint", body, pem), "hold_separately": True}, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))[0]
