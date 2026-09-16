"""As-of evidence inspection (adapted from the preview; V8-005).

Adaptation notes: the preview inspected the published EvidenceObject corpus by ticker. The workbench's objects are its
registered source records (accession, source_hash, available_as_of); the same rules apply — availability cut, missing
identity, duplicate (accession, digest) pairs — and the result is descriptive only (NOT_TESTED).
"""
from __future__ import annotations

from .contracts import timestamp


def inspect_evidence(objects, as_of, label="workspace sources"):
    cutoff = timestamp(as_of)
    eligible, excluded, identities = [], [], set()
    for obj in objects:
        if not isinstance(obj, dict):
            excluded.append({"reason": "malformed_object"})
            continue
        reason = None
        try:
            available = timestamp(obj.get("available_as_of"))
            if available > cutoff:
                reason = "not_available_as_of"
        except ValueError:
            reason = "missing_or_ambiguous_availability"
        source = obj.get("source_hash")
        accession = obj.get("accession")
        if not isinstance(source, str) or not source or not isinstance(accession, str) or not accession:
            reason = reason or "missing_source_identity"
        identity = (accession, source) if reason is None else None
        if reason is None and identity in identities:
            reason = "duplicate_source"
        if reason:
            excluded.append({"accession": accession, "reason": reason})
            continue
        identities.add(identity)
        eligible.append(obj)
    eligible.sort(key=lambda o: (timestamp(o["available_as_of"]), o["accession"], o["source_hash"]))
    return {"scope": label, "as_of": as_of, "eligible_sources": eligible, "excluded": excluded,
            "distinct_filings": len({o["accession"] for o in eligible}),
            "statistical_status": "NOT_TESTED", "permission": "DESCRIPTIVE_EVIDENCE_ONLY",
            "limitations": ["A source match does not establish the truth of a sentence or any predictive value.",
                            "Different filings may remain dependent. Distinct filings is not an effective sample size.",
                            "Objects with unknown extraction protocol remain explicitly unregistered."],
            "not_advice": "Research and education only — not investment advice."}
