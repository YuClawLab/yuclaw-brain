"""EvidenceSnapshot/1 — a stable, digest-identified reading of the v8 claims a brief depends on.

A brief is composed from a snapshot, never from "whatever the journal says now": the snapshot records the v8 tip it was
read at, every cited claim version with its digest, the outcome, the sources with their effective availability and
correction chain, and the v8 calculator's results. Later v8 events (an amendment, a withdrawal, a corrected availability,
a new outcome) do not change the snapshot; `dependency_review` compares the live state with it and names what the brief's
recorded dependencies now need reviewed. Reading a snapshot never mutates v8.
"""
from __future__ import annotations

from v3.receipts.contracts import ContractError, canonical_json, digest
from v8.workbench import availability, calc
from v8.workbench.store import Workspace
from v9.brief import contracts
from v9.brief.contracts import EVIDENCE_SNAPSHOT

MAX_CLAIMS = 32


def _source_entry(src: dict, idx: dict, seen: dict) -> dict:
    sid = availability.source_id(src)
    ent = idx.get(sid) or {}
    return {"source_id": sid, "source_hash": src["source_hash"], "kind": src["kind"], "form": src["form"], "accession": src["accession"], "url": src.get("url"),
            "filed_at": src["filed_at"], "registered_available_as_of": src["available_as_of"], "effective_available_as_of": ent.get("effective") or src["available_as_of"],
            "corrections": [c["payload"]["correction_id"] for c in ent.get("applied", [])], "observed_at": seen.get(sid), "rights": src["rights"], "fictional": src["fictional"],
            "excerpt": src["excerpt"], "excerpt_bytes": len(src["excerpt"].encode("utf-8"))}


def build(ws: Workspace, claim_ids: list[str]) -> dict:
    if not claim_ids or len(claim_ids) > MAX_CLAIMS:
        raise ContractError(f"a snapshot names 1..{MAX_CLAIMS} claims")
    st8 = ws.load()
    if st8["torn_tail"]:
        raise ContractError("the v8 journal has a torn tail; recover it before taking a snapshot")
    evs = st8["events"]; idx = availability.index(evs)
    seen = {e["payload"]["source_id"]: e["time"]["observed_at"] for e in evs if e["kind"] == "SOURCE_REGISTERED"}
    claims = {}
    for cid in dict.fromkeys(claim_ids):
        st = ws.claim_state(cid)
        if st is None:
            raise ContractError(f"claim {cid!r} is not frozen in this workspace")
        results = calc.adjudicate(st)
        orig_eff = next((v for v in reversed(st["versions"]) if v["type"] == "CORRECTED_SOURCE"), st["versions"][0])
        revised = [v for v in st["versions"] if v["type"] == "REVISED"]
        sources, cited = {}, []
        for v in st["versions"]:
            cited.append(v["claim"]["source"])
        if st["outcome"] is not None:
            cited.append(st["outcome"]["source"])
        if st["withdrawn"] is not None:
            cited.append(st["withdrawn"]["source"])
        for s in cited:
            e = _source_entry(s, idx, seen); sources[e["source_id"]] = e
        blk = availability.block(st)
        claims[cid] = {"claim_id": cid,
                       "versions": [{"version_id": v["version_id"], "type": v["type"], "claim_digest": v["claim"]["_digest"], "event_hash": v["event_hash"], "time": v["time"],
                                     "claim": {k: x for k, x in v["claim"].items() if not k.startswith("_")}} for v in st["versions"]],
                       "current_version": st["current"]["version_id"], "original_effective_version": orig_eff["version_id"], "revised_versions": [v["version_id"] for v in revised],
                       "withdrawn": None if st["withdrawn"] is None else {"revision_id": st["withdrawn"]["revision_id"], "event_hash": st["withdrawn"]["event_hash"], "source_id": availability.source_id(st["withdrawn"]["source"])},
                       "outcome": None if st["outcome"] is None else {"outcome_digest": st["outcome"]["_digest"], "event_hash": st["outcome"]["_event_hash"],
                                                                      "outcome": {k: x for k, x in st["outcome"].items() if not k.startswith("_")}},
                       "sources": sources, "results": results, "comparison": calc.compare_versions(orig_eff["claim"], revised[-1]["claim"]) if revised else None,
                       "availability_review": None if blk is None else {"needs_review": blk["needs_review"], "review": blk["review"], "corrected_result": blk["corrected_view"]["result"]},
                       "adjudications": [{"label": a["label"], "disputed": a["disputed"], "reviewer": a["reviewer"], "event_hash": a["event_hash"]} for a in st["adjudications"]],
                       "event_count": len(st["events"])}
    snap = {"schema": EVIDENCE_SNAPSHOT, "workspace_id": ws.meta["workspace_id"], "v8_tip": st8["tip"], "v8_seq": len(evs), "claims": claims,
            "semantics": {"time": "registered_available_as_of = the availability as registered; effective_available_as_of = after linked corrections at snapshot time; observed_at = when this workspace first saw the passage",
                          "stability": "a snapshot is read once at the recorded v8 tip; later v8 events never change it — dependency_review names what they affect"}}
    snap["snapshot_digest"] = digest(snap)
    return snap


def public_view(snap: dict) -> dict:
    """The rights-filtered snapshot for a packet: excerpt bytes travel only for BUNDLE_RIGHTS; digests always."""
    out = {k: v for k, v in snap.items() if k != "claims"}
    out["claims"] = {}
    for cid, c in snap["claims"].items():
        cc = dict(c); srcs = {}
        for sid, s in c["sources"].items():
            s2 = dict(s)
            if s["rights"] not in contracts.BUNDLE_RIGHTS:
                s2["excerpt"] = None; s2["excerpt_withheld"] = f"rights {s['rights']}: excerpt bytes are not bundled (redistribution rights not established); the digest still binds them"
            srcs[sid] = s2
        cc["sources"] = srcs
        vers = []
        for v in c["versions"]:
            v2 = dict(v); cl = dict(v["claim"])
            if cl["source"]["rights"] not in contracts.BUNDLE_RIGHTS:
                cl["source"] = dict(cl["source"], excerpt=None, excerpt_redacted=True)
            v2["claim"] = cl; vers.append(v2)
        cc["versions"] = vers
        if cc.get("outcome") and cc["outcome"]["outcome"]["source"]["rights"] not in contracts.BUNDLE_RIGHTS:
            o = dict(cc["outcome"]); oo = dict(o["outcome"]); oo["source"] = dict(oo["source"], excerpt=None, excerpt_redacted=True); o["outcome"] = oo; cc["outcome"] = o
        out["claims"][cid] = cc
    return out


def dependency_review(ws: Workspace, snap: dict) -> list[dict]:
    """What changed in v8 since the snapshot, per recorded dependency. Each finding names the dependency (claim or source id)
    so the reducer can mark exactly the statements whose evidence links reference it. Nothing is inferred beyond the
    recorded links: a statement with no link to a changed object is not flagged."""
    findings = []
    st8 = ws.load(); evs = st8["events"]; idx = availability.index(evs)
    for cid, c in snap["claims"].items():
        st = ws.claim_state(cid)
        if st is None:
            findings.append({"reason": "CLAIM_AMENDED", "dependency": f"claim:{cid}", "detail": "the claim is no longer readable in this workspace"}); continue
        old = {v["version_id"]: v["claim_digest"] for v in c["versions"]}
        for v in st["versions"]:
            if v["version_id"] not in old:
                findings.append({"reason": "CLAIM_AMENDED", "dependency": f"claim:{cid}", "detail": f"new version {v['version_id']} ({v['type']}) recorded {v['time']['recorded_at']} after the snapshot",
                                 "version_id": v["version_id"]})
            elif old[v["version_id"]] != v["claim"]["_digest"]:
                findings.append({"reason": "CLAIM_AMENDED", "dependency": f"claim:{cid}", "detail": f"version {v['version_id']} digest differs from the snapshot (journal divergence)", "version_id": v["version_id"]})
        if st["withdrawn"] is not None and c.get("withdrawn") is None:
            findings.append({"reason": "CLAIM_WITHDRAWN", "dependency": f"claim:{cid}", "detail": f"withdrawal {st['withdrawn']['revision_id']} recorded after the snapshot"})
        new_out = None if st["outcome"] is None else st["outcome"]["_digest"]; old_out = None if c.get("outcome") is None else c["outcome"]["outcome_digest"]
        if new_out != old_out:
            findings.append({"reason": "OUTCOME_CHANGED", "dependency": f"claim:{cid}", "detail": "the recorded outcome differs from the snapshot (new or superseded outcome)"})
        for sid, s in c["sources"].items():
            ent = idx.get(sid)
            eff = (ent or {}).get("effective") or s["registered_available_as_of"]
            if eff != s["effective_available_as_of"]:
                newc = [x["payload"]["correction_id"] for x in (ent or {}).get("applied", []) if x["payload"]["correction_id"] not in s["corrections"]]
                findings.append({"reason": "SOURCE_AVAILABILITY_CORRECTED", "dependency": f"source:{sid}", "detail": f"effective availability {s['effective_available_as_of']} → {eff} (corrections {newc})", "corrections": newc})
    return findings


def snapshot_bytes(snap: dict) -> bytes:
    return canonical_json(snap)
