"""Universe tier gates (Canada Resources Phase 2, 2026-07-14).

v3/universe.json now carries TWO tiers under an explicit ``tier_contract``:

  scoring tier   — the four legacy keys (equities / sector_etfs / broad_etfs /
                   macro), the Deng-reviewed 79-ticker record. scoring_eligible
                   and lab_universe are TRUE here and only here.
  evidence tier  — the ``evidence_tier`` key (49 Canada Resources SEC filers).
                   Ingested, parsed, classified, and shown on evidence
                   dashboards; NEVER scored, never in signal_snapshots, never
                   in Lab decile/ranking panels or the forward-track universe.

POSITIVE GATING is the rule: nothing is scoring-eligible unless its tier says
scoring_eligible=true. Consumers must use these gates rather than re-reading
universe.json's raw keys:

  scoring_universe()   — snapshot/composite writers (the only scoring entry)
  lab_universe()       — Lab panels / forward-track membership
  coverage_universe()  — ingestion + price-history coverage (scoring ∪ evidence)
  evidence_cik_map()   — ticker -> 10-digit CIK for evidence-tier names, so
                         ingestion does not depend on SEC ticker-map lookups
                         for OTC lines (WCPRF class)
"""
from __future__ import annotations

import json
from pathlib import Path

UNIVERSE_PATH = Path(__file__).resolve().parent / "universe.json"


def _load() -> dict:
    u = json.loads(UNIVERSE_PATH.read_text())
    if "tier_contract" not in u:
        raise RuntimeError(
            "universe.json has no tier_contract — refusing to guess eligibility "
            "(positive gating: nothing is scoring-eligible by default)")
    return u


def _scoring_tier_tickers(u: dict) -> set[str]:
    tier = u["tier_contract"]["scoring_tier"]
    if not tier.get("scoring_eligible") is True:
        return set()
    return {t for key in tier["keys"] for t in u.get(key, [])}


def scoring_universe() -> set[str]:
    """Tickers explicitly marked scoring-eligible. The ONLY set that may enter
    composite scoring / signal_snapshots."""
    return _scoring_tier_tickers(_load())


def lab_universe() -> set[str]:
    """Tickers eligible for Lab panels / the forward-track record."""
    u = _load()
    tier = u["tier_contract"]["scoring_tier"]
    return _scoring_tier_tickers(u) if tier.get("lab_universe") is True else set()


def evidence_tier_records() -> list[dict]:
    """Full metadata records for the evidence-only tier."""
    return list(_load().get("evidence_tier", []))


def evidence_tier_tickers() -> set[str]:
    return {r["ticker"] for r in evidence_tier_records()}


def coverage_universe() -> set[str]:
    """Everything we ingest filings and price history for: scoring tier plus the
    evidence-only tier. Coverage is NOT eligibility — see scoring_universe()."""
    u = _load()
    cov = _scoring_tier_tickers(u)
    cov |= {r["ticker"] for r in u.get("evidence_tier", []) if r.get("evidence_eligible") is True}
    return cov


def evidence_cik_map() -> dict[str, str]:
    """ticker -> zero-padded 10-digit CIK for evidence-tier names."""
    return {r["ticker"]: r["cik"] for r in evidence_tier_records()}


def is_scoring_eligible(ticker: str) -> bool:
    return ticker in scoring_universe()
