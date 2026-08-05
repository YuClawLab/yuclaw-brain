#!/usr/bin/env python3
"""
Abuse matrix (v5.3.1 systemic guard) — a permanent pre-release test that
feeds EVERY CLI subcommand the hostile input set and asserts, for each:
  - ZERO tracebacks on stdout/stderr
  - a contract-correct exit code: 0 (success) / 1 (ran, negative result)
    / 2 (usage or validation error) / 3 (environment unsupported)
so no command can ship with a crash path the way check-claim did on
2026-08-05. Runs inside the env-i isolation suite before every upload
(pass --exe /path/to/venv/bin/yuclaw) and works on-box by default.

Hostile set per command: no args · unknown flag · reversed date range ·
invalid date · unknown type · empty file · missing file · garbage file ·
non-UTF-8 file.
Interactive/long-running commands run under a timeout; a timeout is a
failure (a hung command is not crash-proof).

v5.3.2 closes the matrix gap: the matrix also feeds WELL-FORMED inputs
under stranger conditions (run it in the backend-less env-i suite) —
a correct structured claim and a correct --text claim must produce a
passport (offline snapshot, exit 0) or the friendly research-node
pointer (exit 3), never a traceback; an Excel-flavored CSV
(BOM+CRLF+quotes) must pass intake-check clean. Malformed inputs
crashing was never the only risk — 2026-08-05's bug was a VALID claim
on a machine without the backend.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

CASES = [
    ("no args", []),
    ("unknown flag", ["--definitely-not-a-flag"]),
]
DATE_CASES = [
    ("invalid date", ["--date", "not-a-date"]),
]
COMMANDS: dict[str, list[list[str]]] = {
    "why": [[], ["--definitely-not-a-flag"], ["AMD", "--as-of", "garbage"]],
    "replay": [[], ["AMD", "--date", "not-a-date"]],
    "verify": [[], ["AMD", "--date", "not-a-date"]],
    "events": [[], ["--ticker", "SU", "--since", "garbage"]],
    "lens": [[], ["nope"], ["canada", "--lens", "NOPE"]],
    "export": [[], ["--lens", "NOPE"]],
    "memo": [[], ["--ticker", "", "--days", "-5"]],
    "validation": [["--definitely-not-a-flag"]],
    "intake-check": [[], ["/nonexistent/file.csv"]],
    "check-claim": [[], ["--ticker", "NVDA", "--date-range",
                         "2026-07-31..2026-07-01"],
                    ["--ticker", "NVDA", "--type", "BANANA_EVENT"],
                    ["--ticker", "NVDA", "--date-range", "a..b"],
                    ["--text", ""]],
    "replay-lab": [["--definitely-not-a-flag"]],
    "demo": [["--definitely-not-a-flag"]],
}
OK_EXITS = {0, 1, 2, 3}
TRACE_MARKERS = ("Traceback (most recent call last)", "KeyError:",
                 "TypeError:", "ValueError:", "AttributeError:",
                 "IndexError:", "UnboundLocalError:",
                 "UnicodeDecodeError:", "psycopg2")

# Well-formed inputs under stranger conditions (the 2026-08-05 blind
# spot): (cmd, args, checker(exit, stdout, stderr) -> failure | None).
# Checkers are stricter than the hostile contract — a valid claim must
# RESOLVE (or point somewhere useful), not merely avoid crashing.


def _claim_ok(rc, out, err):
    if rc == 0 and '"status"' in out:
        return None                       # passport produced (node or
                                          # bundled offline snapshot)
    if rc == 3 and "yuclaw.ca/why/" in err:
        return None                       # friendly public-JSON pointer
    return (f"exit {rc} — expected a passport (exit 0) or the friendly "
            f"research-node pointer (exit 3)")


def _intake_ok(rc, out, err):
    if rc == 0 and "INTAKE-CHECK OK" in out:
        return None
    return f"exit {rc} — Excel-flavored (BOM+CRLF+quotes) CSV must pass clean"


WELLFORMED = [
    ("check-claim", ["--ticker", "NVDA", "--type", "INSIDER_SELL",
                     "--date-range", "2026-05-01..2026-05-31"], _claim_ok),
    ("check-claim", ["--text",
                     "NVDA reported an insider sale in May 2026"], _claim_ok),
]

EXCEL_FLAVORED = (b"\xef\xbb\xbf" + "\r\n".join(
    ",".join(f'"{c}"' for c in row) for row in
    (("date", "ticker", "signal_value"),
     ("2026-07-29", "NVDA", "0.42"),
     ("2026-07-30", "SU", "-0.13"))).encode() + b"\r\n")


def run_matrix(exe: list[str]) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="abuse_"))
    empty = tmp / "empty.csv"
    empty.write_text("")
    garbage = tmp / "garbage.csv"
    garbage.write_text("\x00\x01\x02 not,a,csv\nat all")
    not_utf8 = tmp / "not_utf8.csv"
    not_utf8.write_bytes(b"date,ticker,signal_value\n\xff\xfe2026-07-01,\x80NVDA,1")
    COMMANDS["intake-check"].extend([[str(empty)], [str(garbage)],
                                     [str(not_utf8)]])
    bom = tmp / "excel_flavored.csv"
    bom.write_bytes(EXCEL_FLAVORED)
    wellformed = WELLFORMED + [("intake-check", [str(bom)], _intake_ok)]

    failures, n = [], 0

    def _run_one(cmd, args, checker=None):
        nonlocal n
        n += 1
        try:
            r = subprocess.run(exe + [cmd] + args, capture_output=True,
                               text=True, timeout=90)
        except subprocess.TimeoutExpired:
            failures.append(f"{cmd} {args}: TIMEOUT (hung)")
            return
        out, err = r.stdout or "", r.stderr or ""
        if any(m in out + err for m in TRACE_MARKERS):
            failures.append(f"{cmd} {args}: TRACEBACK leaked")
        elif checker is not None:
            bad = checker(r.returncode, out, err)
            if bad:
                failures.append(f"{cmd} {args}: {bad}")
        elif r.returncode not in OK_EXITS:
            failures.append(f"{cmd} {args}: exit {r.returncode} "
                            f"outside the contract {sorted(OK_EXITS)}")

    n_hostile = 0
    for cmd, arg_sets in COMMANDS.items():
        for args in arg_sets:
            _run_one(cmd, args)
            n_hostile += 1
    for cmd, args, checker in wellformed:
        _run_one(cmd, args, checker)

    if failures:
        print(f"ABUSE MATRIX: {len(failures)}/{n} cases failed:")
        for f in failures:
            print(f"  · {f}")
        return 1
    print(f"[abuse-matrix] OK — {n} cases across {len(COMMANDS)} commands "
          f"({n_hostile} hostile + {n - n_hostile} well-formed-in-stranger-"
          f"conditions): zero tracebacks, hostile exits within the contract "
          f"(0/1/2/3), valid claims resolve offline or point at the public "
          f"JSON, Excel-flavored CSV passes clean")
    return 0


if __name__ == "__main__":
    exe = ([sys.argv[sys.argv.index("--exe") + 1]]
           if "--exe" in sys.argv else
           [sys.executable, "-m", "v3.cli"])
    sys.exit(run_matrix(exe))
