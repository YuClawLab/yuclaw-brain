# v5 Layer 1 — Day 5B: Exhibit-Text Extraction + At-Scale Layer-1 Validation

Branch `v5-layer1`. Sequence: **complete the swarm before measuring it.** Part 1 unblocks the two
input-starved specialists (EarningsQuality, SentimentDrift) from Day 5A; Part 2 then validates the
whole of Layer 1 at scale and asks the honest question — do the specialists + risk channel earn
their cost? Model-agnostic (`WORKER_MODEL`, 8B). No deploy. (Layer 2 waits for this verdict.)

## Part 1 — Exhibit-text extraction (the real fix)

### Diagnosis
Day 5A left EarningsQuality + SentimentDrift grounding **0.0**: earnings/guidance 8-Ks store only
the cover ("see Exhibit 99.1") in `events_raw.raw_text`; the results/guidance prose is in the
**un-captured exhibit**. Same root-cause family as the Day-3 XBRL finding — the right text exists,
it just wasn't fetched.

**The exhibit is cleanly fetchable.** EDGAR exposes a per-filing directory `index.json` listing
every document. For the TSLA earnings 8-K it lists `exhibit991.htm` (50 KB — the actual Q1 release)
next to the 27 KB cover and the chart `.jpg`s. So the path mirrors Day-3: source_url → directory
listing → the exhibit doc.

### The extractor (`yuclaw/v5/extract/exhibit.py`)
**Reuses** `narrative.py`'s `fetch_primary` + `strip_filing` + `sanity_ok` (declared UA, polite
delay, disk cache) — not a fork. `find_exhibit_url()` reads the directory `index.json` and selects
the results body: prefer an Exhibit-99-named `.htm`; else the **largest `.htm` that is not the
primary/cover doc, an XBRL R-file, or an index**. This handles naming variance — TSLA's
`exhibit991.htm` AND PSX's non-standard `psx-2026_q1prexrelease.htm` both resolve correctly.
Output is additive to `yuclaw_v5.swarm_inputs` (`narrative_section='exhibit99'`); `public.*` is
read-only.

### HARD GATE (before → after, verbatim)

| specialist | filing | grounding BEFORE (cover) | grounding AFTER (exhibit) |
|---|---|---:|---:|
| EarningsQuality | TSLA earnings 8-K | **0.0** (0/3) | **0.67** (2/3, cites 3/3) |
| SentimentDrift  | PSX guidance-cut 8-K | **0.0** (0/2) | **0.50** (1/2) |

**GATE: PASS** — both starved specialists lift off zero on the extracted exhibit prose. All 10
specialists now ground on adequate input.

## Part 2 — At-scale Layer-1 validation

**N = 27 filings** (28 attempted; 1 dropped on an 8B JSON truncation — the same `num_predict`
class from Day 1/2; the harness skips and continues), spanning **8 corrected event types**
(13 EARNINGS_RESULT, 7 FINANCING, 4 M_AND_A, + GOVERNANCE/GUIDANCE_CUT/GUIDANCE_RAISE/EARNINGS_BEAT/
REGULATORY). Agent-only at this scale (the metrics below don't need the 70B); the 70B synthesis
separation + true cost are validated on a small full-pipeline subset (next section). In-sample,
point-in-time `price_history` for the forward-vol outcome.

| measurement | result |
|---|---|
| **Grounding distribution — base** | n=81 agent-runs, mean **0.52**, median 0.50, ≥0.5 in 51/81 |
| **Grounding distribution — specialists** | n=44, mean **0.59**, median 0.50, ≥0.5 in 30/44 |
| **Base citation fidelity** | mean **0.65** |
| **Spawn accuracy (corrected tags)** | FINANCING → no M&A specialist: **6/6**; earnings/guidance → EarningsQuality: **15/15** |
| **C6 risk/direction separation** | risk-natured specialists emitting a direction: **0/N — PASS** |

**Does the risk channel discriminate?** Forward 20-trading-day realized volatility after each event:

| risk flag | n | mean fwd-20d vol |
|---|---|---|
| elevated | 24 | **0.0405** |
| normal | 3 | 0.0325 |

Separation **+0.0080, correct sign** — elevated-flag names did realize higher forward volatility,
consistent with the C6 hypothesis. **But the honest caveat dominates: the flag is SATURATED** —
24/27 came out elevated, only 3 normal (DELL/MU earnings, AMZN financing). The aggregate takes the
*max* risk_view across base+specialists, and the base Bear agent nearly always reports high risk,
so the flag is almost always elevated. The sign is right; with n=3 in the normal arm the magnitude
is suggestive, not conclusive, and the channel is a **weak discriminator as currently built**.

## Honest verdict — do the specialists + risk channel earn their keep?

A mixed, dimension-by-dimension answer (not a blanket yes):

**Earns its keep:**
- **Deterministic spawn on corrected tags is now exact** — 6/6 financings no longer mis-spawn the
  M&A specialist (the Day-4 bug), 15/15 earnings/guidance correctly spawn EarningsQuality. This is
  a clean, measurable win and the reason Part 1 had to come first.
- **Specialists ground at least as well as the base swarm** (0.59 vs 0.52 mean) — they add
  event-typed evidence without degrading grounding. The exhibit fix made earnings/guidance
  specialists viable (0.0 → 0.5–0.67).
- **C6 separation holds at scale** — 0 risk-natured specialists leaked a direction across N=27.
  Direction and risk stay cleanly separate; this is the architectural property the whole design
  exists to guarantee, and it survives scale.

**Does NOT yet earn its keep:**
- **The risk channel barely discriminates as built.** It points the right way (elevated → +0.008
  higher forward vol) but is **saturated at "elevated" (24/27)** because it aggregates risk_view by
  `max()` and the Bear agent floods it. A flag that fires 89% of the time carries little
  information. **This is the real finding to fix before Layer 2 leans on it**: use a graded/median
  risk aggregation (or calibrate the Bear's risk_view) so "elevated" is rare and meaningful — the
  same lesson C6 itself encodes (extreme labels must be rare by construction).
- **Cost is real:** ~75s/filing agent-only at this worker count (8B), dominated by the base swarm;
  specialists add concurrent GPU load, not much wall-time. Full pipeline (with 70B) is ~3× that.

**Bottom line for the Layer-2 gate:** the spawn-accuracy and C6-separation machinery is sound and
earns adoption; **the risk channel needs a rare-by-construction recalibration before it can drive
anything downstream.** That recalibration — not Layer 2 — is the next step the data points to.

### Full-pipeline subset (70B synthesis separation + true cost)

Two representative filings run through the FULL pipeline (70B synthesis) to validate the one thing
the agent-only scale run doesn't exercise — that synthesis keeps direction/risk separate — on the
new event types:

| filing | spawned | synth direction | synth risk flag | separate channels | C6 |
|--------|---------|-----------------|-----------------|-------------------|----|
| TSLA earnings (exhibit-fed) | earningsquality | positive | elevated | **YES** | none |
| HPE regulatory (4 specialists) | regulatory+litigation+macro+geopolitical | positive | elevated | **YES** | none |

Both came out **positive direction WITH elevated risk** — the C6 demote-not-flip property holds at
the full-pipeline level on exhibit-fed earnings and on the densest 4-specialist filing.
**Full-pipeline cost: 243s/filing** (vs ~75s agent-only — the 70B synthesis is ~70% of wall-time).

## Production safety
Branch-only, no deploy. `public.*` READ-ONLY; additive to `yuclaw_v5.*` only (exhibit narratives
persist=False this run; corrected-tag layer unchanged). `swarm_outputs` untouched (Day-3 v2
baseline intact). 8B worker only (no Gemma / no 2nd daemon). Crons intact, main/Lab untouched,
Ollama not reconfigured. EDGAR hit with declared UA, rate-respecting, disk-cached.

## Cross-references
- Exhibit extractor: `yuclaw/v5/extract/exhibit.py` (reuses `narrative.py`)
- At-scale harness: `yuclaw/v5/swarm/tests/validate_scale.py`, gate `tests/smoke_exhibit.py`
- Day 5A (the specialists + the input finding this fixes): `docs/v5/layer1/day5a.md`
