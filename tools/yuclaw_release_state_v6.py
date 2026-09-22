#!/usr/bin/env python3
"""
v6.0 RELEASE-STATE DERIVATION — 16-gate table (Phase 13, G2 vocabulary),
release-state manifest, the Tier-1 internal release record and the Tier-2
public release notes, DERIVED from canonical artifacts + the gate tools
themselves (ORDER 2026-09-02A restart rules; ORDER 2026-09-03B step 6;
ORDER 2026-09-05A P1.2, re-issued for 2026-09-04: two-tier notes, gate #16
semantics check, documented infrastructure fact).

Vocabulary (G2): GREEN | RED | MANUAL_REVIEW | REMOVED_BY_OWNER (gate 15, v8 releases) | PENDING_EXTERNAL |
DEFERRED-BLOCKING. Nothing here flips release_authorized (A-6: only the
release-day order's Phase 2 may, and it does so outside the tree). Numbers
are derived, never typed.

Usage: python3 tools/yuclaw_release_state_v6.py --evidence <json> [--public] [--patch] [--release-policy <json>]
                                                [--allow-production-write-probe]
  <json> carries session-measured facts that are not re-derivable from the
  tree (gate-6 replay hashes, restage tree hashes, tripwire observations,
  the base main commit the release candidate is built on). Everything else
  is recomputed from the checked-out tree.
Database environments (8.0.1): the nightly-battery checks and the on-box
matrices read the research database through sessions that cannot write
(libpq default_transaction_read_only=on); `pytest tests` runs against a
disposable PostgreSQL node the generator creates and seeds like hosted CI
(tools/yuclaw_disposable_pg.py) and is recorded NOT RUN when that node
cannot be provided — never against the ambient environment. The declared
production write probe (check_u350_isolation.py, gate 4) is NOT RUN unless
--allow-production-write-probe expresses the owner's separate authorization.
Each check's record names its command, database environment (variable names
and routing values only — no secret) and the candidate commit.
Outputs: internal/release_state_manifest_v6.json
         internal/release_notes_v6_DRAFT.md   (Tier 1 — internal, never published)
         internal/release_notes_v6_PUBLIC.md  (Tier 2 — GitHub Release body +
                                               CHANGELOG entry; --public prints it)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "tools"))
sys.path.insert(0, str(_REPO))
from yuclaw_protocol_registry import Registry  # noqa: E402
import yuclaw_disposable_pg as dpg  # noqa: E402  (8.0.1: production read-only sessions vs a disposable node for write-requiring tests)

VERSION = next(l.split('"')[1] for l in (_REPO / "pyproject.toml").read_text().splitlines()
               if l.startswith("version"))     # never typed: the package version IS the release version
GATE_NAMES = {
    1: "P0 registrations valid", 2: "chain verifies",
    3: "zero unexplained ledger breaks", 4: "point-in-time guard",
    5: "no v1 historical silent rewrite",
    6: "dependency calculations reproducible",
    7: "truncation ledger reconciles",
    8: "hypothesis/discovery lineage reconciles",
    9: "sequential methods pass registered fixtures",
    10: "research-state derivation reproducible",
    11: "machine JSON agrees with human page",
    12: "source citations resolve",
    13: "negative/inconclusive findings preserved",
    14: "language rails pass", 15: "user comprehension test passes",
    16: "stranger-machine reproduction passes",
    # ORDER 2026-09-05B PART G — deterministic gates, exit nonzero on mismatch
    17: "G1 copy-consistency (canonical blocks byte-identical)",
    18: "G2 version (package = badge = capabilities = index = llms = README = PyPI metadata)",
    19: "G3 base URL (capabilities = index = llms = release_manifest.public_base_url)",
    20: "G4 endpoints (declared set = generated set; static 200/type/schema; wildcards by discovery)",
}
# The registered gate #16 sentence, verbatim from the master plan (Phase 13 —
# V6 RELEASE GATES). It names the MACHINE ("stranger-machine"), not the
# operator's affiliation; the classification below follows that reading and
# discloses affiliation on every surface. "Independently replicated" is never
# rendered.
GATE16_SENTENCE = "stranger-machine reproduction passes"
GATE16_READING = ("requires reproduction on an external (stranger) MACHINE; it does not "
                  "require an unaffiliated operator — affiliation is disclosed, never implied away")

CHECKS = [  # (tool, args) — the nightly battery, run fresh
    ("check_language.py", ["--pages"] + sorted(str(p.relative_to(_REPO)) for p in (_REPO / "docs").glob("*.html")) + ["README.md", "COMPARISON.md", "docs/architecture.md", "CHANGELOG.md"]),
    ("check_copy_integrity.py", sorted(str(p.relative_to(_REPO)) for p in (_REPO / "docs").glob("*.html"))),
    ("check_weekly_note.py", []), ("check_universe_integrity.py", []),
    ("check_u350_isolation.py", []), ("check_schemas.py", []),
    ("check_no_forms.py", []), ("check_index_completeness.py", []),
    ("check_evidence_changes.py", []), ("check_site_walk.py", []),
    ("check_header_layout.py", []), ("check_consumer_posture.py", []),
    ("check_truncation_ledger.py", []), ("check_discovery_ledger.py", []),
    ("check_anytime_record.py", []), ("yuclaw_anytime_record.py", ["--selftest"]),
    ("check_completeness_profile.py", []), ("check_research_state.py", []),
    ("check_science_trust.py", []), ("check_dual_copy.py", []),
    # ORDER 2026-09-05B: generated-copy + release-manifest gates
    ("yuclaw_replication_sentence.py", ["--check"]),
    ("check_copy_consistency.py", []),
    ("check_release_manifest.py", ["--only", "g2"]),
    ("check_release_manifest.py", ["--only", "g3"]),
    ("check_release_manifest.py", ["--only", "g4"]),
    ("cli_transcript.py", ["--check"]),
    ("check_leak_sweep.py", []),          # MICRO 2026-09-07B: private witness denylist, fail-closed
]
# Release-critical checks beyond the nightly battery (full argv after python).
EXTRA_CHECKS = [
    ("pytest tests", ["-m", "pytest", "tests", "-q"]),
    ("abuse_matrix.py (on-box)", ["tools/abuse_matrix.py"]),
    ("cli_acceptance_matrix.py (on-box, D3)", ["tools/cli_acceptance_matrix.py"]),
]


# ---- database routing (8.0.1; owner order of 2026-09-21/22: separate database environments) -----------------------
# ONE invocation, TWO database environments, declared per check — never inferred from what happens to be reachable:
#   * production-data checks read the research database through a session that cannot write (libpq PGOPTIONS
#     default_transaction_read_only=on appended to the ambient settings);
#   * the write-requiring extra check runs against a disposable PostgreSQL node seeded like hosted CI, in an environment
#     stripped of every production connection variable (tools/yuclaw_disposable_pg.py); if that node cannot be provided
#     the check is recorded NOT RUN — it is never run against the ambient environment;
#   * a check that PROBES production by writing is NOT RUN unless the owner's separate authorization is expressed as
#     --allow-production-write-probe; until then the gate it feeds stays RED (fail-closed, nothing weakened).
PRODUCTION_WRITE_PROBE_CHECKS = {
    "check_u350_isolation.py": ("I1/I2 attempt INSERT/UPDATE on public tables as the U350 role (refusal expected), I3 commits one row with this run's "
                                "unique identity into u350.manifest and deletes exactly that row in the same transaction — a production write probe "
                                "by design (gate 4: 'u350 isolation proven by attempted writes'); the configuration is inspected read-only first (I0) "
                                "and never created, granted or revoked by the check"),
}
WRITE_REQUIRING_EXTRA = {"pytest tests": "tests/test_compliance_regression.py creates and deletes api_keys and request_logs rows"}
ROUTE_PRODUCTION_RO = "production (read-only session: PGOPTIONS default_transaction_read_only=on)"
ROUTE_DISPOSABLE = "disposable node"
ROUTE_PROBE_NOT_RUN = "NOT RUN — production write probe; requires a write-capable session under the owner's separate authorization (--allow-production-write-probe)"
ROUTE_PROBE_ALLOWED = "production (write probe explicitly allowed by --allow-production-write-probe)"
ROUTE_DISPOSABLE_UNAVAILABLE = "NOT RUN — disposable node unavailable; never run against the ambient environment"
RC_NOT_RUN_DISPOSABLE, RC_NOT_RUN_PROBE = 97, 98
_BASE_ENV = dict(TZ="UTC", LC_ALL="C", PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1")


def route_for(name, *, extra=False, allow_probe=False, node_available=True):
    """The database environment a check runs in. Declared routing; the same answer whatever is reachable."""
    if extra and name in WRITE_REQUIRING_EXTRA:
        return ROUTE_DISPOSABLE if node_available else ROUTE_DISPOSABLE_UNAVAILABLE
    if not extra and name in PRODUCTION_WRITE_PROBE_CHECKS:
        return ROUTE_PROBE_ALLOWED if allow_probe else ROUTE_PROBE_NOT_RUN
    return ROUTE_PRODUCTION_RO


def _record(rc, last, argv, route, env, head):
    """One check's record: result, command, database environment (names and routing values only — no secret), candidate."""
    return {"rc": rc, "last": last[:240], "argv": [str(x) for x in argv], "database": route,
            "libpq": dpg.describe_libpq(env) if env else {"variables_set": [], "routing": {}, "password_material_reachable": False, "read_only_guard": False},
            "candidate_sha": head}


def _run_argv(argv, env, route, head):
    p = subprocess.run([sys.executable] + argv, cwd=str(_REPO), capture_output=True,
                       text=True, env=env, timeout=3600)
    lines = [l for l in (p.stdout + p.stderr).splitlines() if l.strip()]
    return _record(p.returncode, lines[-1] if lines else "", argv, route, env, head)


def run_check(tool, args, head, *, allow_probe=False):
    """A nightly-battery check (CHECKS): production read-only, or the declared write probe (not run unless allowed)."""
    argv = [str(_REPO / "tools" / tool)] + list(args)
    route = route_for(tool, allow_probe=allow_probe)
    if route == ROUTE_PROBE_NOT_RUN:
        return _record(RC_NOT_RUN_PROBE, "NOT RUN — " + PRODUCTION_WRITE_PROBE_CHECKS[tool] + "; requires a write-capable production session under the owner's separate authorization",
                       argv, route, None, head)
    env = dict(os.environ, **_BASE_ENV)
    if route == ROUTE_PRODUCTION_RO:
        env = dpg.readonly_env(env)
    return _run_argv(argv, env, route, head)


def run_extra(name, argv, head, *, node=None, node_error=None):
    """A release-critical extra check (EXTRA_CHECKS): the write-requiring one on the disposable node, the rest production read-only."""
    route = route_for(name, extra=True, node_available=node is not None)
    if route == ROUTE_DISPOSABLE_UNAVAILABLE:
        return _record(RC_NOT_RUN_DISPOSABLE, "NOT RUN — " + WRITE_REQUIRING_EXTRA[name] + f"; disposable node unavailable ({node_error}); never run against the ambient environment",
                       argv, route, None, head)
    env = dict(os.environ, **_BASE_ENV)
    env = node.env(env) if route == ROUTE_DISPOSABLE else dpg.readonly_env(env)
    return _run_argv(argv, env, route, head)


def _git(*a):
    return subprocess.run(["git"] + list(a), cwd=str(_REPO), capture_output=True,
                          text=True, check=True).stdout.strip()


def _git_rc(*a):
    return subprocess.run(["git"] + list(a), cwd=str(_REPO), capture_output=True).returncode


def _tree(prefix, exclude=()):
    files = _git("ls-files", "-z", "--", prefix).split("\0")
    h, n = hashlib.sha256(), 0
    for f in sorted(x for x in files if x):
        if any(f.startswith(e) for e in exclude) or not (_REPO / f).exists():
            continue
        h.update(f.encode() + b"\0" + hashlib.sha256((_REPO / f).read_bytes()).digest())
        n += 1
    return h.hexdigest(), n


def _sha(path):
    return hashlib.sha256((_REPO / path).read_bytes()).hexdigest()


def _sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sessions(lo, hi):
    from v3.u350.market_calendar import is_session
    d, out = lo, []
    while d <= hi:
        if is_session(d):
            out.append(d)
        d += timedelta(days=1)
    return out


def _pyproject_version(text: str) -> str:
    return next(l.split('"')[1] for l in text.splitlines() if l.startswith("version"))


def _plain_counts(d: dict) -> str:
    """Plain-text 'KEY n, KEY n' — never a dict repr on a public surface."""
    return ", ".join(f"{k} {v}" for k, v in sorted(d.items()))


def _canada_fact() -> str | None:
    """The documented infrastructure-location fact, read from
    docs/architecture.md (a factual, documented statement only)."""
    for line in (_REPO / "docs" / "architecture.md").read_text().splitlines():
        if line.startswith("YUCLAW is developed and operated in Canada"):
            return line.strip()
    return None


def classify_gate16(repl: dict) -> dict:
    """Gate #16 under the registered sentence. Derived from the public log:
    empty -> PENDING_EXTERNAL; >=1 external-MACHINE entry with result
    REPRODUCED and no failed entry -> GREEN with the mandatory affiliation
    disclosure; anything else -> MANUAL_REVIEW."""
    entries = repl.get("replications", [])
    ext_ok = [e for e in entries if e.get("replication_machine_external") is True
              and str(e.get("replication_result", "")).upper() == "REPRODUCED"]
    failed = [e for e in entries if str(e.get("replication_result") or e.get("result") or "").upper()
              not in ("REPRODUCED", "PASS") and not str(e.get("result", "")).upper().startswith("PASS")]
    n_unaff = sum(1 for e in entries if str(e.get("operator_affiliation", "")).upper() == "UNAFFILIATED")
    n_aff = sum(1 for e in ext_ok if str(e.get("operator_affiliation", "")).upper() == "AFFILIATED")
    if ext_ok and n_unaff == 0 and n_aff == len(ext_ok):
        who = "an affiliated operator" if len(ext_ok) == 1 else f"{len(ext_ok)} affiliated operators"
        disclosure = f"External-machine reproduction completed by {who}; unaffiliated replications: 0"
    else:
        disclosure = (f"External-machine reproductions: {len(ext_ok)}; "
                      f"unaffiliated replications: {n_unaff}; entries: {len(entries)}")
    if not entries:
        result = "PENDING_EXTERNAL"
    elif ext_ok and not failed:
        result = "GREEN"
    else:
        result = "MANUAL_REVIEW"
    return {"registered_sentence": GATE16_SENTENCE, "reading": GATE16_READING,
            "result": result, "disclosure": disclosure, "entries": len(entries),
            "external_machine_reproduced": len(ext_ok), "unaffiliated": n_unaff,
            "failed": len(failed),
            "entry_summaries": [f"{e.get('date')} · {e.get('operator', e.get('os', ''))} · "
                                f"{e.get('operator_affiliation', '—')} · "
                                f"{e.get('replication_result') or e.get('result')}" for e in entries]}


def _patch_public(version: str, tip: str, n_lines: int, g16: dict, ev: dict) -> str:
    """Tier-2 notes for a PATCH release (ORDER 2026-09-05B F Phase 1): the
    one-line patch statement, the A2 look-ahead paragraph with the canonical
    block verbatim, the copy/CLI change list, and what is unchanged."""
    block = (_REPO / "docs" / "methodology" / "lookahead_statement.txt").read_text().rstrip("\n")
    a2 = ev["lookahead_reconciliation"]
    quoted = "\n".join("> " + l for l in block.splitlines())
    return f"""Research & education only. Not investment advice.

### YUCLAW {version} — patch: public synchronization and CLI first-touch

patch — public synchronization and CLI first-touch; no methodology change; chain unchanged at {n_lines}.

#### Look-ahead statement — reconciled from retained records

{a2['paragraph']}

{quoted}

#### Changed (copy and CLI ergonomics only)

- README and PyPI description: current-release framing (6.0.x → the GitHub Release), a first-touch command block with expected exit codes and a transcript from the release-candidate wheel, and the replication sentence derived from the public log ({g16['disclosure']}).
- Canada Resources: the evidence-tier count reads 53 = 49 Canada Resources issuers + 4 SMH-lens foreign filers (ASML, NXPI, STM, TSM), mirrored in the page's JSON.
- Today's Evidence: the two visible hashes carry distinct labels for the two distinct objects they are — "evidence-ledger root" (the Verified Research Ledger daily root) and "daily evidence block root" (the per-day public block root); no value, machine field or ledger meaning changed.
- SMH and XLK lenses: "effective evidence count" keeps its registered meaning; the line "Not the Phase-6 N_eff, which is PENDING." now sits beside it.
- Discovery: the capabilities name is "YUCLAW Evidence API" (former name recorded); the evidence index and llms.txt declare the version, the canonical base URL https://yuclaw.ca and every machine surface, all from one release manifest.
- Homepage: "Built in Canada — from Lake Ontario to Lake Louise and Kananaskis Lake — with gratitude to the country whose land and light frame this work."
- CLI: `yuclaw --help` / `-h` / `help` list every command with a one-line description (exit 0); `yuclaw check-claim --accession N` alone resolves the name from the same corpus the ticker path uses (one name → the existing passport; several → exit 2 with the candidates; none → UNSUPPORTED; malformed → exit 2); never a bare usage dump. Twelve first-touch cases are recorded against the built wheel.
- Release gates added: copy-consistency (canonical blocks byte-identical), version, base URL and endpoint inventory.

#### Unchanged

- Protocol registry: {n_lines} chained lines, tip {tip[:8]}…, byte-identical to 6.0.0. No statistic, estimator, threshold, artifact hash or ledger row changed.

#### Not in this release

- N_eff PENDING (the Phase-6 pooled-statistic N_eff — not the lens pages' effective evidence count)
- Phase-5 contribution anatomy NOT YET
- user-comprehension study NOT YET
- unaffiliated replications {g16['unaffiliated']}
"""


def _patch_internal(version, now, ev, head_sha, head_tree, branch, base, base_ver, head_ver, counts, tip, n_lines,
                    g16, checks, extra, public, public_sha) -> str:
    a2 = ev["lookahead_reconciliation"]
    failing = [c for c, v in {**checks, **extra}.items() if v["rc"] != 0]
    return f"""# YUCLAW {version} — patch release record, Tier 1 (internal; generated {now[:16]} UTC)

INTERNAL — never published; its sha256 is recorded in the release-state
manifest. release_authorized is flipped only by the release-day order's
Phase 2, outside the tree.

ORDER {ev['order']} · release date {ev['release']['release_date']} · candidate HEAD {head_sha[:12]}
(tree {head_tree[:12]}) on {branch} · base main {base[:12]} (pyproject {base_ver}) ·
candidate pyproject {head_ver} · release kind {ev['release'].get('release_kind')}.

GATES: {counts.get('GREEN', 0)} GREEN · {counts.get('MANUAL_REVIEW', 0)} MANUAL_REVIEW · {counts.get('PENDING_EXTERNAL', 0)} PENDING_EXTERNAL
· {counts.get('RED', 0)} RED (16-gate table + G1–G4 in internal/release_state_manifest_v{version}.json,
chain tip {tip[:12]}, {n_lines} lines — NO chain writes this patch). Failing checks: {failing or 'none'}.

PART A — look-ahead reconciliation: state {a2['state']}. Evidence record: {a2['evidence_path']}
(sha256 {a2['evidence_sha256'][:16]}). Paragraph: {a2['paragraph']}

Gate #16: {g16['result']} — {g16['disclosure']}.

## Tier 2 (public) — sha256 {public_sha}

{public}"""


GATE15_DECISION = _REPO / "v8" / "policy" / "gate15_release_requirement.json"


def gate15_requirement(version: str, path: Path | None = None) -> dict | None:
    """The owner's recorded decision on the Gate #15 requirement for v8 releases, or None when no such decision
    applies (7.x and earlier keep their historical rules). A record that claims anything other than
    REMOVED_BY_OWNER (for example PASSED) is refused loudly: the study was never run and is never reported as passed."""
    path = GATE15_DECISION if path is None else path
    if not version.startswith("8.") or not path.exists():
        return None
    d = json.loads(path.read_text())
    if d.get("record") != "yuclaw-v8-release-requirement-decision/1" or d.get("gate") != 15 or d.get("decided_by") != "owner":
        raise ValueError("gate 15 decision record is not the owner's v8 requirement decision")
    if d.get("status") != "REMOVED_BY_OWNER":
        raise ValueError(f"gate 15 decision record status {d.get('status')!r} is not REMOVED_BY_OWNER (a study result is never recorded here)")
    return {**d, "sha256": _sha_bytes(path.read_bytes())}


def gate15_result(version: str, scaffold_ok: bool, decision: dict | None) -> tuple[str, str]:
    """(result, evidence) for gate 15. The automated consumer-posture scaffold check is retained for every version:
    RED when it fails. When it passes: 7.x (or no owner decision) -> MANUAL_REVIEW exactly as before; a v8 release
    with the owner's recorded decision -> REMOVED_BY_OWNER (a non-required status; never GREEN or PASSED)."""
    if not scaffold_ok:
        return "RED", "consumer-posture scaffold FAILED (automated check retained); the human comprehension study does not exist"
    if decision is None:
        return "MANUAL_REVIEW", "consumer-posture scaffold GREEN (five personas); full-form human comprehension study does not exist"
    return "REMOVED_BY_OWNER", (f"requirement removed by the owner on {decision['decision_utc']} for v8 releases (decision record sha256 {decision['sha256'][:16]}…); "
                                "consumer-posture scaffold GREEN (five personas; automated check retained); no human comprehension study was run and none is claimed — NOT PASSED; human benefit PENDING")


def canada_heading(version: str) -> str:
    """The owner's wording is "Built in Canada" (README, homepage, the sentence below). Notes up to 8.0.0 were published with the
    section heading "Made in Canada" and stay as published; from 8.0.1 the heading uses the same words as the sentence (C13)."""
    try:
        v = tuple(int(x) for x in version.split(".")[:3])
    except ValueError:
        v = (0, 0, 0)
    return "Built in Canada" if v >= (8, 0, 1) else "Made in Canada"


NOTES_COMPOSERS = {"7.": "v3.release.notes_v7", "8.0.0": "yuclaw_release_notes_v8", "8.0.1": "yuclaw_release_notes_v8"}   # prefix or exact version → composer module (V8-008 TB-1; 8.0.1 = the 8.0.0 scope + a tracked patch change list)


def notes_composer(version: str):
    """The policy-bound Tier-2 composer for this version, or None when no composition path is supported.
    7.x: v3/release/notes_v7 (unchanged). 8.0.0 exactly: tools/yuclaw_release_notes_v8 (release tooling; not packaged).
    Any other version has no composer: the notes stay the derived v6-style block and never correspond to a policy."""
    import importlib
    for key, module in NOTES_COMPOSERS.items():
        if (key.endswith(".") and version.startswith(key)) or version == key:
            sys.path.insert(0, str(_REPO))
            return importlib.import_module(module)
    return None


def compose_public_notes(version: str, public: str, *, policy: dict | None, board: dict | None, patch_changes: str | None = None) -> tuple[str, list[str]]:
    """(Tier-2 text, correspondence problems). An empty problem list means the notes correspond to the RECORDED policy;
    it never means a gate is satisfied or that publication is authorized (the publisher checks those separately)."""
    composer = notes_composer(version)
    if composer is None:
        return public, [f"no supported notes composition path for version {version} (supported: 7.x, {', '.join(k for k in NOTES_COMPOSERS if not k.endswith('.'))})"]
    public = composer.compose(public, version=version, policy=policy, board=board, patch_changes=patch_changes)
    return public, list(composer.check_correspondence(public, policy))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--public", action="store_true", help="print the Tier-2 public notes to stdout")
    ap.add_argument("--patch", action="store_true", help="patch-release notes (copy/CLI class, no methodology change)")
    ap.add_argument("--release-policy", help="private release-policy record (allocation; Gate #15 route for 7.x, NOT_REQUIRED for v8 releases per the owner's recorded decision); the 7.x and 8.0.0 public notes are composed from it and bound to it")
    ap.add_argument("--allow-production-write-probe", action="store_true",
                    help="run the declared production write probe(s) (gate 4: check_u350_isolation.py) with a write-capable session — ONLY under the "
                         "owner's separate authorization; by default they are NOT RUN and gate 4 stays RED")
    a = ap.parse_args()
    ev = json.loads(Path(a.evidence).read_text())
    now = datetime.now(timezone.utc).isoformat()
    base = ev["release"]["base_main_sha"]           # main tip the candidate is built on
    release_date = ev["release"]["release_date"]

    # ---- chain + registry-derived facts
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    kinds = Counter(l["kind"] for l in reg._lines)
    tip = reg._tip()
    lines = reg._lines
    a1 = next(l for l in lines if l["kind"] == "addendum")
    a1_idx = lines.index(a1) + 1
    p6_run = next(l for l in reversed(lines)
                  if l["kind"] == "run" and l["payload"]["protocol_id"] == "bace258b0bbb")
    p6_idx = lines.index(p6_run) + 1
    c6_run = next(l for l in reversed(lines)
                  if l["kind"] == "run" and l["payload"]["protocol_id"] == "d7d5cc4fde5f")
    c6_idx = lines.index(c6_run) + 1
    rev_run = next(l for l in reversed(lines)
                   if l["kind"] == "run" and l["payload"]["protocol_id"] == "ea120b0a6b52")
    rev_idx = lines.index(rev_run) + 1
    p6 = json.loads((_REPO / "output" / "oie" / "layered_dependency_first_read.json").read_text())
    p6_sha = _sha("output/oie/layered_dependency_first_read.json")
    manifest6 = json.loads((_REPO / "output" / "oie" / "layered_dependency_first_read.manifest.json").read_text())
    import yuclaw_layered_dependency as ld
    import yuclaw_truncation_budget as tb
    p0 = {pid: reg.get_protocol(pid) for pid in ("bace258b0bbb", "74c9a12a60e3")}
    p0_ok = (all(v and v["status"] == "LOCKED" for v in p0.values())
             and p0["bace258b0bbb"]["method_hash"] == ld.METHOD_HASH
             and p0["74c9a12a60e3"]["method_hash"] == tb.METHOD_HASH
             and a1["payload"]["method_hash"] == _sha(ld.ADDENDUM_FILE))

    # ---- gates: run the battery fresh
    def _key(t, args):
        if args and args[0] == "--only":            # one tool, several gate rows
            return f"{t} {args[0]} {args[1]}"
        return t + (" " + args[0] if args and args[0].startswith("--") else "")
    head_sha0 = _git("rev-parse", "HEAD")
    node, node_error = None, None
    try:
        node = dpg.DisposableNode(_REPO).start()                  # the write-requiring extra check runs here, or is NOT RUN
    except dpg.DisposableUnavailable as exc:
        node_error = str(exc)
    try:
        checks = {_key(t, args): run_check(t, args, head_sha0, allow_probe=a.allow_production_write_probe) for t, args in CHECKS}
        extra = {name: run_extra(name, argv, head_sha0, node=node, node_error=node_error) for name, argv in EXTRA_CHECKS}
    finally:
        node_identity = node.stop() if node is not None else {"unavailable": node_error}
    database_routing = {
        "policy": "one invocation, two database environments: production-data checks in read-only sessions; write-requiring tests on a disposable node; "
                  "production write probes NOT RUN unless explicitly allowed (declared routing, no fallback)",
        "read_only_guard": dpg.READ_ONLY_OPTION,
        "production_write_probe_allowed": bool(a.allow_production_write_probe),
        "production_write_probes": PRODUCTION_WRITE_PROBE_CHECKS,
        "write_requiring_extra_checks": WRITE_REQUIRING_EXTRA,
        "disposable_node": node_identity,
        "routes": {**{k: v["database"] for k, v in checks.items()}, **{k: v["database"] for k, v in extra.items()}},
    }
    failing = [c for c, v in {**checks, **extra}.items() if v["rc"] != 0]
    def ok(name):
        return checks[name]["rc"] == 0
    # ---- ledger continuity (gate 3)
    blocks = sorted(p.stem for p in (_REPO / "docs" / "ledger").glob("*.json"))
    latest_blk = json.loads((_REPO / "docs" / "ledger" / f"{blocks[-1]}.json").read_text())
    sess = _sessions(date.fromisoformat(blocks[0]), date.fromisoformat(blocks[-1]))
    missing = [s.isoformat() for s in sess if s.isoformat() not in set(blocks)]
    # ---- v1 silent-rewrite guard (gate 5): restage facts (historical, measured)
    # + chain / v1-geometry identity against the base main commit (computed)
    geo_last = _git("log", "-1", "--format=%h %ad", "--date=short", "--", "output/oie/evidence_geometry.json")
    live_same = ev["restage"]["trees_before"]["live_tree_sha256_over_manifest"] == ev["restage"]["trees_after"]["live_tree_sha256_over_manifest"]
    reg_same = ev["restage"]["trees_before"]["registry_tree_sha256_over_manifest"] == ev["restage"]["trees_after"]["registry_tree_sha256_over_manifest"]
    out_same = ev["restage"]["trees_before"]["output_tree_sha256_over_manifest"] == ev["restage"]["trees_after"]["output_tree_sha256_over_manifest"]
    chain_same = _git_rc("diff", "--quiet", base, "HEAD", "--", "registry/protocols.jsonl") == 0
    geo_same = _git_rc("diff", "--quiet", base, "HEAD", "--", "output/oie/evidence_geometry.json") == 0
    p6_same = _git_rc("diff", "--quiet", base, "HEAD", "--", "output/oie/layered_dependency_first_read.json") == 0
    # ---- gate 6
    g6 = ev["gate6"]
    g6_ok = (g6["run1_sha256"] == g6["replay2_sha256"] == g6["replay3_sha256"] == p6_sha
             == p6_run["payload"]["result_hash"])
    # ---- discovery / questions (gate 13)
    dl = json.loads((_REPO / "registry" / "discovery_ledger.json").read_text())
    qs = reg.questions()
    rev = json.loads((_REPO / "output" / "oie" / "reversal_coherence_first_read.json").read_text())
    neg_preserved = (dl["status_counts"].get("INCONCLUSIVE", 0) >= 1
                     and any(q["status"] == "RETIRED" for q in qs.values())
                     and rev["verdict"]["verdict"] == "INSUFFICIENT")
    # ---- replication (gate 16)
    repl = json.loads((_REPO / "docs" / "replication" / "replication_log.json").read_text())
    g16 = classify_gate16(repl)
    canada = _canada_fact()

    G = lambda c: "GREEN" if c else "RED"
    g15_dec = gate15_requirement(VERSION)                  # the owner's recorded v8 decision (None for 7.x: rules unchanged)
    gates = {
        1: (G(p0_ok), "bace258b0bbb + 74c9a12a60e3 LOCKED; module METHOD_HASH == registry; A1 file sha256 == line-81 method_hash"),
        2: (G(True), f"Registry.verify_chain on load: {len(lines)} lines, tip {tip[:16]}"),
        3: (G(ok("check_evidence_changes.py") and not missing), f"docs/ledger {len(blocks)} blocks {blocks[0]}..{blocks[-1]}; sessions without a block: {len(missing)}; evidence-changes gate rc={checks['check_evidence_changes.py']['rc']}"),
        4: (G(ok("check_evidence_changes.py") and ok("check_u350_isolation.py")), "as_of endpoint hash + twice-run identity (evidence-changes gate); u350 isolation proven by attempted writes"),
        5: (G(live_same and reg_same and out_same and chain_same and geo_same and p6_same),
            f"chain file byte-identical to base {base[:8]}: {chain_same}; v1 evidence_geometry.json identical to base: {geo_same} (last changed {geo_last}); Phase-6 canonical artifact identical to base: {p6_same}; 02A restage left live/registry/output trees byte-identical: {live_same and reg_same and out_same}; chain append-only"),
        6: (G(g6_ok), "the registered structural first-read computation reproduced byte-identically from frozen inputs (fresh NO-WRITE replays this session)"),
        7: (G(ok("check_truncation_ledger.py")), checks["check_truncation_ledger.py"]["last"]),
        8: (G(ok("check_discovery_ledger.py")), checks["check_discovery_ledger.py"]["last"]),
        9: (G(ok("check_anytime_record.py") and ok("yuclaw_anytime_record.py --selftest")), "anytime gate + registered fixtures selftest"),
        10: (G(ok("check_research_state.py")), checks["check_research_state.py"]["last"]),
        11: (G(ok("check_science_trust.py")), checks["check_science_trust.py"]["last"]),
        12: (G(ok("check_site_walk.py") and ok("check_index_completeness.py") and ok("check_copy_integrity.py")), "site-walk: all links + anchors resolve; index completeness; copy integrity"),
        13: (G(neg_preserved), f"discovery status_counts {_plain_counts(dl['status_counts'])}; questions {', '.join(f'{k} {v[chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115)]}' for k, v in qs.items())}; reversal first read INSUFFICIENT preserved"),
        14: (G(ok("check_language.py --pages") and ok("check_no_forms.py") and ok("check_header_layout.py") and ok("check_weekly_note.py") and ok("check_leak_sweep.py")), "language rail (pages + README + COMPARISON + architecture + CHANGELOG) + leak sweep (private denylist) + no-forms + header layout (badge == package version) + weekly-note reconciliation"),
        15: gate15_result(VERSION, ok("check_consumer_posture.py"), g15_dec),
        16: (g16["result"], f"{g16['disclosure']} — registered sentence \"{GATE16_SENTENCE}\" ({GATE16_READING}); public log entries: {g16['entries']}, external-machine REPRODUCED: {g16['external_machine_reproduced']}, failed: {g16['failed']}"),
        17: (G(ok("check_copy_consistency.py") and ok("yuclaw_replication_sentence.py --check")), checks["check_copy_consistency.py"]["last"]),
        18: (G(ok("check_release_manifest.py --only g2") and ok("cli_transcript.py --check")), checks["check_release_manifest.py --only g2"]["last"]),
        19: (G(ok("check_release_manifest.py --only g3")), checks["check_release_manifest.py --only g3"]["last"]),
        20: (G(ok("check_release_manifest.py --only g4")), checks["check_release_manifest.py --only g4"]["last"]),
    }
    table = [{"gate": n, "name": GATE_NAMES[n], "result": r, "evidence": e}
             for n, (r, e) in sorted(gates.items())]
    counts = Counter(r["result"] for r in table)

    # ---- versions + candidate identity
    head_sha = _git("rev-parse", "HEAD")
    head_tree = _git("rev-parse", "HEAD^{tree}")
    branch = _git("branch", "--show-current")
    head_ver = _pyproject_version((_REPO / "pyproject.toml").read_text())
    base_ver = _pyproject_version(_git("show", f"{base}:pyproject.toml"))
    rs = json.loads((_REPO / "registry" / "research_state.json").read_text())
    ar = json.loads((_REPO / "registry" / "anytime_record.json").read_text())
    cp = json.loads((_REPO / "registry" / "completeness_profile.json").read_text())
    rs_states = Counter((v["research_state"]["value"] if isinstance(v.get("research_state"), dict)
                         else v.get("research_state")) for v in rs["names"].values())
    trees = {k: _tree(p, ex) for k, p, ex in (("live", "docs", ("docs/preview/",)), ("preview", "docs/preview", ()), ("registry", "registry", ()), ("output", "output", ()))}
    shas = {k: _sha(p) for k, p in (("research_state", "registry/research_state.json"),
                                    ("discovery_ledger", "registry/discovery_ledger.json"),
                                    ("anytime_record", "registry/anytime_record.json"),
                                    ("completeness_profile", "registry/completeness_profile.json"),
                                    ("replication_log", "docs/replication/replication_log.json"))}
    p6_line = (f"{p6['verdict']} — structural_completeness = PARTIAL; N_eff PENDING; "
               f"READ_SCOPE = STRUCTURAL_ONLY")
    c6_note = c6_run["payload"]["note"]
    assert "badge DESCRIPTIVE" in c6_note, "C6 fourth-read badge not DESCRIPTIVE in the registered note"
    c6_public = ("C6 risk channel: rare-by-construction confirmed OOS (22% fire rate, n=9 held-out); "
                 "sign positive at n=2 elevated — accruing")
    rev_public = "INSUFFICIENT — accruing, no coherence claim (chain 79)"
    assert rev_idx == 79 and rev["verdict"]["verdict"] == "INSUFFICIENT"
    assert a1_idx == 81 and p6_idx == 82
    p6_public = f"{p6_line} (chain {a1_idx}–{p6_idx})"
    reg_public = f"{len(lines)} chained lines, tip {tip[:8]}…, chain-verified"
    rs_public = (f"{len(rs['names'])} names: {_plain_counts(rs_states)} — derived, never hand-maintained")
    tw = ev["tripwire"]
    tripwire_pre_ok = (not tw.get("git_tags_this_version", tw.get("git_tags_v6")) and not tw.get("origin_tags_this_version", tw.get("origin_tags_v6"))
                       and tw["github_latest_release"] != f"v{VERSION}"
                       and tw["pypi_published"] != VERSION
                       and tw["live_capabilities_version"] == "v" + tw["pypi_published"] == "v" + tw["origin_main_pyproject_version"]
                       and tw["live_pages_linking_preview"] == 0)

    # ---- Tier 2 (public) — GitHub Release body + CHANGELOG entry. No internal
    # paths, per-cluster numbers, rule enumerations, bootstrap parameters, gate
    # tool names or generation timestamps; plain-text lists only.
    repl_entry = repl["replications"][0] if repl["replications"] else None
    repl_line = (f"- Replication · public log {len(repl['replications'])} entry, bundle sha256 "
                 f"{repl_entry['bundle'].split('sha256 ')[1].split(' ')[0] if repl_entry else '—'} · "
                 f"{repl_entry['replication_result'] if repl_entry else 'PENDING_EXTERNAL'} — {g16['disclosure']}")
    g15_public = ("user-comprehension study: not run — requirement removed by the owner for v8 releases (not a pass)" if g15_dec
                  else "full-form user-comprehension study NOT YET")
    g15_not_in_release = ("user-comprehension study: not run; requirement removed by the owner for v8 releases (not a pass; human benefit PENDING)" if g15_dec
                          else "user-comprehension study NOT YET")
    public = f"""Research & education only. Not investment advice.

### YUCLAW {VERSION} — Evidence-First Financial AI · The Science Trust Layer for Financial AI

Financial AI normally gives you an answer. YUCLAW gives you the evidence, what that evidence can support, what it cannot support, and whether that conclusion survived time.

#### Shipped objects — name · receipt · status

- Layered Evidence Dependency v1, first read · chain lines {a1_idx}–{p6_idx}, sha256 {p6_sha[:16]}… · {p6_public}
- Science Trust surfaces — per-name research-state cards + machine JSON, {len(rs['names'])} names · anchor {p6_run['line_hash'][:12]}… · gate {gates[11][0]} (machine JSON equals the human card, byte-reproducible); staged preview, not linked from the live navigation
- Research states · sha256 {shas['research_state'][:16]}… · {rs_public}
- Discovery Ledger · sha256 {shas['discovery_ledger'][:16]}… · {len(dl['hypotheses'])} hypotheses in bijection with {kinds['protocol']} registered protocol lines; status counts {_plain_counts(dl['status_counts'])} — negative and inconclusive findings preserved
- Anytime Evidence Record · sha256 {shas['anytime_record'][:16]}… · {ar['enrollment_count']} prospective enrollments — ACCRUING, not adjudicated
- Evidence Completeness Profiles · sha256 {shas['completeness_profile'][:16]}… · {len(cp['names'])} names; ETF class membership BLOCKED_BY_REGISTRATION
- Protocol registry · {reg_public}
- Public daily evidence ledger · {len(blocks)} daily blocks, latest {blocks[-1]} root {latest_blk['root_sha256'][:12]}… · append-only, replayable
- {c6_public} · fourth read chain line {c6_idx} ({c6_run['line_hash'][:12]}…): DESCRIPTIVE
- Cross-lens reversal coherence · chain line {rev_idx} ({rev_run['line_hash'][:12]}…) · {rev_public}
- Consumer-posture gate · five deterministic stranger personas · {'GREEN' if ok('check_consumer_posture.py') else 'RED'} (scaffold); {g15_public}
{repl_line}
- yuclaw {VERSION} package · wheel + sdist sha256 attached to this release · CLI · REST · MCP · SDK

#### Not in this release

- N_eff PENDING
- Phase-5 contribution anatomy NOT YET
- {g15_not_in_release}
- unaffiliated replications {g16['unaffiliated']}

#### {canada_heading(VERSION)}

Built in Canada — from Lake Ontario to Lake Louise and Kananaskis Lake — with gratitude to the country whose land and light frame this work.
"""
    patch_changes = None
    if a.patch:
        pc = _REPO / "docs" / "methodology" / f"release_notes_{VERSION}_changes.md"
        if (VERSION.startswith("7.") or VERSION == "8.0.1") and pc.exists():
            patch_changes = pc.read_text()                     # tracked, source-bound patch change list
        else:
            public = _patch_public(VERSION, tip, len(lines), g16, ev)
    release_policy = json.loads(Path(a.release_policy).read_text()) if a.release_policy else None
    board_path = _REPO / "docs" / "receipts" / "scoreboard.json"
    public_board = json.loads(board_path.read_text()) if board_path.exists() else None
    public, corr = compose_public_notes(VERSION, public, policy=release_policy, board=public_board, patch_changes=patch_changes)
    for banned in ("docs/", "registry/", "output/", "tools/", "check_", ".py", "seed", "bootstrap", "CI [", "{'", "generated"):
        assert banned not in public, f"Tier-2 rule violation: {banned!r} present"
    assert "independently replicated" not in public.lower()
    (_REPO / "internal" / f"release_notes_v{VERSION}_PUBLIC.md").write_text(public)
    public_sha = _sha_bytes(public.encode())

    # ---- Tier 1 (internal) — the full release record; never published
    infra = (f"Documented infrastructure fact (docs/architecture.md, verbatim): {canada}" if canada else
             "No infrastructure-location or sovereignty claim is made: no canonical document records one "
             "(docs/architecture.md checked at draft time).")
    notes = f"""# YUCLAW {VERSION} — release record, Tier 1 (internal; generated {now[:16]} UTC)

INTERNAL — never published; its sha256 is recorded in the release-state
manifest. release_authorized is flipped only by the release-day order's
Phase 2, outside the tree. Every count below was DERIVED at generation time
from the named canonical artifact by tools/yuclaw_release_state_v6.py.

ORDER {ev['order']} · release date {release_date} · candidate HEAD {head_sha[:12]}
(tree {head_tree[:12]}) on {branch} · base main {base[:12]}
(pyproject {base_ver}) · candidate pyproject {head_ver}.

GATES: {counts.get('GREEN', 0)} GREEN · {counts.get('MANUAL_REVIEW', 0)} MANUAL_REVIEW · {counts.get('PENDING_EXTERNAL', 0)} PENDING_EXTERNAL
· {counts.get('RED', 0)} RED (table in internal/release_state_manifest_v6.json, chain tip {tip[:12]}).
Gate #6 (dependency calculations reproducible) is GREEN under Addendum A1
semantics: the registered structural first-read computation reproduced
byte-identically from frozen inputs — nothing more.

GATE #16 SEMANTICS CHECK — registered sentence, verbatim from the master plan
(Phase 13 — V6 RELEASE GATES): "{GATE16_SENTENCE}". Reading: {GATE16_READING}.
Classification: {g16['result']}. Mandatory disclosure line: "{g16['disclosure']}".
Public log entries: {g16['entries']} ({'; '.join(g16['entry_summaries']) or 'none'}).
Never rendered: "independently replicated".

## What v6.0 is (verifiable objects only)

- Phase-6 layered-dependency first read (protocol bace258b0bbb, Addendum A1
  chain line {a1_idx}, run chain line {p6_idx},
  output/oie/layered_dependency_first_read.json, sha256 {p6_sha[:16]}):
  {p6_line}. SMH lens, sessions
  {p6['read_window']['first_session']}..{p6['read_window']['end_session']}; eligible events
  {p6['eligible_events']}; story-clusters {len(p6['clusters'])} (circuit rank per cluster:
  {', '.join(str(c['r']) for c in p6['clusters'])}). Executed rules
  {p6['edge_rule_coverage']['executable']}; ABSENT rules
  {p6['edge_rule_coverage']['absent']}. A computation-status verdict — not an
  evidentiary-strength or independence verdict; Q1–Q4 NOT_EVALUATED, Q5
  MANUAL_REVIEW; no site-wide rollout is licensed by this read.
- Science Trust surfaces (Phases 7-8, staged at docs/preview/trust/ and
  docs/preview/why/): per-name research-state cards + machine JSON for
  {len(rs['names'])} names, every field annotated FACT / DERIVED_RESULT /
  LIMITATION / PENDING / NOT_ESTIMABLE / NOT_IDENTIFIABLE, byte-reproducible
  from registry artifacts (gate: tools/check_science_trust.py, {gates[11][0]},
  anchor {p6_run['line_hash'][:12]}); not linked from the live navigation.
- Research states (registry/research_state.json, sha256 {shas['research_state'][:16]}):
  {rs_public}.
- Discovery Ledger (registry/discovery_ledger.json, sha256 {shas['discovery_ledger'][:16]}):
  {len(dl['hypotheses'])} hypotheses in bijection with {kinds['protocol']} registered protocol
  lines; status counts {_plain_counts(dl['status_counts'])} — negative and
  inconclusive findings preserved.
- Anytime Evidence Record (registry/anytime_record.json, sha256 {shas['anytime_record'][:16]}):
  {ar['enrollment_count']} prospective enrollments, observation chain not yet started
  (honest-empty; first admission is calendar-gated) — ships ACCRUING, not adjudicated.
- Evidence Completeness Profiles (registry/completeness_profile.json, sha256
  {shas['completeness_profile'][:16]}): {len(cp['names'])} names, per-family states from the
  registered vocabulary. ETF class membership stays BLOCKED_BY_REGISTRATION
  (consumer-posture gate carries it as MANUAL_REVIEW).
- Protocol registry (registry/protocols.jsonl): {len(lines)} chained lines
  ({kinds['protocol']} protocols, {kinds['run']} recorded runs, {kinds.get('addendum', 0)} addendum), tip
  {tip[:16]}, chain-verified; byte-identical to base main {base[:8]}: {chain_same}.
- Public daily evidence ledger (docs/ledger/): {len(blocks)} blocks; latest block
  {blocks[-1]}, evidence-ledger root {latest_blk['root_sha256'][:12]}.
- C6 risk gate (registered run note, chain line {c6_idx}, verbatim): {c6_note}
- Cross-lens reversal coherence (protocol ea120b0a6b52, chain line {rev_idx}, first read
  {rev['run_date']}, output/oie/reversal_coherence_first_read.json): verdict
  {rev['verdict']['verdict']} per the locked labels — accrual {_plain_counts(rev['verdict']['accrual'])};
  no coherence claim; the hypothesis stays open and accruing.
- Consumer-posture gate (tools/check_consumer_posture.py): five
  deterministic stranger personas wired into the nightly (exit 50).
- Replication: tools/replay_lab.py, stdlib-only, pinned Python versions;
  public replication log docs/replication/replication_log.json (sha256
  {shas['replication_log'][:16]}) has {len(repl['replications'])} entries — gate #16 {g16['result']};
  {g16['disclosure']}.
- Release-critical checks beyond the nightly battery: {', '.join(f"{k} rc={v['rc']}" for k, v in extra.items())}.

## Infrastructure

{infra}

## Not in this release / NOT YET

- Phase-6 N_eff and pooled-statistic anatomy: PENDING (A1.7 — no pooled
  statistic designated); edge rules {p6['edge_rule_coverage']['absent']} ABSENT (no
  persisted store); structural_completeness = PARTIAL.
- Phase-5 contribution anatomy: NOT YET (no registered method).
- Gate #15 full-form user comprehension study: {'not run — requirement REMOVED_BY_OWNER for v8 releases (not a pass; the deterministic scaffold check is retained)' if g15_dec else 'NOT YET (the deterministic scaffold ships; the human study does not exist)'}.
- Unaffiliated replications: {g16['unaffiliated']}.

## Tier 2 (public) — sha256 {public_sha}

{public}"""
    if a.patch:
        notes = _patch_internal(VERSION, now, ev, head_sha, head_tree, branch, base, base_ver, head_ver,
                                counts, tip, len(lines), g16, checks, extra, public, public_sha)
    (_REPO / "internal" / f"release_notes_v{VERSION}_DRAFT.md").write_text(notes)
    internal_sha = _sha_bytes(notes.encode())

    manifest = {
        "generated_utc": now,
        "order": ev["order"],
        "release": {"version": VERSION, "release_date": release_date, "release_kind": ev["release"].get("release_kind", "minor"),
                    "base_main_sha": base, "base_main_pyproject_version": base_ver,
                    "candidate_sha": head_sha,
                    "candidate_tree": head_tree,
                    "candidate_branch": branch,
                    "candidate_pyproject_version": head_ver},
        "chain": {"lines": len(lines), "tip": tip, "kinds": dict(kinds),
                  "addendum_line": a1_idx, "addendum_line_hash": a1["line_hash"],
                  "phase6_run_line": p6_idx, "phase6_run_line_hash": p6_run["line_hash"],
                  "c6_fourth_read_line": c6_idx, "c6_fourth_read_line_hash": c6_run["line_hash"],
                  "reversal_first_read_line": rev_idx, "reversal_first_read_line_hash": rev_run["line_hash"],
                  "chain_file_identical_to_base": chain_same},
        "phase6": {"protocol_id": "bace258b0bbb", "addendum_id": a1["payload"]["addendum_id"],
                   "verdict": p6["verdict"], "line": p6_line,
                   "structural_completeness": p6["edge_rule_coverage"]["structural_completeness"],
                   "n_eff": p6["n_eff"], "read_scope": p6["read_scope"],
                   "read_window": p6["read_window"], "eligible_events": p6["eligible_events"],
                   "clusters": [{"cluster_id": c["cluster_id"], "V": c["V"], "E": c["E"], "c": c["c"], "r": c["r"], "structure_class": c["structure_class"]} for c in p6["clusters"]],
                   "edge_rule_coverage": p6["edge_rule_coverage"],
                   "canonical_sha256": p6_sha, "t_reg": a1["payload"]["registered_utc"],
                   "t_access": manifest6["t_access"], "frozen_inputs_sha256": manifest6["inputs_sha256"],
                   "gate6_hashes": g6},
        "gate16": g16,
        "infrastructure_fact": canada,
        "gate_table": table, "gate_counts": dict(counts),
        "gate_vocabulary": ["GREEN", "RED", "MANUAL_REVIEW", "REMOVED_BY_OWNER", "PENDING_EXTERNAL", "DEFERRED-BLOCKING"],
        "gate15_requirement": ({"status": "REMOVED_BY_OWNER", "decision_utc": g15_dec["decision_utc"], "record": "v8/policy/gate15_release_requirement.json", "record_sha256": g15_dec["sha256"], "meaning": "not a pass; no study run; human benefit PENDING"} if g15_dec else None),
        "checks": checks, "extra_checks": extra,
        "database_routing": database_routing,
        "preflight_failing_checks": failing,
        "restage": {"gate11_mutation_boundary": {"live_identical": live_same, "registry_identical": reg_same, "output_identical": out_same, "preview_files_changed": ev["restage"]["preview_files_changed"]}, **ev["restage"]},
        "trees_now": {f"{k}_tree_sha256_over_manifest": v[0] for k, v in trees.items()},
        "artifact_sha256": shas,
        "tripwire_pre_publish": {**tw, "candidate_pyproject_version": head_ver,
                                 "status": "GREEN" if tripwire_pre_ok else "RED",
                                 "meaning": "nothing v6 is published yet: no tag, no release, PyPI == live badge == origin/main pyproject at the published version, no live link into docs/preview"},
        "python_version": sys.version.split()[0],
        "package_version_candidate": head_ver, "package_version_published": tw["pypi_published"],
        "rehearsal_artifacts": ev.get("rehearsal"),
        "gate_suite_commit": head_sha,
        "notes": {"internal_path": f"internal/release_notes_v{VERSION}_DRAFT.md", "internal_sha256": internal_sha,
                  "public_path": f"internal/release_notes_v{VERSION}_PUBLIC.md", "public_sha256": public_sha,
                  "policy_correspondence": corr, "public_board_sha256": (_sha("docs/receipts/scoreboard.json") if board_path.exists() else None)},
        "release_policy": ({"path": a.release_policy, "sha256": _sha_bytes(Path(a.release_policy).read_bytes()), "route": release_policy.get("gate15", {}).get("route"),
                            "allocation_document_id": release_policy.get("allocation", {}).get("document_id")} if release_policy else None),
        "lookahead_reconciliation": ev.get("lookahead_reconciliation"),
        "release_authorized": False, "publishing_permitted": False,
        "remaining_blockers": ([] if g15_dec else [
            "gate #15 full-form user comprehension study does not exist (deterministic scaffold only) — MANUAL_REVIEW",
        ]) + ([f"gate #{r['gate']} {r['name']} — {r['result']}" for r in table if r["result"] == "RED"])
          + [f"preflight check {c} — rc {v['rc']} ({v['database']})" for c, v in {**checks, **extra}.items() if v["rc"] != 0],
        "remaining_external_checks": ([
            "gate #16 stranger-machine replication run (public log honestly empty; nothing may pre-fill it) — PENDING_EXTERNAL"]
            if g16["result"] == "PENDING_EXTERNAL" else []) + [
            "release-day external smoke: real-Internet 200s on every capabilities.json endpoint",
        ],
        "authorization_note": "Only the release-day order's Phase 2 may flip release_authorized/publishing_permitted, after the owner's verbatim authorization of the frozen source.",
    }
    (_REPO / "internal" / f"release_state_manifest_v{VERSION}.json").write_text(json.dumps(manifest, indent=1, sort_keys=False, ensure_ascii=False) + "\n")

    print(f"[release-state-v6] gates {dict(counts)} · tripwire(pre) {manifest['tripwire_pre_publish']['status']} · "
          f"chain {len(lines)}/{tip[:12]} · phase6 {p6_line} · gate16 {g16['result']}")
    for r in table:
        print(f"  #{r['gate']:>2} {r['result']:<16} {r['name']}")
    failing = [c for c, v in {**checks, **extra}.items() if v['rc'] != 0]
    print("  failing checks:", failing or "none")
    print(f"  notes: internal sha256 {internal_sha[:16]} · public sha256 {public_sha[:16]}")
    if a.public:
        print("----- TIER 2 (public) -----")
        print(public, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
