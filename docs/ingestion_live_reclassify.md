# Live event re-classification (taxonomy rescue in the ingestion path)

**Date:** 2026-06-24. **Scope:** production ingestion (`v3/extract/`). **No deploy beyond ingestion.**

## The blocker

The producer LLM (`event_worker`, the locked SourceLock taxonomy in `sourcelock.py`) is
**low-precision on the refined categories**: it routinely dumps earnings / financings / M&A into
the `OTHER_MATERIAL` catch-all and emits `M_AND_A_ANNOUNCE` / `EARNINGS_BEAT` rather than the
`M_AND_A` / `EARNINGS_RESULT` strings the v5 consumers read.

The v5 consumers — the L1 corpus query and `spawn_specialists()` — read
`COALESCE(corrected_event_type, event_type)` from `yuclaw_v5.event_type_corrected`. The Day-5A
re-classifier (`yuclaw/v5/extract/reclassify.py`) **rescues** the coarse tags into real L1 types
via verbatim signature matching, but it was **batch-only**. So new events were never rescued and
**4 of 8 L1 types (`EARNINGS_RESULT`, `M_AND_A`, `FINANCING`, `GOVERNANCE`) were unreachable for
new flow** → new earnings/financing/M&A filings produced **zero OOS fuel** and spawned no
specialist. (Full producer-vs-consumer analysis: prior taxonomy-mismatch report.)

## The fix — rescue, live

`v3/extract/reclassify_live.py` ports the batch re-classifier into the live `event_worker` path.
After the worker commits an accepted event, it re-classifies that event and writes the corrected
tag additively to `yuclaw_v5.event_type_corrected`:

- **Verbatim logic.** `_RULES` / `_clean` / `_match` / `classify` / `_filing_text_for` are a
  byte-for-byte copy of the v5 batch module (the two repos share one DB but `yuclaw/v5/` is not on
  `main`, so the logic is ported, not imported). Reproduction-critical — see validation below.
- **Excerpt-first** (the D5A cross-contamination guard): each event is classified against its OWN
  `raw_excerpt`; the full filing text is consulted only when the excerpt is too short (<160 chars).
- **SourceLock by construction:** every re-tag carries a verbatim signature span; if nothing
  matches, the producer tag is kept (no unsupported re-tag).
- **Additive / non-destructive:** `public.events.event_type` is never mutated; the original
  producer tag is preserved as `v4_event_type` for audit. The hook runs AFTER the worker's events
  transaction commits and is **best-effort** — a re-class failure logs and is skipped, never fails
  ingestion (the corrected layer can always be rebuilt by the batch re-classifier).

## Validation — reproduce the batch corrected-layer (the hard gate)

Before shipping, the live port was run over the existing **62-row** batch corrected-layer (the
28-filing L1 corpus + others) and compared tag-for-tag:

> **62 / 62 match — PASS.** The live port reproduces the batch corrected-layer exactly (including
> every rescue: 11 `OTHER_MATERIAL→EARNINGS_RESULT`, 6 `OTHER_MATERIAL→FINANCING`,
> 2 `M_AND_A_CLOSE→M_AND_A`, etc.). No train/serve skew.

## First real result — the recovered June gap

Applied to the 35 recovered June events (1 via an end-to-end worker smoke + 34 batch):
**10 rescued into L1 fuel**, taking **L1-type events 28 → 38**:

| rescued type | n | from (raw) |
|---|---|---|
| FINANCING | 7 | `OTHER_MATERIAL` ×6, `M_AND_A_ANNOUNCE` ×1 |
| GOVERNANCE | 2 | `OTHER_MATERIAL` (director-nominee signatures) |
| EARNINGS_RESULT | 1 | `OTHER_MATERIAL` ("financial results for") |

The June gap was **not** low-L1 after all — 10 L1 events (mostly financings) were buried in
`OTHER_MATERIAL` and are now surfaced. End-to-end smoke (MU, re-queued through the full worker):
producer → live reclassify → `OTHER_MATERIAL→EARNINGS_RESULT` → consumer reads `EARNINGS_RESULT`;
no duplicate event created (producer is `temperature=0`).

## Known follow-ups (NOT done here — out of scope)

- ~~The `_RULES` `REGULATORY` label does not match the consumers' `REGULATORY_ACTION`.~~
  **FIXED 2026-06-24** — the regulatory rescue label is now `REGULATORY_ACTION` in BOTH copies
  (`reclassify_live.py` on main + the v5 batch `reclassify.py`); reproduction gate held (97/97),
  and an `OTHER_MATERIAL`-buried regulatory event now rescues to a consumer-matched
  `REGULATORY_ACTION` that spawns regulatory + litigation. (Was latent: 0 events were leaking yet.)
- Tightening the producer prompt so financings/earnings stop landing in `OTHER_MATERIAL` in the
  first place is a **separate** task (the rescue is the safety net, not the cure).

## Operational notes

Going forward the guarded `yuclaw-event-worker.timer` drains new events **through** this live
reclassify. The corrected layer stays rebuildable from `yuclaw/v5/extract/reclassify.py` if needed.
Keep `reclassify_live.py`'s verbatim block in sync with the v5 batch module.
