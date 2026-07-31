#!/usr/bin/env python3
"""
Factual alert engine (E-tranche) — GENERATION ONLY. No delivery channel is
wired: [COUNSEL] delivery of alerts to any external party is a counsel
decision (channel, framing, disclaimers) and is deliberately absent here.
Alerts land in the box-local internal queue (internal/alerts/queue/,
gitignored) and nowhere else.

Fact classes watched (diff vs the previous run's state):
  A1 C6 risk-channel posture change (new artifact, or flag change per ticker)
  A2 admission-verdict change for any lens with a recorded facts artifact
  A3 new research-question status in the registry
Every alert is a factual statement with its source artifact named — no
interpretation, no direction, no recommendation language.
"""
from __future__ import annotations

import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

STATE = _REPO / "internal" / "alerts" / "state_prev.json"
QUEUE = _REPO / "internal" / "alerts" / "queue"


def current_state() -> dict:
    c6 = {}
    for f in sorted(glob.glob(str(_REPO / "output/swarm/canada/*.json"))):
        d = json.loads(Path(f).read_text())
        rc = d.get("risk_channel") or {}
        if d.get("ticker") and rc.get("flag"):
            c6[d["accession_number"]] = {"ticker": d["ticker"],
                                         "flag": str(rc["flag"])}
    admissions = {}
    so = _REPO / "output" / "oie" / "sector_overlap.json"
    if so.exists():
        admissions["XLK"] = json.loads(so.read_text())["xlk_pilot"]["verdict"]["label"]
    sl = _REPO / "output" / "oie" / "smh_lens_run.json"
    if sl.exists():
        admissions["SMH"] = json.loads(sl.read_text())["verdict"]["label"]
    from yuclaw_protocol_registry import Registry
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    questions = {k: v["status"] for k, v in reg.questions().items()}
    return {"c6": c6, "admissions": admissions, "questions": questions}


def main() -> int:
    QUEUE.mkdir(parents=True, exist_ok=True)
    prev = json.loads(STATE.read_text()) if STATE.exists() else \
        {"c6": {}, "admissions": {}, "questions": {}}
    cur = current_state()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    alerts = []
    for acc, v in cur["c6"].items():
        if acc not in prev["c6"]:
            alerts.append({"class": "A1", "fact": f"new C6 risk-channel "
                           f"artifact for {v['ticker']}: flag={v['flag']}",
                           "source": f"output/swarm/canada/{acc}.json"})
        elif prev["c6"][acc]["flag"] != v["flag"]:
            alerts.append({"class": "A1", "fact": f"C6 flag change for "
                           f"{v['ticker']}: {prev['c6'][acc]['flag']} -> "
                           f"{v['flag']}",
                           "source": f"output/swarm/canada/{acc}.json"})
    for lens, label in cur["admissions"].items():
        if prev["admissions"].get(lens) not in (None, label):
            alerts.append({"class": "A2", "fact": f"admission verdict change "
                           f"for {lens}: {prev['admissions'][lens]} -> {label}",
                           "source": "output/oie"})
    for qid, st in cur["questions"].items():
        if prev["questions"].get(qid) not in (None, st):
            alerts.append({"class": "A3", "fact": f"research question "
                           f"'{qid}' status: {prev['questions'][qid]} -> {st}",
                           "source": "registry/protocols.jsonl"})
    for i, a in enumerate(alerts):
        a["generated_utc"] = ts
        (QUEUE / f"{ts}_{a['class']}_{i}.json").write_text(
            json.dumps(a, indent=1))
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(cur, indent=1))
    print(f"[alerts] {len(alerts)} alert(s) queued (internal only; delivery "
          "is [COUNSEL]-gated and unwired)")
    for a in alerts:
        print(f"  {a['class']}: {a['fact']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
