#!/usr/bin/env python3
"""
Layered Evidence Dependency Spec — pre-registered protocol (v1).
LOCKED WITHOUT COMPUTING (sleeping registration, order of 2026-08-06 P0-A).
===========================================================================
This module exists to LOCK the specification before any computation. It
deliberately contains NO analysis code (zero research runs, zero result
cells, zero statistical estimation — the order's definition). The first
computable read (SMH lens ONLY, owner-slotted date) must be implemented
behind run() below, which refuses to execute unless this exact spec (by
hash) is LOCKED in registry/protocols.jsonl AND the owner date slot is
filled and satisfied.

Citation lineage: witness methodology per the methodology reviewer's
published work (arXiv:2408.07818) + three-AI convergent review.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

METHOD_SPEC = """
LAYERED EVIDENCE DEPENDENCY SPEC (v1, locked 2026-08-07)

PURPOSE
Pooled statistics on this platform treat evidence units as if independent.
This spec locks, before any computation, the method by which cross-unit
dependence is made explicit, decomposed, and printed — so that every
pooled statistic can be read alongside its dependence anatomy and an
effective-independent-evidence count a stranger can recompute from the
printed page alone.

PIPELINE (fixed order)
filings -> events -> layered stories -> cross-story dependency graph ->
effective independent evidence -> conclusion contribution anatomy.

NODES
issuers, events, stories. An event is a persisted accepted row of the
evidence store (event_id, issuer, event date, source accession, source
URL, verified excerpt). A story is a maximal connected component of
events under the union of extracted-from-shared-filing edges and
same-issuer-continuation edges (constructed rules below); stories are
derived deterministically from persisted artifacts, never model opinions.

TEMPORAL LAYER CONVENTION
Every edge carries exactly one temporal layer: the U.S. trading day
(the same trading calendar the daily snapshots use) of the LATER of its
two endpoints; for edges joining same-day endpoints, that shared trading
day. Non-trading-day artifact dates roll forward to the next trading day.

EDGE VOCABULARY — LOCKED TIER
(Amendment A-1: only edge types whose deterministic construction rule is
written IN FULL here are locked; this hash is the lock. The first read
runs on this tier alone.)

 1. extracted-from — event -> filing. Exists iff the event's persisted
    source accession number equals the filing's accession number.
 2. same-story — event <-> event. Exists iff both events belong to the
    same story (story := maximal connected component under rules 1-shared
    -filing and 3). Printed for anatomy; redundant with the construction.
    Two events share a filing iff their persisted accessions are equal.
 3. same-issuer-continuation — event -> event. Exists iff both events
    have the same issuer and the later event's date is within 5 trading
    days strictly after the earlier event's date.
 4. same-day — event <-> event. Exists iff the two events' dates fall on
    the same trading day (any issuers).
 5. shared-source — event <-> event. Exists iff the two events' persisted
    normalized source URLs are byte-identical while their accession
    numbers differ.
 6. shared-exhibit — event <-> event. Exists iff the two events' persisted
    evidence objects reference an identical (accession, exhibit-id) pair.
 7. cascade-parent — event -> event. Exists iff the child event's
    persisted cascade record (C8 cascade engine artifacts) lists the
    parent event as its cascade origin.
 8. supports — event -> event. Exists iff a persisted rule-detected
    evidence relation of type SUPPORTS links the two events in the
    evidence store (read as stored; never recomputed at read time).
 9. contradicts — event -> event. Exists iff a persisted rule-detected
    evidence relation of type CONTRADICTS/TENSION links the two events.
10. supersedes — event -> event. Exists iff the later event's filing is
    the EDGAR amendment of the earlier event's filing: same issuer, form
    type equal to the earlier form plus "/A", per the persisted intake
    linkage.
11. affects-component — event -> component (C1..C8). Exists iff the
    event's persisted component-attribution record lists that component
    with a nonzero weight at scoring time.
12. changes-label — event -> issuer-day. Exists iff the issuer's
    published signal label on the event's trading day differs from that
    issuer's label on the immediately preceding trading day's persisted
    snapshot, and the event is dated that trading day.
13. tested-by — event -> registry run. Exists iff a recorded run entry in
    registry/protocols.jsonl has a data window containing the event's
    trading day and a protocol scoped to a universe containing the
    event's issuer.
14. matured-into — event -> forward outcome. Exists iff the persisted
    forward ledger contains a completed k-day outcome row for that
    (issuer, trading day), any k.
15. excluded-from — event -> surface. Exists iff a persisted exclusion
    record (tier boundary, corporate-action exclusion, arm exclusion)
    names that event or its issuer-day together with the excluding
    surface.
16. truncated-by — event/object -> truncation site. Exists iff a
    Truncation & Error Budget ledger site (companion spec, same order)
    records the event or its evidence object among its dropped/capped
    units in a persisted drop record.

EDGE VOCABULARY — FUTURE-EXTENSION TIER (outside this hash; candidates
only; admissible solely by registered addendum carrying full rule text;
named in this module below the spec, never in it).

SEVERITY STATISTIC
For each story-cluster (connected component of the cross-story dependency
graph restricted to locked-tier edges), build the cluster's issuer-event
graph: vertices = the cluster's issuers and events; edges = the
deduplicated undirected projection of all locked-tier edges between those
vertices. Severity = the circuit rank r = |E| - |V| + c (c = connected
components of that projection), PRINTED PER CLUSTER.

STRUCTURE CLASSES (descriptive labels only, no scoring consequence):
tree (r = 0); single-cycle (r = 1); multi-cycle (r >= 2 and below the
clique threshold); clique-like (|V| >= 4 and |E| >= 0.6 * |V|*(|V|-1)/2).

OUTPUTS PER POOLED STATISTIC
For every pooled statistic S published with a dependency anatomy:
  (a) the as-if-independent term: S's variance V_indep computed treating
      all units as independent (sum of w_i^2 * (x_i - xbar)^2);
  (b) one correction term PER LOCKED EDGE TYPE t, with magnitude:
      C_t = sum over unordered same-cluster unit pairs (i,j) whose
      highest-precedence connecting edge type is t, of
      2 * w_i * w_j * (x_i - xbar) * (x_j - xbar).
      Precedence = the enumeration order 1..16 above (a pair contributes
      to exactly one C_t; precedence is a double-counting guard only —
      every edge remains in the graph and in the printed anatomy);
  (c) N_eff DERIVED from the printed decomposition and never asserted:
      N_eff = N_raw * V_indep / (V_indep + sum_t C_t), computed from the
      printed values of (a) and (b) — a stranger recomputes it from the
      page with this formula, which is printed beside it. Signed C_t are
      printed as signed; if the derived N_eff exceeds N_raw it is capped
      at N_raw for display with the cap disclosed on the same line.

PERSISTENCE
Cluster membership STRUCTURE is stored per day (cluster id -> member node
ids + typed edge list, per trading day), never the scalar N_eff. Scalars
are always recomputed from stored structure by the printed formula.

SUPERSESSION RULE (in-spec)
Currently printed N_eff values (and any effective-independence language
already on the site) STAND until a registered v2 read completes. Any
change ships as a registry supersession with lineage to this protocol —
never as an in-place edit.

PRE-REGISTERED ADOPTION PROTOCOL (locked now, answered at the read):
  Q1. Does the read change any effective-independent-evidence judgment?
  Q2. Does it explain any interval where v1 clustering stays optimistic?
  Q3. Does it surface cross-story dependence v1 missed?
  Q4. Does it change any headline maturity label?
  Q5. Does a stranger understand the printed anatomy in ~3 minutes
      (guest-QA)?
Site-wide rollout only on favorable answers; otherwise the pilot prints
as its own inconclusive/negative read. No third option exists.

FIRST COMPUTABLE READ
SMH lens ONLY. Date: OWNER SLOT — unfilled at registration; suggested
after 2026-08-28 (Phase-A maturity); a date falling on the 8th of any
month is never valid. The guard below refuses to compute while the slot
is empty, before the slotted date arrives, on a slotted date violating
the never-the-8th constraint, or for any lens other than SMH.

COMPUTE DISCIPLINE
Registered BEFORE any computation (zero research runs, zero result
cells, zero statistical estimation at registration). Any edit to this
spec changes its hash and therefore requires supersession in the
registry — never amendment.
"""

# FUTURE-EXTENSION tier — outside the hash by construction (candidates
# only; each needs its own registered addendum with full rule text):
FUTURE_EDGE_CANDIDATES = [
    "supply-chain-link",
    "regulatory-common-cause",
    "management-transition",
    "shared-driver",
    # same-sector: a deterministic rule is available today (shared sector
    # label in the persisted universe sector map) but the locked tier was
    # enumerated at registration — admissible by addendum like the rest.
    "same-sector",
]

METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PARAMS = {"first_read_lens": "SMH", "locked_edge_types": 16}
PROTOCOL_ID = hashlib.sha256(
    (METHOD_SPEC + json.dumps(PARAMS, sort_keys=True)).encode()).hexdigest()[:12]

# OWNER SLOT — fill with an ISO date to arm the first read. Filling this
# slot is an owner act; the METHOD_SPEC hash does not cover it, so arming
# does not require supersession. Constraints on the slotted value are
# in-spec and enforced below.
FIRST_READ_DATE: str | None = None


def _registry_guard(pid: str) -> None:
    """REGISTRY-FIRST: refuse to compute unless the protocol is LOCKED in
    registry/protocols.jsonl (chain-verified on load). Fails closed when
    the registry file is absent."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    if str(root / "tools") not in sys.path:
        sys.path.insert(0, str(root / "tools"))
    from yuclaw_protocol_registry import Registry
    Registry(str(root / "registry" / "protocols.jsonl")).assert_registered(pid)


def _date_guard() -> None:
    """The order's early-refusal guard: empty slot, a slot on the 8th of
    any month, or a not-yet-arrived slot all refuse."""
    if FIRST_READ_DATE is None:
        raise RuntimeError(
            "Layered Evidence Dependency v1: OWNER SLOT for the first read "
            "date is unfilled — the guard refuses early (suggested: after "
            "2026-08-28 Phase-A maturity; never a date on the 8th).")
    slot = date.fromisoformat(FIRST_READ_DATE)
    if slot.day == 8:
        raise RuntimeError(
            f"Layered Evidence Dependency v1: slotted date {slot} falls on "
            f"the 8th — never valid, per the locked spec.")
    if date.today() < slot:
        raise RuntimeError(
            f"Layered Evidence Dependency v1: first read is slotted for "
            f"{slot}; today is earlier — the guard refuses early.")


def run(lens: str = "SMH"):
    """The first computable read enters HERE and nowhere else. Guarded
    first; intentionally unimplemented until the owner-slotted read."""
    _registry_guard(PROTOCOL_ID)
    if lens != "SMH":
        raise RuntimeError(
            f"Layered Evidence Dependency v1: first computable read is the "
            f"SMH lens ONLY (got {lens!r}); other lenses require the "
            f"registered adoption decision.")
    _date_guard()
    raise NotImplementedError(
        f"Layered Evidence Dependency v1 is a sleeping registration "
        f"(protocol {PROTOCOL_ID}, method {METHOD_HASH}). This module "
        f"locks the plan; it does not compute.")


if __name__ == "__main__":
    print(f"[layered-dependency] METHOD_HASH={METHOD_HASH} · "
          f"PROTOCOL_ID={PROTOCOL_ID} · params={PARAMS} · "
          f"first_read_date={FIRST_READ_DATE!r} (owner slot) · "
          f"LOCKED, not computed")
