#!/usr/bin/env python3
"""Bounded excerpt-quality scan (QA-05 E4). Declared corpus: the CURRENT public evidence objects in docs/why/*.json
(preview collections) plus, when present, docs/why/*.history.json (complete histories), keyed by source_hash so
every object counts once. Records the detector rule ids, the unique-object denominator, suspected counts per rule
(overlaps handled by the union), and — from the annotation store — confirmed and corrected counts separately.
Writes the report to --out (private) and prints the public count basis. Never modifies evidence."""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
from v3.extract.excerpt_quality import RULES, assess  # noqa: E402

ANNOTATIONS = _REPO / "registry" / "excerpt_corrections.jsonl"


def corpus(docs: Path) -> dict:
    seen = {}
    for f in sorted(glob.glob(str(docs / "why" / "*.json"))):
        d = json.loads(Path(f).read_text())
        if Path(f).name == "history_manifest.json":
            continue
        for o in d.get("evidence_objects", []):
            key = o.get("source_hash") or hashlib.sha256(json.dumps(o, sort_keys=True).encode()).hexdigest()
            seen.setdefault(key, {"ticker": o.get("ticker"), "accession": o.get("accession_number"), "excerpt": o.get("excerpt", ""), "files": []})["files"].append(Path(f).name)
    return seen


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--docs", default=str(_REPO / "docs")); ap.add_argument("--out"); a = ap.parse_args(argv)
    objs = corpus(Path(a.docs))
    by_rule = {r: [] for r in RULES}; suspected = set()
    for key, o in objs.items():
        for r in assess(o["excerpt"]):
            by_rule[r].append(key); suspected.add(key)
    ann = [json.loads(l) for l in ANNOTATIONS.read_text().splitlines() if l.strip()] if ANNOTATIONS.exists() else []
    by_hash = {x["original"]["source_hash"]: x for x in ann}
    confirmed = {k for k, x in by_hash.items() if x.get("status") in ("CONFIRMED", "CORRECTED")}
    corrected = {k for k, x in by_hash.items() if x.get("status") == "CORRECTED"}
    rep = {"corpus": "current public evidence objects in docs/why/*.json (+ *.history.json when present), unique by source_hash", "scanned_utc": datetime.now(timezone.utc).isoformat(),
           "detector_rules": {r: rx.pattern for r, rx in RULES.items()}, "denominator_unique_objects": len(objs),
           "suspected_by_rule": {r: len(v) for r, v in by_rule.items()}, "suspected_union": len(suspected),
           "confirmed_in_annotation_store": len(confirmed & set(objs)), "corrected_in_annotation_store": len(corrected & set(objs)),
           "suspected_not_yet_reviewed": len(suspected - confirmed), "policy": "a hit stays SUSPECTED until verified against the primary document; corrections are separate annotations (original retained); counts are never inflated to 'every hit fixed'",
           "suspects": [{"source_hash": k, "ticker": objs[k]["ticker"], "accession": objs[k]["accession"], "rules": assess(objs[k]["excerpt"])} for k in sorted(suspected)]}
    if a.out:
        Path(a.out).write_text(json.dumps(rep, indent=1) + "\n")
    print(f"[excerpt-scan] unique objects {rep['denominator_unique_objects']}; suspected {rep['suspected_union']} ({rep['suspected_by_rule']}); confirmed {rep['confirmed_in_annotation_store']}; corrected {rep['corrected_in_annotation_store']}; not yet reviewed {rep['suspected_not_yet_reviewed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
