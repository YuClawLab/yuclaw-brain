"""Derived evidence scoreboard and history (v7).

Built ONLY from records: the receipt store (real provenance), the legacy public log (via the adapter),
challenges and decisions. Columns are shown only when applicable; every column carries its counting
definition and the source timestamp; zero and pending states are displayed as such. Failures,
inconclusive and unresolved findings have equal visibility. No composite trust score, no financial
statistic. Program evidence (any release) is separate from exact-release evidence (bound bytes).
`history(a, b)` answers "what evidence or disposition changed between two snapshots" from the
snapshots themselves."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts import counting, export, legacy
from v3.receipts.challenge import ChallengeStore
from v3.receipts.decision import DecisionStore
from v3.receipts.store import Store

_REPO = Path(__file__).resolve().parents[2]
DEFINITIONS = {
    "witnesses": "people who examined the methodology and left a reviewable receipt (none recorded: 0)",
    "pilots": "BYOS pilot engagements with a signed scope (none: counsel review is the blocker)",
    "replications": "attempts to reproduce published artifacts; primary population = qualified attempts (failed/inconclusive retained); successful reported separately",
    "audits": "third-party audits with a receipt (internal gate runs are not audits)",
    "refusals": "recorded refusals/held submissions (visible, never hidden)",
    "packet_uses": "document-use receipts bound to an exact packet digest and exported with permission",
    "challenges": "structured challenges by disposition; adverse = OPEN or CONFIRMED; RESOLVED keeps the original finding",
}


def build(store_dir, *, synthetic: bool = False, registration: dict | None = None, now: datetime | None = None, legacy_log: Path | None = None) -> dict:
    st = Store(store_dir); cs = ChallengeStore(store_dir); ds = DecisionStore(store_dir)
    derived = counting.derive(st, synthetic=synthetic)
    c = counting.counts(derived, registration=registration)
    log_path = legacy_log or (_REPO / "docs/replication/replication_log.json")
    leg = legacy.adapt_log(json.loads(log_path.read_text())) if (log_path.exists() and not synthetic) else []
    chal = cs.public_view(synthetic=synthetic)
    by_disp = {}
    for r in chal: by_disp[r["disposition"]] = by_disp.get(r["disposition"], 0) + 1
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    rows = export.project_many(derived, st, mode=("synthetic" if synthetic else "public"))
    board = {
        "scoreboard_version": "v7-candidate-1", "synthetic": synthetic, "source_timestamp": ts, "definitions": DEFINITIONS,
        "columns": {
            "witnesses": {"count": 0, "state": "ZERO"},
            "pilots": {"count": 0, "state": "PENDING_COUNSEL_REVIEW"},
            "replications": {"attempts": c["attempts"], "qualified": c["qualified"], "successful": c["successful"], "visible": c["visible"],
                              "windows": c["windows"], "registration": c["registration"], "artifacts": c["artifacts"],
                              "program_evidence_legacy": {"entries": len(leg), "reproduced": sum(1 for l in leg if l["outcome"] == "REPRODUCED"),
                                                          "binding": "PREFIX_ONLY (historical; not exact-release evidence)", "affiliated": sum(1 for l in leg if l["relationship"] == "OWNER-AFFILIATED")},
                              "exact_release_evidence": {"successful_package_reproductions": c["artifacts"]["package_reproductions_successful"],
                                                         "note": "counts only qualified successful attempts whose exact wheel/sdist bytes were verified"},
                              "state": "PENDING_REGISTRATION" if c["registration"]["status"] == "PENDING" else "REGISTERED"},
            "audits": {"count": 0, "state": "ZERO"},
            "refusals": {"count": c["visible"]["unqualified"], "held": sum(1 for r in derived if (r.get("review") or {}).get("state") == "HELD"), "state": "OBSERVED"},
            "packet_uses": {"count": len(ds.export(synthetic=synthetic)), "state": "OBSERVED"},
            "challenges": {"by_disposition": by_disp, "adverse_open": sum(1 for r in chal if r["adverse"]), "total": len(chal), "state": "OBSERVED"},
        },
        "receipts_public": rows, "challenges_public": chal, "decisions_public": ds.export(synthetic=synthetic),
        "policy_version": c["policy_version"], "not_advice": "Research and education only. Not investment advice. No composite trust score is computed.",
    }
    return board


def history(a: dict, b: dict) -> dict:
    """What changed between two scoreboard snapshots (evidence and dispositions only)."""
    ra = {r["receipt_digest"]: r for r in a.get("receipts_public", [])}; rb = {r["receipt_digest"]: r for r in b.get("receipts_public", [])}
    ca = {c["challenge_id"]: c for c in a.get("challenges_public", [])}; cb = {c["challenge_id"]: c for c in b.get("challenges_public", [])}
    changed = [{"challenge_id": k, "from": ca[k]["disposition"], "to": cb[k]["disposition"]} for k in ca if k in cb and ca[k]["disposition"] != cb[k]["disposition"]]
    ma = a["columns"]["replications"]; mb = b["columns"]["replications"]
    return {"from": a["source_timestamp"], "to": b["source_timestamp"],
            "receipts_added": sorted(set(rb) - set(ra)), "receipts_removed_or_superseded": sorted(set(ra) - set(rb)),
            "challenges_added": sorted(set(cb) - set(ca)), "dispositions_changed": changed,
            "movement": counting.movement({"attempts": ma["attempts"], "qualified": ma["qualified"], "successful": ma["successful"]},
                                          {"attempts": mb["attempts"], "qualified": mb["qualified"], "successful": mb["successful"]})}


def load_public(path: Path) -> dict | None:
    """Read-only loader for deployed surfaces (API/MCP/site): a derived non-synthetic scoreboard file."""
    if not path.exists():
        return None
    board = json.loads(path.read_text())
    if board.get("synthetic") is not False:
        return None                          # a synthetic board is never served as public
    return board
