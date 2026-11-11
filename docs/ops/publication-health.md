# Public website publication health

The weekday pipeline starts at 17:00 on Spark's America/Edmonton clock. Page
build times, data-through dates and editorial review dates are different facts.
A successful render or HTTP 200 does not establish publication freshness.

The November 2026 outage was a replay join error: analytical dates used the
Edmonton session calendar while ledger dates used UTC. After the November
clock transition, the 17:00 snapshots belonged to the following UTC date.
The replay gate refused those inputs before commit/push. The old health check
looked at local page mtimes and a push-failure marker, so it missed the failure.

The current replay format is `lab-replay/3`. Each leaf includes its UTC signal
time, cryptographically bound by the original snapshot identifier. The verifier
checks the UTC ledger date, then derives the analytical date with the pinned
production timezone rules named and hashed in `methodology.date_basis`. The
producer refuses disagreement between the database calendar and those rules.
Ledger contents, original scores and historical analytical dates are unchanged.
Calendar updates require an explicit compatibility review and regression tests.

`replay/lab_replay_bundle_v3.json` and `replay/replay_lab.py` are the current pair.
`replay/lab_replay_bundle.json` remains the last verified November 3 snapshot for
already released 9.1.0 clients. It is a compatibility artifact, not current data.
No package release is implied by this website repair.

`cron/run_public_pipeline.sh` logs every upstream stage and records failures.
Both it and the page renderer require the production main branch and take locks.
The push helper refuses a branch mismatch before pulling or pushing.

`tools/check_public_freshness.py` checks served page build stamps and public JSON
data clocks against the last weekday run, allowing two hours for completion.
The production health monitor runs it every 30 minutes. The existing GitHub
heartbeat workflow also runs it independently of Spark; a failed check fails the
public-site job and records the endpoints in the job summary. GitHub scheduling
and account notification settings govern delivery of Actions notifications.
After deployment, `--against-build docs` requires exact served bytes as well.
Each generated page also displays an overdue warning if the next scheduled
completion is missed (requires JavaScript and the visitor's clock).

On failure, inspect the first failing stage in `/tmp/yuclaw_pipeline.log`, the
refresh/pipeline failure markers, and `internal/status/public_site_health.json`.
Preserve the failure evidence. Fix the cause and run the normal gates; do not
change dates, weaken verification, or replace a historical ledger to clear an
alert. Verify the served artifacts after publishing. A quiet market or unchanged
editorial assessment is not a reason to fabricate new source data.
