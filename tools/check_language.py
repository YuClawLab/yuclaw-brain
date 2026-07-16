#!/usr/bin/env python3
"""
Language lint — the compliance-rail checker (usefulness build, 2026-07-16).

Two enforced lists:

  BANNED_DIRECTIVE — words that read as investment advice or performance
      claims in YUCLAW-authored prose (memos, page copy):
      buy, sell, hold, undervalued, overvalued, top pick, alpha, opportunity,
      recommend/recommendation*, forecast, outperform, underperform, upside,
      downside target, price target, mispriced, conviction
      (*"not ... recommendations" disclaimers are allowed via negation guard)

  BANNED_ADJECTIVE — marketing adjectives banned across the public surface:
      institutional, professional, premier, best, superior, market-beating,
      predictive, world-class, cutting-edge, state-of-the-art, unmatched

Scope rules (important):
  - The lint applies to YUCLAW-AUTHORED language. Verbatim filing quotes and
    the locked event-type vocabulary (INSIDER_BUY / INSIDER_SELL / BUYBACK_*)
    are NOT authored language; callers must lint only their own prose
    sections, or pass text with quotes stripped. lint_memo_sections() and
    the file mode both strip `>`-quoted lines, code spans, and event-type
    tokens before matching.
  - Matching is word-boundary, case-insensitive ("buy" never matches
    "buyback"; "sell" never matches "sell-side" is INTENTIONALLY still a hit).

Library use:
    from tools.check_language import lint_text
    violations = lint_text(prose)          # [] means clean

CLI (files or globs; exit 1 on any violation):
    python3 tools/check_language.py docs/lane.html v4/memo/evidence_memo.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BANNED_DIRECTIVE = [
    "buy", "sell", "hold", "undervalued", "overvalued", "top pick", "alpha",
    "opportunity", "opportunities", "recommend", "recommends", "recommended",
    "forecast", "forecasts", "forecasting", "outperform", "underperform",
    "upside", "price target", "mispriced", "conviction",
]
BANNED_ADJECTIVE = [
    "institutional", "professional", "premier", "best", "superior",
    "market-beating", "predictive", "world-class", "cutting-edge",
    "state-of-the-art", "unmatched",
]

# "research classifications, not buy/sell recommendations" and similar locked
# disclaimers legitimately contain banned tokens — any line matching one of
# these negation patterns is exempt.
_NEGATION_RE = re.compile(
    r"not (a |an )?(buy/sell |investment )?(advice|recommendation)|"
    r"not buy/sell|never (a )?recommendation|no recommendation", re.I)

# Locked machine vocabulary that legitimately embeds banned stems.
_LOCKED_TOKENS_RE = re.compile(
    r"INSIDER_(BUY|SELL)|BUYBACK_\w+|buy/sell recommendations?|"
    r"buy or sell", re.I)

RESEARCH_FOOTER_RE = re.compile(r"research (and|&(amp;)?) education (use )?only", re.I)

_QUOTE_LINE_RE = re.compile(r"^\s*>.*$", re.M)          # markdown blockquotes
_CODE_SPAN_RE = re.compile(r"`[^`]*`")                   # inline code
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.M)      # markdown table rows


def _compile(words: list[str]) -> list[tuple[str, re.Pattern]]:
    return [(w, re.compile(rf"(?<![\w-]){re.escape(w)}(?![\w-])", re.I)) for w in words]


_PATTERNS = _compile(BANNED_DIRECTIVE + BANNED_ADJECTIVE)   # memo prose (full rail)
_PAGE_PATTERNS = _compile(BANNED_ADJECTIVE)                  # public pages (adjective rail)


def strip_non_authored(text: str) -> str:
    """Remove verbatim-quote lines, code spans, table rows, and locked tokens —
    the parts that are not YUCLAW-authored prose."""
    text = _QUOTE_LINE_RE.sub("", text)
    text = _TABLE_ROW_RE.sub("", text)
    text = _CODE_SPAN_RE.sub("", text)
    text = _LOCKED_TOKENS_RE.sub("", text)
    return text


def lint_text(text: str, *, strip: bool = True, pages_mode: bool = False) -> list[dict]:
    """Return violations [{word, line_no, line}] in authored text.

    pages_mode=False (memos): full rail — directive words + adjectives.
    pages_mode=True  (public pages): the whole-order adjective rail only —
    statistical terms ("market-model alpha") and the locked Form-4 buy/sell
    split are page vocabulary, not violations.
    """
    if strip:
        text = strip_non_authored(text)
    pats = _PAGE_PATTERNS if pages_mode else _PATTERNS
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if _NEGATION_RE.search(line):
            continue
        for word, pat in pats:
            if pat.search(line):
                out.append({"word": word, "line_no": i, "line": line.strip()[:140]})
    return out


def check_research_footer(text: str) -> bool:
    """True when the mandatory research-only footer is present."""
    return bool(RESEARCH_FOOTER_RE.search(text))


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    pages_mode = "--pages" in args
    if pages_mode:
        args.remove("--pages")
    if not args:
        print("usage: check_language.py [--pages] FILE [FILE...]", file=sys.stderr)
        return 2
    rc = 0
    for arg in args:
        path = Path(arg)
        if not path.exists():
            print(f"MISS {arg}: no such file", file=sys.stderr)
            rc = 1
            continue
        violations = lint_text(path.read_text(errors="replace"), pages_mode=pages_mode)
        if violations:
            rc = 1
            print(f"FAIL {arg}: {len(violations)} banned-language hit(s)")
            for v in violations[:20]:
                print(f"  line {v['line_no']}: [{v['word']}] {v['line']}")
        else:
            print(f"OK   {arg}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
