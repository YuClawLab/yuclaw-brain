# V8-015 — hosted CI on the expanded candidate, 43-family reconciliation, connected module workflow (handoff)

Research and education only. Not investment advice. **One push was made in this order: the exact approved commit
`68daca6d…` to `codex/v8-integration`. Nothing else was pushed, tagged, uploaded, deployed, dispatched or announced.
`release_authorized=false`. D1 is PROPOSED. Gate 15 is REMOVED_BY_OWNER / NOT_REQUIRED (never PASSED). Human benefit is
PENDING. V8-013 stays paused. The revised commit has NO hosted CI: `REMOTE_CI_NOT_RUN` for it.**

Order file `CLAUDE_CODE_ORDER_V8_015.md`, sha256 `8d8ca93e200da5056be95751cd797dc6ba7a5985a2f33846ad581145a26a4122` — verified.

## 1. The approved push and its hosted run

`git push origin 68daca6daa6266591dc4c3e44b63e36b993f0615:refs/heads/codex/v8-integration` — executed 2026-09-20T06:47:37Z
after the pre-checks (clean worktree, expected remote, fast-forward from `a4fa151f…`, validation-only workflow) and the
owner's interactive confirmation, with the existing `gh` login through a one-command credential-helper override. No stored
credential or configuration changed; no token was printed. `origin/main` untouched.

Run **35495154439** — <https://github.com/YuClawLab/yuclaw-brain/actions/runs/35495154439> — `v8-prerelease-validation`,
push event, head `68daca6daa6266591dc4c3e44b63e36b993f0615` (tree `2c78f20e…`, printed by every job), **success**, 06:47:41Z → 06:51:54Z.

| Job | Result | What actually ran |
|---|---|---|
| tests (3.12, x86-64) | success | 334 passed, **1 skipped** = `test_packaged_modules_compile_on_minimum_python` (no python3.10 in that job; established from its position in the log). The five disposable-PostgreSQL-16 tests **ran and passed**; compliance regression 21 passed against the PostgreSQL 16.15 service. All 49 module tests ran with the real worker. |
| python-floor (3.10.21) | success | 151 passed — the same v8 test files on another interpreter, **not** additional coverage |
| package | success | clean-install PASS: wheel and sdist fresh installs, fixtures journey 7/7 and module journey 6/6 each, backend `landlock`; twine 7.0.0 rc 0; artifact digests equal to the local V8-014 pair. The real-source journey does not run hosted (private sources). |

x86-64 isolation: kernel 6.17.0-1022-azure, Landlock in the LSM list; the **landlock** backend passed every probe denial
(canary secret, home, /etc/passwd, writes, TCP, UDP, unix socket, fork, signal to parent, 2 GiB allocation, empty
environment, no inherited descriptor, wall-clock and output bounds) and valid bundles were admitted. **bubblewrap is not
installed there and is verified on no host.** No skip, no weakened control, no host change. → `hosted_ci.json`,
`isolation_support_matrix.json`

## 2. Acceptance: 43 families, 46 rows

`acceptance_matrix.json` (full) and `acceptance_matrix.md` (readable): requirement text verbatim; per family the entry
points, exact tests and journey assertions, authorized and rejected cases, untested subclauses, and software status kept
apart from hosted CI and external evidence. Every module test is cited by at least one family.

Software gaps found by reading the implementation against the families, and fixed: SHD lists and decision pages were not
object-scoped for a submit-only principal; the export preview was not reachable from the browser; reflections and feedback
were not shown as one ordered discussion; a reevaluation request never showed its fulfilment; dispute targets, declared
lineage, EVO version references, test-access principals and discrepancy resolutions were accepted without checking that the
object exists here; a claim amended after a form was shown was accepted silently; a practitioner holding another
capability was not labelled as unconfined; the only skip decorator in the module tests is gone; five documentation clauses
(source owners, approved false statement, authority roles, no alias resolution, packets are not anonymous) were missing.

New tests (15 since V8-014): cross-server sessions and object scope; crash between private write and event; a killed
process holding the lock; copied approval in another workspace with the root trusted there; six hostile archives through
the integrated route; a member lying about its size; input changed during the read; bounded error channel; exposure after
principal revocation and relabelling; test access only for local principals; concurrent admission at the cap; claim
amendment and EVO successor annotate a session; confinement label, storage bound, runtime change; preview writes nothing;
the connected workflow with forged, stale and foreign references.

`backlog_reconciliation.json`: five rows NOT COMPLETE for lack of external evidence (COM-12, PRC-01, PRC-09, SHD-12,
EVO-10); three PARTIAL (EVO-03; and, new on re-reading every clause, PRC-07 and EVO-12); stated limits added for COM-04,
PRC-08, EVO-05; SHD-01 closed by documentation. None is a release gate.

## 3. Identifier entry, same journey and data (`identifier_entry_before_after.json`)

| | typed | redundant | external | new | deliberate selections |
|---|---|---|---|---|---|
| before (`68daca6d`) | 29 | 16 | 3 | 10 | 14 |
| after (final code) | 14 | 1 | 3 | 10 | 24 |

The V8-014 figure of 11 was a hand estimate and was wrong; the instrumented count is above. The one remaining entry is a
digest typed in the journey's **refused** self-approval case, where no approval action is offered by design; in authorized
workflows the count is 0. Observed mistakes are listed in the file. This is workflow behaviour, not measured human benefit.

What a user can now do without retyping: from a **claim page** open COM or Practice with that claim and its version
selected; on **SHD → trust** approve a waiting submission from its own row (still entering the evidence digests they expect,
purpose and expiry); from an **admitted decision** take its packets into COM or import its evaluations into EVO; on an **EVO
version page** register a child, link a commitment from a list, resolve a failure with a listed PASS evaluation; in **COM**
choose lineage and dispute targets from the group's own objects; on a **practice session** build that session's packet;
**Preview** an export. Every decision is still a button; every carried reference is checked again on the server.

## 4. Identity and verification

| | |
|---|---|
| Branch | `codex/v8-integration` — origin at `68daca6d…`; everything after it is **local only** |
| Candidate SOURCE commit / tree | `f6a879b21137f60d9e85b5cc675e6f11125e613a` / `5543108042e16400017e29145b810c3f38f7cb40` |
| Record HEAD | see `git rev-parse HEAD` — on top of the source: one test-file commit (`6e7b91d6`, a skip decorator removed) and evidence-only records; no packaged path differs |
| Wheel | `yuclaw-8.0.0-py3-none-any.whl` sha256 `d1f5c59f030d42600241b6dbebb257a66054d2bb8be29b43ae4ff82536adb0f4`, 1,004,415 B |
| Sdist | `yuclaw-8.0.0.tar.gz` sha256 `8d4b78f146ededb20987f3da8d06f0ba4c9001737b22a43c51e7fa6ba0639acf`, 5,259,183 B |
| Built | 2026-09-20T07:36:07+00:00, SOURCE_DATE_EPOCH 1580601600, python 3.12.3, build build 1.4.2, wheel_generator hatchling 1.32.3 — a CANDIDATE pair, not a final set |
| Superseded | V8-015 build from `e1cc206e…` (passed; later packaged changes); two stopped builds; the V8-014 pair. Kept privately, never relabelled |

- Fresh installs of the **wheel** and the **sdist** outside the checkout: original fixtures journey 7/7 / 7/7, real-source
  regression journey 7/7 / 7/7 (source-time correction included), **module journey 6/6 / 6/6** (42 assertions, 15
  negative) on the `landlock` worker; twine check rc 0; every module file present; no credential store, key, vault,
  journal or order record in either distribution. → `packaging.json`
- Full suite **371 passed**; Python 3.10.21 floor **166 passed**; no skips on the executor. Old exports: a V8-011 wheel's export
  verifies under the new code and the new export verifies under the old code (private run `x04_compat`).
- Gates at the record HEAD: {"GREEN": 19, "REMOVED_BY_OWNER": 1} → `gates.json` (correspondence `['no release-policy record']` while D1 is PROPOSED).
- Help and notes: operator guide §7 (connected pages, clauses above), the notes composer's integration line, CHANGELOG.
- D1: `D1_allocation_8.0.0_PROPOSED.json` = `V8-ALLOC-2026-09-20-P7`, PROPOSED; P6 … P3 preserved unchanged.

## 5. Remaining defects and limits

- **The revised commit has no hosted CI.** Run 35495154439 covers `68daca6d…` only. → `ci_push_plan.json` (PROPOSED, not executed)
- Local vs hosted: same landlock denials on aarch64 and x86-64; bubblewrap verified nowhere; the real-source journey runs
  only on the executor; macOS and Windows untested (SHD admission refuses there; other pages untested).
- Untested subclauses, per family, are in the matrix: no power-cut test; no scheduler-timed race by a second process; the
  parent's multipart splitter is not fuzzed; no isolation sensitivity variant; rollback detection needs an earlier verified
  packet; one hostile-text family; two built-in EVO jobs; the CLI performs host-operator administration only.
- External evidence that does not exist and is not claimed: human effort comparison, qualified reviewer, learning-transfer
  study, independent security review, an organization-wide inventory to check against, deployment controller.
- The stored git token lacks the `workflow` scope (the publisher's plain `git push` would stop at the freeze).

## Manual walkthrough (observations blank until the owner performs them)

From your home directory on the executor (inside a checkout Python would load the checkout, not the wheel):

    cd ~ && W=~/yuclaw/internal/v8/v8_015_20260920T064750Z/clean_install/venv-wheel
    $W/bin/python -m v8.workbench principals init --workspace ~/yuclaw-workspaces/v8-015-modules        # prints the owner credential once
    $W/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/v8-015-modules --port 8765     # terminal 1
    $W/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/v8-015-fresh   --port 8766     # terminal 2 (no `principals init` here)

The servers bind the executor's loopback only; from the Mac use your usual tunnel for both ports, then open
`http://127.0.0.1:8765/login`.

| Step | Observation |
|---|---|
| Sign in as owner; Setup: enroll `alice` (submit), `rita` (review), `pat` (practice) | |
| Load fixture `001_base`; on the claim page use *submit a review packet about it* — the claim and its version are already selected | |
| As alice submit a small bundle; as owner approve it from its own row on SHD → trust; request the decision → ADMITTED; four separate answers clear | |
| On the decision page use *take the packets into the COM queue* (or *import the declared evaluations*) | |
| COM group page: record a dispute by choosing the target from the list; appeal; resolve | |
| From the claim page use *create a practice task on it*; the claim's sources are pre-ticked | |
| As pat: open a session, confirm no comparison is reachable, commit, open it, reflect; the session shows its route confinement; build the session's packet from the session page | |
| `/modx`: Preview (nothing written), then build; verify at `http://127.0.0.1:8766/modx` → SUCCESS, signer UNKNOWN_SIGNER | |
| Anything confusing, missing or wrong | |

## Readiness (realistic)

Not ready to freeze today; ready for owner review. Still required, in order: the walkthrough; your decision on the
follow-up branch push and a green hosted run **on that exact sha**; D1 on the frozen identity; re-integration if
`origin/main` moved (it moves Mon–Fri 23:00 UTC) → new source commit → NEW pair; the freeze procedure
(`v8/V8-012/freeze_procedure.md`). No release date is committed.
