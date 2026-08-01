"""Dual-copy byte-consistency check for the exhibit/narrative extractors.

The live-ingestion copies (v3/extract/{exhibit,narrative}.py, main worktree) and the
v5 originals (yuclaw/v5/extract/{exhibit,narrative}.py, yuclaw-v5 worktree) must stay
verbatim-identical EXCEPT for two sanctioned deltas, documented in each file header:

  1. the "# LIVE-INGESTION COPY ..." header block present only in the v3 copy;
  2. the intra-package import path (v3.extract.* <-> yuclaw.v5.extract.*).

This tool normalizes both sides for exactly those deltas and compares sha256 of the
result. Any other difference is a dual-copy violation and exits non-zero — run it
before every commit that touches either side (DUAL-COPY RULE).

CLI:
    python3 -m v3.tools.check_dual_copy            # verify (exit 0 = consistent)
    python3 -m v3.tools.check_dual_copy --sync     # regenerate v5 copies FROM v3
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

MAIN_ROOT = Path(__file__).resolve().parents[2]            # /home/zhangd2/yuclaw
V5_ROOT = MAIN_ROOT.parent / "yuclaw-v5"                   # sibling worktree

PAIRS = [
    (MAIN_ROOT / "v3/extract/exhibit.py", V5_ROOT / "yuclaw/v5/extract/exhibit.py"),
    (MAIN_ROOT / "v3/extract/narrative.py", V5_ROOT / "yuclaw/v5/extract/narrative.py"),
]

_HEADER_RE = re.compile(r"^# LIVE-INGESTION COPY.*?\n(?:#.*\n)*\n", re.M)


def _normalize_v3(text: str) -> str:
    """v3 copy -> canonical form (header stripped, import mapped to the v5 package)."""
    text = _HEADER_RE.sub("", text, count=1)
    return text.replace("v3.extract.", "yuclaw.v5.extract.")


def _v5_from_v3(v3_text: str) -> str:
    return _normalize_v3(v3_text)


def check() -> int:
    bad = 0
    for v3_path, v5_path in PAIRS:
        v3_text = v3_path.read_text(encoding="utf-8")
        v5_text = v5_path.read_text(encoding="utf-8")
        a = hashlib.sha256(_normalize_v3(v3_text).encode()).hexdigest()
        b = hashlib.sha256(v5_text.encode()).hexdigest()
        status = "CONSISTENT" if a == b else "MISMATCH"
        print(f"[dual-copy] {v3_path.name}: {status}  v3(norm)={a[:12]}  v5={b[:12]}")
        if a != b:
            bad += 1
    return 1 if bad else 0


def sync() -> int:
    for v3_path, v5_path in PAIRS:
        v5_path.write_text(_v5_from_v3(v3_path.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"[dual-copy] synced {v5_path} from {v3_path}")
    return check()


if __name__ == "__main__":
    sys.exit(sync() if "--sync" in sys.argv[1:] else check())
