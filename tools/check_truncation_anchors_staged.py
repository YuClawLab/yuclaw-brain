#!/usr/bin/env python3
"""
Staged truncation-anchor guard (V7-003F, 2026-09). READ-ONLY pre-commit check.

Validates the CANDIDATE commit — the ledger blob and the anchored source blobs
in the effective Git index — whenever the staged change touches
registry/truncation_ledger.json or any path anchored by the HEAD ledger or the
candidate ledger. Reuses check_truncation_ledger.validate_entries (rules (a)
schema and (b) drift) on index blobs: exact bytes, sha256, no normalization.

Contract (see V7-003F §3):
  * honors Git's effective index (GIT_INDEX_FILE, repository/worktree context) —
    never the working copy, never a substituted default index;
  * NUL-delimited plumbing, argument arrays only; paths are never evaluated;
  * anchored blobs are data — never executed, imported or written to live paths;
  * triggers on ledger or anchored-path additions, deletions, renames, type
    changes and on any change of the anchored-path set; entry removal, rename
    and type change have NO retirement rule in the ledger and fail specifically;
  * malformed ledger, unresolved merge stages, missing blobs, symlink/gitlink
    anchors, unsafe paths → explicit failure; index/HEAD movement during the
    check → failure (no retry);
  * never edits source, ledger, index or refs; no network, no database.
Exit 0 = pass or not triggered; 1 = findings; 2 = error (fails closed).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from check_truncation_ledger import LEDGER_REL, sha256_bytes, validate_entries  # noqa: E402

TAG = "[anchor-guard]"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
MODE_SYMLINK, MODE_GITLINK = "120000", "160000"


class GuardError(Exception):
    """Environment/plumbing failure — the guard fails closed (exit 2)."""


def _printable(s: str) -> str:
    return s.encode("unicode_escape").decode("ascii")


def _git(*args: str) -> bytes:
    r = subprocess.run(["git", *args], capture_output=True)
    if r.returncode != 0:
        raise GuardError(f"git {' '.join(args[:2])} failed (exit {r.returncode}): "
                         f"{_printable(r.stderr.decode(errors='replace').strip()[:200])}")
    return r.stdout


def _git_rc(*args: str) -> int:
    return subprocess.run(["git", *args], capture_output=True).returncode


def head_commit() -> str | None:
    r = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD^{commit}"], capture_output=True)
    return r.stdout.decode().strip() or None if r.returncode == 0 else None


def index_entries() -> tuple[dict[str, tuple[str, str]], dict[str, list[int]]]:
    """Effective index → ({path: (mode, oid)} for stage 0, {path: [stages]} for unmerged)."""
    out = _git("ls-files", "--stage", "-z")
    stage0: dict[str, tuple[str, str]] = {}
    unmerged: dict[str, list[int]] = {}
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, path = rec.split(b"\t", 1)
        mode, oid, stage = meta.decode().split(" ")
        p = path.decode("utf-8", errors="surrogateescape")
        if stage == "0":
            stage0[p] = (mode, oid)
        else:
            unmerged.setdefault(p, []).append(int(stage))
    return stage0, unmerged


def staged_changes(head: str | None) -> list[tuple[str, str, str | None]]:
    """[(status, path, new_path_for_renames)] between HEAD (or the empty tree) and the index."""
    base = head or EMPTY_TREE
    out = _git("diff-index", "--cached", "-z", "-M", "--name-status", base)
    toks = [t for t in out.split(b"\0")]
    changes, i = [], 0
    while i < len(toks) and toks[i]:
        st = toks[i].decode()
        if st[0] in "RC":
            old, new = toks[i + 1].decode("utf-8", "surrogateescape"), toks[i + 2].decode("utf-8", "surrogateescape")
            changes.append((st[0], old, new)); i += 3
        else:
            changes.append((st[0], toks[i + 1].decode("utf-8", "surrogateescape"), None)); i += 2
    return changes


def blob_bytes(oid: str) -> bytes:
    return _git("cat-file", "blob", oid)


def head_blob(head: str, rel: str) -> bytes | None:
    r = subprocess.run(["git", "cat-file", "blob", f"{head}:{rel}"], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def snapshot() -> str:
    """Identity of (HEAD, effective index) to detect concurrent staging."""
    return sha256_bytes((head_commit() or "").encode() + b"\n" + _git("ls-files", "--stage", "-z"))


def anchor_paths(led: dict) -> set[str]:
    return {a["path"] for e in led.get("entries", []) for a in e.get("anchors", [])
            if isinstance(a, dict) and isinstance(a.get("path"), str)}


def site_keys(led: dict) -> set[str]:
    return {e.get("site_key") for e in led.get("entries", []) if isinstance(e, dict)}


def unsafe_path(rel: str) -> bool:
    parts = rel.split("/")
    return rel.startswith("/") or ".." in parts or rel == "" or "\\" in rel or any(p == "" for p in parts)


def run(hook: bool = False) -> int:
    findings: list[str] = []
    try:
        _git("rev-parse", "--show-toplevel")            # repository/worktree context must resolve
        snap0 = snapshot()
        head = head_commit()
        stage0, unmerged = index_entries()
        changes = staged_changes(head)
        idx_name = os.path.basename(os.environ.get("GIT_INDEX_FILE", "")) or "index"

        # HEAD ledger (old references) — malformed HEAD ledger is an environment error (fail closed)
        head_led = None
        if head is not None:
            hb = head_blob(head, LEDGER_REL)
            if hb is not None:
                try:
                    head_led = json.loads(hb.decode("utf-8"))
                except Exception as exc:
                    raise GuardError(f"HEAD ledger is not valid JSON: {exc}")
        head_anchors = anchor_paths(head_led) if head_led else set()

        # candidate ledger (index, stage 0)
        cand_led, cand_led_error = None, None
        if LEDGER_REL in stage0:
            mode, oid = stage0[LEDGER_REL]
            if mode == MODE_SYMLINK or mode == MODE_GITLINK:
                cand_led_error = f"ledger index entry has unsupported mode {mode}"
            else:
                try:
                    cand_led = json.loads(blob_bytes(oid).decode("utf-8"))
                    if not isinstance(cand_led, dict):
                        cand_led, cand_led_error = None, "ledger blob is not a JSON object"
                except GuardError:
                    raise
                except Exception as exc:
                    cand_led_error = f"candidate ledger is not valid JSON: {_printable(str(exc))[:120]}"
        cand_anchors = anchor_paths(cand_led) if cand_led else set()

        touched = set()
        for st, p, newp in changes:
            touched.add(p)
            if newp:
                touched.add(newp)
        relevant = head_anchors | cand_anchors | {LEDGER_REL}
        triggered = bool(touched & relevant) or (head_led is not None and head_anchors != cand_anchors) \
            or cand_led_error is not None or (LEDGER_REL in unmerged)
        if not triggered:
            print(f"{TAG} not triggered — no staged change to {LEDGER_REL} or an anchored path "
                  f"({len(relevant) - 1} anchored paths; index={idx_name})")
            return 0

        if cand_led_error:
            findings.append(f"ledger: {cand_led_error}")
        if cand_led is None and cand_led_error is None:
            findings.append(f"ledger: {LEDGER_REL} missing from the candidate index (deletion is not a supported retirement)")
        for p in sorted(unmerged):
            if p in relevant:
                findings.append(f"unresolved merge stages {unmerged[p]} for {_printable(p)}")
        for st, p, newp in changes:
            if st in ("R", "C") and p in head_anchors:
                findings.append(f"anchored path renamed/copied {_printable(p)} -> {_printable(newp or '')}: no rename rule exists in the ledger (unsupported)")
            if st == "T" and (p in head_anchors or p in cand_anchors):
                findings.append(f"anchored path {_printable(p)} changed type (unsupported)")
            if st == "D" and p in head_anchors:
                findings.append(f"anchored path {_printable(p)} deleted from the candidate index")
        if head_led is not None and cand_led is not None:
            for k in sorted(site_keys(head_led) - site_keys(cand_led), key=str):
                findings.append(f"ledger entry {k!r} removed: no retirement rule exists (unsupported)")
            for p in sorted(head_anchors - cand_anchors):
                findings.append(f"anchor reference {_printable(p)} removed from the ledger: no retirement rule exists (unsupported)")
        if cand_led is not None:
            def read_index_bytes(rel: str):
                if unsafe_path(rel):
                    findings.append(f"anchor path rejected as unsafe: {_printable(rel)}")
                    return None
                ent = stage0.get(rel)
                if ent is None:
                    return None                      # validate_entries reports 'missing'
                mode, oid = ent
                if mode in (MODE_SYMLINK, MODE_GITLINK):
                    findings.append(f"anchor {_printable(rel)} is a {'symlink' if mode == MODE_SYMLINK else 'gitlink'} in the index (unsupported)")
                    return None
                return blob_bytes(oid)               # missing object → GuardError (exit 2)
            findings.extend(validate_entries(cand_led, read_index_bytes))
        if snapshot() != snap0:
            findings.append("index or HEAD changed while the guard was running — re-stage and retry")
    except GuardError as exc:
        print(f"{TAG} ERROR (fails closed): {exc}", file=sys.stderr)
        return 2
    if findings:
        print(f"{TAG} {len(findings)} finding(s) in the staged candidate (index={idx_name}):")
        for f in findings:
            print(f"  FAIL {f}")
        print(f"{TAG} commit blocked: staged ledger and anchored blobs disagree; fix the STAGED bytes/digest "
              f"in the same commit (no automatic anchor update)", file=sys.stderr)
        return 1
    print(f"{TAG} OK — candidate ledger consistent with {len(cand_anchors)} anchored index blob(s) "
          f"({len(cand_led.get('entries', []))} entries; index={idx_name})")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    return run(hook="--hook" in argv)


if __name__ == "__main__":
    sys.exit(main())
