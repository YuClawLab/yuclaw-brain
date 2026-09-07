#!/usr/bin/env python3
"""
LEAK SWEEP GATE (MICRO 2026-09-07B) — exit nonzero on any hit in any public
surface. The sensitive terms (witness names, romanized variants, institutions,
cities, box identifiers) are read ONLY from internal/witness_denylist.txt,
which is gitignored — the denylist itself can never leak through this tool.
A missing or empty private list is a RED, never a silent pass.

Public structural patterns (not sensitive) are kept here: internal paths,
box-local output paths, scratch paths, home-directory paths.

Surfaces: every git-tracked file read as text (HTML, Markdown, JSON, YAML,
Python, shell, CSS, …), PDFs through pdftotext, zip members, plus any
--extra-file (e.g. the extracted text of the User Guide PDF). Scope rules:
  witness        → EVERY tracked public surface — any hit is RED
  box            → every tracked surface, counted as WARNINGS with file:line
                   (visible hygiene debt in ops docs and scripts; never a
                   silent pass, never a block on the witness emergency)
  structural, guide → only files passed with --guide (the User Guide text)

CLI: python3 tools/check_leak_sweep.py [--extra-file F ...] [--guide F ...]
     python3 tools/check_leak_sweep.py --self-test     # plants a term in a temp
                                                        # file and proves detection
"""
from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
PRIVATE = _REPO / "internal" / "witness_denylist.txt"
STRUCTURAL = [r"internal/", r"output/oie", r"scratchpad", r"/home/[a-z]"]
TEXT_EXT = {".md", ".html", ".htm", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".cff",
            ".py", ".sh", ".css", ".js", ".csv", ".cfg", ".ini", ".xml", ".svg", ".in", ".rst"}
SKIP_PREFIX = ("internal/", "archive/", "output/", "dist/")
# the sweep tool and the private list are the only places the categories are described
SELF = "tools/check_leak_sweep.py"


def load_private() -> dict[str, list[str]]:
    if not PRIVATE.exists():
        raise SystemExit(f"[leak-sweep] RED — private denylist missing: {PRIVATE} (fail closed)")
    scopes: dict[str, list[str]] = {"witness": [], "box": [], "guide": []}
    for line in PRIVATE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        scope, term = (x.strip() for x in line.split(":", 1))
        if scope in scopes and term:
            scopes[scope].append(term)
    if not scopes["witness"]:
        raise SystemExit("[leak-sweep] RED — private denylist has no witness terms (fail closed)")
    return scopes


def _pattern(term: str) -> re.Pattern:
    esc = re.escape(term)
    if re.fullmatch(r"[A-Za-z][A-Za-z.\-]*", term):        # single token → word boundaries
        return re.compile(rf"(?<![A-Za-z0-9]){esc}(?![A-Za-z0-9])", re.I)
    return re.compile(esc, re.I)                            # phrase → literal, case-insensitive


def _texts_of(path: Path):
    """Yield (label, text) for a tracked file: text files directly, PDFs via
    pdftotext, zips member by member."""
    suf = path.suffix.lower()
    if suf == ".pdf":
        r = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True)
        yield f"{path}(pdftotext)", r.stdout
    elif suf == ".zip":
        try:
            with zipfile.ZipFile(path) as z:
                for n in z.namelist():
                    if Path(n).suffix.lower() in TEXT_EXT:
                        yield f"{path}::{n}", z.read(n).decode("utf-8", "replace")
        except zipfile.BadZipFile:
            return
    elif suf in TEXT_EXT or suf == "":
        try:
            yield str(path), path.read_bytes().decode("utf-8", "replace")
        except OSError:
            return


def scan(text: str, label: str, pats: list[tuple[str, re.Pattern]]) -> list[str]:
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for kind, p in pats:
            m = p.search(line)
            if m:
                hits.append(f"{label}:{i}: [{kind}] …{line[max(0, m.start()-40):m.end()+30].strip()}…")
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra-file", action="append", default=[], help="additional text file(s) to sweep with the public-surface scopes")
    ap.add_argument("--guide", action="append", default=[], help="User Guide text file(s): witness + box + guide scopes")
    ap.add_argument("--self-test", action="store_true", help="plant the first private term in a temp file and prove it is caught")
    ap.add_argument("--only-extra", action="store_true", help="skip the tracked-file scan; sweep only --extra-file/--guide inputs")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    scopes = load_private()
    witness_pats = [("witness", _pattern(t)) for t in scopes["witness"]]
    box_pats = [("box", _pattern(t)) for t in scopes["box"]]
    public_pats = witness_pats + box_pats
    # structural path patterns are a PDF/guide concern (a repository page may
    # legitimately cite an artifact path); they apply to --guide inputs only
    guide_pats = public_pats + [("structural", re.compile(p)) for p in STRUCTURAL] + [("guide", _pattern(t)) for t in scopes["guide"]]
    READER_PREFIX = ("README.md", "CHANGELOG.md", "COMPARISON.md", "CONTRIBUTING.md", "CITATION.cff",
                     "pyproject.toml", "REPLICATIONS.md", "DISCLAIMER.md", "NOTICE", "docs/", "drafts/")
    if a.self_test:
        planted = scopes["witness"][0]
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(f"A harmless sentence.\nReviewed with {planted} last spring.\n")
        hits = scan(Path(f.name).read_text(), "PLANT", guide_pats)
        Path(f.name).unlink()
        ok = bool(hits)
        print(f"[leak-sweep] self-test: planted term {'CAUGHT' if ok else 'MISSED'} ({len(hits)} hit(s); the term itself is not printed)")
        return 0 if ok else 1
    tracked = [] if a.only_extra else subprocess.run(["git", "ls-files", "-z"], cwd=_REPO, capture_output=True, text=True).stdout.split("\0")
    hits: list[str] = []
    warnings: list[str] = []
    n_files = 0
    for rel in sorted(x for x in tracked if x):
        if rel.startswith(SKIP_PREFIX) or rel == SELF or rel.startswith("docs/guide/build/"):
            continue
        p = _REPO / rel
        if not p.exists():
            continue
        reader = rel.startswith(READER_PREFIX)
        for label, text in _texts_of(p):
            label = label.replace(str(_REPO) + "/", "")
            n_files += 1
            hits += scan(text, label, witness_pats)
            warnings.extend(scan(text, label, box_pats))      # box identifiers: visible debt, not blocking
    for f in a.extra_file:
        hits += scan(Path(f).read_text(encoding="utf-8", errors="replace"), f, public_pats)
    for f in a.guide:
        hits += scan(Path(f).read_text(encoding="utf-8", errors="replace"), f, guide_pats)
    # never echo the private terms in the public log: redact denylist hits to the file:line
    if hits:
        print(f"LEAK SWEEP FAILED — {len(hits)} hit(s) across public surfaces:")
        for h in hits[:60]:
            print("  ·", h.split(": [")[0] + ": [" + h.split(": [", 1)[1].split("]")[0] + "]")
        return 1
    if not a.quiet:
        print(f"[leak-sweep] OK — {n_files} tracked surfaces (+{len(a.extra_file) + len(a.guide)} extra) clean of "
              f"{len(scopes['witness'])} witness terms (private list); box-identifier WARNINGS (not blocking): {len(warnings)}"
              + (f" in {len({w.split(':')[0] for w in warnings})} files" if warnings else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
