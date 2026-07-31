"""CLI: yuclaw export --lens GDX --format csv [--out DIR]
     yuclaw export --page lab|open_index|canada [--out DIR]

Evidence exports — YUCLAW-derived data only (the packet export rule: derived
statistics, counts, classifications, verified excerpts; never raw vendor
OHLCV/options data). Usefulness build, 2026-07-16.

  --lens: write that lens's accepted-events file (csv or json) to --out.
  --page: build the full evidence packet .zip for a page into docs/packets/
          (same builder the daily chain runs) and print its path.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw export",
                                description="Export derived evidence data (packet rule applies)")
    tgt = p.add_mutually_exclusive_group(required=True)
    tgt.add_argument("--lens", help="XEG | ZEO | GDX | URNM — lens events export")
    tgt.add_argument("--page", choices=["lab", "open_index", "canada"],
                     help="build the page's full evidence packet (.zip)")
    p.add_argument("--format", choices=["csv", "json"], default="csv",
                   help="lens export format (default csv)")
    p.add_argument("--out", default=".", help="output directory (default: cwd)")
    a = p.parse_args(argv)

    out_dir = Path(a.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    if a.page:
        from v3.web.evidence_packets import build
        info = build(only=a.page)[a.page]
        src = Path(__file__).resolve().parents[2] / "docs" / "packets" / info["zip"]
        print(f"packet: {src} ({info['size_kb']} KB) · data through {info['data_through']}")
        return 0

    from v3.lab.etf_evidence import CANADA_LENS_KEYS, canada_lens_holdings
    lens = a.lens.upper()
    if lens not in CANADA_LENS_KEYS:
        print(f"unknown lens {lens!r} — choose from {', '.join(CANADA_LENS_KEYS)}",
              file=sys.stderr)
        return 2
    tickers = sorted(canada_lens_holdings()[lens])

    from v3.cli.events import fetch_events
    rows: list[dict] = []
    for t in tickers:
        rows.extend(fetch_events(t, None))
    rows.sort(key=lambda r: str(r["available_as_of"]))

    dest = out_dir / f"yuclaw_{lens.lower()}_events.{a.format}"
    if a.format == "json":
        dest.write_text(json.dumps(rows, indent=1, default=str))
    else:
        import csv as _csv
        from v3.cli.events import COLUMNS
        with dest.open("w", newline="") as f:
            w = _csv.writer(f)
            w.writerow(COLUMNS)
            for r in rows:
                w.writerow([r[c] for c in COLUMNS])
    print(f"wrote {dest} · {len(rows)} accepted event(s) across {len(tickers)} covered names "
          f"· derived data only")
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
