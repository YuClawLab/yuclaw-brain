# V8-014 r2 — SHD, EVO, COM and PRC implemented and packaged in the expanded 8.0.0 candidate (handoff)

Research and education only. Not investment advice. **Nothing was pushed, tagged, uploaded, deployed, dispatched or
announced in this order. `release_authorized=false`. D1 is PROPOSED. Gate 15 is REMOVED_BY_OWNER / NOT_REQUIRED (never
PASSED). Human benefit is PENDING. V8-013 stays paused. `REMOTE_CI_NOT_RUN_FOR_NEW_SHA`.**

Inputs: `YUCLAW-V8-014-r2-implementation-inputs.zip`, sha256 `26dd2a5c6b64b4241ea2ef58ad03f13d91f914f82996f5677b45fc1fb3625a87`
— verified; `MANIFEST.json` 41/41 entries match by sha256 and size. Reference prototypes were used as ideas only (strict JSON
and safe-read helpers adapted into the worker; the closure/scope-digest idea in EVO; exact grouping in COM; salted commitment in
PRC). No prototype file, SCI kernel, version metadata or package configuration was copied in.

## Identity

| | |
|---|---|
| Branch | `codex/v8-integration` (origin has it at `a4fa151f…`, the V8-012 tip; **this work is local only**) |
| Baseline | `a4fa151f82efd8e7de45c1a5cd66088ae4a9c2c7` — actual HEAD at start, clean; hosted run 35485844365 is evidence for that sha only |
| Candidate SOURCE commit / tree | `4f2ec11323938888c13a4102c0a50f8a62dbc013` / `02c261c77e14e2a51f6e1d83ab4510a96de179f5` |
| Record HEAD | see `git rev-parse HEAD` — evidence-only commits on top; no packaged path differs from the source |
| Wheel | `yuclaw-8.0.0-py3-none-any.whl` sha256 `05a50fa2cff970b215f07f1abff743e20506ce2b82e4e6b3c4bae2d3eeb3e910`, 997,654 B |
| Sdist | `yuclaw-8.0.0.tar.gz` sha256 `81ff6ae080b0750d75a646c3070760a00142a536ef1b8a26ae707a4c24aadaa9`, 5,252,403 B |
| Built | 2026-09-20T06:22:03+00:00, SOURCE_DATE_EPOCH 1580601600, python 3.12.3, build build 1.4.2, wheel_generator hatchling 1.32.3 — a CANDIDATE pair, not a final set |
| Superseded first build | source `bb1b0d81…`: passed every check; superseded by two packaged fixes (COM correction flag, sign-in cookie). Kept privately, not relabelled |
| New dependency | `cryptography>=41.0` (Ed25519 only). Platform: Linux for SHD admission (kernel Landlock ≥ 5.13 or working bubblewrap); Python ≥ 3.10 |

## What a user can do (entry points; all need the one-time setup below)

Setup (host operator, once): `python -m v8.workbench principals init --workspace <dir>` prints the first administrator's
credential once → sign in at `/login` → **Setup** enrolls principals with `admin` / `submit` / `review` / `practice`.

- **SHD `/shd`, `/shd/trust`** — submit an evidence bundle; an administrator other than the submitter signs an approval for
  its exact bytes; request a decision; read a fixed code, the next action and four separate answers; feed the typed result to
  COM or EVO. Evidence text is inert; an administrator can inspect it escaped.
- **EVO `/evo`, `/evo/version/<id>`** — record the configuration; register measured versions; run built-in evaluations on
  an immutable snapshot; see REUSE / REEVALUATE with reasons, open failures, gaps, a historical cutoff; request targeted
  reevaluation; link commitments; resolve a failure with evidence (administrator).
- **COM `/com`, `/com/group/<id>`** — set budgets; submit packets (direct, or from an SHD decision); see groups, attribution,
  plan and reasons; take / start / pause / finish / release / cancel; set cost, declare effort, override; record, appeal and
  resolve disputes; read the labelled simulation.
- **PRC `/prc`, `/prc/session/<id>`** — freeze tasks; open a session with truthful declarations; read frozen evidence; commit
  an attempt; open the comparison; reflect; receive feedback; see follow-ups; issue and download checkpoints (administrator).
- **Packets `/modx`** — preview and build a scoped export; verify any packet in a fresh workspace, optionally against a
  separately held checkpoint.

## Verification on the candidate (failures and skips listed separately)

- Installed from the **wheel** and from the **sdist**, fresh environments outside the checkout, no editable install, no
  PYTHONPATH: original fixtures journey 7/7 / 7/7, real-source regression journey 7/7 / 7/7, **module journey 6/6 / 6/6**
  (39 assertions, 14 negative) on the `landlock` worker; twine 7.0.0 check rc 0; every module file present;
  no credential store, key, vault or journal in either distribution. → `packaging.json`
- Full suite **356 passed** (307 earlier + 49 module tests). Python **3.10.21** floor job, exact CI commands in a fresh
  environment: **151 passed**. Failures: none. Skips: none in the module tests (the isolation tests run the real worker; they
  are written to fail, not skip, where no backend passes).
- Gates at the record HEAD: see `gates.json` ({"GREEN": 19, "REMOVED_BY_OWNER": 1}; correspondence `['no release-policy record']`).
- Defects found by my own checks and fixed before the final build: a consumer now re-validates exactly the approval its
  decision was bound to; the newest approval's refusal reason is reported; floats kept out of module events (packets were
  unreadable elsewhere); a built-in job read outside its protocol's closure; COM never showed a source-time correction;
  the form-token cookie is replaced at sign-in.
- Not verified: bubblewrap backend (cannot start on this host — platform gap, not worked around); x86-64 seccomp table;
  hosted runner kernel; a staged concurrent-replacement race; anything requiring people.

## Records

`backlog_reconciliation.json` (46 rows) · `claim_to_evidence.md` · `D1_allocation_8.0.0_PROPOSED.json`
(`V8-ALLOC-2026-09-20-P6`, PROPOSED; P5…P3 preserved) · `packaging.json` · `isolation_support_matrix.json` ·
`measurements.json` · `gates.json` · `ci_push_plan.json`. Private: `~/yuclaw/internal/v8/v8_014_20260920T045643Z/`
(inputs, both builds with journey logs and screenshots-free JSON logs, gates, measurement and probe outputs, PROGRESS.md).

## Manual walkthrough (observations blank until the owner performs them)

On the executor, from your home directory (inside a checkout Python would load the checkout, not the wheel):

    cd ~ && W=~/yuclaw/internal/v8/v8_014_20260920T045643Z/clean_install/venv-wheel
    $W/bin/python -m v8.workbench principals init --workspace ~/yuclaw-workspaces/v8-014-modules        # prints the owner credential once
    $W/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/v8-014-modules --port 8765     # terminal 1
    $W/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/v8-014-fresh   --port 8766     # terminal 2 (never run `principals init` here)

The servers bind the executor's loopback only. From the Mac open your usual tunnel with the same ports, then browse
`http://127.0.0.1:8765/login` on the Mac: `ssh -N -L 8765:127.0.0.1:8765 -L 8766:127.0.0.1:8766 <your usual SSH login>`.

| Step | Observation |
|---|---|
| Sign in as owner; Modules and Setup pages readable; the isolation probe table makes sense | |
| Setup: enroll `alice` (submit), `rita` (review), `pat` (practice); each credential shown once | |
| Load fixture `001_base`; claim page shows "In the modules" | |
| SHD: as alice submit any small bundle zip → decision REFUSED_NO_APPROVAL; as owner approve its sha256 → ADMITTED; four separate answers clear | |
| COM: owner sets a budget; alice submits the claim twice → one group, two packets; rita takes it; capacity table understandable | |
| PRC: rita freezes a task on the fixture source; pat opens a session, cannot see a comparison, commits, opens it, reflects | |
| As pat, try `/journal` or the claim page → refused with an explanation | |
| EVO: owner pastes a configuration for a small folder; a version registers; the version page is understandable | |
| `/modx`: build a packet as owner; verify it at `http://127.0.0.1:8766/modx` → SUCCESS, signer UNKNOWN_SIGNER | |
| Anything confusing, missing or wrong | |

## Freeze and readiness (realistic)

The 2026-09-21 target in the scope file is a historical target. Still required, in order: your walkthrough; your decision on
the CI branch push below and a green hosted run **on that exact sha** (x86-64 isolation is the main unknown); D1 on the
frozen identity; re-integration if `origin/main` moved (it moves Mon–Fri 23:00 UTC) → new source commit → NEW pair; the
freeze procedure of `v8/V8-012/freeze_procedure.md` (unchanged in structure) and the stored git token's missing `workflow`
scope. Five backlog rows cannot be completed by software. My assessment: not ready to freeze today; ready for owner review.
