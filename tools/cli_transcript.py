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
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
BEGIN, END = "<!-- CLI-TRANSCRIPT BEGIN -->", "<!-- CLI-TRANSCRIPT END -->"
UNIQUE = "0001045810-26-000019"
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


def compare(readme_text: str, exe: str, wheel: str, repo: Path | None = None) -> tuple[bool, str]:
    """The canonical comparison (the one the release publisher makes): the README's recorded block against a FRESH transcript of
    `exe`, byte for byte. Returns (equal, reason); the reason names the first differing line."""
    recorded = recorded_block(readme_text)
    if recorded is None:
        return False, "README carries no CLI-TRANSCRIPT block"
    fresh = build(exe, wheel, repo)
    if recorded == fresh:
        return True, f"README transcript equals a fresh transcript of {wheel or Path(exe).name} ({len(fresh)} bytes)"
    a, b = recorded.splitlines(), fresh.splitlines()
    first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return False, (f"README transcript block != fresh transcript (first differing line {first + 1}: recorded {a[first][:80] if first < len(a) else '<end>'!r}, "
                   f"fresh {b[first][:80] if first < len(b) else '<end>'!r}) — regenerate with --exe … --write and then tools/yuclaw_readme_pypi.py --write")


def build(exe: str, wheel: str, repo: Path | None = None) -> str:
    repo = Path(repo) if repo else _REPO
    cwd = str(Path.home())          # stranger conditions: never the checkout
    ver = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=120, cwd=cwd).stdout.strip()
    pyv = ".".join(platform.python_version_tuple()[:2])
    parts = [f"Transcript produced from the release-candidate wheel `{wheel}` "
             f"({ver}, Python {pyv}) "
             f"by `tools/cli_transcript.py`; the `replay-lab` run uses the documented local-bundle path. "
             f"No date: release verification compares this block byte-for-byte with a fresh transcript of the final artifact.", ""]
    for cmd in COMMANDS:
        shown = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        r = subprocess.run([exe] + [c if not c.startswith("docs/") else str(repo / c) for c in cmd],
                           capture_output=True, text=True, timeout=900, cwd=cwd)
        body = _trim(r.stdout) if r.stdout.strip() else _trim(r.stderr)
        parts.append("```text")
        parts.append(f"$ yuclaw {shown}")
        parts.append(body)
        parts.append(f"[exit {r.returncode}]")
        parts.append("```")
    return "\n".join(parts)


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
        ok, why = compare(text, a.exe, a.wheel or Path(a.exe).name, Path(a.repo) if a.repo else None)
        print(f"[cli-transcript] {'OK' if ok else 'RED'} — {why}")
        return 0 if ok else 1
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
