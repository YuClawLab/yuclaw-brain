# v5 Layer 1 — Day 2 writeup: Grounding & Citation Discipline

Branch `v5-layer1`. Builds on Day 1 (`day1.md`), which surfaced the fabrication
problem: a v1 bull claimed "debt decreased" while a v1 bear claimed "debt
increased" on the SAME filing. Day 2 makes every agent claim *programmatically*
traceable to a verbatim span of the source filing — the proto-form of Layer 2's
evidence tokens — and nothing trusts the model.

## Architecture

### Grounded output schema (agents.py, `PROMPT_VERSION = "v2"`)
`key_points` are no longer bare strings. Each is now an object:

```json
{"point": "<claim, one sentence>", "quotes": ["<span copied VERBATIM from the filing>", ...]}
```

The v2 role prompts instruct each agent that (1) every key_point must carry ≥1
verbatim quote, (2) any number/%/$ in the claim must appear inside one of its
quotes, (3) unquoted or mis-numbered claims will be DISCARDED, (4) it must never
invent a quote — drop the point instead. `return_view` + `risk_view` (Day-1 dual
channel) are retained.

### The verifier (grounding.py — deterministic, NO LLM)
- `verify_citation(quote, filing_text)` — exact substring match first, then a
  whitespace/case-normalized match (filings are full of ragged whitespace), with
  the located offsets mapped back to the **original** text.
- `verify_numbers(point, verified_quotes)` — every number token in a claim
  (comma-stripped digit core) must appear inside that claim's verified quotes.
  Catches altered/fabricated figures even when a real quote is attached.
- `grade_agent(output, filing)` — a key_point is **grounded** iff it has ≥1
  verified quote AND all its numbers are inside those quotes; otherwise
  **discarded** (with reason). Emits per-agent
  `{citations_total/verified, points_grounded/discarded, grounding_rate}` and the
  **ledger** (de-duplicated verified spans) — the proto evidence token.
- Unit tests (`tests/test_grounding.py`, 11 cases): verbatim hit, normalized hit,
  paraphrase miss, fabricated-number catch, substring non-spuriousness, end-to-end
  grade. All pass before any LLM runs.

### Synthesis upgrade (70B)
Synthesis now receives ONLY the grounded claims (with their verified quotes);
discarded claims are listed separately as "unverified — DO NOT USE". Its prompt
requires per-finding attribution to a verbatim quote and explicitly preserves
genuine quote-backed BULL/BEAR disagreement. The orchestrator then verifies the
synthesis's own cited quotes and assembles the final `citation_ledger`
(accession + the union of verified spans, tagged by source) — persisted to
`yuclaw_v5.swarm_outputs` (new columns `grounding_summary`, `citation_ledger`,
prompt_version `v2`).

## The money exhibit — Day-1 contradiction, re-examined (smoke gate: PASS)

On the contradiction filing `0000097745-26-000018` (Thermo Fisher 10-K):

- BULL: "reduced its debt-to-equity ratio" → **DISCARDED** — its quote
  `"Debt to equity ratio was 0.94 at December 31, 2022."` is **NOT FOUND** in the
  filing (fabricated).
- BEAR: "total debt rising to $575 million" → **DISCARDED** — its quote
  `"Total debt was $575 million at December 31, 2025."` is **NOT FOUND** (fabricated).
- The verifier caught **9/9** bull+bear citations as fabricated.

**The Day-1 contradiction was never real evidence — it was two hallucinations,
and grounding discards both** rather than publishing a fake debate. This is
exactly the failure Day 2 set out to kill.

## Data finding that reframes the problem (the key Day-3 input)

The same smoke exposed *why* the agents fabricate. The text the agents read
(first 6000 chars of `raw_text`) for this filing is the **XBRL financial-
statements R-file**, not MD&A prose: 58 `http://fasb.org/...` taxonomy URLs in the
window, e.g. `"tmo-20251231 ... P3Y http://fasb.org/us-gaap/2025#LongTermDebt..."`.
There is **no quotable prose** for a financial claim, so the 8B invents plausible
sentences (all discarded), and the skeptic "grounds" by quoting the URLs that
literally appear (degenerate but technically verbatim).

Grounding quality therefore tracks **input text quality**, which varies sharply by
form/section:

| form (filing)        | XBRL urls in 6k | character |
|----------------------|----------------:|-----------|
| 8-K (HPE)            | 0               | real press-release prose |
| 10-Q (AAPL)          | 4               | XBRL cover then mixed    |
| 10-K (TMO)           | 58              | pure XBRL R-file         |

## Prompt-iteration history (Phase 5 — agent-only, 3 diverse filings)

Target: grounding_rate ≥ 0.85 per agent with ≥ 3 grounded points, on an 8-K, a
10-Q and a 10-K. Per-agent mean grounding_rate by round:

Mean grounding_rate per agent (per-filing rates 8-K / 10-Q / 10-K in brackets):

| round | change                              | bull            | bear            | skeptic         |
|-------|-------------------------------------|-----------------|-----------------|-----------------|
| 1     | v2 baseline, temp 0.4               | 0.50 [1.0/0.0/—]\* | 0.33 [0.67/0.0/—]\* | 0.62 [1.0/0.25/—]\* |
| 2     | + strong anti-fabrication rules     | 0.11 [0.33/0.0/0.0] | 0.50 [0.5/1.0/0.0] | 0.72 [0.67/0.5/1.0] |
| 3     | anti-fab + **temp 0.2** (final)     | 0.33 [1.0/0.0/0.0]  | 0.33 [0.67/0.33/0.0] | **0.81** [0.75/1.0/0.67] |

\* Round 1's 10-K slot failed on a harness idempotency bug (the smoke had already
run v2 on that accession, so the re-enqueue returned `succeeded` jobs and the
workers found nothing to claim → timeout). Fixed by cleaning prior jobs per
accession each round; rounds 2–3 cover all three filings.

**Read-out.** Two things are stable across rounds: (a) on prose-rich text (the
8-K) the agents ground well — the bull hits 1.00 at temp 0.2; (b) on XBRL-dominated
text (the 10-K, and the 10-Q cover) bull/bear collapse to ~0 because there is
nothing to quote, while the skeptic stays high (it grounds by quoting the
structural/boilerplate text it critiques). 8B grounding is also **high-variance
run-to-run** at temp 0.4 (the 8-K bull swung 1.00→0.33 between identical-input
rounds), so prompt-wording effects are partly masked by sampling noise. Lowering
temperature to **0.2** was the most effective single lever (skeptic 0.62→0.81; bull
restored to 1.00 on prose), so it is the final config. The anti-fabrication wording
helped honesty (fewer invented quotes) but did not move the aggregate.

**Capability finding (do NOT lower the bar):** prompt iteration alone cannot reach
≥85%/≥3-points across diverse forms, because the binding constraint is the input
text, not the prompt. The verifier works perfectly; the agents are simply being
fed the wrong section. This shapes Day 3: extract the **MD&A / narrative prose**
(skip the XBRL R-file), chunk long filings, inject candidate spans, and/or use a
larger agent model. The grounding harness built today is the measurement
instrument for that work.

## Validation batch (Phase 6 — 5 filings, full path, persisted v2)

5 diverse filings end-to-end with the final config (temp 0.2), all persisted to
`swarm_outputs` (prompt_version `v2`) with grounding_summary + citation_ledger:

| filing            | form | bull | bear | skeptic | ledger spans |
|-------------------|------|-----:|-----:|--------:|-------------:|
| HPE 0001645590…52 | 8-K  | 1.00 | 0.50 |   0.67  | 6 |
| AAPL 0000320193…13| 10-Q | 0.00 | 0.00 |   1.00  | 5 |
| TMO 0000097745…18 | 10-K | 1.00 | 0.00 |   1.00  | 8 |
| AMD 0001193125…46 | 8-K  | 1.00 | 0.50 |   1.00  | 5 |
| JNJ 0000200406…87 | 10-Q | 0.00 | 1.00 |   1.00  | 8 |
| **mean**          |      | **0.60** | **0.40** | **0.93** | 32 total |

- **Verifier saves**: every ungrounded claim was discarded before reaching
  synthesis. At temp 0.2 the residual fabrications were whole invented quotes
  (caught as "no verified quote"); 0 were altered-number cases specifically — the
  agents either grounded honestly or were blocked. 32 verified spans entered the
  ledgers.
- **skeptic mean 0.93** clears the 0.85 rate bar (held back from a full PASS only
  by min_grounded_points=2 on the prose 8-K, where it made 3 points and grounded 2).
  **bull 0.60 / bear 0.40** are split bimodally — ~1.0 on prose 8-Ks, ~0.0 on the
  XBRL 10-Q covers — confirming the data-bound ceiling, not a prompt failure.

## Cost constant (v2 vs Day 1)

Grounding is not free. Two token-budget bumps were forced by the richer schema,
each first surfaced as a truncated-JSON failure (the same class as Day 1's agent
truncation — `format=json` runs out of tokens mid-string):

- **Agents**: `num_predict` 768 (Day-1 value, retained) — the v2 quote arrays fit.
- **Synthesis**: `num_predict` 640 → **1024** (`YUCLAW_V5_SYNTH_NUM_PREDICT`). The
  v2 synthesis emits `key_findings` each with a verbatim quote plus a
  `disagreements` array, which overran 640 on prose filings. Effect on latency:
  synthesis ~115s (640, Day-1 schema) → **~145s** (1024, grounded schema) on a
  warm 70B for a prose filing.

Per-filing wall-clock on a quiet box (temp 0.2): agents run concurrently
(~40–55s wall), synthesis ~90s (XBRL, short output) to ~145s (prose, full output).

**Measured cost/filing across the validation batch**: total **162s** (batch_wall
811s / 5), of which synthesis **119s** avg; ~1150 agent eval-tokens + ~500 synth
eval-tokens per filing. Versus Day 1 (~130s/filing), grounding costs **~+30s/filing**
— the price of the larger synthesis budget and the longer grounded prompts. The
deterministic verifier itself is ~free (sub-millisecond, no LLM).

## What this hands Layer 2

- A deterministic **evidence verifier** (exact + normalized span location, number
  checking) that any layer can call — no LLM, no trust.
- The **citation_ledger** per filing: accession + verified verbatim spans
  (offsets, source agent) — the proto evidence token Layer 2 formalises.
- A grounding **measurement harness** (`iterate_grounding.py`) to drive prompt /
  context / model changes against a hard, programmatic metric.

## Production safety

Isolated `yuclaw_v5` schema only (additive columns; DDL in
`yuclaw/v5/swarm/swarm_outputs.sql`). No writes to `public.*` (v4). Crons
untouched, main/Lab untouched, Ollama not reconfigured. 70B-heavy phases scheduled
clear of the `:00`/`:30` `check_nemotron` cron windows.

## Cross-references
- Day 1: `docs/v5/layer1/day1.md`   | Design inputs: `docs/v5/layer1/design_inputs.md`
- Verifier: `yuclaw/v5/swarm/grounding.py` (+ `tests/test_grounding.py`)
- Schema/prompts: `yuclaw/v5/swarm/agents.py`   | Orchestrator: `yuclaw/v5/swarm/orchestrator.py`
- Harnesses: `tests/smoke_grounded.py`, `tests/iterate_grounding.py`, `tests/batch_validation.py`
