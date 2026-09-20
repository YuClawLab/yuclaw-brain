# V8-016 — hosted CI on the V8-015 commit, clause-level verification, fixes (handoff)

Research and education only. Not investment advice. **One push was made in this order: the exact approved commit
`0c58de33…` to `codex/v8-integration`. Nothing else was pushed, tagged, uploaded, deployed, dispatched or announced.
`release_authorized=false`. D1 is PROPOSED. Gate 15 is REMOVED_BY_OWNER / NOT_REQUIRED (never PASSED). Human benefit is
PENDING. V8-013 stays paused. `owner_manual_walkthrough = NOT_PERFORMED_OPTIONAL`: by the owner's final instruction no
demonstration environment was set up, no credential was initialized, and no observation exists or is implied.
The V8-016 commit has NO hosted CI.**

Order file `CLAUDE_CODE_ORDER_V8_016.md`, sha256 `46b8124f52276223cf28627ab124f33d8d73351fbb46651c99aa209a46446e1b` —
verified; its sections 2 and 5 (owner demonstration, manual route) were superseded by the owner's final instruction.

## 1. Hosted CI — what it covers

Run **35500468128** — <https://github.com/YuClawLab/yuclaw-brain/actions/runs/35500468128> — `v8-prerelease-validation`,
push event, head `0c58de3387fa84d1037dd45c92753d1d942bcb92` (tree `1eeadbed…`, printed by every job), **success**,
2026-09-20T08:46:09Z → 08:50:54Z. It covers the **V8-015** state, not the commits of this order.

| Job | Result | What actually ran |
|---|---|---|
| tests (3.12, x86-64) | success | 349 passed, 1 skipped — printed: `no python3.10 interpreter on this host` (one packaging test; the floor job covers 3.10). PostgreSQL: the five disposable-PG16 tests ran and passed; compliance regression 21 passed against the PostgreSQL 16 service. |
| python-floor (3.10.21) | success | 166 passed — the same v8 test files on another interpreter, not additional coverage |
| package | success | clean-install PASS: wheel and sdist fresh installs, fixtures 7/7 and module journey 6/6 each; digests equal the local V8-015 pair. The real-source journey cannot run hosted (private sources). |

Isolation backend that actually ran on x86-64: **landlock**, every probe denial observed, valid bundles admitted. bubblewrap
is not installed there and is **verified on no host**. No failure, no weakened control. → `hosted_ci.json`

## 2. The 43 families, clause by clause

`clause_matrix.json` / `clause_matrix.md`: 125 clauses — 104 verified by software tests, 13 verified with a
stated limit, 5 needing external evidence, 3 not verifiable in this environment. For each clause: existing
evidence, what was missing when this order began, the work performed, the residual limitation. All 21 untested subclauses
V8-015 recorded across 20 families are addressed there — by a test, a fix, or an exact statement of the missing capability.

Defects and gaps this work FOUND and fixed (none was known before):

- a private object was synced but its **directory entry was not** — a power cut could have left the journal naming a lost file;
- the upload reader accepted **truncated bodies, a field given twice and any number of parts**; a client declaring more
  bytes than it sent could keep a server thread busy indefinitely;
- a CSRF field with **non-ASCII bytes crashed** the comparison (connection dropped; nothing written) — found by generated input;
- **terminal-escape and bidirectional-override characters** of untrusted text reached module pages verbatim;
- **C-02 required behaviour was missing**: the same passage under a second accession counted as a second independent root —
  COM now resolves identical bytes and authorized declared aliases to one root, for grouping, corroboration and disputes;
- a **test gap**: disabling the session-ownership rule failed no test (the rule itself was present) — test added;
- the descriptor and CPU limits of the worker were set but never observed — now probed and tested;
- the command line's `principals add | rotate | revoke | list` and its authority were **not documented** — now stated.

New verification (26 tests, `tests/test_v8_mod_verification_016.py` and one in `…acceptance_015.py`): independent processes
with barriers (reservations, caps, revocation between worker and commit, stale form, two attempts and a reveal, a staged
file rewritten while the real worker reads it); SIGKILL before, inside and after the journal append (no half decision,
capacity conserved, no early comparison, idempotent retry); the real upload socket under 16 hand-made and 160 seeded
generated requests; 14 controls disabled one at a time in disposable copies — including Landlock, seccomp and the resource
limits — each caught, none reaching the candidate; a kernel that answers ENOSYS to Landlock (simulated by an unprivileged
seccomp filter; the product unpatched) closes admission only; the command line's surface and record; 14 hostile-text
families; edited journal records; a really different installed distribution; a multi-capability practitioner's sweep;
a journal and export written before the modules existed. Workloads, seeds and unfavorable results: `verification_workloads.json`.

`backlog_reconciliation.json`: unchanged five NOT COMPLETE (COM-12, PRC-01, PRC-09, SHD-12, EVO-10) and three PARTIAL
(EVO-03, PRC-07, EVO-12) rows; COM-04's alias clause gained its software part; PRC-08 and EVO-05 keep their limits.

## 3. Identity and verification of the candidate

| | |
|---|---|
| Branch | `codex/v8-integration` — origin at `0c58de33…`; everything after it is **local only** |
| Candidate SOURCE commit / tree | `35d1d9d97e5d85b09ceb5ac1178ac7396ca4c76e` / `83634f37f4ff2284572369090ff63e5a325f3496` |
| Record HEAD | see `git rev-parse HEAD` — evidence-only records on top of the source; no packaged path differs |
| Wheel | `yuclaw-8.0.0-py3-none-any.whl` sha256 `fb452859000bc2dea943f47fedaa9fc575c25b421f0e15eb629f359a62df0291`, 1,008,322 B |
| Sdist | `yuclaw-8.0.0.tar.gz` sha256 `851e6a2c1d1133961217e51487b2224c05dd14716570533b5e33adcd52b4284f`, 5,263,294 B |
| Built | 2026-09-20T09:31:43+00:00, SOURCE_DATE_EPOCH 1580601600, python 3.12.3, build build 1.4.2, wheel_generator hatchling 1.32.3 — a CANDIDATE pair, not a final set |
| Earlier builds | V8-015 `d1f5c59f…`/`8d4b78f1…`, V8-014 `05a50fa2…`/`81ff6ae0…`, older ones: kept under their own identities, never relabelled. A first V8-016 build (source `6f9fcd15`) FAILED its member inspection — its sdist carried a test-fixture note — and is kept privately as a failed build |

- Fresh installs of the **wheel** and the **sdist** outside the checkout: original fixtures journey 7/7 / 7/7, real-source
  regression journey 7/7 / 7/7, module journey 6/6 / 6/6 (42 assertions, 15 negative) on the `landlock` worker; twine
  check rc 0; no credential store, key, vault, journal, order record or test fixture in either distribution. → `packaging.json`
- Full suite **397 passed**; Python 3.10.21 floor **192 passed**; the same floor with `cryptography==41.0.0` exactly (the declared
  lower bound; private run) **192 passed**; no skips. The pre-module build verifies a new export and reads the extended journal
  (private run); the forward direction is an automated test.
- Gates at the record HEAD: see gates.json → `gates.json`. D1: `V8-ALLOC-2026-09-20-P8`, PROPOSED; P7 … P3 preserved.

## 4. Remaining gaps (exact)

- **No hosted CI for this commit.** → `ci_push_plan.json` (PROPOSED, not executed).
- **bubblewrap**: verified nowhere; missing capability = a host that lets it create an unprivileged user namespace.
- **Power loss**: not staged. Process death at every journal boundary was; disk and file-system behaviour cannot be checked here.
- **macOS / Windows**: not run, not certified. The unsupported-host test is a simulated Linux kernel.
- **Host operator**: outside the principals' boundary by design; documented and journaled, not constrained.
- **Undeclared aliases** of different bytes stay separate roots; **packets are not anonymous**; a clock wrong by less than the
  distance to the last record is undetectable; a fresh receiver cannot know a trust snapshot is old.
- **External evidence that does not exist and is not claimed**: human effort comparison, qualified reviewer, learning-transfer
  study, independent security review, an organization-wide inventory, a deployment controller.

## 5. Decisions that need the owner

1. Approve or decline the follow-up branch push (`ci_push_plan.json`; exact command in the handoff report).
2. D1 (`D1_allocation_8.0.0_PROPOSED.json`), then the freeze (`v8/V8-012/freeze_procedure.md`) — neither is requested by this order.

No release date is committed.
