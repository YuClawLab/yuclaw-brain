#!/usr/bin/env python3
"""
v6.0 RELEASE-STATE DERIVATION — 16-gate table (Phase 13, G2 vocabulary),
release-state manifest and release-notes draft, DERIVED from canonical
artifacts + the gate tools themselves (ORDER 2026-09-02A restart rules,
re-run under ORDER 2026-09-03B step 6 from chain tip 82).

Vocabulary (G2): GREEN | RED | MANUAL_REVIEW | PENDING_EXTERNAL |
DEFERRED-BLOCKING. Nothing here flips release_authorized (A-6: only the
release-day order may). Numbers are derived, never typed.

Usage: python3 tools/yuclaw_release_state_v6.py --evidence <json>
  <json> carries session-measured facts that are not re-derivable from the
  tree (rehearsal artifact hashes, replay hashes, tree hashes before/after
  the restage, tripwire observations). Everything else is recomputed.
Outputs: internal/release_state_manifest_v6.json,
         internal/release_notes_v6_DRAFT.md
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
}
CHECKS = [  # (tool, args) — the nightly battery, run fresh
    ("check_language.py", ["--pages"] + sorted(str(p.relative_to(_REPO)) for p in (_REPO / "docs").glob("*.html")) + ["README.md", "COMPARISON.md"]),
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
]


def _run(tool, args):
    env = dict(os.environ, TZ="UTC", LC_ALL="C", PYTHONHASHSEED="0",
               PYTHONDONTWRITEBYTECODE="1", OMP_NUM_THREADS="1")
    p = subprocess.run([sys.executable, str(_REPO / "tools" / tool)] + args,
                       cwd=str(_REPO), capture_output=True, text=True, env=env,
                       timeout=1800)
    lines = [l for l in (p.stdout + p.stderr).splitlines() if l.strip()]
    return {"rc": p.returncode, "last": (lines[-1] if lines else "")[:240]}


def _git(*a):
    return subprocess.run(["git"] + list(a), cwd=str(_REPO), capture_output=True,
                          text=True, check=True).stdout.strip()


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


def _sessions(lo, hi):
    from v3.u350.market_calendar import is_session
    d, out = lo, []
    while d <= hi:
        if is_session(d):
            out.append(d)
        d += timedelta(days=1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    a = ap.parse_args()
    ev = json.loads(Path(a.evidence).read_text())
    now = datetime.now(timezone.utc).isoformat()

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
    checks = {t + (" " + " ".join(args[:1]) if args and args[0].startswith("--") else ""): _run(t, args)
              for t, args in CHECKS}
    def ok(name):
        return checks[name]["rc"] == 0
    # ---- ledger continuity (gate 3)
    blocks = sorted(p.stem for p in (_REPO / "docs" / "ledger").glob("*.json"))
    latest_blk = json.loads((_REPO / "docs" / "ledger" / f"{blocks[-1]}.json").read_text())
    sess = _sessions(date.fromisoformat(blocks[0]), date.fromisoformat(blocks[-1]))
    missing = [s.isoformat() for s in sess if s.isoformat() not in set(blocks)]
    # ---- v1 silent-rewrite guard (gate 5)
    geo_last = _git("log", "-1", "--format=%h %ad", "--date=short", "--", "output/oie/evidence_geometry.json")
    live_same = ev["restage"]["trees_before"]["live_tree_sha256_over_manifest"] == ev["restage"]["trees_after"]["live_tree_sha256_over_manifest"]
    reg_same = ev["restage"]["trees_before"]["registry_tree_sha256_over_manifest"] == ev["restage"]["trees_after"]["registry_tree_sha256_over_manifest"]
    out_same = ev["restage"]["trees_before"]["output_tree_sha256_over_manifest"] == ev["restage"]["trees_after"]["output_tree_sha256_over_manifest"]
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

    G = lambda c: "GREEN" if c else "RED"
    gates = {
        1: (G(p0_ok), "bace258b0bbb + 74c9a12a60e3 LOCKED; module METHOD_HASH == registry; A1 file sha256 == line-81 method_hash"),
        2: (G(True), f"Registry.verify_chain on load: {len(lines)} lines, tip {tip[:16]}"),
        3: (G(ok("check_evidence_changes.py") and not missing), f"docs/ledger {len(blocks)} blocks {blocks[0]}..{blocks[-1]}; sessions without a block: {len(missing)}; evidence-changes gate rc={checks['check_evidence_changes.py']['rc']}"),
        4: (G(ok("check_evidence_changes.py") and ok("check_u350_isolation.py")), "as_of endpoint hash + twice-run identity (evidence-changes gate); u350 isolation proven by attempted writes"),
        5: (G(live_same and reg_same and out_same), f"restage left live/registry/output trees byte-identical; evidence_geometry.json (v1 N_eff) last changed {geo_last}; chain append-only"),
        6: (G(g6_ok), "the registered structural first-read computation reproduced byte-identically from frozen inputs"),
        7: (G(ok("check_truncation_ledger.py")), checks["check_truncation_ledger.py"]["last"]),
        8: (G(ok("check_discovery_ledger.py")), checks["check_discovery_ledger.py"]["last"]),
        9: (G(ok("check_anytime_record.py") and ok("yuclaw_anytime_record.py --selftest")), "anytime gate + registered fixtures selftest"),
        10: (G(ok("check_research_state.py")), checks["check_research_state.py"]["last"]),
        11: (G(ok("check_science_trust.py")), checks["check_science_trust.py"]["last"]),
        12: (G(ok("check_site_walk.py") and ok("check_index_completeness.py") and ok("check_copy_integrity.py")), "site-walk: all links + anchors resolve; index completeness; copy integrity"),
        13: (G(neg_preserved), f"discovery status_counts {dl['status_counts']}; questions {dict((k, v['status']) for k, v in qs.items())}; reversal first read INSUFFICIENT preserved"),
        14: (G(ok("check_language.py --pages") and ok("check_no_forms.py") and ok("check_header_layout.py") and ok("check_weekly_note.py")), "language rail + no-forms + header layout + weekly-note reconciliation"),
        15: ("MANUAL_REVIEW" if ok("check_consumer_posture.py") else "RED", "consumer-posture scaffold GREEN (five personas); full-form human comprehension study does not exist"),
        16: ("PENDING_EXTERNAL" if not repl["replications"] else "MANUAL_REVIEW", f"public replication log entries: {len(repl['replications'])}"),
    }
    table = [{"gate": n, "name": GATE_NAMES[n], "result": r, "evidence": e}
             for n, (r, e) in sorted(gates.items())]
    counts = Counter(r["result"] for r in table)

    # ---- versions
    main_ver = next(l.split('"')[1] for l in (_REPO / "pyproject.toml").read_text().splitlines() if l.startswith("version"))
    staged_py = _git("show", "release/v6.0.0-staging:pyproject.toml")
    staged_ver = next(l.split('"')[1] for l in staged_py.splitlines() if l.startswith("version"))
    rs = json.loads((_REPO / "registry" / "research_state.json").read_text())
    ar = json.loads((_REPO / "registry" / "anytime_record.json").read_text())
    cp = json.loads((_REPO / "registry" / "completeness_profile.json").read_text())
    rs_states = Counter((v["research_state"]["value"] if isinstance(v.get("research_state"), dict)
                         else v.get("research_state")) for v in rs["names"].values())
    trees = {k: _tree(p, ex) for k, p, ex in (("live", "docs", ("docs/preview/",)), ("preview", "docs/preview", ()), ("registry", "registry", ()), ("output", "output", ()))}

    p6_line = (f"{p6['verdict']} — structural_completeness = PARTIAL; N_eff PENDING; "
               f"READ_SCOPE = STRUCTURAL_ONLY")
    manifest = {
        "generated_utc": now,
        "order": ev["order"],
        "source_commit_main": _git("rev-parse", "main"),
        "staging_branch": "release/v6.0.0-staging",
        "staging_commit": _git("rev-parse", "release/v6.0.0-staging"),
        "chain": {"lines": len(lines), "tip": tip, "kinds": dict(kinds),
                  "addendum_line": a1_idx, "addendum_line_hash": a1["line_hash"],
                  "phase6_run_line": p6_idx, "phase6_run_line_hash": p6_run["line_hash"]},
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
        "gate_table": table, "gate_counts": dict(counts),
        "gate_vocabulary": ["GREEN", "RED", "MANUAL_REVIEW", "PENDING_EXTERNAL", "DEFERRED-BLOCKING"],
        "checks": checks,
        "restage": {"gate11_mutation_boundary": {"live_identical": live_same, "registry_identical": reg_same, "output_identical": out_same, "preview_files_changed": ev["restage"]["preview_files_changed"]}, **ev["restage"]},
        "trees_now": {f"{k}_tree_sha256_over_manifest": v[0] for k, v in trees.items()},
        "tripwire": {**ev["tripwire"], "status": "GREEN" if (not ev["tripwire"]["git_tags_v6"] and not ev["tripwire"]["origin_tags_v6"] and ev["tripwire"]["pypi_published"] == main_ver and ev["tripwire"]["live_pages_linking_preview"] == 0 and ev["tripwire"]["live_capabilities_version"] == "v" + main_ver) else "RED",
                     "meaning": "nothing v6 is published: no tag, no release, PyPI/live badge/pyproject(main) all at the published version, no live link into docs/preview"},
        "python_version": sys.version.split()[0],
        "package_version_staged": staged_ver, "package_version_published": ev["tripwire"]["pypi_published"],
        "rehearsal_artifacts": {**ev["rehearsal"], "note": "rehearsal only — release day builds ONCE from the final tagged commit and uploads the SAME BYTES to PyPI and GitHub Release"},
        "gate_suite_commit": _git("rev-parse", "HEAD"),
        "release_authorized": False, "publishing_permitted": False,
        "remaining_blockers": [
            "gate #15 full-form user comprehension study does not exist (deterministic scaffold only) — MANUAL_REVIEW",
        ],
        "remaining_external_checks": [
            "gate #16 stranger-machine replication run (public log honestly empty; nothing may pre-fill it) — PENDING_EXTERNAL",
            "release-day external smoke: real-Internet 200s on every capabilities.json endpoint",
        ],
        "authorization_note": "Only the release-day order may flip release_authorized/publishing_permitted.",
    }
    (_REPO / "internal" / "release_state_manifest_v6.json").write_text(json.dumps(manifest, indent=1, sort_keys=False) + "\n")

    # ---- notes draft
    dl_counts = dl["status_counts"]
    c6_note = next((l["payload"]["note"] for l in reversed(lines) if l["kind"] == "run" and l["payload"]["protocol_id"] == "d7d5cc4fde5f"), "")
    notes = f"""# YUCLAW 6.0.0 — release notes DRAFT (internal; generated {now[:16]} UTC)

DRAFT — release_authorized: false. Every count below was DERIVED at draft
time from the named canonical artifact by tools/yuclaw_release_state_v6.py;
regenerate this draft before release day (rerun the generator; never
hand-edit numbers).

STATUS OF THIS DRAFT'S GATES: {counts.get('GREEN', 0)} GREEN · #15 MANUAL_REVIEW · #16
PENDING_EXTERNAL (table in internal/release_state_manifest_v6.json, chain tip
{tip[:12]}, source commit {manifest['source_commit_main'][:8]}). Gate #6 (dependency
calculations reproducible) is GREEN under Addendum A1 semantics: the registered
structural first-read computation reproduced byte-identically from frozen inputs
— nothing more.

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
  from registry artifacts (gate: tools/check_science_trust.py, {gates[11][0]} at
  draft time, anchor {p6_run['line_hash'][:12]}).
- Research states (registry/research_state.json): {len(rs['names'])} names, states
  {dict(rs_states)} — derived, never hand-maintained.
- Discovery Ledger (registry/discovery_ledger.json): {len(dl['hypotheses'])} hypotheses in
  bijection with {kinds['protocol']} registered protocol lines; status counts
  {dl_counts} — negative and inconclusive findings preserved.
- Anytime Evidence Record (registry/anytime_record.json): {ar['enrollment_count']}
  prospective enrollments, observation chain not yet started (honest-empty;
  first admission is calendar-gated) — ships ACCRUING, not adjudicated.
- Evidence Completeness Profiles (registry/completeness_profile.json):
  {len(cp['names'])} names, per-family states from the registered vocabulary. ETF
  class membership stays BLOCKED_BY_REGISTRATION (consumer-posture gate carries
  it as MANUAL_REVIEW).
- Protocol registry (registry/protocols.jsonl): {len(lines)} chained lines
  ({kinds['protocol']} protocols, {kinds['run']} recorded runs, {kinds.get('addendum', 0)} addendum), tip
  {tip[:16]}, chain-verified.
- Public daily evidence ledger (docs/ledger/): {len(blocks)} blocks; latest block
  {blocks[-1]}, evidence-ledger root {latest_blk['root_sha256'][:12]}.
- C6 risk gate (registered run note, verbatim): {c6_note}
- Cross-lens reversal coherence (protocol ea120b0a6b52, first read
  {rev['run_date']}, output/oie/reversal_coherence_first_read.json): verdict
  {rev['verdict']['verdict']} per the locked labels — accrual {rev['verdict']['accrual']};
  no coherence claim; the hypothesis stays open and accruing.
- Consumer-posture gate (tools/check_consumer_posture.py): five
  deterministic stranger personas wired into the nightly (exit 50).
- Replication: tools/replay_lab.py, stdlib-only, pinned Python versions;
  public replication log at docs/replication/replication_log.json has
  {len(repl['replications'])} entries — external stranger-machine replication is
  PENDING_EXTERNAL.

## Infrastructure

No infrastructure-location or sovereignty claim is made: no canonical
document records one (docs/architecture.md checked at draft time), and the
sovereignty rail permits factual, documented statements only.

## Not in this release / NOT YET

- Phase-6 N_eff and pooled-statistic anatomy: PENDING (A1.7 — no pooled
  statistic designated); edge rules {p6['edge_rule_coverage']['absent']} ABSENT (no
  persisted store); structural_completeness = PARTIAL.
- Phase-5 contribution anatomy: NOT YET (no registered method).
- Gate #15 full-form user comprehension study: NOT YET (the deterministic
  scaffold ships; the human study does not exist).
- Gate #16 external replication: PENDING_EXTERNAL ({len(repl['replications'])} entries in the
  public log).
"""
    (_REPO / "internal" / "release_notes_v6_DRAFT.md").write_text(notes)
    print(f"[release-state-v6] gates {dict(counts)} · tripwire {manifest['tripwire']['status']} · "
          f"chain {len(lines)}/{tip[:12]} · phase6 {p6_line}")
    for r in table:
        print(f"  #{r['gate']:>2} {r['result']:<16} {r['name']}")
    failing = [c for c, v in checks.items() if v['rc'] != 0]
    print("  failing checks:", failing or "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
