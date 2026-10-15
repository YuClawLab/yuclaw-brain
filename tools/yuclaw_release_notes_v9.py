#!/usr/bin/env python3
"""Tier-2 (public) release-notes composition for 9.0.0, bound to the recorded release policy (the v8 composer's
interface, mirrored: compose() and check_correspondence()). Inputs are read from the tree, never typed:
  * the machine-readable release scope      — v9/scope/v9.0.0-scope.json (enabled features, deferred, excluded, fixture)
  * the recorded candidate evidence          — the newest v9/V9-*/scorecard.json (test counts per runtime, the installed
                                               self-check, the browser inspection, the clean-install record when present)
  * the owner's Gate #15 decision for 9.x    — v9/policy/gate15_release_requirement.json, IF the owner records one; the
                                               8.x removal is NOT carried over (no version-specific exception travels)
Version support: 9.0.0 (the major release) and 9.1.0, a MINOR release of the 9.0 line (SUPPORTED_VERSIONS). A minor release keeps
the 9.0.0 feature scope file (F1–F5) and ADDS functionality and/or a prospective rule change, both named in a TRACKED change list
(docs/methodology/release_notes_<v>_changes.md); it is described as a minor release, never as a patch (a patch is defect repairs
only — no methodology, registration or functionality change — and the 9.x line has none). Gate #15 never travels between versions: each version needs the owner's OWN decision
record (v9/policy/gate15_release_requirement.json for 9.0.0; v9/policy/gate15_release_requirement_<v>.json for a later version);
without it the notes say so and cannot correspond. Nothing here authorizes publication; an empty correspondence list means the
notes match the RECORDED policy, no more."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
SUPPORTED_VERSIONS = ("9.0.0", "9.1.0")
PATCH_OF = {}                                      # patch release → the release whose frozen scope it keeps (defect repairs only; the 9.x line has none)
MINOR_OF = {"9.1.0": "9.0.0"}                      # minor release → the release whose feature scope (F1–F5) it keeps while adding functionality / a prospective rule
CHANGE_LIST_OF = {**PATCH_OF, **MINOR_OF}          # every version that carries a tracked change list
SCOPE_PATH = _REPO / "v9" / "scope" / "v9.0.0-scope.json"
GATE15_DECISION = _REPO / "v9" / "policy" / "gate15_release_requirement.json"          # the owner's 9.0.0-only decision


def gate15_decision_path(version: str) -> Path:
    """The tracked decision record that may apply to THIS version: 9.0.0 keeps its original file; any later version has its own file
    (v9/policy/gate15_release_requirement_<version>.json) — an exception recorded for one version is never read for another."""
    return GATE15_DECISION if version == "9.0.0" else _REPO / "v9" / "policy" / f"gate15_release_requirement_{version}.json"
EXPECTED_FEATURES = ("F1", "F2", "F3", "F4", "F5")
FEATURE_LINES = {
    "F1": "- Sentence and claim inspection (F1): every recorded statement is bound to an exact UTF-8 byte span of its text view and to the specific v8 claim version it uses; six roles (direct quotation, computed statement, attributed source statement, analyst interpretation, model-written commentary, unresolved claim) describe function, not correctness; a four-area inspector (sources and calculations · how the text was produced · changes · checks) and five independent answers per statement (byte integrity · recorded origin · issuer trust · substantive support · time scope) that are never merged into a score; exact quotations and registered arithmetic are decided deterministically, an operator's or model's link is ATTRIBUTED, contradictions and unresolved statements are preserved; coverage is stated over identified statements with extraction completeness NOT established.",
    "F2": "- Financial brief composer (F2): briefs rendered from a stable, digest-identified evidence snapshot by deterministic bilingual templates (guidance change · numerical comparison · explicitly unresolved interpretation) that protect typed amounts, signs, currencies, units, metrics, bases, periods, accessions and quotations as slots over the v8 Decimal calculator; imported drafts are a separate route whose sentences start unassessed; raw and assembled bytes are distinct identities; a changed protected fact cannot keep its support; no API key, model download or hosted service is required.",
    "F3": "- Edits, translations and source corrections (F3): every saved revision is a new immutable version with a parent reference and a transform record (kind, implementation, languages, exact-bytes span mapping, review findings); the original is preserved beside the revision; a parent's checks never carry to the child's bytes; a deterministic template re-rendering binds the other language fully, an entered translation records its provenance, is never sent to a provider and carries no certification claim; a corrected v8 source or an amended claim produces review items on exactly the statements whose recorded dependencies reference it, while earlier exports stay valid historical snapshots.",
    "F4": "- Provenance records and detector-report import (F4): generation receipts, detector reports and calibration records are imported through a bounded parser (duplicate keys, floats, depth and size refused), bound to the exact text view and tested span, and kept apart by origin (operator assertion · connector observation · issuer-signed statement); signature validity, issuer trust under this workspace's own roots, revocation and payload binding are four separate answers; execution, signal (only when COMPLETED) and calibration (APPLICABLE only in the enrolled record's own scope, from an authenticated record) are separate dimensions; an unavailable account, unsupported input, too-short input or failure never becomes NOT_DETECTED; no live detector or provider connector exists in 9.0.",
    "F5": "- Portable verification and measured operations (F5): a readable static HTML brief (no script, CSP), JSON records and a versioned packet (yuclaw.brief-packet/1) verify in a fresh workspace without the author's database; every check is declared separately (VERIFIED · FAILED · NOT_RECOMPUTABLE · REPORT_ONLY · UNSUPPORTED · NOT_APPLICABLE); rights filtering withholds excerpts, prompts and raw responses whose disclosure is not established; keys, secrets and local paths never travel; operation identifiers, attempts, retries, outcomes and durations are measured from the first run with their definitions and missingness, and a methods/limitations appendix is derived from the records.",
}
DETECTOR_NOTE = ("- Detector and watermark evidence: NOT_DETECTED never proves human authorship; a detector score is not the percentage of text written by AI; a watermark establishes neither identity, ownership, responsibility nor factual accuracy; "
                 "a local receipt is neither legal compliance nor an independently anchored timestamp; an imported provider-positive result with unknown calibration is a provider-reported result whose calibration is not established here.")
CONNECTOR_NOTE = "- Deferred, not in 9.0 (explicitly later work, not incomplete core): {deferred}. No public text-detection endpoint, watermark parameter, key or provider capability is invented; no OpenAI-compatible watermark claim is made; primary evidence is never altered to carry a watermark."
BENEFIT_NOTE = "- Human benefit: PENDING — no pilot, no user study; the journeys and tests demonstrate behaviour, not benefit."
REVIEW_NOTE = "- Review: every edit, link, resolution and import in the release evidence was recorded by the automated tests, the installed self-check and the browser inspection as a simulated action; there was no human review and no user study."
FIXTURE_NOTE = "- Fixtures are clearly fictional demonstration data (issuer, filings, amounts); the fictional guidance example is never market data or a historical research record."
OWNER_EXCLUSIONS_NOTE = "- Excluded by the owner: {excluded}."
V8_NOTE = "- The v8 workbench, its four modules, its export format and its published guides are unchanged; v9 writes a separate sidecar beside the v8 journal and an 8.0.1 client reads its own data with the sidecar present and untouched."


def _load(p: Path) -> dict:
    return json.loads(p.read_text())


def latest_scorecard(root: Path | None = None) -> Path | None:
    recs = sorted((d for d in ((root or _REPO) / "v9").glob("V9-[0-9][0-9][0-9]") if (d / "scorecard.json").exists()), key=lambda d: d.name)
    return recs[-1] / "scorecard.json" if recs else None


def clean_install_failed_checks(scorecard_path: Path | None) -> list[str]:
    """The failing check names of the candidate's clean-install record beside its scorecard (empty when none or all passed):
    the public line names what failed on the pre-freeze candidate instead of a bare FAIL."""
    if scorecard_path is None or not (scorecard_path.parent / "clean_install_packaging.json").exists():
        return []
    rec = _load(scorecard_path.parent / "clean_install_packaging.json")
    return sorted({k for v in (rec.get("installs") or {}).values() for k, ok in (v.get("checks") or {}).items() if not ok})


def gate15_decision(path: Path | None = None, version: str = "9.0.0") -> dict | None:
    """The owner's recorded decision for THIS version (with its sha256) or None. A record claiming anything but an explicit
    EXCEPTION_ACCEPTED / MANUAL_REVIEW decision for exactly this version is refused; the 8.x record is never read here and the
    9.0.0 exception is never read for a later version: a version-specific exception does not travel."""
    path = gate15_decision_path(version) if path is None else path
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    if (d.get("record") != "yuclaw-v9-release-requirement-decision/1" or d.get("gate") != 15 or d.get("decided_by") != "owner" or d.get("status") != "EXCEPTION_ACCEPTED" or d.get("gate_result") != "MANUAL_REVIEW"
            or str(d.get("applies_to", {}).get("versions", "")) != f"{version} only" or d.get("applies_to", {}).get("carried_to_later_releases") is not False or not d.get("decision_text_verbatim")
            or (d.get("study") or {}).get("represented_as_passed") is not False):
        raise ValueError(f"gate 15 decision record is not the owner's EXCEPTION_ACCEPTED / MANUAL_REVIEW decision for {version} only")
    return {**d, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def capability_matrix(*, scope: dict | None = None, scorecard: dict | None = None) -> dict:
    if scope is None:
        scope = _load(SCOPE_PATH)
    failed_clean = []
    if scorecard is None:
        p = latest_scorecard(); scorecard = _load(p) if p else {}; failed_clean = clean_install_failed_checks(p)
    enabled = list(scope["enabled_features"])
    if tuple(enabled) != EXPECTED_FEATURES:
        raise ValueError(f"enabled features {enabled} are not the five mandatory features {EXPECTED_FEATURES}")
    runs = scorecard.get("runs") or {}
    demonstrated = bool(runs) and all(r.get("result") == "PASS" for r in runs.values()) and scorecard.get("ui_inspection") == "PASS" and scorecard.get("selftest") == "PASS"
    return {"version": scope["release"], "enabled": enabled, "names": scope["feature_names"], "deferred": list(scope["deferred"]), "excluded": list(scope["excluded_by_owner"]),
            "backup_disclosure": scope["backup_policy"]["disclosure"], "fixture": scope["fixture"], "evidence": scorecard, "demonstrated": demonstrated, "candidate": scorecard.get("candidate"), "clean_install_failed_checks": failed_clean}


def feature_account(m: dict) -> str:
    lines = [FEATURE_LINES[f] for f in m["enabled"]]
    ev = m["evidence"]; runs = ev.get("runs") or {}
    if runs:
        summary = "; ".join(f"{k}: {v.get('passed')}/{v.get('total')} {v.get('result')}" for k, v in runs.items())
        failed = m.get("clean_install_failed_checks") or []
        clean = f"clean install {ev.get('clean_install', 'NOT RUN')}" + (f" on that pre-freeze candidate ({', '.join(x.replace('_', ' ') for x in failed)}); the final pair is verified from fresh installs before any publication" if failed else "")
        lines.append((f"- Candidate evidence (candidate {str(m['candidate'] or 'unrecorded')[:12]}): {summary}; installed self-check {ev.get('selftest')}; browser inspection {ev.get('ui_inspection')}; {clean}."
                      if m["demonstrated"] else f"- Candidate evidence INCOMPLETE (candidate {str(m['candidate'] or 'unrecorded')[:12]}): {summary}; installed self-check {ev.get('selftest')}; browser inspection {ev.get('ui_inspection')}."))
    else:
        lines.append("- Candidate evidence INCOMPLETE: no scorecard recorded.")
    return "\n".join(lines)


GATE15_ROUTE = "EXCEPTION_9_0_0"                                       # the 9.0.0 route word (kept for the published 9.0.0 record)
PATCH_SCOPE_NOTE = "- {version} keeps the frozen {scope_version} scope: every statement below is that scope's own wording and applies to {version} unchanged."
MINOR_SCOPE_NOTE = "- {version} keeps the frozen {scope_version} feature scope (F1–F5): every statement below is that scope's own wording; what {version} adds or changes is listed under Changed above."
MINOR_HEADER = ("#### Changed in {version} — minor release: adds the point-in-time `research-export` command and the prospective SourceLock R10 evidence-admission rule, "
                "and corrects research verification and public evidence text (9.0.0 feature scope F1–F5 kept; no statistic, threshold or historical result changed)")


def gate15_route(version: str) -> str:
    """The typed policy route word for an explicit one-version exception: EXCEPTION_9_0_0, EXCEPTION_9_0_1, …"""
    return "EXCEPTION_" + version.replace(".", "_")


def gate15_line(policy: dict | None, decision: dict | None, version: str = "9.0.0") -> str:
    """The Gate #15 disclosure: the owner's explicit one-version exception for THIS version, verbatim, bound by record hash; the gate
    stays MANUAL_REVIEW and is never described as passed. Without a decision for this version the line says so (the 9.0.0
    exception and the 8.x removal do not carry over)."""
    if decision is None:
        return (f"- Gate #15 (user comprehension test passes): NO owner decision is recorded for {version}; the 8.x removal and the 9.0.0-only exception do not carry over; the gate stands at MANUAL_REVIEW; "
                "no human comprehension study was run, none is scheduled and none is claimed — not a pass; the automated consumer-posture scaffold check is retained; human benefit PENDING")
    ref = (policy or {}).get("gate15", {}).get("decision_record_sha256") or decision.get("sha256") or ""
    verbatim = decision["decision_text_verbatim"].replace("\n", "\n  ")
    return (f"- Gate #15 (user comprehension test passes): MANUAL_REVIEW — requirement NOT satisfied; the owner accepted an explicit release-policy exception for {version} only on {decision.get('decision_utc', 'date not recorded')} "
            f"(decision record sha256 {ref[:16]}…); not carried to any later release; no human comprehension study was run, scheduled or recruited and none is claimed — not a pass; the automated consumer-posture scaffold check is retained; human benefit PENDING. "
            f"The owner's decision, verbatim:\n  {verbatim}")


def policy_disclosure(policy: dict | None, decision: dict | None, version: str = "9.0.0") -> str:
    if not policy:
        return "- Release policy: NOT RECORDED — owner decision D1 (allocation) is pending; these notes are a draft and are not publishable until the policy record exists\n" + gate15_line(None, decision, version)
    al = policy.get("allocation", {})
    return "\n".join([f"- Allocation: decision {al.get('decision', 'unknown')} on allocation document `{al.get('document_id', 'unknown')}` (sha256 {al.get('sha256', '')[:16]}…)", gate15_line(policy, decision, version)])


def not_in_this_release(m: dict, tail: str) -> str:
    lines = [f"- {m['backup_disclosure']}", OWNER_EXCLUSIONS_NOTE.format(excluded=", ".join(x.replace("_", " ") for x in m["excluded"])), BENEFIT_NOTE, REVIEW_NOTE, FIXTURE_NOTE, DETECTOR_NOTE,
             CONNECTOR_NOTE.format(deferred=", ".join(x.replace("_", " ") for x in m["deferred"])), V8_NOTE]
    return "\n".join(lines) + "\n" + tail.strip("\n")


def compose(v6_style_public: str, *, version: str, policy: dict | None, board: dict | None, matrix: dict | None = None, patch_changes: str | None = None) -> str:
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"version {version} has no 9.x notes composition path (supported: {', '.join(SUPPORTED_VERSIONS)})")
    scope_version = CHANGE_LIST_OF.get(version, version)
    if version in CHANGE_LIST_OF and not (patch_changes or "").strip():
        raise ValueError(f"{version} carries a tracked change list ({'patch' if version in PATCH_OF else 'minor'} release): the list is required")
    if version not in CHANGE_LIST_OF and patch_changes:
        raise ValueError(f"{version} is a major release: there is no change list")
    import sys
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    sys.path.insert(0, str(_REPO / "tools"))
    from v3.release import notes_v7
    import yuclaw_release_notes_v8 as n8
    m = matrix or capability_matrix(); dec = gate15_decision(version=version)
    if m["version"] != scope_version:
        raise ValueError(f"scope release {m['version']} != {scope_version} (the scope of version {version})")
    head, rest = v6_style_public.split("#### Shipped objects", 1)
    objects, tail = rest.split("#### Not in this release", 1)
    objects = objects.split("\n", 1)[1].strip("\n")
    activations = n8.activation_status(policy).replace("requirement removed by the owner for v8 releases — not a pass", f"explicit owner exception for {version} only, MANUAL_REVIEW — not a pass" if dec else f"no owner decision recorded for {version}, MANUAL_REVIEW — not a pass")
    if version in PATCH_OF:
        new = [f"#### Changed in {version} — corrective release: research-verification and public-evidence corrections (scope unchanged; one prospective evidence-admission rule registered; no statistic, threshold or historical result changed)", "", patch_changes.strip("\n"), "",
               f"#### In the 9.0 line since {scope_version} — research briefs with traceable AI assistance (local, loopback only; scope unchanged)", "", feature_account(m), ""]
    elif version in MINOR_OF:
        new = [MINOR_HEADER.format(version=version), "", patch_changes.strip("\n"), "",
               f"#### In the 9.0 line since {scope_version} — research briefs with traceable AI assistance (local, loopback only; feature scope F1–F5 kept)", "", feature_account(m), ""]
    else:
        new = [f"#### New in {version} — research briefs with traceable AI assistance (local, loopback only)", "", feature_account(m), ""]
    parts = [head.rstrip("\n"), "", *new,
             "#### Evidence totals (public scoreboard at composition)", "", notes_v7.evidence_totals(board), "",
             "#### Activation status (every proposed activation)", "", activations, "",
             "#### Release policy (recorded; the publisher refuses notes that do not match the record)", "", policy_disclosure(policy, dec, version), "",
             "#### Continuing objects (unchanged from 8.0.1) — name · receipt · status", "", objects, "",
             "#### Not in this release", "", *([PATCH_SCOPE_NOTE.format(version=version, scope_version=scope_version)] if version in PATCH_OF else [MINOR_SCOPE_NOTE.format(version=version, scope_version=scope_version)] if version in MINOR_OF else []), not_in_this_release(m, tail), ""]
    return "\n".join(parts)


def check_correspondence(notes: str, policy: dict | None, matrix: dict | None = None, decision: dict | None = None) -> list[str]:
    problems = []
    if not policy:
        return ["no release-policy record"]
    al = policy.get("allocation", {}); g = policy.get("gate15", {})
    if not al.get("document_id") or f"`{al['document_id']}`" not in notes:
        problems.append("allocation document id absent from the notes")
    if not al.get("sha256") or f"sha256 {al['sha256'][:16]}…" not in notes:
        problems.append("allocation document sha256 prefix absent from the notes")
    if f"decision {al.get('decision')}" not in notes:
        problems.append("allocation decision absent from the notes")
    titled = re.search(r"^#### (?:New|Changed) in (\d+\.\d+\.\d+) — ", notes, re.M); notes_version = titled.group(1) if titled else None
    if notes_version not in SUPPORTED_VERSIONS:
        problems.append(f"the notes are not titled for a supported 9.x version (found {notes_version!r})")
    if str(policy.get("version")) != str(notes_version):
        problems.append(f"policy record is for version {policy.get('version')!r}, not {notes_version}")
    if notes_version in PATCH_OF and "scope unchanged" not in notes:
        problems.append("a patch release must state that the scope is unchanged")
    if notes_version in MINOR_OF and ("minor release: adds" not in notes or "feature scope F1–F5 kept" not in notes):
        problems.append("a minor release must describe itself as a minor release that adds functionality while keeping the prior feature scope")
    if al.get("accepted") is not True:
        problems.append("allocation is not recorded as accepted (a PROPOSED allocation document is not a decision)")
    v = notes_version if notes_version in SUPPORTED_VERSIONS else "9.0.0"; route = gate15_route(v)
    dec = decision if decision is not None else gate15_decision(version=v)
    if g.get("route") == route:
        if dec is None:
            problems.append(f"Gate #15 recorded as {route} but the owner's {v} exception record is absent from the tree (a decision for another version is never read for {v})")
        elif g.get("status") != "MANUAL_REVIEW" or g.get("decision_record_sha256") != dec["sha256"] or g.get("decision_text_sha256") != hashlib.sha256(dec["decision_text_verbatim"].encode()).hexdigest():
            problems.append(f"Gate #15 exception is not bound to the owner's {v} decision record in the tree (status, record sha256 or verbatim text sha256 mismatch)")
        elif gate15_line(policy, dec, v) not in notes:
            problems.append("Gate #15 exception disclosure (verbatim owner text) missing or altered")
    else:
        problems.append(f"Gate #15 route {g.get('route')!r}: {v} needs the owner's explicit exception route {route} bound to the tracked {v} decision record; NOT_REQUIRED (8.x) and routes A/B do not apply, nor does another version's exception; the study was never run")
    if re.search(r"Gate #15[^\n]*\b(PASSED|GREEN|study complete|(?<!NOT )(?<!not )satisfied)\b", notes):      # "NOT satisfied" is the disclosure itself
        problems.append("Gate #15 is described as passed or complete — it never is")
    m = matrix or capability_matrix()
    for f in m["enabled"]:
        if FEATURE_LINES[f] not in notes:
            problems.append(f"feature account for {f} missing or altered")
    for needle, why in ((f"- {m['backup_disclosure']}", "backup disclosure absent or not verbatim"), (BENEFIT_NOTE, "human benefit PENDING statement missing"), (REVIEW_NOTE, "simulated-review attribution missing"),
                        (FIXTURE_NOTE, "fictional-fixture statement missing"), (DETECTOR_NOTE, "detector never-claims statement missing"), (V8_NOTE, "v8-unchanged statement missing"),
                        (CONNECTOR_NOTE.format(deferred=", ".join(x.replace("_", " ") for x in m["deferred"])), "deferred-connectors statement missing")):
        if needle not in notes:
            problems.append(why)
    if not m["demonstrated"] and "Candidate evidence INCOMPLETE" not in notes:
        problems.append("candidate evidence is not complete but the notes do not say so")
    if re.search(r"\b(validated|certif(ied|icate)|guarantee[sd]?|alpha|independently replicated)\b", notes, re.I):
        problems.append("banned claim word present")
    return problems
