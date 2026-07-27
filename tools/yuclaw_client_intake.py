#!/usr/bin/env python3
"""
Client-signal intake validation (BYOS lane) — stranger-machine-grade errors.

Validates a client CSV of point-in-time signals before ANY analysis runs.
Required columns: date, ticker, signal_value (extra columns are carried,
not rejected). Every failure produces a clear one-line message with row
numbers; the CLI exits non-zero with no traceback, ever.

Checks:
  C1 columns      — required columns present (case-insensitive match)
  C2 dates        — ISO YYYY-MM-DD, parseable
  C3 values       — finite floats (NaN/inf/empty/text refused)
  C4 duplicates   — one row per (ticker, date)
  C5 lookahead    — signal dated in the future, or dated after its own
                    stated generation time (optional as_of/generated_at
                    column), is refused: the forward window would start
                    before the signal could have existed
Out-of-universe tickers are NOT an error here — they are returned as a
disclosed exclusion list for the analysis layer to report with counts.

Library: validate(path) -> (rows, report). CLI: exit 0 clean, exit 2 invalid.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REQUIRED = ("date", "ticker", "signal_value")
MAX_SHOWN = 5   # examples per error class


class IntakeError(Exception):
    """Validation failure with a user-facing message list."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("; ".join(problems))


def _fmt_rows(rows):
    shown = ", ".join(f"row {r}" for r in rows[:MAX_SHOWN])
    more = f" (+{len(rows) - MAX_SHOWN} more)" if len(rows) > MAX_SHOWN else ""
    return shown + more


def validate(path: str | Path) -> tuple[list[dict], dict]:
    """Returns (clean_rows, report). Raises IntakeError with friendly
    messages on any hard failure. clean_rows: [{date, ticker, signal_value,
    **extras}] with date as datetime.date and signal_value as float."""
    p = Path(path)
    if not p.exists():
        raise IntakeError([f"file not found: {p}"])
    with p.open() as f:
        lines = [ln for ln in f if not ln.lstrip().startswith("#")]
    if not lines:
        raise IntakeError(["file is empty (or only comment lines)"])
    reader = csv.DictReader(lines)
    cols = [c.strip().lower() for c in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        raise IntakeError(
            [f"missing required column(s): {', '.join(missing)} — expected "
             f"header: date,ticker,signal_value (found: {', '.join(cols) or 'none'})"])
    colmap = {c.strip().lower(): c for c in reader.fieldnames}
    as_of_col = next((colmap[c] for c in ("as_of", "generated_at")
                      if c in colmap), None)

    today = datetime.now(timezone.utc).date()
    bad_date, bad_val, future_rows, after_asof = [], [], [], []
    seen, dup_rows = {}, []
    rows = []
    for n, raw in enumerate(reader, start=2):   # header = line 1
        d_raw = (raw[colmap["date"]] or "").strip()
        tk = (raw[colmap["ticker"]] or "").strip().upper()
        v_raw = (raw[colmap["signal_value"]] or "").strip()
        try:
            d = date.fromisoformat(d_raw)
        except ValueError:
            bad_date.append(n)
            continue
        try:
            v = float(v_raw)
            if math.isnan(v) or math.isinf(v):
                raise ValueError
        except ValueError:
            bad_val.append(n)
            continue
        if not tk:
            bad_val.append(n)
            continue
        if d > today:
            future_rows.append(n)
            continue
        if as_of_col:
            try:
                gen = date.fromisoformat((raw[as_of_col] or "").strip())
                if d > gen:
                    after_asof.append(n)
                    continue
            except ValueError:
                pass   # unparseable as_of: date check C2 covers the main col only
        key = (tk, d)
        if key in seen:
            dup_rows.append(n)
            continue
        seen[key] = n
        rows.append({"date": d, "ticker": tk, "signal_value": v,
                     **{k: v2 for k, v2 in raw.items()
                        if k not in (colmap["date"], colmap["ticker"],
                                     colmap["signal_value"])}})

    problems = []
    if bad_date:
        problems.append(f"unparseable date (need YYYY-MM-DD): {_fmt_rows(bad_date)}")
    if bad_val:
        problems.append(f"signal_value not a finite number (NaN/inf/text/"
                        f"empty refused) or blank ticker: {_fmt_rows(bad_val)}")
    if dup_rows:
        problems.append(f"duplicate (ticker, date) rows: {_fmt_rows(dup_rows)}")
    if future_rows:
        problems.append(f"lookahead-suspicious: signal dated in the future: "
                        f"{_fmt_rows(future_rows)}")
    if after_asof:
        problems.append(f"lookahead-suspicious: signal dated after its own "
                        f"{'as_of' if 'as_of' in cols else 'generated_at'} "
                        f"timestamp: {_fmt_rows(after_asof)}")
    if problems:
        raise IntakeError(problems)
    if not rows:
        raise IntakeError(["no valid data rows after parsing"])

    report = {
        "n_rows": len(rows),
        "n_tickers": len({r['ticker'] for r in rows}),
        "n_dates": len({r['date'] for r in rows}),
        "date_range": [min(r['date'] for r in rows).isoformat(),
                       max(r['date'] for r in rows).isoformat()],
    }
    return rows, report


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: yuclaw_client_intake.py <client.csv>")
        return 2
    try:
        rows, report = validate(args[0])
    except IntakeError as e:
        print("INTAKE REJECTED — fix the following and resubmit:")
        for prob in e.problems:
            print(f"  · {prob}")
        return 2
    print(f"INTAKE OK — {json.dumps(report)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
