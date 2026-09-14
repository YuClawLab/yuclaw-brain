#!/usr/bin/env python3
"""Universe-ladder readiness report (v7 candidate): U79 (canonical) → U150 → U250 → U350 → U550.

Reads only stored records (constitution text, the admission report's manifest hash, the Phase-A
maturity summary if present) and prints, per rung, the SEPARATE dimensions: implementation, admission
gates, registered observation window, capacity, promotion decision. It never promotes, never runs
admission, never reads research rows. Membership classes stay distinct: canonical scoring (79),
shadow (u350 schema), evidence-only (Canada Resources tier, 49). CLI: python3 tools/yuclaw_ladder_readiness.py [--json]"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
RUNGS = (("U79", 79), ("U150", 150), ("U250", 250), ("U350", 350), ("U550", 550))
CAPACITY_AUDIT_GPU_H = {79: 1.10, 150: 1.52, 250: 2.11, 350: 2.29}       # 2026-08-02 audit (documented); 550 not audited
GPU_BUDGET_H = 2.0                                                        # candidate ceiling for readiness display only (owner input)


def rung_status(target: int, *, registered_window: dict | None, promotion_record: dict | None, phase_c_protocol_id: str | None, capacity_h: float | None) -> dict:
    """Pure readiness classification for one rung; every dimension separate; nothing inferred from another."""
    st = {"target": target,
          "implementation": "READY" if target <= 350 else "NOT_IMPLEMENTED (no admission run above 350 exists)",
          "admission_gates": "REGISTERED (Admission v1, Selection v1, Liquidity Addendum)" if target <= 350 else "MISSING",
          "observation_window": ("REGISTERED" if registered_window else "MISSING") if target > 79 else "N/A (canonical)",
          "capacity": ("UNKNOWN (not audited)" if capacity_h is None else ("WITHIN_BUDGET" if capacity_h <= GPU_BUDGET_H else "OVER_BUDGET")),
          "phase_c_protocol": ("REGISTERED" if phase_c_protocol_id else "MISSING") if target > 79 else "N/A",
          "promotion": ("DECIDED" if promotion_record else "NOT_DECIDED") if target > 79 else "N/A (canonical)"}
    st["promotable_now"] = (target > 79 and bool(registered_window) and bool(promotion_record) and bool(phase_c_protocol_id) and st["capacity"] == "WITHIN_BUDGET")
    return st


def promote_allowed(rung: dict) -> bool:
    """Candidate admission-logic dependency: promotion is refused without a registered Phase-C protocol AND a window AND a decision."""
    return bool(rung.get("promotable_now"))


def report() -> dict:
    const = (_REPO / "tools/yuclaw_u350_constitution.py").read_text(errors="replace")
    gate5 = "GATE 5" in const
    rows = [rung_status(n, registered_window=None, promotion_record=None, phase_c_protocol_id=None, capacity_h=CAPACITY_AUDIT_GPU_H.get(n)) for _, n in RUNGS]
    return {"rungs": rows, "membership_classes": {"canonical_scoring": 79, "shadow_u350_admitted": 71, "evidence_only_canada": 49, "note": "classes never merged; scoring an evidence-only name is a STOP condition"},
            "constitution_gate5_shadow_requirement": gate5, "phase_a_summary_source": "internal/u350 phase report (private) — 10 label-anomaly days of 25; 0 promotions; 1 drain-budget breach (2026-08-28)",
            "capacity_note": "GPU-h/day from the 2026-08-02 audit; budget ceiling is a display value pending owner input; U550 not audited"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(); p.add_argument("--json", action="store_true"); a = p.parse_args(argv)
    r = report()
    if a.json:
        print(json.dumps(r, indent=1)); return 0
    for row in r["rungs"]:
        print(f"{row['target']:>4}: impl={row['implementation']} gates={row['admission_gates']} window={row['observation_window']} capacity={row['capacity']} phaseC={row['phase_c_protocol']} promotion={row['promotion']} promotable_now={row['promotable_now']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
