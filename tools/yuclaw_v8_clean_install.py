#!/usr/bin/env python3
"""
V8-003 §4 — prove the workbench ships. Build the candidate artifacts ONCE from a clean detached worktree at a commit,
install each artifact (wheel, then sdist) into a fresh virtual environment outside the checkout — no editable install,
no PYTHONPATH — and demonstrate the INSTALLED browser workflow (fixtures journey and, with --sources, the real-source
retrospective replay) plus offline export verification through the installed command line. The evidence binds to the
commit, the tree and the artifact digests, never to the checkout.

  python3 tools/yuclaw_v8_clean_install.py --commit <sha> --out <dir> [--sources <ingest records dir>] [--twine <exe>]
                                           [--playwright-spec "playwright==1.62.0"] [--artifacts <dir with an identity record>]

With --artifacts the tool does NOT build: it adopts an already-built wheel/sdist pair whose `artifact_identity.json`
(version, commit, tree, file names, sha256, sizes) it verifies byte-for-byte against the files and against the requested
commit and its tree before installing and demonstrating from them. Without --artifacts the build is a PRELIMINARY
development build; the identity record it writes lets a later run (or the publisher) adopt exactly those bytes.

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
FORBIDDEN_MEMBERS = ("internal/", "output/", "archive/", "clawhub/", "v8/V8-", "v8/scope", "v8/policy", "__pycache__", ".pyc", "/private/", "principals.json", ".pem", "commitments.jsonl")      # V8-014: no credential store, signing key, vault or journal ever ships      # "v8/V8-": every order record (the earlier "v8/V8-00" would have missed V8-010 and later)
REQUIRED_WHEEL = ("v8/__init__.py", "v8/workbench/__init__.py", "v8/workbench/server.py", "v8/workbench/export.py", "v8/workbench/journey.py", "v8/workbench/ingest.py", "v8/workbench/availability.py",
                  "v8/workbench/resources/CommitmentClaim.v1.json", "v8/workbench/resources/fixtures/manifest.json", "v8/workbench/resources/fixtures/001_base.json", "v8/workbench/resources/fixtures/008_quarterly.json",
                  "v8/workbench/resources/OPERATOR_GUIDE.md", "v8/workbench/resources/DATA_DICTIONARY.md", "v8/workbench/modkinds.py") + tuple(
                      f"v8/workbench/modules/{m}.py" for m in ("__init__", "core", "authz", "envelope", "sandbox", "sandbox_bootstrap", "shield_worker", "shield", "evolution", "commons", "practice", "modexport", "web", "journey_modules"))      # V8-014: the four modules ship
REQUIRED_SDIST = ("v8/__init__.py", "v8/workbench/server.py", "v8/workbench/modkinds.py", "v8/workbench/modules/shield.py", "v8/workbench/modules/shield_worker.py", "v8/workbench/modules/sandbox_bootstrap.py", "v8/workbench/modules/practice.py", "v8/workbench/resources/CommitmentClaim.v1.json", "v8/workbench/resources/fixtures/008_quarterly.json", "README_PYPI.md", "README.md", "schemas/CommitmentClaim.v1.json")
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


def source_documents(src: Path, out: Path, dist: Path, art: dict) -> dict:
    """V8-017: the README transcript is compared EXACTLY with a fresh transcript of each installed artifact (the comparison
    the release publisher makes — a version-only check let a stale `replay-lab` section reach the release). The commit's
    README.md, README_PYPI.md and replay bundle are kept beside the record for that, and the documents inside the
    distributions must be the commit's bytes. The transcript runs with YUCLAW_CORPUS=snapshot (tools/cli_transcript.py): the
    commit's corpus snapshot is kept too, so the snapshot inside each INSTALLED artifact can be identified as the commit's."""
    keep = out / "source-files"; (keep / "docs" / "replay").mkdir(parents=True, exist_ok=True); (keep / "v3" / "evidence").mkdir(parents=True, exist_ok=True)
    for rel in ("README.md", "README_PYPI.md", "docs/replay/lab_replay_bundle.json", "v3/evidence/corpus_snapshot.json.gz"):
        shutil.copy2(src / rel, keep / rel)
    version = art["version"]; pypi = (src / "README_PYPI.md").read_text(encoding="utf-8").strip()
    with zipfile.ZipFile(dist / art["wheel"]["name"]) as z:
        wheel_desc = z.read(f"yuclaw-{version}.dist-info/METADATA").decode("utf-8").split("\n\n", 1)[-1].strip()
    with tarfile.open(dist / art["sdist"]["name"]) as t:
        rd = {rel: t.extractfile(f"yuclaw-{version}/{rel}").read() for rel in ("README.md", "README_PYPI.md")}
    return {"sdist_README_md_is_the_commits": rd["README.md"] == (src / "README.md").read_bytes(), "sdist_README_PYPI_md_is_the_commits": rd["README_PYPI.md"] == (src / "README_PYPI.md").read_bytes(),
            "wheel_long_description_is_README_PYPI_md": wheel_desc == pypi, "readme_sha256": sha(src / "README.md"), "replay_bundle_sha256": sha(src / "docs" / "replay" / "lab_replay_bundle.json"),
            "corpus_snapshot_sha256": sha(src / "v3" / "evidence" / "corpus_snapshot.json.gz")}


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
        art["source_documents"] = source_documents(src, out, dist, art)
        write_identity(dist, art, label="PRELIMINARY development build")
        return art
    finally:
        run(["git", "worktree", "remove", "--force", src], cwd=_REPO, check=False)


def write_identity(dist: Path, art: dict, *, label: str) -> Path:
    """The artifact identity record next to the pair: what any later consumer (this tool with --artifacts, the publisher's
    adopt stage) verifies before trusting the bytes."""
    rec = {"record": "yuclaw-artifact-identity/1", "label": label, "version": art["version"], "commit": art["commit"], "tree": art["tree"],
           "wheel": {"name": art["wheel"]["name"], "sha256": art["wheel"]["sha256"], "size": art["wheel"]["size"]}, "sdist": {"name": art["sdist"]["name"], "sha256": art["sdist"]["sha256"], "size": art["sdist"]["size"]},
           "build_utc": art["build_utc"], "source_date_epoch": art["source_date_epoch"], "build_tools": art["build_tools"]}
    p = dist / "artifact_identity.json"; p.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n"); return p


def adopt(commit: str, artifacts_dir: Path, out: Path) -> dict:
    """Adopt an already-built pair: the identity record must name this commit and its tree, and every file must match the
    recorded name, sha256 and size. Mismatched identity or bytes → STOP (nothing is installed from them)."""
    idp = artifacts_dir / "artifact_identity.json"
    if not idp.is_file():
        raise SystemExit(f"STOP: {idp} missing — an adopted pair needs its identity record")
    rec = json.loads(idp.read_text())
    if rec.get("record") != "yuclaw-artifact-identity/1":
        raise SystemExit("STOP: unknown artifact identity record format")
    tree = run(["git", "rev-parse", f"{commit}^{{tree}}"], cwd=_REPO).stdout.strip()
    if rec.get("commit") != commit or rec.get("tree") != tree:
        raise SystemExit(f"STOP: identity record binds commit {str(rec.get('commit'))[:12]}/tree {str(rec.get('tree'))[:12]}, not the requested {commit[:12]}/{tree[:12]}")
    dist = out / "dist"; dist.mkdir(parents=True, exist_ok=True)
    art = {"commit": commit, "tree": tree, "version": rec["version"], "build_utc": rec.get("build_utc"), "source_date_epoch": rec.get("source_date_epoch"), "build_tools": rec.get("build_tools"), "adopted_from": str(artifacts_dir), "adopted_identity_label": rec.get("label")}
    blobs = {}
    for kind in ("wheel", "sdist"):                                                             # verify EVERY file before copying or opening anything
        want = rec[kind]; p = artifacts_dir / want["name"]
        if not p.is_file():
            raise SystemExit(f"STOP: adopted {kind} {want['name']} missing")
        data = p.read_bytes(); h = hashlib.sha256(data).hexdigest()
        if h != want["sha256"] or len(data) != want["size"]:
            raise SystemExit(f"STOP: adopted {kind} bytes differ from the identity record (sha256 {h[:12]}… / {len(data)} B vs {want['sha256'][:12]}… / {want['size']} B)")
        blobs[kind] = (data, h)
    for kind in ("wheel", "sdist"):
        want = rec[kind]; data, h = blobs[kind]
        (dist / want["name"]).write_bytes(data)
        if kind == "wheel":
            with zipfile.ZipFile(dist / want["name"]) as z:
                names = z.namelist(); meta = z.read(f"yuclaw-{rec['version']}.dist-info/METADATA").decode("utf-8")
            art["wheel"] = {"name": want["name"], "sha256": h, "size": len(data), "inspection": inspect_members("wheel", names), "long_description": long_description_ok(meta)}
        else:
            with tarfile.open(dist / want["name"]) as t:
                names = [n.split("/", 1)[1] for n in t.getnames() if "/" in n]; pkg = t.extractfile(f"yuclaw-{rec['version']}/PKG-INFO").read().decode("utf-8")
            art["sdist"] = {"name": want["name"], "sha256": h, "size": len(data), "inspection": inspect_members("sdist", names), "long_description": long_description_ok(pkg)}
    src = out / "src-identity"
    run(["git", "worktree", "add", "--detach", src, commit], cwd=_REPO)
    try:
        art["source_resource_identity"] = {"schema": sha(src / "schemas" / "CommitmentClaim.v1.json") == sha(src / "v8" / "workbench" / "resources" / "CommitmentClaim.v1.json"),
                                          "fixtures": all(sha(f) == sha(src / "v8" / "workbench" / "resources" / "fixtures" / f.name) for f in (src / "tests" / "fixtures" / "v8" / "commitments").glob("*.json"))}
        art["source_hashes"] = {"schema": sha(src / "schemas" / "CommitmentClaim.v1.json"), "fixtures": {f.name: sha(f) for f in sorted((src / "tests" / "fixtures" / "v8" / "commitments").glob("*.json"))}}
        art["source_documents"] = source_documents(src, out, dist, art)
    finally:
        run(["git", "worktree", "remove", "--force", src], cwd=_REPO, check=False)
    write_identity(dist, art, label=f"ADOPTED (from {rec.get('label', 'unlabelled')}; bytes verified against the identity record)")
    return art


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
    # the EXACT README transcript comparison of the release publisher, against THIS installed artifact and the commit's own bundle
    sys.path.insert(0, str(Path(__file__).resolve().parent)) if str(Path(__file__).resolve().parent) not in sys.path else None
    import cli_transcript
    keep = out / "source-files"; t = cli_transcript.examine((keep / "README.md").read_text(encoding="utf-8"), str(v / "bin" / "yuclaw"), art["wheel"]["name"], keep, python=py)
    snap = t.get("snapshot") or {}
    res["checks"]["readme_transcript_exact"] = t["byte_exact"] is True                                   # byte for byte; nothing ignored or normalized
    res["checks"]["transcript_answers_come_from_the_bundled_snapshot"] = t.get("answers_from_bundled_snapshot") is True and snap.get("passports_state_this_snapshot") is True
    res["checks"]["installed_corpus_snapshot_is_the_commits"] = snap.get("is_the_commits_file") is True and snap.get("sha256") == art["source_documents"]["corpus_snapshot_sha256"]
    t["reason"] = t.get("reason", "")[:400]; res["readme_transcript"] = t
    res["checks"]["packaged_documents_are_the_commits"] = all(v_ is True for k_, v_ in art["source_documents"].items() if k_.startswith(("sdist_", "wheel_")))
    # 8.0.1 C05/C10: the delegated entry and the installed selftest, from THIS installation (no PYTHONPATH, outside the checkout); --require-isolation: a missing backend FAILS here, never skips
    exe = str(v / "bin" / "yuclaw"); wsdir = out / f"run-{what}" / "documented-route"
    h = run([exe, "workbench", "--help"], cwd=cwd, env=env, check=False); flat = " ".join(h.stdout.split())
    res["checks"]["yuclaw_workbench_help_names_the_four_modules"] = h.returncode == 0 and all(n in flat for n in ("usage: yuclaw workbench", "SHD Distillation Shield", "EVO Evolution Evidence Audit", "COM Research Commons Guard", "PRC Independent Practice", "127.0.0.1"))
    g1, g2 = run([exe, "workbench", "guide"], cwd=cwd, env=env, check=False), run([py, "-m", "v8.workbench", "guide"], cwd=cwd, env=env, check=False)
    res["checks"]["delegated_entry_equals_the_module_form"] = g1.returncode == 0 == g2.returncode and g1.stdout == g2.stdout and "yuclaw workbench" in g1.stdout
    st = {}
    for form, cmd in (("yuclaw workbench selftest", [exe, "workbench", "selftest", "--json", "--require-isolation"]), ("python -m v8.workbench selftest", [py, "-m", "v8.workbench", "selftest", "--json", "--require-isolation"])):
        r = run(cmd, cwd=cwd, env=env, check=False, timeout=900)
        try:
            j = json.loads(r.stdout)
        except ValueError:
            j = {"result": "NO_JSON", "checks": [], "isolation": {}, "stderr_tail": r.stderr[-300:]}
        st[form] = {"rc": r.returncode, "result": j.get("result"), "checks": len(j.get("checks", [])), "failed": [c["name"] for c in j.get("checks", []) if not c.get("ok")], "isolation": j.get("isolation")}
    res["selftest"] = st
    res["checks"]["installed_selftest_passes_in_both_entry_forms_with_isolation_required"] = all(x["rc"] == 0 and x["result"] == "PASS" and x["checks"] >= 15 and (x["isolation"] or {}).get("backend") for x in st.values())
    r1 = run([exe, "workbench", "principals", "init", "--workspace", wsdir, "--id", "owner"], cwd=cwd, env=env, check=False); r2 = run([exe, "workbench", "modules", "--workspace", wsdir], cwd=cwd, env=env, check=False)
    r3 = run([exe, "workbench", "status", "--workspace", wsdir], cwd=cwd, env=env, check=False)
    res["checks"]["documented_route_commands_run"] = r1.returncode == 0 and r2.returncode == 0 and r3.returncode == 0 and wsdir.is_dir()
    shutil.rmtree(wsdir, ignore_errors=True)                                                # a throwaway fictional workspace: its one-time credential is never kept
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
    # V8-014: the integrated SHD → COM → PRC + EVO + fresh-verification journey from the INSTALLED artifact (separate signed-in principals; real restricted worker)
    mout = out / f"journey-{what}-modules"
    r = run([py, "-m", "v8.workbench.modules.journey_modules", "--out", mout, "--candidate", art["commit"], "--artifact", f"{artifact.name}={art[what]['sha256']}"], cwd=cwd, env=env, check=False, timeout=1800)
    mlog = json.loads((mout / "modules_journey_log.json").read_text()) if (mout / "modules_journey_log.json").exists() else {}
    sc = mlog.get("scorecard", {}); mod_dir = str(mlog.get("runtime", {}).get("workbench_module", ""))
    journeys["modules"] = {"rc": r.returncode, "score": sc.get("score"), "assertions": sc.get("assertions"), "negative_assertions": sc.get("negative_assertions"), "isolation_backend": (mlog.get("isolation") or {}).get("backend"),
                           "isolation_probes": (mlog.get("isolation") or {}).get("probes"), "module_inside_venv": mod_dir.startswith(str(v)), "journey_log_sha256": sha(mout / "modules_journey_log.json") if mlog else None,
                           "failed_assertions": [a["name"] for s in (mlog.get("steps") or {}).values() for a in s["assertions"] if not a["ok"]], "stderr_tail": r.stderr[-400:] if r.returncode else ""}
    journeys["modules"]["ok"] = r.returncode == 0 and sc.get("score") == "6/6" and journeys["modules"]["module_inside_venv"] and bool(journeys["modules"]["isolation_backend"])
    res["journeys"] = journeys
    res["ok"] = all(res["checks"].values()) and all(j["ok"] for j in journeys.values())
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--commit", required=True); ap.add_argument("--out", required=True); ap.add_argument("--sources", help="ingestion records for the real-source replay (mchp mode)")
    ap.add_argument("--twine", help="twine executable for `twine check` over the built artifacts (default: the first on PATH)")
    ap.add_argument("--playwright-spec", default="playwright", help="pip requirement for the test-time browser driver (pin it to the version whose browsers are cached)")
    ap.add_argument("--artifacts", help="adopt an already-built wheel/sdist pair from this directory (needs its artifact_identity.json); no build")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    commit = run(["git", "rev-parse", "--verify", a.commit + "^{commit}"], cwd=_REPO).stdout.strip()
    rec = {"record": "v8-clean-install/1", "recorded_utc": now(), "commit": commit, "python": sys.version.split()[0], "not_advice": "Research and education only. Not investment advice."}
    art = adopt(commit, Path(a.artifacts).resolve(), out) if a.artifacts else build(commit, out); rec["build"] = art; rec["mode"] = "ADOPTED_PAIR" if a.artifacts else "PRELIMINARY_BUILD"
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
        scores = ", ".join(f"{m}: {j.get('score')}" for m, j in v.get("journeys", {}).items())
        stop_note = (" STOP " + v["stop"][:200]) if v.get("stop") else ""
        print(f"  {what}: ok={v.get('ok')} journeys={{{scores}}}{stop_note}")
        for form, x in (v.get("selftest") or {}).items():
            print(f"    selftest [{form}]: rc={x['rc']} {x['result']} {x['checks']} checks, failed={x['failed']} isolation={(x['isolation'] or {}).get('backend')}")
        t = v.get("readme_transcript") or {}
        if t:
            snap = t.get("snapshot") or {}
            print(f"    transcript: byte_exact={t.get('byte_exact')} mode={t.get('mode')} snapshot sha256={snap.get('sha256')} generated={snap.get('generated')} is_the_commits={snap.get('is_the_commits_file')}")
            print("    commands: " + "; ".join(f"{c['command'].split()[0]} exit {c['exit']}" + (f" ({c['corpus_mode']})" if "corpus_mode" in c else "") for c in t.get("commands", [])))
            if not t.get("byte_exact"):
                print(f"    {t.get('reason')}")
                for label in ("expected", "actual"):
                    print(f"    {label} from line {t.get('excerpt_starts_at_line')}:"); print("\n".join("      " + x for x in t.get(label, [])))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
