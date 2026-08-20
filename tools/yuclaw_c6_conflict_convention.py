#!/usr/bin/env python3
"""
C6 v2 Addendum A1 — Same-Day Conflicting-Flag Counting Convention.

Formal registration of the population counting convention that was
DECLARED (not registered) in the day-86 recorded note (chain line 76,
2026-08-13 third read) and applied at the day-87 fourth read (chain
line 77). This addendum registers the convention going forward; it does
not supersede d7d5cc4fde5f (C6 v2 stays LOCKED — lineage preserved) and
it never relabels the historical notes.

Pattern mirrors tools/yuclaw_c6_risk_gate_v2.py: METHOD_SPEC text is the
registered object; method_hash = sha256(spec)[:16]; protocol_id =
sha256(spec + params-json)[:12]; registration appends one kind=protocol
line to the canonical chain via Registry.register().
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

METHOD_SPEC_A1 = """
TITLE: C6 v2 Addendum A1 — Same-Day Conflicting-Flag Counting
Convention (supersedes silence in d7d5cc4fde5f; lineage preserved).

CANONICAL RULE: population unit is issuer-day pairs; a pair whose
same-day filings carry conflicting elevated/normal flags is assigned
to the ELEVATED arm (the convention declared in the day-86 recorded
note, now formalized).

MANDATORY ROBUSTNESS: every future read MUST also print counts and,
where computable, effect estimates under (a) artifact-level counting
and (b) conflict-excluded counting. A read whose ELIGIBILITY differs
across the three rules must say so in its recorded note.

EFFECTIVITY: applies to all reads after this registration; no
retroactive relabeling of the day-86/day-87 notes (their
declared-not-registered status is historical fact and stays).

INVALIDATION: any change to this convention requires a further
registered addendum.
"""

METHOD_HASH_A1 = hashlib.sha256(METHOD_SPEC_A1.encode()).hexdigest()[:16]
PARAMS_A1 = {"parent_protocol": "d7d5cc4fde5f"}


def _selftest():
    """Hashes recompute deterministically from the committed text, and the
    spec carries every clause the order requires."""
    assert METHOD_HASH_A1 == hashlib.sha256(
        METHOD_SPEC_A1.encode()).hexdigest()[:16]
    for clause in ("CANONICAL RULE", "MANDATORY ROBUSTNESS",
                   "EFFECTIVITY", "INVALIDATION",
                   "issuer-day pairs", "ELEVATED arm",
                   "artifact-level counting", "conflict-excluded counting",
                   "no\nretroactive relabeling"):
        assert clause in METHOD_SPEC_A1, f"spec missing clause: {clause}"
    from yuclaw_protocol_registry import protocol_id
    pid = protocol_id(METHOD_SPEC_A1, PARAMS_A1)
    assert len(pid) == 12
    print(f"[OK] A1 selftest: spec clauses present; "
          f"protocol_id={pid} method_hash={METHOD_HASH_A1}")
    return pid


def register_a1(lock_date: str):
    """Invoked ONCE (order 2026-08-20B Part 1). Appends the addendum as a
    new kind=protocol line; d7d5cc4fde5f is NOT superseded and stays
    LOCKED — future C6 reads keep running under it with this convention
    in force."""
    from yuclaw_protocol_registry import Protocol, Registry, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(METHOD_SPEC_A1, PARAMS_A1)
    if reg.get_protocol(pid):
        raise RuntimeError(f"A1 already registered as {pid}")
    reg.register(Protocol(
        protocol_id=pid,
        name=("C6 v2 Addendum A1 — Same-Day Conflicting-Flag Counting "
              "Convention"),
        method_hash=METHOD_HASH_A1,
        spec_summary=("Formalizes the population counting convention for "
                      "C6 v2 (d7d5cc4fde5f) reads: unit is issuer-day "
                      "pairs; a same-day conflicting-flag pair is assigned "
                      "to the ELEVATED arm (the day-86 declared convention, "
                      "now registered). Every future read must also print "
                      "artifact-level and conflict-excluded variants, and "
                      "disclose when eligibility differs across the three "
                      "rules. No retroactive relabeling of the day-86/"
                      "day-87 notes; changing this convention requires a "
                      "further registered addendum. Addendum entry; parent "
                      "protocol stays LOCKED."),
        primary_endpoint=("counting-convention addendum entry; no "
                          "statistical endpoint of its own — reads stay "
                          "under d7d5cc4fde5f"),
        secondary_endpoints=[],
        lock_date=lock_date,
        version=1))
    reg.verify_chain()
    tip = reg._tip()
    print(f"[A1] REGISTERED {pid} method_hash={METHOD_HASH_A1} "
          f"lines={len(reg._lines)} tip={tip}")
    return pid


if __name__ == "__main__":
    pid = _selftest()
    if "--register" in sys.argv:
        i = sys.argv.index("--register")
        register_a1(sys.argv[i + 1])
    else:
        print(f"[A1-draft] protocol_id={pid} method_hash={METHOD_HASH_A1} "
              "— not registered (pass --register <lock_date>)")
