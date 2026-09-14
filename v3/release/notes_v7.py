"""Public (Tier-2) release notes for 7.0.0 — composed from the tree and the RECORDED release-policy decisions.

Truthfulness rules: the notes state what 7.0.0 ships (feature account), the evidence totals read from the public
scoreboard file at composition time, the activation status of every proposed activation (all inactive unless the
policy record names an activation as active), the release-policy disclosure (allocation document identity and the
Gate #15 route — the owner's exception text VERBATIM when route B was recorded), and that the Phase-5 contribution
reader is a reader of registered lines, not a registered result. `check_correspondence` is the publisher's gate:
notes that do not correspond to the recorded policy are never published."""
from __future__ import annotations

import re

ACTIVATIONS = (
    ("real receipt program", "no reviewer appointed, no registration record adopted, the three-reproduction floor unadopted (D3)"),
    ("nightly status delivery", "adapter and preview only; delivery not activated (D4-NIGHTLY-STATUS)"),
    ("note-snapshot coordinator", "contract v3 stays live; coordinator not wired (D4-SNAPSHOT)"),
    ("sentinel policy", "unchanged; proposal only (D4-SENTINEL)"),
    ("Phase-C prospective protocol", "draft; unregistered; nothing runs (D4-PHASE-C)"),
    ("Phase 6 / A2 designation of S", "candidate record only; not registered; N_eff not computed (D4-A2-S)"),
    ("ETF class addendum", "proposed classification path; registered set untouched (D4-ETF-ADDENDUM)"),
    ("U-ladder promotion / window", "fixture validation only; no admission, promotion or registered window (D4-U-LADDER-WINDOW)"),
    ("Gate #15 human study", "kit ships; no study run; gate MANUAL_REVIEW"),
)

FEATURES = """- Receipt engine: submission, artifact observation from actual bytes, appointment-bound reviewer decision and typed registration counting kept as separate records; primary counts are qualified attempts.
- Offline verification packet: `yuclaw packet build` / `yuclaw packet verify` — SHA-256 + byte-length manifest, descriptor-pinned reads, exact-byte replay of the frozen public Lab bundle; provenance UNVERIFIED unless an independently obtained identity is supplied.
- Claim support limits: `yuclaw check-claim` reports source match, temporal eligibility, replay status and research interpretation = none; never a verdict, direction, return or prediction.
- Local challenges and document-use receipts: criterion-bound challenge resolution (deterministic verifiers or a designated reviewer's explicit evaluation), every version retained; decision receipts exported only with permission.
- Evidence Scoreboard: `/evidence_scoreboard.html`, `/receipts/scoreboard.json`, REST `/v1/receipts/scoreboard`, MCP `get_evidence_scoreboard` — one canonical payload with a complete public schema; exact-release coverage UNBOUND until a release target manifest is delivered as release evidence.
- Program materials shipped as proposals only (nothing adopted): outsider receipt program specification, Gate #15 formative-study kit with evaluator, Phase-C protocol draft, A2 interface, ETF class addendum path, U-ladder fixture validation, note-snapshot coordinator, nightly-status adapter, sentinel proposal, capacity assessment, commercial governance pack.
- Minimum Python 3.10: the package compiles and its test suite runs on CPython 3.10 and 3.12."""


def _n(board: dict | None, *path, default="unavailable"):
    cur = board
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def evidence_totals(board: dict | None) -> str:
    if not board:
        return "- Public scoreboard file not present at composition time; no totals are stated."
    c = board.get("columns", {})
    rep = c.get("replications", {})
    lines = [
        f"- Replication attempts: primary {_n(rep, 'primary_attempts')}, successful {_n(rep, 'successful_attempts')}; registration {_n(rep, 'registration', 'status')}; exact-release coverage {_n(board, 'target', 'state')}",
        f"- Witness reviews {_n(c, 'witnesses', 'count')} · audit-break attempts {_n(c, 'audits', 'count')} · refusals {_n(c, 'refusals', 'count')} · challenges {_n(c, 'challenges', 'count')} · document-use receipts {_n(c, 'packet_uses', 'count')} · pilots {_n(c, 'pilots', 'count')}",
        f"- Board timestamp {board.get('source_timestamp', 'unavailable')}; these are counts of records, not a quality or independence verdict",
    ]
    return "\n".join(lines)


def activation_status(policy: dict | None) -> str:
    active = set((policy or {}).get("activations_active") or [])
    out = []
    for name, meaning in ACTIVATIONS:
        out.append(f"- {name}: {'ACTIVE — ' + str((policy or {}).get('activation_records', {}).get(name, 'record in the private release-policy file')) if name in active else 'INACTIVE — ' + meaning}")
    out.append("- Phase-5 contribution anatomy: a READER of registered protocol lines and registered results; it is not a registered result and registers nothing")
    return "\n".join(out)


def policy_disclosure(policy: dict | None) -> str:
    if not policy:
        return ("- Release policy: NOT RECORDED — owner decisions D1 (allocation) and D2 (Gate #15 route) are pending; "
                "these notes are a draft and are not publishable until the policy record exists")
    al = policy.get("allocation", {})
    doc = al.get("document_id", "unknown"); dsha = al.get("sha256", "")
    g = policy.get("gate15", {})
    lines = [f"- Allocation: decision {al.get('decision', 'unknown')} on allocation document `{doc}` (sha256 {dsha[:16]}…)"]
    if g.get("route") == "B":
        lines.append("- Gate #15 (user comprehension test passes): NOT SATISFIED; released under the owner's explicit release-policy exception, recorded verbatim:")
        lines.append(f"  > {g.get('exception_text', '')}")
    elif g.get("route") == "A":
        cov = g.get("coverage") or {}
        lines.append(f"- Gate #15 (user comprehension test passes): accepted gate input {g.get('gate_input')} proposing {g.get('gate_15_proposed')}; covers materials manifest {str(cov.get('materials_manifest_sha256', ''))[:16]}… and wheel {str(cov.get('wheel_sha256', ''))[:16]}… only")
    else:
        lines.append("- Gate #15: route not recorded")
    return "\n".join(lines)


def compose(v6_style_public: str, *, version: str, policy: dict | None, board: dict | None) -> str:
    """Rebuild the Tier-2 text for 7.x from the derived v6-style block: keep the disclaimer/title/tagline and the
    continuing objects; add the 7.0 feature account, evidence totals, activation status and policy disclosure."""
    head, rest = v6_style_public.split("#### Shipped objects", 1)
    objects, tail = rest.split("#### Not in this release", 1)
    objects = objects.split("\n", 1)[1].strip("\n")
    parts = [head.rstrip("\n"), "",
             f"#### New in {version} — check → reproduce → challenge → document use", "", FEATURES, "",
             "#### Evidence totals (public scoreboard at composition)", "", evidence_totals(board), "",
             "#### Activation status (every proposed activation)", "", activation_status(policy), "",
             "#### Release policy (recorded; the publisher refuses notes that do not match the record)", "", policy_disclosure(policy), "",
             "#### Continuing objects (unchanged from 6.0) — name · receipt · status", "", objects, "",
             "#### Not in this release" + tail.rstrip("\n"), ""]
    return "\n".join(parts)


def check_correspondence(notes: str, policy: dict | None) -> list[str]:
    """Problems that make the notes unpublishable against the recorded policy (empty list = correspond)."""
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
    if g.get("route") == "B":
        text = g.get("exception_text", "")
        if not text or f"  > {text}\n" not in notes + "\n":
            problems.append("route B: the owner's exception text is not quoted verbatim")
        if "NOT SATISFIED" not in notes:
            problems.append("route B: the unsatisfied gate is not disclosed")
    elif g.get("route") == "A":
        if f"accepted gate input {g.get('gate_input')}" not in notes:
            problems.append("route A: accepted gate input absent")
    else:
        problems.append("policy record has no Gate #15 route")
    active = set(policy.get("activations_active") or [])
    for name, _ in ACTIVATIONS:
        want = f"- {name}: {'ACTIVE' if name in active else 'INACTIVE'}"
        if want not in notes:
            problems.append(f"activation line missing or wrong for {name!r}")
    if "Phase-5 contribution anatomy: a READER of registered protocol lines" not in notes:
        problems.append("Phase-5 reader statement missing")
    if re.search(r"independently replicated", notes, re.I):
        problems.append("banned phrase")
    return problems
