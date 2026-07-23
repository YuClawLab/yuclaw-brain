#!/usr/bin/env python3
"""
YUCLAW Protocol Registry — pre-registration + multiple-testing ledger (v1)
==========================================================================
Lab review §21 (protocol registry) + §26 (multiple-testing control), with the
REGISTRY-FIRST amendment: no mass diagnostic ships without an entry here.

Design (matches the ledger ethos):
  - Append-only chained JSONL: each line carries prev_hash; any edit or
    deletion breaks the chain -> tamper-evident, verifiable by anyone.
  - One PRIMARY endpoint per protocol (exactly one); everything else is
    SECONDARY/exploratory and counted in the test ledger.
  - Runs are recorded against protocols: data window, cells computed,
    result hash -> the §26 ledger aggregates cells per family and reports
    expected false positives + Bonferroni/BH corrections.
  - Engines call assert_registered() before computing on real data.
Stdlib only. Deterministic IDs.
"""
from __future__ import annotations
import hashlib, json, math, os, time
from dataclasses import dataclass, asdict
from typing import Optional

GENESIS = "yuclaw-protocol-registry-genesis"

def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

def protocol_id(spec_text: str, params: dict) -> str:
    return _h(spec_text + json.dumps(params, sort_keys=True))[:12]

# ------------------------------------------------------------------ records
@dataclass
class Protocol:
    protocol_id: str
    name: str
    method_hash: str            # hash of the estimator spec (e.g. b3c57f89...)
    spec_summary: str           # one-paragraph human summary
    primary_endpoint: str       # exactly one
    secondary_endpoints: list   # everything else, labeled
    lock_date: str              # ISO date; external anchor = git commit of entry
    version: int = 1
    status: str = "LOCKED"      # LOCKED | SUPERSEDED (never deleted)
    supersedes: Optional[str] = None

@dataclass
class Run:
    protocol_id: str
    run_date: str
    data_window: str            # e.g. "2026-05-20..2026-07-21 forward-OOS"
    n_primary_cells: int
    n_secondary_cells: int
    result_hash: str            # hash of the results artifact
    note: str = ""

# ------------------------------------------------------------------ registry
class Registry:
    """Chained JSONL store. Lines: {kind, payload, prev_hash, line_hash}."""

    def __init__(self, path: str):
        self.path = path
        self._lines = []
        if os.path.exists(path):
            with open(path) as f:
                self._lines = [json.loads(l) for l in f if l.strip()]
            self.verify_chain()

    # ---- chain
    def _tip(self) -> str:
        return self._lines[-1]["line_hash"] if self._lines else _h(GENESIS)

    def _append(self, kind: str, payload: dict):
        prev = self._tip()
        body = json.dumps({"kind": kind, "payload": payload,
                           "prev_hash": prev}, sort_keys=True)
        line = {"kind": kind, "payload": payload, "prev_hash": prev,
                "line_hash": _h(body)}
        with open(self.path, "a") as f:
            f.write(json.dumps(line, sort_keys=True) + "\n")
        self._lines.append(line)
        return line["line_hash"]

    def verify_chain(self) -> bool:
        prev = _h(GENESIS)
        for i, ln in enumerate(self._lines):
            if ln["prev_hash"] != prev:
                raise ValueError(f"chain broken at line {i}: prev_hash mismatch")
            body = json.dumps({"kind": ln["kind"], "payload": ln["payload"],
                               "prev_hash": ln["prev_hash"]}, sort_keys=True)
            if _h(body) != ln["line_hash"]:
                raise ValueError(f"chain broken at line {i}: line tampered")
            prev = ln["line_hash"]
        return True

    # ---- protocols
    def register(self, p: Protocol) -> str:
        if len(p.secondary_endpoints) < 0 or not p.primary_endpoint:
            raise ValueError("exactly one primary endpoint required")
        if self.get_protocol(p.protocol_id):
            raise ValueError(f"{p.protocol_id} already registered — "
                             "protocols are immutable; register a new version "
                             "with supersedes set")
        return self._append("protocol", asdict(p))

    def supersede(self, old_id: str, new: Protocol) -> str:
        old = self.get_protocol(old_id)
        if not old:
            raise ValueError(f"unknown protocol {old_id}")
        new.supersedes = old_id
        self._append("supersede_notice", {"protocol_id": old_id,
                                          "superseded_by": new.protocol_id,
                                          "date": new.lock_date})
        return self.register(new)

    def get_protocol(self, pid: str) -> Optional[dict]:
        latest = None
        superseded = {l["payload"]["protocol_id"] for l in self._lines
                      if l["kind"] == "supersede_notice"}
        for l in self._lines:
            if l["kind"] == "protocol" and l["payload"]["protocol_id"] == pid:
                latest = dict(l["payload"])
                latest["status"] = ("SUPERSEDED" if pid in superseded
                                    else latest["status"])
        return latest

    def assert_registered(self, pid: str):
        p = self.get_protocol(pid)
        if not p:
            raise RuntimeError(f"protocol {pid} not registered — "
                               "REGISTRY-FIRST rule: register before computing "
                               "on real data")
        if p["status"] != "LOCKED":
            raise RuntimeError(f"protocol {pid} is {p['status']}; use the "
                               "superseding version")
        return p

    # ---- runs
    def record_run(self, r: Run) -> str:
        self.assert_registered(r.protocol_id)
        return self._append("run", asdict(r))

    # ---- §26 multiple-testing ledger
    def test_ledger(self, alpha: float = 0.05) -> dict:
        per = {}
        for l in self._lines:
            if l["kind"] != "run": continue
            p = l["payload"]
            d = per.setdefault(p["protocol_id"],
                               {"runs": 0, "primary_cells": 0,
                                "secondary_cells": 0})
            d["runs"] += 1
            d["primary_cells"] += p["n_primary_cells"]
            d["secondary_cells"] += p["n_secondary_cells"]
        total_sec = sum(d["secondary_cells"] for d in per.values())
        return {
            "alpha": alpha,
            "per_protocol": per,
            "total_secondary_cells": total_sec,
            "expected_false_positives_at_alpha": round(total_sec * alpha, 2),
            "bonferroni_threshold": (alpha / total_sec) if total_sec else None,
            "note": ("secondary/exploratory cells only; each protocol's single "
                     "primary endpoint is tested at nominal alpha by design"),
        }

# ---- Benjamini–Hochberg helper (for when p-values are in hand)
def bh_significant(pvals: list, alpha: float = 0.05) -> list:
    """Returns boolean mask (original order) of BH-significant p-values."""
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    thresh_k = 0
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= rank / n * alpha:
            thresh_k = rank
    sig = [False] * n
    for rank, i in enumerate(order, start=1):
        if rank <= thresh_k: sig[i] = True
    return sig

# ---------------------------------------------------------------- selftest
def _selftest(tmp="/tmp/_reg_test.jsonl"):
    if os.path.exists(tmp): os.remove(tmp)
    reg = Registry(tmp)
    p1 = Protocol("826e82d83591", "Signal Decomposition Lab v1",
                  "b3c57f89911a57bb",
                  "Per-component C1-C9 diagnostics on forward-OOS panel",
                  "per-component IC at k=5",
                  ["quantile monotonicity", "partial IC", "marginal dIC",
                   "churn", "horizon decay", "placebo percentile"],
                  "2026-07-22")
    reg.register(p1)
    # T1: duplicate registration refused (immutability)
    try:
        reg.register(p1); raise AssertionError("T1 dup accepted")
    except ValueError: pass
    # T2: run against unregistered protocol refused
    try:
        reg.record_run(Run("deadbeef0000", "2026-07-23", "x", 1, 1, "h"))
        raise AssertionError("T2 unregistered run accepted")
    except RuntimeError: pass
    # T3: run recorded; ledger math
    reg.record_run(Run("826e82d83591", "2026-07-22",
                       "2026-05-20..2026-07-21 forward-OOS", 7, 33,
                       "resulthash1", "first real run"))
    led = reg.test_ledger()
    assert led["total_secondary_cells"] == 33
    assert abs(led["expected_false_positives_at_alpha"] - 1.65) < 1e-9
    # T4: chain tamper detection
    reg2 = Registry(tmp); reg2.verify_chain()
    lines = open(tmp).read().splitlines()
    bad = lines[:]; bad[0] = bad[0].replace("k=5", "k=6")
    open(tmp + ".bad", "w").write("\n".join(bad) + "\n")
    try:
        Registry(tmp + ".bad"); raise AssertionError("T4 tamper undetected")
    except ValueError: pass
    # T5: supersession — old refuses runs, new accepts
    p2 = Protocol(protocol_id("spec v2", {"k": 5}), "Signal Decomposition v2",
                  "newmethodhash", "v2 spec", "per-component IC at k=5",
                  ["decile spread"], "2026-08-20", version=2)
    reg2.supersede("826e82d83591", p2)
    try:
        reg2.record_run(Run("826e82d83591", "2026-08-21", "x", 1, 1, "h"))
        raise AssertionError("T5 superseded protocol accepted a run")
    except RuntimeError: pass
    reg2.record_run(Run(p2.protocol_id, "2026-08-21", "x", 7, 5, "h2"))
    # T6: BH helper sanity
    # correct BH by hand: thresholds .01/.02/.03/.04/.05 -> 0.04>0.03 fails
    sig = bh_significant([0.001, 0.02, 0.04, 0.6, 0.9])
    assert sig == [True, True, False, False, False], f"T6 BH mask {sig}"
    sig2 = bh_significant([0.001, 0.02, 0.029, 0.6, 0.9])
    assert sig2 == [True, True, True, False, False], f"T6b BH mask {sig2}"
    # T7: reload + chain verify after all operations
    Registry(tmp).verify_chain()
    return reg2

if __name__ == "__main__":
    reg = _selftest()
    print("[OK] T1 immutability · T2 registry-first enforcement · T3 ledger "
          "math · T4 tamper detection · T5 supersession · T6 BH · T7 chain")
    print(json.dumps(reg.test_ledger(), indent=1))
