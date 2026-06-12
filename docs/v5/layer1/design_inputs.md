# v5 Layer 1 — Design Inputs (recorded before build)

Branch `v5-layer1`, based off `v5-layer0-foundation` @ 90f23392.

This document records the empirical findings that shape Layer 1 (the agent swarm)
**before** any code is written, so the design is traceable to evidence rather than
retrofitted.

## Source: the June 12 C6 evidence-component investigation

`docs/methodology/c6_investigation.md` (v4.3-lab-pro branch) established, with
read-only forensics on `signal_snapshots` + `events` + `price_history`:

- The event feed is **93% insider-sell / 7% material-non-insider** by volume.
- These two populations behave with **opposite short-term signs**: insider-sell-
  heavy names are short-term contrarian (negative return-IC ≈ −0.12), while
  names with a **material non-insider event** carry a **positive** within-class
  IC (+0.36). Pooling them into one signed scalar destroys the material-event
  information.
- C6 is a **proven risk gate**: IC(C6, realized volatility) = **−0.317** and
  IC(C6, max drawdown) = **+0.216** — low evidence reliably precedes higher
  volatility and deeper drawdowns, even where mean-return prediction is weak.
- C6's return-drag is **horizon-dependent**: most negative at ~4 weeks, decaying
  by 8 weeks, and flipping slightly positive by ~13 weeks (n=3, suggestive).

## Three amendments to the Layer 1 specialist design

These are recorded now; **only amendment (3) changes Day-1 scope** (the output
schema). Amendments (1) and (2)'s structural build-out is later-day work, but the
schema is made forward-compatible today so the risk channel is never a retrofit.

1. **Insider-Flow specialist SEPARATE from Material-Event specialists.** The two
   event populations have different volumes (93% / 7%) and opposite short-term
   signs, so a single evidence specialist that averages them is provably
   information-destroying. Layer 1's evidence specialists must split insider-
   transaction flow from material corporate events. *(Structural; later day.)*

2. **Horizon-aware synthesis.** Because evidence predicts differently at 1–4w vs
   ~13w, the Synthesis layer should eventually carry an explicit horizon view
   rather than a single next-period scalar. *(Structural; later day.)*

3. **A RISK channel alongside the RETURN channel — in the agent output schema
   from Day 1.** C6 is a demonstrated risk predictor (vol IC −0.317), so every
   agent's structured output (and the synthesis output) carries **both** a
   `return_view` and a `risk_view` field starting today. This makes the risk
   channel a first-class citizen of the schema, not a later migration.

## Day-1 scope (unchanged)

Bull / Bear / Skeptic 8B agents (concurrent) + a 70B Synthesis agent, one real
filing end-to-end through the Layer 0 `EvidenceJobQueue`. The amendment above
fixes the **output JSON schema** to include both channels now; the
insider/material split and horizon-aware synthesis are scaffolded in prompts and
revisited on later Layer-1 days.

## Cross-references

- C6 investigation: `docs/methodology/c6_investigation.md` (v4.3-lab-pro)
- Layer 0 queue: `yuclaw/v5/queue/core.py` (`EvidenceJobQueue`, reused, not reimplemented)
- Day-1 writeup: `docs/v5/layer1/day1.md`
