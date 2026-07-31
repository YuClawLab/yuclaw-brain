"""CLI: yuclaw lens canada --lens XEG

Lens summary-card data as JSON — the SAME numbers the Canada Resources page
renders (posture + maturity), never hand-typed. Usefulness build, 2026-07-16.
"""
from __future__ import annotations

import argparse
import json
import sys


def _main(argv: list[str] | None = None) -> int:
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


def _friendly_backend_exit(exc: Exception) -> int:
    """5.1.0 ship-shape (per the 5.0.1 replay-lab pattern): backend-connected
    commands fail with a message and a distinct exit code, never a traceback.
    0 = ok, 2 = usage, 3 = backend unavailable."""
    import sys as _sys
    print("backend unavailable: this command reads the YUCLAW research "
          "backend (Postgres evidence store + research data files), which "
          "is not present on this machine.\n"
          f"  detail: {type(exc).__name__}: {str(exc)[:140]}\n"
          "  offline instead: `yuclaw demo` (bundled AMD @ 2026-05-20) or "
          "`yuclaw replay-lab` (public bundle).\n"
          "  to connect a backend: see README \u00a7 'connect the local "
          "backend'.", file=_sys.stderr)
    return 3


def main(argv: list[str] | None = None) -> int:
    try:
        return _main(argv)
    except SystemExit:
        raise
    except Exception as exc:                     # noqa: BLE001
        import psycopg2
        if isinstance(exc, (psycopg2.OperationalError, FileNotFoundError,
                            RuntimeError, ImportError)):
            return _friendly_backend_exit(exc)
        raise
