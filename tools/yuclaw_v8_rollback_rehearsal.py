#!/usr/bin/env python3
"""Application-code rollback rehearsal (INT-12 / REL-06) — install the 8.0.0 candidate wheel in a fresh environment outside the
checkout, record research in a workspace, roll the package back to the published 7.0.1 wheel, confirm the workspace bytes are
untouched and 7.0.1 neither offers nor reads the workbench, reinstall 8.0.0 and confirm the same chain tip, integrity OK and
a SUCCESS verification of the export built before the rollback.

    python3 tools/yuclaw_v8_rollback_rehearsal.py --new <yuclaw-8.0.0 wheel> --old <yuclaw-7.0.1 wheel> --out <dir>

Installs with --no-deps (the workbench is standard-library code plus the packaged contracts module), so nothing is read from
the network. This rehearses rolling back APPLICATION CODE only. It is not a backup or a restore drill: backup creation and
restoration are not provided in 8.0.0, and nothing here brings back data that was never written. Test-time tool, never
packaged. Research and education only. Not investment advice.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RECORD = r"""
import json, sys
from pathlib import Path
from v8.workbench import export, schema, server
from v8.workbench.store import Workspace
ws = Workspace(sys.argv[1]); rec = schema.from_fixture(json.loads((server.FIXTURES_DIR / "001_base.json").read_text())); cid = rec["claim"]["claim_id"]
ws.register_source(rec["claim"]["source"], op_id="rollback:src-original"); ws.freeze_claim(rec["claim"], op_id="rollback:freeze")
r = rec["revisions"][0]; ws.register_source(r["source"], op_id="rollback:src-revision")
ws.amend_claim(cid, "REVISED", changes={"range": r["claim"]["range"]}, reason="revised per fixture", source=r["source"], op_id="rollback:amend")
ws.register_source(rec["outcome"]["source"], op_id="rollback:src-outcome"); ws.record_outcome(cid, rec["outcome"], op_id="rollback:outcome")
x = export.build_export(ws, cid, op_id="rollback:export")
print(json.dumps({"status": ws.status(), "export": {k: x[k] for k in ("export_id", "canonical_digest", "zip_path", "zip_sha256")}}))
"""


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree(root: Path) -> dict:
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob("*")) if p.is_file() and p.name != ".lock"}


def run(cmd, **kw):
    env = dict(os.environ); env.pop("PYTHONPATH", None)
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, env=env, **kw)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--new", required=True); ap.add_argument("--old", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args(argv); out = Path(a.out).resolve(); new, old = Path(a.new).resolve(), Path(a.old).resolve()
    repo = Path(__file__).resolve().parents[1]
    if repo in out.parents or out == repo:
        raise SystemExit("refused: --out must be outside the checkout")
    out.mkdir(parents=True, exist_ok=False); venv = out / "venv"; ws = out / "workspace"; py = venv / "bin" / "python"
    rec = {"record": "yuclaw-v8-rollback-rehearsal/1", "recorded_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "new_wheel": {"name": new.name, "sha256": sha(new)}, "old_wheel": {"name": old.name, "sha256": sha(old)},
           "install_mode": "pip --no-deps, fresh virtual environment outside the checkout, no PYTHONPATH", "steps": [], "is_not": "a backup, a restore drill or recovery of unwritten data"}

    def step(name, ok, observed):
        rec["steps"].append({"step": name, "ok": bool(ok), "observed": observed}); print(f"  [{'OK ' if ok else 'BAD'}] {name}")
        return ok

    run([sys.executable, "-m", "venv", venv], check=True)
    version = lambda: run([py, "-m", "pip", "show", "yuclaw"]).stdout.split("Version: ")[1].split()[0]
    p = run([py, "-m", "pip", "install", "-q", "--no-deps", new], cwd=out); step("install the 8.0.0 candidate wheel", p.returncode == 0 and version() == "8.0.0", version() if p.returncode == 0 else p.stderr[-300:])
    p = run([py, "-c", RECORD, ws], cwd=out); first = json.loads(p.stdout) if p.returncode == 0 else {}
    step("record a claim, a revision, an outcome and an export with the installed 8.0.0", p.returncode == 0 and first["status"]["integrity"] == "OK" and first["status"]["events"] == 7, first.get("status") or p.stderr[-400:])
    before = tree(ws)
    p = run([py, "-m", "pip", "install", "-q", "--no-deps", old], cwd=out); step("roll the package back to the published 7.0.1 wheel", p.returncode == 0 and version() == "7.0.1", version() if p.returncode == 0 else p.stderr[-300:])
    p = run([py, "-c", "import v8"], cwd=out); step("7.0.1 has no workbench module: it cannot read or change a workspace", p.returncode != 0 and "No module named 'v8'" in p.stderr, p.stderr.strip().splitlines()[-1:] )
    p = run([py, "-c", "import v3, v4; print('ok')"], cwd=out); step("the 7.0.1 packages import after the rollback (no leftover or missing 7.0.1 module)", p.returncode == 0, (p.stdout + p.stderr).strip()[-200:])
    step("every workspace file is byte-identical after the rollback", tree(ws) == before, f"{len(before)} files")
    p = run([py, "-m", "pip", "install", "-q", "--no-deps", new], cwd=out); step("install 8.0.0 again", p.returncode == 0 and version() == "8.0.0", version() if p.returncode == 0 else p.stderr[-300:])
    p = run([py, "-m", "v8.workbench", "status", "--workspace", ws], cwd=out); st = json.loads(p.stdout) if p.returncode == 0 else {}
    step("the workspace opens unchanged: same chain tip, same event count, integrity OK", st.get("tip") == first["status"]["tip"] and st.get("events") == 7 and st.get("integrity") == "OK", st or p.stderr[-300:])
    p = run([py, "-m", "v8.workbench", "verify-export", first["export"]["zip_path"], "--json"], cwd=out); v = json.loads(p.stdout) if p.stdout.strip().startswith("{") else {}
    step("the export built before the rollback verifies SUCCESS with the same canonical digest", p.returncode == 0 and v.get("result") == "SUCCESS" and v.get("canonical_digest") == first["export"]["canonical_digest"], {"result": v.get("result"), "recompute": (v.get("recompute") or {}).get("result")})
    step("every workspace file is still byte-identical (status and offline verification write nothing)", tree(ws) == before, f"{len(before)} files")
    rec["ok"] = all(s["ok"] for s in rec["steps"]); rec["rollback_instruction"] = "pip install yuclaw==7.0.1 (same environment); workspace directories are left as they are; pip install yuclaw==8.0.0 reads them again unchanged"
    (out / "rollback_rehearsal.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(f"[rollback-rehearsal] {'OK' if rec['ok'] else 'FAILED'} → {out / 'rollback_rehearsal.json'}")
    return 0 if rec["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
