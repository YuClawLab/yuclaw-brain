"""Public (Tier-2) release notes for the SUPPORTED 8.0.0 release — composed from the tree's actual capability
inputs and the RECORDED release-policy decisions (V8-008 TB-1 repair).

Inputs, all explicit and checked (nothing free-typed decides what "ships"):
  * the workbench's own step inventory  — v8.workbench.server.STEPS (the seven steps the shipped code serves);
  * the machine-readable release scope  — v8/scope/v8.0.0-scope.json (enabled workstreams, minimal RIV/ACT
    behaviour, experimental default-off modules, deferred work, the owner's backup policy and its exact disclosure);
  * the recorded journey evidence       — the V8-005 scorecards (7/7 + research notes, dataset, SCI DEMONSTRATED);
  * the release policy record           — allocation (D1) and Gate #15 route (D2) as RECORDED by the publisher's
    policy stage; a missing record is stated as NOT RECORDED and never passes correspondence.
Version support is narrow: only 8.0.0 (SUPPORTED_VERSIONS). The 7.x composer (v3/release/notes_v7.py) is unchanged
and stays the composer for 7.x. Unknown versions have no composer and never correspond.

Distinctions kept apart on purpose: (1) version SUPPORT (this module knows 8.0.0), (2) CORRESPONDENCE between the
notes text and the policy record (check_correspondence; empty list = correspond), (3) SATISFACTION of release gates
(the generator's gate table; Gate #15 keeps its actual status; nothing here changes a gate), (4) publication
AUTHORIZATION (the owner's sentence, accepted by the publisher only with 0 RED + a valid policy + corresponding notes).
A composable 8.0.0 note with a PROPOSED or absent policy is a draft: it says so and it does not correspond.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
SUPPORTED_VERSIONS = ("8.0.0",)
SCOPE_PATH = _REPO / "v8" / "scope" / "v8.0.0-scope.json"
SCORECARDS = (_REPO / "v8" / "V8-005" / "scorecard_fixtures.json", _REPO / "v8" / "V8-005" / "scorecard_mchp.json")
EXPECTED_STEPS = ("source", "claim", "comparison", "calculation", "history", "adjudication", "export")
EXPECTED_FEATURES = ("research_notes", "dataset", "sci")

# Feature account per ENABLED workstream (the scope decides which lines may appear; a line for a workstream that the
# scope does not enable is refused, and an enabled workstream without a line is refused).
FEATURE_LINES = {
    "UX": "- One owner-operated, loopback-only browser workbench traces a financial commitment through seven visible steps — {steps} — with plain HTML forms and no scripts; a second, fresh workspace verifies any export.",
    "DAT": "- Bounded disclosure ingestion (command line, allow-listed hosts, https only, bounded body): original bytes and digests kept, exact passage registered with its availability time, source rights recorded; excerpt bytes travel only under rights that allow it.",
    "CLM": "- Typed commitments (`CommitmentClaim.v1`): currency, unit, scale, metric, accounting basis, fiscal period with explicit dates and resolution rule are mandatory; a missing or incompatible field blocks with every reason listed; freezing is one-way and later edits create successor versions.",
    "RIV": "- Comparison (minimal shared behaviour): original and revised ranges side by side with basis checks; an incompatible metric, basis, unit or period yields INCOMPARABLE with its reasons; explanatory notes are not causal evidence.",
    "CHK": "- Deterministic calculation: the disclosed outcome against each compatible range with visible inputs, formula and source links; a currency, scale or period mismatch never produces a pass.",
    "TIM": "- Three separate times on every record (source availability, observation, recording) and as-of replay at any cutoff; later information is never shown as known earlier; append-only, digest-chained history with operation identifiers and explicit torn-tail recovery.",
    "ACT": "- Research notes and unresolved evidence (minimal shared behaviour): an unresolved question or explanation, the next evidence needed, the reason and an actor label on a frozen claim, corrected only by a new linked note; no automated prioritisation.",
    "SET": "- Dataset coverage: one row per frozen claim derived from stored records (identifiers, source versions and lineage, targets and revisions, corrections and withdrawals, outcome, computed result, reviewer labels and disagreement), a deterministic snapshot digest and a verifiable dataset export.",
    "SCI": "- Scientific report and replay through the adapted kernel: a bounded science journal (a JSON event list) scored by paired Brier improvement with a sequential evidence value; explicit eligibility refusals; report status is conditional statistical evidence only and grants no action.",
    "INT": "- Local persistence and integrity: one append-only journal per workspace, one re-entrant write lock, idempotent submissions, additive event kinds, bounded inputs that are never executed, opened or fetched; nothing binds outside 127.0.0.1.",
    "GOV": "- Scope and controls: the enabled 8.0.0 scope is frozen, the mission and vision wording is checked byte-for-byte, authored product content is English with YUCLAW on public surfaces.",
    "REL": "- Reproducible artifacts: wheel and sdist built with a fixed source-date epoch from the frozen commit, verified from fresh installs; order records and scope documents are excluded from the distribution; every workbench module compiles on Python 3.10.",
}
ENABLED_BUT_DEFERRED_NOTE = "- Deferred beyond 8.0.0: {deferred}. No runtime endpoint, tab or promised benefit for any of them."
EXPERIMENTAL_NOTE = "- Experimental optional modules {modules}: ABSENT from the distribution; nothing is default-on; no benefit is claimed."
CORPUS_NOTE = ("- Real data: one issuer's quarterly guidance ({issuer}) was replayed RETROSPECTIVELY through the workbench as a behaviour demonstration on real sources; "
               "the issuer is NOT ELIGIBLE under the recorded selection criteria (unchanged from the first order) and no dataset product is claimed.")
REVIEW_NOTE = "- Review: every adjudication and note in the release evidence was recorded by the automated journey runner as a simulated test action; there was no human review and no user study."
BENEFIT_NOTE = "- Human benefit: PENDING — no pilot, no user study; the journeys demonstrate behaviour, not benefit."
FIXTURE_NOTE = "- Fixtures are clearly fictional demonstration data; the packaged scientific examples are fictional too."


def _load(p: Path) -> dict:
    return json.loads(p.read_text())


def capability_matrix(*, scope: dict | None = None, steps: list | None = None, scorecards: list | None = None) -> dict:
    """The actual inputs the notes are composed from. Each is read from the tree unless supplied (tests supply fixtures)."""
    if scope is None:
        scope = _load(SCOPE_PATH)
    if steps is None:
        import importlib
        steps = list(importlib.import_module("v8.workbench.server").STEPS)
    if scorecards is None:
        scorecards = [_load(p) for p in SCORECARDS if p.exists()]
    keys = tuple(k for k, _ in steps)
    if keys != EXPECTED_STEPS:
        raise ValueError(f"workbench step inventory {keys} is not the seven-step contract {EXPECTED_STEPS}")
    enabled = list(scope["enabled_workstreams"]); minimal = dict(scope.get("minimal_shared_behavior") or {})
    for ws in list(enabled) + list(minimal):
        if ws not in FEATURE_LINES:
            raise ValueError(f"enabled workstream {ws} has no feature account")
    for ws in FEATURE_LINES:
        if ws not in enabled and ws not in minimal:
            raise ValueError(f"feature account names {ws}, which the scope does not enable")
    evidence = {}
    for sc in scorecards:
        feats = sc.get("features") or {}
        evidence[sc.get("mode") or sc.get("fixture_set") or f"scorecard{len(evidence) + 1}"] = {
            "score": sc.get("score"), "candidate": (sc.get("candidate") or {}).get("commit") if isinstance(sc.get("candidate"), dict) else sc.get("candidate"),
            "features": {k: (feats.get(k) or {}).get("status") for k in EXPECTED_FEATURES}}
    demonstrated = bool(evidence) and all(e["score"] == "7/7" and all(v == "DEMONSTRATED" for v in e["features"].values()) for e in evidence.values())
    return {"version": scope["release"], "steps": [t for _, t in steps], "enabled": enabled, "minimal": minimal,
            "experimental": list(scope["experimental_default_off"]), "deferred": list(scope["deferred"]),
            "backup_disclosure": scope["backup_policy"]["disclosure"], "corpus": scope.get("initial_real_corpus") or {},
            "evidence": evidence, "demonstrated": demonstrated}


def feature_account(matrix: dict) -> str:
    steps = " → ".join(matrix["steps"])
    lines = [FEATURE_LINES[ws].format(steps=steps) for ws in ("UX", "DAT", "CLM", "RIV", "CHK", "TIM", "ACT", "SET", "SCI", "INT", "GOV", "REL") if ws in matrix["enabled"] or ws in matrix["minimal"]]
    ev = "; ".join(f"{k}: {v['score']} + notes {v['features']['research_notes']}, dataset {v['features']['dataset']}, scientific report {v['features']['sci']}" for k, v in matrix["evidence"].items()) or "no journey evidence recorded"
    lines.append(f"- Journey evidence (automated browser journeys on the candidate, from the checkout and from the installed wheel and sdist): {ev}." if matrix["demonstrated"] else f"- Journey evidence INCOMPLETE: {ev}.")
    return "\n".join(lines)


def not_in_this_release(matrix: dict, tail: str) -> str:
    deferred = ", ".join(str(d).replace("_", " ") for d in matrix["deferred"])
    lines = [f"- {matrix['backup_disclosure']}", BENEFIT_NOTE,
             CORPUS_NOTE.format(issuer="Microchip Technology, Q1 FY2026 net-sales guidance"), REVIEW_NOTE, FIXTURE_NOTE,
             EXPERIMENTAL_NOTE.format(modules=" / ".join(matrix["experimental"])), ENABLED_BUT_DEFERRED_NOTE.format(deferred=deferred)]
    return "\n".join(lines) + "\n" + tail.strip("\n")


def compose(v6_style_public: str, *, version: str, policy: dict | None, board: dict | None, matrix: dict | None = None, patch_changes: str | None = None) -> str:
    """Rebuild the Tier-2 text for 8.0.0 from the derived v6-style block: keep the disclaimer/title/tagline and the
    continuing objects; add the 8.0.0 feature account (from the capability matrix), evidence totals, activation
    status and the policy disclosure (NOT RECORDED when no policy record exists)."""
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"version {version} has no 8.x notes composition path (supported: {', '.join(SUPPORTED_VERSIONS)})")
    if patch_changes:
        raise ValueError("8.0.0 is a major release: there is no patch change list")
    import sys
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from v3.release import notes_v7                          # shared, unchanged helpers: evidence totals, activation lines, policy disclosure wording
    m = matrix or capability_matrix()
    if m["version"] != version:
        raise ValueError(f"scope release {m['version']} != version {version}")
    head, rest = v6_style_public.split("#### Shipped objects", 1)
    objects, tail = rest.split("#### Not in this release", 1)
    objects = objects.split("\n", 1)[1].strip("\n")
    parts = [head.rstrip("\n"), "",
             f"#### New in {version} — the source-to-export commitment workbench (local, loopback only)", "", feature_account(m), "",
             "#### Evidence totals (public scoreboard at composition)", "", notes_v7.evidence_totals(board), "",
             "#### Activation status (every proposed activation)", "", notes_v7.activation_status(policy), "",
             "#### Release policy (recorded; the publisher refuses notes that do not match the record)", "", notes_v7.policy_disclosure(policy), "",
             "#### Continuing objects (unchanged from 7.0.1) — name · receipt · status", "", objects, "",
             "#### Not in this release", "", not_in_this_release(m, tail), ""]
    return "\n".join(parts)


def check_correspondence(notes: str, policy: dict | None, matrix: dict | None = None) -> list[str]:
    """Problems that make the notes unpublishable (empty list = correspond). The policy half reuses the 7.x rules
    unchanged (allocation id + sha prefix + decision; route B verbatim text and NOT SATISFIED; route A gate input;
    every activation line; the Phase-5 reader statement; banned phrase). The 8.0.0 half checks the capability
    account against the actual matrix: every enabled workstream present, the backup disclosure verbatim, the
    retrospective/ineligible corpus statement, the simulated-review statement and PENDING benefit, the absent
    experimental modules, and no scope expansion."""
    import sys
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from v3.release import notes_v7
    problems = list(notes_v7.check_correspondence(notes, policy))
    if policy and str(policy.get("version")) != SUPPORTED_VERSIONS[0]:
        problems.append(f"policy record is for version {policy.get('version')!r}, not {SUPPORTED_VERSIONS[0]}")
    if policy and policy.get("allocation", {}).get("accepted") is not True:
        problems.append("allocation is not recorded as accepted (a PROPOSED allocation document is not a decision)")
    g15 = (policy or {}).get("gate15", {})
    if policy and g15.get("route") == "A" and not (g15.get("gate_input") == "CANDIDATE_GATE_INPUT" and g15.get("gate_15_proposed") == "GREEN"):
        problems.append("route A: policy record lacks an accepted gate input (CANDIDATE_GATE_INPUT proposing GREEN); the 7.x text check alone would accept 'None'")
    if policy and g15.get("route") == "B" and not str(g15.get("exception_text") or "").strip():
        problems.append("route B: policy record carries no exception text")
    m = matrix or capability_matrix()
    for ws in list(m["enabled"]) + list(m["minimal"]):
        line = FEATURE_LINES[ws].format(steps=" → ".join(m["steps"]))
        if line not in notes:
            problems.append(f"feature account for enabled workstream {ws} missing or altered")
    for ws in FEATURE_LINES:
        if ws not in m["enabled"] and ws not in m["minimal"] and FEATURE_LINES[ws].split("{")[0][:40] in notes:
            problems.append(f"scope expansion: feature account for {ws}, which the scope does not enable")
    if f"- {m['backup_disclosure']}" not in notes:
        problems.append("backup disclosure absent or not verbatim")
    if "replayed RETROSPECTIVELY" not in notes or "NOT ELIGIBLE under the recorded selection criteria" not in notes:
        problems.append("real-data statement (retrospective replay; issuer NOT ELIGIBLE) missing")
    if REVIEW_NOTE not in notes:
        problems.append("simulated-review attribution missing")
    if BENEFIT_NOTE not in notes:
        problems.append("human benefit PENDING statement missing")
    if EXPERIMENTAL_NOTE.format(modules=" / ".join(m["experimental"])) not in notes:
        problems.append("experimental modules (absent, default-off) statement missing")
    if not m["demonstrated"] and "Journey evidence INCOMPLETE" not in notes:
        problems.append("journey evidence is not complete but the notes do not say so")
    if re.search(r"\b(validated|certif(ied|icate)|guarantee[sd]?|alpha)\b", notes, re.I):
        problems.append("banned claim word present")
    return problems
