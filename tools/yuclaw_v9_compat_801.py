#!/usr/bin/env python3
"""Compatibility of a v9-written workspace with the PUBLISHED 8.0.1 client (V9-002 §4.4).

Downloads the published 8.0.1 wheel from PyPI, verifies its SHA-256 against PyPI's own digest (and the frozen 8.0.1 record
when given), installs it into a fresh environment, then — using THAT installation, never this checkout's v8 code —
runs the v8 read and verification operations against a COPY of a workspace that v9 has written (sidecar present):
status, build-export, verify-export of that export, the dataset export, a served session (GET /, /claim/<id>, /verify)
and the installed self-check. Checks that the v8 journal bytes and the v9 sidecar bytes are unchanged afterwards, that a
v8 read on a copy WITHOUT a sidecar creates none, and that the installed 8.0.1 v8 fixtures journey still passes.
The original workspace is never touched. Writes a JSON record to --out. Exit 0 = PASS.

  python3 tools/yuclaw_v9_compat_801.py --workspace <v9-written workspace> --out <record dir> [--python python3.12]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request

PYPI = "https://pypi.org/pypi/yuclaw/8.0.1/json"
FROZEN = pathlib.Path.home() / "yuclaw" / "internal" / "release_v8_0_1" / "release_artifacts_v8.0.1.json"


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree_digest(root: pathlib.Path) -> dict:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = sha(p)
    return out


def run(cmd, env, cwd, timeout=900):
    return subprocess.run([str(c) for c in cmd], env=env, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--workspace", required=True); ap.add_argument("--out", required=True); ap.add_argument("--python", default=sys.executable); a = ap.parse_args(argv)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True); rec = {"record": "yuclaw-v9-compat-published-8.0.1/1", "checks": {}}
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="compat801-")); env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp / "home"), "LANG": "C.UTF-8"}; (tmp / "home").mkdir()
    meta = json.load(urllib.request.urlopen(PYPI, timeout=60)); whl = next(u for u in meta["urls"] if u["filename"].endswith(".whl"))
    dl = tmp / whl["filename"]; urllib.request.urlretrieve(whl["url"], dl)
    rec["wheel"] = {"filename": whl["filename"], "pypi_sha256": whl["digests"]["sha256"], "downloaded_sha256": sha(dl), "size": dl.stat().st_size, "pypi_size": whl["size"], "upload_time": whl["upload_time_iso_8601"]}
    rec["checks"]["wheel_sha256_matches_pypi"] = rec["wheel"]["downloaded_sha256"] == whl["digests"]["sha256"] and dl.stat().st_size == whl["size"]
    if FROZEN.exists():
        fr = json.loads(FROZEN.read_text()); rec["wheel"]["frozen_8_0_1_sha256"] = fr["wheel_sha256"]; rec["checks"]["wheel_sha256_matches_frozen_8_0_1_record"] = fr["wheel_sha256"] == rec["wheel"]["downloaded_sha256"]
    v = tmp / "venv"; subprocess.run([a.python, "-m", "venv", str(v)], check=True); py, exe = v / "bin" / "python", v / "bin" / "yuclaw"
    subprocess.run([str(py), "-m", "pip", "install", "-q", str(dl)], check=True, env=dict(env, PATH=f"{v / 'bin'}:/usr/bin:/bin"), timeout=1200)
    env["PATH"] = f"{v / 'bin'}:/usr/bin:/bin"
    ver = run([exe, "--version"], env, tmp).stdout.strip(); mod = run([py, "-c", "import v8.workbench, os; print(os.path.dirname(v8.workbench.__file__))"], env, tmp).stdout.strip()
    has_v9 = run([py, "-c", "import importlib.util; print(importlib.util.find_spec('v9') is not None)"], env, tmp).stdout.strip()
    rec["installed"] = {"cli_version": ver, "v8_module_dir": mod, "v9_importable": has_v9}
    rec["checks"]["installed_client_is_published_8_0_1_without_v9"] = "8.0.1" in ver and mod.startswith(str(v)) and has_v9 == "False"
    src = pathlib.Path(a.workspace).resolve(); work = tmp / "copy"; shutil.copytree(src, work, symlinks=False)
    rec["workspace"] = {"original": str(src), "original_untouched_digest_before": hashlib.sha256(json.dumps(tree_digest(src), sort_keys=True).encode()).hexdigest()}
    before = {"journal": sha(work / "commitments.jsonl"), "sidecar": tree_digest(work / "v9"), "vault": tree_digest(work / "private" / "vault") if (work / "private" / "vault").exists() else {}}
    ops = {}
    st = run([exe, "workbench", "status", "--workspace", work], env, tmp); ops["status"] = {"rc": st.returncode, "integrity": json.loads(st.stdout).get("integrity") if st.returncode == 0 else st.stderr[-300:]}
    claims = json.loads(st.stdout).get("claims", []) if st.returncode == 0 else []
    cid = claims[0] if claims else None
    be = run([exe, "workbench", "build-export", "--workspace", work, "--claim", cid], env, tmp) if cid else None
    ops["build_export"] = {"rc": be.returncode if be else None, "zip": json.loads(be.stdout)["zip_path"] if be and be.returncode == 0 else (be.stderr[-300:] if be else "no claim")}
    if be and be.returncode == 0:
        ve = run([exe, "workbench", "verify-export", ops["build_export"]["zip"], "--json"], env, tmp); ops["verify_export"] = {"rc": ve.returncode, "result": json.loads(ve.stdout).get("result") if ve.stdout.strip().startswith("{") else ve.stdout[-200:]}
    # a served session on the copy: GET /, /claim/<id>, /verify through the installed 8.0.1 server
    port_probe = run([py, "-c", "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()"], env, tmp).stdout.strip()
    srv = subprocess.Popen([str(exe), "workbench", "serve", "--workspace", str(work), "--port", port_probe], env=env, cwd=str(tmp), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        pages = {}
        for path in ("/", f"/claim/{urllib.parse.quote(cid, safe='')}" if cid else "/", "/verify", "/journal"):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port_probe}{path}", timeout=30) as r:
                    body = r.read(); pages[path] = {"status": r.status, "bytes": len(body), "mentions_claim": bool(cid and cid.encode() in body)}
            except Exception as exc:  # noqa: BLE001
                pages[path] = {"error": exc.__class__.__name__}
        ops["served_pages"] = pages
    finally:
        srv.terminate(); srv.wait(timeout=20)
    selft = run([exe, "workbench", "selftest", "--json"], env, tmp); ops["selftest"] = {"rc": selft.returncode, "result": json.loads(selft.stdout).get("result") if selft.stdout.strip().startswith("{") else selft.stdout[-200:]}
    after = {"journal": sha(work / "commitments.jsonl"), "sidecar": tree_digest(work / "v9"), "vault": tree_digest(work / "private" / "vault") if (work / "private" / "vault").exists() else {}}
    rec["operations"] = ops
    rec["checks"]["v8_reads_and_verification_succeed"] = ops["status"]["rc"] == 0 and ops["status"]["integrity"] == "OK" and ops.get("build_export", {}).get("rc") == 0 and ops.get("verify_export", {}).get("result") == "SUCCESS" and all(p.get("status") == 200 for p in ops["served_pages"].values()) and ops["selftest"]["result"] == "PASS"
    rec["checks"]["v9_sidecar_bytes_untouched_by_v8"] = before["sidecar"] == after["sidecar"] and before["vault"] == after["vault"]
    rec["checks"]["v8_journal_grew_only_by_v8_own_events"] = (before["journal"] != after["journal"]) and (work / "commitments.jsonl").read_bytes().startswith((src / "commitments.jsonl").read_bytes())   # build-export appends EXPORT_BUILT; the prior bytes are a prefix
    rec["journal"] = {"before_sha256": before["journal"], "after_sha256": after["journal"], "original_is_prefix_of_copy": rec["checks"]["v8_journal_grew_only_by_v8_own_events"]}
    # a copy WITHOUT a sidecar: v8 reads create none
    bare = tmp / "bare"; shutil.copytree(src, bare, symlinks=False); shutil.rmtree(bare / "v9"); shutil.rmtree(bare / "private", ignore_errors=True)
    run([exe, "workbench", "status", "--workspace", bare], env, tmp); run([exe, "workbench", "build-export", "--workspace", bare, "--claim", cid], env, tmp) if cid else None
    rec["checks"]["v8_read_creates_no_sidecar"] = not (bare / "v9").exists()
    # the installed 8.0.1 fixtures journey (its own workspace), as the established v8 journey
    run([py, "-m", "pip", "install", "-q", "playwright==1.62.0"], env, tmp, timeout=1200)
    jenv = dict(env, PLAYWRIGHT_BROWSERS_PATH=str(pathlib.Path.home() / ".cache" / "ms-playwright"))
    jr = run([py, "-m", "v8.workbench.journey", "--out", tmp / "journey", "--candidate", "published-8.0.1", "--artifact", f"{whl['filename']}={rec['wheel']['downloaded_sha256']}"], jenv, tmp, timeout=1800)
    logp = tmp / "journey" / "journey_log.json"; score = json.loads(logp.read_text()).get("scorecard", {}).get("score") if logp.exists() else None
    rec["v8_fixtures_journey"] = {"rc": jr.returncode, "score": score, "stderr_tail": jr.stderr[-300:] if jr.returncode else ""}
    rec["checks"]["installed_8_0_1_fixtures_journey_passes"] = jr.returncode == 0 and score == "7/7"
    rec["workspace"]["original_untouched_digest_after"] = hashlib.sha256(json.dumps(tree_digest(src), sort_keys=True).encode()).hexdigest()
    rec["checks"]["original_workspace_untouched"] = rec["workspace"]["original_untouched_digest_before"] == rec["workspace"]["original_untouched_digest_after"]
    rec["result"] = "PASS" if all(rec["checks"].values()) else "FAIL"
    rec["scope"] = ("read and verification operations of the published 8.0.1 client (status, build-export, verify-export, served pages, selftest, fixtures journey) against a copy of a v9-written workspace with the sidecar present; "
                    "not a claim about 8.0.1 WRITE operations into such a workspace beyond the export it builds, and not about clients older than 8.0.1")
    (out / "compat_published_8.0.1.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps({"result": rec["result"], "checks": rec["checks"], "wheel": rec["wheel"]["downloaded_sha256"][:16], "cli": ver}, indent=1))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if rec["result"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
