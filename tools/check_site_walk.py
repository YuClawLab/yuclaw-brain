#!/usr/bin/env python3
"""
Stranger-walk integrity gate (2026-07-23) — the site as a first-time visitor.

Crawls from docs/index.html through every internal link and asserts, for every
top-level docs/*.html page:

  1. REACHABLE  — from index.html within 3 clicks (BFS over internal links).
  2. HEADER     — carries the shared site header: the logo→home link
                  (<a href="index.html"> wrapping the wordmark) + nav chips.
  3. FRESHNESS  — a machine-readable freshness stamp (built/generated/as of/
                  data through + date) OR an explicit <!-- static-page -->
                  marker.
  4. LINKS      — every internal href resolves to a real file, and every
                  #anchor (same-page or cross-page) resolves to a real id.
  5. DISCLAIMER — the research-only disclaimer appears on the page.

Scope: docs/*.html top level only. docs/preview/ is EXCLUDED BY DESIGN —
previews are unlinked staged pages; linking one from a public page will fail
gate 4's inverse check below (no public page may link into preview/).

SOURCE_DOCS: print sources for shipped documents (not site pages) — exempt
from REACHABLE and HEADER, still checked for FRESHNESS/LINKS/DISCLAIMER.

Exit 0 = green; exit 1 = findings (printed one per line). Runs in the daily
chain as a hard gate.
"""
from __future__ import annotations

import re
import sys
from collections import deque
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
MAX_CLICKS = 3

SOURCE_DOCS = {"YUCLAW_User_Guide_source.html"}   # print source for the PDF

RE_HREF = re.compile(r'href=[\'"]([^\'"]+)[\'"]')
RE_ID = re.compile(r'id=[\'"]([^\'"]+)[\'"]')
RE_LOGO = re.compile(r'<a href="index\.html"[^>]*>\s*<span[^>]*>YU', re.S)
RE_STAMP = re.compile(r'(built|generated|as of|data through)\s*:?\s*20\d\d-',
                      re.I)
STATIC_MARK = "<!-- static-page -->"
DISCLAIMER_RE = re.compile(r'not (investment|financial) advice', re.I)
MIN_CHIPS = 8   # nav chips in the shared header (site_header_html)
CHIP_LABELS = ("Validation Lab", "Open Index Evidence", "Canada Resources",
               "Forward Tracking", "GitHub", "PyPI", "Ledger", "Methodology",
               "Home")


def _internal_targets(page: Path, html: str):
    """(target_path|None, fragment|None, raw) for every internal href."""
    out = []
    for raw in RE_HREF.findall(html):
        if raw.startswith(("http://", "https://", "mailto:", "data:")):
            continue
        path_part, _, frag = raw.partition("#")
        target = (page.parent / path_part).resolve() if path_part else page
        out.append((target, frag or None, raw))
    return out


def main(argv: list[str] | None = None) -> int:
    pages = sorted(p for p in DOCS.glob("*.html"))
    html = {p: p.read_text(errors="replace") for p in pages}
    ids = {p: set(RE_ID.findall(t)) for p, t in html.items()}
    findings: list[str] = []

    # ---- 1. reachability (BFS from index, ≤ MAX_CLICKS)
    index = DOCS / "index.html"
    depth = {index: 0}
    q = deque([index])
    while q:
        cur = q.popleft()
        if depth[cur] >= MAX_CLICKS:
            continue
        for target, _f, _raw in _internal_targets(cur, html.get(cur, "")):
            if target in html and target not in depth:
                depth[target] = depth[cur] + 1
                q.append(target)
    for p in pages:
        if p.name in SOURCE_DOCS:
            continue
        if p not in depth:
            findings.append(f"{p.name}: UNREACHABLE from index.html within "
                            f"{MAX_CLICKS} clicks")

    for p in pages:
        t = html[p]
        name = p.name
        # ---- 2. shared header
        if name not in SOURCE_DOCS:
            if not RE_LOGO.search(t):
                findings.append(f"{name}: missing logo→home link in header")
            n_chips = sum(1 for c in CHIP_LABELS if c in t)
            if n_chips < MIN_CHIPS:
                findings.append(f"{name}: nav chips incomplete "
                                f"({n_chips}/{len(CHIP_LABELS)} labels found)")
        # ---- 3. freshness stamp or static marker
        if not RE_STAMP.search(t) and STATIC_MARK not in t:
            findings.append(f"{name}: no freshness stamp and no "
                            f"{STATIC_MARK} marker")
        # ---- 5. disclaimer
        if not DISCLAIMER_RE.search(t):
            findings.append(f"{name}: disclaimer block not found")
        # ---- 4. every internal href resolves (files + anchors)
        for target, frag, raw in _internal_targets(p, t):
            if "preview/" in raw:
                findings.append(f"{name}: links into docs/preview/ ({raw}) — "
                                f"previews are unlinked by design")
                continue
            if not target.exists():
                findings.append(f"{name}: dead link {raw}")
                continue
            if frag:
                tgt_ids = ids.get(target)
                if tgt_ids is None and target.suffix == ".html":
                    tgt_ids = set(RE_ID.findall(
                        target.read_text(errors="replace")))
                if tgt_ids is not None and frag not in tgt_ids:
                    findings.append(f"{name}: dead anchor {raw} "
                                    f"(no id='{frag}' in {target.name})")

    if findings:
        print(f"[site-walk] {len(findings)} finding(s):")
        for f in findings:
            print(f"  FAIL {f}")
        return 1
    print(f"[site-walk] OK — {len(pages)} pages: reachable≤{MAX_CLICKS} clicks, "
          f"shared header, freshness/static marker, all links+anchors resolve, "
          f"disclaimer present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
