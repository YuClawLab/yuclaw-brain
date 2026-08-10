#!/usr/bin/env python3
"""
Research-state gate (Research-State Derivation v1, order of 2026-08-11 —
active immediately, chain exit 48). The artifact derives from files only
(chain + four registry artifacts), so the gate rebuilds it and requires
byte-for-byte equality — never hand-maintained; plus: every research
state must sit in the six-state vocabulary and carry a registered basis
or a P4 empty basis. Fails closed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools"))


def main() -> int:
    from yuclaw_research_state import (STATE_PATH, RESEARCH_STATES,
                                       build_states)
    findings: list[str] = []
    if not STATE_PATH.exists():
        print("[research-state-gate] FAIL: registry/research_state.json "
              "missing — fails closed", file=sys.stderr)
        return 1
    try:
        disk = json.loads(STATE_PATH.read_text())
    except json.JSONDecodeError as exc:
        print(f"[research-state-gate] FAIL: artifact unparseable "
              f"({exc})", file=sys.stderr)
        return 1
    try:
        derived = build_states()
    except Exception as exc:
        print(f"[research-state-gate] FAIL: rebuild refused ({exc}) — "
              f"fails closed", file=sys.stderr)
        return 1

    for name, body in sorted(disk.get("names", {}).items()):
        st = body.get("research_state")
        if st not in RESEARCH_STATES | {"NOT_APPLICABLE"}:
            findings.append(f"{name}: research_state {st!r} outside the "
                            f"registered vocabulary")
        if st not in ("INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE") and \
                not body.get("basis_protocols"):
            findings.append(
                f"RESEARCH-STATE-LINEAGE: {name} carries research_state "
                f"{st!r} with NO registered protocol basis — forced "
                f"states without a registered read are refused (P4)")

    if not findings:
        if json.dumps(disk, sort_keys=True) != \
                json.dumps(derived, sort_keys=True):
            findings.append(
                "registry/research_state.json differs from the "
                "deterministic rebuild — the artifact is derived-only; "
                "regenerate with tools/yuclaw_research_state.py --write")

    if findings:
        print("[research-state-gate] FAIL:", file=sys.stderr)
        for f in findings[:12]:
            print(f"  · {f}", file=sys.stderr)
        return 1
    print(f"[research-state-gate] OK — {len(disk.get('names', {}))} "
          f"names render registered artifacts only; byte-identical "
          f"rebuild; platform C6 verdict verbatim")
    return 0


if __name__ == "__main__":
    sys.exit(main())
