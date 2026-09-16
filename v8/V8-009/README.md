# V8-009 — Gate #15 human-comprehension study removed by the owner as a mandatory v8 release requirement (recorded REMOVED_BY_OWNER; never PASSED)

Recorded 2026-09-16. Branch `codex/v8-integration`; change commit **`e84e6730`** (tree `12dd57ec…`) on `c3416a77`; this record is a later record-only commit. Nothing pushed, tagged,
deployed, uploaded or messaged; `release_authorized` stays **false**; human benefit **PENDING**; production untouched. All other v8 work stays paused until after
Friday 2026-09-18 18:00 Asia/Shanghai. No DGX Spark access was used or authorized.

Mission: **Make financial AI accountable to evidence.**  Vision: **Become the Science Trust Layer for Financial AI.**

## The owner's decision, as recorded
`v8/policy/gate15_release_requirement.json` (sha256 `45d23007e958ac96…`): "remove Gate 15's human-comprehension study as a mandatory YUCLAW v8 release requirement. Do not
require a study, route A/B selection, or a separate exception statement." Status **REMOVED_BY_OWNER**, applies to 8.x only. It is not a pass: no study was run and none is claimed; the
gate is never reported as PASSED, GREEN or study complete; the automated consumer-posture scaffold check is retained (RED still blocks); 7.x rules and every historical result stay as recorded.

## What changed, consistently
- **Release generator** (`tools/yuclaw_release_state_v6.py`): for a v8 release with the record present, gate 15 = REMOVED_BY_OWNER when the retained check passes, RED when it fails; without
  the record or for 7.x the old MANUAL_REVIEW/RED rule is unchanged; a record claiming any other status is refused; the vocabulary, the manifest (`gate15_requirement`), the remaining-blockers
  list and the public/internal wording follow the decision.
- **Note composer** (`tools/yuclaw_release_notes_v8.py`): the Gate #15 disclosure states the removed requirement bound to the record's sha256 and "not a pass"; the activation line for the
  human study says the same; correspondence accepts Gate #15 = NOT_REQUIRED only (routes A/B and exception statements are not applicable to v8) and rejects notes that call the gate passed.
- **Publisher** (private `publish_v800.py`, identity now `a71782d8cd2d828c…`): the policy stage is `policy <allocation file>`; it records D1 with Gate #15 NOT_REQUIRED bound to the record;
  route arguments are refused; `policy_valid` accepts only a manifest reporting REMOVED_BY_OWNER with a NOT_REQUIRED policy bound to the unchanged record (RED blocks; a stale MANUAL_REVIEW
  manifest must be regenerated; GREEN is never accepted). Allocation, artifact-integrity, one-final-set, tripwire and authorization rules are untouched.
- **Decision documents**: D1 revision 3 (the policy stage now records D1 alone); superseding banners on the V8-008 D2 package and designation proposal; historical text retained.

## Focused checks (`checks.json`)
Repo suites: gate-15 rule tests 3, composer tests 10, 7.x composer regression 5, study-tooling tests 4 — all passed. Publisher suites (private): 15 + 7 passed. pyflakes and Python 3.10
compilation clean. One real generator run on a **check-only** staging (`8081536206ff` = `e84e6730` + the unchanged version patch; not a proposed candidate):
gates **{'GREEN': 18, 'RED': 1, 'REMOVED_BY_OWNER': 1}**; gate 15 **REMOVED_BY_OWNER** with the record's sha256 in its evidence; `remaining_blockers` = ['gate #14 language rails pass — RED'] (gate 14 is the stale committed weekly note, unrelated:
freeze-day render pending); `policy_correspondence` = ['no release-policy record'] (D1 pending); the public notes never describe the gate as passed. Not run: browser journeys, the full
application suite, the rehearsal (fixture updated), any new candidate staging.

## What still blocks a release (unchanged by this decision)
D1 acceptance recorded through the policy stage; designation and the freeze-day render (gate 14); the final artifact set from the authorized commit; the owner's authorization sentence.
A re-staged candidate proposal on this HEAD is prepared only after the pause.

Private record: `internal/v8/v8_009_…/` (check-only staging worktree, bump log, generator evidence/log/manifest/notes, review diff). Research and education only. Not investment advice.
