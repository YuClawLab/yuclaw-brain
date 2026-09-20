# YUCLAW workbench — startup and operator guide

The workbench is a local, owner-operated research tool. It runs on your machine, binds to 127.0.0.1 only, and never
publishes, trades, trains or contacts a service. Research and education only. Not investment advice.

This guide ships inside the installed package and is shown in the running workbench under **Help** (`/help`).
Print it any time with `python -m v8.workbench guide`.

## 1. Install

    python3 -m venv ~/yuclaw-venv
    ~/yuclaw-venv/bin/pip install yuclaw            # or: pip install <the wheel file you were given>

Python 3.10 or newer. The commands below use that environment's interpreter; from a source checkout the same
commands work as `python3 -m v8.workbench …` in the repository root.

## 2. Create the two workspaces and start the server

A workspace is one directory holding one append-only, digest-chained event log plus the exports it built. It is created
the first time you serve it. Use two: one where you do the research, and a **fresh** one that has never seen that
research, so an export can be verified independently of the workspace that produced it.

    ~/yuclaw-venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/research --port 8765
    ~/yuclaw-venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/fresh    --port 8766

Run each command in its own terminal. Open <http://127.0.0.1:8765/> (research) and <http://127.0.0.1:8766/> (fresh).
Keep a workspace outside any published `docs/` tree; the server refuses a bind other than loopback.

**Stop** a server with Ctrl-C in its terminal. Every recorded action is already durable on disk; nothing is lost by
stopping. **Start** it again with the same command: the workspace is re-read and its chain is checked. After a restart,
reload any form page that was already open before you submit it (form tokens are issued per server start).

Check a workspace without a browser: `python -m v8.workbench status --workspace ~/yuclaw-workspaces/research`.

## 3. Every enabled function and where it is

The navigation bar is on every page. With the research server on port 8765:

| Function | Where | What you do there |
|---|---|---|
| Workspace overview | <http://127.0.0.1:8765/> | see your claims and computed results; load a clearly fictional fixture (demonstration data) |
| 1 Source | <http://127.0.0.1:8765/source> | register the exact passage with its availability time; register a record written by the ingestion tool; view sources as of a cutoff; correct a wrong availability time with a linked event (<http://127.0.0.1:8765/source#availability>) |
| 2 Typed claim | <http://127.0.0.1:8765/claim/new> | save and freeze a fully specified commitment; every comparability field is mandatory |
| 3 Comparison | a claim's page, `#comparison` | original and revised ranges side by side, or INCOMPARABLE with every reason |
| 4 Calculation | a claim's page, `#calculation` | the disclosed outcome against each range, with inputs, formula and source links; record the outcome |
| 5 History | a claim's page, `#history` | replay as of any cutoff; later information is never shown as known earlier |
| Research notes | a claim's page, `#notes`; all notes at <http://127.0.0.1:8765/notes> | record an unresolved question, the next evidence needed and why; correct a note without changing the claim |
| 6 Adjudication | a claim's page, `#adjudication` | reviewer label, rule, evidence, reason, conflicts; a disputed label stays visible beside the computed result |
| 7 Reproducible export | a claim's page, `#export` | build and download the research export; publication eligibility is shown separately |
| Dataset coverage | <http://127.0.0.1:8765/dataset> (machine-readable: `/dataset.json`) | one row per frozen claim derived from stored records; snapshot identity; build a verifiable snapshot export |
| Scientific report / replay | <http://127.0.0.1:8765/sci> (each record: `/sci/S1`, `/sci/S2`, …) | replay a science journal through the packaged kernel: a recomputed report, or a refusal with its specific reason |
| Verify an export | <http://127.0.0.1:8766/verify> (the **fresh** workspace) | upload an export zip; bytes, digests, notes, dataset rows and scientific records are recomputed |
| Journal | <http://127.0.0.1:8765/journal> | the append-only, digest-chained event log |
| Help | <http://127.0.0.1:8765/help> | this guide, with links |

A claim's page is `http://127.0.0.1:8765/claim/<claim id>`; open it from the Workspace overview. The seven steps and
the fresh-workspace verification are done entirely in the browser.

**A first run with demonstration data.** On the Workspace page load fixture `001_base` (fictional: original target
110–120 million, revision 105–115 million, actual 112 million). Its claim page shows both ranges evaluated separately —
each IN_RANGE — and states that agreement between them is not evidence of improved accuracy. Build the export under
step 7, download it, open the fresh workspace's **Verify an export** page and upload it: the result is SUCCESS with the
recomputed values. Change one byte of the zip and it is MISMATCH.

**Bounded ingestion (optional, command line).** The server has no network access of its own. To fetch one real
disclosure from an allow-listed host and extract the exact passage:

    ~/yuclaw-venv/bin/python -m v8.workbench.ingest --url <https URL> --kind filing --form "8-K EX-99.1" \
        --accession <EDGAR accession> --cik <CIK> --pattern '<regex locating the passage>' \
        --rights SEC_PUBLIC_FILING --out ~/yuclaw-ingest --label original

**Your SEC request identity is your own setting.** The SEC asks every requester to identify themselves with a name and
a contact address. Before a run that reaches the SEC (every `--kind filing` run does), set the environment variable in
the shell you run the tool from, replacing both parts with your own:

    export SEC_USER_AGENT="Your Name your.address@example.org"

The tool supplies no identity on your behalf and looks for one nowhere else. If the variable is missing, still holds
the placeholder above, or carries no name or no contact address, the tool prints `[ingest] REFUSED: SEC_USER_AGENT …`
with this setup step, exits 2 and sends no request. The value is sent to `www.sec.gov` and `data.sec.gov` in the
request header only: other allow-listed hosts receive the product name without a contact, and the value is never
written into a source record, a provenance record, an export or a message. Nothing else needs it — fixtures, stored
source records, calculations, exports and export verification all work offline without the variable. On success the tool writes `original.source.json` (paste its content into **1 Source → Register from an ingestion record**,
with the `retrieved_at` of `original.provenance.json` as the observation time) and keeps the original bytes. On failure
it prints `[ingest] REFUSED: <reason>`, exits 2 and writes no source record: correct what it names and run it again.

## 4. When something is refused

Nothing is written when a form is refused. The page comes back with the reasons at the top and everything you entered
still in the form; correct the listed fields and submit again. Things that are refused by design:

- a freeze with a missing fiscal period, currency, basis, unit or resolution rule, or without a registered source;
- an unknown availability time (it is never guessed) or a timestamp that is not UTC `YYYY-MM-DDTHH:MM:SSZ`;
- an adjudication label that differs from the computed result without the **Disputed** flag and a reason;
- a scientific input outside the supported contract (for example monetary ranges supplied as probabilities);
- an export zip that is not a supported packet (UNSUPPORTED) or whose content does not reproduce (MISMATCH).

A frozen claim is never edited: a change is an **amendment** (a new version), a wrong source is a **CORRECTED_SOURCE**
amendment, a wrong note is a correcting note. A missing outcome stays `PENDING_OUTCOME`; a withdrawal is not a miss.
Freezing is one-way and the log is append-only.

Timestamps you cannot establish: leave nothing to be guessed. A source whose availability time is unknown cannot be
registered as available. If a claim cited the wrong passage, register the right one and record a CORRECTED_SOURCE
amendment that cites it — what the workspace previously recorded as known, and when it recorded it, stays in the history.
**A wrong availability time is corrected, not edited.** A registered source is never edited and the same passage is
never registered twice. If the time it became public was entered wrongly, open **1 Source → Correct a source's
availability time**, choose the source, and give the corrected UTC time, the reason, an evidence reference (where the
corrected time comes from, e.g. the EDGAR filing index acceptance line — recorded as text, never fetched) and your
actor label. This records a new linked event, `SOURCE_AVAILABILITY_CORRECTED`; the server stamps its recording time
itself. The registration, the passage and its digest, the time this workspace observed it, and every frozen claim,
outcome and adjudication stay exactly as written. Three times stay apart: the *asserted availability* (registered,
then corrected), the *observation* by this workspace, and the *recording of the correction*.

What a correction does to historical views: it applies to cutoffs **at or after the time it was recorded**. A view at
an earlier cutoff keeps the value the record held then and lists the correction as a *later correction*, with what it
would change. A later correction is later knowledge — it is never shown as something known at the cutoff, it never
makes a source known earlier than the record held it, and no historical view is revised silently. On each claim that
cites the source, the recorded result stays where it was and the *corrected view* is shown beside it: the result
recomputed with the corrected time (a withdrawal counts as "before the outcome" only by availability), the
retrospective status, and a **Needs review** list when they differ or when an adjudication predates the correction.
A correction can make a record retrospective; it never makes a retrospective record contemporaneous. If your review
reaches a different label, record a further adjudication as **Disputed** with the reason; the correction event can be
ticked as its evidence. If someone corrected the same source after you opened the page, your submission is refused as
out of date and nothing is written. Exports carry the original registration and the whole correction chain; a fresh
workspace checks the links and recomputes the corrected view, and an export without a correction is unchanged.

## 5. An interrupted write

If the machine or the server stops in the middle of an append, the log can end with bytes that have no terminating
newline (a torn tail). Those bytes were never a durable event; every earlier event is intact. The workbench then shows
the **Workspace integrity** page instead of any other page and accepts no write until you decide:

- in the browser, press **Run recovery** on that page; or
- from the command line: `python -m v8.workbench recover --workspace ~/yuclaw-workspaces/research`.

Recovery copies the torn bytes to a side file next to the log (`…torn.<digest>`), truncates only those bytes and
records a `RECOVERY` event. Repeat the action that was interrupted; it was not recorded. Recovery is not a backup and
does not bring back data that was never written.

If the integrity page reports a chain failure (`E_HASH`, `E_CHAIN`, `E_SEQ`, `E_CORRUPT_LINE`), the log was changed
outside the workbench. Nothing is repaired automatically: stop the server, keep the directory as it is, and inspect it.
An export interrupted while being built is never listed as complete; build it again.

## 6. Limits to keep in mind

- Backup creation and restoration are not provided in 8.0.0. Restore not demonstrated. Research exports and release artifacts do not establish disaster recovery.
  Keep your own copies of a workspace directory if you need them.
- A research export is a local, rights-filtered packet for another researcher to verify. It is separate from public
  publication (shown as NOT ELIGIBLE on the claim page) and from backup.
- Fixtures and the packaged scientific examples are fictional demonstrations, never a dataset product. The workspace is
  a local snapshot of what you registered and when — it is not a live feed and nothing in it updates on its own.
- Reviewer and actor names are attribution labels, not authenticated identities, and do not establish independent
  review. Computational verification (digests re-derived, results recomputed) does not establish source authenticity.
- To return to the previous release: `pip install yuclaw==7.0.1` in the same environment. 7.0.1 has no workbench and
  does not read or change workspace directories; reinstalling 8.0.0 reads them again unchanged.
- One owner, one machine: there are no accounts, no roles and no network service. The person operating the workbench
  is the only one who can change evidence, record adjudications and build exports; no independent reviewer is assigned
  by the software.

## 7. The four modules: SHD, EVO, COM and PRC

Open **Modules** (<http://127.0.0.1:8765/modules>). Each module is always listed; what is not set up yet shows its exact
setup step and refuses — nothing falls back to an unprotected path. All four use the claims, versions and sources of this
workspace and write to the same append-only journal.

**Setup, once per workspace (host operator).** The first administrator is created only from the command line — a browser on
the loopback port can never enroll itself:

    python -m v8.workbench principals init --workspace ~/yuclaw-workspaces/research

It prints a credential once (only a hash is stored; there is no default password and no key ships with the package). From
then on **every page asks for sign-in** (<http://127.0.0.1:8765/login>). The administrator enrolls further principals under
**Setup** with one or more capabilities: `admin` (principals, trust roots, policy, approvals, budgets, overrides, dispute and
failure resolution), `submit`, `review`, `practice`. A credential can be rotated, given an expiry, or revoked (never
revived); sessions end on restart, sign-out, rotation and revocation. A principal whose only capability is `practice` can
open Practice, Modules, Help and its own exports, and nothing else. Signing in shows which local credential acted — not who
a person is, what they are qualified for, or whether two credentials belong to one person. Whoever can read the workspace
directory on this machine is outside every boundary described here. `python -m v8.workbench modules --workspace …` prints
the same status as the Setup page.

**Moving between the modules without retyping.** An object you already chose travels with you: on a claim's page, *submit a review
packet about it* and *create a practice task on it* open COM and Practice with that claim selected and its current version
shown; on **SHD → trust** a waiting submission is approved from its own row (the digest is the workspace's record — you add the
evidence digests you independently expect, the purpose and the expiry); an admitted decision's page offers *take the packets
into the COM queue* or *import the declared evaluations*; an EVO version's page registers a child of that version; a practice
session's page builds that session's packet; lineage, dispute targets, parents, supporting evaluations, principals, roots,
approvals and sessions are chosen from lists. What you still type: a NEW identifier you are creating (a principal, a version,
a budget period), and digests that come from outside the workspace. Every decision stays a button you press. Nothing carried
in a link, a list or a hidden field is trusted: the server checks it again for your principal, this workspace and the
object's present state — a claim amended since the page was shown is refused as a stale selection, and an identifier that
is not an object of this workspace is refused. **Preview** on the export page shows what a packet would contain and writes nothing.

**SHD — Distillation Shield** (<http://127.0.0.1:8765/shd>). A submitter uploads a bundle: a zip with `bundle.json`
(`schema` `yuclaw.shd-bundle/1`, one `purpose` of `evidence.reference`, `com.packets` or `evo.evaluations`, the listed
evidence files with sha256 and size, and a typed payload) plus `evidence/…` files; at most 8 MiB, 64 members. The server
stores and hashes the bytes and never opens them. An administrator **other than the submitter** approves that exact sha256
on **SHD → trust** (purpose, expected evidence digests, expiry within the policy); the approval is signed with the
workspace's Ed25519 key, whose private half stays in the workspace's private directory. **Request a decision**: the bundle is
opened only inside the restricted worker, and the approval is checked again at the moment the decision is committed. The
decision page shows a fixed code (for example `REFUSED_NO_APPROVAL`, `REFUSED_APPROVAL_EXPIRED`, `REFUSED_APPROVAL_REVOKED`,
`REFUSED_SELF_APPROVAL`, `REFUSED_BUNDLE_REJECTED`, `REFUSED_ISOLATION_UNAVAILABLE`), the next action, and four separate
answers: byte integrity, authority approval, factual adjudication (always NOT_ASSESSED) and release permission (always
NONE). An admitted bundle can feed COM intake or the EVO import while its approval stays applicable. Evidence text is shown
only to an administrator or reviewer, as inert escaped text.

*The restricted worker.* Setup shows a live probe. Backend `bwrap` (bubblewrap namespaces) is preferred; backend `landlock`
(Landlock file rules, a seccomp filter that refuses every socket, ptrace, signals to other processes and namespace calls,
resource limits, an empty environment) is used where bubblewrap cannot start. A backend is used only if the probe on this
host showed each denial: a canary secret unreadable, no write anywhere, canary TCP and UDP endpoints unreachable, no unix
socket, no new process, no signal to the server, a 2 GiB allocation refused, output and run time bounded. Support matrix:
Linux x86-64 and aarch64 with kernel Landlock (5.13 or later) or working bubblewrap — supported after the probe passes;
Ubuntu 24.04 denies bubblewrap its user namespace unless the machine's administrator installs an AppArmor profile for it
(this product never asks for that and never weakens a host setting); macOS, Windows and kernels without either facility —
SHD admission stays closed with `REFUSED_ISOLATION_UNAVAILABLE`, everything else works. The `landlock` backend is process
confinement, not a container: no separate PID or mount namespace, no defence against a kernel flaw. No independent security
review has been performed.

**EVO — Evolution Evidence Audit** (<http://127.0.0.1:8765/evo>). The administrator records one JSON configuration:
measurement `roots`, the eight `components` (`path` inside a root, `runtime`, `declared`, `unknown`, or `not_applicable`
with a justification), `depends_on` edges, `protocols` (component scope, built-in job `policy_conformance` or
`json_wellformed`, validity days) and `authority` lists. **Register** measures the configured files now (links and
secret-looking names are skipped unread) and records what changed from the parent. A reviewer who improved nothing on the
lineage runs the **trusted evaluation**: the scope is copied to a private immutable snapshot and the copy is what runs; if
the files no longer match the registered version the run is refused — register the new state as a new version. The
version page shows, per protocol, REUSE or REEVALUATE with reasons, open failures (they persist until an administrator's
evidence-backed resolution), reviews, test exposure, unknown inventory, linked commitments by currency, and a historical
cutoff. The eligibility line is a read-only answer about recorded evidence; it controls no deployment.

**COM — Research Commons Guard** (<http://127.0.0.1:8765/com>). The administrator sets a period budget: review minutes, a
separate practice reserve, a per-principal packet cap and a maximum of open tasks. Submitters send packets that reference a
claim here (or take them in from an SHD-admitted bundle). Packets with the same claim version, the same financial contract
(metric, currency, unit, scale, basis, fiscal period) and the same known source roots form one group with one review task;
every contributor stays listed. A reviewer who did not contribute **takes** a task (its cost is reserved under the workspace
lock), then start / pause / resume / finish / release; a lease that ran out returns the task to the queue with its observed
seconds. Scheduling cost is a default until a reviewer or administrator sets it; a submitter's estimate is only a proposal.
A task that does not fit waits with its reason while smaller ones proceed; an aged task holds the remaining capacity; an
oversized one is escalated; an urgent override orders first and creates no capacity; a budget cut below recorded use shows
the overrun. Only a reviewer or administrator can record a dispute, withdrawal or source correction; affected groups are
quarantined — a handling state, not a finding of misconduct — until an administrator resolves it, and anyone signed in may
appeal. The queue comparison on the page is a simulation on fixed synthetic arrivals.

**PRC — Independent Practice** (<http://127.0.0.1:8765/prc>). A reviewer freezes a task: question, optional claim, source
scope, judgment labels, and the reference with its provenance (unadjudicated reference, model answer, or a reference the
curator declares was reviewed — a declaration, not a verification). The reference is held by the server; the journal keeps
only a salted digest. A practitioner (never the curator) opens a session, declares assistance and earlier exposure
truthfully — every answer is accepted and labelled — reads the frozen evidence, and commits a judgment, reasoning, the
sources it rests on, or UNRESOLVED with what would resolve it. Only then does **Open the comparison** work. The attempt is
never replaced; reflections and reviewer feedback are later records; follow-ups are local due-states — nobody is contacted
and no study is run. A later source correction or claim amendment appears as a note on the current interpretation. Each session records its route confinement: a
practice-only principal is confined to the practice routes; a practitioner who also holds another capability is labelled
NOT_CONFINED, because claim pages, the journal and exports are open to it. Not
confidential from: the host administrator, the curator, an administrator principal, outside help, or an answer that is
public elsewhere. The records cannot prove authorship, comprehension or improved ability.

**Export and verification** (<http://127.0.0.1:8765/modx>). Build a packet of the module records you may export (a
practitioner: its own sessions, optionally with text withheld). Never included: credential hashes, signing keys, staged
bundle bytes, inspection excerpts, a comparison that was not revealed in the session. In a **fresh workspace**, Verify
re-hashes every event into the journal skeleton, links every private object, recomputes the COM, EVO and SHD views, and
reports signatures against that workspace's own trust roots: an unknown signer stays unknown, current authorization is
unknown offline, and nothing is imported. An administrator can issue a **checkpoint** on the Practice page; keep the
downloaded file somewhere else and supply it at verification to detect a truncated or altered journal.
