# EDGAR Live Poller v2 — Runbook

**Module:** `v3/sources/edgar_poll_v2.py` · **Deployed:** 2026-05-30 · **Branch:** v3.0-evidence
**Replaces:** `v3/sources/edgar_poll.py` (the broken `getcurrent` firehose poller — see
`docs/edgar_live_poller_design.md` for the why).

## What it does
Sweeps each universe ticker's own SEC submissions index
(`https://data.sec.gov/submissions/CIK{cik}.json`), filters to recent
`8-K/10-Q/10-K/6-K` filings, dedups on the canonical **accession number**, and
inserts new filings into `events_raw` with `extraction_status='pending'`. The
live (GPU-backed) `event_worker` then extracts them automatically.

This fixed the structural `matched_universe: 0` bug: the old poller polled the
global firehose (latest ~40 filings across all of SEC) and almost never saw our
64 CIKs. The new poller queries our companies directly.

## Configuration (in the module)
| Setting | Value | Notes |
|---|---|---|
| Interval | 300 s (5 min) | respawn-loop `sleep`; `--interval` to override |
| Lookback | 7 days | `--lookback`; accession dedup covers overlap/outages |
| Rate | 0.15 s/request | ~6.6 req/s, under SEC's 10/s cap |
| User-Agent | `YuClawLab vzhang2088@gmail.com` | env `SEC_USER_AGENT` overrides; **must be a real contact** |
| Form types | 8-K, 10-Q, 10-K, 6-K | Form 4 handled separately |
| Dedup key | `events_raw.accession_number` UNIQUE | checked before doc-fetch + `ON CONFLICT DO NOTHING` |

## How it runs
tmux session **`edgar_poll_v2`** on the shared tmux server, running a respawn loop:
```bash
cd ~/yuclaw-v3 && while true; do
  python3 -m v3.sources.edgar_poll_v2 --once >> /tmp/edgar_poll_v2.log 2>&1
  EXIT=$?; [ $EXIT -ne 0 ] && echo "$(date) edgar_poll_v2 exit=$EXIT — respawn in 300s" >> /tmp/edgar_poll_v2.log
  sleep 300
done
```
**Log:** `/tmp/edgar_poll_v2.log`

## Verify it's running / healthy
```bash
tmux has-session -t edgar_poll_v2 && echo ALIVE              # session up
pgrep -af "edgar_poll_v2 --once"                             # process (idle between sweeps is normal)
grep "sweep:" /tmp/edgar_poll_v2.log | tail -3               # recent sweep stats
grep -iE "403|429|error|exit=" /tmp/edgar_poll_v2.log        # should be empty
```
A healthy sweep line looks like:
```
[edgar_poll_v2] sweep: {'tickers': 79, 'window': '...', 'candidates': N,
    'inserted': M, 'skipped_dedup': K, 'doc_fetch_stub': 0, 'ticker_errors': 0, 'latency_s': ~35}
```
- `ticker_errors: 0` and no `403`/`429` → User-Agent + rate compliance OK.
- `skipped_dedup` >> `inserted` in steady state (most recent filings already seen).
- `inserted: N` → N new `pending` rows; `event_worker` (tmux `backfill_signals`) drains them.

## Stop / restart
```bash
# Stop
tmux kill-session -t edgar_poll_v2

# Restart (from ~/yuclaw-v3)
RESPAWN='cd ~/yuclaw-v3 && while true; do python3 -m v3.sources.edgar_poll_v2 --once >> /tmp/edgar_poll_v2.log 2>&1; EXIT=$?; [ $EXIT -ne 0 ] && echo "$(date) exit=$EXIT" >> /tmp/edgar_poll_v2.log; sleep 300; done'
tmux new-session -d -s edgar_poll_v2 "$RESPAWN"
```
Dry-run (no DB writes) for validation:
```bash
python3 -m v3.sources.edgar_poll_v2 --dry-run --tickers AAPL,NVDA,AMD,MSFT,AMZN --lookback 30
```

## What success looks like end-to-end
1. Poller sweep inserts a `pending` row in `events_raw` for a new filing.
2. `event_worker` (GPU, ~25–30 s/filing) picks it up → `events` (accepted) or `rejected_events`.
3. `extraction_status` on the raw row flips `pending → done`.

Verified at cutover: MRK 8-K `0001104659-26-067509` inserted → worker accepted it
(`OTHER_MATERIAL`, `prompt_version=v2`) within seconds.

## Known nuances
- **79 tickers / 64 CIKs:** the universe has 79 tickers but ETF trusts share CIKs
  (e.g. Select Sector SPDRs), so ~64 unique submissions endpoints. Per-ticker
  iteration matches the backfill; accession dedup collapses shared-CIK filings to
  one row (attributed to the alphabetically-first ticker). Minor extra fetches.
- **Gaps > 7 days:** if the poller is down longer than the lookback, patch the
  hole with `edgar_backfill.py --start <last_good> --end <today> --resume`, then
  restart the poller. Don't widen the live lookback unboundedly.
- **Dedup column:** `accession_number` UNIQUE (added 2026-05-30, migration
  `v3/migrations/2026-05-30_add_accession_number.sql`). `source_url` UNIQUE
  retained as a secondary guard.
