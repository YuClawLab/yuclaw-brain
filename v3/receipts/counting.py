"""Derived state and honest counting (v7 receipts).

Qualification is DERIVED, never read from a submission: it needs (1) a validated current submission,
(2) an OBSERVATION whose observed sha256 + length equal the receipt's exact binding (FULL), (3) a trusted
REVIEW in state QUALIFIED bound to the CURRENT digest under the current policy version, (4) relationship
not OWNER-AFFILIATED/UNKNOWN, (5) execution SELF or ASSISTED (with disclosed assistance), (6) no
outcome-dependent incentive. A review carries the authority of its APPOINTMENT (DESIGNATED, SYNTHETIC or
HELD); real qualification requires DESIGNATED.

Populations (never summed together): attempts; qualified (incl. qualified FAILED/INCONCLUSIVE);
successful (qualified AND REPRODUCED); artifact sets (successful cohort's artifacts, attempted
artifacts, verified artifacts, by type — package types are separate from site/endpoint/chain).
Distinct persons/groups: primary = qualified attempts; successful reported separately; deduplicated
across activities/versions inside a registered window.

Registration (owner adoption) is a VALIDATED record {protocol_id, anchor, registered_at, policy_version}.
Records are never reassigned to another protocol: rows of other protocols stay visible in their own
unregistered bucket; rows of the registered protocol observed (or first imported) BEFORE the registration
instant — including earlier on the same UTC day — are `pre-registration` and never enter the prospective
primary floor; a correction cannot move an attempt forward because eligibility uses the EARLIEST observed
and imported instants in its lineage. Without registration the counts are UNWINDOWED (pending) — window
zero is never fabricated."""
from __future__ import annotations

from datetime import date

from v3.receipts.contracts import (NON_QUALIFYING_RELATIONSHIPS, PACKAGE_ARTIFACTS, POLICY_VERSION, WINDOW_DAYS, parse_ts, validate_registration)
from v3.receipts.store import Store


def _binding(obs: dict | None, sub: dict) -> str:
    """FULL only when the stored observation's OBSERVED values equal the receipt's exact binding (recomputed
    here; the stored `verified` flag alone is never trusted)."""
    if not obs:
        return "NONE"
    b = sub["artifact_binding"]
    if (obs.get("observed_sha256"), obs.get("observed_size_bytes"), obs.get("artifact_type")) == (b["sha256"], b["size_bytes"], b["artifact_type"]) \
            and obs.get("verified") is True and obs.get("claimed_sha256") == b["sha256"] and obs.get("claimed_size_bytes") == b["size_bytes"]:
        return "FULL"
    return "UNVERIFIED"


def _real_review_evidence(store: Store, rev: dict) -> list[str]:
    """A REAL qualification rests on immutable appointment evidence, never on the review line's own label:
    the review must name an appointment id whose record is DESIGNATED under the review's policy version, for the
    same role, appointed no later than the decision. Legacy reviews without an appointment id are ambiguous and
    need a new explicit review (history is never rewritten)."""
    aid = rev.get("appointment_id")
    if not aid:
        return ["review lacks appointment evidence (legacy or ambiguous review; a new explicit designated review is required)"]
    rec = store.appointment_record(aid)
    if rec is None:
        return ["review appointment id has no immutable appointment record"]
    if rec.get("status") != "DESIGNATED" or rec.get("designated") is not True:
        return [f"review appointment is {rec.get('status')} — not designated (real qualification pending)"]
    if rec.get("role") != rev.get("reviewer_role"):
        return ["review appointment belongs to a different role"]
    if rec.get("policy_version") != rev.get("policy_version"):
        return ["review appointment is bound to a different policy version"]
    if rev.get("decided_at") and rec.get("appointed_at") and rev["decided_at"] < rec["appointed_at"]:
        return ["review decided before its appointment existed"]
    if rev.get("authority") != "DESIGNATED":
        return ["review line authority label disagrees with its appointment record"]
    return []


ELIGIBILITY = ("unwindowed", "other_protocol", "pre_registration", "pre_anchor", "prospective")


def derive(store: Store, *, synthetic: bool) -> list[dict]:
    """Derived view of CURRENT submissions whose provenance matches `synthetic`."""
    out = []
    for aid, rec in sorted(store.current_submissions().items()):
        if rec["provenance"]["synthetic"] != synthetic:
            continue
        sub = rec["submission"]; d = rec["digest"]
        obs = store.observation_for(d); rev = store.review_for(d)
        binding = _binding(obs, sub)
        reasons = []
        review_state = rev["state"] if rev else "RECEIVED"
        if rev and rev.get("policy_version") != POLICY_VERSION:
            reasons.append("review under a different policy version"); review_state = "RECEIVED"
        if review_state != "QUALIFIED":
            reasons.append(f"review state {review_state}")
        elif not synthetic:
            reasons.extend(_real_review_evidence(store, rev))
        if sub["relationship"] in NON_QUALIFYING_RELATIONSHIPS:
            reasons.append(f"relationship {sub['relationship']} never qualifies")
        if sub["execution_control"] == "OPERATOR-RUN":
            reasons.append("OPERATOR-RUN cannot satisfy independent execution")
        if sub["execution_control"] == "ASSISTED" and sub["assistance"] == "NONE":
            reasons.append("ASSISTED without disclosed assistance")
        if sub["incentive_outcome_dependent"]:
            reasons.append("outcome-dependent incentive disqualifies")
        if binding != "FULL":
            reasons.append(f"binding {binding} (exact bytes not verified)")
        qualified = not reasons
        hist = store.history(aid)
        lineage = {"versions": len(hist),
                   "first_observed_at": min(h["submission"]["observed_at"] for h in hist),
                   "first_imported_at": min(h["provenance"]["imported_at"] for h in hist),
                   "superseded_at": rec["provenance"]["imported_at"] if rec["version"] > 1 else None,
                   "chain": [h["digest"] for h in hist]}
        out.append({"attempt_id": aid, "digest": d, "version": rec["version"], "submission": sub, "observation": obs, "review": rev,
                    "activity_type": sub.get("activity_type", "REPLICATION"), "corrected": rec["version"] > 1,
                    "binding_completeness": binding, "qualified": qualified, "reasons": reasons, "lineage": lineage,
                    "successful": qualified and sub["outcome"] == "REPRODUCED", "synthetic": rec["provenance"]["synthetic"]})
    return out


def _artifact_key(sub: dict) -> tuple:
    b = sub["artifact_binding"]; return (b["artifact_type"], b["sha256"], b["size_bytes"])


def classify(row: dict, reg: dict | None) -> dict:
    """Typed placement of a derived row: {key, eligibility, protocol_id, window}. Eligibility is a closed value —
    never inferred from the key text. Never reassigns a protocol; never backdates. The prospective admission
    contract is applied to the WHOLE lineage: the earliest observed and first-imported instants must be at or
    after the registration instant, the earliest observed date must be on or after the anchor, and the counting
    WINDOW is derived from that earliest observed date — a correction cannot promote an attempt by moving its
    timestamp and cannot move it into a later window (it is rendered CORRECTED inside its original window)."""
    sub = row["submission"]; pid = sub["protocol_id"]
    if reg is None:
        return {"key": "unwindowed", "eligibility": "unwindowed", "protocol_id": pid, "window": None}
    if pid != reg["protocol_id"]:
        return {"key": f"unregistered-protocol/{pid}", "eligibility": "other_protocol", "protocol_id": pid, "window": None}
    registered_at = parse_ts(reg["registered_at"], "registration.registered_at")
    observed = parse_ts(sub["observed_at"], "observed_at")
    lin = row.get("lineage") or {}
    earliest_obs = min(observed, parse_ts(lin["first_observed_at"], "lineage.first_observed_at")) if lin.get("first_observed_at") else observed
    earliest_imp = parse_ts(lin["first_imported_at"], "lineage.first_imported_at") if lin.get("first_imported_at") else None
    if earliest_obs < registered_at or (earliest_imp is not None and earliest_imp < registered_at):
        return {"key": f"{pid}/pre-registration", "eligibility": "pre_registration", "protocol_id": pid, "window": None}
    anchor = date.fromisoformat(reg["anchor"])
    if earliest_obs.date() < anchor:
        return {"key": f"{pid}/pre-anchor", "eligibility": "pre_anchor", "protocol_id": pid, "window": None}
    w = (earliest_obs.date() - anchor).days // WINDOW_DAYS          # PINNED to the original lineage: a correction never re-enters a later window
    return {"key": f"{pid}/w{w}", "eligibility": "prospective", "protocol_id": pid, "window": w}


def bucket(row: dict, reg: dict | None) -> str:
    return classify(row, reg)["key"]


def category_counts(derived: list[dict]) -> dict:
    """Per-activity-type derived counts (receipted = validated current submissions of that type; qualified =
    derived qualification). Internal test runs and unreceipted relationships are not records and never count."""
    out = {}
    for t in ("REPLICATION", "WITNESS_REVIEW", "AUDIT_BREAK_ATTEMPT", "REFUSAL"):
        rows = [r for r in derived if r["activity_type"] == t]
        q = [r for r in rows if r["qualified"]]
        by_outcome = {}
        for r in q:
            by_outcome[r["submission"]["outcome"]] = by_outcome.get(r["submission"]["outcome"], 0) + 1
        out[t] = {"receipted": len(rows), "qualified": len(q), "unqualified": len(rows) - len(q),
                  "distinct_persons_qualified": len({r["submission"]["participant_id"] for r in q}),
                  "qualified_by_outcome": by_outcome}
    return out


def counts(derived: list[dict], *, registration: dict | None = None) -> dict:
    """registration = validated owner adoption record when adopted; None → unwindowed (pending).
    The replication population (attempts/qualified/successful/windows/artifacts) covers REPLICATION receipts only;
    the other categories are summarized separately in `categories`."""
    reg = validate_registration(registration) if registration is not None else None
    all_rows = derived
    derived = [r for r in derived if r["activity_type"] == "REPLICATION"]
    attempts = len(derived)
    q = [r for r in derived if r["qualified"]]
    s = [r for r in q if r["successful"]]
    windows: dict[str, dict] = {}
    for bkt, rows in (("qualified", q), ("successful", s)):
        for r in rows:
            c = classify(r, reg)
            w = windows.setdefault(c["key"], {"eligibility": c["eligibility"], "qualified": {"persons": set(), "groups": set(), "attempts": 0}, "successful": {"persons": set(), "groups": set(), "attempts": 0}})
            w[bkt]["persons"].add(r["submission"]["participant_id"]); w[bkt]["attempts"] += 1
            if r["submission"]["group_id"]:
                w[bkt]["groups"].add(r["submission"]["group_id"])
    by_type = lambda rows: {t: len({_artifact_key(r["submission"]) for r in rows if r["submission"]["artifact_binding"]["artifact_type"] == t})
                            for t in sorted({r["submission"]["artifact_binding"]["artifact_type"] for r in rows})}
    by_protocol = {}
    for r in derived:
        p = by_protocol.setdefault(r["submission"]["protocol_id"], {"attempts": 0, "qualified": 0, "successful": 0})
        p["attempts"] += 1; p["qualified"] += int(r["qualified"]); p["successful"] += int(r["successful"])
    windows_out = {k: {"primary_distinct_persons": len(v["qualified"]["persons"]), "primary_distinct_groups": len(v["qualified"]["groups"]), "primary_attempts": v["qualified"]["attempts"],
                       "successful_distinct_persons": len(v["successful"]["persons"]), "successful_distinct_groups": len(v["successful"]["groups"]), "successful_attempts": v["successful"]["attempts"],
                       "eligibility": v["eligibility"], "prospective": v["eligibility"] == "prospective"}
                   for k, v in sorted(windows.items())}
    excluded = {"pre_registration": sum(v["primary_attempts"] for v in windows_out.values() if v["eligibility"] == "pre_registration"),
                "pre_anchor": sum(v["primary_attempts"] for v in windows_out.values() if v["eligibility"] == "pre_anchor"),
                "other_protocols": {k.split("/", 1)[1]: v["primary_attempts"] for k, v in windows_out.items() if v["eligibility"] == "other_protocol"},
                "note": "excluded from the prospective primary floor but retained and visible; never reassigned to another protocol; never backdated"}
    return {
        "attempts": attempts, "qualified": len(q), "successful": len(s),
        "visible": {"failed": sum(1 for r in derived if r["submission"]["outcome"] == "FAILED"),
                    "inconclusive": sum(1 for r in derived if r["submission"]["outcome"] == "INCONCLUSIVE"),
                    "qualified_failed": sum(1 for r in q if r["submission"]["outcome"] == "FAILED"),
                    "qualified_inconclusive": sum(1 for r in q if r["submission"]["outcome"] == "INCONCLUSIVE"),
                    "unqualified": attempts - len(q)},
        "by_protocol": by_protocol,
        "artifacts": {"successful_cohort_artifacts": len({_artifact_key(r["submission"]) for r in s}),
                      "attempted_artifacts": len({_artifact_key(r["submission"]) for r in derived}),
                      "verified_artifacts": len({_artifact_key(r["submission"]) for r in derived if r["binding_completeness"] == "FULL"}),
                      "attempted_by_type": by_type(derived), "successful_by_type": by_type(s),
                      "package_reproductions_successful": sum(1 for r in s if r["submission"]["artifact_binding"]["artifact_type"] in PACKAGE_ARTIFACTS),
                      "note": "successful_cohort_artifacts are the artifacts of successful qualified attempts — not all tested artifacts; site/endpoint/chain checks are not package reproductions"},
        "registration": ({"status": "REGISTERED", **reg, "window_days": WINDOW_DAYS,
                          "prospective_rule": "only attempts observed and first imported at or after registered_at, on or after the anchor, enter windows; the anchor never precedes the registration instant"}
                         if reg else {"status": "PENDING", "note": "no registration record adopted; counts are unwindowed"}),
        "windows": windows_out,
        "excluded_from_primary": excluded if reg else {"note": "not applicable without registration"},
        "corrected_attempts": sum(1 for r in derived if r["corrected"]),
        "categories": category_counts(all_rows),
        "policy_version": POLICY_VERSION,
    }


def movement(previous: dict | None, current: dict) -> dict:
    """Absolute movement between two count snapshots; never a multiplier (zero baseline → undefined)."""
    keys = ("attempts", "qualified", "successful")
    prev = previous or {}
    return {k: {"before": prev.get(k, 0), "after": current.get(k, 0), "delta": current.get(k, 0) - prev.get(k, 0),
                "growth_multiplier": "UNDEFINED (zero baseline)" if prev.get(k, 0) == 0 else round(current.get(k, 0) / prev[k], 3)} for k in keys}
