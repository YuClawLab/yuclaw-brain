#!/usr/bin/env python3
"""
RESEARCH-STATE DERIVATION v1 — Science Trust addendum (registered method
spec). Adjudication UNCOMPUTED · derivation machinery ACTIVE (order of
2026-08-11, executed 2026-08-10 UTC). Fourth registered addendum under
SCIENCE TRUST PROTOCOL v1 (be8b34040c2e). This component computes NO new
statistics: it RENDERS registered ones into the trust-card fields under
the in-hash precedence table. Derived artifact
registry/research_state.json — never hand-maintained; chain gate exit 48
rebuilds it byte-for-byte from registered artifacts only.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
STATE_PATH = _REPO / "registry" / "research_state.json"
UMBRELLA_PROTOCOL_ID = "be8b34040c2e"

RESEARCH_STATES = {"SUPPORTED", "WEAK", "INCONCLUSIVE", "CONFLICTED",
                   "INSUFFICIENT_EVIDENCE", "NOT_IDENTIFIABLE"}

METHOD_SPEC = """
RESEARCH-STATE DERIVATION v1 (Science Trust addendum, locked 2026-08-10)

STATUS
Adjudication UNCOMPUTED. Derivation machinery ACTIVE (ledger pattern).
Registered as an addendum under SCIENCE TRUST PROTOCOL v1 (protocol
be8b34040c2e). This is a RENDERER: nothing here computes a new
statistic; every field is a deterministic mapping from artifacts that
are already registered in the canonical chain or derived by registered
addenda.

TRUST-CARD FIELD SOURCES (fixed mapping)
  research state        <- registered read verdicts, VERBATIM (a chain
                           run note matching "Verdict: X" — the C6 OOS
                           INCONCLUSIVE stays INCONCLUSIVE, annotation
                           carried in full, never re-adjudicated)
  multiplicity          <- Discovery Ledger v1 family adjudication
                           (PENDING until a family's registered read)
  sequential evidence   <- Anytime Evidence Record v1 enrollment state
  truncation impact     <- Truncation & Error Budget ledger (site count,
                           interpretation-change flags, verbatim)
  coverage              <- Evidence Completeness Profile v1 (observed /
                           expected / material-missing, verbatim)

PRECEDENCE / CONFLICT RULE (complete, in-hash; "first match" selects
the registered derivation rule, never an arbitrary winner between
contradictory conclusions)
  P1. An exact-name registered read outranks lens-context inheritance.
  P2. Only the latest valid non-superseded methodology participates:
      a read recorded under a protocol that has since been superseded
      does not compete (its verdict remains visible in lineage, never
      in adjudication).
  P3. Within the winning precedence tier, contemporaneously valid,
      materially contradictory registered conclusions derive
      CONFLICTED — never a silent pick.
  P4. If no qualifying read exists for the name or its lens context:
      INSUFFICIENT_EVIDENCE when the name is inside the registered
      coverage scope; NOT_APPLICABLE when it is outside registered
      scope. Never forced, never interpolated.
  P5. Signal labels never enter research-state adjudication, in either
      direction (S6 vocabulary separation, absolute).

SCOPE TABLE (fixed at this version; extended only by supersession)
A protocol's registered scope is its declared target: lens-scoped CAR /
falsification / geometry protocols target their lens (SMH, XLK, ...);
component protocols (C6 risk gate) target the platform component, not
names; governance/registry protocols target the platform. A name's lens
context is its ETF-lens membership as committed in the platform
membership artifacts. Exact-name protocols (none registered at v1 lock)
would target their named ticker.

DERIVATION PER NAME (deterministic, first match wins)
  1. collect qualifying reads: chain run lines with a "Verdict:" marker
     whose protocol is not superseded (P2), mapped through the scope
     table to this name (exact-name first, then lens context; P1).
  2. multiple qualifying reads in the winning tier with materially
     different verdicts -> CONFLICTED (P3).
  3. exactly one winning verdict -> that verdict VERBATIM.
  4. none -> INSUFFICIENT_EVIDENCE (in coverage scope) or
     NOT_APPLICABLE (outside; P4).
Platform-component verdicts (C6) render in the platform block only —
they never map to names.

REFUSAL RULE (active, negative-tested)
The derivation REFUSES any read whose protocol_id is not a registered
chain protocol, and refuses to derive a research state for any name
with no qualifying registered read basis — a forced state without a
registered protocol is a lineage violation, not a derivable value.

DERIVED ARTIFACT
registry/research_state.json — derived deterministically from: the
canonical chain, registry/discovery_ledger.json,
registry/anytime_record.json, registry/truncation_ledger.json, and
registry/completeness_profile.json (files only — no live store), so the
same inputs always yield byte-identical output; NEVER hand-maintained;
chain gate exit 48 rebuilds and compares byte-for-byte. S6 walks the
artifact; the canonical research-state field carries only the six
research states.

COMPUTE DISCIPLINE
Zero new statistics, zero re-adjudication, zero signal/score/label
changes, zero public page changes, zero version bump. Any edit to this
spec changes its hash and therefore requires supersession — never
amendment.
"""

PARAMS = {"precedence_rules": 5, "field_sources": 5, "states": 6}
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_ID = hashlib.sha256(
    (METHOD_SPEC + json.dumps(PARAMS, sort_keys=True)).encode()).hexdigest()[:12]

_RE_VERDICT = re.compile(r"Verdict: ([A-Z_]+)")


def _registry():
    import sys
    if str(_REPO / "tools") not in sys.path:
        sys.path.insert(0, str(_REPO / "tools"))
    from yuclaw_protocol_registry import Registry
    return Registry(str(_REPO / "registry" / "protocols.jsonl"))


def qualifying_reads(reg) -> list[dict]:
    """Chain run lines with Verdict markers under non-superseded
    protocols (P2), tagged with their registered scope."""
    superseded = {l["payload"]["protocol_id"] for l in reg._lines
                  if l["kind"] == "supersede_notice"}
    out = []
    for l in reg._lines:
        if l["kind"] != "run":
            continue
        m = _RE_VERDICT.search(l["payload"].get("note", ""))
        if not m:
            continue
        pid = l["payload"]["protocol_id"]
        out.append({"protocol_id": pid, "verdict": m.group(1),
                    "annotation": l["payload"]["note"],
                    "superseded": pid in superseded,
                    "scope": "platform:c6"})   # scope table v1: the only
        # verdict-bearing protocols are the C6 component reads.
    return out


def derive_name_state(name: str, reads: list[dict], reg,
                      in_coverage: bool) -> dict:
    """P1-P5 for one name. REFUSES unregistered or forced reads."""
    for r in reads:
        if not reg.get_protocol(r["protocol_id"]):
            raise ValueError(
                f"RESEARCH-STATE REFUSED: read for {name} cites "
                f"protocol {r['protocol_id']} which is not registered "
                f"in the canonical chain — a forced research state "
                f"without a registered protocol is a lineage "
                f"violation, not a derivable value")
        if r.get("verdict") not in RESEARCH_STATES:
            raise ValueError(
                f"RESEARCH-STATE REFUSED: read for {name} carries "
                f"non-research-state verdict {r.get('verdict')!r} "
                f"(P5: signal labels never enter adjudication)")
    live = [r for r in reads if not r["superseded"]]          # P2
    exact = [r for r in live if r["scope"] == f"name:{name}"]  # P1
    tier = exact or [r for r in live
                     if r["scope"].startswith("lens:")
                     and name in r.get("lens_members", ())]
    if tier:
        verdicts = {r["verdict"] for r in tier}
        if len(verdicts) > 1:                                  # P3
            return {"research_state": "CONFLICTED",
                    "basis": sorted(r["protocol_id"] for r in tier)}
        return {"research_state": tier[0]["verdict"],
                "basis": [tier[0]["protocol_id"]],
                "annotation": tier[0]["annotation"]}
    return {"research_state": ("INSUFFICIENT_EVIDENCE" if in_coverage
                               else "NOT_APPLICABLE"),
            "basis": []}                                       # P4


def build_states() -> dict:
    reg = _registry()
    reg.assert_registered(PROTOCOL_ID)
    completeness = json.loads(
        (_REPO / "registry" / "completeness_profile.json").read_text())
    discovery = json.loads(
        (_REPO / "registry" / "discovery_ledger.json").read_text())
    anytime = json.loads(
        (_REPO / "registry" / "anytime_record.json").read_text())
    trunc = json.loads(
        (_REPO / "registry" / "truncation_ledger.json").read_text())
    reads = qualifying_reads(reg)

    platform_reads = [r for r in reads if r["scope"] == "platform:c6"
                      and not r["superseded"]]
    names = {}
    for name, cov in completeness["names"].items():
        d = derive_name_state(name, reads, reg, in_coverage=True)
        names[name] = {
            "research_state": d["research_state"],
            "basis_protocols": d["basis"],
            "coverage": {
                "observed_families": cov["observed_families"],
                "material_missing_families":
                    cov["material_missing_families"]},
            "multiplicity": "PENDING (Discovery Ledger family "
                            "adjudication awaits registered read)",
            "sequential_evidence": "NOT_APPLICABLE at name level "
                                   "(enrolled instruments are "
                                   "label-tier)",
        }

    return {
        "spec": {"name": "Research-State Derivation v1",
                 "protocol_id": PROTOCOL_ID, "method_hash": METHOD_HASH,
                 "umbrella_protocol_id": UMBRELLA_PROTOCOL_ID,
                 "adjudication_state": "UNCOMPUTED",
                 "derivation_machinery": "ACTIVE",
                 "derivation_anchor_chain_tip": reg._tip(),
                 "inputs": ["protocols.jsonl", "discovery_ledger.json",
                            "anytime_record.json",
                            "truncation_ledger.json",
                            "completeness_profile.json"]},
        "platform": {
            "c6_component": ([{"research_state": r["verdict"],
                               "protocol_id": r["protocol_id"],
                               "annotation": r["annotation"]}
                              for r in platform_reads] or
                             [{"research_state": "INSUFFICIENT_EVIDENCE",
                               "basis": []}]),
            "multiplicity": {
                "families": len(discovery["families"]),
                "adjudication": "PENDING for every family (Discovery "
                                "Ledger v1)"},
            "sequential_evidence": {
                "enrollments": [
                    {"enrollment_id": e["enrollment_id"],
                     "instrument": e["instrument"]}
                    for e in anytime["enrollments"]],
                "note": "state per registered anytime state machine; "
                        "no eligible observation admitted yet -> "
                        "REGISTERED/OPEN"},
            "truncation_impact": {
                "sites": len(trunc["entries"]),
                "interpretation_change_yes":
                    sum(1 for e in trunc["entries"]
                        if e["interpretation_change"] == "yes"),
                "interpretation_change_unknown":
                    sum(1 for e in trunc["entries"]
                        if e["interpretation_change"] == "unknown")},
        },
        "names": names,
    }


def write_states() -> dict:
    st = build_states()
    STATE_PATH.write_text(json.dumps(st, indent=1, sort_keys=True) + "\n")
    return st


if __name__ == "__main__":
    import sys
    if "--write" in sys.argv:
        st = write_states()
        from collections import Counter
        c = Counter(v["research_state"] for v in st["names"].values())
        print(f"[research-state] wrote {STATE_PATH} — "
              f"{len(st['names'])} names, states={dict(c)}")
    else:
        print(f"[research-state] METHOD_HASH={METHOD_HASH} · "
              f"PROTOCOL_ID={PROTOCOL_ID} · params={PARAMS} · "
              f"adjudication UNCOMPUTED · derivation ACTIVE (renders "
              f"registered artifacts only)")
