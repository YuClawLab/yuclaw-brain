#!/usr/bin/env python3
"""
Index-completeness gate (audit F2, 2026-08-05): every nav-linked public
page must appear in evidence_index.json AND be named in llms.txt — the
machine surface can never lag the human one again.

Nav-linked = every internal .html target in the shared header's chip
list (v3/web/useful_blocks._NAV_CHIPS) plus pages linked from the home
hero (tour.html). Exit 0 green / 1 violation; chained hard.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> int:
    from v3.web.useful_blocks import _NAV_CHIPS
    nav = [href for _l, href in _NAV_CHIPS
           if href.endswith(".html") and not href.startswith("http")]
    nav.append("tour.html")                     # hero-linked, not chipped
    idx = json.loads((_REPO / "docs" / "evidence_index.json").read_text())
    idx_pages = {p["url"].rsplit("/", 1)[-1] if "/why/" not in p["url"]
                 else "why/" + p["url"].rsplit("/", 1)[-1]
                 for p in idx.get("pages", [])}
    llms = (_REPO / "docs" / "llms.txt").read_text()
    problems = []
    for page in sorted(set(nav)):
        if page not in idx_pages:
            problems.append(f"{page}: nav-linked but absent from "
                            f"evidence_index.json pages")
        if f"/{page}" not in llms:
            problems.append(f"{page}: nav-linked but not named in llms.txt")
    if problems:
        print("INDEX-COMPLETENESS GATE FAILED:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(f"[index-completeness] OK — {len(set(nav))} nav-linked pages all "
          f"present in evidence_index.json and llms.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
