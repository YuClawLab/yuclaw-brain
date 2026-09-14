# Phase 5 — contribution anatomy: descriptive decomposition contract (DRAFT, v7)

Commitment located: master plan Phase 5 (line 79) is a plan item only; no protocol or result line exists in the chain. This contract prepares a DESCRIPTIVE decomposition of a published composite classification into per-component contributions using already-published examples (`docs/why/{TICKER}.json`, schema `WhyAnatomy.v1`).

Contract: for one why-JSON, `contributions = [{component, score, confidence, weight, contribution = score × confidence × weight}]`, with `Σ contribution` equal to the published composite up to the schema's rounding. Zero-weight (gated) components are listed with contribution 0 and their gate reason (e.g., C2 confidence-gated, C4 frozen 2026-05-18). No causal language: a contribution is an arithmetic share of a classification, not an attribution of any market outcome.
Fixtures: `docs/why/AAPL.json` (published) as the worked example; a synthetic why-JSON for boundary cases (all-zero, single-component, negative).
Registration: producing a new decomposition surface for all 79 names is a new registered read (not performed here).
