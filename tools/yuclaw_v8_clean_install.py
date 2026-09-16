#!/usr/bin/env python3
"""
V8-003 §4 — prove the workbench ships. Build the candidate artifacts ONCE from a clean detached worktree at a commit,
install each artifact (wheel, then sdist) into a fresh virtual environment outside the checkout — no editable install,
no PYTHONPATH — and demonstrate the INSTALLED browser workflow (fixtures journey and, with --sources, the real-source
retrospective replay) plus offline export verification through the installed command line. The evidence binds to the
commit, the tree and the artifact digests, never to the checkout.

  python3 tools/yuclaw_v8_clean_install.py --commit <sha> --out <dir> [--sources <ingest records dir>] [--twine <exe>]
                                           [--playwright-spec "playwright==1.62.0"]

Playwright is installed into the disposable environments as a TEST-TIME tool (dependencies are read from PyPI; pin the
version that matches the cached browsers with --playwright-spec); Chromium comes from the Playwright browser cache. Nothing is uploaded, tagged or pushed. Exit 0 only when every
check passed; the record (`packaging.json`) is written either way. Research and education only. Not investment advice.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
SOURCE_DATE_EPOCH = "1580601600"                      # the publishers' reproducible-build epoch
FORBIDDEN_MEMBERS = ("internal/", "output/", "archive/", "clawhub/", "v8/V8-00", "v8/scope", "__pycache__", ".pyc")
REQUIRED_WHEEL = ("v8/__init__.py", "v8/workbench/__init__.py", "v8/workbench/server.py", "v8/workbench/export.py", "v8/workbench/journey.py", "v8/workbench/ingest.py",
                  "v8/workbench/resources/CommitmentClaim.v1.json", "v8/workbench/resources/fixtures/manifest.json", "v8/workbench/resources/fixtures/001_base.json", "v8/workbench/resources/fixtures/008_quarterly.json")
REQUIRED_SDIST = ("v8/__init__.py", "v8/workbench/server.py", "v8/workbench/resources/CommitmentClaim.v1.json", "v8/workbench/resources/fixtures/008_quarterly.json", "README_PYPI.md", "README.md", "schemas/CommitmentClaim.v1.json")
_HOME_PATH = re.compile(r"/home/[A-Za-z0-9_.-]+/|/Users/[A-Za-z0-9_.-]+/")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(cmd, *, cwd=None, env=None, timeout=1800, check=True) -> subprocess.CompletedProcess:
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None, env=env, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise SystemExit(f"STOP: {' '.join(str(c) for c in cmd)} rc={r.returncode}\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
    return r


# ------------------------------------------------------------------ pure checks (unit-tested)
def inspect_members(kind: str, names: list[str]) -> dict:
    """What an artifact must and must not carry. `names` are member paths relative to the artifact root
    (the sdist's leading `yuclaw-<version>/` already stripped)."""
    required = REQUIRED_WHEEL if kind == "wheel" else REQUIRED_SDIST
    missing = [r for r in required if r not in names]
    forbidden = sorted(n for n in names if any(f in n for f in FORBIDDEN_MEMBERS))
    tests = sorted(n for n in names if n.startswith("tests/"))
    home = sorted(n for n in names if _HOME_PATH.search(n))
    return {"kind": kind, "members": len(names), "missing_required": missing, "forbidden_present": forbidden, "test_tree_present": tests[:5], "home_paths_in_names": home,
            "ok": not missing and not forbidden and not tests and not home}


def long_description_ok(metadata_text: str) -> dict:
    """The PyPI long description (wheel METADATA / sdist PKG-INFO) must be Markdown without the GitHub-only picture block
    or a relative brand image path, and must still carry the canonical MISSION-VISION block markers."""
    body = metadata_text.split("\n\n", 1)[1] if "\n\n" in metadata_text else ""
    ctype = re.search(r"^Description-Content-Type: (.+)$", metadata_text, re.M)
    return {"content_type": ctype.group(1).strip() if ctype else None, "has_picture_element": "<picture" in body, "has_relative_brand_path": 'src="brand/' in body,
            "has_mission_vision_markers": "<!-- MISSION-VISION-CANONICAL:BEGIN -->" in body and "<!-- MISSION-VISION-CANONICAL:END -->" in body,
            "ok": bool(ctype) and ctype.group(1).strip().startswith("text/markdown") and "<picture" not in body and 'src="brand/' not in body and "<!-- MISSION-VISION-CANONICAL:BEGIN -->" in body}


# ------------------------------------------------------------------ build
def build(commit: str, out: Path) -> dict:
    src = out / "src"
    if src.exists():
        raise SystemExit(f"STOP: {src} exists — one build per record directory")
    run(["git", "worktree", "add", "--detach", src, commit], cwd=_REPO)
    try:
        head = run(["git", "rev-parse", "HEAD"], cwd=src).stdout.strip(); tree = run(["git", "rev-parse", "HEAD^{tree}"], cwd=src).stdout.strip()
        if head != commit or run(["git", "status", "--porcelain"], cwd=src).stdout.strip():
            raise SystemExit("STOP: build worktree is not the requested commit or not clean")
        dist = out / "dist"; dist.mkdir()
        env = dict(os.environ, SOURCE_DATE_EPOCH=SOURCE_DATE_EPOCH); env.pop("PYTHONPATH", None)
        t0 = now(); p = run([sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", dist, src], cwd=src, env=env)
        files = sorted(x.name for x in dist.iterdir())
        whl = next((f for f in files if f.endswith(".whl")), None); sd = next((f for f in files if f.endswith(".tar.gz")), None)
        if len(files) != 2 or not whl or not sd:
            raise SystemExit(f"STOP: unexpected dist contents {files}")
        version = re.match(r"yuclaw-([^-]+)-", whl).group(1)
        with zipfile.ZipFile(dist / whl) as z:
            wheel_names = z.namelist(); meta = z.read(f"yuclaw-{version}.dist-info/METADATA").decode("utf-8")
            generator = re.search(r"^Generator: (.+)$", z.read(f"yuclaw-{version}.dist-info/WHEEL").decode(), re.M).group(1)
        with tarfile.open(dist / sd) as t:
            sdist_names = [n.split("/", 1)[1] for n in t.getnames() if "/" in n]
            pkg = t.extractfile(f"yuclaw-{version}/PKG-INFO").read().decode("utf-8")
        art = {"commit": head, "tree": tree, "version": version, "build_utc": t0, "source_date_epoch": SOURCE_DATE_EPOCH,
               "build_tools": {"python": sys.version.split()[0], "build": run([sys.executable, "-m", "build", "--version"]).stdout.strip().split(" (")[0], "wheel_generator": generator},
               "wheel": {"name": whl, "sha256": sha(dist / whl), "size": (dist / whl).stat().st_size, "inspection": inspect_members("wheel", wheel_names), "long_description": long_description_ok(meta)},
               "sdist": {"name": sd, "sha256": sha(dist / sd), "size": (dist / sd).stat().st_size, "inspection": inspect_members("sdist", sdist_names), "long_description": long_description_ok(pkg)},
               "build_stdout_tail": p.stdout[-300:]}
        # resource identity against the SOURCE tree of the commit (the packaged copies must be the tree's bytes)
        ident = {"schema": sha(src / "schemas" / "CommitmentClaim.v1.json") == sha(src / "v8" / "workbench" / "resources" / "CommitmentClaim.v1.json"),
                 "fixtures": all(sha(f) == sha(src / "v8" / "workbench" / "resources" / "fixtures" / f.name) for f in (src / "tests" / "fixtures" / "v8" / "commitments").glob("*.json"))}
        art["source_resource_identity"] = ident
        art["source_hashes"] = {"schema": sha(src / "schemas" / "CommitmentClaim.v1.json"), "fixtures": {f.name: sha(f) for f in sorted((src / "tests" / "fixtures" / "v8" / "commitments").glob("*.json"))}}
        return art
    finally:
        run(["git", "worktree", "remove", "--force", src], cwd=_REPO, check=False)


# ------------------------------------------------------------------ install + demonstrate
def _venv(out: Path, name: str) -> Path:
    v = out / name
    run([sys.executable, "-m", "venv", v])
    run([v / "bin" / "python", "-m", "pip", "install", "-q", "--upgrade", "pip"], timeout=900)
    return v


def install_and_demonstrate(what: str, art: dict, artifact: Path, out: Path, sources: Path | None, browsers_path: str | None, playwright_spec: str = "playwright") -> dict:
    v = _venv(out, f"venv-{what}"); py = v / "bin" / "python"
    home = out / f"home-{what}"; home.mkdir(exist_ok=True); cwd = out / f"run-{what}"; cwd.mkdir(exist_ok=True)
    env = {"PATH": f"{v / 'bin'}:/usr/bin:/bin", "HOME": str(home), "LANG": "C.UTF-8"}          # no PYTHONPATH, no checkout on any path
    if browsers_path:
        env["PLAYWRIGHT_BROWSERS_PATH"] = browsers_path
    res: dict = {"artifact": artifact.name, "artifact_sha256": art[what]["sha256"], "checks": {}}
    run([py, "-m", "pip", "install", "-q", artifact], env=dict(env, PATH=env["PATH"]), timeout=1800)             # non-editable install of the file; dependencies from PyPI
    run([py, "-m", "pip", "install", "-q", playwright_spec], env=env, timeout=1800)                                 # test-time tool only
    res["test_time_tools"] = {"playwright_spec": playwright_spec, "playwright_version": run([py, "-c", "import importlib.metadata as m; print(m.version('playwright'))"], env=env).stdout.strip()}
    probe = run([py, "-c", "import importlib.metadata as m, v8.workbench as w, v8.workbench.server, v8.workbench.export, v8.workbench.journey, v8.workbench.ingest, json, sys, os;"
                            "print(json.dumps({'version': m.version('yuclaw'), 'module': os.path.dirname(w.__file__), 'pythonpath': os.environ.get('PYTHONPATH'), 'sys_path_has_cwd_repo': any(p.endswith('/v8') for p in sys.path)}))"], cwd=cwd, env=env)
    info = json.loads(probe.stdout); res["installed"] = info
    res["checks"]["module_inside_venv"] = info["module"].startswith(str(v)); res["checks"]["no_pythonpath"] = info["pythonpath"] is None; res["checks"]["metadata_version"] = info["version"] == art["version"]
    ident = run([py, "-c", "import hashlib, json, pathlib, v8.workbench as w; r = pathlib.Path(w.__file__).parent / 'resources';"
                           "print(json.dumps({'schema': hashlib.sha256((r / 'CommitmentClaim.v1.json').read_bytes()).hexdigest(), 'fixtures': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((r / 'fixtures').glob('*.json'))}}))"], cwd=cwd, env=env)
    got = json.loads(ident.stdout); res["checks"]["installed_resources_equal_source_tree"] = got == art["source_hashes"]
    res["checks"]["cli_help_rc0"] = run([py, "-m", "v8.workbench", "--help"], cwd=cwd, env=env, check=False).returncode == 0
    journeys = {}
    modes = [("fixtures", [])] + ([("mchp", ["--mode", "mchp", "--sources", str(sources)])] if sources else [])
    for mode, extra in modes:
        jout = out / f"journey-{what}-{mode}"
        r = run([py, "-m", "v8.workbench.journey", "--out", jout, "--candidate", art["commit"], "--artifact", f"{artifact.name}={art[what]['sha256']}", *extra], cwd=cwd, env=env, check=False, timeout=1800)
        log = json.loads((jout / "journey_log.json").read_text()) if (jout / "journey_log.json").exists() else {}
        cand = log.get("candidate", {})
        journeys[mode] = {"rc": r.returncode, "score": log.get("scorecard", {}).get("score"), "candidate_commit": cand.get("commit"), "commit_source": cand.get("commit_source"), "artifacts": cand.get("artifacts"),
                          "workbench_module": cand.get("runtime", {}).get("workbench_module"), "module_inside_venv": str(cand.get("runtime", {}).get("workbench_module", "")).startswith(str(v)),
                          "browser": log.get("browser"), "journey_log_sha256": sha(jout / "journey_log.json") if (jout / "journey_log.json").exists() else None, "stderr_tail": r.stderr[-400:] if r.returncode else ""}
        # offline verification through the installed command line: every export the journey downloaded verifies; every tampered/incomplete/unsafe packet is refused
        ver = {}
        for z in sorted(jout.glob("*.zip")):
            rc = run([py, "-m", "v8.workbench", "verify-export", z], cwd=cwd, env=env, check=False).returncode
            ver[z.name] = {"rc": rc, "sha256": sha(z), "expected": 0 if z.name.startswith("exp-") else "nonzero"}
        journeys[mode]["verify_export"] = ver
        journeys[mode]["ok"] = r.returncode == 0 and journeys[mode]["score"] == "7/7" and cand.get("commit") == art["commit"] and journeys[mode]["module_inside_venv"] and bool(ver) \
            and all((x["rc"] == 0) if x["expected"] == 0 else (x["rc"] != 0) for x in ver.values())
    res["journeys"] = journeys
    res["ok"] = all(res["checks"].values()) and all(j["ok"] for j in journeys.values())
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--commit", required=True); ap.add_argument("--out", required=True); ap.add_argument("--sources", help="ingestion records for the real-source replay (mchp mode)")
    ap.add_argument("--twine", help="twine executable for `twine check` over the built artifacts (default: the first on PATH)")
    ap.add_argument("--playwright-spec", default="playwright", help="pip requirement for the test-time browser driver (pin it to the version whose browsers are cached)")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    commit = run(["git", "rev-parse", "--verify", a.commit + "^{commit}"], cwd=_REPO).stdout.strip()
    rec = {"record": "v8-clean-install/1", "recorded_utc": now(), "commit": commit, "python": sys.version.split()[0], "not_advice": "Research and education only. Not investment advice."}
    art = build(commit, out); rec["build"] = art
    twine = a.twine or shutil.which("twine")
    if twine:
        r = run([twine, "check", "--strict", out / "dist" / art["wheel"]["name"], out / "dist" / art["sdist"]["name"]], check=False, timeout=600)
        rec["twine_check"] = {"rc": r.returncode, "output_tail": (r.stdout + r.stderr)[-600:]}
    else:
        rec["twine_check"] = {"rc": None, "output_tail": "twine not available; long description checked structurally only"}
    browsers = str(Path.home() / ".cache" / "ms-playwright") if (Path.home() / ".cache" / "ms-playwright").is_dir() else None
    sources = Path(a.sources).resolve() if a.sources else None
    rec["installs"] = {}
    for what in ("wheel", "sdist"):
        try:
            rec["installs"][what] = install_and_demonstrate(what, art, out / "dist" / art[what]["name"], out, sources, browsers, a.playwright_spec)
        except SystemExit as exc:
            rec["installs"][what] = {"ok": False, "stop": str(exc)[:1200]}
    ok = (art["wheel"]["inspection"]["ok"] and art["sdist"]["inspection"]["ok"] and art["wheel"]["long_description"]["ok"] and art["sdist"]["long_description"]["ok"] and all(art["source_resource_identity"].values())
          and rec["twine_check"]["rc"] in (0, None) and all(v.get("ok") for v in rec["installs"].values()))
    rec["result"] = "PASS" if ok else "FAIL"
    (out / "packaging.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n")
    print(f"[clean-install] {rec['result']} — commit {commit[:12]} wheel {art['wheel']['sha256'][:12]}… sdist {art['sdist']['sha256'][:12]}… → {out / 'packaging.json'}")
    for what, v in rec["installs"].items():
        print(f"  {what}: ok={v.get('ok')} journeys={{{', '.join(f'{m}: {j.get('score')}' for m, j in v.get('journeys', {}).items())}}}" + (f" STOP {v['stop'][:200]}" if v.get("stop") else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
