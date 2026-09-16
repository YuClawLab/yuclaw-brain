# V8-002 — connect the source-to-export workbench (local implementation and evidence only)

Recorded 2026-09-15. Branch `codex/v8-integration` (worktree `~/yuclaw-v8`, base v7.0.1 `696d871e`); implementation commit
`a41dc39e`; this record and its evidence follow in the next commit. Nothing in this order pushes, tags, deploys, uploads,
edits published assets, sends messages or sets `release_authorized`.

Mission: **Make financial AI accountable to evidence.**  Vision: **Become the Science Trust Layer for Financial AI.**

## Status per governing correction

| # | Correction | Status | Where |
|---|---|---|---|
| 1 | Interactive local browser workflow, seven steps, user saves/freezes, amends, adjudicates, downloads, verifies in a fresh workspace through the UI; outside `docs/`; guards preserved | COMPLETE | `v8/workbench/server.py`; journey 7/7 (`scorecard.json`, `journey/journey_log.json`) |
| 2 | Typed schema, deterministic comparator/calculator, v7 adapters; currency, unit, scale, metric, basis, fiscal period, resolution rule explicit; exact arithmetic; explicit unresolved reasons | COMPLETE | `schemas/CommitmentClaim.v1.json`, `v8/workbench/{schema,money,calc}.py` |
| 3 | FY2026 fixture preserved; quarterly fixture with explicit quarter dates and a new manifest entry; period mismatches tested; both calculations shown separately, no inference from two IN_RANGE results | COMPLETE | `tests/fixtures/v8/commitments/008_quarterly.json`, `manifest.json`; `tests/test_v8_workbench_calc.py` |
| 4 | Append-only version/history storage, safe writes, operation identifiers, retry handling, interruption tests without duplicate durable events; three time axes; no backdating | COMPLETE | `v8/workbench/store.py`; `tests/test_v8_workbench_store.py` |
| 5 | Local export separate from publication eligibility; PERMITTED class untouched; rights/privacy checks; canonical hashes AND recomputation in the fresh workspace; tampered/incomplete/unsafe packets rejected | COMPLETE | `v8/workbench/export.py`; `tests/test_v8_workbench_export.py` |
| 6 | Loopback bind; write protection (Origin/Sec-Fetch-Site/cookie/CSRF); Host allow-listed; file/network access restricted; source content inert | COMPLETE | `v8/workbench/server.py`; `tests/test_v8_workbench_server.py` |
| 7 | At most one eligible SEC-reporting issuer for quarterly revenue guidance under the established criteria; missing sources/outcomes recorded honestly | COMPLETE as a record: **NO_ELIGIBLE_ISSUER** | `real_data_selection.json` |
| 8 | Publisher drafting moved to V8-003; preservation of 6.0.x/7.0.0/7.0.1, journal operation identifiers and the PyPI README/logo rendering defect carried forward | CARRIED to V8-003 | proposal below |

Journey score: **7/7 DEMONSTRATED** in Chromium on candidate `a41dc39e` (every positive and negative acceptance case of the
scope's §5 table; see `scorecard.json`). Human benefit **PENDING**; experimental audits **EXPERIMENTAL** and absent; the fixture
data is clearly fictional and a demonstration, not a dataset product whose quality has been established. Gate #15 stays NOT_SATISFIED for v8 (the v7
exception is not inherited). Backups stay canceled. `release_authorized` stays false.

## Start the workbench (owner-operated, loopback only)

```
cd <this checkout>
python3 -m v8.workbench serve --workspace ~/yuclaw-workspaces/research --port 8765   # research workspace
python3 -m v8.workbench serve --workspace ~/yuclaw-workspaces/fresh    --port 8766   # a second, fresh workspace for verification
```
Open `http://127.0.0.1:8765/` (steps 1–7 are plain HTML forms; no JavaScript; nothing leaves the machine). Build an export on the
claim page, download the zip, then open `http://127.0.0.1:8766/verify` and upload it. Offline, without a browser:

```
python3 -m v8.workbench verify-export <export.zip>      # exit 0 SUCCESS · 1 MISMATCH · 3 UNSUPPORTED
python3 -m v8.workbench status  --workspace <dir>       # integrity (OK / TORN_TAIL / E_*), claims
python3 -m v8.workbench recover --workspace <dir>       # preserves a torn tail in a side file, truncates only it, records RECOVERY
python3 -m v8.workbench selftest                        # the workbench unit tests
```
A workspace must not live inside a public `docs/` tree (the v7 store boundary refuses it). The server refuses any bind other than
loopback; network exposure needs its own authenticated deployment design (scope §3).

## Reproduce the browser evidence

Playwright is a test-time tool, not a product dependency:
```
python3 -m venv /tmp/pw && /tmp/pw/bin/pip install playwright        # Chromium from the Playwright cache (or: playwright install chromium)
/tmp/pw/bin/python -m v8.workbench.journey --out <evidence dir>       # exit 0 only at 7/7
```
The runner starts two loopback servers, drives every step and negative case in Chromium, and writes `journey_log.json`
(per-step assertions, POST statuses, screenshot digests) plus the screenshots. A step is DEMONSTRATED only when all of its
positive and negative assertions passed in the browser; HTTP-level and unit tests never count.

## What was built

- **Typed claim** (`CommitmentClaim.v1`): every comparability field mandatory; amounts are integers or decimal strings in units
  (floats refused); the validator lists every blocking reason; the statement is authored text, the excerpt is the quoted passage
  whose digest binds the bytes (not publisher authenticity).
- **Calculator** (pure functions): compatibility in resolution order (basis, unit/currency, fiscal period, metric, declared
  comparability); `IN_RANGE` / `OUT_OF_RANGE` with exact midpoint, delta and signed distance; every unresolved state names its
  reason; original-range and revised-range evaluations are separate, with the standing statement that agreement is not evidence
  of improved accuracy. For the fictional 110–120 / 105–115 / actual 112 case: original delta −3,000,000, revised delta +2,000,000,
  both IN_RANGE.
- **Journal** (`commitments.jsonl`): digest-chained lines; a rewritten, deleted or reordered line makes the workspace refuse to
  serve; a torn tail blocks writes until recovery; `op_id` retries are idempotent and conflicts explicit; each event keeps
  `source_available_as_of`, `observed_at` and `recorded_at` apart; as-of views are cut by source availability.
- **Export/verify**: canonical research digest excludes the export id and time (two exports of one state reproduce the same
  digest); excerpts bundled only under `FICTIONAL` or `SEC_PUBLIC_FILING` rights; verification refuses traversal, symlinks and
  oversized archives, checks every digest and length, re-derives claim digests and event hashes and recomputes the results; an
  imported packet is recorded as a verification and never becomes a claim. Publication eligibility is reported separately and is
  NOT ELIGIBLE (commitments are not in the receipts `PERMITTED` class; adding them is an owner decision).
- **Server**: `127.0.0.1` only; CSP `default-src 'none'` (no scripts anywhere); Host allow-list; POST requires same-origin
  `Origin`, `Sec-Fetch-Site` same-origin/none when sent, the HttpOnly `SameSite=Strict` session cookie and its HMAC token;
  bounded bodies; exports served only by an id matching a fixed pattern; uploads verified in memory; all output escaped, passages in `<pre>`.
- **v7 reuse**: `v3.receipts.contracts` (canonical JSON, digests, timestamps), `v3.receipts.storage.resolve_store_root`
  (public-tree boundary), `v3.receipts.export` publication policy and free-text gates, `v3.receipts.packet.PERMITTED`
  (read, never changed). The fixture loader replays the V8-001 fixtures under fixture-suffixed claim ids.

## Checks run (this order)

| Check | Result |
|---|---|
| `pytest tests` (existing suite + workbench tests) | 225 passed |
| `pyflakes v8/workbench/*.py` | clean |
| `tools/check_leak_sweep.py` (tracked + staged) | OK; 93 pre-existing box-identifier warnings, unchanged |
| `tools/check_no_forms.py` (docs/ untouched) | OK |
| `tools/check_copy_consistency.py` | OK (canonical blocks unchanged) |
| CJK scan on new files | none |
| Browser journey (Chromium 151, Playwright) | 7/7 on `a41dc39e`; 22 positive and 18 negative assertions; POST statuses 303 / 422 / 200 as designed |

Not run: the 20-gate release-state generator on the v8 branch (no release candidate designated), live network probes,
any real-source ingestion, any independent review.

## Remaining blockers and findings

- **No eligible real issuer.** All three guidance objects in the offline corpus fail criteria 2 and 3 (no numeric range with
  currency, period and basis in the sourced passage; no comparable outcome in the window). Real data needs a bounded one-issuer
  ingestion path (DAT) with rights recorded — proposed for V8-003, owner approval required. Until then the workbench is a
  demonstration on fictional data.
- **Gate #15** remains NOT_SATISFIED for v8; **human benefit** PENDING; no pilot.
- **Publisher** not drafted (moved to V8-003 by the order): preservation tripwires for 6.0.x, 7.0.0 and 7.0.1, operation
  identifiers on the download-verification journal, and the **PyPI README/logo rendering defect** (README is the PyPI long
  description; the relative `brand/…` image path and the `<picture>` element do not render there) are carried forward.
- **Review attribution (corrected by V8-003 §3)**: the adjudications in the journey evidence were recorded by the automated
  journey runner as simulated test actions. They are neither owner review nor independent review, whatever identity the
  reviewer field carried at the time; the evidence itself (7/7 on `a41dc39e`) is unchanged.
- The Gate B go/no-go on 2026-09-19 (evening, Asia/Shanghai) must rerun the journey on the designated release candidate; this
  score binds candidate `a41dc39e` only.

## Proposed next bounded order — V8-003 "release path" (for owner approval)

1. Draft the v8 publisher as a reviewed copy of `publish_v701.py`: keep the A-6 authorization sentence bound to sha+tree and
   the actor/type checks, one build / same bytes, inverted tripwires that protect 6.0.x, 7.0.0 **and 7.0.1**, and an operation
   identifier on every download-verification journal write (the 7.0.1 repair carried forward). No upload; `release_authorized`
   stays false.
2. Resolve the PyPI README/logo rendering defect without touching the live site: either a PyPI-specific long description or an
   absolute asset URL that is only wired once the assets are public; the README canonical blocks stay byte-identical.
3. One bounded real-data ingestion path (DAT): one SEC-reporting issuer, quarterly revenue guidance, original bytes, exact
   passages, availability and retrieval dates, rights recorded (`SEC_PUBLIC_FILING`); re-run the selection criteria; if an
   issuer qualifies, run the seven steps on it through the browser and record a second scorecard. Fixture validation, real-data
   quality and human benefit stay three separate questions.
4. Gate B package for 2026-09-19: rerun the journey on the designated candidate, run the 20-gate generator on the v8 branch
   with the inherited-gate map (`v8/V8-001/inherited_gates.json`), record the owner's functional review as such, and write the
   two-tier release notes with the backup limitation (`v8/V8-001/release_limitation.txt`) and the Gate #15 status.
5. Keep COM/PRC/SHD/EVO absent/default-off, human benefit PENDING, optional modules out of the distribution; no push, deploy,
   PyPI upload, website change or community messaging in this order. Artifact freeze target 2026-09-20; release readiness
   target Monday 2026-09-21 (Asia/Shanghai), subject to the concrete release decision.
