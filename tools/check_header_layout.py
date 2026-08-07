#!/usr/bin/env python3
"""
Header-layout gate (clean-header order, 2026-08-07 — supersedes the
2026-08-06 stamp-placement order).

Asserts, for EVERY generated page (docs/*.html + docs/why/*.html):

  1. CLEAN HEADER — ZERO freshness stamps inside any header: no
     hdr-stamp node anywhere on the page (the class is retired), and no
     stamp phrasing inside the site-hdr subtree. The header renders
     brand + version badge + nav chips ONLY.
  2. ONE STAMP — exactly one freshness stamp per page ANYWHERE on the
     page: a page's own in-content freshness box (<div class="fresh">)
     counts as its single stamp; every other page carries exactly one
     footer stamp line (footer_stamp_html). Counting is whitespace-
     normalized so multi-line box wording counts like single-line
     wording. Same exemptions as check_site_walk: static-page marker,
     SOURCE_DOCS, scripts and the buildinfo footer excluded.
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
RE_FRESH_BOX = re.compile(r'<div class="fresh"[^>]*>.*?</div>', re.S)
RE_STRIP_PHRASE = re.compile(
    r"\(last completed U\.S\. trading day[^)]*\) · regenerated (daily|weekly)",
    re.I)
RE_UPDATED = re.compile(r"Updated 20\d\d-\d\d-\d\d")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def stamp_count(body: str) -> int:
    """Stamps on a page: each in-content freshness box counts once
    (whatever its wording); stamp phrasing outside the boxes counts per
    match. body must already have scripts + buildinfo stripped."""
    boxes = RE_FRESH_BOX.findall(body)
    rest = _norm(RE_FRESH_BOX.sub("", body))
    return (len(boxes) + len(RE_STRIP_PHRASE.findall(rest)) +
            len(RE_UPDATED.findall(rest)))


class _HeaderText(HTMLParser):
    """Collects the text content of the site-hdr subtree."""

    def __init__(self):
        super().__init__()
        self.depth = 0            # element depth inside site-hdr (0 = outside)
        self.hdr_seen = False
        self.text: list[str] = []

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "")
        if self.depth:
            self.depth += 1
        elif "site-hdr" in classes:
            self.hdr_seen = True
            self.depth = 1

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.text.append(data)


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
        # 1a. the retired hdr-stamp node may not appear anywhere
        if "hdr-stamp" in t:
            findings.append(f"{name}: hdr-stamp node present — the header "
                            f"must carry zero stamps")
        if STATIC_MARK in t:
            continue
        # 1b. zero stamp phrasing inside the site-hdr subtree
        ht = _HeaderText()
        ht.feed(t)
        if "hdr-nav" in t and not ht.hdr_seen:
            findings.append(f"{name}: site-hdr container missing from the "
                            f"shared header")
        hdr_text = _norm(" ".join(ht.text))
        if RE_STRIP_PHRASE.search(hdr_text) or RE_UPDATED.search(hdr_text):
            findings.append(f"{name}: freshness stamp inside the header")
        # 2. exactly one stamp anywhere on the page
        body = RE_BUILDINFO.sub("", RE_SCRIPT.sub("", t))
        n_stamp = stamp_count(body)
        if n_stamp != 1:
            findings.append(f"{name}: {n_stamp} freshness stamps — "
                            f"exactly one required")
    if findings:
        print(f"[header-layout] {len(findings)} finding(s):")
        for f in findings:
            print(f"  FAIL {f}")
        return 1
    print(f"[header-layout] OK — {n_checked} pages: zero stamps in any "
          f"header, exactly one stamp per page, badge {VERSION} == "
          f"package version")
    return 0


if __name__ == "__main__":
    sys.exit(main())
