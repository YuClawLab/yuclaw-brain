# YUCLAW v9 — research briefs with traceable AI assistance: quick start

Research and education only. Not investment advice.
Mission: Make financial AI accountable to evidence. Vision: Become the Science Trust Layer for Financial AI.

A **brief** is a short piece of financial research text whose individual sentences can be inspected: which exact source
passage, which frozen v8 claim version and which registered calculation each one rests on, how the text was produced,
what changed since, and which checks could or could not be run. Everything runs locally beside the v8 workbench. No API
key, no model download and no hosted service is needed for the complete journey below.

## 1. Install (same package as the v8 workbench)

```
python3 -m venv ~/yuclaw-venv && source ~/yuclaw-venv/bin/activate
python -m pip install yuclaw
yuclaw workbench brief --help
yuclaw workbench brief selftest          # checks this installation in a temporary fictional workspace
```

Windows PowerShell: use `& "$HOME\yuclaw-venv\Scripts\python.exe" -m v9.brief …` for every command below
(`python -m v9.brief` and `yuclaw workbench brief` are the same program).

## 2. The complete fictional example in one command

```
yuclaw workbench brief example --workspace ~/yuclaw-workspaces/research
```

This loads the packaged fictional fixture `001_base` (issuer "Fictional Example Corp", original guidance USD 110–120 million,
revised 105–115 million, later actual 112 million — synthetic data, never market data) and composes a brief from the three
deterministic templates. The output lists every statement with its role and its five independent answers:

| Answer | Words you will see |
|---|---|
| Byte integrity | VERIFIED · FAILED |
| Recorded origin | template_render · import · edit · translate, with explicit unknowns |
| Issuer trust (signed records only) | VALID / INVALID signature · TRUSTED / UNKNOWN_SIGNER / REVOKED_ROOT |
| Substantive support | SUPPORTED · ATTRIBUTED · UNRESOLVED · CONTRADICTED · NOT_ASSESSED · INVALIDATED |
| Time scope | "No later information recorded" · "Later information exists" (+ review items) |

The midpoint moves from USD 115 million to USD 110 million: −5 million, approximately −4.35 % (−5 / 115 × 100, rounded
half-even to two decimals; the exact fraction is kept). The actual lies inside both ranges — which the brief says does
not establish improved forecast accuracy. The sentence "Management cut guidance because demand collapsed." stays
**UNRESOLVED**: no evidence for that causal statement exists in the workspace, and no citation, signature or detector
result can make it supported.

## 3. Inspect one sentence

```
yuclaw workbench brief list --workspace ~/yuclaw-workspaces/research
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-… --statement 3
```

The inspector has four areas: **1 Sources and calculations** (excerpt, locator, dates, scope, formula, inputs, rounding,
recomputed now), **2 How the text was produced** (template / import / edit / translation, known settings, explicit
unknowns), **3 Changes** (parent versions, review items on this statement's dependencies), **4 Checks** (byte binding,
signatures and issuer trust, detector report scope). `--json` prints the same view; the browser page shows the same.

## 4. Edit, translate, review

```
yuclaw workbench brief show --workspace … --brief brf-… --json | python3 -c "import sys,json;print(json.load(sys.stdin)['text'])" > draft.txt
# edit draft.txt, then:
yuclaw workbench brief edit --workspace … --brief brf-… --file draft.txt
yuclaw workbench brief translate --workspace … --brief brf-… --version B1 --to fr        # deterministic re-render of a template version
yuclaw workbench brief translate --workspace … --brief brf-… --to fr --file traduction.txt  # an entered translation (its provenance is recorded)
yuclaw workbench brief review --workspace … --brief brf-…
```

Every save is a new version with a parent; the original is never overwritten. A sentence whose exact bytes survive the
edit keeps its binding; a sentence that lost a protected fact (currency, amount, period, basis, accession) is
**INVALIDATED** and a review item names what changed. A currency, period or basis in free prose that contradicts the
claim produces a review item within the stated scan scope. When a v8 source is corrected or a claim amended after the
brief's snapshot, `review` lists the statements whose recorded dependencies need a look; earlier exports stay valid as
historical snapshots.

## 5. Import a draft or a provenance record

```
yuclaw workbench brief import --workspace … --file draft.txt --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
yuclaw workbench brief link --workspace … --brief brf-… --start 0 --end 57 --role direct_quotation --claim ZZFX-…-001-base --claim-version V1
yuclaw workbench brief import-record --workspace … --kind report --file report.json
yuclaw workbench brief trust --workspace … enroll --public-key <base64 Ed25519> --label "issuer X"
```

An imported draft's sentences start **NOT_ASSESSED**; you link spans by UTF-8 byte offsets. A direct quotation is checked
against the registered excerpt bytes; a link of free prose to a claim is **ATTRIBUTED** to you, never SUPPORTED. A
detector report must bind to the exact tested bytes; its `execution` (NOT_REQUESTED / ACCESS_UNAVAILABLE / UNSUPPORTED /
INSUFFICIENT_INPUT / COMPLETED / FAILED), `signal` (only when COMPLETED) and `calibration` (APPLICABLE / OUT_OF_SCOPE /
NOT_ESTABLISHED) are kept apart. NOT_DETECTED never proves human authorship; a score is not a percentage of AI text; a
watermark establishes neither identity nor accuracy.

## 6. Export and verify elsewhere

```
yuclaw workbench brief export --workspace ~/yuclaw-workspaces/research --brief brf-…
yuclaw workbench brief verify ~/yuclaw-workspaces/research/exports/bpk-….zip --workspace ~/yuclaw-workspaces/fresh
```

The packet holds the readable `brief.html` (no script), `brief.json`, `records.json`, the snapshot, the text of every
version, a methods/limitations appendix and `VERIFY.md`. Verification declares each check separately: VERIFIED, FAILED,
NOT_RECOMPUTABLE (an input was withheld by rights), REPORT_ONLY (a detector result cannot be rerun), UNSUPPORTED,
NOT_APPLICABLE. Signatures are judged against the receiving workspace's own trust roots; a packet never enrolls its signer.

## 7. When something goes wrong

- `refused: …` with exit 2 — a contract refusal; nothing was written. Fix the named field.
- `E_OP_CONFLICT` with exit 1 — the same `--op-id` was reused with different content; use a new operation id.
- `E_TORN_TAIL` — an interrupted write; `yuclaw workbench brief recover --workspace …` preserves the bytes and records it.
- `INCOMPLETE` on a version — its prepared objects are missing; it is never shown or exported as complete.
- `orphans` lists prepared objects that no record commits; `--remove` deletes only those.
- `measure` prints operation counts with their definitions (one op_id = one operation; attempts and retries counted separately).

Full guide, schema reference and migration note: `docs/guide/v9/` in the repository.
