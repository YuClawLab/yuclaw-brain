"""Event kinds of the four v8 modules (V8-014). No imports: the store reads this tuple for its allow-list.

Every module event is workspace-level (`claim_id` None) and names the canonical claim, version and source objects it
concerns inside its payload, so a claim's own export and the verification of older exports are unchanged. Private
content (a practice comparison, an attempt, staged evidence bytes, a credential hash) is never an event payload: an
event carries only the sha256 of a vault object (see v8/workbench/modules/core.py)."""

AUTH_KINDS = ("PRINCIPAL_ENROLLED", "PRINCIPAL_ROTATED", "PRINCIPAL_REVOKED")
SHD_KINDS = ("SHD_ROOT_ENROLLED", "SHD_ROOT_REVOKED", "SHD_POLICY_SET", "SHD_APPROVAL_ISSUED", "SHD_APPROVAL_REVOKED",
             "SHD_SUBMISSION_RECEIVED", "SHD_DECISION_RECORDED", "SHD_TRUST_DISCREPANCY", "SHD_TRUST_RESOLUTION")
EVO_KINDS = ("EVO_VERSION_REGISTERED", "EVO_EVALUATION_RECORDED", "EVO_REVIEW_RECORDED", "EVO_FAILURE_RECORDED", "EVO_FAILURE_RESOLVED",
             "EVO_TEST_ACCESS_RECORDED", "EVO_REEVAL_REQUESTED", "EVO_COMMITMENT_LINKED")
COM_KINDS = ("COM_BUDGET_SET", "COM_PACKET_SUBMITTED", "COM_COST_SET", "COM_TASK_TRANSITION", "COM_EFFORT_DECLARED", "COM_OVERRIDE_RECORDED",
             "COM_DISPUTE_RECORDED", "COM_APPEAL_RECORDED", "COM_DISPUTE_RESOLVED")
PRC_KINDS = ("PRC_TASK_FROZEN", "PRC_SESSION_OPENED", "PRC_EVIDENCE_READ", "PRC_ATTEMPT_COMMITTED", "PRC_COMPARISON_REVEALED", "PRC_REFLECTION_RECORDED",
             "PRC_FEEDBACK_RECORDED", "PRC_FOLLOWUP_SCHEDULED", "PRC_CHECKPOINT_ISSUED")
MODULE_EXPORT_KINDS = ("MODULE_EXPORT_BUILT", "MODULE_PACKET_VERIFIED")
MODULE_KINDS = AUTH_KINDS + SHD_KINDS + EVO_KINDS + COM_KINDS + PRC_KINDS + MODULE_EXPORT_KINDS
