#!/usr/bin/env python3
"""Capacity assessment (v7 P2): a usable tool over EXISTING metadata — measured values, inferred values and
unknowns are reported SEPARATELY. No RTX workload, no commissioning assumption, no backup trigger, no reboot.

  python3 tools/yuclaw_capacity_assessment.py [--metadata FILE] [--json]

Metadata (JSON) shape: {"audit_date": "2026-08-02", "gpu_h_per_day_measured": {"79": 1.10, "150": 1.52, "250": 2.11, "350": 2.29},
  "shadow_drain_gpu_min_per_day": {"min": 10.6, "max": 49.7, "budget": 48.0, "breaches": 1}, "box": {...}, "ceiling_gpu_h": 2.0, "operator_hours_per_week": null}
Default metadata = the 2026-08-02 audit as documented in docs/methodology/capacity_and_rtx_status.md."""
from __future__ import annotations

import argparse
import json
import sys

DEFAULT = {"audit_date": "2026-08-02", "source": "docs/methodology/capacity_and_rtx_status.md (capacity audit 2026-08-02; fact packet §6)",
           "gpu_h_per_day_measured": {"79": 1.10, "150": 1.52, "250": 2.11, "350": 2.29},
           "shadow_drain_gpu_min_per_day": {"min": 10.6, "max": 49.7, "budget": 48.0, "breaches": 1, "breach_date": "2026-08-28"},
           "box": {"model": "GB10", "ram_gib": 119, "filesystem_tb": 3.7, "gpu_lock": "exclusivity contract (MemoryMax=100G scope)"},
           "ceiling_gpu_h": 2.0, "ceiling_source": "display ceiling pending owner input", "operator_hours_per_week": None,
           "rtx_pro_6000": {"commissioning_record": None, "storage_record": None, "availability_record": None}}


def assess(meta: dict) -> dict:
    m = meta.get("gpu_h_per_day_measured", {}); pts = sorted((int(k), float(v)) for k, v in m.items())
    measured = {str(k): {"gpu_h_per_day": v, "basis": "MEASURED", "audit_date": meta.get("audit_date")} for k, v in pts}
    inferred = {}
    if len(pts) >= 2:
        (x1, y1), (x2, y2) = pts[-2], pts[-1]; slope = (y2 - y1) / (x2 - x1) if x2 != x1 else 0.0
        for target in (550,):
            if str(target) not in measured:
                inferred[str(target)] = {"gpu_h_per_day": round(y2 + slope * (target - x2), 2), "basis": "INFERRED (linear extrapolation of the last two measured rungs; not a measurement)", "from_rungs": [x1, x2]}
    ceiling = meta.get("ceiling_gpu_h")
    verdicts = {}
    for k, v in {**measured, **inferred}.items():
        verdicts[k] = ("WITHIN_CEILING" if v["gpu_h_per_day"] <= ceiling else "OVER_CEILING") if ceiling is not None else "NO_CEILING"
        verdicts[k] += "" if v["basis"] == "MEASURED" else " (inferred)"
    drain = meta.get("shadow_drain_gpu_min_per_day", {})
    software = {"shadow_drain_gpu_min_per_day": drain, "note": "software workload estimate from the audit; per-form seconds for 10-Q/20-F were MODELED (150 s), disclosed as such in the audit"}
    operator = {"hours_per_week": meta.get("operator_hours_per_week"), "basis": "UNKNOWN (not a data item; never inferred)"} if meta.get("operator_hours_per_week") is None else {"hours_per_week": meta["operator_hours_per_week"], "basis": "SUPPLIED"}
    rtx = meta.get("rtx_pro_6000", {})
    return {"audit_date": meta.get("audit_date"), "source": meta.get("source"), "measured": measured, "inferred": inferred, "ceiling_gpu_h": ceiling, "ceiling_basis": meta.get("ceiling_source"), "verdicts": verdicts,
            "software_workload": software, "operator_hours": operator, "box": meta.get("box"),
            "rtx_pro_6000": {"status": "NOT_COMMISSIONED" if not any(rtx.values()) else "RECORDS_PRESENT", "records": rtx, "note": "never assumed as capacity; its first project workload requires a commissioning order"},
            "commissioning_checklist": ["owner commissioning order naming the workload", "hardware/driver inventory recorded on the box", "storage and availability records", "gpu-lock contract extended or a separate scope defined",
                                        "a measured (not inferred) GPU-h/day audit on the new device before any capacity claim", "backup custody decision unchanged by commissioning (Calgary trigger)"],
            "rules": "measured vs inferred vs unknown are never merged; no workload was run to produce this assessment"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--metadata"); ap.add_argument("--json", action="store_true"); a = ap.parse_args(argv)
    meta = json.loads(open(a.metadata).read()) if a.metadata else DEFAULT
    out = assess(meta)
    if a.json:
        print(json.dumps(out, indent=1)); return 0
    for k, v in out["measured"].items(): print(f"U{k}: {v['gpu_h_per_day']} GPU-h/day MEASURED ({v['audit_date']}) → {out['verdicts'][k]}")
    for k, v in out["inferred"].items(): print(f"U{k}: {v['gpu_h_per_day']} GPU-h/day {v['basis']} → {out['verdicts'][k]}")
    print(f"operator hours: {out['operator_hours']['basis']}; RTX PRO 6000: {out['rtx_pro_6000']['status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
