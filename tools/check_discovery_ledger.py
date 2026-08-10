#!/usr/bin/env python3
"""
Discovery-ledger gate (Discovery Ledger v1, order of 2026-08-10 — active
immediately, chain exit 45). Two gates, both fail closed:

  LEDGER-RECONCILIATION — every kind=protocol chain line maps to exactly
      one hypothesis identity and every hypothesis identity maps to
      exactly one such line; any orphan in either direction fails the
      chain. The on-disk artifact must equal the chain-derived rebuild
      byte-for-byte (registry/discovery_ledger.json is DERIVED — never
      hand-maintained; hand-maintenance is structurally impossible).

  FAMILY-LOCK — any difference between on-disk family membership
      (evidence_family / parent_family / families.members) and the
      chain-derived membership without a supersession line covering it
      fails the chain.

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

    from yuclaw_discovery_ledger import LEDGER_PATH, build_ledger
    if not LEDGER_PATH.exists():
        print("[discovery-gate] LEDGER-RECONCILIATION FAIL: "
              "registry/discovery_ledger.json missing — the gate fails "
              "closed", file=sys.stderr)
        return 1
    try:
        disk = json.loads(LEDGER_PATH.read_text())
    except json.JSONDecodeError as exc:
        print(f"[discovery-gate] LEDGER-RECONCILIATION FAIL: artifact "
              f"unparseable ({exc}) — the gate fails closed",
              file=sys.stderr)
        return 1
    try:
        derived = build_ledger()   # verifies chain + spec registration
    except Exception as exc:
        print(f"[discovery-gate] LEDGER-RECONCILIATION FAIL: chain-derived "
              f"rebuild refused ({exc}) — the gate fails closed",
              file=sys.stderr)
        return 1

    # ---- LEDGER-RECONCILIATION: bijection, both directions.
    want = {(h["hypothesis_id"], h["protocol_id"], h["chain_line"])
            for h in derived["hypotheses"]}
    have = {(h.get("hypothesis_id"), h.get("protocol_id"),
             h.get("chain_line")) for h in disk.get("hypotheses", [])}
    for hid, pid, line in sorted(want - have):
        findings.append(
            f"LEDGER-RECONCILIATION: chain protocol line {line} "
            f"({pid}) has no hypothesis identity on disk — orphan "
            f"chain line (expected {hid})")
    for hid, pid, line in sorted(have - want):
        findings.append(
            f"LEDGER-RECONCILIATION: hypothesis {hid} ({pid}, "
            f"chain_line {line}) has no matching kind=protocol chain "
            f"line — orphan hypothesis identity")
    ids = [h.get("hypothesis_id") for h in disk.get("hypotheses", [])]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        findings.append(f"LEDGER-RECONCILIATION: hypothesis_id {dup} "
                        f"appears more than once — identities are "
                        f"permanent and unique")

    # ---- FAMILY-LOCK: membership immutable except by supersession, and
    # the chain-derived rebuild already reflects every supersession line;
    # any on-disk divergence is therefore an unsupported membership edit.
    d_by_id = {h["hypothesis_id"]: h for h in derived["hypotheses"]}
    for h in disk.get("hypotheses", []):
        ref = d_by_id.get(h.get("hypothesis_id"))
        if ref is None:
            continue   # already reported as reconciliation orphan
        for field in ("evidence_family", "parent_family"):
            if h.get(field) != ref[field]:
                findings.append(
                    f"FAMILY-LOCK: {h['hypothesis_id']} {field} "
                    f"{h.get(field)!r} != registered membership "
                    f"{ref[field]!r} — family membership is immutable "
                    f"except by a supersession line with lineage")
    d_fams = {k: sorted(v["members"]) for k, v in derived["families"].items()}
    x_fams = {k: sorted(v.get("members", []))
              for k, v in disk.get("families", {}).items()}
    for fam in sorted(set(d_fams) | set(x_fams)):
        if d_fams.get(fam) != x_fams.get(fam):
            findings.append(
                f"FAMILY-LOCK: family {fam!r} members {x_fams.get(fam)} "
                f"!= registered membership {d_fams.get(fam)} — no "
                f"supersession line covers this change")

    # ---- Derived-artifact discipline: byte-for-byte equality.
    if not findings:
        canon = json.dumps(derived, indent=1, sort_keys=True) + "\n"
        if LEDGER_PATH.read_text() != canon:
            findings.append(
                "LEDGER-RECONCILIATION: registry/discovery_ledger.json "
                "differs from the chain-derived rebuild — the artifact "
                "is derived, never hand-maintained; regenerate with "
                "tools/yuclaw_discovery_ledger.py --write")

    if findings:
        print("[discovery-gate] FAIL:", file=sys.stderr)
        for f in findings:
            print(f"  · {f}", file=sys.stderr)
        return 1
    n_h = len(derived["hypotheses"])
    n_f = len(derived["families"])
    print(f"[discovery-gate] OK — {n_h} hypotheses <-> {n_h} protocol "
          f"lines (bijection both directions), {n_f} families locked, "
          f"artifact byte-identical to chain-derived rebuild; "
          f"status_counts={derived['status_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
