#!/usr/bin/env python3
"""
MISSION & VISION canonical block — generator (MICRO 2026-09-07A, redesigned 2026-09-07C).

Source: docs/methodology/mission_vision.md — owner-approved Markdown, VERBATIM,
between <!-- MISSION-VISION-CANONICAL:BEGIN --> / <!-- MISSION-VISION-CANONICAL:END -->.
UTF-8, LF line endings. G1 payload definition: the bytes immediately after the
BEGIN marker's terminating LF, up to but excluding the END marker line, INCLUDING
the payload's final LF; exactly one marker pair; sha256 of those bytes.

Consumers (one canonical source, no second hand-maintained copy):
  README.md                 write_readme(): the payload placed verbatim between the same markers
  homepage About card       render_html("site"): the payload through the site's Markdown renderer
  User Guide chapter 1      render_html("guide"): the same renderer, guide presentation transforms
  homepage compact strip    sections(): the HOW WE WORK / WHAT YOU GET table rows (data rows only)
counts() (registry line count, research-state name count) stays available for other surfaces.

Usage: python3 tools/yuclaw_mission_vision.py               # print the payload
       python3 tools/yuclaw_mission_vision.py --sha         # payload sha256
       python3 tools/yuclaw_mission_vision.py --html site|guide
       python3 tools/yuclaw_mission_vision.py --write-readme
       python3 tools/yuclaw_mission_vision.py --check       # README payload == canonical bytes
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
SRC = _REPO / "docs" / "methodology" / "mission_vision.md"
BEGIN, END = "<!-- MISSION-VISION-CANONICAL:BEGIN -->", "<!-- MISSION-VISION-CANONICAL:END -->"


def extract_payload(text: str, where: str = "source") -> str:
    """G1 extraction: exactly one marker pair; payload = bytes after the BEGIN
    line's LF up to the END marker line, final LF included. No trimming."""
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit(f"{where}: exactly one MISSION-VISION marker pair required "
                         f"(BEGIN×{text.count(BEGIN)}, END×{text.count(END)})")
    i = text.index(BEGIN) + len(BEGIN)
    if not text.startswith("\n", i):
        raise SystemExit(f"{where}: BEGIN marker must be terminated by LF")
    j = text.index(END)
    if j == 0 or text[j - 1] != "\n":
        raise SystemExit(f"{where}: END marker must start its own line")
    return text[i + 1:j]


def payload() -> str:
    raw = SRC.read_bytes()
    if b"\r" in raw:
        raise SystemExit("mission_vision.md must use LF line endings")
    return extract_payload(raw.decode("utf-8"), str(SRC.relative_to(_REPO)))


def payload_sha256() -> str:
    return hashlib.sha256(payload().encode("utf-8")).hexdigest()


def wrapped() -> str:
    return f"{BEGIN}\n{payload()}{END}"


def counts() -> dict:
    """Registry line count and research-state name count — kept for other
    surfaces (the block itself no longer carries a counts line)."""
    lines = sum(1 for l in (_REPO / "registry" / "protocols.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())
    names = len(json.loads((_REPO / "registry" / "research_state.json").read_text(encoding="utf-8"))["names"])
    return {"CHAIN_LINES": lines, "NAME_COUNT": names}


_WORDMARK = re.compile(r'<h1 align="center">YUCLAW</h1>')
_MAPLE_SVG = ('<svg class="mv-leaf" viewBox="0 0 24 24" width="1em" height="1em" aria-hidden="true" '
              'style="vertical-align:-0.12em"><path fill="#d0342c" d="M12 2l1.6 3.6 3.1-1.5-.8 3.6 3.4.2-2.5 2.6 '
              '2.8 2.1-3.3.9 1.5 3.3-3.6-1.1-.6 3.7L12 16.9l-1.6 2.5-.6-3.7-3.6 1.1 1.5-3.3-3.3-.9 2.8-2.1L4.7 7.9 '
              '8.1 7.7l-.8-3.6 3.1 1.5L12 2zm-.6 15.2h1.2V22h-1.2z"/></svg>')


def render_html(variant: str = "site") -> str:
    """The canonical payload through the site's Markdown renderer (python-markdown,
    GFM tables), then renderer-level PRESENTATION transforms only — the input
    Markdown is never altered:
      - the h1 wordmark becomes YU + CLAW spans (accessible name stays "YUCLAW");
      - align="center" becomes a class the surface styles;
      - variant "guide": the maple-leaf emoji becomes an inline SVG glyph so the
        PDF does not depend on a color-emoji font.
    Also emits <!-- mv-source sha256:… --> so a gate can prove the rendered
    surface consumed exactly these bytes."""
    import markdown
    src = payload()
    html = markdown.markdown(src, extensions=["tables"])
    html = _WORDMARK.sub('<h1 class="mv-wordmark"><span class="mv-yu">YU</span><span class="mv-claw">CLAW</span></h1>', html, count=1)
    html = html.replace('<p align="center">', '<p class="mv-center">').replace('<h2 align="center">', '<h2 class="mv-h2">')
    if variant == "guide":
        html = html.replace("🍁", _MAPLE_SVG)
    return f"<!-- mv-source sha256:{hashlib.sha256(src.encode('utf-8')).hexdigest()} -->\n{html}"


def sections() -> dict:
    """Data rows of the two canonical tables, for the homepage strip. Headings are
    the exact source headings; header and separator rows are never emitted;
    cell bold markers are stripped (the strip applies its own emphasis)."""
    out: dict = {}
    cur = None
    for line in payload().splitlines():
        m = re.match(r"^### (.+?)\s*$", line)
        if m:
            cur = m.group(1); out[cur] = []; continue
        if cur and line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):     # separator row
                out[cur].append(None); continue
            out[cur].append([re.sub(r"^\*\*(.+)\*\*$", r"\1", c) for c in cells])
    result = {}
    for heading, rows in out.items():
        if None not in rows:
            continue                                   # not a table section
        sep = rows.index(None)
        result[heading] = {"header": rows[sep - 1], "rows": rows[sep + 1:]}
    return result


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
        print(f"[mission-vision] README {'updated' if ch else 'already current'} — payload sha256 {payload_sha256()[:16]}")
        return 0
    if "--check" in argv:
        got = extract_payload((_REPO / "README.md").read_text(encoding="utf-8"), "README.md")
        ok = got.encode("utf-8") == payload().encode("utf-8")
        print(f"[mission-vision] README payload {'OK' if ok else 'STALE'} — sha256 {payload_sha256()[:16]}")
        return 0 if ok else 1
    if "--sha" in argv:
        print(payload_sha256()); return 0
    if "--html" in argv:
        print(render_html(argv[argv.index("--html") + 1] if len(argv) > argv.index("--html") + 1 else "site")); return 0
    sys.stdout.write(payload())
    return 0


if __name__ == "__main__":
    sys.exit(main())
