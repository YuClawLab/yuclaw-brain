# YUCLAW Version 8 — User Guide

*English edition • YUCLAW 8.0.1*

Downloads: [PDF](YUCLAW-v8-User-Guide-EN.pdf) · [DOCX (editable)](YUCLAW-v8-User-Guide-EN.docx) · [Guide index (bilingual)](README.md)  
Version française : [Guide utilisateur (FR)](YUCLAW-v8-User-Guide-FR.md)

> This Markdown edition is rendered from the same `guide_content.json` as the PDF and DOCX editions (`render_markdown.py`). Page references in the PDF correspond to the numbered sections below.

From a financial statement to a claim you can trace, review and reproduce.

### Mission

Make financial AI accountable to evidence.

### Vision

Become the Science Trust Layer for Financial AI.

A practical manual for researchers, reviewers and local workspace operators. Covers the seven-step workbench, SHD, EVO, COM, PRC, research exports and the public research website.

**Software covered:** 8.0.1. **Guide edition:** 1.1, 9 October 2026. Instructions are tied to this release; later versions may change labels or behavior.

Research and education only. Not investment advice. The workbench records and checks research; it does not place trades or publish your workspace.

- [yuclaw.ca](https://yuclaw.ca)

## Contents

1. [1 Find your way](#1-find-your-way)
2. [2 Install YUCLAW](#2-install-yuclaw)
3. [3 Your first complete workflow](#3-your-first-complete-workflow)
4. [4 Register a source](#4-register-a-source)
5. [5 Create and freeze a typed claim](#5-create-and-freeze-a-typed-claim)
6. [6 Compare and calculate](#6-compare-and-calculate)
7. [7 Read history without hindsight](#7-read-history-without-hindsight)
8. [8 Add notes and review judgments](#8-add-notes-and-review-judgments)
9. [9 Dataset and scientific replay](#9-dataset-and-scientific-replay)
10. [10 Export and verify research](#10-export-and-verify-research)
11. [11 Set up local principals](#11-set-up-local-principals)
12. [12 SHD protected evidence intake](#12-shd-protected-evidence-intake)
13. [13 EVO evidence reuse audit](#13-evo-evidence-reuse-audit)
14. [14 COM bounded review queues](#14-com-bounded-review-queues)
15. [15 PRC attempt before comparison](#15-prc-attempt-before-comparison)
16. [16 Export and verify module records](#16-export-and-verify-module-records)
17. [17 Optional disclosure ingestion](#17-optional-disclosure-ingestion)
18. [18 Troubleshoot without losing history](#18-troubleshoot-without-losing-history)
19. [19 Command and route reference](#19-command-and-route-reference)
20. [20 Terms and source documentation](#20-terms-and-source-documentation)

## 1 Find your way

Choose the public website to explore published evidence. Install the local workbench to create your own sources, claims, reviews and reproducible packets. A public ticker page does not automatically populate a local workspace.

| Your task | Read |
|---|---|
| Understand the product and read public evidence | This section |
| Install and finish a fictional first run | Sections [2](#2-install-yuclaw)–[3](#3-your-first-complete-workflow) |
| Register sources and freeze a financial claim | Sections [4](#4-register-a-source)–[5](#5-create-and-freeze-a-typed-claim) |
| Compare ranges and interpret outcomes | Section [6](#6-compare-and-calculate) |
| Replay history and correct a source time | Section [7](#7-read-history-without-hindsight) |
| Record notes, review and dataset or science records | Sections [8](#8-add-notes-and-review-judgments)–[9](#9-dataset-and-scientific-replay) |
| Export research and verify it independently of its workspace | Section [10](#10-export-and-verify-research) |
| Set up local roles and use the four modules | Sections [11](#11-set-up-local-principals)–[16](#16-export-and-verify-module-records) |
| Fetch a disclosure with the optional ingestion tool | Section [17](#17-optional-disclosure-ingestion) |
| Resolve an error or find a command | Sections [18](#18-troubleshoot-without-losing-history)–[19](#19-command-and-route-reference) |
| Check terminology and source documentation | Section [20](#20-terms-and-source-documentation) |

### Reading the public website

At `https://yuclaw.ca`, start with Explorer or a sector evidence lens, then open a ticker’s evidence and source links. Use Forward Tracking for recorded outcomes, the Evidence Scoreboard for receipt coverage, and Methodology for definitions. Check each artifact’s date, scope and completeness before comparing it with another.

Signal labels are research classifications. A score is not an expected return; evidence coverage is not a probability. A preview or capped list is not a full historical dataset. Read any limitation beside a benchmark score before using it.

### What v8 adds to your workflow

The local source-to-export workbench connects immutable claim versions, exact calculations, time-aware history and review. Four experimental modules add protected bundle intake, evidence reuse audits, bounded review queues and attempt-before-comparison practice. They record decisions and their limits; they do not certify truth or authorize an external deployment.

In this guide, English names such as **Source**, **Build export** and `IN_RANGE` match the product. Examples marked fictional are demonstrations, not observations about a real issuer.

## 2 Install YUCLAW

Use Python 3.10 or newer and a separate virtual environment. Internet access is needed to download the package. The fictional workbench walkthrough then uses packaged data; it does not require your production database or a live filing feed.

### macOS or Linux

```bash
python3 -m venv ~/yuclaw-venv
source ~/yuclaw-venv/bin/activate
python -m pip install "yuclaw==8.0.1"
python -m pip show yuclaw
yuclaw workbench --help
```

### Windows PowerShell

Use the environment’s interpreter directly; no PowerShell activation-policy change is required. Adjust the Python launcher selection if more than one version is installed.

```powershell
py -3 -m venv "$HOME\yuclaw-venv"
& "$HOME\yuclaw-venv\Scripts\python.exe" -m pip install "yuclaw==8.0.1"
& "$HOME\yuclaw-venv\Scripts\python.exe" -m pip show yuclaw
& "$HOME\yuclaw-venv\Scripts\python.exe" -m v8.workbench --help
```

### Check this installation once

```bash
yuclaw workbench selftest
yuclaw workbench guide
```

On Windows, replace `yuclaw workbench` in later commands with the environment’s `python.exe -m v8.workbench` form above. On macOS or Linux, activate the environment in each new terminal, or use its full executable path. Commands continued with a trailing backslash use macOS/Linux syntax; in PowerShell, enter the command on one line and remove those continuation backslashes.

**Expected:** package metadata shows 8.0.1; help lists the workbench commands. The optional selftest creates temporary fictional workspaces, exercises calculations and export verification, checks refusal behavior, then removes its temporary folder. It checks this installation, not the entire development test suite.

### Platform distinction

Core workflows and the other modules are available without SHD admission. Protected SHD intake requires a supported Linux isolation backend that passes the live probe. On macOS and Windows that route stays closed. A closed SHD route is not a failed installation of the core workbench.

These Windows commands are the interpreter equivalent of the shipped CLI. This guide does not claim that every OS, kernel and hardware combination was independently tested.

## 3 Your first complete workflow

### Start a research workspace

In the first terminal, with the virtual environment active:

```bash
yuclaw workbench serve --workspace ~/yuclaw-workspaces/research --port 8765
```

In a second terminal, activate the same environment and start a different workspace:

```bash
yuclaw workbench serve --workspace ~/yuclaw-workspaces/fresh --port 8766
```

On Windows use quoted absolute workspace paths, for example `"$HOME\yuclaw-workspaces\research"`. Each directory is created on first use. Keep it outside a published website directory. Use a different workspace directory for each server.

### Follow the fictional example

- Open `http://127.0.0.1:8765/`. In **Load a fictional fixture**, select `001_base`, then **Load fixture**.
- Open claim `ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base` (the loader appends the fixture identifier to the claim ID, so a loaded demonstration is never mistaken for a hand-made claim). Read steps 1–6: source, typed claim, comparison, calculation, history and adjudication.
- Confirm the original range is 110–120 million, the revised range 105–115 million and the disclosed outcome 112 million. Both calculations should be `IN_RANGE`.
- Under step 7, choose **Build export**, then download the ZIP. Keep its reported digest with it.
- Open `http://127.0.0.1:8766/verify` in the fresh workspace. Select the downloaded ZIP and submit it. Expect `SUCCESS` with recomputed results.

This is a fictional retrospective example, including its future-dated outcome. It demonstrates software behavior. It does not establish real predictive accuracy, and the fresh workspace is not a second independent person.

### Stop and resume

Press **Ctrl+C** in each server terminal to stop it. Restart with the same directory and port to resume. Completed recorded actions remain in the journal. Reload browser forms after a restart; their tokens belong to that server session.

```bash
yuclaw workbench status --workspace ~/yuclaw-workspaces/research
```

The server binds to `127.0.0.1`. Opening yuclaw.ca does not start it. Closing a browser tab does not stop the terminal process. No filing or outcome arrives automatically in this local workspace.

## 4 Register a source

Open **1 Source** at `/source`. Start with the exact passage you want the claim to cite. Registration preserves the passage and its digest; a paraphrase belongs in your research notes, not in the source excerpt.

| Field or concept | What to enter |
|---|---|
| Kind and form | The actual document type, such as a filing and its form. Do not label a press release as a filing merely to pass validation. |
| Accession or publisher identifier | The real EDGAR accession, or the supported publisher identifier shown by the form. |
| URL and filed date | The source location and stated filing date. A URL alone is not the evidence passage. |
| Exact excerpt | The source’s words, with its stated amounts, units and context intact. |
| Available as of | When the source became available. Use a supported UTC timestamp, such as 2026-02-10T21:05:00Z. |
| Observation time | When this workspace observed the source. It is distinct from the public availability time. |
| Rights and fictional flag | Use the applicable rights category. Mark demonstration data as fictional; do not assume reuse rights. |

Submit the form and confirm the registered source appears in the source table with its passage digest and times. The server stamps its own recording time. Select this registered source when creating the claim.

### If you already have an ingestion record

Use **Register from an ingestion record**. Paste the contents of the tool’s `original.source.json`; use the `retrieved_at` value from its provenance file as the observation time. The optional network ingestion procedure is on section [17](#17-optional-disclosure-ingestion).

### When the source is incomplete or wrong

An unknown availability time must remain unknown; it cannot be guessed to obtain a valid registration. If you cited the wrong passage, register the right one and create a `CORRECTED_SOURCE` amendment. If only the availability time is wrong, use the linked correction procedure on section [7](#7-read-history-without-hindsight). Never edit the stored source or journal by hand.

**Checkpoint:** the passage, document identity, rights and three different times are understandable without relying on your memory. Digest agreement establishes byte consistency; it does not authenticate the publisher or prove the statement true.

## 5 Create and freeze a typed claim

Open **2 Typed claim** at `/claim/new`. A typed claim makes the financial comparison explicit before a result is interpreted. Select the registered source, then complete every comparability field.

| Required information | Fictional example or rule |
|---|---|
| Claim and issuer identity | Use a stable new claim ID and the issuer’s correct name and identifiers. |
| Metric and statement | Revenue; retain the meaning of the source’s commitment. |
| Low and high in units | For USD 110–120 million, enter 110000000 and 120000000, not 110 and 120. |
| Currency, unit and scale | USD; USD; millions as stated. Scale describes the source wording; amounts are entered in units. |
| Accounting basis | Use the source’s GAAP, IFRS or other supported basis. Do not silently equate adjusted and unadjusted measures. |
| Fiscal period | Label, type and exact start/end dates. FY2026 in the fixture is 2026-01-01 through 2026-12-31. |
| Resolution rule and source | Choose the supported rule that defines the outcome test; cite the registered passage. |
| Fictional status | Mark fictional claims explicitly. Do not use demonstration identifiers for a real company. |

### Freeze deliberately

Check amount scale, basis, period and source before freezing. A successful freeze creates version `V1` and a digest. **Freezing is one-way.** A later correction or change creates a new record; it does not overwrite this version.

### Record a revision or withdrawal

On the claim page, use **Create an amendment**. Select the amendment type, update the fields supported by the new source, and give a reason. `REVISED` records a changed commitment; `CORRECTED_SOURCE` records a source correction. Earlier versions and their digests remain visible.

Use the withdrawal action when the commitment was withdrawn, with its supporting source and reason. A withdrawal is an event, not a replacement claim, and is not automatically a miss. Check the time relationship to the outcome.

Use plain decimal numbers in numeric fields. French thousands separators or decimal commas are not a substitute for the field’s required numeric syntax.

## 6 Compare and calculate

On a claim page, **3 Comparison** shows original and revised commitments. **4 Calculation** evaluates the disclosed outcome against each applicable range. Register the outcome source first, then use **Record the disclosed outcome**.

Enter the actual amount in units, currency, metric, basis and fiscal period. The recorder’s comparability checkbox is a declaration: the calculator still checks the fields. A result is meaningful only within the supported contract.

### Worked fictional example

| Quantity | Original | Revised |
|---|---|---|
| Range in USD millions | 110–120 | 105–115 |
| Midpoint | 115 | 110 |
| Actual | 112 | 112 |
| Actual minus midpoint | −3 million | +2 million |
| Containment result | IN_RANGE | IN_RANGE |

The rule is inclusive: **low ≤ actual ≤ high**. The midpoint is `(low + high) / 2`; the midpoint difference is `actual − midpoint`. Both ranges contain the same actual value. Their agreement does not establish that the revision improved forecasting accuracy or caused the outcome.

### Read unresolved results correctly

| Result | Meaning and next action |
|---|---|
| IN_RANGE / OUT_OF_RANGE | A compatible outcome is inside/outside the specified range. Read the source and rule alongside it. |
| PENDING_OUTCOME | No applicable disclosed outcome is recorded. Register it when supported; do not replace missing with zero. |
| INCOMPARABLE | The version comparison cannot be made. Read every reason; no comparative delta should be inferred. |
| INCOMPATIBLE_BASIS / UNIT_MISMATCH | Check source definitions, accounting basis and amount units. |
| PERIOD_MISMATCH / METRIC_MISMATCH | The periods or metrics differ. Correct the supported input through the appropriate recorded action. |
| WITHDRAWN_BEFORE_OUTCOME | A time-qualified withdrawal state, not a computed forecasting failure. |

Unsupported rules and a declared non-comparable outcome also remain unresolved. Never change a definition simply to turn an unresolved result into a pass.

## 7 Read history without hindsight

Use **5 History** on the claim page. Enter a UTC cutoff and select **Replay**. Compare that view with the current view to see what the record could support at each point. Module historical views use their recorded action times.

| Time | What it answers |
|---|---|
| Availability | When the source was asserted to be publicly available. |
| Observation | When the workspace observed it. |
| Recording | When the server recorded the action or correction. |

A historical filing entered today is not proof that this workspace held it at the filing time. A retrospective record stays labeled accordingly. Later information must not be read as earlier knowledge.

### Correct a wrong availability time

- Open **1 Source → Correct a source’s availability time** at `/source#availability`. Select the registered source.
- Enter the corrected UTC time, a reason, an evidence reference supporting that time and your actor label. The evidence reference is recorded text; the server does not fetch it.
- Submit. Confirm a new `SOURCE_AVAILABILITY_CORRECTED` event links the old and new values. The original passage, digest and observation time remain unchanged.
- Review each affected claim’s **corrected view** beside its recorded result. Read **Needs review** when timing, retrospective status or an earlier adjudication is affected.

### How cutoffs treat the correction

For a cutoff before the correction was recorded, the old value remains in force and the correction is shown as later knowledge. At or after its recording time, the corrected view applies. A correction can make a record retrospective; it cannot promote a retrospective record into a contemporaneous one.

If another correction arrived after you opened the form, reload it before deciding again. If your review changes the adjudication, record a further adjudication with **Disputed** and a reason; do not erase the earlier judgment.

**Checkpoint:** the history explains both what changed and when the workspace learned it. Exports carry the correction chain so another workspace can recompute the same views.

## 8 Add notes and review judgments

### Research notes

Use the claim’s **Research notes** section or `/notes`. Record the unresolved question, a possible explanation, the next evidence needed and why. Notes organize inquiry; they do not change frozen claims, computed outcomes or source passages.

A useful note names the exact uncertainty. For example: “The revised statement uses an adjusted basis. Obtain the reconciliation before comparing it with the original GAAP target.” This identifies an action without asserting a causal explanation.

Correct a mistaken note through a correcting note. Keep the earlier text and its place in the history visible. If the financial claim itself changes, use an amendment instead.

### Step 6 Adjudication

- Read the sources, exact calculation and any unresolved comparability reasons before selecting a label.
- Enter the reviewer label, rule, evidence references, reason and relevant conflicts in the adjudication form.
- If your label differs from the computed result, select **Disputed** and give the reason. The system retains the disagreement rather than replacing the calculation.
- After submitting, confirm that the reviewer’s label and the computed result are separately visible. Revisit the history if a later amendment or source-time correction affects the review.

### Attribution and authentication are different

A reviewer or actor name in the core research workflow is an attribution label. It does not establish an authenticated person, independence or qualifications. Module actions use local credentials once principals are configured; those credentials still do not prove real-world identity.

### A useful review handoff

Provide the claim ID, version and digest; source references; the applicable period, metric and basis; the calculation; unresolved questions; and the reviewer’s reason. Build the corresponding export on section [10](#10-export-and-verify-research) so a recipient can check the recorded computation.

An adjudication is a documented judgment under a stated rule. It is not an investment recommendation or permission to publish private workspace material.

## 9 Dataset and scientific replay

### Inspect dataset coverage

Open `/dataset`; `/dataset.json` provides the machine-readable view. There is one row per frozen claim, derived from this workspace’s records. Rows retain versions, source lineage, outcomes, review disagreement, rights restrictions, notes and unresolved reasons.

- Check counts for fictional and real-source records, retrospective status, missing outcomes, incomparable cases and withheld excerpts.
- Read **Coverage gaps and known omissions** before using any aggregate. An empty workspace is not evidence of complete coverage.
- Select **Build dataset snapshot export**. Retain its snapshot digest. Earlier snapshots remain available; their comparison identifies what changed.

The snapshot identity depends on records and method, not the moment you clicked the button. It describes this local collection, not a validated market-wide dataset or an automatically sampled population.

### Replay a supported science journal

Open `/sci`. Start with a packaged fictional exploratory example using the page’s example selector. Review the manifest and journal, submit the replay, then open its scientific record, such as `/sci/S1`. The record shows the recomputed report or an explicit refusal.

The supported kernel works with its declared statistical contract, including paired probability forecasts, Brier-score improvement and sequential evidence accounting. Read the manifest’s metric, unit, pairing and error-budget requirements before supplying your own journal. A monetary guidance range is not a pair of probabilities.

| Input or state | Interpretation |
|---|---|
| Packaged exploratory journal | Fictional software demonstration. No claim of financial benefit. |
| Prospective-mode example with a pending unit | A demonstration of pending-state handling, not a completed experiment. |
| Monetary amounts used as probabilities | Refused: outside the supported input contract. |
| Unsupported metric or missing prediction pair | Correct the protocol/input definition; do not reinterpret it as a passing result. |

Scientific replay recomputes what the journal states. It does not establish that observations were honestly collected, that an experiment was registered, or that an AI system improved. Keep fixture and real-research provenance distinct.

## 10 Export and verify research

### Create a claim or dataset packet

On a claim page, step 7 **Build export** creates a rights-filtered research ZIP. For a whole collection, use the dataset snapshot export. Download the completed packet and retain its reported digest and byte identity.

A claim packet contains the supported schema, versions, source references and permitted excerpts, events, methods, results and related research records. Rights restrictions may withhold excerpts. Module records require a separate module packet (section [16](#16-export-and-verify-module-records)).

### Verify in a fresh workspace

- Use the separate fresh server at `http://127.0.0.1:8766/verify`. Select the unchanged downloaded ZIP and submit.
- Read the result and the first discrepancy, if any. The verifier re-derives digests and recomputes the supported research content; it does not rely on the sender’s displayed result.
- Record what you verified: packet identity, result, software version and time. Do not describe a different file or sibling artifact as covered by this check.

### Verify a research ZIP from the command line

Replace `research-export.zip` with your downloaded file path. This command verifies a claim or dataset research export; use the module verification interface for module trust and checkpoint options.

```bash
yuclaw workbench verify-export research-export.zip --json
```

| Result | Exit | What to do |
|---|---|---|
| SUCCESS | 0 | Supported content was consistent and recomputed. Read its provenance and limits. |
| MISMATCH | 1 | Inspect the first discrepancy. Obtain the unchanged packet or have its producer resolve the recorded defect. |
| UNSUPPORTED | 3 | The format or input is outside this verifier’s contract. Check the packet type and software version. |

### What verification establishes

It establishes consistency of the supported packet and its calculations. It does not establish source authenticity, factual truth, independent human review or public-release approval. Research export is separate from publication and is not a workspace backup or a demonstrated restore procedure.

Keep the original ZIP unchanged. If you investigate corruption, work on a separate copy and retain the original identity.

## 11 Set up local principals

The core seven-step workflow can be explored before principal setup. The four modules require local capabilities. Create the first administrator from the host’s command line; browser access cannot enroll itself.

```bash
yuclaw workbench principals init --workspace ~/yuclaw-workspaces/research
```

The credential is printed once. Store it securely and do not paste it into notes or exports. There is no default password. After setup, every page requires sign-in at `/login`; use **Setup** at `/setup` to manage the workspace.

| Capability | Purpose |
|---|---|
| admin | Manage principals, trust, policy, approvals, budgets, overrides and recorded resolutions. |
| submit | Submit evidence bundles and review packets within the configured rules. |
| review | Review eligible work, run trusted evaluations and curate practice tasks within the module rules. |
| practice | Use practice tasks. A practice-only principal is confined to Practice, Modules, Help and its own exports. |

### Enroll only the capabilities needed

Use Setup or the host CLI. This example creates a practice-only credential; replace the ID with a new local identifier.

```bash
yuclaw workbench principals add --workspace ~/yuclaw-workspaces/research \
  --id learner1 --caps practice
yuclaw workbench principals list --workspace ~/yuclaw-workspaces/research
```

Rotation issues a new credential; revocation is permanent for that principal. Sessions end on sign-out, restart, rotation or revocation. Reload forms after signing in again.

### Keep separation meaningful

Use separate browser profiles for separate principals. A submitter cannot approve its own SHD submission; an EVO reviewer cannot have improved the reviewed lineage; a COM reviewer cannot review a group to which it contributed; a practitioner cannot be its task’s curator.

A local credential identifies which credential acted. It does not establish that two credentials belong to different people. Anyone who controls the operating-system account and workspace directory is the host operator and can administer principals through the CLI. These browser capabilities do not constrain that host operator.

```bash
yuclaw workbench modules --workspace ~/yuclaw-workspaces/research
```

## 12 SHD protected evidence intake

**SHD — Distillation Shield**, at `/shd`, checks a submitted evidence bundle through an approved, restricted intake path. Start by checking the live isolation status in Setup. An unavailable isolation backend keeps admission closed.

### Input contract

Use a ZIP conforming to `yuclaw.shd-bundle/1`: a `bundle.json` manifest plus the evidence files it lists under `evidence/`. The manifest identifies one purpose, full SHA-256 digests, byte lengths and the typed payload. This is not an arbitrary document-upload form. The bundle limit is 8 MiB and 64 members; further per-member and expansion limits apply.

Supported purposes are `evidence.reference`, `com.packets` and `evo.evaluations`. For bundle construction, follow the versioned schema and worker validation source listed on section [20](#20-terms-and-source-documentation). Do not invent fields or approvals.

### Submit and obtain a decision

- As a submitter, upload the prepared bundle. Record its reported digest. Uploading stores the bytes; it does not admit them.
- A different administrator opens `/shd/trust`, chooses the waiting submission, independently checks the expected evidence digests, and records purpose and expiry. Approval is bound to the exact bundle and workspace.
- Request a decision. The restricted worker opens and checks the bundle; the approval is checked again when the decision is committed.
- Read all four answers: byte integrity, authority approval, factual adjudication and release permission. An admitted bundle may then feed COM or EVO through its offered action while approval remains applicable.

| Refusal | Next action |
|---|---|
| REFUSED_NO_APPROVAL | Obtain an applicable approval from a different administrator. |
| REFUSED_APPROVAL_EXPIRED / REVOKED | Resolve approval state; an old approval cannot be reused. |
| REFUSED_SELF_APPROVAL | Use the required separate approving principal. |
| REFUSED_BUNDLE_REJECTED | Read the structural/digest reason; correct the bundle as new bytes. |
| REFUSED_ISOLATION_UNAVAILABLE | Use a supported Linux host whose probe passes. Do not bypass the closed route. |

**ADMITTED does not mean true.** Factual adjudication remains `NOT_ASSESSED` and release permission `NONE`. Protected intake uses a probed bubblewrap or Landlock backend; it is not an independent security certification. Landlock confinement is not a full container.

## 13 EVO evidence reuse audit

**EVO — Evolution Evidence Audit**, at `/evo`, records what changed in an AI system and whether recorded evaluation evidence still applies. It does not modify the system or control its deployment.

### Configure what you can actually measure

An administrator records the JSON configuration on the EVO page. Set existing absolute measurement `roots`, component modes, dependency edges, evaluation protocols and authority lists. Use the schema in the versioned source for exact JSON; a path must remain inside a configured root.

| Component keys | How to represent them |
|---|---|
| model, agent_code, tool_policy, memory | Measure accessible files with mode path; use declared for an attributed statement, or unknown when unmeasured. |
| data, grader, evaluation_data | Keep evaluation inputs and grader identity explicit. Their changes can invalidate evidence reuse. |
| runtime | Use runtime to measure the environment, or another supported mode that accurately describes the evidence. |
| Any inapplicable component | Use not_applicable with a justification, not an unexplained omission. |

A protocol names its component scope, a supported job (`policy_conformance` or `json_wellformed`) and validity days. `depends_on` records relevant dependencies. Authority lists identify grader writers, evidence writers, release authorizers and protected-test readers. A change to those lists stops reuse; earlier test exposure is retained.

### Register and evaluate

- Select **Measure and register**, supply a new version ID and its parent where applicable. Read measured, declared, unknown and not-applicable status separately.
- A reviewer who did not improve that lineage runs the trusted evaluation. The runner checks the registered identity and executes against a private immutable copy of the supported scope.
- If current files differ from the registered version, register their new state as a new version. Do not reuse the old version label for changed bytes.
- On the version page, inspect each protocol’s `REUSE` or `REEVALUATE` answer, dependency reasons, open failures, reviews and test exposure. Use a historical cutoff when reviewing an earlier decision.

Open failures remain until an administrator records an evidence-backed resolution. An SHD-imported evaluation is a `DECLARED_IMPORT`, not a trusted local run. Linked financial commitments remain separated by currency.

**Checkpoint:** reuse is justified by the recorded identity and scope. An eligibility line is an evidence assessment; no external release is authorized by EVO.

## 14 COM bounded review queues

**COM — Research Commons Guard**, at `/com`, groups related packets and allocates a recorded review budget. Begin with an administrator’s period budget: review minutes, a separate practice reserve, per-principal packet cap and maximum open tasks.

### Submit and group packets

From a claim page choose **submit a review packet about it**, or use COM directly. Confirm the selected claim version and financial contract. An admitted SHD bundle can provide a separate intake route.

Packets sharing the same claim version, metric, currency, unit, scale, basis, fiscal period and known source roots form one group with one review task. Contributors remain listed. Multiple packets are not automatically multiple independent pieces of evidence.

### Handle duplicate sources explicitly

Identical passage bytes resolve to one source root. A reviewer or administrator may declare a source alias under **Source aliases**, with a reason; retraction preserves both records. This is not semantic similarity detection: a different rendering remains separate unless its relationship is recorded. A dispute on an alias reaches groups resting on the same document.

### Work a task

- As a reviewer who did not contribute to the group, take the task with **Take (reserves the cost)**. Its scheduling cost is reserved under the workspace lock.
- Use **start**, **pause**, **resume**, **finish** or **release** to record the actual workflow. A lease that expires returns the task with its observed seconds.
- Check the reason when a task waits. Small tasks may proceed while one does not fit; an aged task can hold remaining capacity; an oversized task is escalated.
- An urgent override changes priority, not available minutes. A budget reduced below recorded use shows the overrun rather than hiding it.

### Disputes and appeals

A reviewer or administrator can record a dispute, withdrawal or source correction. Affected groups are quarantined until an administrator resolves them. Quarantine is a handling state, not a misconduct finding. Any signed-in principal may appeal; the record retains the reason and disposition.

A submitter’s time estimate is only a proposal; the reviewer or administrator sets scheduling cost. The queue comparison shown on the page uses fixed synthetic arrivals. It is a simulation, not evidence of real productivity gains.

## 15 PRC attempt before comparison

**PRC — Independent Practice**, at `/prc`, preserves an initial attempt before revealing a reference comparison. It is an optional local practice workflow. It does not recruit participants, contact anyone or run a study.

### Curate a task

A reviewer freezes the question, optional claim reference, source scope, allowed judgment labels and comparison reference. State the reference provenance: unadjudicated reference, model answer or curator-declared reviewed reference. The declaration does not independently validate the reference.

The server keeps the unrevealed comparison privately; the journal holds a salted digest. Configure the separate practice budget before sessions require it. Use a practitioner other than the task curator.

### Complete a session

- Sign in with the practitioner credential. A practice-only credential keeps the browser session within practice routes and its own exports.
- Open a session and declare assistance and earlier exposure honestly. Answers are accepted and labeled; disclosure does not erase the attempt.
- Read the frozen evidence. Commit a judgment, reasoning and supporting source references. Use `UNRESOLVED` when appropriate and state what would resolve it.
- Only after committing, choose **Open the comparison**. Review the reference’s provenance and how it differs from your attempt.
- Add a reflection. A reviewer can add later feedback. Both are new records; the original attempt remains unchanged.

### Interpret confinement and privacy

A practitioner with additional capabilities is labeled `NOT_CONFINED`, because other routes may reveal relevant information. The reference is not confidential from the host operator, curator or administrator, and the software cannot prevent outside help or an answer found elsewhere.

A source correction or claim amendment appears as a note on current interpretation. Follow-ups are local due-states, not notifications sent to people. Build a session packet from its page if you want to retain or share the supported record.

**Checkpoint:** an attempt precedes the recorded comparison reveal. That sequence does not prove human authorship, no outside assistance, research originality, comprehension or improved ability. No ranking of people is produced.

## 16 Export and verify module records

Open **Module evidence export and verification** at `/modx`. A claim’s research export does not carry module records. Choose the module scope and practice sessions your principal is allowed to export.

### Preview before building

- Choose SHD, EVO or COM scope and any permitted PRC sessions. A practitioner can export its own sessions, with the available option to withhold text.
- Select **Preview**. It shows the intended contents without writing an export. Review identities and disclosure before building.
- Build and download the packet. Keep its digest and, when applicable, a separately issued checkpoint.

| Included when in scope | Excluded |
|---|---|
| Supported module events, journal skeleton, selected private objects and derived views | Credentials, credential hashes and signing private keys |
| Attempts, reflections, feedback and comparisons already revealed in the chosen sessions | Staged bundle bytes, inspection excerpts and unrevealed comparisons |
| Principal identifiers and provenance labels | Any claim that the packet is anonymous |

### Verify in a fresh workspace

Use the fresh workspace’s verification page and the module packet workflow. Supply a checkpoint when you have one. The verifier checks journal links and objects, recomputes COM, EVO and SHD views, and evaluates signatures against that receiving workspace’s own trust roots. Verification imports no records into operational module state.

A structurally valid signature from an unknown signer remains unknown. Current authorization is unknown offline; a historical trust snapshot does not prove that approval is still current. Do not enroll a key merely because an untrusted packet asks you to trust it.

### Checkpoint purpose

An administrator can issue a checkpoint on the Practice page. It records a journal sequence and tip with a signature. Keeping that file separately and presenting it to the verifier lets the check detect truncation or alteration relative to that checkpoint. It is not a backup or a restore mechanism.

A valid packet supports reproducibility of recorded operations. It does not make an admitted claim true, make two credentials independent people, or prove that a practice task improved someone’s ability.

## 17 Optional disclosure ingestion

The local server does not fetch filings on its own. The separate ingestion CLI can fetch one disclosure from an allow-listed host and extract a passage. Use it only when you know the document, relevant passage and rights category.

### Set your own SEC request identity

Every `--kind filing` run reaches the SEC. Replace both placeholder values with your own name and contact address before executing. No identity is supplied on your behalf.

```bash
export SEC_USER_AGENT="Your Name your.address@example.org"
```

In PowerShell, the equivalent environment assignment is:

```powershell
$env:SEC_USER_AGENT = "Your Name your.address@example.org"
```

A missing or placeholder identity is refused before any request. It is sent in headers to SEC hosts only, not written into source records or exports. Fictional fixtures and offline export verification do not need it.

### Fill in a command for one document

The following is a macOS/Linux shell template, not a ready-to-run real filing. Replace each angle-bracket value. Use the installed environment’s Python; on PowerShell use its full `python.exe` path and place the arguments on one line.

```bash
python -m v8.workbench.ingest \
  --url '<https URL>' --kind filing --form '8-K EX-99.1' \
  --accession '<EDGAR accession>' --cik '<CIK>' \
  --pattern '<regex locating the passage>' \
  --rights SEC_PUBLIC_FILING \
  --out ~/yuclaw-ingest --label original
```

### Inspect and register the result

On success, inspect `original.source.json`, `original.provenance.json` and the retained source bytes. Confirm that the selected excerpt contains the intended financial statement in context. On **1 Source → Register from an ingestion record**, paste the source JSON and use the provenance `retrieved_at` as observation time.

On refusal, read `[ingest] REFUSED: …`; exit 2 means no source record was written. Correct the named input. An extraction pattern matching text is not proof that the text supports your claim.

For other source types and supported options, read `python -m v8.workbench.ingest --help` in the installed version. Do not reuse `SEC_PUBLIC_FILING` for material whose rights differ.

## 18 Troubleshoot without losing history

| Symptom | Action |
|---|---|
| Command not found or wrong version | Use the intended environment’s executable. Run python -m pip show yuclaw with that same interpreter. |
| Browser cannot reach 127.0.0.1 | Keep the serve command running. Check its terminal error and port; if occupied, choose another port and use it in the URL. |
| Sign-in or form fails after restart | Sign in again and reload the form. Do not reuse a page carrying an old session token. |
| Operation already recorded, HTTP 409 | The operation ID was already used with different content. Reopen the form; reselect any uploaded file; submit deliberately. No recovery is needed. |
| Freeze or outcome refused | Read the listed fields. Check source, UTC time, metric, period, unit, scale, basis and resolution rule. |
| PENDING_OUTCOME or INCOMPARABLE | Missing or incompatible evidence is a real state. Supply supported evidence or retain the unresolved result. |
| SHD isolation unavailable | Check Setup. macOS/Windows keep admission closed; supported Linux still requires a passing probe. |
| Stale selection or changed EVO files | Reload and reselect the current object. Register changed system files as a new EVO version. |
| Module permission refusal | Check the signed-in principal, capabilities, current approval, contributor separation and configured budget. |
| Export MISMATCH or UNSUPPORTED | Check file identity and packet type. Read the first discrepancy; keep the original packet unchanged. |

### Workspace integrity page

An interrupted append can leave a final unterminated fragment, a torn tail. When the integrity page identifies that condition, **Run recovery** preserves those bytes separately, removes only the fragment and records a recovery event. Then repeat the interrupted action.

```bash
yuclaw workbench recover --workspace ~/yuclaw-workspaces/research
```

Use recovery for the diagnosed torn-tail condition, not as a general repair command. For `E_HASH`, `E_CHAIN`, `E_SEQ` or `E_CORRUPT_LINE`, stop the server, retain the directory unchanged and investigate. Do not delete journal lines to make the check pass.

Process-interruption handling does not establish survival of every power loss. An interrupted export is not listed as complete; build it again. An integrity error should remain visible until its actual cause is understood.

## 19 Command and route reference

With the environment active, `yuclaw workbench …` and `python -m v8.workbench …` call the same workbench. Replace example paths and identifiers with yours. `--help` starts no server.

### Daily commands

```bash
yuclaw workbench --help
yuclaw workbench guide
yuclaw workbench selftest --json
yuclaw workbench serve --workspace ~/yuclaw-workspaces/research --port 8765
yuclaw workbench status --workspace ~/yuclaw-workspaces/research
yuclaw workbench modules --workspace ~/yuclaw-workspaces/research
yuclaw workbench build-export --workspace ~/yuclaw-workspaces/research \
  --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
yuclaw workbench verify-export research-export.zip --json
```

### Credential maintenance by the host operator

```bash
yuclaw workbench principals rotate --workspace ~/yuclaw-workspaces/research \
  --id learner1
yuclaw workbench principals revoke --workspace ~/yuclaw-workspaces/research \
  --id learner1 --reason "Access ended"
```

These are actions, not status queries. Rotation issues a new credential; revocation cannot be undone. Use `principals list` for inspection.

| Local route | Purpose |
|---|---|
| /  ·  /source  ·  /claim/new | Workspace, source registration, new typed claim |
| /claim/\<claim id\> | Comparison, calculation, history, notes, review and claim export |
| /notes  ·  /dataset  ·  /dataset.json | Research notes and collection coverage |
| /sci  ·  /journal  ·  /help | Science replay, recorded events and packaged guide |
| /modules  ·  /setup  ·  /login | Module overview, setup and local sign-in |
| /shd  ·  /shd/trust  ·  /evo | Evidence intake, trust administration and reuse audit |
| /com  ·  /prc  ·  /modx  ·  /verify | Review queue, practice, module export and packet verification |

All routes above are relative to your local server, normally `http://127.0.0.1:8765`. Verification in the fresh example uses port 8766. They are not promised public routes on yuclaw.ca.

The broader YUCLAW package also has public-evidence and integration commands. Consult `yuclaw --help` for the installed release; their backend requirements are separate from this offline local walkthrough.

## 20 Terms and source documentation

| Term | Meaning in this guide |
|---|---|
| Source / claim / outcome | The evidence passage; the typed commitment; the separately disclosed result. |
| Freeze / amendment | Preserve a claim version; append a new linked version without overwriting it. |
| Digest | A hash identifying bytes or canonical content. Equal digests do not establish truth. |
| Journal | The ordered digest-linked record of local actions. Host filesystem access remains outside browser-role boundaries. |
| Retrospective | Recorded with hindsight or later knowledge; not established as a contemporaneous commitment. |
| Adjudication | A recorded judgment with a rule, evidence and reason; distinct from automatic calculation. |
| Principal | A local credential with capabilities, not a verified real-world person. |
| Source root | The underlying document identity used for grouping; aliases do not add independent corroboration. |
| Research packet / module packet | Different export formats and scopes. Verification must match the packet type. |
| Checkpoint | A signed journal position used to test continuity; not a restore mechanism. |

### Versioned references

The instructions are based on the 8.0.1 operator guide, CLI, data dictionary and module implementations, cross-read with the packaged fictional fixture. The public homepage was checked during preparation. Examples are instructional; this document is not a new release or an independent security audit.

- [YUCLAW 8.0.1 on PyPI](https://pypi.org/project/yuclaw/8.0.1/)
- [YUCLAW 8.0.1 release](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v8.0.1)
- [Versioned operator guide](https://github.com/YuClawLab/yuclaw-brain/blob/v8.0.1/v8/workbench/resources/OPERATOR_GUIDE.md)
- [Data dictionary and dataset card](https://github.com/YuClawLab/yuclaw-brain/blob/v8.0.1/v8/workbench/resources/DATA_DICTIONARY.md)
- [Workbench CLI and module source](https://github.com/YuClawLab/yuclaw-brain/tree/v8.0.1/v8/workbench)
- [SHD bundle validation contract](https://github.com/YuClawLab/yuclaw-brain/blob/v8.0.1/v8/workbench/modules/shield_worker.py)
- [EVO configuration contract](https://github.com/YuClawLab/yuclaw-brain/blob/v8.0.1/v8/workbench/modules/evolution.py)

For an issue report, include the software version, OS, exact action, expected result, actual result and a minimal fictional reproduction. Remove credentials and private evidence. Use the repository’s available support channel; sending a report is a separate action you choose.

The English and French guides cover the same release and preserve identical executable command examples. Neither changes the software’s rules, permissions or stored records.
