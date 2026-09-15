# V8-001 §5 — initial one-issuer real-data selection criteria

Purpose: choose ONE real issuer for the first real-data pass of the source-to-export workbench, after the fictional
fixtures pass. Fixture validation, real-data quality and human benefit are three separate questions; passing one does
not establish the others. No crawler is activated and no commercial dataset coverage is claimed by this document.

Selection criteria (all required):
1. **Already in the v7 evidence corpus** — the issuer appears in `v3/evidence/corpus_snapshot.json.gz` with at least one
   `GUIDANCE_RAISE` or `GUIDANCE_CUT` evidence object (`check-claim` must resolve offline); no new ingestion.
2. **Machine-readable commitment** — the guidance sentence states a numeric range with explicit currency, fiscal period
   and basis (GAAP / non-GAAP named) in the filing text itself (not a press-release image, not a transcript).
3. **A comparable outcome exists inside the corpus window** — a later filing states the actual for the same period and
   basis; availability dates for both are the EDGAR acceptance timestamps already stored (`available_as_of`).
4. **Point-in-time clean** — every record's `available_as_of` is at or before the corpus end; nothing back-filled.
5. **No custody or denylist conflict** — the issuer is not in the Canada Resources evidence-only tier (scoring those names
   is a STOP condition) and no excerpt trips `tools/check_leak_sweep.py` or the excerpt-quality annotations.
6. **One issuer, one claim chain** — a single claim with at most one revision; complexity is added only after the
   seven steps are demonstrated once.

Exclusions: issuers with restatements inside the window, non-USD reporting, or guidance stated only as growth
percentages (a percentage needs a base that must itself be sourced — a second claim chain).

Output of the selection step: a short record (`v8/V8-002/real_data_selection.json`) naming the issuer, the two
accessions, the available_as_of timestamps and the criterion checks — nothing is scored, nothing is published.
