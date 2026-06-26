# v5 Layer 1 — Prose-first text extraction (Order B, the root-cause fix)

Branch `v5-layer1`. Order A's honest finding: 22/37 filings grounded at **0.34** because the text
path fell back to `raw_cover` (XBRL/cover soup); clean prose grounded 0.75–0.89. This fixes the
text path — feed the swarm **prose**, not XBRL — measured A/B before adoption.

## Diagnosis (read-only)

`_acquire_text` fetched Exhibit 99.x **only when `et in EARNINGS_TYPES`**. FINANCING / M&A /
GOVERNANCE 8-Ks are not earnings types → exhibit fetch skipped → and they aren't 10-K/Q → MD&A
skipped → `raw_cover` (XBRL tag soup). Yet the **prose is available**: testing `extract_exhibit`
on the raw_cover FINANCING filings returned usable prose (indentures, "$2.25 BILLION TERM LOAN
CREDIT AGREEMENT"), 3–16k chars. Available-but-not-fetched. (M&A 8-Ks are the exception — their
substance is in the 8-K body, no Exhibit 99.x — genuinely no fetchable prose.)

## The fix (additive, text source only)

`_acquire_text`: try the exhibit extractor for **any 8-K** (not just earnings), keep `raw_cover`
as the fallback when no usable exhibit exists. **Reuses** `exhibit.py`/`narrative.py` (declared UA,
cached, rate-respecting). SourceLock, the corrected-event-type layer, the producer prompt, and the
reclassify logic are all **unchanged** — this changes only which TEXT the swarm reads.

## A/B — full corpus, Gemma worker (N=36; 38 attempted)

### The target set — 22 raw_cover filings: **0.34 → 0.74 base grounding (+0.39)**

| filing | source | before → after |
|---|---|---|
| GS FINANCING | raw_cover → exhibit | 0.00 → **1.00** |
| AXP FINANCING | raw_cover → exhibit | 0.17 → **1.00** |
| PSX FINANCING | raw_cover → exhibit | 0.11 → **1.00** |
| DELL/META/NVDA/PYPL/AMZN FINANCING | raw_cover → exhibit | 0.2–0.5 → **0.83–0.89** |
| MU M_AND_A (×2) | raw_cover → exhibit | 0.5–0.83 → **1.00** |
| HPE / INTC M_AND_A | raw_cover → raw_cover | 0.17 / 0.11 (no exhibit — unchanged) |

### Corpus-wide vs Order A (8B baseline 0.52)

| metric | Order A (raw_cover path) | **prose-first** |
|---|---:|---:|
| base grounding mean | 0.52 | **0.75** (+0.23) |
| base citation fidelity | 0.66 | **0.85** (+0.19) |
| specialist mean | 0.68 | 0.74 |
| text-source mix | raw_cover 22 / exhibit 12 / existing 3 | **raw_cover 7 / exhibit 26 / existing 3** |

15 filings converted raw_cover → exhibit prose. **Spawn accuracy held: FINANCING→no-M&A 14/14,
earnings→earningsquality 15/15** — better text did not mis-tag.

### No-regression on controls (clean-text, unchanged text)

Clean-text filings (already exhibit/existing) vary only stochastically (worker temp 0.4): META
0.92→1.00, MU 0.72→0.83, DELL 0.67→0.69; AMD 0.89→0.69 is the one dip — on **unchanged text**
(exhibit both runs), i.e. run-to-run noise, not a prose-first regression.

## Honest caveats

- **M&A 8-Ks (2 of 4) genuinely lack fetchable prose** — no Exhibit 99.x; substance is in the 8-K
  body. They correctly keep the `raw_cover` fallback (~0.17). A real finding: prose-first helps
  FINANCING strongly, M&A only where an exhibit exists.
- **C6: 1 leak (RKLB geopolitical emitted a direction)** — on a filing whose text was **unchanged**
  by this fix (exhibit both runs). C6 neutrality for risk-natured specialists is *prompt*-enforced,
  not code-forced, so an occasional temp-0.4 slip is expected (Order A's 0/37 vs this 1/36 are both
  in stochastic range); **not introduced by prose-first**. If leaks recur, code-forcing neutral for
  RISK_NATURED is the hardening (separate).
- Risk-channel discrimination sign flipped (in-sample, n=13) — a secondary, noisy metric.

## Decision

**Adopt prose-first `_acquire_text`** (committed). The win is unambiguous: target set +0.39,
corpus base 0.52→0.75, citation 0.66→0.85, no tagging regression. **Production follow-on** (not in
this branch-only order): the live ingestion should likewise persist exhibit prose to
`swarm_inputs.narrative_text` for FINANCING/M&A so the production swarm reads prose, not just the
validation path. raw_cover stays the fallback for genuine no-prose (M&A-body) filings.

## Safety
Branch-only, no deploy. `public.*` READ-ONLY. Additive (raw_cover fallback preserved). Producer
prompt (rejected, Order-B-prequel), reclassify logic, the cap, Ollama version, crons, Lab — all
untouched. EDGAR re-fetch via declared UA, cached, rate-respecting.
