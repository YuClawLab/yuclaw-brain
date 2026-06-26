# v5 Layer 1 — Gemma at-scale validation (Order A)

Branch `v5-layer1`. Two parts: (1) fix the harness synthesis key-nesting bug, then (2) re-validate
the full Gemma swarm across the corpus to see whether the 0.95 grounding holds **at scale**.

## Part 1 — harness fix

`tests/gemma_swap_ab.py` read synthesis at `res['synthesis']` but the validated output is nested
under `res['synthesis']['output']` (see `_validate_day4_synth`), showing phantom `direction=None`.
Fixed to read the correct nesting. Verified on one filing: now renders
`synth direction=positive risk_flag=normal (separate-channels YES)` — real values, not None.

## Part 2 — full-corpus batch (N=37; 38 attempted, 1 dropped on 8B-class JSON truncation)

Agent-only (matches the 8B D5B methodology for a fair grounding comparison), Gemma worker
(`gemma4:26b-a4b-it-q4_K_M`, think=false, num_ctx=8192). 1443s total, **39 s/filing**. Memory
held **~49–91 GiB available throughout** (incl. the 23:00 oil/swarm cron window) — no OOM.
Results persisted: `docs/v5/layer1/data/scale_gemma_2026-06-26.json`.

### Grounding — overall vs the 8B baseline (D5B)

| metric | 8B baseline (D5B) | **Gemma (this run)** |
|---|---:|---:|
| base agents mean | 0.52 | **0.52** (no gain at base) |
| specialists mean | 0.59 | **0.68** (+0.09) |
| base citation fidelity | 0.65 | 0.66 |

### Why base didn't move — it's TEXT QUALITY, not the model

Base grounding splits sharply by **text source** — and the corpus is dominated by the poor one:

| text source | n (agent-runs) | base grounding |
|---|---:|---:|
| existing (Day-3 narrative prose) | 9 | **0.84** |
| exhibit99 (extracted earnings prose) | 36 | **0.75** |
| **raw_cover (8-K cover / XBRL tag soup)** | 66 | **0.34** |

…and by event type, exactly tracking which types fall back to `raw_cover`:

| event type | n | base grounding | text |
|---|---:|---:|---|
| EARNINGS_BEAT | 3 | 0.89 | prose |
| GUIDANCE_CUT / REGULATORY / GOVERNANCE | 3/3/6 | 0.81–0.83 / 0.75 | prose |
| EARNINGS_RESULT | 39 | 0.69 | mostly exhibit |
| **M_AND_A** | 12 | **0.40** | raw_cover |
| **GUIDANCE_RAISE** | 3 | **0.33** | raw_cover |
| **FINANCING** | 42 | **0.29** | raw_cover |

**22 of 37 filings fall back to `raw_cover`** (financing/M&A have no fetchable exhibit/MD&A), where
grounding is ~0.34 for ANY model — the same XBRL/cover-text ceiling the 8B hit (8B base was also
0.52). On clean text Gemma grounds at **0.75–0.89**.

### Per-specialist grounding (the durable Gemma win)

`litigation 1.00 (n1)`, `geopolitical 0.81`, `earningsquality 0.78`, `regulatory 0.67`,
`esg 0.67`, `ma 0.56`, `macro 0.54`, `sentimentdrift 0.50`, `supplychain 0.00 (n1)` — **mean 0.68
vs 8B 0.59**. Gemma's improvement concentrates on the specialists, consistent with the A/B.

### Other dimensions (all hold at scale)

- **C6 risk/direction separation: 0 leaks across N=37 — PASS.**
- **Spawn accuracy:** FINANCING → no M&A specialist **14/14**; earnings/guidance → earningsquality
  **16/16**.
- **Risk channel discriminates:** elevated fwd-20d vol 0.0449 vs normal 0.0355, **sep +0.0094**
  (correct sign), elevated base rate 10/37 (27% — count≥2 still rare).

## Honest verdict — does 0.95 hold at scale?

**No — base grounding at corpus scale is 0.52, not 0.95.** But the regression is **text-gated, not
a Gemma weakness**: the single-filing 0.95/1.00 was on clean exhibit prose, and Gemma still grounds
**0.75–0.89 on clean-text filings**; the corpus mean is dragged down by the 22 raw_cover
financing/M&A filings (~0.34), where every model is capped by uninterpretable XBRL/cover input.
**Gemma's real, durable win is on the specialists (0.68 vs 0.59, +0.09)** plus a faster, well-formed
worker. C6, spawn, and risk-discrimination all hold at scale.

**The lever for higher base grounding is the SAME as before — better text extraction for
financing/M&A (raw_cover → prose)**, not the worker model. Adopting Gemma is still correct (specialist
gain + well-formed JSON + faster), but the "0.95" headline only applies to clean-text filings.

## Production safety
Branch-only, no deploy. `public.*` READ-ONLY; outputs additive/versioned (new JSON, baseline
untouched). Daemon cap, Ollama version, producer prompt, reclassify, crons, Lab — all untouched.
