# V8-012 — release notes completed, pre-release CI prepared locally, one freeze procedure (handoff)

Research and education only. Not investment advice. **Nothing was pushed, tagged, uploaded, deployed, dispatched or
announced. `release_authorized=false`. D1 is PROPOSED. Gate 15 is REMOVED_BY_OWNER / NOT_REQUIRED (never PASSED).
Human benefit is PENDING. Remote CI is NOT_RUN; INT-11 stays incomplete.**

## Identity

| | |
|---|---|
| Branch | `codex/v8-integration` (local only; origin has no such branch) |
| Source commit / tree of this order | `51d039d535215a12d7244df20531abccdb819e67` / `aadc9a9424d9575e62ff74d6c47f4d1311454de6` |
| Commits on the V8-011 record HEAD `c38cdb84…` | `046f81f6…` notes composer + tests · `51d039d5…` CI workflow + constraints · then this record (evidence only) |
| Packaged content | unchanged since candidate source `9d1de81ef91d033f9d828e7e4b40753a1f39acd7`: 0 paths inside the wheel or sdist differ |
| Candidate pair | unchanged, under its original identity only: wheel `7c2dd63d5094…afdc94`, sdist `9c4fc99ff734…ac6d1e`, built from `9d1de81e`. No new candidate build; the final pair is bound at the freeze |
| Upstream | `origin/main` `5edb9e7e8502a11727b6174b8cc62f47107a6a91`, observed once 2026-09-20T02:30:59Z — an ancestor of the branch |

## What changed

1. **Public release description** (`release_notes_additions.json`). Two sentences appended to the composer's fixed
   accounts, so the generated body states them and the correspondence check binds them:
   - *A wrong source-availability time is corrected by a linked, append-only event, never by editing: the original
     records and earlier historical views stay intact, the corrected result is shown separately beside the recorded
     one, and the correction chain is exported for a fresh workspace to recompute. Availability times are asserted by
     the operator, not authenticated.*
   - *A new live request to the SEC requires the operator's own `SEC_USER_AGENT` setting — required, never defaulted: a
     missing or unusable value is refused before any request is sent; stored-source replay and every other offline
     function work without it.*

   Generated with the real generator at `51d039d5`: 19 GREEN / 0 RED / 1 REMOVED_BY_OWNER; exactly two lines differ from
   the V8-011 notes; the draft still says `Release policy: NOT RECORDED` and the correspondence is
   `['no release-policy record']`. The v7 composer, the Gate 15 disclosure and the publisher (identity unchanged) are untouched.
2. **Pre-release CI** (`ci_workflow.json`): `.github/workflows/v8-validation.yml`, validation only, three jobs, read-only
   token, no secrets. Syntax-checked and every job's commands rehearsed locally in a shallow clone. **Hosted: NOT_RUN.**
3. **Freeze procedure** (`freeze_procedure.md`): one frozen commit `F` for push, CI, pair, manifest and authorization;
   nothing is committed after `F`; recommended window Monday 2026-09-21 08:30–17:00 Asia/Shanghai; no refresh pause needed.
4. **Allocation** `D1_allocation_8.0.0_PROPOSED.json` = `V8-ALLOC-2026-09-20-P5`, an amendment of P4 (scope, capabilities
   and activations unchanged; references, evidence, limitations and obligations updated). PROPOSED. P4 and P3 are preserved.
5. **Checkpoint** (`checkpoint.json`): which V8-011 evidence stays applicable, what is superseded, reusable commands, locations.

## Functional walkthrough — the installed V8-011 candidate wheel

The environment is the V8-011 one: installed from the candidate wheel (pip's own record shows sha256 `7c2dd63d…`).
**Run from your home directory, not from a checkout** — inside `~/yuclaw-v8` Python would load the checkout's `v8/`
instead of the installed wheel. On the executor machine:

    cd ~ && W=~/yuclaw/internal/v8/v8_011_20260919T110207Z/walkthrough
    $W/venv/bin/python -c "import v8.workbench, os; print(os.path.dirname(v8.workbench.__file__))"   # must print a path under $W/venv
    $W/venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/v8-012-research --port 8765     # terminal 1
    $W/venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/v8-012-fresh    --port 8766     # terminal 2

The servers bind the **executor machine's** loopback only. `http://127.0.0.1:8765/` opened in a browser on another
computer reaches that computer, not the executor. From a Mac, first open a tunnel yourself, in a Mac terminal, with your
usual SSH login to the executor, keeping the same port numbers (the server checks the Host header):

    ssh -N -L 8765:127.0.0.1:8765 -L 8766:127.0.0.1:8766 <your usual SSH login to the executor>

Then, on the Mac, open <http://127.0.0.1:8765/> (research) and <http://127.0.0.1:8766/verify> (fresh). Stop the tunnel
and the servers with Ctrl-C. Nothing listens on a network interface at any point.

Path: **Load a fictional fixture** `003_withdrawal` → follow the seven steps on its claim → **1 Source → Correct a
source's availability time**: the withdrawal source (`0000000000-26-000004…`, available 2026-08-04T20:58:00Z), corrected
time `2027-03-01T00:00:00Z`, a reason, an evidence reference, your name → open the claim: recorded result beside the
corrected view, *Needs review* → add `?as_of=2026-09-01T00:00:00Z` to the claim URL: the correction is only *listed as
later* → **7 Reproducible export** → upload the zip at the fresh workspace's `/verify`. Help is at `/help`.

| Check | Observation (blank until the owner performs it) |
|---|---|
| Both servers start; the module path is under the walkthrough environment; Help is readable | |
| Seven-step journey on the fixture: source → typed claim → comparison → calculation → history → adjudication → export | |
| Source-time correction recorded; a refused form explains itself and keeps the entries | |
| Claim page: recorded result and corrected view are shown separately; *Needs review* is clear | |
| Earlier historical cutoff (`?as_of=2026-09-01T00:00:00Z`): the correction is listed as later, not applied | |
| The export verifies in the fresh workspace (SUCCESS, recomputed) | |
| Anything confusing, missing or wrong | |

This is ordinary functional review. It is not a study and Gate 15 is not reopened.

## Remaining decisions (the owner's)

1. Approve or decline the **branch push** of this branch tip (full sha in the handoff report). It publishes the
   unreleased source in the public repository; it deploys, tags and uploads nothing. Then read the hosted
   `v8-prerelease-validation` run whose `headSha` is that sha. Until it succeeds, remote CI is NOT_RUN.
2. Perform the walkthrough.
3. D1 (P5) — at the freeze, on the private copy naming the frozen commit (`freeze_procedure.md` step 6b).
4. The freeze window, then the separate verbatim authorization sentence for the frozen commit and tree.
