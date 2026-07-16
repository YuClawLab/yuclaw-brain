# event_id Local-Day vs UTC-Day Mismatch — standing quirk

**Standing behavior: the event worker's per-row `event_id` duplicate guard
(commit `c622458a`) plus the `DUPLICATE_EVENT_ID` audit row in
`rejected_events` are the permanent mitigation for this quirk. Unifying the
day derivation is deferred to the L2 identity layer (decision 2026-07-15);
do not "fix" the derivation in the v3 worker.**

## The quirk

`v3/extract/event_worker.py` builds an event's identity two different ways:

- `event_id` = `TICKER_YYYYMMDD_hash12`, where `YYYYMMDD` is the **local**
  day of `source_publish_time` (whatever timezone the timestamp carries —
  in practice America/Denver from the poller/backfill).
- The `events` dedup index is `(content_hash, ticker, UTC day of
  available_as_of)` — a **UTC** day.

Two filings with identical extracted content (same `content_hash`) that
straddle UTC midnight therefore land on *different* UTC days — so the
`ON CONFLICT ... DO NOTHING` clause does not fire — while their *local*
days are identical, so they collide on the `events_pkey` primary key.

## Why it matters (2026-07-15 incident)

During the Canada Phase-2 backfill drain, an IAG 6-K pair (2026-02-17,
filed 32 minutes apart, both falling back to near-identical raw-cover text,
temperature 0 → identical extraction) hit exactly this window. The pkey
violation aborted the whole batch transaction; because the worker always
selects the 8 **oldest** pending rows, the same poison batch was re-picked
on every run. The 15-min timer worker crash-looped 37 times and the
session-bound drain loop died, stalling the drain for ~9.5 hours.

## Standing mitigation

Before the accept-path INSERT, the worker checks whether the computed
`event_id` already exists (visible within the same transaction too, which
is what the IAG pair needed). A hit is treated as the duplicate it is:

1. audit row in `rejected_events` with reason `DUPLICATE_EVENT_ID: <eid>`
   and the full LLM output;
2. the `events_raw` row is marked `done`;
3. the batch proceeds — one bad row can no longer poison the queue head.

Related hardening from the same incident: backfill drains run as detached
transient units via `services/canada_drain_loop.sh` (never session-bound),
with a 10-consecutive-failure circuit breaker.

## Deferred decision

Deriving `event_id` from the UTC day would remove the mismatch but changes
event identity for future rows (and any replay/join keyed on `event_id`).
That unification belongs to the L2 identity layer and is deferred there.
Until then: guard + audit row is the contract. If `DUPLICATE_EVENT_ID`
rejections appear for rows that are *not* same-content near-midnight pairs,
that is a new bug, not this quirk.
