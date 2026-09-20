"""python3 -m v8.workbench  — serve | verify-export | build-export | status | recover | guide | principals | modules | selftest"""
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
    sub.add_parser("guide", help="print the packaged startup and operator guide")
    pr = sub.add_parser("principals", help="local principals of the four modules (host operator): init | add | rotate | revoke | list")
    pr.add_argument("action", choices=("init", "add", "rotate", "revoke", "list")); pr.add_argument("--workspace", required=True); pr.add_argument("--id", default="owner")
    pr.add_argument("--caps", default="admin", help="comma separated: admin,submit,review,practice"); pr.add_argument("--expires", default=None); pr.add_argument("--reason", default="revoked by the host operator")
    ms = sub.add_parser("modules", help="module status: principals configured, isolation capability (live probe), budgets and configuration"); ms.add_argument("--workspace", required=True)
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
    if a.cmd == "principals":
        from v8.workbench.modules import authz
        ws = store.Workspace(a.workspace); P = authz.Principals(ws)
        if a.action == "list":
            print(json.dumps([{k: v for k, v in p.items() if k != "enrolled_by"} for p in P.state().values()], indent=1)); return 0
        if a.action == "init" and P.configured():
            print("[principals] this workspace already has principals; sign in as an administrator, or use `principals add` as the host operator", file=sys.stderr); return 1
        op = store.new_op_id("cli")
        if a.action in ("init", "add"):
            ev, cred = P.enroll(a.id, ["admin"] if a.action == "init" else [c.strip() for c in a.caps.split(",") if c.strip()], expires_at=a.expires, op_id=op, by=None)
        elif a.action == "rotate":
            ev, cred = P.rotate(a.id, expires_at=a.expires, op_id=op, by=None)
        else:
            P.revoke(a.id, a.reason, op_id=op, by=None); print(f"[principals] {a.id} revoked (never revived)"); return 0
        # the credential goes to the terminal ONCE; it is not written to the journal, a log or a file
        print(f"[principals] {a.id} ({', '.join(P.state()[a.id]['caps'])}) — credential, shown once:\n{cred}\nSign in at http://127.0.0.1:<port>/login (through your usual SSH tunnel when remote).")
        return 0
    if a.cmd == "modules":
        from v8.workbench.modules import authz, commons, evolution, sandbox
        ws = store.Workspace(a.workspace, create=False); cap = sandbox.capability()
        print(json.dumps({"principals_configured": authz.Principals(ws).configured(), "setup_step": authz.SETUP_STEP, "isolation_backend": cap["backend"], "isolation_closed_reason": cap["closed_reason"],
                          "isolation_probes": [{k: p.get(k) for k in ("backend", "available", "reason", "platform")} for p in cap["probes"]],
                          "com_budget": commons.capacity(commons.state(ws)), "evo_configured": evolution.state(ws)["config"] is not None}, indent=1)); return 0
    if a.cmd == "guide":
        from v8.workbench.server import GUIDE_PATH
        print(GUIDE_PATH.read_text(encoding="utf-8"), end=""); return 0
    if a.cmd == "selftest":
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_v8_workbench_calc.py", "tests/test_v8_workbench_store.py", "tests/test_v8_workbench_export.py", "tests/test_v8_workbench_server.py", "tests/test_v8_commitment_fixtures.py"], cwd=_REPO).returncode
    return 2
