"""
YuClaw v4 — Agent Research API: unified response schema (Python source of truth).

ONE contract, consumed by every v4 surface:
  - Memo Generator
  - MCP v2 server
  - REST  GET /v1/why/{ticker}
  - LangChain tool wrapper
  - LlamaIndex tool wrapper

Pydantic v2 models. The OpenAPI 3.1 spec (docs/v4/openapi.yaml) is the
language-neutral mirror of this file; this file wins on any disagreement.

ARCHITECTURAL INVARIANTS — do not weaken without security review:
  1. `SignalLabel` IS the locked public vocabulary (== sdk PUBLIC_LABELS). There is
     no SELL / SHORT / BUY classification — labels are research classifications only.
  2. `compliance` is REQUIRED on every response (regulatory hard constraint).
  3. `Evidence.raw_excerpt` is SourceLock-verified UPSTREAM (R1..R8). This schema
     transports it; it does not relax verification. Do not add a field that would
     require returning unverified text.
  4. `Component` exposes score / confidence / rationale / evidence_ids ONLY — never
     the internal `details` dict (impact weights, is_insider, etc.). Component
     scores are already public in v3; no internal-only bearish score is introduced.
  5. `Component.evidence_ids` MUST reference `Evidence.event_id` values present in
     the same response (self-contained — a consumer never needs a second DB query).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "v4.0"


# --------------------------------------------------------------------------- #
# Locked vocabularies
# --------------------------------------------------------------------------- #
class SignalLabel(str, Enum):
    """The locked public signal vocabulary (mirrors sdk.yuclaw_py PUBLIC_LABELS).

    Ordered most-bullish → most-bearish. These are RESEARCH CLASSIFICATIONS, not
    buy/sell recommendations. SELL / SHORT / BUY are intentionally absent.
    """
    STRONG_BULLISH = "STRONG_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    WATCH = "WATCH"
    WEAKENING = "WEAKENING"
    RISK_ALERT = "RISK_ALERT"          # reserved; emitted by v4 risk overlay
    NEGATIVE_EVENT = "NEGATIVE_EVENT"
    BEARISH_WATCH = "BEARISH_WATCH"


class EvidenceGrade(str, Enum):
    """Bucketed Evidence Quality Grade (per ChatGPT review).

    Communicates *how well-supported* the signal is, independent of direction.
    Deriving rule lives in `Confidence.grade_for()` — deterministic, auditable.
    """
    A = "A"                  # strong, corroborated evidence
    B = "B"                  # adequate evidence
    C = "C"                  # thin / single-source evidence
    INSUFFICIENT = "Insufficient"   # not enough to stand behind


# Human-readable component names (id → label). Mirrors v3 COMPONENT_WEIGHTS keys.
COMPONENT_NAMES: dict[str, str] = {
    "c1": "Price Momentum",
    "c2": "Volume Confirmation",
    "c3": "Sector Velocity",
    "c4": "Macro Regime",
    "c5": "Oil / Rates / FX",
    "c6": "Event Impact",
    "c7": "Peer Correlation",
    "c8": "Cascade Effect",
    "c9": "Model Trust",
}

# Standard caveats present on EVERY response (per-signal caveats are appended).
DEFAULT_LIMITATIONS: tuple[str, ...] = (
    "This is a research classification, not a price target, recommendation, or solicitation.",
    "Point-in-time as of `as_of`; filings or market data after that instant are not reflected.",
    "Does not incorporate options flow, intraday microstructure, or private/non-public information.",
    "Insider Form 4 transactions feed the C6 Event Impact component under a capped weight; they are not scored as a standalone insider signal.",
    "Signal quality depends on evidence coverage; see `confidence.grade` and `components[].confidence`.",
)


# --------------------------------------------------------------------------- #
# Nested models
# --------------------------------------------------------------------------- #
class Component(BaseModel):
    """One C1–C9 component anatomy. Internal `details` are deliberately excluded."""
    model_config = ConfigDict(extra="forbid")

    key: str = Field(..., pattern=r"^c[1-9]$", description="Component id, c1..c9")
    name: str = Field(..., description="Human-readable component name")
    score: float = Field(..., ge=-1.0, le=1.0, description="Directional score [-1,1]")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Component self-confidence [0,1]")
    weight: float = Field(..., ge=0.0, le=1.0, description="Composite weight (v3 COMPONENT_WEIGHTS)")
    rationale: str = Field("", description="Short human-readable justification")
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="event_ids (in this response's `evidence`) that fed this component; "
                    "empty for purely technical/macro components (C1–C5, C7, C9).",
    )
    implemented: bool = Field(True, description="False if this component is a stub (confidence forced 0)")


class Evidence(BaseModel):
    """A single source event backing the signal. raw_excerpt is SourceLock-verified."""
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., description="Stable event identifier")
    event_type: str = Field(..., description="Locked extraction vocabulary (R2-validated)")
    source_url: str = Field(..., description="Canonical source (e.g. SEC primary document)")
    accession_number: Optional[str] = Field(
        None, pattern=r"^\d{10}-\d{2}-\d{6}$",
        description="SEC accession (canonical) when source is an EDGAR filing; null otherwise.",
    )
    ledger_hash: str = Field(..., description="Per-event integrity hash (events.content_hash) — ledger anchor")
    available_as_of: datetime = Field(..., description="When this evidence became knowable (point-in-time)")
    # Verifiability + magnitude fields (already public in v3; kept for self-containment)
    raw_excerpt: Optional[str] = Field(
        None, max_length=400,
        description="Verbatim, SourceLock-verified excerpt from the source (<=400 chars).",
    )
    direction: Optional[int] = Field(None, ge=-1, le=1, description="-1/0/1 directional sign")
    magnitude: Optional[float] = Field(None, ge=0.0, le=1.0, description="Event magnitude [0,1]")
    llm_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Extraction confidence [0,1]")
    cascade_depth: Optional[int] = Field(None, ge=0, description="Depth if a cascade child, else null/0")


class Confidence(BaseModel):
    """Overall confidence + bucketed Evidence Quality Grade."""
    model_config = ConfigDict(extra="forbid")

    value: float = Field(..., ge=0.0, le=1.0, description="Composite confidence [0,1] (v3 composite_confidence)")
    grade: EvidenceGrade = Field(..., description="Bucketed Evidence Quality Grade")
    basis: str = Field("", description="One-line explanation of how the grade was derived")

    @staticmethod
    def grade_for(value: float, evidence: list["Evidence"]) -> EvidenceGrade:
        """Deterministic v4.0 grading rule (refinable; documented in openapi.yaml).

        Combines composite confidence with evidence corroboration so a confident
        score built on a single thin source cannot earn an 'A'.
        """
        strong = [e for e in evidence if (e.llm_confidence or 0.0) >= 0.7]
        if value >= 0.75 and len(strong) >= 3:
            return EvidenceGrade.A
        if value >= 0.55 and len(evidence) >= 1:
            return EvidenceGrade.B
        if value >= 0.30:
            return EvidenceGrade.C
        return EvidenceGrade.INSUFFICIENT


class Compliance(BaseModel):
    """REQUIRED on every response. Mirrors sdk COMPLIANCE + adds v4 metadata.

    Hard regulatory constraint: this object is non-optional. A securities reviewer
    must be able to read it and conclude the response is research, not advice.
    """
    model_config = ConfigDict(extra="forbid")

    not_advice: bool = Field(True, description="Always true")
    research_only: bool = Field(True, description="Always true")
    not_registered_adviser: bool = Field(True, description="Always true")
    # Q4: conservative wording, marked PLACEHOLDER pending securities review. Swapping
    # in lawyer-reviewed text is a one-field change + a bump of compliance_text_version.
    notice: str = Field(
        "This is research output, not investment advice. "
        "Past performance does not guarantee future results. "
        "Not a recommendation to buy or sell any security.",
        description="Not-advice notice. PLACEHOLDER (draft-v0) pending securities review.",
    )
    compliance_text_version: str = Field(
        "draft-v0",
        description="Version tag for `notice`. 'draft-v0' = pre-legal-review placeholder.",
    )
    jurisdiction: str = Field("US", description="Regulatory jurisdiction the notice is written for")
    model_id: str = Field(..., description="Extraction model id (e.g. yuclaw-llm-70b)")
    prompt_version: str = Field(..., description="Extraction prompt version (e.g. v2)")

    @field_validator("not_advice", "research_only", "not_registered_adviser")
    @classmethod
    def _must_be_true(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("compliance posture flags cannot be set false")
        return v


# --------------------------------------------------------------------------- #
# Top-level response
# --------------------------------------------------------------------------- #
class ResearchResponse(BaseModel):
    """The single unified response. Every v4 surface returns exactly this shape."""
    model_config = ConfigDict(extra="forbid", json_schema_extra={"x-schema-version": SCHEMA_VERSION})

    schema_version: str = Field(SCHEMA_VERSION, description="Schema contract version")

    # --- identity / point-in-time ---
    ticker: str = Field(..., pattern=r"^[A-Z][A-Z0-9.\-]{0,9}$", description="Uppercase ticker")
    as_of: datetime = Field(..., description="Point-in-time instant this signal reflects (ISO-8601, tz-aware)")
    replay_id: str = Field(..., description="Opaque handle to reconstruct this exact response point-in-time")

    # --- the signal ---
    signal: SignalLabel = Field(..., description="Locked public vocabulary label")
    signal_overlay: Optional[str] = Field(
        None,
        description="If the label diverges from the score-derived band, why (Q1: e.g. "
                    "'RISK_ALERT: REGULATORY_ACTION/LAWSUIT within 30d'). None when label == score band.",
    )
    score: Optional[float] = Field(
        None, ge=-1.0, le=1.0,
        description="Composite directional score [-1,1] (v3 total_score). Q2: gated — default OFF for "
                    "REST/MCP (opt in via include_score), default ON for SDK/CLI. None when not included.",
    )
    is_backfill: bool = Field(False, description="True if as_of is historical/backfilled rather than live")

    # --- anatomy ---
    components: list[Component] = Field(..., min_length=1, description="C1–C9 component anatomies")
    evidence: list[Evidence] = Field(
        ..., description="Source events backing the signal (required key; may be empty for technical-only signals)",
    )

    # --- confidence / honesty ---
    confidence: Confidence = Field(..., description="Composite confidence + Evidence Quality Grade")
    limitations: list[str] = Field(..., min_length=1, description="Explicit caveats — what this does NOT consider")

    # --- integrity ---
    ledger_hash: str = Field(..., description="SHA-256 over the canonical response (verification anchor)")
    ledger_anchor_url: Optional[str] = Field(
        None,
        description="Q3: URL to this signal's entry in the git-anchored Verified Research Ledger "
                    "(v3/proof/). Null if the ledger run has not published this (ticker, date) yet. "
                    "Excluded from the ledger_hash so publication state does not change the content hash.",
    )

    # --- regulatory (REQUIRED) ---
    compliance: Compliance = Field(..., description="Required not-advice / provenance block")

    @model_validator(mode="after")
    def _evidence_ids_resolve(self) -> "ResearchResponse":
        """Invariant 5: every Component.evidence_id must exist in `evidence`."""
        known = {e.event_id for e in self.evidence}
        for c in self.components:
            missing = [eid for eid in c.evidence_ids if eid not in known]
            if missing:
                raise ValueError(f"component {c.key} references unknown evidence ids {missing}")
        return self

    # ---- integrity helpers ----
    def canonical_payload(self) -> dict:
        """Deterministic dict for hashing — excludes ledger_hash and ledger_anchor_url.

        ledger_anchor_url is publication metadata (it embeds a git commit that may be
        written after the signal); excluding it keeps the content hash stable and
        reproducible regardless of whether/when the ledger entry was published.
        """
        d = self.model_dump(mode="json", exclude={"ledger_hash", "ledger_anchor_url"})
        return d

    def compute_ledger_hash(self) -> str:
        """SHA-256 of the canonical (ledger_hash-excluded) payload."""
        blob = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    def with_sealed_ledger_hash(self) -> "ResearchResponse":
        """Return a copy with ledger_hash set to the computed canonical hash."""
        return self.model_copy(update={"ledger_hash": self.compute_ledger_hash()})

    def verify_ledger_hash(self) -> bool:
        return self.ledger_hash == self.compute_ledger_hash()


__all__ = [
    "SCHEMA_VERSION", "SignalLabel", "EvidenceGrade", "COMPONENT_NAMES",
    "DEFAULT_LIMITATIONS", "Component", "Evidence", "Confidence", "Compliance",
    "ResearchResponse",
]
