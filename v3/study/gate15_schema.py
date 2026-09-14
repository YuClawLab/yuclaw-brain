"""ONE machine-readable schema for the Gate #15 kit, scoring key and decision form (V5).

Every expected element and critical error of the scoring key is encoded here; the participant script and the
reviewer scoring key are rendered from / checked against it. Rules encoded: 10-minute timeout → INCOMPLETE;
any critical error → FAIL_CRITICAL; any missing expected element → FAIL_INCOMPLETE; a session PASSES only when
every task PASSES; assistance (LIVE_HELP) takes precedence over the task results (session ASSISTED, counted as
non-PASS); fixed denominator 5 per mode; EXECUTION and TRANSCRIPT modes are never pooled."""
from __future__ import annotations

PROTOCOL_ID = "gate15-formative-comprehension-candidate-2026-09"
PROTOCOL_STATUS = "UNADOPTED"
MODES = ("EXECUTION", "TRANSCRIPT")
PRIMARY_MODE = "EXECUTION"
DENOMINATOR = 5
TASK_MINUTES = 10
CANDIDATE_THRESHOLD = {"pass_sessions": 4, "of": DENOMINATOR, "over_tasks": "all five", "status": "UNADOPTED"}
TASK_RESULTS = ("PASS", "FAIL_INCOMPLETE", "FAIL_CRITICAL", "INCOMPLETE")
SESSION_DECISIONS = ("PASS", "FAIL", "MISSING", "ASSISTED")
ASSISTANCE = ("NONE", "LIVE_HELP")

TASKS = {
    1: {"name": "Check", "modes": MODES, "elements": {
            "E1.1": "the status means the parsed claim elements (ticker NVDA, type INSIDER_SELL) matched stored evidence objects (five filings)",
            "E1.2": "it is a coverage statement about the corpus, not that the claim is true",
            "E1.3": "no recommendation, direction, expected return or research interpretation (research_interpretation NONE)"},
        "critical": {"C1.1": "says the claim is proven true", "C1.2": "says an UNSUPPORTED status would mean the claim is false", "C1.3": "reads buy/sell direction, return or advice from the passport"}},
    2: {"name": "Reproduce", "modes": MODES, "elements": {
            "E2.1": "verify recomputed each listed file's SHA-256 and byte length against the packet manifest first",
            "E2.2": "it then replayed the frozen Lab bundle and reproduced the published statistics/roots",
            "E2.3": "SUCCESS is not an outsider receipt, not independent, not proof of official origin, not scientific validation"},
        "critical": {"C2.1": "says SUCCESS is an independent/outsider result", "C2.2": "says it proves official origin", "C2.3": "says it validates the research"}},
    3: {"name": "Scoreboard", "modes": MODES, "elements": {
            "E3.1": "the exact-target count is zero or the state is UNBOUND/PENDING/UNAVAILABLE, stated as such",
            "E3.2": "the state is displayed, not hidden",
            "E3.3": "the legacy program entry is prefix-bound and affiliated and does not count as an exact-wheel outsider reproduction"},
        "critical": {"C3.1": "reads a zero/pending/unavailable state as a positive count", "C3.2": "invents a number", "C3.3": "counts the legacy entry as an outsider reproduction of the wheel"}},
    4: {"name": "Limits", "modes": MODES, "elements": {
            "E4.1": "no page gives buy/sell direction or expected returns",
            "E4.2": "the disclaimer states research and education only, not investment advice"},
        "critical": {"C4.1": "believes the site gives investment direction or performance expectations"}},
    5: {"name": "Challenge", "modes": MODES, "elements": {
            "E5.1": "a challenge was recorded (EXECUTION: list shows OPEN and adverse true; TRANSCRIPT: template completely filled)",
            "E5.2": "recording changes nothing about the published evidence until a designated reviewer disposes it; the local synthetic record, public aggregation, disposition history and immutable original evidence are distinct",
            "E5.3": "adverse findings remain visible"},
        "critical": {"C5.1": "cannot record a challenge / template incomplete", "C5.2": "believes recording one changes the evidence or the counts"}},
}

FORM_FIELDS = ("session_code", "mode", "materials_manifest_sha256", "wheel_label", "tasks", "assistance", "relationship", "reviewer_role", "decided_at")
TASK_FORM_FIELDS = ("task", "completed", "minutes", "elements", "critical", "note")
WHEEL_LABELS = ("REHEARSAL", "RC", "FINAL", "NONE")
RELATIONSHIPS = ("RELATED-DISCLOSED", "UNRELATED")


def as_dict() -> dict:
    return {"protocol_id": PROTOCOL_ID, "status": PROTOCOL_STATUS, "modes": MODES, "primary_mode": PRIMARY_MODE, "denominator": DENOMINATOR, "task_minutes": TASK_MINUTES,
            "candidate_threshold": CANDIDATE_THRESHOLD, "tasks": {str(k): v for k, v in TASKS.items()}, "task_results": TASK_RESULTS, "session_decisions": SESSION_DECISIONS,
            "assistance": ASSISTANCE, "form_fields": FORM_FIELDS, "task_form_fields": TASK_FORM_FIELDS, "wheel_labels": WHEEL_LABELS, "relationships": RELATIONSHIPS}
