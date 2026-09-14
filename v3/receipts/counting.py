"""Derived state and honest counting (v7 receipts).

Qualification is DERIVED, never read from a submission: it needs (1) a validated current submission,
(2) an OBSERVATION with verified=True (FULL binding), (3) a trusted REVIEW in state QUALIFIED bound to
the CURRENT digest under the current policy version, (4) relationship not OWNER-AFFILIATED/UNKNOWN,
(5) execution SELF or ASSISTED (with disclosed assistance), (6) no outcome-dependent incentive.
A review is DESIGNATED or SYNTHETIC authority; real qualification requires DESIGNATED.

Populations (never summed together): attempts; qualified (incl. qualified FAILED/INCONCLUSIVE);
successful (qualified AND REPRODUCED); artifact sets (successful cohort's artifacts, attempted
artifacts, verified artifacts, by type — package types are separate from site/endpoint/chain).
Distinct persons/groups: primary = qualified attempts; successful reported separately; deduplicated
across activities/versions inside a registered window; without a registration anchor the counts are
UNWINDOWED (registration pending) — window zero is never fabricated.
"""
from __future__ import annotations

from datetime import date

from v3.receipts.contracts import (NON_QUALIFYING_RELATIONSHIPS, PACKAGE_ARTIFACTS, POLICY_VERSION, parse_ts, window_index)
from v3.receipts.store import Store


def derive(store: Store, *, synthetic: bool) -> list[dict]:
    """Derived view of CURRENT submissions whose provenance matches `synthetic`."""
    out = []
    for aid, rec in sorted(store.current_submissions().items()):
        if rec["provenance"]["synthetic"] != synthetic:
            continue
        sub = rec["submission"]; d = rec["digest"]
        obs = store.observation_for(d); rev = store.review_for(d)
        binding = "FULL" if (obs and obs.get("verified")) else ("UNVERIFIED" if obs else "NONE")
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
        out.append({"attempt_id": aid, "digest": d, "version": rec["version"], "submission": sub, "observation": obs, "review": rev,
                    "binding_completeness": binding, "qualified": qualified, "reasons": reasons,
                    "successful": qualified and sub["outcome"] == "REPRODUCED", "synthetic": rec["provenance"]["synthetic"]})
    return out


def _artifact_key(sub: dict) -> tuple:
    b = sub["artifact_binding"]; return (b["artifact_type"], b["sha256"], b["size_bytes"])


def counts(derived: list[dict], *, registration: dict | None = None) -> dict:
    """registration = {"protocol_id":..., "anchor": "YYYY-MM-DD"} when adopted; None → unwindowed."""
    attempts = len(derived)
    q = [r for r in derived if r["qualified"]]
    s = [r for r in q if r["successful"]]
    anchor = date.fromisoformat(registration["anchor"]) if registration else None
    def key(r):
        if anchor is None:
            return "unwindowed"
        return f"{registration['protocol_id']}/w{window_index(parse_ts(r['submission']['observed_at'], 'observed_at'), anchor)}"
    windows: dict[str, dict] = {}
    for bucket, rows in (("qualified", q), ("successful", s)):
        for r in rows:
            w = windows.setdefault(key(r), {"qualified": {"persons": set(), "groups": set()}, "successful": {"persons": set(), "groups": set()}})
            w[bucket]["persons"].add(r["submission"]["participant_id"])
            if r["submission"]["group_id"]:
                w[bucket]["groups"].add(r["submission"]["group_id"])
    by_type = lambda rows: {t: len({_artifact_key(r["submission"]) for r in rows if r["submission"]["artifact_binding"]["artifact_type"] == t})
                            for t in sorted({r["submission"]["artifact_binding"]["artifact_type"] for r in rows})}
    return {
        "attempts": attempts, "qualified": len(q), "successful": len(s),
        "visible": {"failed": sum(1 for r in derived if r["submission"]["outcome"] == "FAILED"),
                    "inconclusive": sum(1 for r in derived if r["submission"]["outcome"] == "INCONCLUSIVE"),
                    "qualified_failed": sum(1 for r in q if r["submission"]["outcome"] == "FAILED"),
                    "qualified_inconclusive": sum(1 for r in q if r["submission"]["outcome"] == "INCONCLUSIVE"),
                    "unqualified": attempts - len(q)},
        "artifacts": {"successful_cohort_artifacts": len({_artifact_key(r["submission"]) for r in s}),
                      "attempted_artifacts": len({_artifact_key(r["submission"]) for r in derived}),
                      "verified_artifacts": len({_artifact_key(r["submission"]) for r in derived if r["binding_completeness"] == "FULL"}),
                      "attempted_by_type": by_type(derived), "successful_by_type": by_type(s),
                      "package_reproductions_successful": sum(1 for r in s if r["submission"]["artifact_binding"]["artifact_type"] in PACKAGE_ARTIFACTS),
                      "note": "successful_cohort_artifacts are the artifacts of successful qualified attempts — not all tested artifacts; site/endpoint/chain checks are not package reproductions"},
        "registration": ({"status": "REGISTERED", **registration} if registration else {"status": "PENDING", "note": "no registration anchor adopted; counts are unwindowed"}),
        "windows": {k: {"primary_distinct_persons": len(v["qualified"]["persons"]), "primary_distinct_groups": len(v["qualified"]["groups"]),
                        "successful_distinct_persons": len(v["successful"]["persons"]), "successful_distinct_groups": len(v["successful"]["groups"])}
                    for k, v in sorted(windows.items())},
        "policy_version": POLICY_VERSION,
    }


def movement(previous: dict | None, current: dict) -> dict:
    """Absolute movement between two count snapshots; never a multiplier (zero baseline → undefined)."""
    keys = ("attempts", "qualified", "successful")
    prev = previous or {}
    return {k: {"before": prev.get(k, 0), "after": current.get(k, 0), "delta": current.get(k, 0) - prev.get(k, 0),
                "growth_multiplier": "UNDEFINED (zero baseline)" if prev.get(k, 0) == 0 else round(current.get(k, 0) / prev[k], 3)} for k in keys}
