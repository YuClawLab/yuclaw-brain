#!/usr/bin/env python3
"""
MISSION & VISION canonical block — generator (MICRO 2026-09-07A).

Source: docs/methodology/mission_vision.txt (owner-approved text, VERBATIM,
between <!-- MISSION-VISION-CANONICAL:BEGIN --> / <!-- MISSION-VISION-CANONICAL:END -->).
Two placeholders are filled at build and NEVER hand-typed:

  {{CHAIN_LINES}}  = number of lines in registry/protocols.jsonl
  {{NAME_COUNT}}   = number of names in registry/research_state.json

Consumers embed render_block() byte-identically between the same markers:
README.md (via --write-readme), the homepage (v3/web/render_landing.py),
the User Guide chapter 1. tools/check_copy_consistency.py compares every
copy to the filled source (G1).

Usage: python3 tools/yuclaw_mission_vision.py            # print the filled block
       python3 tools/yuclaw_mission_vision.py --write-readme
       python3 tools/yuclaw_mission_vision.py --check    # README carries the current fill
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
SRC = _REPO / "docs" / "methodology" / "mission_vision.txt"
BEGIN, END = "<!-- MISSION-VISION-CANONICAL:BEGIN -->", "<!-- MISSION-VISION-CANONICAL:END -->"


def counts() -> dict:
    lines = sum(1 for l in (_REPO / "registry" / "protocols.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())
    names = len(json.loads((_REPO / "registry" / "research_state.json").read_text(encoding="utf-8"))["names"])
    return {"CHAIN_LINES": lines, "NAME_COUNT": names}


def template() -> str:
    """The text strictly between the markers in the source file (placeholders unfilled)."""
    text = SRC.read_text(encoding="utf-8")
    m = re.search(re.escape(BEGIN) + r"\n(.*?)\n" + re.escape(END), text, re.S)
    if not m:
        raise SystemExit("mission_vision.txt: markers missing")
    body = m.group(1)
    if "\r" in body or re.search(r"[&<>]", body):
        raise SystemExit("mission_vision.txt: CR or HTML-significant byte inside the block")
    return body


def render_block() -> str:
    body = template()
    for k, v in counts().items():
        body = body.replace("{{" + k + "}}", str(v))
    if "{{" in body:
        raise SystemExit("mission_vision.txt: unfilled placeholder remains")
    return body


def sections() -> dict:
    """The filled block split at its section headers, for compact presentations
    (the homepage strip). Paragraph lines are joined with spaces; nothing is
    typed here — every string comes from the source file."""
    paras = render_block().split("\n\n")
    out = {"headline": paras[0].splitlines()[0], "identity": paras[0].splitlines()[1],
           "hook": " ".join(paras[1].splitlines()), "closing": " ".join(paras[-2].splitlines()),
           "counts": " ".join(paras[-1].splitlines())}
    for para in paras[2:-2]:
        lines = para.splitlines()
        key = lines[0].strip().lower().replace(" ", "_")
        if key in ("mission", "vision"):
            out[key] = " ".join(lines[1:])
        else:
            items, cur = [], ""
            for ln in lines[1:]:
                if re.match(r"^(We |Analysts:|Builders:|Institutions:)", ln) and cur:
                    items.append(cur); cur = ln
                else:
                    cur = (cur + " " + ln).strip() if cur else ln
            if cur:
                items.append(cur)
            out[key] = items
    return out


def wrapped() -> str:
    return f"{BEGIN}\n{render_block()}\n{END}"


def write_readme() -> bool:
    p = _REPO / "README.md"
    s = p.read_text(encoding="utf-8")
    if s.count(BEGIN) != 1 or s.count(END) != 1:
        raise SystemExit("README.md must carry exactly one MISSION-VISION marker pair")
    new = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), lambda _m: wrapped(), s, flags=re.S)
    changed = new != s
    if changed:
        p.write_text(new, encoding="utf-8")
    return changed


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--write-readme" in argv:
        ch = write_readme()
        print(f"[mission-vision] README {'updated' if ch else 'already current'} — {counts()}")
        return 0
    if "--check" in argv:
        s = (_REPO / "README.md").read_text(encoding="utf-8")
        ok = wrapped() in s
        print(f"[mission-vision] README {'OK' if ok else 'STALE'} — {counts()}")
        return 0 if ok else 1
    print(render_block())
    return 0


if __name__ == "__main__":
    sys.exit(main())
