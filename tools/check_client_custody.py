#!/usr/bin/env python3
"""
Client-custody check — the machine keeps the data-handling promise.

The client-data one-pager promises: client work lives box-local in
gitignored directories and never enters git or any backup. This check makes
that promise falsifiable:

  K1 gitignore  — every client path is ignored by git (git check-ignore)
  K2 git index  — no client-marker file is tracked in the repo
  K3 backups    — no client-marker path exists under any backup root
                  (~/ *backup* directories, present or future)
  K4 jobs       — no cron/service script copies the repo or output/ tree
                  with rsync/tar/cp without excluding client paths

Exit 0 = promise kept; exit 1 = violation (message says exactly where).
--selftest plants a marker in a throwaway fake backup root and asserts K3
detects it, proving the check can actually fail.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
HOME = Path.home()

CLIENT_DIRS = ("output/byos_dryrun", "internal")
# Data markers only — tools/yuclaw_byos_dryrun.py is committed infrastructure
# and must NOT trip the check; what may never leak is client DATA:
CLIENT_DIR_MARKERS = ("byos_dryrun", "legal_drafts")   # directory names
CLIENT_FILE_MARKERS = ("registry_client.jsonl", "CLIENT_MEMO",
                       "client_input.csv", "client_signals.csv",
                       "client_deliverable")


def backup_roots():
    return [p for p in HOME.glob("*backup*") if p.is_dir()]


def scan_backups(roots) -> list[str]:
    hits = []
    for root in roots:
        for marker in CLIENT_DIR_MARKERS:
            hits += [str(h) for h in root.rglob(marker) if h.is_dir()]
        for marker in CLIENT_FILE_MARKERS:
            hits += [str(h) for h in root.rglob(f"{marker}*") if h.is_file()]
        if len(hits) > 20:
            return hits[:20]
    return hits


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    problems = []

    if "--selftest" in args:
        with tempfile.TemporaryDirectory(prefix="fake_backup_") as td:
            fake = Path(td) / "yuclaw_backup_fake"
            (fake / "output" / "byos_dryrun").mkdir(parents=True)
            (fake / "output" / "byos_dryrun" / "CLIENT_MEMO.md").write_text("x")
            hits = scan_backups([fake])
            assert hits, "selftest: planted client marker was NOT detected"
        print("[custody] SELFTEST OK — planted client marker detected in a "
              "fake backup root")
        return 0

    # K1 + K2
    for d in CLIENT_DIRS:
        rc = subprocess.run(["git", "check-ignore", "-q", d + "/x"],
                            cwd=_REPO).returncode
        if rc != 0:
            problems.append(f"K1: {d}/ is NOT gitignored")
    tracked = subprocess.run(["git", "ls-files"], cwd=_REPO,
                             capture_output=True, text=True).stdout.splitlines()
    for path in tracked:
        if any(path.startswith(d + "/") for d in CLIENT_DIRS) or \
                any(m in path.rsplit("/", 1)[-1] for m in CLIENT_FILE_MARKERS):
            problems.append(f"K2: client data path tracked in git: {path}")

    # K3
    roots = backup_roots()
    hits = scan_backups(roots)
    for h in hits:
        problems.append(f"K3: client path inside a backup root: {h}")

    # K4 — heuristic: repo-tree copy commands in scheduled scripts
    script_dirs = [_REPO / "cron", _REPO / "services", _REPO / "engines"]
    for sd in script_dirs:
        if not sd.exists():
            continue
        for sh in sd.glob("*.sh"):
            text = sh.read_text(errors="replace")
            for ln in text.splitlines():
                l = ln.strip()
                if l.startswith("#"):
                    continue
                if any(cmd in l for cmd in ("rsync ", "tar c", "tar -c",
                                            "cp -r", "cp -a")) and \
                        ("yuclaw" in l or "output" in l) and \
                        "byos" not in l and "--exclude" not in l:
                    problems.append(f"K4: {sh.name}: repo/output copy without "
                                    f"client exclusion: {l[:100]}")

    if problems:
        print("CUSTODY VIOLATION — the data-handling promise is broken:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(f"[custody] OK — {len(roots)} backup root(s) scanned "
          f"({', '.join(r.name for r in roots) or 'none'}); client paths "
          "gitignored, untracked, absent from all backups; no unexcluded "
          "copy jobs in scheduled scripts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
