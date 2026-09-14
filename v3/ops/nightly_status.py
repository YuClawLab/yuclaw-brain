"""Nightly status adapter (v7 candidate; NOT activated).

Reads the existing pipeline log (cron/refresh_v3_pages.sh output) and the launcher's own `|| exit N`
table as TEXT, and reports per run: start stamp, last successful stage, first failing gate with its
exit code, whether the run pushed, whether deploy-verify completed, plus (optionally) the Pages build
state through an injected reader. It never changes the nightly's exit status, never re-renders, and a
delivery failure of the report is reported as DELIVERY_FAILED — never as job success.

Activation (heartbeat delivery) needs a scoped order; this module only computes and formats."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
LAUNCHER = _REPO / "cron" / "refresh_v3_pages.sh"
RE_PUSHED = re.compile(r"\[refresh_v3_pages\] pushed at (\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC)")
RE_DEPLOYED = re.compile(r"\[refresh_v3_pages\] deploy-verified at (\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC)")
RE_LANDING = re.compile(r"\[render_landing\] wrote ")
RE_FAIL = re.compile(r"^\s*FAIL |\] FAIL\b|FAILED|\] RED\b")
RE_GATE_TAG = re.compile(r"^\[([a-z0-9_-]+)\]")


def exit_table(launcher_text: str) -> dict[str, int]:
    """Map each launcher command (first token after python3/bash) to its `|| exit N` code."""
    table = {}
    for line in launcher_text.splitlines():
        m = re.search(r"(?:python3|bash)\s+(?:-m\s+)?(\S+).*\|\|\s*exit\s+(\d+)", line)
        if m:
            table[m.group(1)] = int(m.group(2))
    return table


def exit_code_for(gate_tag: str, exits: dict[str, int]) -> int | None:
    """Map a log gate tag (e.g. 'truncation-gate', 'note-gate', 'deploy-verify') to the launcher command's
    exit code by token overlap; a '-gate' tag prefers the check_* command over a producer."""
    head = gate_tag.split("-")[0].lower()
    cands = [(cmd, code) for cmd, code in exits.items() if head in cmd.lower().replace("-", "_")]
    if not cands:
        return None
    if gate_tag.endswith("-gate"):
        checks = [c for c in cands if "check_" in c[0]]
        cands = checks or cands
    return cands[0][1]


@dataclass
class RunStatus:
    start_stamp: str | None = None          # the run's own "pushed at" label is the START stamp when present
    lines: tuple[int, int] = (0, 0)
    last_ok_stage: str | None = None
    first_failure: str | None = None
    failing_gate: str | None = None
    exit_code: int | None = None            # from the launcher's exit table (None = unknown)
    pushed: bool = False
    deploy_verified: bool = False
    deploy_stamp: str | None = None
    state: str = "UNKNOWN"                  # COMPLETED | FAILED | INTERRUPTED | STALE
    build: dict | None = None
    notes: list[str] = field(default_factory=list)


def segment_runs(log_lines: list[str]) -> list[tuple[int, int]]:
    """A run starts at each `[render_landing] wrote` line and ends before the next one."""
    starts = [i for i, l in enumerate(log_lines) if RE_LANDING.search(l)]
    return [(s, (starts[k + 1] if k + 1 < len(starts) else len(log_lines))) for k, s in enumerate(starts)]


def classify_run(log_lines: list[str], seg: tuple[int, int], exits: dict[str, int], *, log_complete: bool = True) -> RunStatus:
    a, b = seg
    st = RunStatus(lines=(a + 1, b)); prev_ok = None
    for i in range(a, b):
        l = log_lines[i]
        m = RE_PUSHED.search(l)
        if m:
            st.pushed = True; st.start_stamp = m.group(1)
        m = RE_DEPLOYED.search(l)
        if m:
            st.deploy_verified = True; st.deploy_stamp = m.group(1)
        tag = RE_GATE_TAG.match(l)
        if tag and not RE_FAIL.search(l) and st.first_failure is None:
            prev_ok = st.last_ok_stage
            st.last_ok_stage = tag.group(1)
        if RE_FAIL.search(l) and st.first_failure is None and "non-fatal" not in l:
            st.first_failure = l.strip()[:200]
            # attribute to the nearest preceding gate tag; the last OK stage is the one before that gate
            for j in range(i, a - 1, -1):
                t = RE_GATE_TAG.match(log_lines[j])
                if t:
                    st.failing_gate = t.group(1)
                    if st.last_ok_stage == st.failing_gate:
                        st.last_ok_stage = prev_ok
                    break
    if st.first_failure and st.failing_gate:
        st.exit_code = exit_code_for(st.failing_gate, exits)
    if st.deploy_verified:
        st.state = "COMPLETED"
    elif st.first_failure:
        st.state = "FAILED"
    elif not log_complete or b == len(log_lines):
        st.state = "INTERRUPTED_OR_RUNNING"
    else:
        st.state = "STALE"
    if st.pushed and not st.deploy_verified and not st.first_failure:
        st.notes.append("pushed but deploy-verify missing: treat as STALE/INTERRUPTED, not success")
    return st


def attach_build(status: RunStatus, builds_reader, commit_sha: str | None) -> RunStatus:
    """builds_reader(commit_sha) → {'status': 'built'|'errored'|'building'|None, ...}; failures stay explicit."""
    try:
        status.build = builds_reader(commit_sha) if commit_sha else {"status": None, "note": "no commit for this run"}
    except Exception as exc:  # noqa: BLE001 — surfaced, never hidden
        status.build = {"status": None, "error": str(exc)[:120]}
    return status


def deliver(report: dict, transport) -> dict:
    """transport(report) → True on delivery. A transport failure never changes the run's state."""
    try:
        ok = bool(transport(report))
    except Exception as exc:  # noqa: BLE001
        ok = False; report = dict(report, delivery_error=str(exc)[:120])
    return dict(report, delivery="DELIVERED" if ok else "DELIVERY_FAILED")


def latest_status(log_path: Path = None, launcher_path: Path = LAUNCHER) -> dict:
    log_lines = Path(log_path).read_text(errors="replace").splitlines()
    exits = exit_table(Path(launcher_path).read_text())
    segs = segment_runs(log_lines)
    if not segs:
        return {"state": "NO_RUN_FOUND"}
    return asdict(classify_run(log_lines, segs[-1], exits))


def launch_identity(launcher_path: Path = LAUNCHER, repo: Path | None = None, start_stamp: str | None = None) -> dict:
    """Identity of the launch: launcher file digest + the commit the run created (found read-only in the repo by
    the run's own 'auto: v3.0 page refresh <stamp>' subject). Missing evidence stays explicit (None), never guessed."""
    out = {"launcher_path": str(launcher_path), "launcher_sha256": None, "run_commit": None, "run_commit_subject": None}
    try:
        out["launcher_sha256"] = hashlib.sha256(Path(launcher_path).read_bytes()).hexdigest()
    except OSError:
        pass
    if repo and start_stamp:
        r = subprocess.run(["git", "--no-optional-locks", "log", "-1", "--format=%H%x00%s", f"--grep=auto: v3.0 page refresh {start_stamp}", "--fixed-strings"], cwd=str(repo), capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            sha, subj = r.stdout.strip().split("\x00", 1); out["run_commit"], out["run_commit_subject"] = sha, subj
    return out


def preview(log_path, launcher_path: Path = LAUNCHER, repo: Path | None = None, builds_reader=None) -> dict:
    """Local preview of the latest nightly run (read-only): identity, start/end, exit/failing gate, push and
    deploy outcome, Pages build through an injected reader (None → not queried). A missing log is NO_LOG, an
    empty one NO_RUN_FOUND; the underlying exit status is preserved in `exit_code`. Nothing is sent."""
    lp = Path(log_path)
    if not lp.exists():
        return {"state": "NO_LOG", "log": str(lp), "delivery": "NOT_ATTEMPTED"}
    st = latest_status(lp, launcher_path)
    if st.get("state") == "NO_RUN_FOUND":
        return {**st, "log": str(lp), "delivery": "NOT_ATTEMPTED"}
    ident = launch_identity(launcher_path, repo, st.get("start_stamp"))
    report = {"identity": ident, "run": st, "log": str(lp), "delivery": "NOT_ATTEMPTED (preview; activation needs the owner's scoped decision)"}
    if builds_reader is not None:
        rs = RunStatus(**{k: v for k, v in st.items() if k in RunStatus.__dataclass_fields__})
        report["run"]["build"] = attach_build(rs, builds_reader, ident.get("run_commit")).build
    else:
        report["run"]["build"] = {"status": None, "note": "Pages build not queried in preview"}
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3 -m v3.ops.nightly_status", description="Nightly status preview (read-only; sends nothing)")
    p.add_argument("--log", default="/tmp/yuclaw_pipeline.log"); p.add_argument("--repo", default=str(_REPO)); p.add_argument("--launcher", default=str(LAUNCHER))
    a = p.parse_args(argv)
    print(json.dumps(preview(a.log, Path(a.launcher), Path(a.repo)), indent=1)); return 0


if __name__ == "__main__":
    sys.exit(main())
