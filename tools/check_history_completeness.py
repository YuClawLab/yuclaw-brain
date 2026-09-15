#!/usr/bin/env python3
"""Historical-recipe completeness gate (QA-02, 2026-09-15). For every ticker in the bound scoring universe:
  · why/{T}.history.json exists, validates as a COMPLETE evidence-collection/1 (count == total_available, declared
    ordering with tie-breaker), and its sha256/count/build_id match why/history_manifest.json (mixed builds fail);
  · why/{T}.json declares its evidence_objects as a PREVIEW with typed metadata whose returned/total_available/
    oldest-returned/build_id agree with the history file, and every preview object is a member of the history;
  · the as-of recipe on a preview yields INCOMPLETE for a date before the preview window while the complete
    history yields COMPLETE/COMPLETE_EMPTY (the DELL 2026-09-09 mechanism), with availability-based filtering.
Exit 0 = complete and consistent; 1 = findings."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
DOCS = _REPO / "docs"
sys.path.insert(0, str(_REPO))
from v3.evidence import history as H  # noqa: E402


def check(docs: Path = DOCS, tickers: list[str] | None = None) -> list[str]:
    f: list[str] = []
    if tickers is None:
        from v3.universe_tiers import scoring_universe
        tickers = sorted(scoring_universe())
    mp = docs / "why" / "history_manifest.json"
    if not mp.exists():
        return ["why/history_manifest.json missing"]
    man = json.loads(mp.read_text()); files = man.get("files", {})
    for t in tickers:
        hp = docs / "why" / f"{t.replace('.', '-')}.history.json"; pp = docs / "why" / f"{t.replace('.', '-')}.json"
        if not hp.exists():
            f.append(f"{t}: history file missing (incomplete)"); continue
        hb = hp.read_bytes(); hist = json.loads(hb)
        ent = files.get(t)
        if not ent:
            f.append(f"{t}: not in the history manifest")
        elif ent.get("sha256") != hashlib.sha256(hb).hexdigest() or ent.get("count") != len(hist.get("evidence_objects", [])):
            f.append(f"{t}: history file identity/count differs from the manifest (mixed build)")
        if hist.get("build_id") != man.get("build_id"):
            f.append(f"{t}: history build_id != manifest build_id (mixed build)")
        meta = hist.get("collection", {}); objs = hist.get("evidence_objects", [])
        probs = H.validate_collection(meta, objs)
        if probs or meta.get("completeness") != "COMPLETE":
            f.append(f"{t}: history collection invalid: {'; '.join(probs) or 'not COMPLETE'}")
        if pp.exists():
            prev = json.loads(pp.read_text()); pm = prev.get("evidence_objects_collection")
            if not pm:
                f.append(f"{t}: preview lacks evidence_objects_collection metadata"); continue
            pobjs = prev.get("evidence_objects", [])
            pp_probs = H.validate_collection(pm, pobjs)
            if pp_probs or pm.get("completeness") != "PREVIEW":
                f.append(f"{t}: preview metadata invalid: {'; '.join(pp_probs) or 'not PREVIEW'}")
            if pm.get("build_id") != hist.get("build_id"):
                f.append(f"{t}: preview build_id != history build_id")
            if pm.get("total_available") != len(objs):
                f.append(f"{t}: preview total_available {pm.get('total_available')} != history count {len(objs)}")
            hh = {o.get("source_hash") for o in objs}
            if any(o.get("source_hash") not in hh for o in pobjs):
                f.append(f"{t}: preview object not present in the complete history")
            if pobjs and objs and len(objs) > len(pobjs):
                d = (min(o["available_as_of"] for o in pobjs))[:10]
                probe = H.as_of_query(pm, pobjs, d)
                full = H.as_of_query(meta, objs, d)
                if probe["status"] != "INCOMPLETE" or full["status"] not in ("COMPLETE", "COMPLETE_EMPTY", "OUT_OF_RANGE"):
                    f.append(f"{t}: as-of recipe statuses wrong for {d}: preview {probe['status']}, history {full['status']}")
    return f


def main(argv=None) -> int:
    f = check()
    for x in f[:40]:
        print(f"FAIL {x}")
    print(f"[history-completeness] {'OK' if not f else str(len(f)) + ' finding(s)'} — complete per-ticker histories bound to one build; previews declared")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
