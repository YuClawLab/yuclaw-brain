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
        elif rev.get("authority") != "DESIGNATED" and not synthetic:
            reasons.append("review authority not designated (real qualification pending)")
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
                   "first_imported_at": min(h["provenance"]["imported_at"] for h in hist)}
        out.append({"attempt_id": aid, "digest": d, "version": rec["version"], "submission": sub, "observation": obs, "review": rev,
                    "binding_completeness": binding, "qualified": qualified, "reasons": reasons, "lineage": lineage,
                    "successful": qualified and sub["outcome"] == "REPRODUCED", "synthetic": rec["provenance"]["synthetic"]})
    return out


def _artifact_key(sub: dict) -> tuple:
    b = sub["artifact_binding"]; return (b["artifact_type"], b["sha256"], b["size_bytes"])


def bucket(row: dict, reg: dict | None) -> str:
    """Where a derived row is counted. Never reassigns a protocol; never backdates."""
    sub = row["submission"]
    if reg is None:
        return "unwindowed"
    if sub["protocol_id"] != reg["protocol_id"]:
        return f"unregistered-protocol/{sub['protocol_id']}"
    registered_at = parse_ts(reg["registered_at"], "registration.registered_at")
    observed = parse_ts(sub["observed_at"], "observed_at")
    lin = row.get("lineage") or {}
    earliest_obs = min(observed, parse_ts(lin["first_observed_at"], "lineage.first_observed_at")) if lin.get("first_observed_at") else observed
    earliest_imp = parse_ts(lin["first_imported_at"], "lineage.first_imported_at") if lin.get("first_imported_at") else None
    if earliest_obs < registered_at or (earliest_imp is not None and earliest_imp < registered_at):
        return f"{reg['protocol_id']}/pre-registration"
    anchor = date.fromisoformat(reg["anchor"])
    if observed.date() < anchor:
        return f"{reg['protocol_id']}/pre-anchor"
    return f"{reg['protocol_id']}/w{(observed.date() - anchor).days // WINDOW_DAYS}"


def counts(derived: list[dict], *, registration: dict | None = None) -> dict:
    """registration = validated owner adoption record when adopted; None → unwindowed (pending)."""
    reg = validate_registration(registration) if registration is not None else None
    attempts = len(derived)
    q = [r for r in derived if r["qualified"]]
    s = [r for r in q if r["successful"]]
    windows: dict[str, dict] = {}
    for bkt, rows in (("qualified", q), ("successful", s)):
        for r in rows:
            w = windows.setdefault(bucket(r, reg), {"qualified": {"persons": set(), "groups": set(), "attempts": 0}, "successful": {"persons": set(), "groups": set(), "attempts": 0}})
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
                       "prospective": bool(reg) and "/w" in k}
                   for k, v in sorted(windows.items())}
    excluded = {"pre_registration": sum(v["primary_attempts"] for k, v in windows_out.items() if k.endswith("/pre-registration")),
                "pre_anchor": sum(v["primary_attempts"] for k, v in windows_out.items() if k.endswith("/pre-anchor")),
                "other_protocols": {k.split("/", 1)[1]: v["primary_attempts"] for k, v in windows_out.items() if k.startswith("unregistered-protocol/")},
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
        "policy_version": POLICY_VERSION,
    }


def movement(previous: dict | None, current: dict) -> dict:
    """Absolute movement between two count snapshots; never a multiplier (zero baseline → undefined)."""
    keys = ("attempts", "qualified", "successful")
    prev = previous or {}
    return {k: {"before": prev.get(k, 0), "after": current.get(k, 0), "delta": current.get(k, 0) - prev.get(k, 0),
                "growth_multiplier": "UNDEFINED (zero baseline)" if prev.get(k, 0) == 0 else round(current.get(k, 0) / prev[k], 3)} for k in keys}
