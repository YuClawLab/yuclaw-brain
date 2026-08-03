#!/usr/bin/env python3
"""
U350 constitution (Phase 0 Part 1) — the two uncomputed-standard
registrations. Specs are the module constants below, registered verbatim;
edits => supersession. No runs are ever recorded against either entry.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

ADMISSION_SPEC = """
UNIVERSE ADMISSION PROTOCOL — v1 (uncomputed-standard class, locked 2026-08-02)
Every name enters the U350 research universe through SIX GATES; no other
path exists. U79 is unaffected by this protocol forever.

GATE 1 — IDENTITY INTEGRITY. A name is admitted only with: unique ticker,
CIK, legal name, exchange, security type, country, filer class, SIC sector
code, a PERMANENT INTERNAL ID (issuer_id + security_id), and a
corporate-action lineage record. Ticker is display; the internal ID is
identity. Missing or ambiguous identity = NOT ADMITTED.

GATE 2 — PRICE AVAILABILITY. >= 252 trading days of price history from the
research price store; a gap of > 5 consecutive trading days inside the
trailing 252 = NOT ADMITTED (gap rule); available_as_of recorded for every
row. Inherits BY REFERENCE the standing price policies: unadjusted closes,
no dividend reinvestment, corporate-action windows excluded never adjusted
(methodology, v5.2 policies section).

GATE 3 — LIQUIDITY. Thresholds are LOCKED ONLY AFTER the Phase-0 coverage
audit measures the real distribution of trailing-252d median dollar volume
across the candidate pool; this spec names the PROCEDURE now: thresholds
will be set at Phase-A lock as an absolute floor (dollar-volume percentile
of the measured pool, stated with its measured value) plus a zero-volume-day
rate cap; numbers enter via a versioned addendum registration, never by
edit. Until that addendum exists, no liquidity verdict may be issued.

GATE 4 — EVIDENCE SUBSTRATE. Admission requires a mapped substrate path:
8-K/10-Q/10-K (domestic), 6-K/20-F (FPI), or 6-K/40-F (MJDS). Names whose
substrate yields little or nothing carry explicit statuses on every
surface: EVIDENCE_THIN (substrate exists, low volume),
NO_CURRENT_EVENT_SUBSTRATE (no mapped path currently produces events),
PRICE_ONLY_COMPONENTS_ACTIVE (scored on price components only). Absence of
evidence NEVER becomes neutral evidence: evidence components self-mask at
zero confidence exactly as C2 does.

GATE 5 — SCORING COMPLETENESS. Shadow-run requirement before any Phase-B
consideration: component success floors (each active component computes on
>= 95% of the name's shadow days; names below floor carry
COMPONENT_INCOMPLETE), deterministic repeatability (same inputs => same
score, verified by re-run), and label mapping through the LOCKED published
thresholds only.

GATE 6 — CROSS-SECTIONAL FIT (disclosure-triggering, never
result-blocking). On SIC sector groupings: no sector > 22% of the
universe; sectors present must reach the >= 15-name floor or carry a
SECTOR_THIN disclosure; market-cap, liquidity, and Form-4-density skew vs
the candidate pool measured and disclosed. Fit findings trigger
disclosures on every affected surface; they never silently alter results.

Verdicts per name per gate are recorded in the admission report with
reasons; the report is deterministic given (rule version, as-of date).
"""

SELECTION_SPEC = """
U350 SELECTION RULE — v1 (uncomputed-standard class, locked 2026-08-02)
Deterministic, licensing-clean, zero human discretion after registration,
zero performance inputs.

CANDIDATE POOL (operational, licensing-clean): the union of (a) the
current coverage universe and (b) US-exchange-listed operating companies
appearing as constituents in the thirteen ingested SPDR sector-fund
issuer disclosures (data/holdings/*.json, as-of 2026-07-29), resolved
against the SEC ticker file for exchange/CIK identity. Constituent
MEMBERSHIP is the only fact used from the fund disclosures — no index
weights enter selection.

EQUITY RANKING: within SIC sector groups, rank candidates by trailing-252d
MEDIAN daily dollar volume (median(close x volume), unadjusted closes, the
research price store's convention), as-of the registered date. Selection
fills sector floors first (admission Gate 6 floors), then proceeds by
global rank until the phase's count is reached. Ties break by CIK
ascending (deterministic).

ETF SLEEVE (~70 at full U350; phased): selected by AUM-PROXY liquidity
rank = trailing-252d median dollar volume of the fund itself; ETNs carry
an issuer-credit flag on every surface. The sleeve enters at Phase B or
later; Phase A is operating companies plus the existing U79 ETFs only.

AS-OF DATE: fixed at registration of each phase manifest; the Phase-A
as-of is 2026-08-01 (last completed trading day before this registration).
PERFORMANCE INPUTS: none — returns, scores, labels, and outcomes are
structurally absent from this rule.
"""

for name, spec, summary, primary in (
    ("Universe Admission Protocol v1", ADMISSION_SPEC,
     "Six admission gates (identity, price, liquidity-procedure, substrate "
     "statuses, scoring completeness, cross-sectional fit); standard entry, "
     "no runs ever recorded; liquidity numbers enter only via versioned "
     "addendum after the coverage audit.",
     "admission-gate ruling — standard entry; no statistical endpoint, no "
     "runs ever recorded"),
    ("U350 Selection Rule v1", SELECTION_SPEC,
     "Deterministic licensing-clean selection: membership-only candidate "
     "pool from ingested fund disclosures + coverage universe; SIC-grouped "
     "median-dollar-volume ranking; fixed as-of; zero performance inputs; "
     "standard entry, no runs ever recorded.",
     "selection ruling — standard entry; no statistical endpoint, no runs "
     "ever recorded"),
):
    from yuclaw_protocol_registry import Protocol, Registry, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(spec, {"class": "standard", "version": 1})
    if reg.get_protocol(pid):
        print(f"already locked: {pid} ({name})")
        continue
    reg.register(Protocol(
        protocol_id=pid, name=name,
        method_hash=hashlib.sha256(spec.encode()).hexdigest()[:16],
        spec_summary=summary, primary_endpoint=primary,
        secondary_endpoints=[],
        lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")))
    reg.verify_chain()
    print(f"LOCKED {pid} ({name}) method="
          f"{hashlib.sha256(spec.encode()).hexdigest()[:16]}")
