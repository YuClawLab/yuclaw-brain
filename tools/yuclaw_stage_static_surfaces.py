#!/usr/bin/env python3
"""Stage the homepage's STATIC fragments on a release candidate without the database (8.0.1 C05 / C06 / C07 / C12).

The nightly refresh renders docs/index.html from the database through v3/web/render_landing.py. A candidate site is staged
without it, so the fragments that do not depend on data are taken from the SAME helper functions the generator uses
(v3/web/useful_blocks.py) and written into the staged page: the current-guide links (the v5.1 PDFs become labelled history),
the footer guide links, the local-workbench card, and the page's own identity strings (<title>, "YUCLAW vX.Y.Z") at the
package version. Every data-bearing byte of the page is left alone.
  python3 tools/yuclaw_stage_static_surfaces.py [--check]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
from v3.web import useful_blocks as U  # noqa: E402

PAGE = _REPO / "docs" / "index.html"
LEGACY_GUIDE = re.compile(r'<p style="font-size:12px;color:#A0AEC0;margin:10px 0 0"><a href="YUCLAW_User_Guide\.pdf">.*?</p>', re.S)
LEGACY_FOOTER = re.compile(r'<a href="YUCLAW_User_Guide\.pdf">[^<]*</a> ·\s*<a href="YUCLAW_Guide_Utilisateur_FR\.pdf">[^<]*</a> ·')
INSTALL_CARD = '    <div class="card">\n      <div class="card-title">Install + try it</div>'
IDENTITY = re.compile(r"(<title>YUCLAW v|YUCLAW v)(\d+\.\d+\.\d+)")


def _put(html: str, mark: str, frag: str, legacy: re.Pattern | None, insert_before: str | None = None) -> str:
    pat = re.compile(re.escape(f"<!-- {mark} BEGIN -->") + r".*?" + re.escape(f"<!-- {mark} END -->"), re.S)
    if pat.search(html):
        return pat.sub(lambda _m: frag, html, count=1)
    if legacy is not None and legacy.search(html):
        return legacy.sub(lambda _m: frag, html, count=1)
    if insert_before and html.count(insert_before) == 1:
        return html.replace(insert_before, frag + "\n\n" + insert_before)
    raise SystemExit(f"STOP: no place for {mark} on {PAGE.name}")


def staged(html: str) -> str:
    html = _put(html, U.GUIDE_MARK, U.guide_links_html(), LEGACY_GUIDE)
    html = _put(html, U.FOOTER_GUIDE_MARK, U.footer_guide_links_html(), LEGACY_FOOTER)
    html = _put(html, U.WORKBENCH_MARK, U.workbench_card_html(), None, INSTALL_CARD)
    return IDENTITY.sub(lambda m: m.group(1) + U.VERSION.lstrip("v"), html)


def main(argv=None) -> int:
    check = "--check" in (argv if argv is not None else sys.argv[1:]); old = PAGE.read_text(encoding="utf-8"); new = staged(old)
    if check:
        print(f"[stage-static] {'OK — the staged homepage carries the current static fragments at ' + U.VERSION if new == old else 'RED — the staged homepage is not current (run without --check)'}")
        return 0 if new == old else 1
    if new != old:
        PAGE.write_text(new, encoding="utf-8")
    print(f"[stage-static] {'staged' if new != old else 'already current'}: docs/index.html at {U.VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
