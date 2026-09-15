"""ONE shared public coverage artifact (QA-01, 2026-09-15): docs/coverage.json.

Evidence Coverage v1 (registered protocol e3d51f5b0ca3) is computed once per build into the private artifact
output/oie/evidence_coverage.json. Every public surface that displays the coverage score (homepage table,
Explorer HTML/JSON, Why HTML/JSON) reads THIS public projection — never the private artifact directly — so all
surfaces built in one run carry the same values and the same identity (as_of + sha256 of the source artifact).
Renderers embed that identity next to the values; tools/check_coverage_consistency.py joins every surface on
(ticker, metric_id, as_of, source_sha256) and fails on any unexplained same-metric difference."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
PRIVATE = _REPO / "output" / "oie" / "evidence_coverage.json"
PUBLIC = _REPO / "docs" / "coverage.json"
SCHEMA = "coverage/1"
METRIC_ID = "ecs"
COMPONENTS = ("events_90d", "recency_days", "type_diversity", "substrate_active")


def publish(private: Path = PRIVATE, public: Path = PUBLIC, now: datetime | None = None) -> dict:
    """Project the private artifact into the public shared artifact (public-safe fields only)."""
    raw = private.read_bytes()
    art = json.loads(raw)
    from v3.universe_tiers import scoring_universe
    universe = sorted(scoring_universe())
    scores = art.get("scores", {})
    tickers = {}
    for t in universe:
        s = scores.get(t)
        if not isinstance(s, dict):
            continue
        row = {"ecs": s.get("ecs")}
        for c in COMPONENTS:
            if c in s:
                row[c] = s[c]
        tickers[t] = row
    doc = {
        "schema": SCHEMA,
        "metric_id": METRIC_ID,
        "metric_label": "Evidence coverage (ECS, 0–100)",
        "definition": art.get("caption", "how much evidence stands under this classification — coverage, not prediction"),
        "basis": {"protocol_id": art.get("protocol_id"), "method_hash": art.get("method_hash"), "window_days": 90,
                  "components": list(COMPONENTS), "note": "coverage, not prediction; recency_days moves with the clock, so the value is bound to as_of"},
        "as_of": art.get("as_of"),
        "source_identity": {"artifact": "evidence_coverage.json", "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)},
        "generated_at": (now or datetime.now(timezone.utc)).isoformat(),
        "ticker_set": {"source": "v3/universe.json scoring tier (bound universe artifact)", "count": len(universe), "missing_from_artifact": sorted(set(universe) - set(tickers))},
        "tickers": tickers,
        "not_advice": "Research and education only — not investment advice. Coverage is not a prediction.",
    }
    public.parent.mkdir(parents=True, exist_ok=True)
    public.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    return doc


def read(public: Path = PUBLIC) -> dict:
    """The shared artifact as renderers consume it: {'identity': {...}, 'scores': {ticker: {...}}}.
    Missing/invalid → empty scores with identity None (surfaces then show '—', never a stale number)."""
    try:
        doc = json.loads(public.read_text())
        if doc.get("schema") != SCHEMA or doc.get("metric_id") != METRIC_ID:
            return {"identity": None, "scores": {}}
        return {"identity": {"as_of": doc["as_of"], "source_sha256": doc["source_identity"]["sha256"], "metric_id": METRIC_ID}, "scores": doc["tickers"]}
    except (OSError, ValueError, KeyError):
        return {"identity": None, "scores": {}}


def identity_attrs(identity: dict | None) -> str:
    """HTML data attributes that bind a rendered table to the artifact instance it was rendered from."""
    if not identity:
        return 'data-coverage-metric="ecs" data-coverage-as-of="" data-coverage-sha256=""'
    return (f'data-coverage-metric="{identity["metric_id"]}" data-coverage-as-of="{identity["as_of"]}" '
            f'data-coverage-sha256="{identity["source_sha256"]}"')


if __name__ == "__main__":
    d = publish()
    print(f"[coverage-public] wrote {PUBLIC} ({len(d['tickers'])} tickers; as_of {d['as_of']}; source sha256 {d['source_identity']['sha256'][:12]}…)")
