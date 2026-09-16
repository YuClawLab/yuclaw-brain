# YUCLAW 8.0.0 candidate — start here (local workbench)

One documented startup path. Everything runs on your machine, bound to 127.0.0.1; nothing here publishes, trades, trains or contacts a service.
Research and education only. Not investment advice.

## Install and start

```
python3 -m venv ~/yuclaw-venv && ~/yuclaw-venv/bin/pip install <the wheel file>      # the identified candidate artifact (see the release notes for its sha256)
~/yuclaw-venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/research --port 8765
~/yuclaw-venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/fresh    --port 8766   # a second, fresh workspace for verification
```
Open `http://127.0.0.1:8765/`. A workspace must not live inside a public `docs/` tree; the server refuses any bind other than loopback.
From a source checkout the same commands work with `python3 -m v8.workbench …` in the repository root.

## Navigation (top of every page)

| Entry | What you do there |
|---|---|
| **Workspace** | see your claims and their computed results; load a clearly fictional fixture (demonstration data) |
| **1 Source** | register the exact passage a commitment comes from, with its availability timestamp; view sources as of a cutoff |
| **2 Typed claim** | save and freeze a fully specified commitment (currency, unit, scale, basis, fiscal period, resolution rule) |
| claim page → **3 Comparison** | original vs revised ranges side by side, or INCOMPARABLE with every reason; amendment notes and research notes beside it |
| claim page → **4 Calculation** | the outcome against each range with inputs, formula and source links; mismatches never pass |
| claim page → **5 History** | replay as of any cutoff; later information is never shown as known earlier |
| claim page → **Research notes** | record an unresolved question, next evidence, reason and actor label; correct a note without changing the claim |
| claim page → **6 Adjudication** | reviewer label, rule, evidence, reason, conflicts; disputed labels stay visible |
| claim page → **7 Reproducible export** | build and download the research export; publication eligibility is shown separately (NOT ELIGIBLE) |
| **Research notes** | every note across claims with actor kind and local action time |
| **Dataset coverage** | one row per frozen claim derived from stored records; snapshot identity; build a verifiable dataset snapshot; `/dataset.json` |
| **Scientific report** | replay a science journal (a JSON event list, or a packaged fictional example) through the adapted kernel: report or specific refusal, links to claim/version/source bytes, replay status; `/sci/S<n>` for each record |
| **Verify an export** | in a fresh workspace: upload any export; bytes, digests, notes, dataset rows and scientific records are recomputed |
| **Journal** | the append-only, digest-chained event log |

Offline: `python3 -m v8.workbench verify-export <zip>` (exit 0 SUCCESS · 1 MISMATCH · 3 UNSUPPORTED), `status`, `recover`.

## What the labels mean

- **FICTIONAL** fixtures are demonstration data, never a dataset product. The packaged scientific examples are fictional fixtures too.
- The Microchip example is a **retrospective** real-source replay (observed after its outcome was public) and is **NOT_ELIGIBLE_UNDER_V8_001_CRITERIA**; it demonstrates behaviour, not real-data quality.
- An actor label is attribution only; automated actions are marked **simulated test action**. No human study has been run; human benefit is PENDING.
- **Computational verification** (hashes re-derived, statistics recomputed) is not source truth, independent review or an externally authenticated timestamp.
