"""Dataset coverage view and deterministic snapshot (V8-004 §4, workstream SET) — derived from stored records only.

A row is derived from one claim's state (versions, corrections, withdrawal, outcome, computed result, adjudications,
research notes, rights) plus the workspace's source-registration events (when each source was first observed). The
snapshot is the sorted set of rows with counts, coverage gaps and known omissions; its identity is the sha256 of its
canonical JSON, which excludes any generation time, so the same records reproduce the same identity. Nothing here
invents an issuer, a result or a count: an empty workspace yields an empty snapshot. Eligibility is not computed here —
it is whatever eligibility note (an attribution-labelled research note) the workspace holds, or NOT_RECORDED.
Research and education only. Not investment advice.
"""
from __future__ import annotations

import hashlib
import json

from v3.receipts.contracts import canonical_json
from v8.workbench import NOT_ADVICE, WORKBENCH_VERSION, availability, calc, schema

DATASET_SCHEMA = "yuclaw-commitment-dataset/1"
METHOD = {"calculator": calc.CALCULATOR, "claim_schema": schema.SCHEMA, "outcome_schema": schema.OUTCOME_SCHEMA, "dataset_schema": DATASET_SCHEMA, "workbench": WORKBENCH_VERSION,
          "comparison_limits": "a comparison is supported only when metric, currency, unit, accounting basis and fiscal period are identical; the resolution rule is RANGE_CONTAINS_ACTUAL over exact amounts in units; original-range and revised-range evaluations are separate and never combined into a skill claim"}
KNOWN_OMISSIONS = [
    "the dataset holds only commitments registered in this workspace; it is not an issuer universe, a market dataset or a sample of anything",
    "eligibility is an attribution-labelled note recorded in the workspace, not a criteria run; the selection criteria are applied outside the workbench",
    "retrospective rows are reconstructions from source availability timestamps, observed after the outcome was public; they are not prospective evidence",
    "source availability precision is second-level for EDGAR acceptance timestamps and as entered by the registrar otherwise; the workbench does not verify a publisher's clock",
    "reviewer labels are attribution, not authenticated identity or independent review; automated actions are identified as simulated tests",
    "excerpt bytes are withheld wherever rights do not allow redistribution; digests remain",
    "no market prices, returns, forecasts or financial performance are recorded; no commercial dataset of established quality, prospective evidence or user benefit is claimed",
    "backup creation and restoration are not provided in 8.0.0; a snapshot is not a backup",
]
RUNNER_MARK = "automated test action"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def availability_precision(src: dict) -> str:
    if src.get("kind") == "filing":
        return "second (EDGAR acceptance timestamp)"
    return "as entered by the registrar (publisher dateline or stated time; clock precision not verified by the workbench)"


def _source_row(src: dict, seen: dict) -> dict:
    sid = f"{src['accession']}:{src['source_hash'][:16]}"
    return {"source_id": sid, "kind": src["kind"], "form": src["form"], "accession": src["accession"], "url": src.get("url"), "filed_at": src["filed_at"],
            "available_as_of": src["available_as_of"], "availability_precision": availability_precision(src), "observed_at": seen.get(sid), "rights": src["rights"],
            "fictional": src["fictional"], "excerpt_included": src["rights"] in ("FICTIONAL", "SEC_PUBLIC_FILING"), "source_hash": src["source_hash"]}


def retrospective(state: dict) -> dict:
    """RETROSPECTIVE when every source was first observed after the latest source became public (and an outcome exists)."""
    if state.get("outcome") is None:
        return {"retrospective": False, "reason": "no outcome recorded; the replay status is undetermined until an outcome exists"}
    evs = [e for e in state["events"] if e.get("kind") != "SOURCE_REGISTERED"]                    # claim-scoped events only (the store's and the verifier's common view)
    avail = [schema.parse_ts(e["time"]["source_available_as_of"]) for e in evs if e["time"].get("source_available_as_of")]
    observed = [schema.parse_ts(e["time"]["observed_at"]) for e in evs if e["time"].get("source_available_as_of")]
    if avail and observed and min(observed) > max(avail):
        return {"retrospective": True, "reason": f"every source first observed {min(observed).strftime('%Y-%m-%d')}, after the latest source became public {max(avail).strftime('%Y-%m-%d')}"}
    return {"retrospective": False, "reason": "at least one source was observed no later than the latest source availability"}


def build_row(state: dict, seen: dict | None = None) -> dict:
    """One dataset row for one claim state. `seen` maps source_id → observed_at from the workspace's SOURCE_REGISTERED events."""
    seen = seen or {}
    res = calc.adjudicate(state)
    versions = state["versions"]; original = versions[0]["claim"]
    orig_eff = next((v for v in reversed(versions) if v["type"] == "CORRECTED_SOURCE"), versions[0])
    revised = [v for v in versions if v["type"] == "REVISED"]
    comparison = calc.compare_versions(orig_eff["claim"], revised[-1]["claim"]) if revised else None
    notes = state.get("research_notes", []); current_notes = state.get("research_notes_current", [])
    elig = [n for n in current_notes if n["category"] == "eligibility"]
    adjs = state.get("adjudications", [])
    vrows = [{"version_id": v["version_id"], "type": v["type"], "claim_digest": v["claim"]["_digest"], "supersedes": v.get("supersedes"), "reason": v.get("reason"), "stated_at": v["claim"]["stated_at"],
              "range": v["claim"]["range"], "currency": v["claim"]["currency"], "unit": v["claim"]["unit"], "basis": v["claim"]["basis"], "metric": v["claim"]["metric"], "fiscal_period": v["claim"]["fiscal_period"],
              "version_notes": v.get("notes"), "source": _source_row(v["claim"]["source"], seen), "recorded_at": v["time"]["recorded_at"]} for v in versions]
    sources = [r["source"] for r in vrows]
    if state.get("withdrawn"):
        sources.append(_source_row(state["withdrawn"]["source"], seen))
    if state.get("outcome"):
        sources.append(_source_row(state["outcome"]["source"], seen))
    withheld = sorted({s["source_id"] for s in sources if not s["excerpt_included"]})
    retro = retrospective(state)
    gaps = []
    if state.get("outcome") is None:
        gaps.append("no outcome recorded (PENDING_OUTCOME)")
    if state.get("withdrawn"):
        gaps.append("withdrawn")
    if comparison is not None and not comparison["comparable"]:
        gaps.append("comparison INCOMPARABLE: " + "; ".join(r["reason"] for r in comparison["reasons"]))
    if not adjs:
        gaps.append("no adjudication recorded")
    if withheld:
        gaps.append(f"excerpt withheld by rights for {len(withheld)} source(s)")
    if retro["retrospective"]:
        gaps.append("retrospective replay (sources observed after the outcome was public)")
    if not elig and not original["fictional"]:
        gaps.append("eligibility not recorded in this workspace")
    if res["result"] in calc.UNRESOLVED:
        gaps.append(f"result unresolved: {res['result']}")
    corrected = availability.row_block(state)                        # None unless a cited source's availability was corrected: an uncorrected row keeps its earlier bytes
    if corrected is not None:
        gaps.append("source availability corrected after registration" + (": the corrected view needs review (" + ", ".join(sorted({r["code"] for r in corrected["review"]})) + ")" if corrected["needs_review"] else " (the corrected view computes the same result)"))
    row = {"claim_id": state["claim_id"], "issuer": original["issuer"], "metric": original["metric"], "fiscal_period": original["fiscal_period"],
           "identifiers": {"claim_id": state["claim_id"], "versions": [v["version_id"] for v in versions], "current_version": state["current"]["version_id"], "original_digest": original["_digest"], "current_digest": state["current"]["claim"]["_digest"]},
           "status": {"fictional": bool(original["fictional"]), "retrospective": retro["retrospective"], "retrospective_reason": retro["reason"],
                      "eligibility": elig[-1]["reason"] if elig else "NOT_RECORDED", "eligibility_note": elig[-1]["note_id"] if elig else None, "eligibility_actor": elig[-1]["actor"] if elig else None},
           "original_target": {"version_id": versions[0]["version_id"], "range": original["range"], "currency": original["currency"], "unit": original["unit"], "basis": original["basis"], "scale_as_stated": original["scale_as_stated"]},
           "revisions": [{"version_id": v["version_id"], "range": v["claim"]["range"], "reason": v.get("reason"), "supersedes": v.get("supersedes"), "notes": v.get("notes")} for v in revised],
           "source_corrections": [{"version_id": v["version_id"], "reason": v.get("reason"), "supersedes": v.get("supersedes")} for v in versions if v["type"] == "CORRECTED_SOURCE"],
           "withdrawal": None if not state.get("withdrawn") else {"revision_id": state["withdrawn"]["revision_id"], "reason": state["withdrawn"]["reason"], "available_as_of": state["withdrawn"]["source"]["available_as_of"]},
           "outcome": None if not state.get("outcome") else {"actual": state["outcome"]["actual"], "currency": state["outcome"]["currency"], "unit": state["outcome"]["unit"], "basis": state["outcome"]["basis"], "fiscal_period": state["outcome"]["fiscal_period"], "comparable_declared": state["outcome"]["comparable"], "outcome_digest": state["outcome"]["_digest"], "available_as_of": state["outcome"]["source"]["available_as_of"]},
           "computed": {"result": res["result"], "original": res["original"]["result"] if res.get("original") else None, "revised": None if not res.get("revised") else res["revised"]["result"], "comparison": None if comparison is None else comparison["result"], "comparison_direction": None if comparison is None or not comparison["comparable"] else comparison["direction"], "comparison_permitted": res.get("comparison_permitted")},
           "reviewer": {"labels": [{"reviewer": a["reviewer"], "label": a["label"], "computed": a["computed_result"], "disputed": a["disputed"], "recorded_at": a["time"]["recorded_at"], "attribution": "simulated test action" if RUNNER_MARK in a["reviewer"] else "attribution label (not authenticated; not independent review)"} for a in adjs],
                        "disagreement": [{"reviewer": a["reviewer"], "label": a["label"], "computed": a["computed_result"], "conflicts": a["conflicts"]} for a in adjs if a["disputed"] or a["label"] != a["computed_result"]]},
           "unresolved_reasons": [r["reason"] if isinstance(r, dict) else str(r) for r in res.get("reasons", [])],
           "research_notes": {"count": len(notes), "current": len(current_notes), "corrections": len([n for n in notes if n.get("supersedes_note")]), "by_category": {c: len([n for n in current_notes if n["category"] == c]) for c in schema.NOTE_CATEGORIES if any(n["category"] == c for n in current_notes)},
                              "latest": [{"note_id": n["note_id"], "category": n["category"], "actor": n["actor"], "actor_kind": n["actor_kind"], "recorded_at": n["time"]["recorded_at"], "version_ref": n["version_ref"]} for n in current_notes[-3:]]},
           "sources": sources, "rights": {"withheld_excerpts": withheld, "rights_present": sorted({s["rights"] for s in sources})},
           "calculation": {"rule": res["rule"], "rule_text": res["rule_text"], "formula": calc.FORMULA, "currency": state["current"]["claim"]["currency"], "unit": state["current"]["claim"]["unit"], "comparison_limits": METHOD["comparison_limits"], "no_inference": calc.NO_INFERENCE},
           "versions": vrows, "coverage_gaps": gaps}
    if corrected is not None:
        row["availability_corrections"] = corrected                  # the fields above stay as recorded; the corrected view sits beside them
    row["row_digest"] = _sha(canonical_json(row))
    return row


def build_snapshot(ws) -> dict:
    """The workspace's dataset snapshot, derived from stored records. Deterministic: no generation time inside."""
    events = ws.events()
    seen = {e["payload"]["source_id"]: e["time"]["observed_at"] for e in events if e["kind"] == "SOURCE_REGISTERED"}
    rows = []
    for cid in sorted(ws.claim_ids(events)):
        st = ws.claim_state(cid)
        if st is not None:
            rows.append(build_row(st, seen))
    return finish_snapshot(rows, ws.meta["workspace_id"])


def finish_snapshot(rows: list[dict], workspace_id: str | None) -> dict:
    counts = {"claims": len(rows), "issuers": len({r["issuer"]["cik"] for r in rows}), "with_outcome": sum(1 for r in rows if r["outcome"]), "adjudicated": sum(1 for r in rows if r["reviewer"]["labels"]),
              "withdrawn": sum(1 for r in rows if r["withdrawal"]), "incomparable": sum(1 for r in rows if r["computed"]["comparison"] == "INCOMPARABLE"), "fictional": sum(1 for r in rows if r["status"]["fictional"]),
              "real_source": sum(1 for r in rows if not r["status"]["fictional"]), "retrospective": sum(1 for r in rows if r["status"]["retrospective"]), "eligibility_recorded": sum(1 for r in rows if r["status"]["eligibility"] != "NOT_RECORDED"),
              "research_notes": sum(r["research_notes"]["count"] for r in rows), "sources": sum(len(r["sources"]) for r in rows), "withheld_excerpts": sum(len(r["rights"]["withheld_excerpts"]) for r in rows)}
    gaps = sorted({g for r in rows for g in r["coverage_gaps"]})
    snap = {"schema": DATASET_SCHEMA, "workspace_id": workspace_id, "method": METHOD, "rows": rows, "counts": counts, "coverage_gaps": gaps, "known_omissions": KNOWN_OMISSIONS,
            "empty": not rows, "meaning": "rows are derived from the workspace's stored records at the time of derivation; an empty workspace has empty coverage", "not_advice": NOT_ADVICE}
    return snap


def snapshot_digest(snap: dict) -> str:
    return _sha(canonical_json(snap))


def diff_snapshots(prev: dict | None, cur: dict) -> dict:
    """What changed between two snapshots, by claim and top-level row field (nothing is overwritten; both remain)."""
    if prev is None:
        return {"previous": None, "added": [r["claim_id"] for r in cur["rows"]], "removed": [], "changed": {}}
    p = {r["claim_id"]: r for r in prev.get("rows", [])}; c = {r["claim_id"]: r for r in cur["rows"]}
    changed = {}
    for cid in sorted(set(p) & set(c)):
        fields = sorted(k for k in set(p[cid]) | set(c[cid]) if k != "row_digest" and json.dumps(p[cid].get(k), sort_keys=True) != json.dumps(c[cid].get(k), sort_keys=True))
        if fields:
            changed[cid] = fields
    return {"previous": snapshot_digest(prev), "added": sorted(set(c) - set(p)), "removed": sorted(set(p) - set(c)), "changed": changed}
