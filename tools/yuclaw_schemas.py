#!/usr/bin/env python3
"""
API object standardization (§7) — the five frozen JSON Schemas, DERIVED
from the actual current artifacts, never invented:

  SignalSnapshot   — a live signal_snapshots row (the ledger-hashed object)
  EvidenceEvent    — one element of the `yuclaw events --json` export
  ResearchProtocol — a protocol payload line of registry/protocols.jsonl
  RobustnessCell   — one cell of output/oie/robustness_profile.json
  ResearchMemo     — v4.memo.generator.MemoOutput.model_json_schema()

`generate` writes schemas/<Name>.v1.json (versioned, $id-stamped).
Freezing = committing those files; any regeneration that would change a
frozen file is a signal that the artifact shape drifted — that is exactly
what tools/check_schemas.py exists to catch, from the other direction
(today's real outputs validated against the frozen schemas).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

OUT = _REPO / "schemas"
BASE_ID = "https://yuclaw.ca/schemas"

SNAPSHOT_NUMERIC = [f"c{i}_{n}" for i, n in enumerate(
    ("price_momentum", "volume_confirm", "sector_velocity", "macro_regime",
     "oil_rates_fx", "event_impact", "peer_correlation", "cascade_effect",
     "model_trust"), start=1)]


def _schema(name: str, description: str, properties: dict, required: list,
            additional=True) -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"{BASE_ID}/{name}.v1.json",
        "title": name, "version": "v1",
        "description": description + " Research classifications, not "
        "buy/sell recommendations; research and education only.",
        "type": "object", "properties": properties, "required": required,
        "additionalProperties": additional,
    }


def signal_snapshot() -> dict:
    props = {
        "snapshot_id": {"type": "string", "pattern": "^snap_"},
        "ticker": {"type": "string"},
        "signal_time": {"type": "string"},
        "available_as_of": {"type": "string",
                            "description": "point-in-time visibility bound"},
        "signal_label": {"type": "string", "enum": [
            "STRONG_BULLISH", "BULLISH", "NEUTRAL", "WATCH", "WEAKENING",
            "NEGATIVE_EVENT", "BEARISH_WATCH", "RISK_ALERT"]},
        "total_score": {"type": "number"},
        "evidence_event_ids": {"type": ["array", "null"],
                               "items": {"type": "string"}},
        "content_hash": {"type": "string",
                         "description": "SHA-256 anchored in the daily "
                                        "ledger root"},
    }
    for c in SNAPSHOT_NUMERIC:
        props[c] = {"type": ["number", "null"]}
    return _schema(
        "SignalSnapshot",
        "One point-in-time composite signal snapshot — the object whose "
        "content_hash is committed to the public ledger.",
        props,
        ["snapshot_id", "ticker", "signal_time", "available_as_of",
         "signal_label", "total_score", "content_hash"])


def evidence_event() -> dict:
    return _schema(
        "EvidenceEvent",
        "One accepted evidence event as exported by `yuclaw events --json` "
        "— derived data tracing to a primary SEC filing.",
        {
            "event_id": {"type": "string"},
            "ticker": {"type": "string"},
            "event_type": {"type": "string"},
            "magnitude": {"type": "number", "minimum": 0, "maximum": 1},
            "direction": {"type": "integer", "enum": [-1, 0, 1]},
            "available_as_of": {"type": "string"},
            "source_type": {"type": "string",
                            "description": "SEC form type (8-K, 6-K, 4, ...)"},
            "source_url": {"type": "string", "format": "uri"},
            "llm_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "raw_excerpt": {"type": "string"},
        },
        ["event_id", "ticker", "event_type", "magnitude", "direction",
         "available_as_of", "source_type", "source_url"])


def research_protocol() -> dict:
    return _schema(
        "ResearchProtocol",
        "One protocol payload from the append-only hash-chained registry "
        "(registry/protocols.jsonl, kind=protocol) — a statistic's "
        "specification locked BEFORE computation.",
        {
            "protocol_id": {"type": "string", "pattern": "^[0-9a-f]{12}$"},
            "name": {"type": "string"},
            "method_hash": {"type": "string", "pattern": "^[0-9a-f]{16}$"},
            "spec_summary": {"type": "string"},
            "primary_endpoint": {"type": "string"},
            "secondary_endpoints": {"type": "array",
                                    "items": {"type": "string"}},
            "lock_date": {"type": "string", "format": "date"},
            "version": {"type": "integer"},
            "status": {"type": "string", "enum": ["LOCKED", "SUPERSEDED"]},
            "supersedes": {"type": ["string", "null"]},
        },
        ["protocol_id", "name", "method_hash", "spec_summary",
         "primary_endpoint", "lock_date", "status"])


def robustness_cell() -> dict:
    s = _schema(
        "RobustnessCell",
        "One cell of a Robustness Profile grid "
        "(output/oie/robustness_profile.json) — where a result holds or "
        "breaks, printed as measured. A cell may be null: structurally "
        "uncomputable slices (e.g. trend split before the SPY series "
        "begins) are disclosed as empty, never proxied.",
        {
            "estimate": {"type": ["number", "null"]},
            "ci": {"type": ["array", "null"], "items": {"type": "number"},
                   "minItems": 2, "maxItems": 2},
            "n": {"type": ["integer", "null"]},
            "G": {"type": ["integer", "null"],
                  "description": "independent clusters behind n"},
            "badge": {"type": ["string", "null"]},
            "note": {"type": "string"},
        },
        [])
    s["type"] = ["object", "null"]
    return s


def research_memo() -> dict:
    from v4.memo.generator import MemoOutput
    s = MemoOutput.model_json_schema()
    s["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    s["$id"] = f"{BASE_ID}/ResearchMemo.v1.json"
    s["title"] = "ResearchMemo"
    s["version"] = "v1"
    s["description"] = ((s.get("description") or "") +
                        " Derived directly from v4.memo.generator."
                        "MemoOutput (pydantic model_json_schema). Research "
                        "classifications, not buy/sell recommendations.")
    return s


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for fn in (signal_snapshot, evidence_event, research_protocol,
               robustness_cell, research_memo):
        s = fn()
        path = OUT / f"{s['title']}.v1.json"
        path.write_text(json.dumps(s, indent=1, sort_keys=True) + "\n")
        print(f"[schemas] wrote {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
