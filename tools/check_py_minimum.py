#!/usr/bin/env python3
"""Minimum-runtime grammar check (v7): flag f-string replacement fields that need Python 3.12 (PEP 701) —
backslashes or same-quote nesting inside the expression part — across v3/ and tools/. pyproject declares
`requires-python >= 3.10`; this scan runs on the box's 3.12 tokenizer and is a static proxy, not a run on 3.10.
Exit 0 = clean; 1 = findings."""
from __future__ import annotations

import io
import re
import sys
import tokenize
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def scan(paths) -> list[tuple[str, int, str]]:
    hits = []
    for p in paths:
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(p.read_text(errors="replace")).readline))
        except Exception as exc:  # noqa: BLE001
            hits.append((str(p.relative_to(_REPO)), 0, f"tokenize error {exc.__class__.__name__}")); continue
        stack, depth = [], []
        for t in toks:
            if t.type == getattr(tokenize, "FSTRING_START", -1):
                stack.append(t.string.lstrip("fFrRbB")); depth.append(0)
            elif t.type == getattr(tokenize, "FSTRING_END", -1):
                stack.pop(); depth.pop()
            elif stack and t.type == tokenize.OP and t.string == "{":
                depth[-1] += 1
            elif stack and t.type == tokenize.OP and t.string == "}":
                depth[-1] = max(0, depth[-1] - 1)
            elif stack and depth[-1] > 0 and t.type == tokenize.STRING:
                q = stack[-1]
                if t.string.lstrip("fFrRbBuU").startswith(q[0]) and q not in ('"""', "'''"):
                    hits.append((str(p.relative_to(_REPO)), t.start[0], "same-quote string nested in an f-string expression (3.12-only)"))
                if "\\" in t.string:
                    hits.append((str(p.relative_to(_REPO)), t.start[0], "backslash inside an f-string expression (3.12-only)"))
    return hits


NEWER_STDLIB = ("tomllib", "datetime.UTC", "ExceptionGroup", "typing.Self", "StrEnum")   # added in 3.11+


def scan_stdlib(paths) -> list[tuple[str, int, str]]:
    """Unguarded use of stdlib names newer than 3.10 (an `import tomllib` inside try/except ImportError is fine)."""
    hits = []
    for p in paths:
        if p.resolve() == Path(__file__).resolve():
            continue                                                                  # the scanner names these identifiers on purpose
        lines = p.read_text(errors="replace").splitlines()
        for i, line in enumerate(lines, 1):
            for name in NEWER_STDLIB:
                if re.search(rf"(^|[^\w.]){re.escape(name)}([^\w]|$)", line) and not line.lstrip().startswith("#"):
                    if name == "tomllib" and "import" in line:
                        prev = "\n".join(lines[max(0, i - 3):i - 1])
                        if "try:" in prev:
                            continue
                    if name == "tomllib" and "import" not in line:
                        continue                                                  # a use after a guarded import
                    hits.append((str(p.relative_to(_REPO)), i, f"{name} needs Python 3.11+ (no guard)"))
    return hits


def main(argv=None) -> int:
    paths = list((_REPO / "v3").rglob("*.py")) + list((_REPO / "tools").glob("*.py")) + list((_REPO / "v4").rglob("*.py"))
    hits = scan(paths) + scan_stdlib(paths)
    if hits:
        for h in hits: print(f"FAIL {h[0]}:{h[1]}: {h[2]}")
        print(f"[py-minimum] {len(hits)} finding(s) — pyproject declares >=3.10"); return 1
    print(f"[py-minimum] OK — {len(paths)} files scanned; no PEP 701-only f-string grammar (static proxy on Python {sys.version.split()[0]})"); return 0


if __name__ == "__main__":
    sys.exit(main())
