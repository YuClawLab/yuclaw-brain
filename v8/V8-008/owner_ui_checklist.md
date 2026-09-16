# Owner browser checklist — 8.0.0 candidate workbench (functional review by the owner; NOT a Gate #15 study; observations left blank until a human performs them)

This is the owner's own click-through of the local workbench. It records nothing as human review, enrols no participant, and does not change Gate #15 (MANUAL_REVIEW) or human benefit (PENDING). Research and education only. Not investment advice.

Setup (from the coherent candidate's wheel, or from a checkout at the designated commit):
```
python3 -m venv ~/yuclaw-venv && ~/yuclaw-venv/bin/pip install <yuclaw-8.0.0-py3-none-any.whl>   # sha256 aa988727055aa81f…
~/yuclaw-venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/research --port 8765
~/yuclaw-venv/bin/python -m v8.workbench serve --workspace ~/yuclaw-workspaces/fresh    --port 8766
```
Open `http://127.0.0.1:8765/`. Tick each line only when you saw it yourself.

| # | Where | What to check | Expected | Observed (owner; blank until performed) |
|---|---|---|---|---|
| 1 | Workspace | version badge in the footer / package version | `8.0.0`; header shows YUCLAW; mission and vision sentences present and unchanged | |
| 2 | Workspace | load a fixture | fixture labelled FICTIONAL (demonstration data); claim appears with its computed result | |
| 3 | 1 Source | register a source passage with an availability timestamp | source id assigned; as-of view lists it only from its availability time onward | |
| 4 | 2 Typed claim | save a claim with a missing field (e.g. no fiscal-period end) | refused with every reason listed; nothing frozen | |
| 5 | 2 Typed claim | save and freeze a complete claim | frozen version with digest; freeze is one-way | |
| 6 | Claim → 3 Comparison | revise the range with a different basis | INCOMPARABLE with the reason; original and revised shown side by side; amendment note visible | |
| 7 | Claim → 4 Calculation | record an outcome | result per range with inputs, formula and source links; an incompatible unit never passes | |
| 8 | Claim → 5 History | replay as of a cutoff before a revision | later information absent; "source observed" time shown | |
| 9 | Claim → Research notes | record an unresolved question, then correct it | second note supersedes the first; earlier text retained; claim digest unchanged; actor label shown as attribution only | |
| 10 | Claim → 6 Adjudication | record a reviewer label with a conflicting one | both labels visible; conflict listed | |
| 11 | Claim → 7 Reproducible export | build the export | zip downloads; publication eligibility shows NOT ELIGIBLE separately | |
| 12 | Research notes (nav) | all notes across claims | actor kind and local action time per note | |
| 13 | Dataset coverage | rows and snapshot | one row per frozen claim; snapshot identity; `/dataset.json` matches the page | |
| 14 | Scientific report | replay the packaged exploratory example | report with status EXPLORATORY_ONLY, kernel identity `5b3e0d221c2200b2…`, links to claim/version/source bytes | |
| 15 | Scientific report | replay a refused example (monetary probabilities) | specific refusal reason MONETARY_OR_OUT_OF_RANGE_PROBABILITY; nothing recorded as evidence | |
| 16 | Verify an export (port 8766, fresh workspace) | upload the export from #11 | SUCCESS: bytes, digests, notes, dataset row and scientific records recomputed | |
| 17 | Verify an export | upload the same zip with one byte changed | MISMATCH; refused | |
| 18 | Journal | the event log | append-only, digest-chained; the export and verification events present | |
| 19 | Any page | browser back after a submit | a fresh form (no accidental resubmission); a retried submission lands once | |
| 20 | Terminal | `python -m v8.workbench verify-export <zip>` | exit 0 SUCCESS on the good zip, 1 MISMATCH on the altered one | |
| 21 | Any page | wording | English only; YUCLAW on every authored surface; no wording that claims independent review, human benefit or a validated method | |

Record each observation in the last column in your own words; nothing here writes a record, and a completed checklist is the owner's functional review, not Gate #15 evidence (Gate #15 needs the comprehension study or an explicit owner route decision). If any line fails, that is a candidate defect and the designation waits.
