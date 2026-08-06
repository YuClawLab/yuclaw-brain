#!/usr/bin/env python3
"""
Header-layout gate (display-defect order, 2026-08-06).

Asserts, for EVERY generated page (docs/*.html + docs/why/*.html):

  1. STAMP PLACEMENT — the freshness stamp renders in its own block
     (class="hdr-stamp") OUTSIDE the nav chip row (class="hdr-nav"),
     never inline in the chips again. Structural check via an HTML
     parser, not substring guessing.
  2. ONE STAMP — exactly one freshness stamp per page (same regexes and
     exemptions as check_site_walk: static-page marker, SOURCE_DOCS,
     buildinfo footer excluded).
  3. BADGE = PACKAGE — the header version badge equals v{pyproject
     version}; no page can advertise a stale hardcoded version.

Exit 0 = green; exit 1 = findings. Runs in the daily chain after
site-walk.
"""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
DOCS = _REPO / "docs"
sys.path.insert(0, str(_REPO))

SOURCE_DOCS = {"YUCLAW_User_Guide_v5.1_source.html",
               "YUCLAW_Guide_Utilisateur_v5.1_FR_source.html"}
STATIC_MARK = "<!-- static-page -->"
RE_SCRIPT = re.compile(r"<script\b.*?</script>", re.S | re.I)
RE_BUILDINFO = re.compile(r'<footer class="buildinfo".*?</footer>', re.S)
RE_STRIP_PHRASE = re.compile(
    r"\(last completed U\.S\. trading day[^)]*\) · regenerated (daily|weekly)",
    re.I)
RE_UPDATED = re.compile(r"Updated 20\d\d-\d\d-\d\d")


class _NavStamp(HTMLParser):
    """Tracks whether an hdr-stamp node opens inside the hdr-nav subtree."""

    def __init__(self):
        super().__init__()
        self.depth = 0            # element depth inside hdr-nav (0 = outside)
        self.nav_seen = False
        self.stamp_seen = False
        self.stamp_inside_nav = False

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "")
        if self.depth:
            self.depth += 1
        elif "hdr-nav" in classes:
            self.nav_seen = True
            self.depth = 1
        if "hdr-stamp" in classes:
            self.stamp_seen = True
            if self.depth:
                self.stamp_inside_nav = True

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1


def main() -> int:
    from v3.web.useful_blocks import VERSION
    badge = f">{VERSION}</span>"
    pages = sorted(DOCS.glob("*.html")) + sorted((DOCS / "why").glob("*.html"))
    findings: list[str] = []
    n_checked = 0
    for p in pages:
        name = p.name if p.parent == DOCS else f"why/{p.name}"
        if p.name in SOURCE_DOCS:
            continue
        t = p.read_text(errors="replace")
        n_checked += 1
        # 3. badge equals the package version on every shared-header page
        if "hdr-nav" in t and badge not in t:
            findings.append(f"{name}: version badge != {VERSION}")
        if STATIC_MARK in t:
            continue
        body = RE_BUILDINFO.sub("", RE_SCRIPT.sub("", t))
        n_stamp = (len(RE_STRIP_PHRASE.findall(body)) +
                   len(RE_UPDATED.findall(body)))
        # 2. exactly one stamp
        if n_stamp != 1:
            findings.append(f"{name}: {n_stamp} freshness stamps — "
                            f"exactly one required")
        # 1. stamp block outside the nav row
        ps = _NavStamp()
        ps.feed(t)
        if ps.nav_seen and n_stamp:
            if not ps.stamp_seen:
                findings.append(f"{name}: stamp not in the shared "
                                f"hdr-stamp block")
            elif ps.stamp_inside_nav:
                findings.append(f"{name}: hdr-stamp renders INSIDE the "
                                f"nav row")
    if findings:
        print(f"[header-layout] {len(findings)} finding(s):")
        for f in findings:
            print(f"  FAIL {f}")
        return 1
    print(f"[header-layout] OK — {n_checked} pages: stamp in its own block "
          f"below the nav row, exactly one stamp, badge {VERSION} == "
          f"package version")
    return 0


if __name__ == "__main__":
    sys.exit(main())
