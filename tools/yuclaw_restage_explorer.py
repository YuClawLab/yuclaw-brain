#!/usr/bin/env python3
"""Restage docs/explorer.html from the PUBLIC docs/explorer_data.json with the current Explorer template (8.0.1 C09). No database.

The nightly refresh renders the page from the database through v3/web/render_explorer.py. A release candidate stages the site without
the database: this tool renders the same template from the data file the last refresh published beside the page, and splices ONLY the
template regions (the <style> block, and the controls + table + script) into the staged page. The shared header, the footer and its
freshness stamp stay byte-identical, and the embedded rows must equal the staged rows — otherwise it stops.
  python3 tools/yuclaw_restage_explorer.py [--check]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

REGIONS = ((re.compile(r"<style>.*?</style>", re.S), "style"), (re.compile(r'<div class="bar".*?</script>', re.S), "controls+table+script"))
ROWS = re.compile(r"const ROWS = (\[.*?\]);\n", re.S)


def restaged(page: str) -> str:
    from v3.web import render_explorer as R
    fresh = R.render(json.loads((_REPO / "docs" / "explorer_data.json").read_text(encoding="utf-8")))
    a, b = ROWS.search(page), ROWS.search(fresh)
    if not a or not b or json.loads(a.group(1)) != json.loads(b.group(1)):
        raise SystemExit("STOP: the rows embedded in the staged page are not the rows of docs/explorer_data.json — restage only a page and a data file from the same refresh")
    for pat, name in REGIONS:
        m_new, m_old = pat.search(fresh), pat.search(page)
        if not m_new or not m_old:
            raise SystemExit(f"STOP: region {name!r} not found")
        page = page[:m_old.start()] + m_new.group(0) + page[m_old.end():]
    return page


def main(argv=None) -> int:
    check = "--check" in (argv if argv is not None else sys.argv[1:]); p = _REPO / "docs" / "explorer.html"; old = p.read_text(encoding="utf-8"); new = restaged(old)
    if check:
        print(f"[restage-explorer] {'OK — the staged page carries the current template' if new == old else 'RED — the staged page does not carry the current template (run without --check)'}")
        return 0 if new == old else 1
    if new != old:
        p.write_text(new, encoding="utf-8")
    print(f"[restage-explorer] {'restaged' if new != old else 'already current'}: {p.relative_to(_REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
