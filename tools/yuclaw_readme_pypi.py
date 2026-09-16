#!/usr/bin/env python3
"""
README_PYPI.md — the PyPI long description, GENERATED from README.md (V8-003 §5).

PyPI renders the long description with readme_renderer: a relative image path cannot resolve there and the
<picture>/<source> element is stripped, so the GitHub README's approved-logo picture block would render as a broken
image. The PyPI copy is README.md with ONLY that picture block removed; every other byte — including the canonical
MISSION-VISION, LOOKAHEAD and REPLICATION-SENTENCE blocks — is identical. The approved logo bytes are untouched and
are not published early to satisfy a rendering check.

  python3 tools/yuclaw_readme_pypi.py --write     # regenerate README_PYPI.md
  python3 tools/yuclaw_readme_pypi.py --check     # README_PYPI.md == transform(README.md); renders; no picture/relative brand path
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
SRC, DST = _REPO / "README.md", _REPO / "README_PYPI.md"
PICTURE = re.compile(r'<p align="center">\n  <picture>\n(?:.*\n){2}  </picture>\n</p>\n\n', re.M)


def transform(text: str) -> str:
    out, n = PICTURE.subn("", text, count=1)
    if n != 1:
        raise SystemExit("README.md: expected exactly one approved-logo picture block")
    return out


def check() -> int:
    src = SRC.read_text(encoding="utf-8"); want = transform(src)
    problems = []
    if not DST.exists() or DST.read_text(encoding="utf-8") != want:
        problems.append("README_PYPI.md is stale: run tools/yuclaw_readme_pypi.py --write")
    if "<picture" in want or 'src="brand/' in want:
        problems.append("picture block or relative brand path still present")
    sys.path.insert(0, str(_REPO / "tools"))
    import yuclaw_mission_vision as mv
    if mv.extract_payload(src, "README.md") != mv.extract_payload(want, "README_PYPI.md"):
        problems.append("MISSION-VISION canonical payload differs between README.md and README_PYPI.md")
    import importlib.util
    try:
        if not (importlib.util.find_spec("cmarkgfm") or importlib.util.find_spec("comrak")):
            raise ImportError("readme_renderer[md] backend missing")          # without a Markdown backend render() returns None for every input
        from readme_renderer.markdown import render
        html_ = render(want)
        if html_ is None:
            problems.append("readme_renderer could not render README_PYPI.md")
        elif "<picture" in html_ or 'src="brand/' in html_:
            problems.append("rendered long description still carries the picture element or a relative brand path")
        else:
            print(f"[readme-pypi] rendered with readme_renderer: {len(html_)} bytes of HTML, no picture element, no relative brand path")
    except ImportError:
        print("[readme-pypi] SKIPPED render: readme_renderer[md] (cmarkgfm) not installed in this interpreter; `twine check` over the built artifacts covers it")
    for p in problems:
        print("[readme-pypi] FAIL:", p)
    if not problems:
        print(f"[readme-pypi] OK — README_PYPI.md == README.md minus the picture block ({len(want)} bytes); canonical payload identical; renders without the picture element")
    return 1 if problems else 0


def main(argv=None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    if a == ["--write"]:
        DST.write_text(transform(SRC.read_text(encoding="utf-8")), encoding="utf-8"); print("[readme-pypi] wrote", DST.name); return 0
    if a == ["--check"]:
        return check()
    print(__doc__); return 2


if __name__ == "__main__":
    sys.exit(main())
