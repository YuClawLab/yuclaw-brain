#!/usr/bin/env python3
"""Validation Lab derived prose vs the PUBLIC replay bundle beside the page (8.0.1 C01). No database.

  python3 tools/yuclaw_lab_prose.py --check      # rc 1 when a derived sentence on docs/validation_lab.html is not what the bundle's numbers say
  python3 tools/yuclaw_lab_prose.py --restage    # rewrite ONLY those sentences from the bundle (a staged candidate site; the nightly refresh
                                                 # renders the whole page from the same numbers through v3/web/render_validation_lab.py)

The bundle's `expected` block is `v3.lab.rigor.compute_rigor()` — the same dictionary the page's tables are rendered from — and the refresh
exports the bundle before it renders the page, so page and bundle describe the same data.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
from v3.web import lab_prose  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true"); ap.add_argument("--restage", action="store_true")
    ap.add_argument("--page", default=str(_REPO / "docs" / "validation_lab.html")); ap.add_argument("--bundle", default=str(_REPO / "docs" / "replay" / "lab_replay_bundle.json"))
    a = ap.parse_args(argv)
    page = Path(a.page); b = json.loads(Path(a.bundle).read_text(encoding="utf-8")); rig, ident = b["expected"], lab_prose.bundle_identity(b); html = page.read_text(encoding="utf-8")
    if a.restage:
        new = lab_prose.restage(html, rig, ident)
        if new != html:
            page.write_text(new, encoding="utf-8")
        print(f"[lab-prose] restaged {page.name} from the bundle built {ident.get('built_utc')} ({ident.get('n_leaves'):,} leaves): {'changed' if new != html else 'already consistent'}")
        html = new
    bad = lab_prose.stale(html, rig, ident)
    print(f"[lab-prose] {'RED — stale derived prose: ' + ', '.join(bad) if bad else 'OK — derived prose equals the numbers of the bundle built ' + str(ident.get('built_utc'))}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
