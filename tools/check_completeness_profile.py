#!/usr/bin/env python3
"""
Completeness-profile gate (Evidence Completeness Profile v1, order of
2026-08-11 — active immediately, chain exit 47). Derived-only lineage:
the registered deterministic derivation (apply_rules) is re-applied to
every printed (family, expectedness, count, gap_days) in the artifact;
ANY state that diverges is a hand-maintained override without derivation
provenance and fails the chain — regardless of which state value was
planted. A legitimately derived UNKNOWN is valid (C-3). Also enforced:
state vocabulary, expected-set-per-class table, and the
material_missing definition. Fails closed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO / "tools") not in sys.path:
    sys.path.insert(0, str(_REPO / "tools"))


def main() -> int:
    from yuclaw_completeness_profile import (PROFILE_PATH, FAMILIES,
                                             COMPLETENESS_STATES,
                                             apply_rules)
    findings: list[str] = []
    if not PROFILE_PATH.exists():
        print("[completeness-gate] FAIL: registry/completeness_profile"
              ".json missing — fails closed", file=sys.stderr)
        return 1
    try:
        prof = json.loads(PROFILE_PATH.read_text())
    except json.JSONDecodeError as exc:
        print(f"[completeness-gate] FAIL: artifact unparseable ({exc})",
              file=sys.stderr)
        return 1

    EXPECTED = {
        "us_scoring": {"sec_primary", "insider_form4", "pricing",
                        "corporate_actions"},
        "canada_evidence": {"sec_primary", "insider_form4", "pricing",
                             "corporate_actions"},
        "foreign_issuer": {"foreign_filings", "canada_sedi", "pricing",
                            "corporate_actions"},
        "etf": {"pricing"},
    }
    n_checked = 0
    for name, body in sorted(prof.get("names", {}).items()):
        cls = body.get("class")
        if cls not in EXPECTED:
            findings.append(f"{name}: unknown class {cls!r}")
            continue
        if set(body.get("expected_accessible_families", [])) != \
                EXPECTED[cls]:
            findings.append(f"{name}: expected_accessible_families "
                            f"diverge from the registered class table")
        derived_missing = []
        for fam in FAMILIES:
            cell = body.get("per_family", {}).get(fam)
            if cell is None:
                findings.append(f"{name}: family {fam} missing")
                continue
            st = cell.get("state")
            if st not in COMPLETENESS_STATES:
                findings.append(f"{name}/{fam}: state {st!r} outside "
                                f"the registered vocabulary")
                continue
            want = apply_rules(fam, fam in EXPECTED[cls],
                               cell.get("count", 0),
                               cell.get("gap_days"))
            n_checked += 1
            if st != want:
                findings.append(
                    f"COMPLETENESS-LINEAGE: {name}/{fam} state {st!r} "
                    f"!= registered derivation {want!r} for printed "
                    f"count={cell.get('count')} — hand-maintained "
                    f"override without derivation provenance; the "
                    f"artifact is derived-only (a legitimately derived "
                    f"UNKNOWN remains valid)")
            if fam in EXPECTED[cls] and want in ("ABSENT", "UNKNOWN"):
                derived_missing.append(fam)
        if sorted(body.get("material_missing_families", [])) != \
                sorted(derived_missing):
            findings.append(f"{name}: material_missing_families "
                            f"{body.get('material_missing_families')} != "
                            f"derived {derived_missing}")

    if findings:
        print("[completeness-gate] FAIL:", file=sys.stderr)
        for f in findings[:12]:
            print(f"  · {f}", file=sys.stderr)
        return 1
    print(f"[completeness-gate] OK — {len(prof.get('names', {}))} names, "
          f"{n_checked} states re-derived from printed inputs, zero "
          f"lineage violations; UNKNOWN legal where derived")
    return 0


if __name__ == "__main__":
    sys.exit(main())
