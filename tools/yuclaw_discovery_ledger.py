#!/usr/bin/env python3
"""
DISCOVERY LEDGER v1 — Science Trust addendum (registered method spec).
Adjudication UNCOMPUTED · counting ACTIVE (order of 2026-08-10).
===========================================================================
First registered addendum under SCIENCE TRUST PROTOCOL v1 (protocol
be8b34040c2e), which named the Discovery Ledger as a future component,
UNCOMPUTED / METHOD NOT REGISTERED until its own addendum. This module IS
that addendum: the complete method text below is in-hash. The counting
machinery (identity assignment, deterministic status derivation, family
construction, counters, derived artifact) is ACTIVE from registration;
every adjudication path (BH family control, maturity reads) REFUSES until
its own registered read. registry/discovery_ledger.json is DERIVED — never
hand-maintained; the chain gate rebuilds it from the canonical chain and
fails on any divergence.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
CHAIN = _REPO / "registry" / "protocols.jsonl"
LEDGER_PATH = _REPO / "registry" / "discovery_ledger.json"

# Umbrella this addendum registers under (Science Trust Protocol v1).
UMBRELLA_PROTOCOL_ID = "be8b34040c2e"

# Ledger status vocabulary (research-state axis; never signal labels).
LEDGER_STATUSES = {
    "REGISTERED", "OPEN", "ACCRUING", "MATURED",
    "SUPPORTED", "NOT_SUPPORTED", "INCONCLUSIVE", "SUPERSEDED",
}
# Family-aware adjudication output vocabulary (research-state axis ONLY,
# covered by schema-gate S6 in both directions; never signal labels).
LEDGER_ADJUDICATION_STATES = {
    "NOMINAL_ONLY", "SURVIVED_FAMILY_CONTROL", "NOT_APPLICABLE",
}
# Verdict tokens admissible from run-note markers (verbatim mapping).
VERDICT_TOKENS = {"SUPPORTED", "NOT_SUPPORTED", "INCONCLUSIVE"}

PURPOSE_LINE = ("No result is presented as though the related tests "
                "were never run.")

METHOD_SPEC = """
DISCOVERY LEDGER v1 (Science Trust addendum, locked 2026-08-10)

STATUS
Adjudication UNCOMPUTED. Counting ACTIVE. Registered as an addendum under
SCIENCE TRUST PROTOCOL v1 (protocol be8b34040c2e), which named the
Discovery Ledger as a future component admissible only through its own
registered addendum with full method text. This is that addendum; the
full method is this text.

PURPOSE
No result is presented as though the related tests were never run.
The ledger gives every registered hypothesis a permanent identity, a
deterministic research status, an immutable discovery-family membership,
and family-level error control — so that any single result is always
read against the full set of related attempts.

HYPOTHESIS IDENTITY
Population: every line of the canonical chain (registry/protocols.jsonl)
with kind = "protocol", in chain order. Each such line is exactly one
registered hypothesis; each registered hypothesis is exactly one such
line (the LEDGER-RECONCILIATION gate enforces this bijection in both
directions). Run, supersede_notice, question, and question_status lines
are auxiliary: runs and supersessions attach to hypotheses through
protocol_id; questions are research questions, not hypotheses.

hypothesis_id = "H-YYYY-NNNNNN" where YYYY is the year of the protocol
line's lock_date and NNNNNN is the 1-based ordinal of the protocol line
among all kind="protocol" lines in chain order, zero-padded to six
digits. The ordinal is global and permanent: future registrations
continue the sequence; supersession never renumbers.

Identity fields, all derived by counting (copied verbatim, never
paraphrased, never estimated):
  hypothesis_id; claim (= primary_endpoint verbatim); registered_at
  (= lock_date); universe, population, horizon (copied only from
  same-named locked fields in the source payload; absent fields print
  NOT_DECLARED_IN_SOURCE_LINE — backfill never parses prose);
  evidence_family; parent_family (= evidence_family of the protocol this
  one supersedes, else null); protocol_id; method_hash; name; version;
  chain_line (1-based); status; maturity (NOT_DECLARED_IN_SOURCE_LINE at
  backfill; set only by a registered read); family_q; family_adjudication
  (PENDING until the family's first post-registration read);
  verdict_annotation (full run note verbatim when a verdict marker
  exists, else null); result_lineage (every run line and supersession
  notice touching this protocol_id, in chain order, fields verbatim).

STATUS VOCABULARY
REGISTERED / OPEN / ACCRUING / MATURED / SUPPORTED / NOT_SUPPORTED /
INCONCLUSIVE / SUPERSEDED. Research-state axis only; never signal
labels, score labels, trading classifications, buy/sell fields, or
portfolio actions (schema-gate S6, both directions).

DETERMINISTIC STATUS DERIVATION (first matching rule wins; zero
recomputation, zero re-adjudication, zero paraphrase):
  1. SUPERSEDED — a supersede_notice line names this protocol_id. The
     superseding hypothesis carries the lineage; any verdict recorded
     before supersession is preserved verbatim in result_lineage.
  2. VERDICT — the latest run line for this protocol_id whose note
     contains the exact marker "Verdict: " followed by a token in
     {SUPPORTED, NOT_SUPPORTED, INCONCLUSIVE}: status = that token
     verbatim; verdict_annotation = the full note verbatim. Existing
     verdicts (e.g. the C6 OOS INCONCLUSIVE with its exact printed
     annotation) map verbatim — never re-adjudicated, never
     paraphrased. Any other token after the marker fails the build
     (fail closed; no silent coercion).
  3. REGISTERED — the protocol name contains "sleeping" or "UNCOMPUTED"
     (sleeping / umbrella / governance registrations: locked without
     computing).
  4. ACCRUING — at least one run line exists for this protocol_id.
  5. OPEN — otherwise (locked, active, no run yet).
MATURED, SUPPORTED, and NOT_SUPPORTED beyond rule 2 arise only from a
future registered read; the backfill can never produce them by
construction.

DISCOVERY FAMILIES
Every hypothesis declares its discovery family AT registration;
membership is immutable except by supersession with lineage (the
FAMILY-LOCK gate fails the chain on any other membership change).

ANTI-GERRYMANDER RULE (both directions): no retroactive family
construction to rescue a result, and no retroactive family inflation to
bury one. Families exist before results are read; regrouping ships only
as a supersession line with explicit lineage.

BACKFILL FAMILY RULE (structural, results-blind, counting-only): the
family of a backfilled hypothesis is its supersession-lineage root —
follow the supersedes pointer to the root protocol line, then derive
  family_key = slug(root name) where slug =
    (a) strip any parenthetical suffix starting at " (";
    (b) strip a trailing version token matching \\s+v\\d+(\\.\\d+)*$;
    (c) lowercase;
    (d) replace every maximal run of non-alphanumeric characters with a
        single hyphen; strip leading/trailing hyphens.
This rule references chain text only — never results — so it can
neither rescue nor bury: it is the minimal family structure already
present in the chain. Future registrations declare richer families
explicitly at registration time.

FAMILY-LEVEL ERROR CONTROL (deterministic; UNCOMPUTED until each
family's first post-registration read)
Within each family: Benjamini-Hochberg over the matured PRIMARY
endpoints only, at the family's declared q (declared at registration;
default q = 0.10, and every backfilled family carries q = 0.10).
Procedure, fixed now: order the m matured primary p-values ascending,
p_(1) <= ... <= p_(m); k* = max { k : p_(k) <= (k/m) * q }; reject
hypotheses 1..k*. Output per matured primary endpoint:
  SURVIVED_FAMILY_CONTROL — BH-rejected at family q;
  NOMINAL_ONLY — nominally significant at alpha = 0.05 but not
    BH-rejected within the family;
  NOT_APPLICABLE — not matured, no primary p-value, or descriptive.
This output vocabulary is a research-state axis ONLY (schema-gate S6
covers it; it never appears as a signal label). Until a family's first
post-registration read, every family_adjudication field prints PENDING.
Registering this spec computes nothing: no p-value is computed, read,
or compared by the backfill.

SECONDARY CELLS
Secondary cells remain descriptive and inherit the existing FP@0.05
accounting of the canonical registry test ledger. The ledger's FOUNDING
ENTRY absorbs that lineage: at registration, 751 secondary cells with
expected false positives 37.55 at alpha = 0.05. The founding entry is
re-derived from the live test ledger at every build — counting only.

FAMILY COUNTERS (per family, derived by counting)
registered — hypotheses ever registered in the family (SUPERSEDED
  included);
matured — status MATURED or a terminal verdict status;
nominal_findings — family_adjudication NOMINAL_ONLY or
  SURVIVED_FAMILY_CONTROL;
family_aware_findings — family_adjudication SURVIVED_FAMILY_CONTROL;
negative — status NOT_SUPPORTED;
inconclusive — status INCONCLUSIVE.
Purpose: No result is presented as though the related tests were never
run.

BACKFILL (A-2 pattern: counting only)
Hypothesis identities are assigned to all existing registered protocols
and their primary endpoints from the chain and its run artifacts. Zero
recomputation, zero re-adjudication, zero statistical estimation beyond
the deterministic status mapping above. Family-aware adjudication
fields print PENDING until each family's first post-registration read.

DERIVED ARTIFACT
registry/discovery_ledger.json — derived deterministically from the
canonical chain by this module; NEVER hand-maintained. It contains no
wall-clock timestamp; its derivation anchor is the chain tip hash, so
the same chain always yields byte-identical output.

GATES (active from registration; chain-gate exit 45)
LEDGER-RECONCILIATION — every kind="protocol" chain line maps to
  exactly one hypothesis identity and every hypothesis identity maps to
  exactly one such line; any orphan in either direction fails the
  chain, as does any divergence between the on-disk artifact and the
  chain-derived rebuild (hand-maintenance is structurally impossible).
FAMILY-LOCK — any difference between on-disk family membership
  (evidence_family, parent_family, families.members) and the
  chain-derived membership without a supersession line covering it
  fails the chain.
Both gates fail closed: a missing artifact, an unregistered spec, or an
unparseable chain is a failure, not a skip.

COMPUTE DISCIPLINE
Registered with zero research recomputation, zero re-adjudication, zero
statistical estimation beyond the deterministic status mapping, zero
signal/score/N_eff changes, zero public page changes, zero version
bump. Any edit to this spec changes its hash and therefore requires
supersession in the registry — never amendment.
"""

PARAMS = {
    "statuses": 8,
    "adjudication_states": 3,
    "default_family_q": 0.10,
    "id_scheme": "H-YYYY-NNNNNN",
}
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_ID = hashlib.sha256(
    (METHOD_SPEC + json.dumps(PARAMS, sort_keys=True)).encode()).hexdigest()[:12]

_RE_VERDICT = re.compile(r"Verdict: ([A-Z_]+)")
_RE_VERSION_SUFFIX = re.compile(r"\s+v\d+(\.\d+)*$")


def _registry(path: Path = CHAIN):
    import sys
    if str(_REPO / "tools") not in sys.path:
        sys.path.insert(0, str(_REPO / "tools"))
    from yuclaw_protocol_registry import Registry
    return Registry(str(path))


def family_slug(root_name: str) -> str:
    s = root_name.split(" (")[0]
    s = _RE_VERSION_SUFFIX.sub("", s)
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s


def build_ledger(chain_path: Path = CHAIN) -> dict:
    """Derive the full ledger from the canonical chain. Counting only:
    every field is copied or counted; nothing is recomputed, estimated,
    or re-adjudicated. Fails closed on any unrecognized verdict token.
    Registry-first: refuses unless this spec is itself registered."""
    reg = _registry(chain_path)          # verifies the chain on load
    reg.assert_registered(PROTOCOL_ID)   # fail closed: spec must be locked
    lines = reg._lines

    protos = []          # (chain_line_1based, payload)
    runs = {}            # protocol_id -> [(chain_line, payload)]
    superseded = {}      # old protocol_id -> (chain_line, payload)
    by_id = {}
    for i, ln in enumerate(lines, start=1):
        p = ln["payload"]
        if ln["kind"] == "protocol":
            protos.append((i, p))
            by_id[p["protocol_id"]] = p
        elif ln["kind"] == "run":
            runs.setdefault(p["protocol_id"], []).append((i, p))
        elif ln["kind"] == "supersede_notice":
            superseded[p["protocol_id"]] = (i, p)

    def _root(payload: dict) -> dict:
        seen = set()
        cur = payload
        while cur.get("supersedes"):
            if cur["protocol_id"] in seen:
                raise ValueError("supersession cycle at "
                                 f"{cur['protocol_id']}")
            seen.add(cur["protocol_id"])
            nxt = by_id.get(cur["supersedes"])
            if nxt is None:
                break                    # dangling pointer: root is cur
            cur = nxt
        return cur

    def _status(pid: str, payload: dict):
        if pid in superseded:
            return "SUPERSEDED", None
        for _, rp in reversed(runs.get(pid, [])):
            m = _RE_VERDICT.search(rp.get("note", ""))
            if m:
                tok = m.group(1)
                if tok not in VERDICT_TOKENS:
                    raise ValueError(
                        f"unrecognized verdict token {tok!r} in run note "
                        f"for {pid} — fail closed, no silent coercion")
                return tok, rp["note"]
        name = payload["name"]
        if "sleeping" in name or "UNCOMPUTED" in name:
            return "REGISTERED", None
        if runs.get(pid):
            return "ACCRUING", None
        return "OPEN", None

    hypotheses = []
    families: dict = {}
    for ordinal, (chain_line, p) in enumerate(protos, start=1):
        pid = p["protocol_id"]
        hyp_id = f"H-{p['lock_date'][:4]}-{ordinal:06d}"
        status, annotation = _status(pid, p)
        fam = family_slug(_root(p)["name"])
        parent_fam = (family_slug(_root(by_id[p["supersedes"]])["name"])
                      if p.get("supersedes") and p["supersedes"] in by_id
                      else None)
        lineage = []
        for ln_no, rp in runs.get(pid, []):
            lineage.append({"kind": "run", "chain_line": ln_no,
                            **{k: rp[k] for k in sorted(rp)
                               if k != "protocol_id"}})
        if pid in superseded:
            ln_no, sp = superseded[pid]
            lineage.append({"kind": "supersede", "chain_line": ln_no,
                            "superseded_by": sp["superseded_by"],
                            "date": sp["date"]})
        lineage.sort(key=lambda e: e["chain_line"])
        hypotheses.append({
            "hypothesis_id": hyp_id,
            "claim": p["primary_endpoint"],
            "registered_at": p["lock_date"],
            "universe": p.get("universe", "NOT_DECLARED_IN_SOURCE_LINE"),
            "population": p.get("population", "NOT_DECLARED_IN_SOURCE_LINE"),
            "horizon": p.get("horizon", "NOT_DECLARED_IN_SOURCE_LINE"),
            "evidence_family": fam,
            "parent_family": parent_fam,
            "protocol_id": pid,
            "method_hash": p["method_hash"],
            "name": p["name"],
            "version": p.get("version", 1),
            "chain_line": chain_line,
            "status": status,
            "maturity": "NOT_DECLARED_IN_SOURCE_LINE",
            "family_q": PARAMS["default_family_q"],
            "family_adjudication": "PENDING",
            "verdict_annotation": annotation,
            "result_lineage": lineage,
        })
        families.setdefault(fam, {"q": PARAMS["default_family_q"],
                                  "members": [],
                                  "adjudication": "PENDING",
                                  "counters": None})
        families[fam]["members"].append(hyp_id)

    terminal = {"MATURED"} | VERDICT_TOKENS
    for fam, body in families.items():
        members = [h for h in hypotheses if h["evidence_family"] == fam]
        body["counters"] = {
            "registered": len(members),
            "matured": sum(1 for h in members if h["status"] in terminal),
            "nominal_findings": sum(1 for h in members
                                    if h["family_adjudication"] in
                                    ("NOMINAL_ONLY",
                                     "SURVIVED_FAMILY_CONTROL")),
            "family_aware_findings": sum(1 for h in members
                                         if h["family_adjudication"] ==
                                         "SURVIVED_FAMILY_CONTROL"),
            "negative": sum(1 for h in members
                            if h["status"] == "NOT_SUPPORTED"),
            "inconclusive": sum(1 for h in members
                                if h["status"] == "INCONCLUSIVE"),
        }

    led = reg.test_ledger()
    status_counts = {}
    for h in hypotheses:
        status_counts[h["status"]] = status_counts.get(h["status"], 0) + 1

    return {
        "spec": {
            "name": "Discovery Ledger v1 (Science Trust addendum)",
            "protocol_id": PROTOCOL_ID,
            "method_hash": METHOD_HASH,
            "umbrella_protocol_id": UMBRELLA_PROTOCOL_ID,
            "adjudication_state": "UNCOMPUTED",
            "counting_state": "ACTIVE",
            "derivation_anchor_chain_tip": reg._tip(),
            "chain_lines": len(lines),
        },
        "purpose": PURPOSE_LINE,
        "founding_entry": {
            "source": "tools/yuclaw_protocol_registry.py test_ledger()",
            "alpha": led["alpha"],
            "total_secondary_cells": led["total_secondary_cells"],
            "expected_false_positives_at_alpha":
                led["expected_false_positives_at_alpha"],
            "note": ("secondary/exploratory cells remain descriptive and "
                     "inherit this FP accounting; absorbed as the "
                     "ledger's founding lineage entry"),
        },
        "hypotheses": hypotheses,
        "families": {k: families[k] for k in sorted(families)},
        "status_counts": dict(sorted(status_counts.items())),
    }


def write_ledger(chain_path: Path = CHAIN,
                 out_path: Path = LEDGER_PATH) -> dict:
    ledger = build_ledger(chain_path)
    out_path.write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n")
    return ledger


def adjudicate(*_args, **_kwargs):
    """Family-aware adjudication is UNCOMPUTED — admissible only through
    a registered read for the family. The BH procedure is fully fixed
    in-hash above; this path refuses until that read is registered."""
    raise NotImplementedError(
        f"Discovery Ledger v1 adjudication is UNCOMPUTED (protocol "
        f"{PROTOCOL_ID}, method {METHOD_HASH}). Family-aware "
        f"adjudication requires each family's own registered "
        f"post-registration read; counting is the only active surface.")


if __name__ == "__main__":
    import sys
    if "--write" in sys.argv:
        ledger = write_ledger()
        print(f"[discovery-ledger] wrote {LEDGER_PATH} — "
              f"{len(ledger['hypotheses'])} hypotheses, "
              f"{len(ledger['families'])} families, "
              f"status_counts={ledger['status_counts']}")
    else:
        print(f"[discovery-ledger] METHOD_HASH={METHOD_HASH} · "
              f"PROTOCOL_ID={PROTOCOL_ID} · params={PARAMS} · "
              f"adjudication UNCOMPUTED · counting ACTIVE")
