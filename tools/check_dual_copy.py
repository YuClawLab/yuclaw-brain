#!/usr/bin/env python3
"""Dual-copy byte-consistency check (Canada Resources Phase 2 ship gate).

exhibit.py and narrative.py exist twice by design:
  live ingestion copy : v3/extract/{exhibit,narrative}.py            (main worktree)
  v5 swarm copy       : yuclaw/v5/extract/{exhibit,narrative}.py     (v5-layer1 worktree)

The copies must be byte-identical EXCEPT for two documented differences:
  1. the 5-line "LIVE-INGESTION COPY" header block present only in the v3 copy;
  2. the intra-package import root (v3.extract.<mod> vs yuclaw.v5.extract.<mod>).

This script normalizes exactly those two differences and fails (exit 1) on any
other divergence, printing a unified diff. Run before any commit that touches
either copy:

    python3 tools/check_dual_copy.py
"""
from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

MAIN_ROOT = Path("/home/zhangd2/yuclaw")
V5_ROOT = Path("/home/zhangd2/yuclaw-v5")

PAIRS = [
    (MAIN_ROOT / "v3/extract/exhibit.py", V5_ROOT / "yuclaw/v5/extract/exhibit.py"),
    (MAIN_ROOT / "v3/extract/narrative.py", V5_ROOT / "yuclaw/v5/extract/narrative.py"),
]

_HEADER_RE = re.compile(
    r"# LIVE-INGESTION COPY[^\n]*\n(?:#[^\n]*\n)*\n", re.M)


def normalize(text: str) -> str:
    text = _HEADER_RE.sub("", text)
    text = text.replace("from v3.extract.", "from PKG.extract.")
    text = text.replace("from yuclaw.v5.extract.", "from PKG.extract.")
    return text


def main() -> int:
    rc = 0
    for a, b in PAIRS:
        na, nb = normalize(a.read_text()), normalize(b.read_text())
        if na == nb:
            print(f"OK   {a.name}: copies byte-consistent after documented normalization")
            continue
        rc = 1
        print(f"FAIL {a.name}: copies diverge beyond the documented header/import lines")
        for line in difflib.unified_diff(
                na.splitlines(), nb.splitlines(),
                fromfile=str(a), tofile=str(b), lineterm="", n=2):
            print("  " + line)
    return rc


if __name__ == "__main__":
    sys.exit(main())
