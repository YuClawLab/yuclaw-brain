#!/usr/bin/env python3
"""
CLI ACCEPTANCE MATRIX (ORDER 2026-09-05B D3) — executed against a built
wheel (`--exe /path/to/venv/bin/yuclaw`) or on-box (default: python -m
v3.cli); stdout / stderr / exit recorded PER CASE to a JSON file, expected
exit codes asserted, and the D2 payload identity asserted. Exit 0 = every
case within its contract; 1 = any deviation. Companion to abuse_matrix.py
(which carries the same cases permanently as pass/fail checks); this tool
is the RECORDER — its output is attached to the release record.

Cases (expected exit):
  --version (0) · --help (0) · -h (0) · help (0) ·
  check-claim --text <valid> (0) ·
  check-claim --ticker <known> --accession <known> (0) ·
  check-claim --accession <known-unique> (0, payload == explicit path minus
      input echo) ·
  check-claim --accession <known-ambiguous> (2, sorted candidates) ·
  check-claim --accession <unknown> (0, UNSUPPORTED) ·
  check-claim --accession <malformed> (2) ·
  malformed generic input: yuclaw "" (2) ·
  replay-lab <documented local-bundle path> (0 = reproduced)
On a machine with neither a research node nor the bundled snapshot the
claim cases legitimately exit 3 (friendly pointer) — recorded as such and
accepted ONLY when --allow-exit-3 is passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
UNIQUE = "0001045810-26-000019"
AMBIGUOUS = "0001645590-26-000045"
UNKNOWN = "0000000000-00-000000"
BUNDLE = _REPO / "docs" / "replay" / "lab_replay_bundle.json"


def cases(bundle: str) -> list[tuple[str, list[str], set[int]]]:
    return [
        ("--version", ["--version"], {0}),
        ("--help", ["--help"], {0}),
        ("-h", ["-h"], {0}),
        ("help", ["help"], {0}),
        ("check-claim --text <valid>", ["check-claim", "--text", "NVDA reported an insider sale in May 2026"], {0}),
        ("check-claim --ticker <known> --accession <known>", ["check-claim", "--ticker", "NVDA", "--accession", UNIQUE], {0}),
        ("check-claim --accession <known-unique>", ["check-claim", "--accession", UNIQUE], {0}),
        ("check-claim --accession <known-ambiguous>", ["check-claim", "--accession", AMBIGUOUS], {2}),
        ("check-claim --accession <unknown>", ["check-claim", "--accession", UNKNOWN], {0}),
        ("check-claim --accession <malformed>", ["check-claim", "--accession", "not-an-accession"], {2}),
        ("malformed generic input (empty command)", [""], {2}),
        ("replay-lab <documented local-bundle path>", ["replay-lab", bundle], {0}),
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--exe", help="path to a built `yuclaw` console script (default: python -m v3.cli on-box)")
    ap.add_argument("--bundle", default=str(BUNDLE), help="local replay bundle path (documented replay-lab local path)")
    ap.add_argument("--out", help="write the per-case record (JSON) here")
    ap.add_argument("--allow-exit-3", action="store_true", help="accept exit 3 (no corpus) for claim cases")
    a = ap.parse_args(argv)
    exe = [a.exe] if a.exe else [sys.executable, "-m", "v3.cli"]
    # a built wheel runs from a neutral directory (stranger conditions); the
    # on-box module form needs the checkout on sys.path
    cwd = str(Path.home()) if a.exe else str(_REPO)
    rows, failures = [], []
    for name, args, expected in cases(a.bundle):
        try:
            r = subprocess.run(exe + args, capture_output=True, text=True, timeout=600, cwd=cwd)
            rc, out, err = r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired:
            rc, out, err = None, "", "TIMEOUT"
        ok = rc in expected or (a.allow_exit_3 and rc == 3 and args and args[0] == "check-claim")
        if "Traceback" in out + err:
            ok = False
        if not ok:
            failures.append(f"{name}: exit {rc} (expected {sorted(expected)})")
        rows.append({"case": name, "argv": args, "exit": rc, "expected": sorted(expected), "ok": ok,
                     "stdout_sha256": hashlib.sha256(out.encode()).hexdigest(),
                     "stdout_head": out[:1200], "stderr_head": err[:800]})
    # D2 identity assertion
    a1 = next(r for r in rows if r["case"] == "check-claim --accession <known-unique>")
    a2 = next(r for r in rows if r["case"] == "check-claim --ticker <known> --accession <known>")
    ident = None
    if a1["exit"] == 0 and a2["exit"] == 0:
        p1 = subprocess.run(exe + ["check-claim", "--accession", UNIQUE], capture_output=True, text=True, timeout=300, cwd=cwd).stdout
        p2 = subprocess.run(exe + ["check-claim", "--ticker", "NVDA", "--accession", UNIQUE], capture_output=True, text=True, timeout=300, cwd=cwd).stdout
        d1, d2 = json.loads(p1), json.loads(p2)
        for k in ("claim_as_given", "generated"):
            d1.pop(k, None); d2.pop(k, None)
        ident = json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)
        if not ident:
            failures.append("D2: accession-only payload != explicit ticker+accession payload beyond input echo")
    ver = subprocess.run(exe + ["--version"], capture_output=True, text=True, timeout=120, cwd=cwd).stdout.strip()
    record = {"generated_utc": datetime.now(timezone.utc).isoformat(), "exe": exe, "cli_version": ver,
              "python": platform.python_version(), "platform": platform.platform(),
              "d2_payload_identity": ident, "cases": rows, "failures": failures,
              "status": "GREEN" if not failures else "RED"}
    if a.out:
        Path(a.out).write_text(json.dumps(record, indent=1) + "\n")
    print(f"{'CASE':<50} {'EXIT':>4}  EXPECTED  OK")
    for r in rows:
        print(f"{r['case']:<50} {str(r['exit']):>4}  {str(r['expected']):<9} {'GREEN' if r['ok'] else 'RED'}")
    print(f"D2 payload identity: {ident}  ·  {record['status']}  ·  {ver}")
    for f in failures:
        print("  RED:", f)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
