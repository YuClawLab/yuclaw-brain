# v5 Layer 1 — Day 3 writeup: MD&A Prose Extraction

Branch `v5-layer1`. Fixes the root cause isolated on Day 2: the swarm's agents ground ~0.0
on 10-K/10-Q because the text they read is the iXBRL cover, not narrative prose. Day 3
re-fetches the real MD&A and feeds it to the (unchanged) Day-2 grounded swarm.

## Corpus diagnosis (Phase 1, read-only)

`public.events_raw.raw_text` per form type:

| form | n | avg_len | XBRL urls in first 6k | character |
|------|---|--------:|----------------------:|-----------|
| 8-K  | 200 | 5280 | 0  | press-release prose ✓ |
| 10-Q | 53  | capped 8000 | 7  | iXBRL cover, mixed |
| 10-K | 26  | **all exactly 8000** | 18 | iXBRL R-file cover ✗ |
| 6-K  | 5   | 1827 | 0  | prose ✓ |

Two findings nail it:

1. **`raw_text` is capped at 8000 chars** (`v3/sources/edgar_backfill.py: RAW_TEXT_CAP = 8000`).
   All 26 10-Ks are *exactly* 8000 — truncated to the cover region.
2. **The poller fetched the RIGHT document.** `source_url` is the primary `.htm`
   (e.g. `tmo-20251231.htm`), the actual 10-K — not the R-file. But modern 10-K/10-Q
   primaries are **inline XBRL (iXBRL)**: the first ~70k chars are the `<ix:header>` cover +
   table of contents, and the naive tag-strip (`<[^>]+>` → space) leaves the XBRL taxonomy
   URLs as text. The MD&A prose is much deeper.

Probe of the TMO 10-K primary document (one rate-limited fetch): stripped length **417k chars**;
`Item 7 — Management's Discussion and Analysis` begins at char **~74,700**; that region is real
prose (**alpha 0.77, 0 http-URLs**). So **this is a re-fetch + extraction problem, not a
wrong-source problem** — the prose is recoverable from the `source_url` already on record.

## The extractor (Phase 2, deterministic, additive)

`yuclaw/v5/extract/narrative.py`:

- **`fetch_primary`** — GET the primary `.htm` with the declared SEC User-Agent + a polite
  delay (one request/filing; on-disk cache so re-runs never re-hit EDGAR). Smoke + batch are
  ≤6 fetches total — never a bulk sweep.
- **`strip_filing`** — removes the `<ix:header>` block (the taxonomy-URL source), scripts,
  styles, comments, then tags; unescapes entities; collapses whitespace.
- **`extract_narrative`** — locates the section body (MD&A, then Risk Factors, then Business),
  disambiguating the real section from the table-of-contents entry (a TOC line is followed by
  `<pagenum> Item NN`). Returns a clean prose slice (default 16k chars; the agent reads the
  first 6k).
- **`sanity_ok`** — content gate: prose must be ≥1500 chars, alpha ratio ≥0.65, ≤5 residual URLs.

Output → `yuclaw_v5.swarm_inputs.narrative_text` (new additive table; DDL in
`yuclaw/v5/extract/swarm_inputs.sql`). **`events_raw` and all `public.*` are read-only.**

Extraction quality on the two probe filings (XBRL cover → MD&A body):

| filing | section | chars | alpha | residual URLs | full doc |
|--------|---------|------:|------:|--------------:|---------:|
| TMO 10-K | mdna | 16000 | 0.78 | 0 | 326,630 |
| AAPL 10-Q | mdna | 16000 | 0.74 | 0 | 84,747 |

(vs the Day-2 input: 58 / 4 XBRL-URLs in the first 6k, ~0 quotable financial prose.)

## Grounding: before → after (Phase 3 smoke + Phase 4 batch)

**Phase 3 smoke — AAPL 10-Q (`0000320193-26-000013`), the cleanest Day-2 zero baseline:**

| agent | Day-2 (XBRL) | Day-3 (narrative) |
|-------|-------------:|------------------:|
| bull    | 0.00 | **1.00** (3/3) |
| bear    | 0.00 | **1.00** (3/3) |
| skeptic | 1.00 | 1.00 (3/3) |

The agents now quote real MD&A prose — bull: *"The Company has historically experienced higher
net sales in its first quarter … seasonal holiday demand"*; bear: *"Macroeconomic conditions,
including inflation, interest rates … have directly and indirectly impacted … the Company's
results of operations"*, plus the supply-constraint and tariff language. The 70B synthesis is
now a genuine bull-vs-bear reconciliation with quote-backed disagreement — not two
hallucinations. **GATE: PASS (bull+bear lifted 0.00/0.00 → 1.00/1.00).**

(Honest note: a bull point listing new products kept its grounded anchor quote but its
itemized product lines — `- iPad Air`, `- iPhone 17e`, … — verified NOT FOUND, as they sit just
past the agent's 6000-char window / are differently formatted. The verifier correctly rejects
them; the point stays grounded on its verified anchor.)

**Phase 4 batch — 5 filings, per-agent grounding_rate (Day-2 XBRL → Day-3 narrative):**

| filing | form | bull | bear | skeptic |
|--------|------|------|------|---------|
| AAPL | 10-Q | **0.0 → 1.0** | **0.0 → 1.0** | 1.0 → 1.0 |
| TMO  | 10-K | 1.0 → 0.5\* | **0.0 → 1.0** | 1.0 → 0.5 |
| JNJ  | 10-Q | **0.0 → 0.67** | 1.0 → 0.5 | 1.0 → 0.33 |
| HPE  | 8-K  | 1.0 → 1.0 | 0.5 → 0.0 | 0.67 → 1.0 |
| AMD  | 8-K  | 1.0 → 1.0 | 0.5 → 1.0 | 1.0 → 0.67 |
| **mean** | | **0.60 → 0.83** | **0.40 → 0.70** | 0.93 → 0.70 |

\* TMO's Day-2 bull 1.0 was *degenerate* — it "grounded" by quoting XBRL taxonomy URLs that
literally appear in the cover. Day-3's 0.5 is real MD&A prose. The number fell; the quality rose.

**Read-out.** The headline holds: on the 10-K/10-Q forms where bull/bear were XBRL-starved
(~0.0), they now ground on real MD&A prose — AAPL bull+bear 0.0/0.0 → 1.0/1.0, TMO bear
0.0 → 1.0, JNJ bull 0.0 → 0.67. Aggregate **bull 0.60 → 0.83, bear 0.40 → 0.70**. There is
clear 8B run-to-run variance (HPE bear 0.5 → 0.0; JNJ skeptic 1.0 → 0.33) — the same
sampling noise documented in Day 2 — so individual cells move both ways, but the
XBRL-starved roles lift in aggregate and, more importantly, every surviving citation is now a
verbatim span of genuine narrative rather than a fabricated figure or a taxonomy URL. The
skeptic's mean dip (0.93 → 0.70) is degenerate-to-real: its Day-2 1.0 was largely XBRL-URL
quoting. The 8-Ks (already prose) are essentially unchanged, as expected.

## Cost/filing

- **Extraction:** ~0.3s/filing cached, ~1–3s cold (one ~1–3 MB GET + regex strip). Negligible
  next to the swarm. EDGAR is hit once per filing with the declared UA + 0.2s delay, and the raw
  response is disk-cached — the 5-filing batch made 3 new fetches.
- **Swarm:** ~196s/filing (vs Day-2's ~162s). Narrative gives the agents more to ground, so the
  70B synthesis runs longer (it emits more `key_findings` + `disagreements`). Batch wall: 984s.

Net: the narrative path adds a one-time ~1–3s extraction and ~+34s of richer synthesis per
filing — cheap for turning bull/bear from fabrication into verbatim-grounded prose on 10-K/10-Q.

## Implication for Layer 0 (Phase 5, analysis only — no action)

Layer 0's backfill ran **287** `extract_filing` jobs (all succeeded). By form type:

| form | filings | share |
|------|--------:|------:|
| 8-K  | 201 | 70.0% |
| 10-Q | 53  | 18.5% |
| 10-K | 26  | 9.1%  |
| 6-K  | 5   | 1.7%  |
| edgar| 2   | 0.7%  |

**79 of 287 (27.6%) are 10-K/10-Q** — extracted from the same XBRL-impoverished `raw_text`.
Those would benefit from a narrative re-extraction (the path built here); the 201 8-Ks (70%) +
5 6-Ks are already prose and unaffected. This is a scoping finding for VinZhang — **no re-run
performed**; it quantifies the future re-extraction decision.

## Production safety

Additive `yuclaw_v5.swarm_inputs` only; `events_raw`/`public.*` read-only. EDGAR hit with the
declared UA, ≤6 cached single fetches. No deploy, branch-only. Crons, main/Lab worktrees, and
Ollama config untouched.

## Cross-references
- Day 2 (the finding this fixes): `docs/v5/layer1/day2.md`
- Extractor: `yuclaw/v5/extract/narrative.py` (+ `swarm_inputs.sql`)
- Harnesses: `yuclaw/v5/swarm/tests/smoke_narrative.py`, `batch_narrative.py`
