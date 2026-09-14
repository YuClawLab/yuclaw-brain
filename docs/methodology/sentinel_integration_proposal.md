# Sentinel — source-based integration proposal (v7; PROPOSAL, no policy change)

**What exists (source: `services/sentinel_nightly.sh`, timer `yuclaw-sentinel.timer` 23:45 America/Edmonton):** a bounded autonomous audit launcher that (1) refuses to start while any Claude session is live (solo-session rule; `SENTINEL_SUPERVISED=1` bypass for operator-present runs only), (2) refuses when its lock is held, (3) refuses when the hash-pinned prompt changed (tamper-evident; exit 1 and alert), (4) runs headless under a 25-minute bound, (5) lets the session commit but never push, (6) after the run hard-resets any commit that touched a forbidden path (registry chain, universe, signal base, tiers, u350, check_ tools, C6/reversal tools, C6 services) with a CRITICAL alert, otherwise pushes, and (7) appends an accountability line to a private log.

**Reconciliation with the recorded refusals:** the private launcher log holds run entries only (four entries, all launcher runs with `pushed: yes`); refusals under rules (1)–(3) exit before the accountability line is written, so they are visible only on the launcher's stdout/journal, not in the log. The solo-session rule therefore silently skips the sentinel on every night an executor session (such as this one) is live — a correct refusal that is currently unrecorded.

**Proposal (unadopted; owner decision D4-SENTINEL if any part is wanted):**
1. Record refusals: write an accountability line for every refusal (`kind: refusal`, `rule`, `date`) before exiting, so `v3/ops/nightly_status` can report "sentinel: REFUSED_SOLO_SESSION" beside the nightly outcome. No rule changes.
2. Model, not policy: `v3/ops/sentinel_lifecycle.py` encodes the current rules (preflight order, supervised bypass, forbidden-path revert, push-after-verify, timeout) as a pure function with synthetic lifecycle tests (`tests/test_sentinel_lifecycle.py`); the status adapter classifies log entries without reading session content.
3. Keep every existing refusal: the solo-session rule, the lock, the prompt pin and the forbidden-path revert are unchanged; supervised bypass remains operator-present only; the launcher still never pushes a commit that touched a forbidden path.
4. Not proposed: terminating sessions, disabling the guard, widening the forbidden list, or inferring a policy from a night without a run.

Activation of (1) needs an owner decision because it edits the launcher; until then this document and the model are the only change.
