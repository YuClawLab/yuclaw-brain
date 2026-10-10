# YUCLAW v9 — Research briefs with traceable AI assistance: user guide

Research and education only. Not investment advice.
Mission: Make financial AI accountable to evidence. Vision: Become the Science Trust Layer for Financial AI.

Software covered: YUCLAW **9.0.0** (brief layer `v9.brief/1`), as frozen for release on branch `codex/v9-integration` in October
2026. The CHANGELOG entry `[9.0.0]` and the GitHub release state whether it is published; this guide describes the frozen behaviour.
Every command and every output excerpt in this guide was run against that checkout in a disposable workspace. **All data
shown is fictional** — the packaged fixture `001_base` describes "Fictional Example Corp (ZZFX)", accession numbers of the
form `0000000000-26-00000x`, and amounts that were invented for the example. Identifiers such as `brf-4625e1016814`,
`bpk-a3ff4d970a5e16c3`, digests and timestamps differ on every run; the status words do not.

`yuclaw workbench brief …` and `python -m v9.brief …` are the same program. This guide writes `yuclaw workbench brief`.
Long workspace paths in the output excerpts are shortened to `~/yuclaw-workspaces/…`.

---

## 1. What a brief is, and what runs where

A **brief** is a short piece of financial research text whose individual sentences can be inspected: which exact source
passage, which frozen v8 claim version and which registered calculation each sentence rests on, how the text was produced,
what changed since, and which checks could or could not be run.

Everything in this guide runs **on your machine**, inside a workspace folder you name:

| Runs locally (v9) | Provided by the public website and repository |
|---|---|
| Composing briefs from templates over the frozen claims of your v8 workspace | The `yuclaw` package (PyPI releases from 9.0.0) |
| Importing drafts, linking sentences to claims, editing, translating | Documentation, release notes, the source code |
| Importing provenance records and keeping your own trust roots | Nothing about your workspace, briefs or packets: no brief is sent anywhere |
| Building verification packets and verifying them in a fresh workspace | |
| The browser pages at `http://127.0.0.1:8765/brief` (loopback only) | |

No API key, model download or hosted service is needed for anything below. Nothing in v9 contacts a translation or
generation provider; a translation you supply is recorded as *entered*, with your stated provenance, and is not certified.

---

## 2. Installation and prerequisites

- Python **3.10 or newer** (`requires-python = ">=3.10"`; this guide was run on 3.12).
- The `yuclaw` package. The v9 brief layer is part of the same package as the v8 workbench and **requires the v8 workbench
  in the same installation**: a brief is composed over a v8 workspace (`workspace.json`, `commitments.jsonl`) and reads its
  frozen claims. The declared dependency `cryptography` is needed to check signed provenance records (section 9).

```
python3 -m venv ~/yuclaw-venv && source ~/yuclaw-venv/bin/activate
python -m pip install yuclaw
yuclaw workbench brief --help
yuclaw workbench brief selftest          # checks this installation in a temporary fictional workspace
```

Until 9.0 is released, the same commands run from a checkout of the branch with `cd <checkout> && PYTHONPATH=. python3 -m v9.brief …`.

`selftest` creates a temporary workspace, runs the complete journey and deletes it. Expected ending (17 checks):

```
  [ok] packet verifies SUCCESS in a fresh workspace
  [ok] packet carries no private material or local paths
  [ok] one-byte tampering is detected
  [ok] v8 journal untouched by v9 writes
  [ok] relative change rounding rule stated
  not run here: the repository test suite (developers: python -m pytest tests/test_v9_*.py), the browser journeys, live provider connectors (none exist in 9.0), real sources
[brief selftest] PASS — 17/17 checks
```

The packaged quick start is printed by `yuclaw workbench brief guide` (`--lang fr` for French).

### Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | the operation ran and the result is negative: `verify` MISMATCH, `show --strict` with open items or non-supported statements, `E_OP_CONFLICT` |
| 2 | a contract refusal or usage error (`refused: …`); nothing was written |
| 3 | environment or store state unsupported: `verify` UNSUPPORTED, `E_TORN_TAIL`, `E_WORKSPACE_MISMATCH`, `E_NO_SIDECAR` |

---

## 3. The complete fictional example

### 3.1 On the command line

```
yuclaw workbench brief example --workspace ~/yuclaw-workspaces/research
```

`example` creates the workspace if needed, loads the fictional fixture `001_base` (idempotent) and composes one brief from
all three templates. The output lists every statement with its role and its five independent answers:

```
claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
brf-4625e1016814 B1 (en) — Research brief — ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
status COMPLETE · Evidence bound · snapshot f618f796af628a55… at v8 tip 5b841dfc6e49…
9 of 10 identified statements have mapped evidence; extraction completeness is not established.

[ 1] attributed_source_statement  SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     Fictional Example Corp (ZZFX) stated revenue guidance for FY2026 (GAAP) of USD 110–120 million in its 8-K (fictional) filed 2026-02-10 (accession 0000000000-26-000001).
[ 2] attributed_source_statement  SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     In its 8-K (fictional) filed 2026-05-12 (accession 0000000000-26-000002), the company revised that guidance to USD 105–115 million.
[ 3] computed_statement           SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     The midpoint moved from USD 115 million to USD 110 million: a change of -5 million (-4.35%, computed as -5 / 115 × 100 and rounded half-even to two decimals, so approximately).
[ 4] computed_statement           SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     The later disclosed actual of USD 112 million (10-K (fictional) filed 2027-02-09, accession 0000000000-26-000003) lies inside the original range and inside the revised range.
[ 5] analyst_interpretation       SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     That the actual falls inside both ranges — or that they agree in any way — does not by itself establish improved forecast accuracy, forecasting skill or causation.
[ 6] computed_statement           SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     Compared with the original range, the revised range is lowered: the low end moved by -5 million and the high end by -5 million; the width went from 10 to 10 million.
[ 7] computed_statement           SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     The two ranges overlap between USD 110–115 million.
[ 8] direct_quotation             SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     The original filing states: “expects full-year 2026 revenue of $110 million to $120 million”
[ 9] unresolved_claim             UNRESOLVED   bytes VERIFIED No later information recorded · Watermark check not requested
     Management cut guidance because demand collapsed.
[10] analyst_interpretation       NOT_ASSESSED bytes VERIFIED No later information recorded · Watermark check not requested
     Evidence that would support or refute it: a source passage in which management attributes the revision to demand, registered with its availability time.

open review items: 0 · receipts: 1 · reports: 0 · versions: ['B1']
These five answers are independent. None is a confidence percentage, and no overall score is computed from them.
```

Fictional numbers, read as the brief states them: original guidance USD 110–120 million, revised 105–115 million, later
actual 112 million. The midpoint moves from 115 to 110 million: −5 million, approximately −4.35 % (−5 / 115 × 100, rounded
half-even to two decimals; the exact fraction −5 000 000 / 115 000 000 is kept in the record). The actual lies inside both
ranges — which, the brief says itself, does not establish improved forecast accuracy. The causal sentence "Management cut
guidance because demand collapsed." stays **UNRESOLVED**: no evidence for it exists in the workspace, and no citation,
signature or detector result can make it supported.

```
yuclaw workbench brief list --workspace ~/yuclaw-workspaces/research
```
```
brf-4625e1016814  B1   en     complete  Research brief — ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base  claims ['ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base']
```

Your brief id will differ; copy it from `list` into the commands below.

### 3.2 In the browser

The v9 pages are served by the v8 workbench server, on the loopback interface only:

```
yuclaw workbench serve --workspace ~/yuclaw-workspaces/research
```

Then open **http://127.0.0.1:8765/brief** (the port is 8765 unless you pass `--port`). Routes:

| Route | What it shows |
|---|---|
| `/brief` | the briefs of the workspace, a form to create a brief from templates over a frozen claim, a form to import a draft |
| `/brief/<brief id>` | one brief: text, statements with their five dimensions, review items, provenance records, versions, and the forms edit / translate / link / resolve / import a record / export |
| `/brief/<brief id>?s=N` | the same page with the **sentence inspector** open on statement N (four areas, section 4) |
| `/brief/<brief id>/html` | the readable static HTML brief as a download (no script) |
| `/brief/verify` | upload a packet built elsewhere and read the per-check outcomes; nothing is imported |
| `/brief/trust` | this workspace's trust roots for signed provenance records: enroll, revoke |
| `…?lang=fr` | French explanations on any of these pages; identifiers, commands and status words stay as they are |

The pages use the v8 server's protections (loopback binding, CSRF token, Origin check, session). Until principals are
configured, the single owner of the workspace may write; once they are, writing needs one of the capabilities `admin`,
`review` or `submit`, and enrolling or revoking a trust root needs `admin`. The surrounding v8 pages keep their English labels.

---

## 4. Inspecting one sentence: four areas, five dimensions

```
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --statement 3
```

```
Statement 3 [435:612] role computed_statement
  The midpoint moved from USD 115 million to USD 110 million: a change of -5 million (-4.35%, computed as -5 / 115 × 100 and rounded half-even to two decimals, so approximately).

1. Sources and calculations
   support: SUPPORTED — Supported by a deterministic check (exact quotation or registered arithmetic).
   method: registered_arithmetic/1 · assessor: v9.brief.templates/1
   limits: exact midpoints and difference; the percentage is rounded under the stated rule; agreement of the two ranges is not evidence of accuracy
   claim: {'claim_digest': 'ab1eb46f…', 'claim_id': 'ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base', 'version_id': 'R1'}
   evidence: claim_version ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base#V1 0db93c38ae7130d7
   evidence: claim_version ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base#R1 ab1eb46f659be7ce
   evidence: calculation guidance_change 0a85639ba3b482f7
   calculation: guidance_change — midpoint = (low + high) / 2 (exact); absolute_change = midpoint_revised - midpoint_original (exact); relative_change = absolute_change / midpoint_original * 100
     inputs: {"original_high": 120000000, "original_low": 110000000, "revised_high": 115000000, "revised_low": 105000000}
     midpoint_original: 115000000
     midpoint_revised: 110000000
     absolute_change: -5000000
     relative_change: {"approximate": true, "denominator": 115000000, "formula": "(new - old) / old * 100", "numerator": -5000000, "rounding": {"applies_to": "relative change in percent only; every amount, midpoint and difference is exact", "decimals": 2, "rule": "ROUND_HALF_EVEN"}, "value_percent": "-4.35"}
   recomputed now: {'outcome': 'VERIFIED', 'detail': None}
   protected slots: midpoint_original='USD 115 million', midpoint_revised='USD 110 million', absolute_change='-5', relative_change='-4.35%'

2. How the text was produced
   transform: template_render · implementation: v9.brief.templates/1 · renderer: v9.brief.templates/1 · template: guidance_change+numerical_comparison+unresolved_interpretation · deterministic: True
   receipts: ['1a91e646c83d499f…']
   explicit unknowns: {}

3. Changes
   No later information recorded · snapshot f618f796af628a55… · review items: []

4. Checks
   byte integrity: {'status': 'VERIFIED', 'recorded': '8a317102e2128261…', 'observed': '8a317102e2128261…'}
   issuer trust: no signed record on these bytes
   detector: {'reports': [], 'label': 'Watermark check not requested'}
   These five answers are independent. None is a confidence percentage, and no overall score is computed from them.
```

`[435:612]` are the **UTF-8 byte offsets** of the sentence inside the brief's text (half-open: byte 435 included, 612
excluded). `--json` prints the same view as data; the browser inspector (`?s=3`) shows the same four areas.

### The four areas

| Area | Contents |
|---|---|
| **1 Sources and calculations** | support status, method, assessor and limits; the claim version; each evidence item (source excerpt, claim version, outcome, calculation) with its digest; the registered calculation with its inputs, formula, rounding rule and *recomputed now* result; the protected slots |
| **2 How the text was produced** | the transform (`template_render` / `import` / `edit` / `translate`), its implementation, whether it was deterministic, the generation receipts bound to these bytes, and the **explicit unknowns** (every quantity a receipt could not expose, with the reason) |
| **3 Changes** | whether later information exists in the v8 workspace since the snapshot, and the review items on this statement's recorded dependencies |
| **4 Checks** | byte integrity (recorded vs observed digest), issuer trust for signed records on these bytes, detector reports covering these bytes |

### The five independent dimensions

Every statement carries five answers, kept apart on every surface (CLI, JSON, browser, exported HTML). **There is no overall
score, and none of the five is a confidence percentage.**

| Dimension | Words you will see | What it answers | What it does not answer |
|---|---|---|---|
| **Byte integrity** | `VERIFIED` · `FAILED` | do the sentence's bytes still hash to the recorded digest in this exact text view? | anything about truth or authorship |
| **Recorded origin** | `template_render` · `import` · `edit` · `translate`, with explicit unknowns | how the text was produced, with which known settings, and what is unknown | whether the text is correct |
| **Issuer trust** | signature `VALID` / `INVALID`; trust `TRUSTED` / `UNKNOWN_SIGNER` / `REVOKED_ROOT`; binding `BOUND` / `MISMATCH` (signed records only) | who signed a record *about these bytes*, under this workspace's policy | whether the statement is supported |
| **Substantive support** | `SUPPORTED` · `ATTRIBUTED` · `UNRESOLVED` · `CONTRADICTED` · `NOT_ASSESSED` · `INVALIDATED` | whether a deterministic check or an assessor's assertion supports the statement, by which method and with which limits | authorship, authenticity of the source |
| **Time scope** | "No later information recorded" · "Later information exists" (+ review items) | whether the v8 workspace recorded later information on this statement's dependencies | whether the later information changes the conclusion |

A sixth, separate answer — the **detector report** — says whether a watermark/detector check was requested, unavailable or
completed over these exact bytes (section 9). A positive detector signal or a valid signature never changes substantive
support; a correct calculation never authenticates a provider.

---

## 5. Imported drafts and span links

A draft you wrote yourself, or produced with an AI assistant, is imported as a new brief. Its sentences are identified by a
plain sentence segmenter and start **NOT_ASSESSED** until you link them.

```
printf 'Fictional Example Corp (ZZFX) guided to USD 110–120 million. Demand was weak in Q2 2026. The filing says “expects full-year 2026 revenue of $110 million to $120 million”. The filing says “expects revenue of $130 million”.\n' > ~/yuclaw-workspaces/draft-2.txt
yuclaw workbench brief import --workspace ~/yuclaw-workspaces/research --file ~/yuclaw-workspaces/draft-2.txt --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --provenance "hand-written draft for the guide (fictional)"
```
```
[brief] brf-fbc613defe63 B1 imported — 4 statements identified (v9.brief.compose/1 sentence segmentation (terminal punctuation and blank lines); not a claim extractor: it finds sentences, not claims, and misses nothing only in the sense that every byte belongs to some segment); link them with `link`
```

`--claim` names the frozen v8 claim(s) the draft is about (repeatable); `--provenance` is your statement, in words, of
where the text came from; `--receipt` may attach a `GenerationReceipt/1` JSON describing how the draft was produced
(section 9). The text is stored as data and never executed.

### Computing byte offsets

Spans are addressed by **UTF-8 byte offsets, half-open** (`start` included, `end` excluded), never by an editor's character
offsets. An en dash (–) or a curly quote (“) is 3 bytes; `é` is 2. Compute offsets from the exact text:

```
python3 -c "
text = open('$HOME/yuclaw-workspaces/draft-2.txt', encoding='utf-8').read()
for sentence in ['Fictional Example Corp (ZZFX) guided to USD 110–120 million.', 'Demand was weak in Q2 2026.', 'The filing says “expects full-year 2026 revenue of \$110 million to \$120 million”.', 'The filing says “expects revenue of \$130 million”.']:
    i = text.index(sentence); j = i + len(sentence)
    start = len(text[:i].encode('utf-8')); end = len(text[:j].encode('utf-8'))
    print(start, end, 'chars', i, j)
"
```
```
0 62 chars 0 60
63 90 chars 61 88
91 176 chars 89 170
177 231 chars 171 221
```

The first sentence is 60 characters but 62 bytes (the en dash). `show --json` gives each identified statement's `start` and
`end` directly, and `text_view.view_sha256` is the digest of the whole text.

### Linking

```
yuclaw workbench brief link --workspace ~/yuclaw-workspaces/research --brief brf-fbc613defe63 --start 0 --end 62 --role attributed_source_statement --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --claim-version V1 --note "restates the original guidance"
yuclaw workbench brief link --workspace ~/yuclaw-workspaces/research --brief brf-fbc613defe63 --start 63 --end 90 --role unresolved_claim --note "no source passage about demand is registered"
yuclaw workbench brief link --workspace ~/yuclaw-workspaces/research --brief brf-fbc613defe63 --start 91 --end 176 --role direct_quotation --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --claim-version V1
yuclaw workbench brief link --workspace ~/yuclaw-workspaces/research --brief brf-fbc613defe63 --start 177 --end 231 --role direct_quotation --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --claim-version V1
```
```
[brief] span 0..62 → role attributed_source_statement, support ATTRIBUTED (assessor_assertion/1); the operator 'host-operator(cli)' links this sentence to ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base#V1; this is an attributed suggestion, not a deterministic check. restates the original guidance
[brief] span 63..90 → role unresolved_claim, support UNRESOLVED (none); marked unresolved by the operator: no source passage about demand is registered
[brief] span 91..176 → role direct_quotation, support SUPPORTED (exact_quotation_match/1); verbatim substring of registered excerpt 0000000000-26-000001:45b937ee0c849642 (45b937ee0c849642…); a quotation binds bytes, it does not authenticate the publisher
[brief] span 177..231 → role direct_quotation, support UNRESOLVED (exact_quotation_match/1); the quoted bytes are not a verbatim substring of any registered excerpt of the linked claim
```

`show` now reads `4 of 4 identified statements have mapped evidence` with the statuses `ATTRIBUTED`, `UNRESOLVED`,
`SUPPORTED`, `UNRESOLVED`. A later `link` on the same byte range replaces the earlier one (the newest link for a range wins);
the earlier link stays in the record.

### Roles

A role describes the statement's **function**; it does not establish correctness.

| Role | Use it for | Support it can reach |
|---|---|---|
| `direct_quotation` | text between quotation marks (“ ”, « », ") copied from a registered source | `SUPPORTED` when the quoted bytes are a verbatim substring of a registered excerpt of the linked claim's sources (`exact_quotation_match/1`); otherwise `UNRESOLVED` |
| `computed_statement` | a number the brief derives (midpoint, change, containment, comparison) | `SUPPORTED` by a registered calculation (`registered_arithmetic/1`) — template sentences only; your own link of free prose is `ATTRIBUTED` |
| `attributed_source_statement` | a restatement of what a source says | templates: `SUPPORTED` (`typed_slot_render/1`); your link: `ATTRIBUTED` |
| `analyst_interpretation` | your reading of the facts | `ATTRIBUTED` when linked to a claim; `NOT_ASSESSED` without a claim |
| `generated_commentary` | sentences of an imported or edited draft not yet classified (the default) | `NOT_ASSESSED` until linked |
| `unresolved_claim` | a claim for which no evidence is recorded (for example a causal statement) | `UNRESOLVED` by definition (the contract refuses `SUPPORTED` for this role) |

### Support words

| Status | Meaning | How it arises |
|---|---|---|
| `SUPPORTED` | supported by a deterministic check | exact quotation match, registered arithmetic, typed template rendering, or a method statement of the calculator — never by an assessor's assertion alone |
| `ATTRIBUTED` | an assessor (you) asserted the link; not reproduced deterministically | `link` of free prose to a claim version |
| `UNRESOLVED` | no evidence supporting the statement is recorded | the `unresolved_claim` role; a quotation not found in any registered excerpt |
| `CONTRADICTED` | contradicted by recorded evidence | a registered calculation that no longer recomputes (the reducer turns `SUPPORTED` into `CONTRADICTED`) |
| `NOT_ASSESSED` | nothing has been decided about this sentence | every sentence of an imported draft, a new sentence after an edit, every sentence of an entered translation |
| `INVALIDATED` | the text or a protected fact changed after the check; earlier support does not carry over | an edit that changed a protected slot; a byte-integrity failure |

---

## 6. Edits and translations

### Edit

Every save is a new version with a parent; the original is never overwritten.

```
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --json | python3 -c "import sys,json;print(json.load(sys.stdin)['text'])" > ~/yuclaw-workspaces/draft.txt
```

For the guide, `draft.txt` was changed in two places: `USD 110–120 million` became `CAD 110–120 million` in sentence 1,
and the sentence "The company also opened a new office in Montréal." was added after the causal sentence. Then:

```
yuclaw workbench brief edit --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --file ~/yuclaw-workspaces/draft.txt --provenance "edited by the operator for the guide (fictional)"
```
```
[brief] brf-4625e1016814 B2 saved (parent B1 preserved) — mapped 9/10 statements; findings: PROTECTED_FACT_CHANGED: sentence 130..300 of the parent lost protected slot(s) ['range']; its SUPPORTED support does not carry over; PROSE_CONTRADICTS_PROTECTED_FACT: the text names currency CAD; the claim's currency is USD. scan scope: ISO-4217 codes among a fixed list, fiscal-period labels FY/Qn/Hn/Mnn + year, and the words GAAP / non-GAAP / IFRS, anywhere in the text; semantic contradictions outside this scope are not detected
```

```
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B2
```
```
brf-4625e1016814 B2 (en) — Research brief — ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
status COMPLETE · Evidence incomplete · snapshot f618f796af628a55… at v8 tip 5b841dfc6e49…
8 of 11 identified statements have mapped evidence; extraction completeness is not established.

[ 1] attributed_source_statement  INVALIDATED  bytes VERIFIED No later information recorded · Watermark check not requested
     Fictional Example Corp (ZZFX) stated revenue guidance for FY2026 (GAAP) of CAD 110–120 million in its 8-K (fictional) filed 2026-02-10 (accession 0000000000-26-000001).
[ 2] attributed_source_statement  SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     In its 8-K (fictional) filed 2026-05-12 (accession 0000000000-26-000002), the company revised that guidance to USD 105–115 million.
…
[ 9] unresolved_claim             UNRESOLVED   bytes VERIFIED No later information recorded · Watermark check not requested
     Management cut guidance because demand collapsed.
[10] generated_commentary         NOT_ASSESSED bytes VERIFIED No later information recorded · Watermark check not requested
     The company also opened a new office in Montréal.
[11] analyst_interpretation       NOT_ASSESSED bytes VERIFIED No later information recorded · Watermark check not requested
     Evidence that would support or refute it: …

open review items: 2 · receipts: 1 · reports: 0 · versions: ['B1', 'B2']
```

What happened, mechanically:

- **Exact-bytes mapping.** A parent sentence is MAPPED to the child only when its exact bytes occur exactly once in the new
  text; nine of ten did, and they keep their support. A mapped sentence keeps its support only if every **protected slot**
  (currency, amount or range, period, basis, accession, percent, quotation) still reads the same.
- **Protected fact changed.** Sentence 1 lost the protected slot `range` (`USD 110–120 million`). The child sentence that still
  carries the remaining protected values inherits the link as **INVALIDATED** — never the support — and a review item
  `PROTECTED_FACT_CHANGED` names what changed. Statement 1 of B2 reads `support: INVALIDATED … limits: protected slot(s)
  ['range'] changed in this edit; the parent's SUPPORTED does not carry over; re-link after checking the typed fact`.
- **Prose scan.** Free prose naming a currency, fiscal period or accounting basis different from the claim's produces
  `PROSE_CONTRADICTS_PROTECTED_FACT`. The scan scope is stated in the finding itself: ISO-4217 codes from a fixed list,
  period labels of the forms FY/Qn/Hn/Mnn + year, and the words GAAP / non-GAAP / IFRS, anywhere in the text. **No semantic
  contradiction outside that scope is detected.**
- **New sentences** ("…office in Montréal.") become `NOT_ASSESSED` statements to link or mark.
- The parent **B1 is untouched**: `show --version B1` still shows 0 open review items on its own findings.

### Review items and dispositions

```
yuclaw workbench brief review --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B2
```
```
OPEN     d3cf2bbd5d1d191d40f7132d PROTECTED_FACT_CHANGED (this version): sentence 130..300 of the parent lost protected slot(s) ['range']; its SUPPORTED support does not carry over
OPEN     773f24297bfe94e7f1ee32cb PROSE_CONTRADICTS_PROTECTED_FACT (this version): the text names currency CAD; the claim's currency is USD. scan scope: …
```

A disposition is recorded with `--resolve <item id> --disposition … --note …`; the disposition must be one of
`REVIEWED_NO_CHANGE`, `REVISED`, `WITHDRAWN_STATEMENT`, `DISPUTED`, and a note is required:

```
yuclaw workbench brief review --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B2 --resolve d3cf2bbd5d1d191d40f7132d --disposition REVIEWED_NO_CHANGE --note "the CAD edit was deliberate for the guide; the statement stays INVALIDATED until re-linked (fictional)"
```
```
resolved d3cf2bbd5d1d191d40f7132d PROTECTED_FACT_CHANGED (this version): …
OPEN     773f24297bfe94e7f1ee32cb PROSE_CONTRADICTS_PROTECTED_FACT (this version): …
```

Resolving an item records your decision; it does not change the statement's support. `show --strict` exits 1 while any
item is open or any statement is not `SUPPORTED`/`ATTRIBUTED` — useful before publishing a version.

### Deterministic translation (template versions)

A template-rendered version can be re-rendered in the other language from the same snapshot, so every typed statement is
bound again. No prose is translated and nothing is sent anywhere.

```
yuclaw workbench brief translate --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B1 --to fr
```
```
[brief] brf-4625e1016814 B3 (fr) saved from B1 — mapping operator_mapped/1; findings: none
```
```
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B3 --lang fr
```
```
brf-4625e1016814 B3 (fr) — Note de recherche — ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
status COMPLETE · Éléments probants liés · snapshot f618f796af628a55… at v8 tip 5b841dfc6e49…
9 des 10 énoncés identifiés ont des éléments probants associés ; l’exhaustivité de l’extraction n’est pas établie.

[ 1] attributed_source_statement  SUPPORTED    bytes VERIFIED Aucune information ultérieure consignée · Vérification du filigrane non demandée
     Fictional Example Corp (ZZFX) a annoncé des prévisions de revenue pour FY2026 (GAAP) de 110–120 millions USD dans son 8-K (fictional) déposé le 2026-02-10 (numéro 0000000000-26-000001).
…
[ 3] computed_statement           SUPPORTED    bytes VERIFIED Aucune information ultérieure consignée · Vérification du filigrane non demandée
     Le point médian est passé de 115 millions USD à 110 millions USD : une variation de −5 millions (−4,35 %, calculée comme −5 / 115 × 100 et arrondie au pair le plus proche à deux décimales, donc approximativement).
…
[ 9] unresolved_claim             UNRESOLVED   bytes VERIFIED Aucune information ultérieure consignée · Vérification du filigrane non demandée
     La direction a abaissé ses prévisions parce que la demande s’est effondrée.
```

The digits are identical in both languages; only presentation differs (decimal comma, a narrow no-break space before %,
the real minus sign). Statement 3 of B3 carries the same registered calculation and `recomputed now: VERIFIED`.

### Entered translation (any version)

```
yuclaw workbench brief translate --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B2 --to fr --file ~/yuclaw-workspaces/traduction.txt --provenance "translation entered by the operator; not certified"
```
```
[brief] brf-4625e1016814 B4 (fr) saved from B2 — mapping none; findings: SPAN_UNMAPPED: 11 parent statement(s) are not bound in the translation; the typed numbers were compared instead; PROSE_CONTRADICTS_PROTECTED_FACT: the text names currency CAD; the claim's currency is USD. …
```

An entered translation is recorded with your stated provenance. Its sentences are all `NOT_ASSESSED` (binding to evidence is
not inherited across languages); the digit sequences of parent and translation are compared (language-independent), and
the protected-fact scan runs on the new text. Nothing is sent to a translation provider, and nothing is certified: the
inspector's area 2 for a translated sentence reads `transform: translate · implementation: operator translate through the
workbench form or CLI · deterministic: False` with the explicit unknowns `provider`, `model`, `settings` ("not exposed: the
text was entered or imported locally…").

---

## 7. Source corrections and dependency review

A brief is composed from a **snapshot** of the v8 claims it depends on (the snapshot digest and the v8 journal tip appear
in every `show`). Later v8 events never change the snapshot; `review` compares the live v8 state with it and lists the
statements whose *recorded dependencies* are affected. Nothing is inferred beyond the recorded links.

For the guide, the availability of the first fictional source was corrected on the v8 side (the workbench's source page,
form "correct availability", records a `SOURCE_AVAILABILITY_CORRECTED` event; see the v8 guide) from 2026-02-10T21:05:00Z
to 2026-02-10T21:30:00Z. Then:

```
yuclaw workbench brief review --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B1
```
```
OPEN     95163986d91f0a893efdd0c3 SOURCE_AVAILABILITY_CORRECTED (source:0000000000-26-000001:45b937ee0c849642): effective availability 2026-02-10T21:05:00Z → 2026-02-10T21:30:00Z (corrections ['AC1'])
```
```
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B1 --statement 1
```
```
3. Changes
   Later information exists · snapshot f618f796af628a55… · review items: ['95163986d91f0a893efdd0c3']
   - SOURCE_AVAILABILITY_CORRECTED (source:0000000000-26-000001:45b937ee0c849642): effective availability 2026-02-10T21:05:00Z → 2026-02-10T21:30:00Z (corrections ['AC1'])
```

Exactly the statements whose evidence cites that source (statements 1 and 8 of B1) now read **Later information exists**;
statement 3, which cites claim versions and a calculation but not that source, still reads "No later information recorded".
The brief's header switches from `Evidence bound` to `Evidence incomplete` while an item is open.

Review reasons you may see: `SOURCE_AVAILABILITY_CORRECTED`, `CLAIM_AMENDED`, `CLAIM_WITHDRAWN`, `OUTCOME_CHANGED` (from the
live v8 state), `SPAN_UNMAPPED`, `PROTECTED_FACT_CHANGED`, `PROSE_CONTRADICTS_PROTECTED_FACT` (from an edit or
translation), `OPERATOR_FLAG`.

**Earlier exports stay valid snapshots.** The packet built before the correction (section 10) still verifies `SUCCESS`
afterwards: it records the research cutoff (snapshot digest and v8 tip) it was built against, and verification checks what
the packet carries, not today's workspace.

---

## 8. Provenance records: what they are, what they are not

Three kinds of record can be imported with `import-record --kind receipt | report | calibration --file <json>`. Each is
validated against its contract, bound to an exact text view (and, for a report, to the exact tested span), and
signature-checked. Section 9 covers signatures; SCHEMA.md lists every field.

### Generation receipts (`GenerationReceipt/1`)

A receipt says how a text was produced: origin, recording method, template or provider and model, settings, digests of the
prompt and of the raw and assembled outputs, and **explicit unknowns** — every quantity the receipt cannot expose must name
why ("not exposed: …"). A template rendering carries its own receipt (`recording_method: template_deterministic`,
`provider: local`). This fictional receipt describes B1 as produced by a provider:

```
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind receipt --file ~/yuclaw-workspaces/receipt.json --label "fictional provider receipt"
```
```
[brief] receipt aa325501a90cf167 imported — origin operator_assertion; signature NONE / trust NOT_EVALUATED / binding NOT_APPLICABLE; bound to {'brief_id': 'brf-4625e1016814', 'version_id': 'B1', 'language': 'en'}
```

The receipt binds through `assembled_output_sha256`, which must equal the `view_sha256` of a brief version in this
workspace; otherwise it is refused (`receipt refused: assembled_output_sha256 0000000000000000… is not a text view of any
brief version here; a receipt binds to the exact assembled bytes`).

### Detector reports (`DetectionReport/1`)

A report keeps three things apart:

| Field | Values | Meaning |
|---|---|---|
| `execution` | `NOT_REQUESTED` · `ACCESS_UNAVAILABLE` · `UNSUPPORTED` · `INSUFFICIENT_INPUT` · `COMPLETED` · `FAILED` | whether the detector ran; every value other than `NOT_REQUESTED` and `COMPLETED` requires a `failure_reason` |
| `signal` | `DETECTED` · `NOT_DETECTED` · `INCONCLUSIVE` | the result — present **only** when execution is `COMPLETED` |
| `calibration` | `APPLICABLE` · `OUT_OF_SCOPE` · `NOT_ESTABLISHED` | what the report claims about calibration; `APPLICABLE` needs a `COMPLETED` execution and a `calibration_ref` |

The four quantities `threshold`, `p_value`, `scored_context_count`, `key_epoch` must be supplied (in `diagnostics` or
`configuration`) or declared unavailable under `unknown` with a reason; they are never inferred from a paper. The report
binds to `view_sha256` plus the exact tested span (`start`, `end`, `span_sha256`); `show --json` gives the view digest and
the statement's offsets, and the span digest is `sha256` of exactly those bytes:

```
python3 -c "
import hashlib, json
view = json.load(open('show_B1.json'))          # saved from: yuclaw workbench brief show … --json
data = view['text'].encode('utf-8')
s = view['statements'][8]                      # statement 9 (1-based): the unresolved causal sentence
print(view['text_view']['view_sha256'] == hashlib.sha256(data).hexdigest())
print(s['start'], s['end'], hashlib.sha256(data[s['start']:s['end']]).hexdigest())
"
```
```
True
1358 1407 5dba767631f8fb11064804c7e711c0d075ca3d2ed3427f34d5447398761d57a2
```

Two fictional reports over that span — one where no detector could be reached, one completed — and one that the contract
refuses (SCHEMA.md shows the full JSON of each):

```
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file ~/yuclaw-workspaces/report_unavailable.json --label "fictional detector record 1"
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file ~/yuclaw-workspaces/report_completed.json --label "fictional detector record 2"
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file ~/yuclaw-workspaces/report_bad.json
```
```
[brief] report 302e9f106f7275bb imported — origin operator_assertion; signature NONE / trust NOT_EVALUATED / binding NOT_APPLICABLE; bound to {'brief_id': 'brf-4625e1016814', 'version_id': 'B1', 'language': 'en'}; execution ACCESS_UNAVAILABLE signal None calibration NOT_ESTABLISHED
[brief] report 77bdd65b2c9af9e2 imported — origin operator_assertion; signature NONE / trust NOT_EVALUATED / binding NOT_APPLICABLE; bound to {'brief_id': 'brf-4625e1016814', 'version_id': 'B1', 'language': 'en'}; execution COMPLETED signal NOT_DETECTED calibration NOT_ESTABLISHED
[brief] refused: detection report cannot be recorded: report.signal: must be absent unless execution is COMPLETED (FAILED cannot become NOT_DETECTED); report.calibration: APPLICABLE is meaningless without a COMPLETED execution; report.calibration: APPLICABLE requires calibration_ref (the CalibrationRecord it rests on)
```

Statement 9 of B1 now lists both reports in area 4; its label becomes `Watermark check unavailable` (the first covering
report decides the label), the completed one is marked `Provider-reported result; not reproduced or calibrated here`, and
its substantive support is still `UNRESOLVED`. A report covers exactly the tested span of one text view; it does not apply
to other bytes, versions or languages.

### Calibration records (`CalibrationRecord/1`)

A calibration record describes a detector's measured error rates: corpus, label provenance, languages, domains, length
strata, test unit, selection rule, split, error-rate plan, confusion counts, interval method, missing strata. A report that
claims `calibration: APPLICABLE` is shown as applicable **only** when the referenced calibration record is present, in
scope (same detector, version, configuration, key scope, and the view's language among the calibrated ones), **and**
issuer-signed by a signer this workspace trusts. An operator-imported calibration assertion stays `NOT_ESTABLISHED`:

```
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind calibration --file ~/yuclaw-workspaces/calibration.json
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file ~/yuclaw-workspaces/report_applicable.json --label "fictional detector record 3 (claims APPLICABLE)"
```
```
[brief] calibration 8fc00981097616d7 imported — origin operator_assertion; signature NONE / trust NOT_EVALUATED / binding NOT_APPLICABLE; bound to workspace
[brief] report 0977b46d62b172e8 imported — … execution COMPLETED signal NOT_DETECTED calibration APPLICABLE
```

and in `show --json`, that report's `calibration` reads:

```
"calibration_claimed": "APPLICABLE",
"calibration": {
 "applicability": "NOT_ESTABLISHED",
 "claimed": "APPLICABLE",
 "calibration_record": "8fc00981097616d7…",
 "reason": "the calibration record is operator_assertion (signature NONE, trust NOT_EVALUATED); an imported assertion is not independently measured calibration"
}
```

### Origin kinds

| `origin` | Meaning | Requirement |
|---|---|---|
| `operator_assertion` | you entered or imported the record; it records what was supplied | none beyond the contract |
| `connector_observed` | a response observed by a configured connector | `recording_method: connector_observed`; **no connector exists in 9.0** — the kind is reserved so a staged connector result can be imported later without a schema change |
| `issuer_signed` | a cryptographically signed statement by an issuer | a valid `signature_envelope` (section 9); otherwise the import is refused |

**A filename, a screenshot, a request id or a timestamp is not a provider signature.** A receipt whose `origin` says
`issuer_signed` without an envelope is refused with exactly that reason:

```
[brief] refused: generation receipt cannot be recorded: receipt.origin: issuer_signed requires a signature_envelope (a filename, screenshot or request id is not a provider signature)
```

### The four "never" statements

They appear on every brief page, in every packet and in the appendix:

- NOT_DETECTED does not prove human authorship.
- A detector score is not the percentage of text written by AI.
- A watermark does not establish identity, ownership, responsibility or factual accuracy.
- A local receipt is not legal compliance and not an independently anchored timestamp.

---

## 9. Signatures and trust roots

A signed record carries a `signature_envelope` (`yuclaw.signed-record/1`): Ed25519 over a domain-separated input that
includes the record type (`brief.generation_receipt`, `brief.detection_report`, `brief.calibration_record`) and the
canonical JSON of the signed body. Four answers are reported separately and never merged:

| Answer | Values | Question |
|---|---|---|
| **signature** | `NONE` · `VALID` · `INVALID` · `UNVERIFIABLE` | do the bytes verify under the key the envelope names? |
| **trust** | `NOT_EVALUATED` · `TRUSTED` · `UNKNOWN_SIGNER` · `REVOKED_ROOT` | is that key a root *this* workspace's administrator enrolled, and not revoked? |
| **binding** | `NOT_APPLICABLE` · `BOUND` · `MISMATCH` | is the body inside the envelope the same record as the one presented with it? |
| **revocation** | part of trust: `REVOKED_ROOT` | was the root revoked here (a revocation shows at once in every view) |

Trust roots are **the receiver's**: there is no trust on first use, and a packet never enrolls its own signer. For the
guide, a fictional Ed25519 key signed a detector report (`origin: issuer_signed`):

```
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file ~/yuclaw-workspaces/report_signed.json --label "signed fictional report"
```
```
[brief] report ba1ab1a47e52f54e imported — origin issuer_signed; signature VALID / trust UNKNOWN_SIGNER / binding BOUND; bound to {'brief_id': 'brf-4625e1016814', 'version_id': 'B1', 'language': 'en'}; execution COMPLETED signal NOT_DETECTED calibration NOT_ESTABLISHED
```

A valid signature from an unknown signer is not a malformed signature; the record is kept with `UNKNOWN_SIGNER`. Enroll the
key (raw 32-byte Ed25519 public key, base64) and the same record reads `TRUSTED`:

```
yuclaw workbench brief trust --workspace ~/yuclaw-workspaces/research enroll --public-key aAEMoJmJ7OrLpSg9IcPmBVJfErPlP2EU+RGdNXcBn2A= --label "fictional detector vendor key" --issuer "Fictional Detector Vendor"
yuclaw workbench brief trust --workspace ~/yuclaw-workspaces/research list
```
```
{
 "key_id": "aa89f0dc1d354af4e81ba4571823001b",
 "kind": "TRUST_ROOT_ENROLLED",
 "duplicate": false
}
{
 "aa89f0dc1d354af4e81ba4571823001b": {
  "public_key": "aAEMoJmJ7OrLpSg9IcPmBVJfErPlP2EU+RGdNXcBn2A=",
  "label": "fictional detector vendor key",
  "revoked": false,
  "enrolled_at": "2026-10-10T04:06:29.208476Z",
  "issuer": "Fictional Detector Vendor"
 }
}
```

Area 4 of statement 9 then shows `'signature': 'VALID', 'trust': 'TRUSTED', 'key_id': 'aa89f0dc…', 'binding': 'BOUND'`. The
evaluation is made under the receiver's *current* roots whenever a view is rendered, so after

```
yuclaw workbench brief trust --workspace ~/yuclaw-workspaces/research revoke --key-id aa89f0dc1d354af4e81ba4571823001b --reason "key retired (fictional)"
```

the same record reads `'trust': 'REVOKED_ROOT'` while its signature stays `VALID` and its binding `BOUND`. A revoked root is
never revived (`refused: key aa89f0dc… is already enrolled (a revoked root is never revived; enroll a new key)`).

A record edited after signing is refused — the signature is valid for the body inside the envelope, but that body is not
the record presented:

```
[brief] refused: report refused: the signature verifies for the body inside the envelope, but that body differs from the record presented with it (payload mismatch: a valid signature on different bytes)
```

A trusted signer may still make an unsupported financial claim: nothing in this section changes **substantive support**.
Statement 9 stays `UNRESOLVED` with a `TRUSTED` signed report on its bytes.

---

## 10. Exports and verification

```
yuclaw workbench brief export --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B1
```
```
[brief] packet bpk-a3ff4d970a5e16c3 → ~/yuclaw-workspaces/research/exports/bpk-a3ff4d970a5e16c3.zip (39038 bytes, sha256 f7698355281d6fce…); members: brief.html, brief.json, records.json, snapshot.json, appendix.md, text/, VERIFY.md
```

### Packet members

| Member | Contents |
|---|---|
| `BRIEF_MANIFEST.json` | format `yuclaw.brief-packet/1`, packet id, brief and version, language, software identities, snapshot digest, research cutoff (v8 tip, snapshot digest, built-at), the file list with digests and sizes, the content digest, the omitted components, the limitations |
| `VERIFY.md` | how to verify, the file table, omitted components, limitations |
| `brief.html` | the readable brief: static HTML with a Content-Security-Policy meta tag and **no script** |
| `brief.json` | the reducer view of the exported version with private fields removed |
| `records.json` | every version with its spans, transform and receipt; imported receipts, reports and calibrations; review resolutions; the author's trust-root labels; measurements; the research cutoff |
| `snapshot.json` | the rights-filtered evidence snapshot |
| `text/<view_sha256>.txt` | the exact text bytes of **every** version of the brief (four members in the example: B1–B4) |
| `appendix.md` | the methods and limitations appendix generated from the records |

**Rights filtering.** Source excerpts travel only for the rights classes `FICTIONAL`, `SEC_PUBLIC_FILING` and
`OPERATOR_OWN_TEXT`; for other classes the digest travels and the excerpt is withheld, which makes the checks over it
`NOT_RECOMPUTABLE`, never a failure. Prompts and raw provider responses are never in a record (only their digests);
retained raw bytes stay in the private vault. API keys, signing secrets and workspace paths never travel. The manifest's
`omitted` list names every withheld component and its effect (empty in the fictional example).

### Verifying in a fresh workspace

```
yuclaw workbench brief verify ~/yuclaw-workspaces/research/exports/bpk-a3ff4d970a5e16c3.zip --workspace ~/yuclaw-workspaces/fresh
```
```
[brief verify] SUCCESS — every recomputable binding and calculation reproduced; non-recomputable and report-only components are listed, not assumed; nothing here establishes truth, authorship or approval
  zip sha256 f7698355281d6fce9744adfee0d2d510563b3ced3057482edb33c010a54c67ea
  outcomes {'VERIFIED': 49, 'FAILED': 0, 'NOT_RECOMPUTABLE': 0, 'REPORT_ONLY': 5, 'UNSUPPORTED': 0, 'NOT_APPLICABLE': 6}
  summary {'versions': 4, 'spans': 46, 'calculations': 12, 'reports': 5, 'omitted': []}
```

`--workspace` names the **receiving** workspace: its trust roots judge the packet's signatures, and a `PACKET_VERIFIED`
record is written there (`status --workspace ~/yuclaw-workspaces/fresh` shows it; `briefs: []` — verification installs no
brief, claim, root or policy). Without `--workspace`, the checks run the same way and trust is `NOT_EVALUATED`. `--json`
lists every check; the browser page `/brief/verify` shows the same table.

### Check outcomes

| Outcome | Meaning |
|---|---|
| `VERIFIED` | recomputed from the packet's material and reproduced: member digests and lengths, the content digest, canonical JSON form, the snapshot digest, every text member's digest, every span binding, every registered calculation, each quotation against its excerpt, each version's parent link and receipt binding, each report's span binding, each signature, the measurements' internal consistency, the HTML's safety |
| `FAILED` | did not reproduce; the first failure is named as `first_discrepancy` and the result is `MISMATCH` |
| `NOT_RECOMPUTABLE` | an input was withheld by rights (excerpt, prompt); listed, not assumed, not a failure |
| `REPORT_ONLY` | a detector result cannot be rerun here; recorded as reported |
| `UNSUPPORTED` | a calculation kind this verifier does not know |
| `NOT_APPLICABLE` | an unsigned record (operator assertion) has no signature to check; a `pending` calculation has no arithmetic |

**What verification establishes:** that the packet's bytes are what its manifest says, that every statement's span still
hashes to its recorded digest in the packed text, that every registered calculation recomputes from its typed inputs, that
each quotation is a substring of its packed excerpt, and how each signature stands under the receiver's roots.
**What it does not establish:** source authenticity, factual truth, human authorship, independent review, legal compliance
or publication approval. A manifest hash or a badge never substitutes for the per-check outcomes.

### Negative results

A packet with one altered byte in a text member:

```
[brief verify] MISMATCH — byte mismatch at text/1739c5a93a813faf….txt
  outcomes {'VERIFIED': 11, 'FAILED': 1, …}
```

A file that is not a packet, and a v8 export (which has its own verifier):

```
[brief verify] UNSUPPORTED — refused: not a zip archive
[brief verify] UNSUPPORTED — this is a v8 export (EXPORT_MANIFEST.json present, no BRIEF_MANIFEST.json); verify it with the v8 verifier (`yuclaw workbench verify-export`), which stays unchanged — this reader never reinterprets it
```

Conversely `yuclaw workbench verify-export` on a v9 packet answers `MISMATCH — incomplete packet: missing ['EXPORT_MANIFEST.json']`:
neither verifier reinterprets the other's format.

---

## 11. What is measured, asserted, independently checked, or unavailable

| | Examples in this guide | Where it is stated |
|---|---|---|
| **Measured by the software** | byte digests of every view and span; registered arithmetic recomputed from typed inputs (midpoints 115 and 110 million, −5 million, −4.35 %); exact quotation matching; whether a sentence's bytes occur once in an edited text; operation counts and durations | area 1 and 4; `recomputed now`; `measure` |
| **Asserted by a person or an imported record** | your `--provenance` text; an `ATTRIBUTED` link; everything in an `operator_assertion` receipt, report or calibration record; a provider's detector result (`Provider-reported result; not reproduced or calibrated here`) | area 2; the record's `origin` |
| **Independently checked** | a signature under a root this workspace enrolled (`VALID` / `TRUSTED` / `BOUND`); a calibration record's scope and authentication | area 4; `trust list` |
| **Unavailable, and said so** | the explicit unknowns of a receipt or report ("not exposed: …"); `ACCESS_UNAVAILABLE` with its failure reason; `NOT_RECOMPUTABLE` for a withheld excerpt; `REPORT_ONLY` for a detector result; the "extraction completeness is not established" sentence on every brief | the record itself; `verify`; the coverage sentence |

Operation measurements:

```
yuclaw workbench brief measure --workspace ~/yuclaw-workspaces/research
```
```
operations 24 · attempts 24 · retries 0 · outcomes {'COMMITTED': 21, 'REFUSED': 3} · durations {'n': 24, 'sum_ms': 402, 'median_ms': 15, 'max_ms': 46} · missing {'corrupt_lines': 0, 'missing_duration': 0}
per task: { "create_brief": {…}, "edit_brief": {…}, "export_packet": {…}, … }
definitions: {
 "operation": "one logical operation = one op_id; counted once however many times it was attempted",
 "attempt": "one measured run of an operation (a line in v9/operations.jsonl); retries are additional attempts of the same operation",
 "retries": "attempts − operations, over operations with ≥ 1 attempt",
 "outcome": "per attempt: COMMITTED | DUPLICATE | CONFLICT | REFUSED | FAILED | READ — …",
 "elapsed_ms": "wall-clock milliseconds of the software attempt, from entering the operation to leaving it; not labour time, not cognitive effort",
 "eligible_denominator": "all attempts recorded by this workspace's v9 surfaces since measurement began; nothing earlier is reconstructed",
 "exclusions": "v8 workbench operations (recorded in the v8 journal, not measured here); operations of other workspaces",
 "missingness": "an attempt whose line is corrupt or lacks finished_at is listed under missing, not estimated"
}
```

Durations measure the program, not a person's labour or cognitive effort. Refused and failed attempts stay in the counts.
The same aggregate travels in every packet (`records.json` → `measurements`) and in the appendix.

---

## 12. Troubleshooting

Every word below is printed by the software; the exit code is in brackets.

| You see | Meaning | What to do |
|---|---|---|
| `[brief] refused: …` [2] | a contract refusal; **nothing was written**. Examples: `span: start offset 19 is inside a multi-byte UTF-8 sequence`; `span: offsets 1500..1700 outside the view of 1560 bytes`; `span: half-open range needs start < end (got 10..5)`; `sections must be a non-empty subset of […]`; `disposition must be REVIEWED_NO_CHANGE, REVISED, WITHDRAWN_STATEMENT or DISPUTED`; `detection report cannot be recorded: …` | fix the named field or offset (section 5 for byte offsets) and run again |
| `E_OP_CONFLICT: op_id '…' was already used for a different operation; a retry must repeat the same content` [1] | the same `--op-id` was reused with different content | a retry must repeat the same content exactly (it is then answered by the existing record: `DUPLICATE`); otherwise use a new operation id |
| `E_TORN_TAIL: the v9 sidecar has a torn tail; run \`brief recover\` before writing (nothing durable is lost)` [3] | an interrupted write left bytes without a terminating newline; `status` shows `"integrity": "TORN_TAIL"` and reads still work | `yuclaw workbench brief recover --workspace …` preserves the bytes in `v9/brief.jsonl.torn.<digest>` and appends a `RECOVERY` record; a second `recover` answers `"recovered": false, "reason": "no torn tail"` |
| `INCOMPLETE` on a version (`list`, `show`, browser) | the version's prepared objects (text, snapshot) are missing from the vault | the version is never shown or exported as complete; `export` refuses it (`this version is INCOMPLETE (prepared objects missing); an incomplete brief is never exported as complete`); recreate the version from its parent |
| `orphans` lists objects | prepared vault objects that no record commits (an operation died between preparing bytes and committing its record) | listing deletes nothing; `--remove` deletes **only** those, re-checked under the lock (`"removed": […], "kept_referenced_or_unknown": []`) |
| `E_WORKSPACE_MISMATCH: sidecar belongs to workspace ws-… but this is ws-… (a sidecar is never read against another workspace's journal)` [3] | a `v9/` folder was copied into a different workspace | put the sidecar back beside its own `workspace.json`; never mix folders |
| `E_NO_SIDECAR: this workspace has no v9 sidecar yet (nothing v9 was recorded here)` [3] | `status`, `recover`, `orphans` or `measure` on a workspace where v9 never wrote | nothing to repair; `example`, `create` or `import` creates the sidecar |
| `E_MISSING: store does not exist` [2] | the `--workspace` path is not a workspace at all | check the path |
| `[brief verify] UNSUPPORTED — …` [3] | not a v9 packet this verifier understands: `refused: not a zip archive`, `this is a v8 export (EXPORT_MANIFEST.json present …)`, an unknown format | use the right verifier (`yuclaw workbench verify-export` for a v8 export); nothing was reinterpreted |
| `[brief verify] MISMATCH — <first discrepancy>` [1] | at least one binding or calculation did not reproduce; the first is named (`byte mismatch at text/….txt`, `incomplete packet: missing …`, `version B2: span 0..5 binding failed`, …) | the packet is not the one that was built, or was altered; obtain it again |
| `show --strict` exits 1 | review items are open or a statement is not `SUPPORTED`/`ATTRIBUTED` | resolve or revise, then run again |
| a browser form answers `E_SIGN_IN` / `E_FORBIDDEN` | principals are configured and your session lacks `admin`, `review` or `submit` (trust roots need `admin`) | sign in with a principal that has the capability |

### Reference: the command family

From `yuclaw workbench brief --help`:

```
example        load the fictional fixture (idempotent) and compose the acceptance brief from all three templates
create         compose a brief from deterministic templates over one frozen claim
import         import an AI-assisted or hand-written draft as a new brief (sentences become unassessed statements to link)
list           briefs of this workspace
show           the brief and its statements (the reducer view); --statement N opens the inspector's four areas
edit           save edited text as a new version (parent preserved; spans re-mapped; protected facts validated)
translate      add a translation: deterministic re-render for a template version, or --file with an entered translation
link           link a byte span to a claim version and role (manual span selection / link correction)
review         review items of a brief (live dependency review + transform findings); --resolve records a disposition
import-record  import a generation receipt, detector report or calibration record (validated, bound, signature-checked)
trust          this workspace's trust roots for signed provenance records: enroll | revoke | list
export         build the readable HTML brief, JSON records and the verification packet (zip)
verify         verify a brief packet offline (exit 0 SUCCESS / 1 MISMATCH / 3 UNSUPPORTED); --workspace records the verification in that fresh workspace
measure        operation measurements with their definitions
status         sidecar status (integrity, briefs, v8 binding)
recover        recover a torn sidecar tail (preserves the bytes; records a RECOVERY record)
orphans        list prepared vault objects that no record commits; --remove deletes only those
schema         the v9 record contracts and vocabularies (developer reference)
selftest       bounded self-check from the installed package in a temporary fictional workspace
guide          print the packaged v9 quick start (--lang fr for French)
```

Every write accepts `--actor` (an attribution label recorded with the write — not authentication) and `--op-id` (a retry
with the same id and content is idempotent; the default is a fresh `cli:<24 hex>` id). `create` takes `--sections`, a comma
list of `guidance_change`, `numerical_comparison`, `unresolved_interpretation`:

```
yuclaw workbench brief create --workspace ~/yuclaw-workspaces/research --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --sections guidance_change --lang fr
```
```
[brief] brf-8e4f44bfb327 B1 created — 1194 bytes, 5 statements
```

Developer references: [SCHEMA.md](SCHEMA.md) (contracts, vocabularies, byte semantics, packet manifest) and
[MIGRATION.md](MIGRATION.md) (what v9 creates in a workspace, what it never touches, recovery).
