#!/usr/bin/env python3
"""
README first-touch transcript (ORDER 2026-09-05B B3) — GENERATED from the
release-candidate wheel and embedded in README.md between the fixed markers
<!-- CLI-TRANSCRIPT BEGIN --> / <!-- CLI-TRANSCRIPT END -->; regenerated
every release. Records, per command: the command line, the exit code, and
the head of stdout/stderr (JSON passports trimmed to their status block).

Usage:
  python3 tools/cli_transcript.py --exe /path/to/rc-venv/bin/yuclaw --wheel yuclaw-6.0.1-py3-none-any.whl [--write]
  python3 tools/cli_transcript.py --check          # README block carries the current package version
  python3 tools/cli_transcript.py --check --exe /path/to/rc-venv/bin/yuclaw --wheel yuclaw-8.0.0-py3-none-any.whl
                                                   # EXACT: the block equals a fresh transcript of that artifact, byte for byte

Never typed by hand: the release gate (tools/check_release_manifest.py G2)
asserts the block's recorded `yuclaw <version>` equals the package version.

The version-only check cannot see a STALE transcript: the `replay-lab` section depends on
docs/replay/lab_replay_bundle.json, which every production refresh rewrites, so after a merge of main the block can
be out of date with its version line unchanged (this stopped the 8.0.0 release at the publisher's exact comparison on
2026-09-21). `--check --exe` is that same exact comparison, available BEFORE the release: the clean-install tool
(and therefore hosted CI) runs it against each freshly installed artifact. `--check` alone is unchanged, because on
main the bundle moves every weekday while the transcript is a release-time record.

ONE transcript environment. `check-claim` normally asks a research node first and answers from the snapshot bundled
in the wheel only when none is reachable; the two passports differ (the snapshot answer carries the `corpus` scope
block), so a transcript of the DEFAULT invocation depends on the host — the first hosted run of the exact comparison
failed on exactly that (2026-09-21: recorded on a research node, replayed on a runner without one). Every command of
the transcript therefore runs with YUCLAW_CORPUS=snapshot (v3/cli/check_claim.py): the bundled snapshot only, no
research node looked for, whatever database settings the host carries. build() sets it itself, so generation, the
clean-install check, hosted CI and the release publisher (which calls build()) use the same mechanism, and the
comparison stays byte for byte everywhere. Nothing here claims that the default invocation prints the same on every
host. examine() also confirms where the data came from: each passport says `corpus.mode = offline_snapshot`, and the
snapshot file inside the installed artifact is identified by sha256 and compared with the candidate commit's file.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
BEGIN, END = "<!-- CLI-TRANSCRIPT BEGIN -->", "<!-- CLI-TRANSCRIPT END -->"
UNIQUE = "0001045810-26-000019"
CORPUS_ENV, CORPUS_MODE = "YUCLAW_CORPUS", "snapshot"        # the ONE transcript environment (see the module docstring)
SNAPSHOT_FILE = "v3/evidence/corpus_snapshot.json.gz"
COMMANDS = [
    ["--version"],
    ["--help"],
    ["check-claim", "--text", "NVDA reported an insider sale in May 2026"],
    ["check-claim", "--ticker", "NVDA", "--accession", UNIQUE],
    ["check-claim", "--accession", UNIQUE],
    ["replay-lab", "docs/replay/lab_replay_bundle.json"],
]


def _trim(out: str, max_lines: int = 14) -> str:
    out = out.rstrip("\n")
    if out.startswith("{"):
        try:
            d = json.loads(out)
            keep = {k: d[k] for k in ("status", "claim_as_parsed", "misses") if k in d}
            keep["matched_evidence"] = f"<{len(d.get('matched_evidence', []))} object(s)>"
            if isinstance(d.get("corpus"), dict):                       # the passport's own statement of its source — never inferred from the field count
                keep["corpus"] = {k: d["corpus"].get(k) for k in ("mode", "snapshot_generated")}
            keep["..."] = f"<{len(d)} fields total; not_advice line present: {'not_advice' in d}>"
            return json.dumps(keep, indent=1)
        except ValueError:
            pass
    lines = out.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(out.splitlines()) - max_lines} more lines)"]
    return "\n".join(lines)


def recorded_block(readme_text: str) -> str | None:
    m = re.search(re.escape(BEGIN) + r"\n(.*?)\n" + re.escape(END), readme_text, re.S)
    return m.group(1) if m else None


def transcript_env() -> dict:
    env = dict(os.environ); env[CORPUS_ENV] = CORPUS_MODE
    return env


def run_commands(exe: str, repo: Path | None = None) -> list[dict]:
    """Every transcript command against `exe`, in the ONE transcript environment: argv as shown, exit status, trimmed body, and —
    for a JSON passport — the source the passport itself states."""
    repo = Path(repo) if repo else _REPO
    cwd = str(Path.home())          # stranger conditions: never the checkout
    out = []
    for cmd in COMMANDS:
        r = subprocess.run([exe] + [c if not c.startswith("docs/") else str(repo / c) for c in cmd],
                           capture_output=True, text=True, timeout=900, cwd=cwd, env=transcript_env())
        rec = {"shown": " ".join(f'"{c}"' if " " in c else c for c in cmd), "exit": r.returncode,
               "body": _trim(r.stdout) if r.stdout.strip() else _trim(r.stderr)}
        if cmd[0] == "check-claim":
            try:
                d = json.loads(r.stdout)
                rec["corpus"] = d.get("corpus") if isinstance(d, dict) else None
            except ValueError:
                rec["corpus"] = None
        out.append(rec)
    return out


def render(exe: str, wheel: str, records: list[dict]) -> str:
    ver = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=120, cwd=str(Path.home()), env=transcript_env()).stdout.strip()
    pyv = ".".join(platform.python_version_tuple()[:2])
    parts = [f"Transcript produced from the release-candidate wheel `{wheel}` "
             f"({ver}, Python {pyv}) "
             f"by `tools/cli_transcript.py`; the `replay-lab` run uses the documented local-bundle path. "
             f"Every command ran with `{CORPUS_ENV}={CORPUS_MODE}`: `check-claim` answers from the corpus snapshot bundled in the wheel and never looks for a research node "
             f"(without that setting, a host that reaches a research node answers from it and its passport has no `corpus` block). "
             f"No date: release verification compares this block byte-for-byte with a fresh transcript of the final artifact, made the same way.", ""]
    for rec in records:
        parts += ["```text", f"$ yuclaw {rec['shown']}", rec["body"], f"[exit {rec['exit']}]", "```"]
    return "\n".join(parts)


def build(exe: str, wheel: str, repo: Path | None = None) -> str:
    return render(exe, wheel, run_commands(exe, repo))


def snapshot_identity(python: str | None) -> dict | None:
    """The corpus snapshot INSIDE the installation `python` belongs to: path, sha256, generated stamp, size. None when there is no
    interpreter to ask (a stand-in executable in a unit test)."""
    if not python or not Path(python).exists():
        return None
    code = ("import hashlib, json; from v3.evidence import snapshot as s; snap = s.load_snapshot() or {}; b = s.SNAPSHOT_PATH.read_bytes(); "
            "print(json.dumps({'path': str(s.SNAPSHOT_PATH), 'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b), 'generated': snap.get('generated'), "
            "'names': len(snap.get('names', {})), 'objects': sum(len(v) for v in snap.get('names', {}).values())}))")
    env = transcript_env(); env.pop("PYTHONPATH", None)
    r = subprocess.run([python, "-c", code], capture_output=True, text=True, timeout=300, cwd=str(Path.home()), env=env)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"error": (r.stderr or r.stdout)[-300:]}


def examine(readme_text: str, exe: str, wheel: str, repo: Path | None = None, python: str | None = None) -> dict:
    """The canonical comparison (the one the release publisher makes): the README's recorded block against a FRESH transcript of
    `exe`, byte for byte — plus what a failure needs to be understood: the transcript mode, each command's exit status and stated
    source, the snapshot's identity, the first differing line and a bounded expected/actual excerpt. Nothing is ignored or normalized."""
    repo_p = Path(repo) if repo else _REPO
    res: dict = {"ok": False, "mode": f"{CORPUS_ENV}={CORPUS_MODE}", "byte_exact": False}
    recorded = recorded_block(readme_text)
    if recorded is None:
        res["reason"] = "README carries no CLI-TRANSCRIPT block"
        return res
    records = run_commands(exe, repo_p); fresh = render(exe, wheel, records)
    res["commands"] = [{"command": r["shown"], "exit": r["exit"], **({"corpus_mode": (r["corpus"] or {}).get("mode"), "snapshot_generated": (r["corpus"] or {}).get("snapshot_generated")}
                                                                       if "corpus" in r else {})} for r in records]
    claims = [r for r in records if "corpus" in r]
    res["answers_from_bundled_snapshot"] = bool(claims) and all((r["corpus"] or {}).get("mode") == "offline_snapshot" for r in claims)
    python = python or (str(Path(exe).parent / "python") if (Path(exe).parent / "python").exists() else None)
    ident = snapshot_identity(python); res["snapshot"] = ident
    if ident and "sha256" in ident:
        src = repo_p / SNAPSHOT_FILE
        if src.exists():
            import hashlib
            ident["commit_file_sha256"] = hashlib.sha256(src.read_bytes()).hexdigest(); ident["is_the_commits_file"] = ident["commit_file_sha256"] == ident["sha256"]
        ident["passports_state_this_snapshot"] = bool(claims) and all((r["corpus"] or {}).get("snapshot_generated") == ident.get("generated") for r in claims)
    res["byte_exact"] = recorded == fresh
    if res["byte_exact"]:
        res["ok"] = True
        res["reason"] = f"README transcript equals a fresh transcript of {wheel or Path(exe).name} ({len(fresh)} bytes)"
        return res
    a, b = recorded.splitlines(), fresh.splitlines()
    first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    res["first_differing_line"] = first + 1
    lo = max(0, first - 2)
    res["expected"] = [x[:160] for x in a[lo:first + 3]]; res["actual"] = [y[:160] for y in b[lo:first + 3]]; res["excerpt_starts_at_line"] = lo + 1
    res["lines"] = {"recorded": len(a), "fresh": len(b), "differing": sum(1 for i in range(max(len(a), len(b))) if i >= len(a) or i >= len(b) or a[i] != b[i])}
    why = "" if res["answers_from_bundled_snapshot"] else f" [this executable did NOT answer check-claim from the bundled snapshot under {CORPUS_ENV}={CORPUS_MODE}]"
    res["reason"] = (f"README transcript block != fresh transcript (first differing line {first + 1}: recorded {a[first][:80] if first < len(a) else '<end>'!r}, "
                     f"fresh {b[first][:80] if first < len(b) else '<end>'!r}){why} — regenerate with --exe … --write and then tools/yuclaw_readme_pypi.py --write")
    return res


def compare(readme_text: str, exe: str, wheel: str, repo: Path | None = None) -> tuple[bool, str]:
    """(equal, reason) of examine(): byte for byte; the reason names the first differing line."""
    r = examine(readme_text, exe, wheel, repo)
    return r["ok"], r["reason"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", help="built `yuclaw` console script (release-candidate venv)")
    ap.add_argument("--wheel", default="", help="wheel filename recorded in the transcript header")
    ap.add_argument("--write", action="store_true", help="write the block into README.md")
    ap.add_argument("--check", action="store_true", help="assert README block version == package version; with --exe: the block equals a fresh transcript of that artifact exactly")
    ap.add_argument("--readme", default=None, help="README to read (default: this repository's README.md)")
    ap.add_argument("--repo", default=None, help="tree whose docs/ the replay-lab run uses (default: this repository)")
    a = ap.parse_args(argv)
    readme = Path(a.readme) if a.readme else _REPO / "README.md"
    text = readme.read_text(encoding="utf-8")
    if a.check and a.exe:
        r = examine(text, a.exe, a.wheel or Path(a.exe).name, Path(a.repo) if a.repo else None)
        print(f"[cli-transcript] {'OK' if r['ok'] else 'RED'} — {r['reason']}")
        print(f"[cli-transcript] mode {r['mode']}; commands: " + "; ".join(f"{c['command'].split()[0]} exit {c['exit']}" + (f" ({c['corpus_mode']})" if "corpus_mode" in c else "") for c in r.get("commands", [])))
        if r.get("snapshot"):
            print(f"[cli-transcript] snapshot inside the installation: {json.dumps(r['snapshot'], sort_keys=True)}")
        if not r["ok"] and "expected" in r:
            print(f"[cli-transcript] from line {r['excerpt_starts_at_line']} — expected (README):"); print("\n".join("    " + x for x in r["expected"]))
            print("[cli-transcript] actual (fresh):"); print("\n".join("    " + x for x in r["actual"]))
        return 0 if r["ok"] else 1
    if a.check:
        pv = re.search(r'^version = "([^"]+)"', (_REPO / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)   # no tomllib: Python 3.10 minimum
        m = re.search(re.escape(BEGIN) + r"\n(.*?)\n" + re.escape(END), text, re.S)
        if not m or f"yuclaw {pv}" not in m.group(1) or "pending" in m.group(1).lower():
            print(f"[cli-transcript] RED — README transcript block missing, pending, or not at {pv}")
            return 1
        print(f"[cli-transcript] OK — README transcript recorded at yuclaw {pv}")
        return 0
    if not a.exe:
        ap.error("--exe is required unless --check")
    block = build(a.exe, a.wheel or Path(a.exe).name, Path(a.repo) if a.repo else None)
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("README.md must carry exactly one CLI-TRANSCRIPT BEGIN/END marker pair")
    new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _m: f"{BEGIN}\n{block}\n{END}", text, flags=re.S)
    if a.write:
        readme.write_text(new, encoding="utf-8")
        print(f"[cli-transcript] wrote README block ({len(block)} bytes) from {a.exe}")
    else:
        print(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
