"""Packaged v9 text resources: the bilingual quick start printed by `brief guide`."""
from __future__ import annotations

from pathlib import Path

DIR = Path(__file__).resolve().parent / "resources"


def guide(lang: str = "en") -> str:
    p = DIR / ("QUICKSTART_FR.md" if lang == "fr" else "QUICKSTART_EN.md")
    if not p.is_file():
        return "the packaged quick start is missing from this installation (a packaging defect, not a workspace problem)\n"
    return p.read_text(encoding="utf-8")
