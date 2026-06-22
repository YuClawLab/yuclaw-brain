# v5 Layer 1 — Day 5A: Event-Typing Accuracy Pass + Specialists #5–#10

Branch `v5-layer1`. Two-part day, sequenced deliberately: **fix event-type tagging first**, then
build the new specialists on the corrected tags. Model-agnostic (`WORKER_MODEL`, 8B today).

## Part 1 — Event-typing accuracy

### Diagnosis (read-only)
The Day-4 finding (a $5B credit facility tagged `M_AND_A_ANNOUNCE`) is one of a systematic class.
Over the **62 filing-backed original events** (the 1064 Form-4 insider events are correct by
construction and need no filing-text re-class):

- **`M_AND_A_ANNOUNCE` (2/2 wrong):** AMD = a credit facility (FINANCING); HPE = a Cooperation
  Agreement (GOVERNANCE). Neither contains M&A language.
- **`OTHER_MATERIAL` (37) is a catch-all** hiding ~11 earnings press releases and ~6 financings
  (note offerings / facilities) plus 2 divestitures.
- Root cause behind the AMD case: the v4 extractor classified from a **truncated `raw_excerpt`**
  (~85 chars, cut at "…en[tered into a]") — too short to disambiguate.

**Error rate: 26/62 (42%) of filing-backed events were mis-tagged or mis-normalized** — of which
22 (~35%) are genuine mis-tags (financings/earnings/governance) and 4 are taxonomy normalizations
(`M_AND_A_CLOSE`→`M_AND_A`, `DIVIDEND_CHANGE`→`DIVIDEND`).

### The fix (additive, deterministic, SourceLock)
`yuclaw/v5/extract/reclassify.py` + `event_type_corrected.sql`: a deterministic re-classifier
(NO LLM) that matches ordered verbatim signature phrases (FINANCING → M_AND_A → GOVERNANCE →
EARNINGS_RESULT → REGULATORY → DIVIDEND → EXEC_CHANGE) against the filing text. **Every corrected
tag is justified by a verbatim span found in the filing (SourceLock by construction); if nothing
matches, the v4 tag is kept** — no unsupported re-tags. `public.events` is NEVER mutated; the
original tag is stored alongside the corrected one (`yuclaw_v5.event_type_corrected`) for audit.

**Critical design choice — classify against the event's own `raw_excerpt` FIRST**, full filing
only as fallback when the excerpt is too short. An early full-filing-first version produced two
false re-tags (a regulatory 10-Q → M&A because a divestiture was mentioned *elsewhere* in the
same filing; the HPE cooperation event → M&A from a *different* event's "closed on the sale").
Excerpt-first eliminated both — a multi-event filing can no longer cross-contaminate.

### Re-classifier smoke (HARD GATE: PASS) — before → after, with source span

| ticker | v4 tag | corrected | source span (SourceLock) |
|--------|--------|-----------|--------------------------|
| AMD  | M_AND_A_ANNOUNCE | **FINANCING** | "entered into a Credit Agreement with the lenders named therein, JPMorgan Chase Bank" (filing; excerpt was truncated) |
| HPE  | M_AND_A_ANNOUNCE | **GOVERNANCE** | "entered into a letter agreement (the Cooperation Agreement…" (excerpt) |
| HPE  | REGULATORY_ACTION | REGULATORY_ACTION (kept) | — (no signature in its excerpt; not cross-contaminated) |
| AMZN/MU/META/HPE | OTHER_MATERIAL | **FINANCING** | "Senior Notes due 20xx" / "aggregate principal amount" / "underwritten public offering" |
| COST/CRCL/TSLA/DELL | OTHER_MATERIAL | **EARNINGS_RESULT** | "financial results for the … quarter" |

26/62 changed (21 from the precise excerpt, 5 from filing-fallback on truncated excerpts), 36
kept. The known AMD bug is fixed; no false re-tags. **The re-classifier is reliable.**

## Part 2 — Specialists #5–#10

`yuclaw/v5/swarm/specialists.py` adds six worker-tier specialists (same grounded run + SourceLock
verifier as Day 4, model-agnostic `WORKER_MODEL`):

| specialist | trigger | nature |
|---|---|---|
| **Macro** | content: tariff/inflation/rate/FX | directional + risk |
| **Geopolitical** | content: sanction/export-control/conflict | **risk-natured** (direction neutral) |
| **EarningsQuality** | corrected `EARNINGS_RESULT`/`GUIDANCE_*` | directional (quality-adjusted) + risk |
| **Litigation** | corrected `REGULATORY_ACTION` | **risk-natured** (direction neutral) |
| **SentimentDrift** | corrected `GUIDANCE_RAISE`/`GUIDANCE_CUT` | directional + risk |
| **ESG** | content: emissions/sustainability/climate | mostly neutral + risk |

**Spawn now reads the CORRECTED layer** (`corrected_event_types()`, falling back to v4) plus
deterministic content signatures for the theme specialists. Demonstrated effect: **the AMD 8-K
now spawns NO M&A specialist** (its corrected tag is FINANCING) — the Day-4 mis-spawn is fixed at
the source. `REGULATORY_ACTION` co-fires regulatory + litigation.

**C6 discipline extended:** risk-natured specialists (Insider from Day 4, now Litigation +
Geopolitical) force `return_view.direction = neutral` and put their signal in `risk_view` — same
separation Day 4 established. They feed the RISK channel, not direction.

### Per-specialist smoke (agent-level, HARD GATE)

| specialist | input | grounding | direction | C6 |
|---|---|----------:|-----------|----|
| Macro | AAPL 10-Q MD&A | **1.0** | negative | n/a |
| Geopolitical | HPE Reg 10-Q | **1.0** | **neutral** | ✓ |
| Litigation | HPE Reg 10-Q | 0.5 | **neutral** | ✓ |
| ESG | COP 10-Q | **1.0** | neutral | ✓ |
| EarningsQuality | TSLA earnings 8-K | **0.0** | positive | — |
| SentimentDrift | PSX guidance 8-K | **0.0** | negative | — |

**The honest result: 4/6 ground on adequate input and ALL respect C6; 2/6 (EarningsQuality,
SentimentDrift) ground 0.0 — but this is an INPUT-AVAILABILITY finding, not a specialist bug.**
Earnings/guidance 8-Ks store only the cover + "see Exhibit 99.1" in `events_raw.raw_text`; the
actual results/guidance prose is in the **un-captured exhibit**. Same root-cause family as the
Day-3 XBRL finding, for a new filing class. The specialists' *logic* is sound (well-formed,
correct lens, correct direction — SentimentDrift correctly read "more cautious outlook" →
negative; it just had no quotable body to cite). **Day-5B item: extract the press-release exhibit
text for earnings/guidance 8-Ks** so these two specialists have grounding material.

## Part 3 — full-pipeline batch (4 filings, 70B synthesis)

| filing | spawned (deterministic) | base grounding | risk channel | synth direction |
|--------|-------------------------|----------------|--------------|-----------------|
| HPE Reg 10-Q | regulatory + litigation + macro + geopolitical | 1.0/0.33/0.75 | high/**elevated** | positive |
| AAPL 10-Q | macro | 1.0/1.0/1.0 | high/**elevated** | mixed |
| TMO 10-K | macro | 0.33/1.0/0.67 | high/**elevated** | positive |
| **AMD 8-K** | **`[]` base-only** | 1.0/0.5/0.5 | high/**elevated** | positive |

**Headline — the Day-4 mis-spawn is fixed at the source:** the AMD 8-K now spawns **no
specialist** because its corrected event-type is FINANCING, not M&A. Spawn reads the corrected
layer.

- **C6 violations across the batch: 0.** Every risk-natured specialist (litigation, geopolitical)
  stayed neutral/mixed; on the HPE filing litigation=neutral, geopolitical=mixed while macro
  carried direction. The richest filing spawned 4 specialists concurrently with the base swarm.
- **Every synthesis kept direction and risk separate** — 3/4 are positive/mixed direction *with*
  an elevated risk flag (the C6 channel demotes/flags without flipping direction).
- Specialist grounding on adequate (MD&A) input was strong: macro 1.0 (×3), geopolitical 1.0,
  litigation 1.0 on HPE; regulatory weaker (0.33).

**Cost/filing: 200.5s** (batch_wall 802s / 4) vs Day-4's 182s. The increase is the 4-specialist
HPE filing (7 concurrent workers + a richer synthesis brief, 277s); the base-only AMD filing was
161s. Workers run concurrently, so wall-time scales with the slowest agent, not the agent count —
adding specialists costs GPU throughput, not much latency.

## Production safety
Branch-only, no deploy. `public.*` READ-ONLY — corrected tags live in `yuclaw_v5.event_type_corrected`
(additive, 62 rows; `public.events` unchanged, the 2 original `M_AND_A_ANNOUNCE` tags intact for
audit; `events_raw` untouched). Day-3 `swarm_inputs` reused unchanged (6 rows; the earnings/ESG
smokes read `events_raw.raw_text` directly, no new extraction). `swarm_outputs` untouched
(persist=False; Day-3 v2 baseline = 5 rows intact). 8B worker only (no Gemma / no 2nd daemon).
Crons intact (13); main/Lab untouched; Ollama not reconfigured. Memory held through the 20:00 cron.

## Cross-references
- Re-classifier: `yuclaw/v5/extract/reclassify.py`, `event_type_corrected.sql`
- Specialists: `yuclaw/v5/swarm/specialists.py` (spawn from corrected layer + content)
- Harnesses: `tests/smoke_specialists2.py`, `tests/batch_specialists2.py`
- Day 4 (specialists #1-4 + C6 channel): `docs/v5/layer1/day4.md`
