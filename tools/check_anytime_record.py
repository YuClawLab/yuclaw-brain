#!/usr/bin/env python3
"""
Anytime-record gate (Anytime Evidence Record v1, order of 2026-08-11 —
active immediately, chain exit 46). Three gates, all fail closed:

  ANYTIME-PROSPECTIVE    — any enrollment (chain line or on-disk record
      entry) whose start_time is earlier than its enrolled_at fails the
      chain: historical starts are never enrolled, nothing is
      retrofitted.
  ANYTIME-SCHEMA         — any enrollment missing a required field
      (registered null, parameters, start time, observation cadence,
      stopping/decision policy, dependency assumptions, invalidation
      conditions with mappings, maturity, evidence family) fails the
      chain.
  ANYTIME-RECONCILIATION — registry/anytime_record.json must equal the
      chain-derived rebuild byte-for-byte (derived, never
      hand-maintained).

Exit 0 = green; exit 1 = findings. Missing artifact, unregistered spec,
or unparseable chain = failure, not a skip.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools"))


def main() -> int:
    findings: list[str] = []

    from yuclaw_anytime_record import (RECORD_PATH, build_record,
                                       _check_enrollment_payload)
    if not RECORD_PATH.exists():
        print("[anytime-gate] ANYTIME-RECONCILIATION FAIL: "
              "registry/anytime_record.json missing — the gate fails "
              "closed", file=sys.stderr)
        return 1
    try:
        disk = json.loads(RECORD_PATH.read_text())
    except json.JSONDecodeError as exc:
        print(f"[anytime-gate] ANYTIME-RECONCILIATION FAIL: artifact "
              f"unparseable ({exc}) — the gate fails closed",
              file=sys.stderr)
        return 1
    try:
        derived = build_record()   # verifies chain + spec registration
    except Exception as exc:
        print(f"[anytime-gate] ANYTIME-RECONCILIATION FAIL: chain-derived "
              f"rebuild refused ({exc}) — the gate fails closed",
              file=sys.stderr)
        return 1

    # ---- per-enrollment REFUSALS, chain-derived and on-disk alike.
    for src, entries in (("chain", derived["enrollments"]),
                         ("record", disk.get("enrollments", []))):
        for e in entries:
            eid = e.get("enrollment_id", "<no id>")
            for p in _check_enrollment_payload(e):
                gate = ("ANYTIME-PROSPECTIVE"
                        if "historical starts are refused" in p
                        or "unparseable enrollment time" in p
                        else "ANYTIME-SCHEMA")
                findings.append(f"{gate} REFUSED [{src}] enrollment "
                                f"{eid}: {p}")

    # ---- derived-artifact discipline: byte-for-byte equality.
    canon = json.dumps(derived, indent=1, sort_keys=True) + "\n"
    if RECORD_PATH.read_text() != canon:
        findings.append(
            "ANYTIME-RECONCILIATION: registry/anytime_record.json differs "
            "from the chain-derived rebuild — the artifact is derived, "
            "never hand-maintained; regenerate with "
            "tools/yuclaw_anytime_record.py --write")

    if findings:
        print("[anytime-gate] FAIL:", file=sys.stderr)
        for f in dict.fromkeys(findings):    # stable order, no dups
            print(f"  · {f}", file=sys.stderr)
        return 1
    print(f"[anytime-gate] OK — {derived['enrollment_count']} enrollments "
          f"(honest-empty is green), every enrollment prospective and "
          f"schema-complete, artifact byte-identical to chain-derived "
          f"rebuild")
    return 0


if __name__ == "__main__":
    sys.exit(main())
