#!/usr/bin/env python3
"""
SCIENCE TRUST PROTOCOL — pre-registered umbrella governance spec (v1).
UNCOMPUTED (sleeping registration, order of 2026-08-07d — v6 ignition).
===========================================================================
Umbrella GOVERNANCE registration only. This module locks how YUCLAW
determines what financial evidence can support and how research
conclusions are described. It deliberately contains NO analysis code:
no Science Trust dimension has a computable metric, estimator, threshold,
decision rule, or user-facing output by virtue of this registration.
Every computational implementation requires its own separately registered
addendum with full method text — no unwritten method is inherited from
this umbrella.
"""
from __future__ import annotations

import hashlib
import json

# Research-state vocabulary — protocol/research conclusions ONLY (never
# signal labels, score labels, bullish/bearish, buy/sell, or portfolio
# action). Single source for the vocabulary-separation gate (S6).
RESEARCH_STATES = {
    "SUPPORTED", "WEAK", "INCONCLUSIVE", "CONFLICTED",
    "INSUFFICIENT_EVIDENCE", "NOT_IDENTIFIABLE",
}

# Public identity — LOCKED VERBATIM (also in-hash below).
PUBLIC_IDENTITY = ("YUCLAW — Evidence-First Financial AI · "
                   "The Science Trust Layer for Financial AI.")

# Banned as BRAND language (in-hash below; statistics may appear inside
# methodology where technically necessary — it must not replace the
# Evidence-First / Science Trust identity).
BANNED_BRAND_TERMS = [
    "Statistical Trust Layer",
    "mathematically proven",
    "mathematically verified",
    "market law",
    "certified truth",
    "AI oracle",
]

METHOD_SPEC = """
SCIENCE TRUST PROTOCOL (v1, umbrella governance spec, locked 2026-08-07)

STATUS
UNCOMPUTED. Umbrella governance registration only.

PURPOSE
Govern how YUCLAW determines what financial evidence can support and how
research conclusions are described, without changing signal labels,
scores, existing research results, or investment meaning.

PUBLIC IDENTITY — LOCKED VERBATIM
"YUCLAW — Evidence-First Financial AI ·
The Science Trust Layer for Financial AI."

TEN GOVERNANCE DIMENSIONS
provenance; dependence; multiplicity; sequential evidence; contradiction;
completeness; truncation impact; maturity; contribution sensitivity;
reproducibility.

CRITICAL INVARIANT
The ten dimensions are GOVERNANCE DIMENSIONS ONLY. Registration of this
umbrella does NOT imply that any dimension already has a computable
metric, estimator, threshold, decision rule, or user-facing output. Any
computational implementation requires a separately registered addendum
containing the complete deterministic/statistical method, assumptions,
inputs, outputs, invalidation rules, and method hash before computation.
No unwritten method is inherited from this umbrella.

RESEARCH-STATE VOCABULARY
SUPPORTED · WEAK · INCONCLUSIVE · CONFLICTED · INSUFFICIENT_EVIDENCE ·
NOT_IDENTIFIABLE.
These states apply to protocol/research conclusions ONLY. They must never
be mechanically translated into: signal labels; score labels;
bullish/bearish meaning; buy/sell meaning; portfolio action. Existing
YUCLAW signal vocabularies remain independent and unchanged.

FIVE-VALUE CONSTITUTION — LOCKED VERBATIM
evidence before opinion
independence before sample size
error control before significance
uncertainty before confidence
forward survival before reputation

GOVERNANCE / TWO-TIER RULE
The umbrella may NAME future components — Discovery Ledger; Anytime
Evidence Record; Evidence Completeness Profile; Science Trust Card
derivation; Contribution Anatomy — but naming creates NO executable
methodology. Each component becomes admissible only through its own
registered addendum containing full method text. Until then its state
is: UNCOMPUTED / METHOD NOT REGISTERED.

IDENTITY / LANGUAGE RAILS
Public identity remains:
"YUCLAW — Evidence-First Financial AI ·
The Science Trust Layer for Financial AI."
Banned as BRAND language: "Statistical Trust Layer"; "mathematically
proven"; "mathematically verified"; "market law"; "certified truth";
"AI oracle". Statistics may appear inside methodology where technically
necessary. It must not replace YUCLAW's Evidence-First / Science Trust
identity.

VOCABULARY-SEPARATION GATE (active from registration)
The language/schema gate rejects, context-aware (structured fields, never
ordinary prose): (A) any research-state value used as a signal label,
score label, trading classification, buy/sell field, or portfolio-action
field; (B) any signal-label value used as the canonical Science Trust
research-state field.

COMPUTE DISCIPLINE
Registered with zero research computation, zero statistical estimation,
zero result cells, zero signal/score/N_eff changes, zero public copy
changes, zero version bump. Any edit to this spec changes its hash and
therefore requires supersession in the registry — never amendment.
"""

NAMED_COMPONENTS = [
    "Discovery Ledger",
    "Anytime Evidence Record",
    "Evidence Completeness Profile",
    "Science Trust Card derivation",
    "Contribution Anatomy",
]
COMPONENT_STATE = "UNCOMPUTED / METHOD NOT REGISTERED"

METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PARAMS = {"governance_dimensions": 10, "research_states": 6}
PROTOCOL_ID = hashlib.sha256(
    (METHOD_SPEC + json.dumps(PARAMS, sort_keys=True)).encode()).hexdigest()[:12]


def _registry_guard(pid: str) -> None:
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    if str(root / "tools") not in sys.path:
        sys.path.insert(0, str(root / "tools"))
    from yuclaw_protocol_registry import Registry
    Registry(str(root / "registry" / "protocols.jsonl")).assert_registered(pid)


def run(component: str | None = None):
    """No component is computable under the umbrella alone. Guarded
    first; every path refuses until a registered addendum exists."""
    _registry_guard(PROTOCOL_ID)
    if component is not None:
        raise NotImplementedError(
            f"Science Trust component {component!r} is "
            f"{COMPONENT_STATE} — admissible only through its own "
            f"registered addendum with full method text.")
    raise NotImplementedError(
        f"SCIENCE TRUST PROTOCOL v1 is an umbrella governance "
        f"registration only (protocol {PROTOCOL_ID}, method "
        f"{METHOD_HASH}, UNCOMPUTED). No dimension has a computable "
        f"metric, estimator, threshold, decision rule, or user-facing "
        f"output by this registration.")


if __name__ == "__main__":
    print(f"[science-trust] METHOD_HASH={METHOD_HASH} · "
          f"PROTOCOL_ID={PROTOCOL_ID} · params={PARAMS} · UNCOMPUTED · "
          f"components: {', '.join(NAMED_COMPONENTS)} — each "
          f"{COMPONENT_STATE}")
