#!/usr/bin/env python3
"""
COPY-CONSISTENCY GATE (G1, ORDER 2026-09-05B) — deterministic, exit nonzero
on any mismatch.

For each canonical block:
  canonical_source = ONE named file (UTF-8, LF, no HTML tags, no trailing
                     whitespace, exactly one trailing newline);
  every target embeds the block between FIXED markers
      <!-- NAME-CANONICAL BEGIN -->  ...  <!-- NAME-CANONICAL END -->
  extraction rule (the ONLY normalization): the bytes strictly between the
  BEGIN marker + one "\\n" and one "\\n" + the END marker. No re-wrapping, no
  whitespace collapsing, no entity decoding.
  RED when: a marker is missing or duplicated; CR present; an HTML tag
  appears inside the block; or sha256(target block) != sha256(canonical).
  An altered, omitted or extra sentence changes the hash → RED.

Blocks:
  LOOKAHEAD            docs/methodology/lookahead_statement.txt →
                       README.md, docs/methodology/backfill.md,
                       docs/methodology/validation_lab.md,
                       docs/validation_lab.html, docs/methodology.html
  REPLICATION-SENTENCE docs/replication/replication_sentence.txt (itself
                       re-derived from replication_log.json — a stale file
                       is RED) → README.md

CLI: python3 tools/check_copy_consistency.py            (exit 0 green / 1 RED)
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "tools"))

BLOCKS = {
    # MICRO 2026-09-07A: owner-approved MISSION & VISION text. The source file
    # carries its own markers (colon form) and two generator placeholders
    # ({{CHAIN_LINES}}, {{NAME_COUNT}}) that every target must show FILLED;
    # the comparison is against the filled source.
    "MISSION-VISION": {
        "canonical": "docs/methodology/mission_vision.txt",
        "marker": "<!-- MISSION-VISION-CANONICAL:{which} -->",
        "source_has_markers": True,
        "fill": "mission_vision",
        "targets": ["README.md", "docs/index.html"],
    },
    "LOOKAHEAD": {
        "canonical": "docs/methodology/lookahead_statement.txt",
        "targets": ["README.md", "docs/methodology/backfill.md",
                    "docs/methodology/validation_lab.md",
                    "docs/validation_lab.html", "docs/methodology.html"],
    },
    "REPLICATION-SENTENCE": {
        "canonical": "docs/replication/replication_sentence.txt",
        "targets": ["README.md"],
        "derive": "replication_log",
    },
}
_TAG_RE = re.compile(r"<[A-Za-z/!?]")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _marker(spec: dict, name: str, which: str) -> str:
    fmt = spec.get("marker") or f"<!-- {name}-CANONICAL {{which}} -->"
    return fmt.format(which=which)


def canonical_bytes(rel: str, problems: list[str], spec: dict | None = None, name: str = "") -> bytes | None:
    p = _REPO / rel
    if not p.exists():
        problems.append(f"{rel}: canonical source missing")
        return None
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        problems.append(f"{rel}: canonical source is not UTF-8"); return None
    if "\r" in text:
        problems.append(f"{rel}: canonical source contains CR")
    if not (spec and spec.get("source_has_markers")) and _TAG_RE.search(text):
        problems.append(f"{rel}: canonical source contains an HTML tag")
    if not text.endswith("\n") or text.endswith("\n\n"):
        problems.append(f"{rel}: canonical source must end with exactly one newline")
    if any(l != l.rstrip() for l in text.splitlines()):
        problems.append(f"{rel}: canonical source has trailing whitespace")
    body = text.rstrip("\n")
    if spec and spec.get("source_has_markers"):
        b, e = _marker(spec, name, "BEGIN"), _marker(spec, name, "END")
        m = re.search(re.escape(b) + r"\n(.*?)\n" + re.escape(e), text, re.S)
        if not m or text.count(b) != 1 or text.count(e) != 1:
            problems.append(f"{rel}: canonical source must carry exactly one marker pair"); return None
        body = m.group(1)
        if _TAG_RE.search(body):
            problems.append(f"{rel}: canonical block contains an HTML tag")
    if spec and spec.get("fill") == "mission_vision":
        import yuclaw_mission_vision as mv
        for k, v in mv.counts().items():
            body = body.replace("{{" + k + "}}", str(v))
        if "{{" in body:
            problems.append(f"{rel}: unfilled placeholder in the canonical source"); return None
    return body.encode("utf-8")


def extract(target_rel: str, name: str, problems: list[str], spec: dict | None = None) -> bytes | None:
    p = Path(target_rel) if Path(target_rel).is_absolute() else _REPO / target_rel
    if not p.exists():
        problems.append(f"{target_rel}: target missing"); return None
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        problems.append(f"{target_rel}: not UTF-8"); return None
    begin, end = _marker(spec or {}, name, "BEGIN"), _marker(spec or {}, name, "END")
    nb, ne = text.count(begin), text.count(end)
    if nb != 1 or ne != 1:
        problems.append(f"{target_rel}: {name} markers BEGIN×{nb} END×{ne} (need exactly one each)")
        return None
    i, j = text.index(begin) + len(begin), text.index(end)
    inner = text[i:j]
    if not (inner.startswith("\n") and inner.endswith("\n")):
        problems.append(f"{target_rel}: {name} block must start and end with a single newline adjacent to the markers")
        return None
    block = inner[1:-1]
    if "\r" in block:
        problems.append(f"{target_rel}: {name} block contains CR")
    if _TAG_RE.search(block):
        problems.append(f"{target_rel}: {name} block contains an HTML tag")
    return block.encode("utf-8")


def main() -> int:
    # --extra-target PATH [PATH ...]: additional LOOKAHEAD targets checked on
    # demand (ORDER 2026-09-05C G-c: the extracted text of the User Guide PDF
    # must carry the canonical block byte-for-byte between the same markers).
    extra = []
    if "--extra-target" in sys.argv:
        i = sys.argv.index("--extra-target")
        extra = [x for x in sys.argv[i + 1:] if not x.startswith("--")]
    problems: list[str] = []
    report = []
    for name, spec in BLOCKS.items():
        if extra:
            b = _marker(spec, name, "BEGIN")
            hits = [x for x in extra if Path(x).exists() and b in Path(x).read_text(encoding="utf-8", errors="replace")]
            if hits:
                spec = {**spec, "targets": spec["targets"] + hits}
        if spec.get("derive") == "replication_log":
            import yuclaw_replication_sentence as rs
            import json
            derived = rs.derive(json.loads((_REPO / "docs" / "replication" / "replication_log.json").read_text()))
            cur = (_REPO / spec["canonical"]).read_text(encoding="utf-8") if (_REPO / spec["canonical"]).exists() else None
            if cur != derived + "\n":
                problems.append(f"{spec['canonical']}: stale — derived sentence differs from the file")
        can = canonical_bytes(spec["canonical"], problems, spec, name)
        if can is None:
            continue
        for t in spec["targets"]:
            blk = extract(t, name, problems, spec)
            if blk is None:
                continue
            same = _sha(blk) == _sha(can)
            report.append((name, t, same))
            if not same:
                problems.append(f"{t}: {name} block sha256 {_sha(blk)[:16]} != canonical {_sha(can)[:16]}")
    for name, t, same in report:
        print(f"  {'GREEN' if same else 'RED  '} {name:<22} {t}")
    if problems:
        print("COPY-CONSISTENCY GATE FAILED:")
        for p in problems:
            print("  ·", p)
        return 1
    print(f"[copy-consistency] OK — {len(report)} target blocks byte-identical to their canonical sources "
          f"({', '.join(f'{n}: sha256 {_sha(canonical_bytes(s['canonical'], [], s, n))[:12]}' for n, s in BLOCKS.items())})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
