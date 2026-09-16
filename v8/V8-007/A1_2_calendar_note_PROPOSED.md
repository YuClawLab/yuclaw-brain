# Proposed addendum note A1.2 — first-read calendar identity (OPTIONAL; NOT applied; owner decision)

Origin: `v8/V8-006/gate6_correction.json` (`protocol_question.proposed_text_for_review`). Nothing in the registry, the guard or the historical manifest is changed by this file. Research and education only. Not investment advice.

## Proposed text (verbatim, for the owner to record, edit or reject)
> The first read's calendar identity remains the registered 2026-08-28C table (sha256 c51d05fa334899d6…). A NO-WRITE replay of the first read is performed against that pinned calendar taken from repository history (commit e988084b); the current calendar (extended to 2028 on 2026-09-14) is a later registration for later sessions and does not re-pin the first read. Replays that use any other calendar remain refused.

## Governing rules
- Addenda are registered as lines in `registry/protocols.jsonl` (the chained protocol registry); a line is appended, never edited; the chain tip changes; the gate suite re-verifies the chain (gates 2, 8, 10). Recording it is an owner act on the production registry, outside this order.
- The guard in `tools/yuclaw_layered_dependency.py --replay` keeps refusing any calendar whose hash differs from the manifest-pinned `c51d05fa…`; the note documents the relationship, it does not relax the guard and does not re-hash anything.
- Gate 6 is already GREEN from the pinned-calendar replay (three fresh NO-WRITE runs, exit 0, output `0b2ac8a5…`, V8-006). The note is needed only if a future replay must be explained from the CURRENT tree without checking out the historical calendar.

## What recording it permits / does not permit
- Permits: a registered statement that the first read's replay input is the historical calendar at `e988084b`, so later readers do not mistake the 2028 extension for a re-pin.
- Does not permit: replays with the current calendar (still refused); any change to the first-read manifest; any claim about 2028 sessions (those belong to the separate release queue with the calendar/2028 findings).

## Next action after the decision
- Record → owner appends the line to the registry in the production checkout; the chain tip advances; the next generator run reflects it (tripwire and gate suite unchanged).
- Do not record → nothing changes; gate 6 stays GREEN on the pinned replay; the finding stays in the release queue.
