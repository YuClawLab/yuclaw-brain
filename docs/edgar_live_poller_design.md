# EDGAR Live Poller Redesign — Design Document

**Status:** DRAFT for review — no code written, no infra touched.
**Author:** Claude (investigation 2026-05-29, late night)
**Decision owner:** YuClawLab (review before any implementation)

---

## 0. Problem statement (why we're here)

The live poller `v3/sources/edgar_poll.py` polls the **global EDGAR firehose**:

```
EDGAR_FEED_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom"
```

`getcurrent` returns only the latest ~40 filings across **all** of SEC. Our
universe is 64 CIKs. The probability that any 40-entry snapshot contains one of
our companies' 8-K/10-K/10-Q is near zero, so `matched_universe: 0` on every
cycle (verified across the full 2.8 MB `/tmp/yuclaw_edgar_poll.log`).

`_extract_cik` is **not** the bug — a live test extracted 40/40 CIKs in correct
10-digit format. The feed choice is the bug.

**Downstream impact:** edgar_poll inserts 0 → `events_raw` gets no new pending
rows → `event_worker` reports `processed: 0` every cycle. The live
EDGAR→extraction path has produced ~zero events since it started. (The 280 rows
currently in `events_raw` came from the one-shot `edgar_backfill.py`, not the
live poller.)

**Good news:** `v3/sources/edgar_backfill.py` already implements the correct
per-company submissions-API fetch path. This redesign is largely "promote the
backfill's proven fetch logic into a continuous poller," not greenfield work.

---

## 1. Approach A — request pattern (per-company submissions API)

### Endpoint
```
https://data.sec.gov/submissions/CIK{cik}.json      # cik = 10-digit zero-padded
```
Returns the filer's recent filing history as **parallel arrays** under
`filings.recent`: `accessionNumber[]`, `form[]`, `filingDate[]`,
`primaryDocument[]`, `primaryDocDescription[]`, `acceptanceDateTime[]`.
(`edgar_backfill._filter_filings` already parses exactly this shape.)

Per-document text fetch (only for filings that pass the form + date + dedup
filters), via `edgar_backfill._archive_url`:
```
https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_no_dashes}/{primaryDocument}
```
Note `cik_int` is the **un-padded** integer CIK in the Archives path.

### Request rate & volume
- **One** submissions request per CIK per poll cycle = **64 requests/cycle** for
  the index sweep, plus 1 document fetch per *new* filing (typically 0–3/cycle
  in steady state).
- SEC published cap: **10 req/sec**. Reuse backfill's `SEC_SLEEP_SECONDS = 0.15`
  (~6.6 req/s) → a full 64-CIK index sweep takes ~10 s wall-clock. Safe margin.
- **Recommended poll interval: 5 minutes** (vs. the current 60 s). EDGAR
  acceptance is not sub-minute real-time and 8-K/10-Q cadence per company is
  days-to-weeks; 5 min is far more than fast enough.
  - 64 req/sweep ÷ 300 s = ~0.21 req/s average — trivial load.
  - Polls/day: `(86400 / 300) × 64 = 18,432` submissions requests/day +
    handful of doc fetches. Well within courtesy limits.
- **Alternative considered:** keep 60 s interval → 92,160 req/day. Works under
  the rate cap but is needlessly chatty for the freshness benefit. **5 min
  recommended; 60 s rejected as wasteful.**

### Rate-limit headers / etiquette to respect
- Honor `Retry-After` on HTTP 429 (back off, don't hammer). Current
  tenacity retry uses exponential backoff but does **not** read `Retry-After` —
  **add explicit 429/`Retry-After` handling** in the new poller.
- Treat HTTP 403 as a User-Agent/identification problem, not a transient error
  (don't blind-retry; log loudly).
- `data.sec.gov` supports `Accept-Encoding: gzip` (backfill already sends it) —
  keep it; submissions JSONs are large.
- Per-CIK ETag / `Last-Modified`: submissions JSON responses are CDN-cached.
  **Optional optimization (Phase 2):** store the per-CIK ETag and send
  `If-None-Match`; a `304 Not Modified` skips parsing entirely and is the
  politest possible poll. Not required for v1.

### User-Agent compliance — ⚠️ ACTION REQUIRED
Current value is a **placeholder**:
```python
USER_AGENT = "YuClawLab v3.0 yuclawlab@example.com"   # example.com — non-compliant
```
SEC requires a **real** contact (sample admin email or company contact) in the
format `Sample Company Name AdminContact@example.com`. `@example.com` risks a
403 block. **Replace with a real monitored address before scaling to 64.**
Recommend moving it to an env var (e.g. `SEC_USER_AGENT`) so it's not
hard-coded.

---

## 2. Dedup strategy

### Current state (and its flaw)
- `events_raw` dedups on a **`source_url` UNIQUE** constraint
  (`events_raw_source_url_key`). There is **no `accession_number` column.**
- The 280 existing rows are URL-shape-inconsistent:
  - **257** are primary-document URLs (`.../{accession}/aapl-20260331.htm`) — from backfill.
  - **23** are `...-index.htm` URLs — from early test runs / the broken poller
    (incl. raw_id 3,4, MSFT, `source_type='edgar'`).
- **The flaw:** the *same filing* can appear under two different URL strings
  (primary-doc vs index.htm), so `source_url` UNIQUE will **not** catch it as a
  duplicate. A filing already ingested as `-index.htm` could be re-ingested by
  the new poller as a primary-doc URL.

### Recommendation: key dedup on `accession_number`
The accession number (e.g. `0000320193-26-000013`) is SEC's **canonical,
URL-shape-independent** filing identifier, and the submissions API hands it to
us directly. Proposed migration (DDL is design spec, not implementation):

```sql
ALTER TABLE events_raw ADD COLUMN accession_number text;

-- Backfill accession from existing source_urls (both shapes embed it):
--   primary-doc: .../data/{cik}/{acc_nodashes}/{primary}
--   index.htm:   .../data/{cik}/{acc_nodashes}/{acc_dashed}-index.htm
-- Parse {acc_nodashes} (18 digits) from the path, re-insert dashes:
--   NNNNNNNNNN-NN-NNNNNN
UPDATE events_raw SET accession_number = <derived> WHERE accession_number IS NULL;

ALTER TABLE events_raw ADD CONSTRAINT events_raw_accession_key UNIQUE (accession_number);
```

The new poller's insert becomes `ON CONFLICT (accession_number) DO NOTHING`.

- **Composite alternative considered:** `UNIQUE (cik, filing_date, form_type)`.
  Rejected — a company can file two 8-Ks the same day; accession is the only
  guaranteed-unique key.
- **Keep `source_url` UNIQUE too?** Yes, leave it as a secondary guard during
  cutover; drop later if desired. Belt-and-suspenders during migration.

### Avoiding re-ingest of the existing 280 rows
1. Migrate `accession_number` onto all 280 existing rows **first** (above).
2. New poller dedups on `accession_number` → all 280 known filings are skipped
   on the very first sweep regardless of URL shape.
3. The 23 index.htm rows are thereby protected from primary-doc-shape
   re-ingest. ✅ This is the concrete reason to add the column before cutover.

---

## 3. Backfill window (first-run behavior of the live poller)

The live poller is **not** the historical backfiller — `edgar_backfill.py`
already did Feb 18 → May 29. The live poller only needs a **lookback window** to
catch filings that landed between "now" and "last successful poll."

### Recommendation: bounded lookback, not full history
- **Per-cycle window:** look back **7 days** of `filingDate` on each sweep, then
  rely on accession dedup to drop everything already seen. 7 days >> 5-min poll
  interval, so even a multi-hour outage is covered without gaps.
- **First run:** because `edgar_backfill` already covers through 2026-05-29, a
  7-day lookback on first live run will re-see only recent filings — all
  deduped by accession. **No special first-run mode needed** if the accession
  migration (§2) is done first.
- **If there IS a gap** (e.g. poller offline for >7 days): run
  `edgar_backfill.py --start <last_good> --end <today> --resume` as a one-shot
  to patch the hole, *then* start the live poller. Keep these two tools
  separate — don't make the live poller do unbounded history.
- **Reject** "pull 1 year / all history on first run": that's the backfiller's
  job, it's already done, and it would dump hundreds of filings into the
  extraction queue at once (see §3 extraction-cost note).

### Does new volume flow through the live extraction chain? — YES, with a caveat
New rows are inserted with `extraction_status='pending'` (table default), and
the **same** `event_worker` loop (already running, respawn wrapper in the
`backfill_signals` tmux session) picks up pending rows and runs the locked
prompt + SourceLock Guard `validate()`. So yes — anything the poller inserts
goes through the identical live extraction path as everything else.

> ⚠️ **Naming caveat to confirm:** you referred to the "v2 prompt + new R7
> chain." On disk, `event_worker.py` loads `v3/extract/prompts/v1.txt`
> ("locked v1 prompt") and there is **no `v2.txt`** and no `R7` reference in
> the worker. Either (a) the v2/R7 work isn't merged yet, or (b) it lives
> somewhere I haven't been pointed at. **Please confirm which extraction chain
> is actually live before we rely on "new filings get the R7 treatment."** The
> poller design is unaffected either way — it just feeds `events_raw`.

> **Extraction-cost note:** the worker uses Ollama at ~120 s/filing (per its own
> comments). In steady state (0–3 new filings/cycle) this is fine. This is the
> real reason to keep the lookback bounded — a wide backfill would create an
> hours-long extraction backlog on the GPU.

---

## 4. Migration safety

### Is an old poller running right now? — YES
- tmux session **`backfill_edgar`** (created Mon May 18), pane PID **1892627**,
  running the respawn loop:
  `while true; do python3 -m v3.sources.edgar_poll --once ...; sleep 60; done`
- It is harmless (inserts 0) but **must be stopped** before/at cutover to avoid
  two pollers writing concurrently.
- (For reference: the `event_worker` loop lives in the **`backfill_signals`**
  tmux session, PID 1966341 — that is the *extraction* worker and should
  **keep running**. Don't kill the wrong session — the names are misleading.)

### Cutover sequence (proposed)
1. **Pre-flight:** run §2 accession migration on `events_raw` (additive,
   reversible).
2. **Dry-run** the new poller on 5 CIKs (§5) — no DB writes.
3. **Stop old poller:** `tmux send-keys -t backfill_edgar C-c` then verify PID
   1892627's child python is gone (or kill the session). Leave `event_worker`
   (`backfill_signals`) untouched.
4. **Start new poller** in its own clearly-named tmux session
   (e.g. `edgar_live_poll`) — do not reuse the misleadingly-named
   `backfill_edgar`.
5. Watch the new poller's log for one full sweep (~10 s) + the extraction
   queue draining.

### What happens to the extraction queue during cutover?
- The queue (`events_raw WHERE extraction_status='pending'`) is currently
  **empty** (all 280 rows are `done`). So there is **nothing in flight to
  lose** — cutover is low-risk by timing.
- `event_worker` is decoupled from the poller via the DB. Stopping/starting the
  poller does not interrupt extraction; the worker simply has nothing to do
  until the new poller inserts pending rows. No coordination needed beyond "add
  accession column first."
- Insert + extraction are independent transactions, so a poller crash
  mid-sweep cannot corrupt in-flight extraction.

---

## 5. Test plan (staged, DB-write-gated)

### Stage 1 — dry-run, 5 CIKs, NO DB writes
Target tickers: **AAPL, NVDA, AMD, MSFT, AMZN**.
- Add a `--dry-run` flag (backfill already has the pattern) that fetches
  submissions, filters to FORM_TYPES + 30-day window, and **prints** the
  candidate filings (ticker, form, filing_date, accession, primary URL) without
  touching `events_raw`.
- **Pass criteria:**
  - All 5 submissions JSONs fetch with HTTP 200 (validates the real
    User-Agent).
  - We see **real 8-K/10-Q/10-K** filings from the past 30 days for at least
    AAPL/NVDA/MSFT (high-frequency filers — if these show zero, something's
    wrong).
  - Extracted accession numbers match the canonical `NNNNNNNNNN-NN-NNNNNN`
    format.
  - Cross-check: at least one printed accession should already exist in
    `events_raw` (proving dedup will catch it once writes are on).

### Stage 2 — dedup validation (still 5 CIKs)
- With the accession column migrated, run the poller in **write** mode on the 5
  CIKs.
- **Pass criteria:** filings already present (by accession) are skipped
  (`skipped_dedup` > 0, `inserted` only for genuinely new ones). Re-run
  immediately → second run inserts **0** (idempotency proof).

### Stage 3 — scale to 64, production writes
- Only after Stages 1–2 pass: expand to the full `_get_universe_tickers()` set,
  enable writes, start the `edgar_live_poll` tmux session at the 5-min interval.
- **Watch for the first hour:**
  - Per-sweep stats show `matched_universe` ≈ filings actually filed (no longer
    a structural 0).
  - `event_worker` begins reporting `processed > 0` as new pending rows appear.
  - No 403/429 in the poller log (User-Agent + rate compliance).
  - `events_raw` accession UNIQUE never throws (dedup holding).

### Rollback
- Stop `edgar_live_poll` tmux session. The accession column is additive and can
  stay. Old poller can be restarted if ever needed (though it does nothing
  useful). No data migration is destructive.

---

## Open questions for reviewer
1. **Confirm the live extraction chain** — v1.txt is what's on disk; where is
   "v2 prompt / R7"? (§3)
2. **Real SEC User-Agent address** to replace `@example.com`. (§1)
3. Poll interval: I recommend **5 min** — acceptable, or do you want tighter?
4. OK to add the `accession_number` column + UNIQUE constraint to `events_raw`?
   (Required for safe dedup — §2.)
5. New tmux session name `edgar_live_poll` (vs. reusing `backfill_edgar`)?

## Appendix — file/infra inventory (as found 2026-05-29)
- `v3/sources/edgar_poll.py` — broken live poller (firehose). To be replaced/rewritten.
- `v3/sources/edgar_backfill.py` — working per-company submissions fetch. **Template for Approach A.**
- `v3/extract/event_worker.py` — extraction worker, loads `prompts/v1.txt`, Ollama, SourceLock `validate()`.
- `events_raw` — 280 rows, all `extraction_status='done'`; dedup on `source_url` UNIQUE; **no accession column.**
- tmux `backfill_edgar` (PID 1892627) — old poller loop, **stop at cutover.**
- tmux `backfill_signals` (PID 1966341) — event_worker loop, **keep running.**
- tmux `yuclaw_api` — API server (pane idle/blank; unrelated to this change).
