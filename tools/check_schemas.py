#!/usr/bin/env python3
"""
Schema gate (§7, 2026-08-04): validates TODAY'S REAL OUTPUTS against the
five frozen JSON Schemas in schemas/*.v1.json. A validation failure means
an artifact's shape drifted from its published contract — that is a chain
failure, not a schema edit; schemas change only by a new version file.

  S1  latest signal_snapshots row       vs SignalSnapshot.v1
  S2  latest 25 accepted events         vs EvidenceEvent.v1
  S3  every protocol payload in the
      canonical registry                vs ResearchProtocol.v1
  S4  every cell in the robustness
      profile artifact                  vs RobustnessCell.v1
  S5  ResearchMemo schema freshness: the frozen file must equal
      MemoOutput.model_json_schema() as post-processed by the generator
      (the memo object is validated at construction by pydantic itself)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import jsonschema
import psycopg2
import psycopg2.extras


def _load(name):
    return json.loads((_REPO / "schemas" / f"{name}.v1.json").read_text())


def main() -> int:
    problems = []

    snap_s = _load("SignalSnapshot")
    ev_s = _load("EvidenceEvent")
    proto_s = _load("ResearchProtocol")
    cell_s = _load("RobustnessCell")

    with psycopg2.connect("dbname=yuclaw_events") as cn:
        cn.set_session(readonly=True)
        with cn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""SELECT snapshot_id, ticker, signal_time,
                available_as_of, signal_label, total_score,
                c1_price_momentum, c2_volume_confirm, c3_sector_velocity,
                c4_macro_regime, c5_oil_rates_fx, c6_event_impact,
                c7_peer_correlation, c8_cascade_effect, c9_model_trust,
                evidence_event_ids, content_hash
                FROM signal_snapshots ORDER BY signal_time DESC LIMIT 1""")
            snap = dict(cur.fetchone())
            cur.execute("""SELECT event_id, ticker, event_type, magnitude,
                direction, available_as_of, source_type, source_url,
                llm_confidence, raw_excerpt FROM events
                WHERE event_status='accepted'
                ORDER BY available_as_of DESC LIMIT 25""")
            events = [dict(r) for r in cur.fetchall()]

    for label, obj, schema in (("S1 snapshot", snap, snap_s),):
        try:
            jsonschema.validate(json.loads(json.dumps(obj, default=str)),
                                schema)
        except jsonschema.ValidationError as exc:
            problems.append(f"{label}: {exc.message[:160]}")

    for i, e in enumerate(events):
        try:
            jsonschema.validate(json.loads(json.dumps(e, default=str)), ev_s)
        except jsonschema.ValidationError as exc:
            problems.append(f"S2 event[{i}] {e.get('event_id')}: "
                            f"{exc.message[:120]}")
            break

    n_proto = 0
    for line in (_REPO / "registry" / "protocols.jsonl").read_text(
            ).splitlines():
        entry = json.loads(line)
        if entry.get("kind") != "protocol":
            continue
        n_proto += 1
        try:
            jsonschema.validate(entry["payload"], proto_s)
        except jsonschema.ValidationError as exc:
            problems.append(f"S3 protocol "
                            f"{entry['payload'].get('protocol_id')}: "
                            f"{exc.message[:120]}")

    rp = json.loads((_REPO / "output" / "oie" /
                     "robustness_profile.json").read_text())
    n_cells = 0
    for lens, body in rp.items():
        if not isinstance(body, dict) or "cells" not in body:
            continue
        for cname, cell in body["cells"].items():
            n_cells += 1
            try:
                jsonschema.validate(cell, cell_s)
            except jsonschema.ValidationError as exc:
                problems.append(f"S4 cell {lens}/{cname}: "
                                f"{exc.message[:120]}")

    from tools.yuclaw_schemas import research_memo
    frozen = json.loads((_REPO / "schemas" / "ResearchMemo.v1.json"
                         ).read_text())
    if json.dumps(frozen, sort_keys=True) != json.dumps(
            research_memo(), sort_keys=True):
        problems.append("S5 ResearchMemo.v1.json no longer matches "
                        "MemoOutput.model_json_schema() — the memo object "
                        "shape drifted; freeze a v2, never edit v1")

    # ---- S6 vocabulary separation (Science Trust Protocol v1, order of
    # 2026-08-07d — active from registration). CONTEXT-AWARE: structured
    # field values only, never ordinary prose. (A) research-state
    # vocabulary is rejected in signal-label / score-label / trading-
    # classification / buy-sell / portfolio-action fields; (B) signal-
    # label vocabulary is rejected in the canonical research-state field.
    from tools.yuclaw_science_trust import RESEARCH_STATES
    from tools.yuclaw_discovery_ledger import LEDGER_ADJUDICATION_STATES
    from tools.yuclaw_anytime_record import ANYTIME_STATES
    from v3.web.useful_blocks import PUBLIC_LABELS
    # Discovery Ledger v1 (2026-08-10) + Anytime Evidence Record v1
    # (2026-08-11): ledger adjudication vocabulary and anytime states
    # live on the research-state axis — rejected in signal-context
    # fields exactly like research states.
    RESEARCH_AXIS = (RESEARCH_STATES | LEDGER_ADJUDICATION_STATES
                     | ANYTIME_STATES)
    SIGNAL_FIELD_KEYS = {"label", "signal_label", "signal", "score_label",
                         "classification", "trading_classification",
                         "action", "buy_sell", "portfolio_action"}
    RESEARCH_FIELD_KEYS = {"research_state", "science_trust_state"}
    n_vocab = 0

    def _s6_walk(obj, where):
        nonlocal n_vocab
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str):
                    val = v.upper()
                    if k in SIGNAL_FIELD_KEYS:
                        n_vocab += 1
                        if val in RESEARCH_AXIS:
                            problems.append(
                                f"S6 {where}: research state {v!r} used as "
                                f"signal-context field '{k}' — research "
                                f"states never translate to signal/score/"
                                f"trading meaning")
                    if k in RESEARCH_FIELD_KEYS:
                        n_vocab += 1
                        if val in PUBLIC_LABELS:
                            problems.append(
                                f"S6 {where}: signal label {v!r} used as "
                                f"canonical research-state field '{k}' — "
                                f"signal vocabulary never enters research "
                                f"states")
                else:
                    _s6_walk(v, where)
        elif isinstance(obj, list):
            for v in obj:
                _s6_walk(v, where)

    _s6_walk(json.loads(json.dumps(snap, default=str)), "snapshot")
    _s6_walk(json.loads((_REPO / "docs" / "explorer_data.json"
                         ).read_text()), "explorer_data.json")
    for wf in sorted((_REPO / "docs" / "why").glob("*.json")):
        _s6_walk(json.loads(wf.read_text()), f"why/{wf.name}")
    for line in (_REPO / "registry" / "protocols.jsonl").read_text(
            ).splitlines():
        _s6_walk(json.loads(line).get("payload", {}), "registry")
    _s6_walk(json.loads((_REPO / "registry" / "truncation_ledger.json"
                         ).read_text()), "truncation_ledger.json")
    _s6_walk(json.loads((_REPO / "registry" / "discovery_ledger.json"
                         ).read_text()), "discovery_ledger.json")
    _s6_walk(json.loads((_REPO / "registry" / "anytime_record.json"
                         ).read_text()), "anytime_record.json")
    _s6_walk(json.loads((_REPO / "registry" / "completeness_profile.json"
                         ).read_text()), "completeness_profile.json")
    _s6_walk(json.loads((_REPO / "registry" / "research_state.json"
                         ).read_text()), "research_state.json")

    if problems:
        print("SCHEMA GATE FAILED:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(f"[schema-gate] OK — snapshot, {len(events)} events, "
          f"{n_proto} protocols, {n_cells} robustness cells validate "
          f"against the frozen v1 schemas; memo schema fresh; "
          f"vocabulary separation clean over {n_vocab} labeled fields")
    return 0


if __name__ == "__main__":
    sys.exit(main())
