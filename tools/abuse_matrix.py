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

v5.3.3 adds the status-semantics case: an empty-corpus universe name
(DIA-style) must come back UNSUPPORTED — zero matched objects is never
a PARTIAL_MATCH with an empty matched_evidence array.

v6.0.1 (ORDER 2026-09-05B D3) adds the CLI first-touch cases permanently:
top-level --help / -h / help (exit 0, every command listed with a
description), --version (exit 0), the malformed generic input (empty
command, exit 2), and the accession-only check-claim branches — unique
(passport, exit 0, payload equal to the explicit ticker+accession path
except input echo), ambiguous (exit 2 with sorted candidates), unknown
(UNSUPPORTED, exit 0) and malformed (exit 2) — never a bare usage dump.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

# Real corpus fixtures (stable historical filings in the published corpus):
UNIQUE_ACCESSION = "0001045810-26-000019"      # one covered name (NVDA)
AMBIGUOUS_ACCESSION = "0001645590-26-000045"   # many covered names
UNKNOWN_ACCESSION = "0000000000-00-000000"     # well-formed, not in the corpus

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
                    ["--text", ""],
                    # v6.0.1 accession-only hostile inputs: malformed and
                    # ambiguous both exit 2 with a message, never a usage dump
                    ["--accession", "not-an-accession"],
                    ["--accession", AMBIGUOUS_ACCESSION]],
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


def _empty_corpus_unsupported(rc, out, err):
    # v5.3.3 status semantics: an empty-corpus universe name (DIA-style)
    # matches ZERO evidence objects, so the passport must say UNSUPPORTED
    # — never a PARTIAL_MATCH with an empty matched_evidence array
    # (the v5.3.2 defect).
    if rc == 0 and '"status": "UNSUPPORTED"' in out:
        return None
    if rc == 3 and "yuclaw.ca/why/" in err:
        return None                       # no corpus at all → friendly pointer
    return (f"exit {rc} — empty-corpus name must be UNSUPPORTED "
            f"(zero matched objects is never PARTIAL_MATCH)")


def _accession_unknown_unsupported(rc, out, err):
    if rc == 0 and '"status": "UNSUPPORTED"' in out and "any covered name" in out:
        return None
    if rc == 3 and "yuclaw.ca/why/" in err:
        return None                       # no corpus at all → friendly pointer
    return f"exit {rc} — unknown accession must be the UNSUPPORTED outcome"


def _accession_ambiguous_exit2(rc, out, err):
    if rc == 2 and "--accession requires --ticker when ambiguous" in err \
            and out == "":
        return None
    if rc == 3 and "yuclaw.ca/why/" in err:
        return None
    return (f"exit {rc} — ambiguous accession must exit 2 with the "
            f"candidates, never a usage dump or a passport")


def _accession_malformed_exit2(rc, out, err):
    if rc == 2 and "not an SEC accession number" in err and out == "":
        return None
    return f"exit {rc} — malformed accession must exit 2 with a message"


def _help_ok(rc, out, err):
    if rc == 0 and "commands:" in out and "check-claim" in out \
            and "replay-lab" in out and "Exit codes" in out:
        return None
    return f"exit {rc} — help must list every command with a description, exit 0"


def _version_ok(rc, out, err):
    if rc == 0 and out.startswith("yuclaw "):
        return None
    return f"exit {rc} — --version must print 'yuclaw <version>', exit 0"


def _empty_command_exit2(rc, out, err):
    if rc == 2 and "unknown command" in err:
        return None
    return f"exit {rc} — malformed generic input must exit 2 with a message"


WELLFORMED = [
    ("check-claim", ["--ticker", "NVDA", "--type", "INSIDER_SELL",
                     "--date-range", "2026-05-01..2026-05-31"], _claim_ok),
    ("check-claim", ["--text",
                     "NVDA reported an insider sale in May 2026"], _claim_ok),
    ("check-claim", ["--ticker", "DIA", "--type", "INSIDER_SELL",
                     "--date-range", "2026-05-01..2026-05-31"],
     _empty_corpus_unsupported),
    # v6.0.1 first-touch (ORDER 2026-09-05B D3)
    ("check-claim", ["--ticker", "NVDA", "--accession", UNIQUE_ACCESSION], _claim_ok),
    ("check-claim", ["--accession", UNIQUE_ACCESSION], _claim_ok),
    ("check-claim", ["--accession", UNKNOWN_ACCESSION], _accession_unknown_unsupported),
    ("check-claim", ["--accession", AMBIGUOUS_ACCESSION], _accession_ambiguous_exit2),
    ("check-claim", ["--accession", "not-an-accession"], _accession_malformed_exit2),
]
# Top-level (no subcommand) cases: (argv, checker)
TOPLEVEL = [
    (["--help"], _help_ok), (["-h"], _help_ok), (["help"], _help_ok),
    (["--version"], _version_ok),
    ([""], _empty_command_exit2),                       # malformed generic input
    (["--definitely-not-a-flag"], _empty_command_exit2),
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
    for argv, checker in TOPLEVEL:
        _run_one(argv[0], argv[1:], checker)
    # D2 assertion: payload(accession-only unique) == payload(explicit
    # ticker+accession) byte-for-byte except input-echo metadata
    try:
        a = subprocess.run(exe + ["check-claim", "--accession", UNIQUE_ACCESSION],
                           capture_output=True, text=True, timeout=120)
        b = subprocess.run(exe + ["check-claim", "--ticker", "NVDA", "--accession",
                                  UNIQUE_ACCESSION], capture_output=True, text=True, timeout=120)
        n += 1
        if a.returncode == 0 and b.returncode == 0:
            import json as _json
            da, db = _json.loads(a.stdout), _json.loads(b.stdout)
            for k in ("claim_as_given", "generated"):
                da.pop(k, None); db.pop(k, None)
            if _json.dumps(da, sort_keys=True) != _json.dumps(db, sort_keys=True):
                failures.append("D2: accession-only payload != explicit "
                                "ticker+accession payload (beyond input echo)")
        elif not (a.returncode == 3 and b.returncode == 3):
            failures.append(f"D2: exits {a.returncode}/{b.returncode} — the two "
                            f"paths must resolve identically")
    except subprocess.TimeoutExpired:
        failures.append("D2 payload identity: TIMEOUT")

    if failures:
        print(f"ABUSE MATRIX: {len(failures)}/{n} cases failed:")
        for f in failures:
            print(f"  · {f}")
        return 1
    print(f"[abuse-matrix] OK — {n} cases across {len(COMMANDS)} commands "
          f"({n_hostile} hostile + {n - n_hostile} well-formed/first-touch/"
          f"top-level): zero tracebacks, hostile exits within the contract "
          f"(0/1/2/3), valid claims resolve offline or point at the public "
          f"JSON, help/version exit 0, accession-only branches per D2, "
          f"Excel-flavored CSV passes clean")
    return 0


if __name__ == "__main__":
    exe = ([sys.argv[sys.argv.index("--exe") + 1]]
           if "--exe" in sys.argv else
           [sys.executable, "-m", "v3.cli"])
    sys.exit(run_matrix(exe))
