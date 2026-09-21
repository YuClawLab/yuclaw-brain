"""Public (Tier-2) release notes for the SUPPORTED 8.0.0 release — composed from the tree's actual capability
inputs and the RECORDED release-policy decisions (V8-008 TB-1 repair).

Inputs, all explicit and checked (nothing free-typed decides what "ships"):
  * the workbench's own step inventory  — v8.workbench.server.STEPS (the seven steps the shipped code serves);
  * the machine-readable release scope  — v8/scope/v8.0.0-scope.json (enabled workstreams, minimal RIV/ACT
    behaviour, experimental default-off modules, deferred work, the owner's backup policy and its exact disclosure);
  * the recorded journey evidence       — the scorecards of the NEWEST order record that carries both journeys
    (v8/V8-*/scorecard_fixtures.json + scorecard_mchp.json); each names the candidate commit it ran on and the notes
    repeat that identity, so evidence for an earlier candidate is never presented as the current candidate's;
  * the release policy record           — allocation (D1) as RECORDED by the publisher's policy stage, with Gate #15
    NOT_REQUIRED bound to the owner's recorded v8 decision (v8/policy/gate15_release_requirement.json: the human-
    comprehension study is not a required input to a v8 release — REMOVED_BY_OWNER, never PASSED); a missing record
    is stated as NOT RECORDED and never passes correspondence.
Version support is narrow: 8.0.0 (the major release) and its patch 8.0.1 (SUPPORTED_VERSIONS). A patch release keeps the
8.0.0 scope file and capability account unchanged — it adds a TRACKED patch change list
(docs/methodology/release_notes_<version>_changes.md) and says that the scope did not change; it cannot be composed
without that list, and 8.0.0 cannot be composed with one. The 7.x composer (v3/release/notes_v7.py) is unchanged and
stays the composer for 7.x. Unknown versions have no composer and never correspond.

Distinctions kept apart on purpose: (1) version SUPPORT (this module knows 8.0.0), (2) CORRESPONDENCE between the
notes text and the policy record (check_correspondence; empty list = correspond), (3) SATISFACTION of release gates
(the generator's gate table; Gate #15 reports REMOVED_BY_OWNER for v8, never PASSED; nothing here changes a gate), (4) publication
AUTHORIZATION (the owner's sentence, accepted by the publisher only with 0 RED + a valid policy + corresponding notes).
A composable 8.0.0 note with a PROPOSED or absent policy is a draft: it says so and it does not correspond.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
SUPPORTED_VERSIONS = ("8.0.0", "8.0.1")
PATCH_OF = {"8.0.1": "8.0.0"}                      # patch release → the release whose frozen scope it keeps
SCOPE_PATH = _REPO / "v8" / "scope" / "v8.0.0-scope.json"
GATE15_DECISION = _REPO / "v8" / "policy" / "gate15_release_requirement.json"
def _activations():
    """Every proposed activation, as in 7.x (names unchanged: the correspondence check keys on them); only the Gate #15
    line's meaning differs for v8: the study is not a required input (owner decision), which is not a pass."""
    import sys
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from v3.release import notes_v7
    return tuple((name, "kit ships; no study run; requirement removed by the owner for v8 releases — not a pass; human benefit PENDING" if name == "Gate #15 human study" else meaning)
                 for name, meaning in notes_v7.ACTIVATIONS)


def gate15_decision(path: Path | None = None) -> dict | None:
    """The owner's recorded v8 decision (with its sha256) or None; a record with any status other than REMOVED_BY_OWNER is refused."""
    import hashlib
    path = GATE15_DECISION if path is None else path
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    if d.get("record") != "yuclaw-v8-release-requirement-decision/1" or d.get("gate") != 15 or d.get("decided_by") != "owner" or d.get("status") != "REMOVED_BY_OWNER":
        raise ValueError("gate 15 decision record is not the owner's REMOVED_BY_OWNER decision for v8")
    return {**d, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def activation_status(policy: dict | None) -> str:
    active = set((policy or {}).get("activations_active") or [])
    out = []
    for name, meaning in _activations():
        out.append(f"- {name}: {'ACTIVE — ' + str((policy or {}).get('activation_records', {}).get(name, 'record in the private release-policy file')) if name in active else 'INACTIVE — ' + meaning}")
    out.append("- Phase-5 contribution anatomy: a READER of registered protocol lines and registered results; it is not a registered result and registers nothing")
    return "\n".join(out)


def gate15_line(policy: dict | None, decision: dict | None) -> str:
    """The Gate #15 disclosure for a v8 release: the requirement is removed by the owner (bound by record hash when a
    policy is recorded); the study was never run; the gate is never reported as passed."""
    d = decision or {}
    ref = (policy or {}).get("gate15", {}).get("decision_record_sha256") or d.get("sha256") or ""
    return (f"- Gate #15 (user comprehension test passes): requirement REMOVED BY OWNER for v8 releases on {d.get('decision_utc', 'date not recorded')} "
            f"(decision record sha256 {ref[:16]}…); no human comprehension study was run and none is claimed — not a pass; "
            "the automated consumer-posture scaffold check is retained; human benefit PENDING")


def policy_disclosure(policy: dict | None, decision: dict | None) -> str:
    if not policy:
        return ("- Release policy: NOT RECORDED — owner decision D1 (allocation) is pending; these notes are a draft and are not publishable until the policy record exists\n"
                + gate15_line(None, decision))
    al = policy.get("allocation", {})
    doc = al.get("document_id", "unknown"); dsha = al.get("sha256", "")
    lines = [f"- Allocation: decision {al.get('decision', 'unknown')} on allocation document `{doc}` (sha256 {dsha[:16]}…)"]
    g = policy.get("gate15", {})
    if g.get("route") == "NOT_REQUIRED":
        lines.append(gate15_line(policy, decision))
    else:
        lines.append(f"- Gate #15: route {g.get('route')!r} is not applicable to a v8 release (the requirement was removed by the owner; NOT_REQUIRED expected)")
    return "\n".join(lines)
def latest_scorecards(root: Path | None = None) -> tuple:
    """(fixtures, mchp) scorecard paths of the newest order record that holds both; () when none does."""
    recs = sorted((d for d in ((root or _REPO) / "v8").glob("V8-[0-9][0-9][0-9]") if (d / "scorecard_fixtures.json").exists() and (d / "scorecard_mchp.json").exists()), key=lambda d: d.name)
    return (recs[-1] / "scorecard_fixtures.json", recs[-1] / "scorecard_mchp.json") if recs else ()


SCORECARDS = latest_scorecards()
EXPECTED_STEPS = ("source", "claim", "comparison", "calculation", "history", "adjudication", "export")
EXPECTED_FEATURES = ("research_notes", "dataset", "sci")

# Feature account per ENABLED workstream (the scope decides which lines may appear; a line for a workstream that the
# scope does not enable is refused, and an enabled workstream without a line is refused).
FEATURE_LINES = {
    "UX": "- One owner-operated, loopback-only browser workbench traces a financial commitment through seven visible steps — {steps} — with plain HTML forms and no scripts; a refused form returns with its reasons and the entries kept; every field is labelled and wide tables scroll inside the page; an in-app Help page lists every function and shows the packaged operator guide and data dictionary; a second, fresh workspace verifies any export.",
    "DAT": "- Bounded disclosure ingestion (command line, allow-listed hosts, https only, bounded body): original bytes and digests kept, exact passage registered with its availability time, source rights recorded; the record the tool writes is registered in the browser as pasted data and a replayed registration never duplicates a source; excerpt bytes travel only under rights that allow it. A new live request to the SEC requires the operator's own `SEC_USER_AGENT` setting — required, never defaulted: a missing or unusable value is refused before any request is sent; stored-source replay and every other offline function work without it.",
    "CLM": "- Typed commitments (`CommitmentClaim.v1`): currency, unit, scale, metric, accounting basis, fiscal period with explicit dates and resolution rule are mandatory; a missing or incompatible field blocks with every reason listed; freezing is one-way and later edits create successor versions.",
    "RIV": "- Comparison (minimal shared behaviour): original and revised ranges side by side with basis checks; an incompatible metric, basis, unit or period yields INCOMPARABLE with its reasons; explanatory notes are not causal evidence.",
    "CHK": "- Deterministic calculation: the disclosed outcome against each compatible range with visible inputs, formula and source links; a currency, scale or period mismatch never produces a pass.",
    "TIM": "- Three separate times on every record (source availability, observation, recording) and as-of replay at any cutoff; later information is never shown as known earlier; append-only, digest-chained history with operation identifiers and explicit torn-tail recovery. A wrong source-availability time is corrected by a linked, append-only event, never by editing: the original records and earlier historical views stay intact, the corrected result is shown separately beside the recorded one, and the correction chain is exported for a fresh workspace to recompute. Availability times are asserted by the operator, not authenticated.",
    "ACT": "- Research notes and unresolved evidence (minimal shared behaviour): an unresolved question or explanation, the next evidence needed, the reason and an actor label on a frozen claim, corrected only by a new linked note; no automated prioritisation.",
    "SET": "- Dataset coverage: one row per frozen claim derived from stored records (identifiers, source versions and lineage, targets and revisions, corrections and withdrawals, outcome, computed result, reviewer labels and disagreement), a deterministic snapshot digest and a verifiable dataset export.",
    "SCI": "- Scientific report and replay through the adapted kernel: a bounded science journal (a JSON event list) scored by paired Brier improvement with a sequential evidence value; explicit eligibility refusals; report status is conditional statistical evidence only and grants no action.",
    "INT": "- Local persistence and integrity: one append-only journal per workspace, one re-entrant write lock, idempotent submissions, additive event kinds, bounded inputs that are never executed, opened or fetched; nothing binds outside 127.0.0.1. The four modules share one local principal layer (separate capabilities for administration, submission, review and practice; credentials shown once and kept only as hashes; once a principal exists every page needs sign-in): it shows which local credential acted, not legal identity or qualification. A claim, submission, decision, version or session chosen in one module is carried to the next with its version shown, and every carried reference is checked again on the server for the principal, the workspace and the object's present state.",
    "SHD": "- Distillation Shield (protected evidence intake): a bundle is admitted only when an administrator other than its submitter signed an approval for its exact bytes, evidence digests, one purpose and this workspace, unexpired and unrevoked at the moment of use; archive extraction and parsing run in a restricted worker whose file, network and process denials are probed on the host before it is used, and the route stays closed when none is available; results are typed fields with fixed reason codes and evidence text stays inert; byte integrity, authority approval, factual adjudication and release permission are four separate answers, so an approved statement is never thereby true. No independent security review has been performed.",
    "EVO": "- Evolution Evidence Audit: versions of an AI system's eight parts (model, agent code, tool policy, memory, data, runtime, grader, evaluation data) are recorded as measured, declared, unknown or not applicable, and a provider alias is never a measurement; review evidence is reused only while the administrator-configured dependency closure, the protocol, the authority state and the validity period still apply, with reasons; a trusted local evaluation runs a built-in job on an immutable snapshot and refuses changed files; failures stay open until an authorized evidence-backed resolution; historical views use recorded time. It audits and controls no deployment.",
    "COM": "- Research Commons Guard: a durable review queue with one task per exact duplicate group of compatible claim contracts and known source roots, retained attribution, authenticated admission limits, transactional review budgets with a separately reserved practice allocation, leases, rollover, aged holds, recorded overrides, and authorized disputes with appeals; a shared source is not independent corroboration — two registrations of identical passage bytes, or an authorized declared alias, are one root — and a duplicate is not misconduct; the queue comparison is a labelled simulation and no human productivity result exists.",
    "PRC": "- Independent Practice: a frozen task and source scope, truthful assistance and exposure declarations, one preserved attempt committed before a server-held comparison opens, the comparison's provenance shown, reflection, reviewer feedback, local follow-up due states, and a scoped private export with separately held checkpoints; the records cannot prove authorship, comprehension or improved ability, and no study was run.",
    "GOV": "- Scope and controls: the enabled 8.0.0 scope is frozen, the mission and vision wording is checked byte-for-byte, authored product content is English with YUCLAW on public surfaces.",
    "REL": "- Reproducible artifacts: wheel and sdist built with a fixed source-date epoch from the frozen commit, verified from fresh installs; order records, scope and release-policy documents are excluded from the distribution; every workbench module compiles on Python 3.10.",
}
ENABLED_BUT_DEFERRED_NOTE = "- Deferred beyond 8.0.0: {deferred}. No runtime endpoint, tab or promised benefit for any of them."
EXPERIMENTAL_NOTE = "- Experimental optional modules {modules}: ABSENT from the distribution; nothing is default-on; no benefit is claimed."
MODULES_NOTE = ("- Modules SHD / EVO / COM / PRC are INCLUDED in the distribution (owner scope decision 2026-09-20). Including them activates nothing: no principal, trust root, approval, budget, reviewer, "
                "study or deployment control exists until the local operator sets one up, and the protected intake stays closed on a host without a working restricted worker. External evidence that does not exist: an actual "
                "human effort comparison, a qualified independent task reviewer or learning result, an independent security review, an authorized external deployment integration.")
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
    lines = [FEATURE_LINES[ws].format(steps=steps) for ws in ("UX", "DAT", "CLM", "RIV", "CHK", "TIM", "ACT", "SET", "SCI", "SHD", "EVO", "COM", "PRC", "INT", "GOV", "REL") if ws in matrix["enabled"] or ws in matrix["minimal"]]
    ev = "; ".join(f"{k} (candidate {str(v['candidate'] or 'unrecorded')[:12]}): {v['score']} + notes {v['features']['research_notes']}, dataset {v['features']['dataset']}, scientific report {v['features']['sci']}" for k, v in matrix["evidence"].items()) or "no journey evidence recorded"
    lines.append(f"- Journey evidence (automated browser journeys on the candidate, from the checkout and from the installed wheel and sdist): {ev}." if matrix["demonstrated"] else f"- Journey evidence INCOMPLETE: {ev}.")
    return "\n".join(lines)


def modules_statement(matrix: dict) -> str:
    """The scope decides: experimental modules the scope still lists are ABSENT; with none listed, the four modules are
    included and the statement says what inclusion does NOT activate and which external evidence does not exist."""
    return EXPERIMENTAL_NOTE.format(modules=" / ".join(matrix["experimental"])) if matrix["experimental"] else MODULES_NOTE


def not_in_this_release(matrix: dict, tail: str) -> str:
    deferred = ", ".join(str(d).replace("_", " ") for d in matrix["deferred"])
    lines = [f"- {matrix['backup_disclosure']}", BENEFIT_NOTE,
             CORPUS_NOTE.format(issuer="Microchip Technology, Q1 FY2026 net-sales guidance"), REVIEW_NOTE, FIXTURE_NOTE,
             modules_statement(matrix), ENABLED_BUT_DEFERRED_NOTE.format(deferred=deferred)]
    return "\n".join(lines) + "\n" + tail.strip("\n")


def compose(v6_style_public: str, *, version: str, policy: dict | None, board: dict | None, matrix: dict | None = None, patch_changes: str | None = None) -> str:
    """Rebuild the Tier-2 text for 8.0.0 from the derived v6-style block: keep the disclaimer/title/tagline and the
    continuing objects; add the 8.0.0 feature account (from the capability matrix), evidence totals, activation
    status and the policy disclosure (NOT RECORDED when no policy record exists)."""
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"version {version} has no 8.x notes composition path (supported: {', '.join(SUPPORTED_VERSIONS)})")
    scope_version = PATCH_OF.get(version, version)
    if version in PATCH_OF and not (patch_changes or "").strip():
        raise ValueError(f"{version} is a patch release: its tracked patch change list is required")
    if version not in PATCH_OF and patch_changes:
        raise ValueError(f"{version} is a major release: there is no patch change list")
    import sys
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from v3.release import notes_v7                          # shared, unchanged helper: evidence totals
    m = matrix or capability_matrix(); dec = gate15_decision()
    if m["version"] != scope_version:
        raise ValueError(f"scope release {m['version']} != {scope_version} (the scope of version {version})")
    head, rest = v6_style_public.split("#### Shipped objects", 1)
    objects, tail = rest.split("#### Not in this release", 1)
    objects = objects.split("\n", 1)[1].strip("\n")
    if version in PATCH_OF:
        new = [f"#### Changed in {version} — patch: defect repairs and clearer entry points (no methodology, statistic, threshold, registration or scope change)", "", patch_changes.strip("\n"), "",
               f"#### In the 8.0 line since {scope_version} — the source-to-export commitment workbench (local, loopback only; scope unchanged)", "", feature_account(m), ""]
    else:
        new = [f"#### New in {version} — the source-to-export commitment workbench (local, loopback only)", "", feature_account(m), ""]
    parts = [head.rstrip("\n"), "", *new,
             "#### Evidence totals (public scoreboard at composition)", "", notes_v7.evidence_totals(board), "",
             "#### Activation status (every proposed activation)", "", activation_status(policy), "",
             "#### Release policy (recorded; the publisher refuses notes that do not match the record)", "", policy_disclosure(policy, dec), "",
             "#### Continuing objects (unchanged from 7.0.1) — name · receipt · status", "", objects, "",
             "#### Not in this release", "", not_in_this_release(m, tail), ""]
    return "\n".join(parts)


def check_correspondence(notes: str, policy: dict | None, matrix: dict | None = None, decision: dict | None = None) -> list[str]:
    """Problems that make the notes unpublishable (empty list = correspond). Policy half for v8: allocation id + sha
    prefix + decision, accepted allocation, every activation line, the Phase-5 reader statement, banned phrase, and
    Gate #15 = NOT_REQUIRED bound to the owner's recorded decision (record hash must match the tree; the disclosure
    line must be present; the notes must never call the gate passed). Routes A/B do not apply to a v8 release. The
    8.0.0 half checks the capability account against the actual matrix: every enabled workstream present, the backup
    disclosure verbatim, the retrospective/ineligible corpus statement, the simulated-review statement and PENDING
    benefit, the absent experimental modules, and no scope expansion."""
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
    titled = re.search(r"^#### (?:New|Changed) in (\d+\.\d+\.\d+) — ", notes, re.M)
    notes_version = titled.group(1) if titled else None
    if notes_version not in SUPPORTED_VERSIONS:
        problems.append(f"the notes are not titled for a supported 8.x version (found {notes_version!r})")
    if str(policy.get("version")) != str(notes_version):
        problems.append(f"policy record is for version {policy.get('version')!r}, not {notes_version}")
    if notes_version in PATCH_OF and "scope unchanged" not in notes:
        problems.append("a patch release must state that the scope is unchanged")
    if al.get("accepted") is not True:
        problems.append("allocation is not recorded as accepted (a PROPOSED allocation document is not a decision)")
    dec = decision if decision is not None else gate15_decision()
    if g.get("route") != "NOT_REQUIRED":
        problems.append(f"Gate #15 route {g.get('route')!r} is not applicable to a v8 release: the owner removed the requirement (NOT_REQUIRED expected; no study, route A/B or exception statement)")
    else:
        if dec is None:
            problems.append("Gate #15 recorded as NOT_REQUIRED but the owner's decision record is absent from the tree")
        elif g.get("status") != "REMOVED_BY_OWNER" or g.get("decision_record_sha256") != dec["sha256"]:
            problems.append("Gate #15 NOT_REQUIRED is not bound to the owner's decision record in the tree (status or record sha256 mismatch)")
        elif gate15_line(policy, dec) not in notes:
            problems.append("Gate #15 removed-requirement disclosure missing or altered")
    if re.search(r"Gate #15[^\n]*\b(PASSED|GREEN|study complete|satisfied)\b", notes):
        problems.append("Gate #15 is described as passed or complete — it never is (requirement removed, study not run)")
    active = set(policy.get("activations_active") or [])
    for name, _ in _activations():
        want = f"- {name}: {'ACTIVE' if name in active else 'INACTIVE'}"
        if want not in notes:
            problems.append(f"activation line missing or wrong for {name!r}")
    if "Phase-5 contribution anatomy: a READER of registered protocol lines" not in notes:
        problems.append("Phase-5 reader statement missing")
    if re.search(r"independently replicated", notes, re.I):
        problems.append("banned phrase")
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
    if modules_statement(m) not in notes:
        problems.append("experimental modules (absent, default-off) statement missing" if m["experimental"] else "included-modules statement (what inclusion does not activate; external evidence that does not exist) missing")
    if not m["demonstrated"] and "Journey evidence INCOMPLETE" not in notes:
        problems.append("journey evidence is not complete but the notes do not say so")
    if re.search(r"\b(validated|certif(ied|icate)|guarantee[sd]?|alpha)\b", notes, re.I):
        problems.append("banned claim word present")
    return problems
