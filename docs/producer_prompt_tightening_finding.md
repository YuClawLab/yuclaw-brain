# Producer-prompt tightening — A/B finding (DON'T SHIP)

**Date:** 2026-06-25. **Outcome:** the tightened producer prompt **fails the precision gate** — kept
**out of production**. The live producer (`v2.txt` + `sourcelock.EVENT_TYPES`) and the reclassify
rescue layer are **unchanged**. This documents the negative result.

## Diagnosis (the dumping)

Using the corrected-layer (`yuclaw_v5.event_type_corrected`) as ground truth: **28/38 L1 events
(74%) were dumped into OTHER_MATERIAL** by the producer, concentrated where the producer's
vocabulary has **no matching type**:

| L1 type | miss rate | why |
|---|---:|---|
| FINANCING | 86% (12/14) | producer enum has **no FINANCING** |
| EARNINGS_RESULT | 92% (12/13) | producer has EARNINGS_BEAT/MISS, **no generic EARNINGS_RESULT** |
| M_AND_A | 50% | partly enum mismatch (M_AND_A_ANNOUNCE vs M_AND_A) |
| GUIDANCE/REGULATORY/EARNINGS_BEAT | 0% | producer HAS these exact types |

So the dumping is a **taxonomy gap**, not under-confidence. The signal IS in the producer's input
(`raw_text[:2500]`): FINANCING 5/5 and EARNINGS_RESULT 5/5 of sampled misses had the signature
present — the producer just had no valid tag.

## The A/B (current vs tightened, ground-truthed, N=22 = 14 rescued-L1 + 8 genuine-OTHER_MATERIAL)

Drafts added `FINANCING` + `EARNINGS_RESULT` to the vocabulary with precise criteria (v3), then
added explicit "ignore XBRL/boilerplate metadata, classify only from prose" guidance (v4).

| prompt | RECALL (L1 caught at source) | FALSE L1 (on genuine OTHER_MATERIAL) | precision |
|---|---:|---:|---:|
| **v2 (current/live)** | 0/14 (0%) | 0/8 | — |
| v3 (tightened) | **14/14 (100%)** | **4/8 (50%)** | 78% |
| v4 (anti-noise) | **14/14 (100%)** | **3/8 (37%)** | 82% |

## Verdict — DON'T SHIP

The recall ceiling is reachable (0 → 14/14), but **both tightened prompts introduce false L1 tags
on genuine OTHER_MATERIAL** (37–50%), which the order defines as worse than dumping: a false
`FINANCING`/`EARNINGS_RESULT` spawns the wrong specialist and pollutes fuel, and the rescue layer
**cannot demote** it (rescue only re-tags toward MORE specific types).

**Root cause of the false positives is the INPUT, not the prompt.** `raw_text` is dominated by XBRL
tag soup (`amzn:A3.100NotesDue2030Member`...) and 8-K cover boilerplate, not prose. The 70B
over-assigns the new types from those tokens **despite explicit instructions to ignore metadata**
(v4 only fixed 1 of 4). A prompt tweak can't overcome noisy input.

**Caveat (honest):** the ground truth is itself imperfect — e.g. AMZN's note-tag filing may
genuinely be financing-adjacent that the rescue under-caught, so the *true* false-positive rate may
be nearer 25%. But 25–37% is still too high to ship without per-case adjudication.

## Decision

- **Keep the current producer** (`v2.txt`, enum unchanged) and **rely on the reclassify rescue
  layer** — it is deterministic and SourceLock-precise (re-tags only on a verbatim signature in the
  event's own excerpt), so it achieved the 38 L1 fuel **without** false-promoting these
  XBRL/boilerplate filings. For this task, deterministic signatures beat an LLM prompt on precision.
- The real lever for source-level precision is **cleaner producer input** (feed exhibit/MD&A prose
  instead of XBRL `raw_text`, as the v5 swarm does) — a separate, larger change.

## Artifacts (experiment only — NOT wired into production)

- `v3/extract/prompt_ab.py` — the A/B harness (reproducible).
- `v3/extract/prompts/v3.txt`, `v4.txt` — the rejected draft prompts. The live producer remains
  `v2.txt` (`event_worker.PROMPT_PATH`); `sourcelock.EVENT_TYPES` and `reclassify_live.py` unchanged.
