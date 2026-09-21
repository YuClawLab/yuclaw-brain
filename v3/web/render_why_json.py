"""
Ground Truth JSON API (v5.3 PART A): docs/why/{TICKER}.json for all 79,
schema-validated at build against schemas/WhyAnatomy.v1.json and
schemas/EvidenceObject.v1.json. Plus the discovery + verification
endpoints: docs/capabilities.json, docs/evidence/verify.json, and
per-day ledger-root files docs/ledger/{DATE}.json.

AS-OF DECISION (stated): the client-side reconstruction recipe, not
@DATE file fan-out. Trailing-30-day per-date files would be ~2,400
regenerated artifacts per build (~24 MB of daily git churn) for data the
same JSON already contains: every EvidenceObject carries available_as_of
and the label_history ribbon carries the per-day classification. Recipe
(also in llms.txt with a worked example): to reconstruct name X as of
date D — take why/X.json; evidence = objects with available_as_of <= D;
classification at D = the label_history entry for the last date <= D.
Older dates beyond the ribbon: `yuclaw replay X --date D` (CLI path).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import jsonschema

from v3.evidence import evidence_objects
from v3.signal.base import SIGNAL_THRESHOLDS

OUT_DIR = _REPO / "docs" / "why"
NOT_ADVICE = ("Research and education only — not investment advice. "
              "Signal labels are research classifications, not buy/sell "
              "recommendations. Investment implication: none established "
              "— no buy, sell, or alpha conclusion is supported by this "
              "object.")


def _band(score: float, label: str) -> dict:
    floors = list(SIGNAL_THRESHOLDS)
    for i, (f, l) in enumerate(floors):
        if l == label:
            return {"floor": f, "ceiling": floors[i - 1][0] if i else None}
    return {"floor": None, "ceiling": None}


def build_all() -> int:
    from v3.web.render_why_pages import _load_all
    snaps, hist, _events, ecs, _stories = _load_all()
    from v3.web import render_why_pages as _rwp
    _cov_id = _rwp.COVERAGE_IDENTITY
    eo_schema = json.loads((_REPO / "schemas" /
                            "EvidenceObject.v1.json").read_text())
    wa_schema = json.loads((_REPO / "schemas" /
                            "WhyAnatomy.v1.json").read_text())
    stamp = datetime.now(timezone.utc).isoformat()
    from v3.evidence import evidence_history, history as H
    from v3.web.excerpt_corrections import annotations_for, public_projection
    import hashlib as _hl
    build_id = "why-" + stamp.replace(":", "").replace("+00:00", "Z")[:17]
    wh_schema = json.loads((_REPO / "schemas" / "WhyHistory.v1.json").read_text()) if (_REPO / "schemas" / "WhyHistory.v1.json").exists() else None
    manifest = {"schema": "why-history-manifest/1", "build_id": build_id, "generated": stamp, "files": {}, "note": "one build = one consistent read per ticker; a history file whose sha256 or build_id differs from this manifest is a mixed-build result and must be treated as incomplete"}
    n = 0
    for tk, snap in sorted(snaps.items()):
        _t, label, score, st, *comps = snap
        hist_read = evidence_history(tk)
        full = hist_read["objects"]
        hist_meta = H.collection_metadata(full, scope=f"accepted evidence objects for {tk} in the declared corpus", total_available=hist_read["total"], cap=None, ordering=H.ORDERING_HISTORY, build_id=build_id, completeness="COMPLETE", corpus_start=hist_read["corpus_start"], corpus_end=hist_read["read_at"])
        hist_doc = {"schema": "WhyHistory.v1", "ticker": tk, "build_id": build_id, "generated": stamp, "collection": hist_meta, "evidence_objects": full, "corrections": annotations_for(full), "not_advice": NOT_ADVICE}
        hb = json.dumps(hist_doc, indent=1).encode()
        hp = OUT_DIR / f"{tk.replace('.', '-')}.history.json"; hp.write_bytes(hb)
        manifest["files"][tk] = {"path": f"why/{tk.replace('.', '-')}.history.json", "sha256": _hl.sha256(hb).hexdigest(), "bytes": len(hb), "count": len(full), "corpus_end": hist_read["read_at"]}
        # the compatibility preview: the newest 100 of the SAME read, declared as a PREVIEW
        objs = sorted(full, key=lambda o: (o["available_as_of"], o.get("accession_number") or "", o.get("source_hash") or ""), reverse=True)[:100]
        pub = [dict(o) for o in objs]
        preview_meta = H.collection_metadata(pub, scope=hist_meta["scope"], total_available=hist_read["total"], cap=100, ordering=H.ORDERING_PREVIEW, build_id=build_id, completeness="PREVIEW", corpus_start=hist_read["corpus_start"], corpus_end=hist_read["read_at"])
        doc = {
            "ticker": tk, "generated": stamp,
            "label": label, "score": round(float(score), 4),
            "threshold_band": _band(float(score), label),
            "components": {f"c{i}": (float(v) if v is not None else None)
                           for i, v in enumerate(comps, 1)},
            "evidence_coverage": {**ecs.get(tk, {}), **({"as_of": _cov_id["as_of"], "source_sha256": _cov_id["source_sha256"], "metric_id": "ecs"} if _cov_id else {})},
            "evidence_objects": pub,
            "evidence_objects_collection": preview_meta,
            "history_url": f"/why/{tk.replace('.', '-')}.history.json",
            "history_manifest_url": "/why/history_manifest.json",
            "build_id": build_id,
            "corrections": annotations_for(pub),
            "label_history": [{"date": d.isoformat(), "label": l}
                              for d, l in hist.get(tk, [])],
            "as_of_recipe": ("evidence_objects here is a PREVIEW (newest "
                             f"{len(pub)} of {hist_read['total']} accepted objects; see "
                             "evidence_objects_collection). Reconstruct evidence as of D "
                             "ONLY from the complete history file at history_url (same "
                             "build_id; verify its sha256 in history_manifest_url): objects "
                             "with available_as_of <= D (the recorded availability, never "
                             "filing_date or generated timestamps). From this preview alone the "
                             "result is INCOMPLETE for every D unless returned == total_available. "
                             "D before collection.corpus_start or after corpus_end is OUT_OF_RANGE. "
                             "Classification at D = label_history entry for the last date <= D; "
                             f"older dates: yuclaw replay {tk} --date D"),
            "verify": ("each object's source_hash is a SHA-256 anchored "
                       "via the daily ledger root — see "
                       "/evidence/verify.json"),
            "not_advice": NOT_ADVICE,
        }
        jsonschema.validate(doc, wa_schema)
        for o in pub[:5]:
            jsonschema.validate(o, eo_schema)
        (OUT_DIR / f"{tk.replace('.', '-')}.json").write_text(
            json.dumps(doc, indent=1))
        n += 1
    (OUT_DIR / "history_manifest.json").write_text(json.dumps(manifest, indent=1))
    public_projection(_REPO / "docs" / "evidence" / "excerpt_corrections.json", stamp)
    return n


def _pkg_version() -> str:
    """The package version at generation time — capabilities.json can
    never advertise a stale hardcoded version again (v5.3.3). ONE
    source: v3.web.useful_blocks (the header badge and citation
    snippets derive from the same function since 2026-08-06)."""
    from v3.web.useful_blocks import _pkg_version as pv
    return pv()


def _release_manifest() -> dict:
    """release_manifest.json at the repo root — the single source for the
    public version, canonical base URL and machine-endpoint inventory
    (ORDER 2026-09-05B C4/C5/G2-G4). Its version must equal the package
    version; a mismatch is a build failure, never a silent skew."""
    m = json.loads((_REPO / "release_manifest.json").read_text())
    if m["version"] != _pkg_version():
        raise SystemExit(f"release_manifest.version {m['version']} != package "
                         f"version {_pkg_version()} — fix one, never publish both")
    return m


def build_endpoints() -> None:
    m = _release_manifest()
    base = m["public_base_url"].rstrip("/")
    endpoints = {e["key"]: f"{base}{e['path']}" for e in m["machine_surfaces"]}
    (_REPO / "docs" / "capabilities.json").write_text(json.dumps({
        "name": m["api_name"],
        "former_name": m["api_former_name"],
        "former_name_status": m.get("api_former_name_status", "deprecated compatibility alias; not a product claim"),   # 8.0.1 C11: the alias is retained on purpose — and says so
        "version": f"v{m['version']}", "generated":
            datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "positioning": "The open evidence layer for financial AI.",
        "endpoints": endpoints,
        "endpoint_kinds": {e["key"]: e["kind"] for e in m["machine_surfaces"]},
        "wildcard_discovery": {e["key"]: e["discovery_rule"] for e in m["machine_surfaces"]
                               if e["kind"] == "wildcard_family"},
        "endpoint_case": "JSON endpoints are case-sensitive: {TICKER} is "
                         "uppercase (why/NVDA.json — why/nvda.json is a "
                         "404); the CLI uppercases ticker arguments for "
                         "you",
        "formats": {
            "evidencebench": "JSONL — one item per line: {item_id, "
                             "template (T1|T2|T3), question, key}; "
                             "/evidencebench/meta.json carries the "
                             "item-set hash and scoring rule",
        },
        "cli": {"install": "pip install yuclaw",
                "help": "yuclaw --help",
                "check_claim": "yuclaw check-claim --ticker X --type T "
                               "--date-range A..B  (or --text '...', or "
                               "--accession N alone when the accession maps to one name)",
                "replay": "yuclaw replay TICKER --date D",
                "reproduce": "yuclaw replay-lab"},
        "as_of_recipe": ("evidence as of D = evidence_objects with "
                         "available_as_of <= D; classification at D = "
                         "label_history last entry <= D; beyond the "
                         "ribbon: the replay CLI"),
        "not_advice": NOT_ADVICE}, indent=1))

    ledger_src = Path.home() / "yuclaw-trust" / "verified_research_ledger.jsonl"
    led_dir = _REPO / "docs" / "ledger"
    led_dir.mkdir(exist_ok=True)
    roots = []
    if ledger_src.exists():
        import hashlib
        for line in ledger_src.read_text().splitlines():
            e = json.loads(line)
            day = e["date"]
            root = hashlib.sha256(json.dumps(
                e["entries"], sort_keys=True).encode()).hexdigest()
            (led_dir / f"{day}.json").write_text(json.dumps({
                "date": day, "snapshot_count": e.get("snapshot_count"),
                "root_sha256": root,
                "entries": e["entries"],
                "verify": "recompute sha256 over the sorted entries and "
                          "compare; each entry's content_hash matches its "
                          "snapshot object",
                "not_advice": NOT_ADVICE}, indent=1))
            roots.append({"date": day, "root_sha256": root})
    (_REPO / "docs" / "evidence").mkdir(exist_ok=True)
    (_REPO / "docs" / "evidence" / "verify.json").write_text(json.dumps({
        "generated": datetime.now(timezone.utc).isoformat(),
        "how": ["fetch /ledger/{date}.json for the snapshot's date",
                "recompute sha256 over its sorted entries — must equal "
                "root_sha256",
                "the snapshot's content_hash must appear among entries",
                "offline: the same files ship in the repo and the ledger "
                "repo (YuClawLab/yuclaw-trust)"],
        "days": roots, "not_advice": NOT_ADVICE}, indent=1))


def main() -> int:
    n = build_all()
    build_endpoints()
    print(f"[why-json] {n} why/*.json schema-checked · capabilities + "
          f"verify + per-day ledger endpoints written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
