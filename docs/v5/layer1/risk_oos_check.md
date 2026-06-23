# v5 Layer 1 — Risk-Channel Out-of-Sample Check

Branch `v5-layer1`. Single purpose: confirm the Day-5C `count≥2` risk aggregation holds its
**positive sign** (elevated → higher forward vol) on filings it was **not** tuned on, before
Layer 2 builds on it. Frozen config (`YUCLAW_RISK_AGG=count2`, exactly as committed in `c28f8542`)
— no re-tuning to this batch. Model-agnostic (`WORKER_MODEL`, 8B). No deploy.

## The honest constraint — there is no same-regime held-out data

D5C tuned/measured `count≥2` on the **L1 corpus**: the 8 event types
(EARNINGS_RESULT/BEAT, GUIDANCE_RAISE/CUT, M_AND_A, FINANCING, GOVERNANCE, REGULATORY_ACTION),
run as **base swarm + spawned specialists**. The decisive PHASE-1 finding:

- `_filings()` returns **28** filings today — **identical** to the D5C set. The only accession not
  in the D5C success rows is **META FINANCING**, which is the 28th filing that *failed* during D5C
  (8B JSON truncation) — it was part of the D5C attempt set, **not** held-out.
- The newest L1-qualifying event in the corpus is **2026-06-02**, which *predates* the D5C run
  (2026-06-14). No new L1-type filings have been ingested since. `price_history` is fresh through
  today, so this is not a maturation lag — **the corpus simply has not grown.**

**So the number of genuinely held-out, same-regime (L1-type, base+specialist) filings is ZERO.**
Per the honesty gate, we do **not** pad with D5C filings, do **not** shrink the forward window, and
do **not** call an in-sample re-run "validation." The same-regime out-of-sample sign-confirmation
**cannot be done yet** and must wait for new L1-type filings to be ingested and mature.

## What OOS data *does* exist — and what it can (and cannot) test

There are **34** filings of event types **never used to tune `count≥2`**: OTHER_MATERIAL (18),
EXEC_CHANGE (14), DIVIDEND (2). 33/34 have usable text; 34/34 have a computable forward-20d vol.
These are genuinely unseen — but they **spawn no specialists** (`spawn_specialists()` → `[]` for
these types), so they exercise the risk channel in a **base-only regime** (bull/bear/skeptic only).

This is a different regime from the one `count≥2` was measured in. Under base+specialists, `count≥2`
reaches its 2nd "high" via a hot specialist (geopolitical/litigation/etc.); base-only, it can only
fire if Bull or Skeptic also goes high — which the D5C diagnosis showed is rare. So this batch can
test **one half** of the pass criterion rigorously and **cannot** test the other:

- **CAN test (and it's a real OOS test):** does `count≥2`'s *rare-by-construction* property
  generalize to unseen filings — does it stay rare while `max()` re-saturates via Bear?
- **CANNOT test:** the forward-vol *sign* on a populated elevated arm — base-only filings rarely
  trip elevated, so the elevated arm is too small to measure separation honestly.

## OOS run (frozen `count2`, N=34, agent-only, base-only regime)

**Diagnosis carries over unchanged:** the Bear floods "high" on **30/34 (88%)** out-of-sample
(Bull 0%, Skeptic 0%); 30/34 elevated-by-a-single-agent are the Bear — the same mechanism as
in-sample. (The only specialist that spawned at all was ESG on 2 filings, never "high".)

| candidate | elev rate | n_elev / n_norm | vol_elev | vol_norm | separation |
|---|---:|---:|---:|---:|---:|
| `max` (D5B baseline, replaced) | 88% | 30 / 4 | 0.0319 | 0.0361 | **−0.0042** (wrong sign) |
| **`count≥2` (ADOPTED, frozen)** | **0%** | **0 / 34** | — | 0.0324 | **— (no elevated arm)** |
| exclude-bear max | 0% | 0 / 34 | — | 0.0324 | — |
| mean ≥ 1.2 | 74% | 25 / 9 | 0.0303 | 0.0383 | −0.0080 |
| mean ≥ 1.34 | 0% | 0 / 34 | — | 0.0324 | — |

Two things stand out. **(1)** `count≥2` fires elevated **0/34** out-of-sample — it does **not**
re-saturate; in the base-only regime it is maximally conservative, because reaching a 2nd "high"
requires Bull or Skeptic (≈never) or a specialist (none spawn here). The rare-by-construction
property generalizes. **(2)** the replaced `max()` again discriminates the **wrong way**
out-of-sample (−0.0042), echoing the D5C in-sample finding that the saturated aggregator is a
non-discriminator — independent corroboration that replacing it was correct.

## Verdict

**INCONCLUSIVE** — and that is the truthful outcome, not a hedge.

Against the pre-committed logic:
- **PASS** required elevated to stay rare (20–40%) **AND** a correctly-signed separation on a real
  normal arm (n_norm ≥ ~10). `count≥2` is rare (in fact 0%), but it produced **no elevated arm at
  all** (n_elev = 0), so the sign clause cannot be satisfied. Not a pass.
- **FAIL** required the sign to flip or vanish out-of-sample on the adopted config. `count≥2` did
  **not** flip — it simply did not fire in this regime. (The *old* `max()` does show the wrong sign
  OOS, but `max()` is not the adopted config; that is corroboration for the D5C decision, not a
  failure of `count≥2`.) Not a fail.
- **INCONCLUSIVE** required the held-out batch to be the wrong shape for the arms to mean anything.
  This is exactly the case: **zero same-regime (L1-type, base+specialist) held-out filings exist**,
  and the only available unseen filings run base-only, where `count≥2` cannot populate an elevated
  arm. The D5C **+0.0078 remains in-sample-only (N=27) — neither confirmed nor refuted OOS.**

**What we *did* learn (genuine, just not the sign):**
1. `count≥2`'s rare-by-construction property **generalizes** to 34 unseen filings — it does not
   re-saturate (0% vs `max()`'s 88%). The specific failure mode we were testing for (re-saturation)
   did **not** occur.
2. A real architectural property surfaced: under `count≥2`, **"elevated" requires specialist
   corroboration** (≥2 highs) **or the insider-sell gate** — the structurally-pessimistic Bear
   alone can never trigger it. On event types that spawn no specialist the risk channel is
   intentionally silent. For L1-type filings (which do spawn specialists) this is the intended
   discrimination; Layer 2 must know the flag only fires meaningfully on specialist-spawning events.

**Implication for the Layer-2 gate:** the OOS sign-confirmation this check set out to provide is
**not yet available** — the corpus has no fresh same-regime filings. Layer 2 should remain gated on
this confirmation. The correct next action is to **wait for ≥~10 new L1-type filings** (which spawn
specialists) to be ingested and mature a 20-day forward window, then re-run *this exact check*
(`risk_oos_capture` pointed at the new L1 filings + `risk_recal_analyze`). Proceeding into Layer 2
before then means leaning on a risk channel whose discrimination is established **in-sample only**
(N=27, +0.0078) — a known, bounded risk to record, not to paper over.

## Production safety
Branch-only, no deploy. `public.*` READ-ONLY; additive to `yuclaw_v5.*`/tests only; persist=False
(Day-3 baseline intact). 8B worker only (no Gemma / no 2nd daemon). Crons/main/Lab untouched,
Ollama not reconfigured. No session wakeup re-armed.

## Cross-references
- The recalibration under test: `docs/v5/layer1/day5c_risk_recal.md`, `specialized._risk_channel`
- OOS capture + A/B (reused): `tests/risk_oos_capture.py`, `tests/risk_recal_analyze.py`
