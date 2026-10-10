#!/usr/bin/env python3
"""Record the v9 candidate's evidence as a scorecard the 9.x notes composer reads (v9/V9-NNN/scorecard.json): the v9 test
files on the current interpreter and, when given, on a second runtime (the declared minimum), the installed self-check,
the newest browser inspection record and, when present, a clean-install record. Counts come from pytest's own summary
lines, never typed. Nothing here claims more than the runs it executed.

  python3 tools/yuclaw_v9_scorecard.py --out v9/V9-002 [--python-floor /path/to/python3.10] [--clean-install DIR]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
TESTS = ("tests/test_v9_brief_engine.py", "tests/test_v9_brief_web.py", "tests/test_v9_brief_packaging.py", "tests/test_release_notes_v9.py")


def _run(cmd, cwd=REPO, timeout=1800):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env={**__import__("os").environ, "PYTHONPATH": str(REPO)})
    return p.returncode, p.stdout + p.stderr


def pytest_run(python: str) -> dict:
    rc, out = _run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *[t for t in TESTS if (REPO / t).exists()]])
    m = re.search(r"(\d+) passed", out); f = re.search(r"(\d+) failed", out); e = re.search(r"(\d+) error", out)
    passed = int(m.group(1)) if m else 0; failed = (int(f.group(1)) if f else 0) + (int(e.group(1)) if e else 0)
    ver = _run([python, "-c", "import sys;print(sys.version.split()[0])"])[1].strip()
    return {"python": ver, "passed": passed, "failed": failed, "total": passed + failed, "result": "PASS" if rc == 0 and failed == 0 and passed > 0 else "FAIL", "exit": rc}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--python-floor", default=None); ap.add_argument("--clean-install", default=None); a = ap.parse_args(argv)
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    commit = _run(["git", "rev-parse", "HEAD"])[1].strip(); dirty = bool(_run(["git", "status", "--porcelain", "--untracked-files=no"])[1].strip())
    runs = {"current": pytest_run(sys.executable)}
    if a.python_floor:
        runs["floor"] = pytest_run(a.python_floor)
    rc, so = _run([sys.executable, "-m", "v9.brief", "selftest", "--json"]); selftest = json.loads(so[so.index("{"):]) if "{" in so else {"result": "FAIL"}
    ui = None
    for d in sorted((REPO / "v9").glob("V9-[0-9][0-9][0-9]")):
        if (d / "ui_inspection.json").exists():
            ui = json.loads((d / "ui_inspection.json").read_text()); ui_dir = d.name
    clean = None
    if a.clean_install and (pathlib.Path(a.clean_install) / "packaging.json").exists():
        clean = json.loads((pathlib.Path(a.clean_install) / "packaging.json").read_text())
    card = {"record": "yuclaw-v9-scorecard/1", "candidate": commit, "worktree_dirty": dirty, "recorded_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "tests": list(TESTS),
            "runs": runs, "selftest": selftest.get("result"), "selftest_checks": f"{selftest.get('passed')}/{selftest.get('total')}",
            "ui_inspection": (ui or {}).get("result", "NOT RUN"), "ui_inspection_record": (ui_dir if ui else None),
            "clean_install": (clean or {}).get("result") or ("recorded" if clean else "NOT RUN"), "clean_install_record": a.clean_install,
            "meaning": "counts are pytest's own; PASS means the named runs passed on this candidate; nothing about benefit, review or release authorization"}
    (out / "scorecard.json").write_text(json.dumps(card, indent=1) + "\n")
    print(json.dumps({k: card[k] for k in ("candidate", "runs", "selftest", "ui_inspection", "clean_install")}, indent=1))
    return 0 if all(r["result"] == "PASS" for r in runs.values()) and card["selftest"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
