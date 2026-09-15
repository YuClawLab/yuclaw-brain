"""python3 -m v8.workbench  — serve | verify-export | build-export | status | recover | selftest"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from v8.workbench import NOT_ADVICE, export, store

_REPO = Path(__file__).resolve().parents[2]


def _candidate() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO, capture_output=True, text=True, timeout=5).stdout.strip() or None
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python3 -m v8.workbench", description="YUCLAW v8 source-to-export workbench (local, loopback only). " + NOT_ADVICE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="serve one workspace at http://127.0.0.1:PORT"); s.add_argument("--workspace", required=True); s.add_argument("--port", type=int, default=8765); s.add_argument("--fixtures", default=None); s.add_argument("--candidate", default=None)
    v = sub.add_parser("verify-export", help="verify an export zip offline (exit 0 SUCCESS / 1 MISMATCH / 3 UNSUPPORTED)"); v.add_argument("zip"); v.add_argument("--json", action="store_true")
    b = sub.add_parser("build-export", help="build an export for a claim"); b.add_argument("--workspace", required=True); b.add_argument("--claim", required=True)
    st = sub.add_parser("status", help="workspace status (integrity, claims)"); st.add_argument("--workspace", required=True)
    rc = sub.add_parser("recover", help="recover a torn tail (preserves the bytes; records a RECOVERY event)"); rc.add_argument("--workspace", required=True)
    sub.add_parser("selftest", help="run the workbench unit tests")
    a = ap.parse_args(argv)
    if a.cmd == "serve":
        from v8.workbench.server import serve
        serve(a.workspace, a.port, fixtures_dir=a.fixtures, candidate_commit=a.candidate or _candidate()); return 0
    if a.cmd == "verify-export":
        r = export.verify_export(a.zip)
        print(json.dumps(r, indent=1) if a.json else f"[verify-export] {r['result']} — {r.get('first_discrepancy') or r.get('meaning')}\n  zip sha256 {r['zip_sha256']}\n  canonical digest {r['canonical_digest']}\n  recompute {r.get('recompute')}")
        return {"SUCCESS": 0, "MISMATCH": 1}.get(r["result"], 3)
    if a.cmd == "build-export":
        r = export.build_export(store.Workspace(a.workspace), a.claim, candidate_commit=_candidate())
        print(json.dumps({k: r[k] for k in ("export_id", "canonical_digest", "zip_path", "zip_sha256", "zip_bytes")}, indent=1)); return 0
    if a.cmd == "status":
        print(json.dumps(store.Workspace(a.workspace, create=False).status(), indent=1)); return 0
    if a.cmd == "recover":
        print(json.dumps(store.Workspace(a.workspace, create=False).recover(), indent=1, default=str)); return 0
    if a.cmd == "selftest":
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_v8_workbench_calc.py", "tests/test_v8_workbench_store.py", "tests/test_v8_workbench_export.py", "tests/test_v8_workbench_server.py", "tests/test_v8_commitment_fixtures.py"], cwd=_REPO).returncode
    return 2
