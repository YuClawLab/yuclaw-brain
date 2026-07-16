"""CLI: yuclaw lens canada --lens XEG

Lens summary-card data as JSON — the SAME numbers the Canada Resources page
renders (posture + maturity), never hand-typed. Usefulness build, 2026-07-16.
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw lens",
                                description="Lens summary data as JSON (derived, read-only)")
    p.add_argument("vertical", choices=["canada"], help="evidence vertical")
    p.add_argument("--lens", required=True, help="XEG | ZEO | GDX | URNM")
    a = p.parse_args(argv)

    from v3.lab.etf_evidence import CANADA_LENS_KEYS, canada_event_maturity, canada_posture
    lens = a.lens.upper()
    if lens not in CANADA_LENS_KEYS:
        print(f"unknown lens {lens!r} — choose from {', '.join(CANADA_LENS_KEYS)}",
              file=sys.stderr)
        return 2

    posture = canada_posture(lens)
    mat = canada_event_maturity(lens)
    n_insider = sum(1 for m in posture["members"]
                    if m["insider_scope"].startswith("Form 4 stream"))
    out = {
        "lens": lens,
        "name": posture["name"],
        "theme": posture["theme"],
        "coverage_weight_pct": posture["sec_filer_weight_pct"],
        "sec_filer_count": posture["n_names_covered"],
        "names_total": posture["n_names_total"],
        "filings_ingested": posture["filings_total"],
        "accepted_events": posture["events_total"],
        "matured_events": mat["n_matured"],
        "insider_eligible_names": n_insider,
        "outside_scope": posture["uncovered_scope"],
        "note": ("Evidence tier only — never scored. Counts and classifications, "
                 "not recommendations."),
    }
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
