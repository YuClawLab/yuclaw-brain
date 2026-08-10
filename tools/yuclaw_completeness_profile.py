#!/usr/bin/env python3
"""
EVIDENCE COMPLETENESS PROFILE v1 — Science Trust addendum (registered
method spec). Counting ACTIVE (order of 2026-08-11, executed 2026-08-10
UTC). Third registered addendum under SCIENCE TRUST PROTOCOL v1
(be8b34040c2e). Full method text in-hash below; the derived artifact
registry/completeness_profile.json is counting-only, never
hand-maintained, and reconciled by chain gate exit 47.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
PROFILE_PATH = _REPO / "registry" / "completeness_profile.json"
UMBRELLA_PROTOCOL_ID = "be8b34040c2e"

COMPLETENESS_STATES = {"HIGH", "MEDIUM", "LOW", "PARTIAL", "ABSENT",
                       "UNKNOWN", "NOT_APPLICABLE"}
FAMILIES = ("sec_primary", "insider_form4", "pricing", "canada_sedi",
            "foreign_filings", "corporate_actions", "macro_series")

# Deterministic source_type -> family mapping (counting only).
SEC_PRIMARY_TYPES = ("8-K", "10-Q", "10-K", "8-K-cascade")
FORM4_TYPES = ("4-parsed",)
FOREIGN_TYPES = ("6-K", "40-F", "20-F")

METHOD_SPEC = """
EVIDENCE COMPLETENESS PROFILE v1 (Science Trust addendum, locked
2026-08-10)

STATUS
Counting ACTIVE. Registered as an addendum under SCIENCE TRUST PROTOCOL
v1 (protocol be8b34040c2e), which named the Evidence Completeness
Profile as a future component admissible only through its own registered
addendum with full method text. This is that addendum.

PURPOSE
Separate evidence COUNT from COVERAGE: per name x evidence-family, say
what has been observed, what was expected to be accessible, and what is
materially missing — by counting committed artifacts only, never by
estimating what has not been seen.

STATE VOCABULARY
HIGH / MEDIUM / LOW / PARTIAL / ABSENT / UNKNOWN / NOT_APPLICABLE.
States describe observed evidence density, freshness, and channel
status, counting-only. They are NOT probabilistic coverage estimates.
UNKNOWN is a legal, first-class state: it marks a family expected to be
accessible for the name but having no live platform ingestion channel,
so absence-of-evidence cannot be distinguished from absence-of-channel.
Research-state axis discipline applies (S6 walks the artifact).

IN-HASH BAN
NO numerical unseen-evidence estimator of any kind (no unseen-species
estimators, no capture-recapture, no extrapolated totals). Descriptive
states only. This ban is liftable SOLELY by a future registered
sampling-model addendum with full method text.

EVIDENCE FAMILIES (fixed)
sec_primary; insider_form4; pricing; canada_sedi; foreign_filings;
corporate_actions; macro_series. macro_series is PLATFORM-LEVEL: it
never attaches at name level and derives NOT_APPLICABLE for every name;
its counts are reported once in the platform block.

NAME CLASSES (derived deterministically, counting only)
  foreign_issuer — the name has >= 1 accepted event whose source_type is
      in {6-K, 40-F, 20-F} (foreign-private-issuer filing channel;
      such issuers are Form-4-exempt, e.g. the ENB/IMO exemption).
  etf            — the name is in the declared ETF membership set
      (empty at registration; ETFs are lens contexts, not covered
      names, today).
  us_scoring     — otherwise, if the name is in the scoring universe
      (v3.universe_tiers.scoring_universe()).
  canada_evidence— otherwise (coverage universe minus scoring tier).
Class evaluation order: foreign_issuer, etf, us_scoring,
canada_evidence — first match wins.

EXPECTED-ACCESSIBLE FAMILIES BY CLASS (fixed table)
  us_scoring / canada_evidence (US-domestic filers):
      sec_primary, insider_form4, pricing, corporate_actions
  foreign_issuer:
      foreign_filings, canada_sedi, pricing, corporate_actions
      (sec_primary and insider_form4 are NOT expected: foreign private
      issuers file 6-K/40-F in place of 8-K/10-Q/10-K and are exempt
      from Form 4 — exemption is NOT_APPLICABLE, never "missing")
  etf: pricing
macro_series is never expected at name level.

PER-FAMILY STATE DERIVATION (deterministic, first match wins; c = count
of committed observations for (name, family); all counts from the live
platform stores: events (accepted), price_history, and
corporate_action_lineage)
  1. family not expected-accessible for the class -> NOT_APPLICABLE
  2. family expected but platform has NO live ingestion channel
     (canada_sedi today) -> UNKNOWN
  3. event families (sec_primary, insider_form4, foreign_filings),
     mapped from accepted-event source_type
     (sec_primary <- {8-K, 10-Q, 10-K, 8-K-cascade};
      insider_form4 <- {4-parsed};
      foreign_filings <- {6-K, 40-F, 20-F}):
     c >= 10 -> HIGH; 3 <= c <= 9 -> MEDIUM; 1 <= c <= 2 -> LOW;
     c = 0 -> ABSENT
  4. pricing (price_history rows; g = calendar days from
     max(trade_date) to the derivation date):
     c >= 250 and g <= 7 -> HIGH; c >= 60 and g <= 14 -> MEDIUM;
     c >= 1 otherwise -> PARTIAL (sparse or stale); c = 0 -> ABSENT
  5. corporate_actions (corporate_action_lineage rows; channel live):
     c >= 1 -> HIGH; c = 0 -> LOW (recorded zero on a live channel is
     thin observed coverage, not absence of channel)

OUTPUTS PER NAME
observed_families (families with c >= 1, pure counting);
expected_accessible_families (from the class table);
material_missing_families (expected AND state in {ABSENT, UNKNOWN});
per-family state with its count.

DERIVED ARTIFACT
registry/completeness_profile.json — derived deterministically by this
module, counting-only; NEVER hand-maintained; derivation anchor = the
canonical chain tip hash + the derivation date printed once. Any state
in the artifact that differs from the registered deterministic
derivation is a derived-only-lineage violation and fails the chain
(gate exit 47), regardless of which state value was planted — a
legitimately derived UNKNOWN is valid; a hand-maintained override of
any value is not.

COMPUTE DISCIPLINE
Counting and bucketing over committed artifacts only. Zero statistical
estimation, zero signal/score/label/N_eff changes, zero public page
changes, zero version bump. Any edit to this spec changes its hash and
therefore requires supersession in the registry — never amendment.
"""

PARAMS = {"states": 7, "families": len(FAMILIES),
           "event_buckets": [10, 3, 1], "pricing_buckets": [250, 60, 1]}
METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PROTOCOL_ID = hashlib.sha256(
    (METHOD_SPEC + json.dumps(PARAMS, sort_keys=True)).encode()).hexdigest()[:12]


def apply_rules(fam: str, expected: bool, count: int,
                gap_days=None) -> str:
    """The registered per-family state derivation, as a pure function of
    (family, expectedness, printed count, printed pricing gap). Used by
    the builder AND re-applied verbatim by gate exit 47 to every printed
    state — any divergence is a derived-only-lineage violation."""
    if fam == "macro_series" or not expected:
        return "NOT_APPLICABLE"
    if fam == "canada_sedi":
        return "UNKNOWN"
    if fam in ("sec_primary", "insider_form4", "foreign_filings"):
        return ("HIGH" if count >= 10 else "MEDIUM" if count >= 3
                else "LOW" if count >= 1 else "ABSENT")
    if fam == "pricing":
        if count == 0:
            return "ABSENT"
        if count >= 250 and gap_days is not None and gap_days <= 7:
            return "HIGH"
        if count >= 60 and gap_days is not None and gap_days <= 14:
            return "MEDIUM"
        return "PARTIAL"
    return "HIGH" if count >= 1 else "LOW"   # corporate_actions


def _registry():
    import sys
    if str(_REPO / "tools") not in sys.path:
        sys.path.insert(0, str(_REPO / "tools"))
    from yuclaw_protocol_registry import Registry
    return Registry(str(_REPO / "registry" / "protocols.jsonl"))


def _counts():
    import psycopg2
    import sys
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from v3.sources.edgar_poll import DB_DSN
    conn = psycopg2.connect(DB_DSN)
    with conn.cursor() as cur:
        cur.execute("""SELECT ticker, source_type, count(*) FROM events
                       WHERE event_status='accepted' GROUP BY 1,2""")
        ev = {}
        for t, st, c in cur.fetchall():
            ev.setdefault(t, {})[st] = c
        cur.execute("""SELECT ticker, count(*), max(trade_date)
                       FROM price_history GROUP BY 1""")
        px = {t: (c, m) for t, c, m in cur.fetchall()}
        cur.execute("""SELECT si.ticker, count(*)
                       FROM corporate_action_lineage cal
                       JOIN security_identity si USING (security_id)
                       GROUP BY 1""")
        ca = dict(cur.fetchall())
        cur.execute("""SELECT source, count(*) FROM macro_series
                       GROUP BY 1 ORDER BY 1""")
        macro = dict(cur.fetchall())
    conn.close()
    return ev, px, ca, macro


def build_profile(as_of=None) -> dict:
    """Derive the full profile. Counting only; registry-first."""
    from datetime import date
    reg = _registry()
    reg.assert_registered(PROTOCOL_ID)
    as_of = as_of or date.today()
    import sys
    if str(_REPO) not in sys.path:
        sys.path.insert(0, str(_REPO))
    from v3.universe_tiers import scoring_universe, coverage_universe
    scoring, coverage = scoring_universe(), coverage_universe()
    ev, px, ca, macro = _counts()
    ETF_SET: set = set()   # empty at registration (in-hash)

    def _class(name):
        types = ev.get(name, {})
        if any(types.get(t) for t in FOREIGN_TYPES):
            return "foreign_issuer"
        if name in ETF_SET:
            return "etf"
        if name in scoring:
            return "us_scoring"
        return "canada_evidence"

    EXPECTED = {
        "us_scoring": ("sec_primary", "insider_form4", "pricing",
                        "corporate_actions"),
        "canada_evidence": ("sec_primary", "insider_form4", "pricing",
                             "corporate_actions"),
        "foreign_issuer": ("foreign_filings", "canada_sedi", "pricing",
                            "corporate_actions"),
        "etf": ("pricing",),
    }

    names = {}
    for name in sorted(coverage):
        cls = _class(name)
        expected = EXPECTED[cls]
        fam_out = {}
        observed, missing = [], []
        types = ev.get(name, {})
        for fam in FAMILIES:
            exp = fam in expected
            g = None
            if fam in ("sec_primary", "insider_form4", "foreign_filings"):
                tset = {"sec_primary": SEC_PRIMARY_TYPES,
                        "insider_form4": FORM4_TYPES,
                        "foreign_filings": FOREIGN_TYPES}[fam]
                c = sum(types.get(t, 0) for t in tset) if exp else 0
            elif fam == "pricing":
                c, mx = px.get(name, (0, None))
                g = (as_of - mx).days if mx else None
            elif fam == "corporate_actions":
                c = ca.get(name, 0)
            else:
                c = 0
            st = apply_rules(fam, exp, c, g)
            fam_out[fam] = {"state": st, "count": c}
            if fam == "pricing":
                fam_out[fam]["gap_days"] = g
            if not exp:
                continue
            if fam == "canada_sedi":
                missing.append(fam)
                continue
            if c >= 1:
                observed.append(fam)
            if st in ("ABSENT", "UNKNOWN"):
                missing.append(fam)
        names[name] = {
            "class": cls,
            "per_family": fam_out,
            "observed_families": observed,
            "expected_accessible_families": list(expected),
            "material_missing_families": missing,
        }

    return {
        "spec": {"name": "Evidence Completeness Profile v1",
                 "protocol_id": PROTOCOL_ID, "method_hash": METHOD_HASH,
                 "umbrella_protocol_id": UMBRELLA_PROTOCOL_ID,
                 "counting_state": "ACTIVE",
                 "unseen_evidence_estimator": "BANNED_IN_HASH",
                 "derivation_anchor_chain_tip": reg._tip(),
                 "derived_as_of": as_of.isoformat()},
        "platform": {"macro_series": {"level": "platform",
                                      "name_level": "NOT_APPLICABLE",
                                      "counts_by_source": macro},
                     "canada_sedi_channel": "NOT_INGESTED (UNKNOWN at "
                                            "name level where expected)"},
        "names": names,
    }


def write_profile(as_of=None) -> dict:
    prof = build_profile(as_of)
    PROFILE_PATH.write_text(json.dumps(prof, indent=1, sort_keys=True) + "\n")
    return prof


if __name__ == "__main__":
    import sys
    if "--write" in sys.argv:
        p = write_profile()
        n = len(p["names"])
        miss = sum(1 for v in p["names"].values()
                   if v["material_missing_families"])
        print(f"[completeness] wrote {PROFILE_PATH} — {n} names, "
              f"{miss} with material missing families")
    else:
        print(f"[completeness] METHOD_HASH={METHOD_HASH} · "
              f"PROTOCOL_ID={PROTOCOL_ID} · params={PARAMS} · "
              f"counting ACTIVE · unseen-evidence estimation BANNED")
