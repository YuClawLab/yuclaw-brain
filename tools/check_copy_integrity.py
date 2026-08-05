#!/usr/bin/env python3
"""
Copy-integrity lint for rendered public pages (in-freeze order, 2026-07-22).

Catches the truncated-copy bug class at the gate instead of in external review:

  1. clipped decimals   — "(5." style: open paren + number ending at a decimal
                          point with no digits after it (the split('.') bug).
  2. unclosed parens    — per text block, '(' / '[' without a matching closer.
  3. unterminated <p>   — paragraph text ending without terminal punctuation.
  4. dangling links     — empty href, href="#", or a local href whose target
                          file does not exist under docs/.

Scope: rendered HTML text nodes (tags stripped per block). Code/pre blocks and
inline <code> are exempt (commands are not prose). Exit 1 on any violation.

CLI:  python3 tools/check_copy_integrity.py docs/*.html
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# blocks whose inner text is prose we check
_BLOCK_RE = re.compile(r"<(p|li|td|h1|h2|h3|div)\b[^>]*>(.*?)</\1>", re.S | re.I)
_TAG_RE = re.compile(r"<[^>]+>")
_CODEISH_RE = re.compile(r"<(pre|code|script|style)\b.*?</\1>", re.S | re.I)
_HREF_RE = re.compile(r'href="([^"]*)"')

# 1. "(5." — open paren, digits, decimal point, then NOT a digit
_CLIPPED_DECIMAL_RE = re.compile(r"\(\d+\.(?!\d)")
# A <p> is flagged only on POSITIVE truncation signatures — ending mid-clause
# (comma / em-dash / middot / open connector word). Bare-noun endings are
# legitimate for label lists and metadata rows, so "no period" alone is not
# an error.
_CUT_ENDINGS = re.compile(
    r"([,·&—–-]|\b(?:the|a|an|of|and|or|with|to|for|from|by|in|on|at|is|are|was|has))$",
    re.I)

def _text(block_html: str) -> str:
    t = _TAG_RE.sub(" ", block_html)
    t = (t.replace("&amp;", "&").replace("&nbsp;", " ").replace("&middot;", "·")
          .replace("&rarr;", "→").replace("&mdash;", "—").replace("&rsquo;", "'")
          .replace("&#8593;", "↑"))
    return re.sub(r"\s+", " ", t).strip()


def lint_file(path: Path, docs_root: Path) -> list[str]:
    raw = path.read_text(errors="replace")
    body = _CODEISH_RE.sub(" ", raw)
    problems: list[str] = []

    for m in _BLOCK_RE.finditer(body):
        tag, inner = m.group(1).lower(), m.group(2)
        # nested containers re-match on their own; only lint leaf-ish text
        if "<div" in inner or "<table" in inner:
            continue
        txt = _text(inner)
        if not txt:
            continue
        if _CLIPPED_DECIMAL_RE.search(txt):
            problems.append(f"clipped decimal: …{txt[max(0, _CLIPPED_DECIMAL_RE.search(txt).start()-40):_CLIPPED_DECIMAL_RE.search(txt).start()+12]}…")
        if txt.count("(") > txt.count(")") or txt.count("[") > txt.count("]"):
            problems.append(f"unclosed paren/bracket in <{tag}>: …{txt[:90]}…")
        if tag == "p" and len(txt) > 60 and _CUT_ENDINGS.search(txt):
            problems.append(f"cut-off <p>: …{txt[-90:]}")

    # href scan runs on `body` (script/style/pre/code stripped): JS
    # template literals inside <script> are not rendered copy, and their
    # client-side-built links are covered by the site-walk's spot checks.
    for href in _HREF_RE.findall(body):
        if href in ("", "#"):
            problems.append(f"dangling link: href=\"{href}\"")
            continue
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path_part = href.split("#")[0].split("?")[0]   # query strings resolve
        target = (docs_root / path_part).resolve()
        if path_part and not target.exists():
            problems.append(f"dead local link: {href}")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args:
        print("usage: check_copy_integrity.py FILE [FILE...]", file=sys.stderr)
        return 2
    docs_root = Path(__file__).resolve().parents[1] / "docs"
    bad = 0
    for a in args:
        p = Path(a)
        probs = lint_file(p, docs_root)
        if probs:
            bad += 1
            print(f"FAIL {p}: {len(probs)} copy-integrity issue(s)")
            for x in probs[:10]:
                print(f"  - {x}")
        else:
            print(f"OK   {p}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
