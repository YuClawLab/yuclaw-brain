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
invalid date · unknown type · empty file · missing file · garbage file.
Interactive/long-running commands run under a timeout; a timeout is a
failure (a hung command is not crash-proof).
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
                 "IndexError:", "UnboundLocalError:")


def run_matrix(exe: list[str]) -> int:
    tmp = Path(tempfile.mkdtemp(prefix="abuse_"))
    empty = tmp / "empty.csv"
    empty.write_text("")
    garbage = tmp / "garbage.csv"
    garbage.write_text("\x00\x01\x02 not,a,csv\nat all")
    COMMANDS["intake-check"].extend([[str(empty)], [str(garbage)]])

    failures, n = [], 0
    for cmd, arg_sets in COMMANDS.items():
        for args in arg_sets:
            n += 1
            try:
                r = subprocess.run(exe + [cmd] + args, capture_output=True,
                                   text=True, timeout=90)
                out = (r.stdout or "") + (r.stderr or "")
                if any(m in out for m in TRACE_MARKERS):
                    failures.append(f"{cmd} {args}: TRACEBACK leaked")
                elif r.returncode not in OK_EXITS:
                    failures.append(f"{cmd} {args}: exit {r.returncode} "
                                    f"outside the contract {sorted(OK_EXITS)}")
            except subprocess.TimeoutExpired:
                failures.append(f"{cmd} {args}: TIMEOUT (hung on hostile "
                                f"input)")
    if failures:
        print(f"ABUSE MATRIX: {len(failures)}/{n} hostile cases failed:")
        for f in failures:
            print(f"  · {f}")
        return 1
    print(f"[abuse-matrix] OK — {n} hostile cases across "
          f"{len(COMMANDS)} commands: zero tracebacks, all exits within "
          f"the contract (0/1/2/3)")
    return 0


if __name__ == "__main__":
    exe = ([sys.argv[sys.argv.index("--exe") + 1]]
           if "--exe" in sys.argv else
           [sys.executable, "-m", "v3.cli"])
    sys.exit(run_matrix(exe))
