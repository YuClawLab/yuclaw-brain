#!/usr/bin/env python3
"""
C6 Risk Gate Lab v2 — DRAFT FOR OWNER REVIEW (Part C, Option B).
NOT REGISTERED. NOTHING COMPUTES. The owner decides A (strict exclusion,
this file stays a dead draft) or B (supersession; register_v2() is then
invoked once, BEFORE any backlog computation).

The as-of verifier below is real, self-tested code — prepared so Option B,
if chosen, is mechanical rather than aspirational.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

METHOD_SPEC_V2 = """
C6 RISK GATE LAB — pre-committed specification (v2 DRAFT; supersedes
0df6fc002d79 if and only if the owner selects Option B)

INHERITANCE
Every clause of v1 (question, population definition, primary endpoint,
secondary endpoints S1-S3, analysis plan, minimum arm size, badge rules,
thin-arm clause, reporting rules) is inherited VERBATIM except the single
arm-assignment amendment below. v1's 2026-07-30 first read (INCONCLUSIVE,
empty arms) stands as recorded and is never re-characterized.

ARM-ASSIGNMENT AMENDMENT (the only change)
v1 required the risk-channel flag to be "recorded point-in-time ... never
recomputed retroactively." v2 permits LATE COMPUTATION for exactly the
process-failure window 2026-07-16 through 2026-07-30 (the live-accrual gap
created because no live artifact path existed — an operational failure,
not a market fact), under all of the following, mechanically enforced:

  (1) STRICTLY AS-OF INPUTS. Each late artifact is computed ONLY from:
      (a) the filing's own narrative text as persisted in
          yuclaw_v5.swarm_inputs (content of the filing itself — content
          date = filing date), and
      (b) event-type rows for the SAME accession (content date = filing
          date). No price data, no cross-filing context, no input whose
          CONTENT date postdates the filing day may enter. The specialized
          runner takes (accession, narrative_text) and nothing else; the
          verifier asserts the manifest matches this closure.
  (2) INPUT MANIFEST. Every late artifact must embed:
      late_computed=true, computed_at (UTC), filing_date,
      input_manifest = {narrative_sha256, narrative_source,
      accession_scoped_inputs: [...], max_input_content_date}.
  (3) MECHANICAL VERIFICATION. yuclaw_c6_risk_gate_v2.verify_as_of() must
      pass for every late artifact BEFORE it may enter the analysis
      population: max_input_content_date <= filing_date; the narrative
      sha256 matches the persisted swarm_inputs row byte-for-byte; every
      listed input is accession-scoped. Any failure excludes the artifact
      permanently (no repair, no retry with different inputs).
  (4) LAG DISCLOSURE. computation lag (computed_at - filing_date, days) is
      disclosed per artifact and summarized (min/median/max) in every
      report that uses late artifacts.
  (5) SEGREGATED LABELING. Late artifacts carry late_computed=true forever;
      any analysis using them reports the late/live split (n_late vs
      n_live) beside every statistic.
  (6) WINDOW CLOSURE. The late-computation permission applies to filings
      dated 2026-07-16..2026-07-30 ONLY. Filings from 2026-07-31 onward are
      point-in-time via the live runner (services/c6_specialized_live.py);
      any future gap requires its own supersession — this clause does not
      generalize.

COMPUTE DISCIPLINE
v2 is registered BEFORE any backlog computation; registration supersedes
0df6fc002d79 via the registry's supersession path (v1 refuses further runs
once superseded; its recorded first read remains in the chain). Any edit to
this spec changes its hash and requires a further supersession — never
amendment.
"""

METHOD_HASH_V2 = hashlib.sha256(METHOD_SPEC_V2.encode()).hexdigest()[:16]
PARAMS_V2 = {"k_primary": 10, "late_window": ["2026-07-16", "2026-07-30"]}
GAP_LO, GAP_HI = date(2026, 7, 16), date(2026, 7, 30)


def verify_as_of(artifact: dict, narrative_text: str,
                 filing_date: date) -> list[str]:
    """Mechanical as-of check for a late artifact. Returns [] when the
    artifact satisfies the v2 closure; otherwise a list of violations."""
    problems = []
    if artifact.get("late_computed") is not True:
        problems.append("late_computed flag missing/false")
    man = artifact.get("input_manifest") or {}
    for key in ("narrative_sha256", "narrative_source",
                "accession_scoped_inputs", "max_input_content_date"):
        if key not in man:
            problems.append(f"input_manifest.{key} missing")
    if problems:
        return problems
    want = hashlib.sha256(narrative_text.encode()).hexdigest()
    if man["narrative_sha256"] != want:
        problems.append("narrative sha256 does not match the persisted "
                        "swarm_inputs row")
    try:
        mx = date.fromisoformat(man["max_input_content_date"])
        if mx > filing_date:
            problems.append(f"input content date {mx} postdates filing "
                            f"date {filing_date}")
    except ValueError:
        problems.append("max_input_content_date unparseable")
    acc = artifact.get("accession_number", "")
    for item in man["accession_scoped_inputs"]:
        if acc and acc not in str(item):
            problems.append(f"non-accession-scoped input listed: {item}")
    if not (GAP_LO <= filing_date <= GAP_HI):
        problems.append(f"filing date {filing_date} outside the late "
                        f"window {GAP_LO}..{GAP_HI}")
    return problems


def _selftest():
    text = "sample filing narrative"
    sha = hashlib.sha256(text.encode()).hexdigest()
    good = {"late_computed": True, "accession_number": "0001-26-X",
            "input_manifest": {"narrative_sha256": sha,
                               "narrative_source": "yuclaw_v5.swarm_inputs",
                               "accession_scoped_inputs":
                                   ["events:0001-26-X"],
                               "max_input_content_date": "2026-07-20"}}
    assert verify_as_of(good, text, date(2026, 7, 20)) == []
    # future-dated input refused
    bad1 = json.loads(json.dumps(good))
    bad1["input_manifest"]["max_input_content_date"] = "2026-07-25"
    assert any("postdates" in p for p in
               verify_as_of(bad1, text, date(2026, 7, 20)))
    # tampered narrative refused
    assert any("sha256" in p for p in
               verify_as_of(good, text + "x", date(2026, 7, 20)))
    # out-of-window filing refused
    assert any("outside the late window" in p for p in
               verify_as_of(good, text, date(2026, 8, 2)))
    # non-scoped input refused
    bad2 = json.loads(json.dumps(good))
    bad2["input_manifest"]["accession_scoped_inputs"] = ["prices:SPY"]
    assert any("non-accession-scoped" in p for p in
               verify_as_of(bad2, text, date(2026, 7, 20)))
    print("[OK] verifier selftest: clean pass + 4 refusals "
          "(future-dated, tampered narrative, out-of-window, non-scoped)")


def register_v2():
    """Invoked ONCE, only after the owner selects Option B, BEFORE any
    backlog computation. Refuses without the explicit owner flag."""
    import os
    if os.environ.get("YUCLAW_OWNER_DECISION") != "B":
        raise RuntimeError(
            "register_v2 refused: Part C is an owner decision point. Set "
            "YUCLAW_OWNER_DECISION=B only when the owner has selected "
            "Option B (supersession).")
    from datetime import datetime, timezone
    from yuclaw_protocol_registry import Protocol, Registry, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC_V2, PARAMS_V2)
    reg.supersede("0df6fc002d79", Protocol(
        protocol_id=pid, name="C6 Risk Gate Lab v2", method_hash=METHOD_HASH_V2,
        spec_summary=("v1 inherited verbatim; single amendment permits late "
                      "computation for the 2026-07-16..30 process-failure "
                      "gap from strictly as-of, accession-scoped inputs, "
                      "with per-artifact lag disclosure and a mechanical "
                      "verifier gating population entry."),
        primary_endpoint=("forward realized volatility ratio "
                          "elevated/normal at k=10 (inherited from v1)"),
        secondary_endpoints=["S1 max drawdown diffs (inherited)",
                             "S2 tail-event frequency diff (inherited)",
                             "S3 sign endpoint reference (inherited)",
                             "late/live split disclosure cells"],
        lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"), version=2))
    reg.verify_chain()
    print(f"[v2] REGISTERED {pid} (supersedes 0df6fc002d79); backlog "
          "computation may now proceed under the locked text")
    return pid


if __name__ == "__main__":
    _selftest()
    print(f"[v2-draft] METHOD_HASH={METHOD_HASH_V2} — DRAFT, NOT REGISTERED; "
          "owner decision pending (A: strict exclusion / B: supersession)")
