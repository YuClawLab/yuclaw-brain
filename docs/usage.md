# YUCLAW CLI usage

Copy-pasteable examples with real (truncated) output. Every command exports
**YUCLAW-derived data only** — typed classifications, verified excerpts,
derived statistics; never raw vendor price/options data.

*Research and education use only. Not investment advice. Event types, grades,
and postures are research classifications, not recommendations.*

Install: `pip install yuclaw`

> The `events` / `lens` / `export` subcommands ship in the next PyPI release;
> until then run them from a checkout: `python3 -m v3.cli ...`.
> `memo` note: pip 5.0.0 ships the **earlier** memo interface (positional
> ticker, `--as-of`); the evidence-memo CLI documented below
> (`--ticker`/`--days`, citation-verified) also ships next release — run it
> from a checkout meanwhile: `python3 -m v4.memo.cli --ticker SU --days 90`.
> `yuclaw replay-lab` works in the published 5.0.0 today.

---

## yuclaw events — accepted-events export

```console
$ yuclaw events --ticker SU --since 2026-05-01
2026-05-05  DIVIDEND_CHANGE    dir +1  mag 0.80  6-K      News Release dated May 5, 2026, Suncor Energy declares dividend
2026-05-05  OTHER_MATERIAL     dir +0  mag 0.20  6-K      Suncor Energy reports voting results from Annual General Meeting
2026-05-06  EARNINGS_BEAT      dir +1  mag 0.80  6-K      Generated over $4.0 billion in adjusted funds from operations and $2.9 billion in free fun…
2026-05-14  OTHER_MATERIAL     dir +0  mag 0.20  6-K      Suncor Energy Inc. Extractive Sector Transparency Measures Act Report for the reporting ye…

4 accepted event(s) · research classifications, not recommendations
```

`--json` or `--csv` switch the output format for machine use.

## yuclaw lens — lens summary data as JSON

```console
$ yuclaw lens canada --lens XEG
{
 "lens": "XEG",
 "name": "iShares S&P/TSX Capped Energy Index ETF",
 "theme": "Canadian oil & gas (cap-weighted)",
 "coverage_weight_pct": 76.0,
 "sec_filer_count": 8,
 "names_total": 28,
 "filings_ingested": 86,
 "accepted_events": 70,
 "matured_events": 58,
 "insider_eligible_names": 0,
 "outside_scope": "TSX-only issuers with no current EDGAR reporting — Tourmaline (5.6%), …",
 "note": "Evidence tier only — never scored. Counts and classifications, not recommendations."
}
```

The same numbers the Canada Resources page renders — pulled live, never
hand-typed.

## yuclaw export — derived-data exports and evidence packets

```console
$ yuclaw export --lens GDX --format csv
wrote ./yuclaw_gdx_events.csv · 399 accepted event(s) across 28 covered names · derived data only

$ yuclaw export --page canada
[packets] canada: yuclaw_canada_resources_packet.zip (127.8 KB) data_through=2026-07-16 files=['coverage.json', 'events.csv', 'lens_summaries.json', 'scope_disclosures.txt']
packet: …/docs/packets/yuclaw_canada_resources_packet.zip (127.8 KB) · data through 2026-07-16
```

Every packet ships `METADATA.json` (data-through date, build date, source
commit, ledger root, methodology version, scope note, known limitations) and
`CITATION.txt`.

## yuclaw memo — evidence memo (analyst work product)

```console
$ yuclaw memo --ticker SU --days 90
# Evidence memo — Suncor Energy Inc (SU)

*Window: last 90 days (2026-04-17 → 2026-07-16) · generated 2026-07-16 08:12 UTC · evidence grade A (events + prose evidence)*

## Research question
What changed in Suncor Energy Inc's filings evidence over the last 90 days?

## Evidence table
| Date | Form | Exhibit | Event type | Verified quote | Grade | C6 posture | SourceLock |
|---|---|---|---|---|---|---|---|
| 2026-05-06 | 6-K | exhibit99 | EARNINGS_BEAT | “Generated over $4.0 billion in adjusted funds from operations…” | A | high / normal | accepted |
…
```

Full example: [docs/examples/evidence_memo_su.md](examples/evidence_memo_su.md).
The change narrative is LLM-written but machine-verified: every sentence must
cite an event ID and every number must appear in the cited verified quotes —
any uncited claim fails the generation. A banned-word lint (buy, sell, hold,
undervalued, … — see `tools/check_language.py`) also fails generation.
Generation is on-demand only, serialized through `gpu-lock`; there is no bulk
memo generation. The deterministic conclusion vocabulary is locked:
*evidence posture improved / weakened · risk-gate elevated · insufficient
matured evidence · outside current evidence scope · not statistically
proven · underpowered*.

## yuclaw replay-lab — verify the public record

```console
$ yuclaw replay-lab
[replay-lab] cohorts rebuilt · statistics recomputed · 33 daily roots match the public ledger
exit 0
```

No install needed: `tools/replay_lab.py` is standard-library-only — see the
[replication page](replication.html) for the exact procedure and pass
criteria, and file replication reports (pass or fail) via the GitHub issue
template.
