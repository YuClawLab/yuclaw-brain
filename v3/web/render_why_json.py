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
    eo_schema = json.loads((_REPO / "schemas" /
                            "EvidenceObject.v1.json").read_text())
    wa_schema = json.loads((_REPO / "schemas" /
                            "WhyAnatomy.v1.json").read_text())
    stamp = datetime.now(timezone.utc).isoformat()
    n = 0
    for tk, snap in sorted(snaps.items()):
        _t, label, score, st, *comps = snap
        objs = evidence_objects(tk, limit=100)
        pub = [{k: v for k, v in o.items() if not k.startswith("_")}
               for o in objs]
        doc = {
            "ticker": tk, "generated": stamp,
            "label": label, "score": round(float(score), 4),
            "threshold_band": _band(float(score), label),
            "components": {f"c{i}": (float(v) if v is not None else None)
                           for i, v in enumerate(comps, 1)},
            "evidence_coverage": ecs.get(tk, {}),
            "evidence_objects": pub,
            "label_history": [{"date": d.isoformat(), "label": l}
                              for d, l in hist.get(tk, [])],
            "as_of_recipe": ("evidence as of D = objects with "
                             "available_as_of <= D; classification at D = "
                             "label_history entry for the last date <= D; "
                             "older dates: yuclaw replay "
                             f"{tk} --date D"),
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
    return n


def _pkg_version() -> str:
    """The package version at generation time — capabilities.json can
    never advertise a stale hardcoded version again (v5.3.3). ONE
    source: v3.web.useful_blocks (the header badge and citation
    snippets derive from the same function since 2026-08-06)."""
    from v3.web.useful_blocks import _pkg_version as pv
    return pv()


def build_endpoints() -> None:
    base = "https://yuclaw.ca"
    (_REPO / "docs" / "capabilities.json").write_text(json.dumps({
        "name": "YUCLAW Ground Truth API",
        "version": f"v{_pkg_version()}", "generated":
            datetime.now(timezone.utc).isoformat(),
        "positioning": "The open evidence layer for financial AI.",
        "endpoints": {
            "discovery": f"{base}/capabilities.json",
            "index": f"{base}/evidence_index.json",
            "llms": f"{base}/llms.txt",
            "why_json": f"{base}/why/{{TICKER}}.json",
            "why_html": f"{base}/why/{{TICKER}}.html",
            "explorer_data": f"{base}/explorer_data.json",
            "schemas": f"{base}/schemas/{{Name}}.v1.json",
            "verify": f"{base}/evidence/verify.json",
            "ledger_day": f"{base}/ledger/{{YYYY-MM-DD}}.json",
            "evidencebench": f"{base}/evidencebench/items.jsonl",
            "c6_posture_current": f"{base}/c6_posture_current.json",
            "evidence_changes_day": f"{base}/evidence_changes/{{YYYY-MM-DD}}.json",
        },
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
                "check_claim": "yuclaw check-claim --ticker X --type T "
                               "--date-range A..B  (or --text '...')",
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
