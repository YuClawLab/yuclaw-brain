<div align="center">

# YUCLAW

**The open evidence layer for financial research — every claim carries its own audit trail.**

Statistics pre-registered before data. Adverse results published.

<!-- REPLICATION-SENTENCE-CANONICAL BEGIN -->
Designed for reproduction from published artifacts. One affiliated external-machine reproduction recorded; unaffiliated replications: 0.
<!-- REPLICATION-SENTENCE-CANONICAL END -->

![PyPI](https://img.shields.io/pypi/v/yuclaw)
![License Apache--2.0](https://img.shields.io/badge/License-Apache--2.0-green)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![Ledger git-anchored](https://img.shields.io/badge/Ledger-git--anchored-blue)

</div>

**First touch — install, ask for help, check a claim, reproduce the Lab** (expected exit code in the comment):

```bash
pip install yuclaw                                              # installs the CLI
yuclaw --help                                                   # command list with one-line descriptions · exit 0
yuclaw check-claim --text "NVDA reported an insider sale in May 2026"   # Evidence Passport JSON · exit 0
yuclaw check-claim --ticker NVDA --accession 0001045810-26-000019       # passport for one cited filing · exit 0
yuclaw check-claim --accession 0001045810-26-000019            # accession alone: unique → same passport · exit 0
                                                               # (ambiguous accession → exit 2 with the candidate tickers)
yuclaw replay-lab                                              # rebuilds every published Lab statistic · exit 0 = reproduced
```

Exit-code contract for every command: 0 = success · 1 = ran, negative result (e.g. a
replay mismatch) · 2 = usage or validation error · 3 = environment unsupported. The
transcript below is generated from the release-candidate wheel and regenerated every release:

<!-- CLI-TRANSCRIPT BEGIN -->
Transcript generated from the release-candidate wheel `yuclaw-6.0.1-py3-none-any.whl` (yuclaw 6.0.1, Python 3.12.3, 2026-09-04 UTC) by `tools/cli_transcript.py`; the `replay-lab` run uses the documented local-bundle path.

```text
$ yuclaw --version
yuclaw 6.0.1
[exit 0]
```
```text
$ yuclaw --help
yuclaw 6.0.1 — evidence-first financial research CLI (research and education only; not investment advice)

usage: yuclaw <command> [args]   ·   yuclaw <command> --help

commands:
  brief         evidence brief (legacy v3 helper)
  cascade       supply-chain cascade view for a ticker (deterministic, evidence-backed)
  check-claim   Evidence Passport — deterministic claim check (--text, --ticker/--type/--date-range, --accession)
  demo          3-minute guided offline journey — zero config, no backend
  events        accepted-events export (derived data only)
  export        lens events export (--format csv|json; --page builds the evidence packet)
  intake-check  client-side pre-check of a signal CSV for Signal Review (never transmits)
  keys          manage API keys for the REST server
  lens          lens summary-card data as JSON (the numbers the page renders)
... (11 more lines)
[exit 0]
```
```text
$ yuclaw check-claim --text "NVDA reported an insider sale in May 2026"
{
 "status": "SOURCE_MATCHED",
 "claim_as_parsed": {
  "ticker": "NVDA",
  "type": "INSIDER_SELL",
  "accession": null,
  "date_range": null
 },
 "misses": [],
 "matched_evidence": "<5 object(s)>",
 "...": "<8 fields total; not_advice line present: True>"
}
[exit 0]
```
```text
$ yuclaw check-claim --ticker NVDA --accession 0001045810-26-000019
{
 "status": "SOURCE_MATCHED",
 "claim_as_parsed": {
  "ticker": "NVDA",
  "type": null,
  "accession": "0001045810-26-000019",
  "date_range": null
 },
 "misses": [],
 "matched_evidence": "<1 object(s)>",
 "...": "<8 fields total; not_advice line present: True>"
}
[exit 0]
```
```text
$ yuclaw check-claim --accession 0001045810-26-000019
{
 "status": "SOURCE_MATCHED",
 "claim_as_parsed": {
  "ticker": "NVDA",
  "type": null,
  "accession": "0001045810-26-000019",
  "date_range": null
 },
 "misses": [],
 "matched_evidence": "<1 object(s)>",
 "...": "<8 fields total; not_advice line present: True>"
}
[exit 0]
```
```text
$ yuclaw replay-lab docs/replay/lab_replay_bundle.json
Replay bundle built 2026-09-04 09:51 UTC from source commit 251f13141ee6
Ledger repo: https://github.com/YuClawLab/yuclaw-trust @ c7f6fa2dd84d

[forward] 72 rebalance periods, window ['2026-05-20', '2026-09-03']
  spread top_minus_bottom   mean/period -0.00159  t=-0.47 p=0.640  n=72  CI95=(-0.00837,+0.00491)
  spread top_minus_universe mean/period -0.00172  t=-0.97 p=0.335  n=72  CI95=(-0.00528,+0.00169)
  IC  1d  mean +0.0081  NW-t=+0.28 (lag 0) p=0.778  T=76 dates
  IC  5d  mean -0.0095  NW-t=-0.23 (lag 4) p=0.822  T=72 dates
  IC 20d  mean -0.0300  NW-t=-0.73 (lag 19) p=0.467  T=57 dates  [T too small — descriptive only]
  market-model vs_universe  alpha/period -0.00160 beta +0.90  t(alpha)=-0.89 p=0.376  R2=0.189  n=72
  market-model vs_spy       alpha/period -0.00115 beta +0.80  t(alpha)=-0.63 p=0.529  R2=0.158  n=72

[in_sample] 13 rebalance periods, window ['2026-02-18', '2026-05-18']
  spread top_minus_bottom   mean/period +0.00553  t=+0.41 p=0.686  n=13  CI95=(-0.01937,+0.03079)
... (11 more lines)
[exit 0]
```
<!-- CLI-TRANSCRIPT END -->

Protocol chain (statistics locked BEFORE computation, tamper-evident):
`curl -sO https://raw.githubusercontent.com/YuClawLab/yuclaw-brain/main/registry/protocols.jsonl` ·
full clean-environment replication: `make replicate`.

**[How we compare →](COMPARISON.md)** · **[Take the 5-minute tour →](https://yuclaw.ca/tour.html)**

**What you'll find inside:** the baseline test our own composite lost at current
sample sizes — published under the pre-registered protocol · a label-calibration
panel that says "directional meaning not yet demonstrated" · retired hypotheses
preserved with their grounds · 500+ filings shown to be 3 evidence stories ·
robustness grids that print where results break.

**Research and education only — not investment advice.** Signal labels are
research classifications, not buy/sell recommendations.

<div align="center">

[Live site (yuclaw.ca)](https://yuclaw.ca) ·
[Validation Lab](https://yuclaw.ca/validation_lab.html) ·
[SMH Evidence Lens](https://yuclaw.ca/etf_evidence.html) ·
[XLK Evidence Lens](https://yuclaw.ca/xlk_evidence.html) ·
[Canada Resources](https://yuclaw.ca/canada_resources.html) ·
[Forward Tracking](https://yuclaw.ca/validation.html) ·
[📖 User Guide (EN)](https://yuclaw.ca/YUCLAW_User_Guide.pdf) ·
[📖 Guide (FR)](https://yuclaw.ca/YUCLAW_Guide_Utilisateur_FR.pdf) ·
[Weekly Note](https://yuclaw.ca/weekly_note.html) ·
[For AI agents → llms.txt](https://yuclaw.ca/llms.txt) ·
[**⚠️ Disclaimer**](#%EF%B8%8F-disclaimer) ·
[PyPI](https://pypi.org/project/yuclaw)

</div>

> [!IMPORTANT]
> **Research and education only — not investment advice.** Signal labels are research
> classifications, not buy/sell recommendations. Hypothetical research; past results do
> not predict future performance.

---

## Why this is different

- **Statistics are registered before they are computed.** Every published
  statistic names its protocol in a hash-chained, append-only registry
  ([registry/protocols.jsonl](registry/protocols.jsonl)); estimator changes
  are supersessions, never edits. Check the chain yourself:

  ```bash
  python3 - <<'EOF'
  import sys; sys.path.insert(0, 'tools')
  from yuclaw_protocol_registry import Registry
  Registry('registry/protocols.jsonl').verify_chain(); print('chain OK')
  EOF
  ```

- **Self-audits publish as measured.** A pre-registered champion-challenger
  test found a persistence baseline ahead of our own composite at the primary
  horizon — that table is on the [Lab page](https://yuclaw.ca/validation_lab.html),
  not in a drawer. The label-calibration panel prints where labels carry no
  demonstrated directional meaning.
- **Lenses pass a published admission standard or they don't ship.** The XLK
  lens is live because it passed the same admission standard the SMH lens
  registered; verdicts and their reasons print on each page.
- **The evidence layer is machine-readable.** [llms.txt](https://yuclaw.ca/llms.txt)
  and [evidence_index.json](https://yuclaw.ca/evidence_index.json) give AI
  agents stable URLs for every page, packet, and protocol.

---

## What YUCLAW does

- **Every signal traces to a filing.** Each composite score decomposes into nine
  components, and every evidence event links to the SEC document it was
  extracted from — checked against the source text before any signal sees it.
- **Every snapshot is hashed to a public, tamper-evident ledger — git-anchored,
  never edited.** Daily signal sets are content-hashed and committed to
  [yuclaw-trust](https://github.com/YuClawLab/yuclaw-trust) before pages
  publish. Outages are disclosed, never backfilled.
- **Every Lab chart is reproducible bit-for-bit.** `yuclaw replay-lab` (or a
  standalone stdlib script) rebuilds the cohorts, recomputes every statistic,
  and re-derives every ledger hash root from published derived data.

---

## Sixty seconds

```bash
pip install yuclaw
yuclaw demo                        # 3-minute guided journey — works offline, zero config
yuclaw why AMD --as-of 2026-05-20  # bundled offline signal, no backend needed
```

Live signals for **all** tickers need the local backend
([docs/v4/backend_setup.md](docs/v4/backend_setup.md)); the published-data
commands work anywhere with no backend. The most recent recorded external-machine
replication (see the [Replication Log](https://yuclaw.ca/replication.html)) ran
`replay-lab` from a fresh venv with nothing but `pip install yuclaw` and reproduced
**74 daily ledger roots exactly plus one anchored-subset day (6,165 leaf hashes
recomputed)** and every published statistic, exit 0. It exits non-zero on any
mismatch.

---

## What is in 6.0.x

Current package version: `6.0.1` — the release notes, the frozen wheel and sdist
SHA-256 hashes, and the shipped-object list live on the
[GitHub Release for this version](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v6.0.1)
([all releases](https://github.com/YuClawLab/yuclaw-brain/releases) ·
[CHANGELOG](CHANGELOG.md)). 6.0.1 is a patch — public synchronization and CLI
first-touch; no methodology change; protocol chain unchanged at 82 lines.

### Command surface

```bash
yuclaw --help                      # Command list with one-line descriptions (also -h, help)
yuclaw why TICKER                  # Composite signal + ranked evidence w/ SEC source URLs
yuclaw check-claim --text "..."    # Evidence Passport — deterministic claim check (also --ticker/--type/--date-range/--accession)
yuclaw replay TICKER --date DATE   # Point-in-time signal at end of date
yuclaw replay-lab                  # Reproduce the Validation Lab from the public bundle
yuclaw validation                  # In-sample event validation + forward tracking ledger
yuclaw events --ticker SU --since 2026-05-01   # Accepted-events export (derived data only)
yuclaw lens canada --lens XEG      # Lens summary-card data as JSON (same numbers the page renders)
yuclaw export --lens GDX --format csv          # Lens events export; --page builds the evidence packet
yuclaw memo --ticker SU --days 30  # Evidence memo — grounded, citation-verified, linted (docs/usage.md)
yuclaw verify TICKER --date DATE   # Verified Research Ledger integrity check
```

Worked examples with real output: [docs/usage.md](docs/usage.md).

**Public signal vocabulary:** `STRONG_BULLISH`, `BULLISH`, `NEUTRAL`, `WATCH`,
`WEAKENING`, `NEGATIVE_EVENT`, `BEARISH_WATCH`, `RISK_ALERT`.
There is no `SELL` or `SHORT` label — these are research classifications, not trade directions.

---

## How it works

```
SEC EDGAR (Form 4 / 8-K / 10-Q / 10-K / 6-K / 20-F / 40-F)
  │
  ▼ systemd poller (always-on, 5-min sweep)
  ├──▶ Form 4 → deterministic XML parser (no LLM, zero GPU) → events table
  ▼ prose-first text acquisition (exhibit / MD&A prose; XBRL cover fallback)
  ▼ Llama 3.1 70B extraction + SourceLock Guard (checked against source text)
  ▼ events table — the evidence layer
  ▼ Layer-1 specialist swarm (10 specialists; risk channel kept SEPARATE from direction)
  ▼ 9-component composite (C1..C9)
  ▼ signal_snapshots (content-hashed)
  ├──▶ Verified Research Ledger (git-anchored, public)
  ├──▶ Forward Tracking Ledger (outcomes vs SPY at 1 / 5 / 20 days)
  ├──▶ Live landing + Validation Lab pages (regenerated daily)
  └──▶ SDK / REST / MCP server
```

**132-name coverage:** a 79-name scoring universe (equities + sector ETFs +
broad ETFs + macro instruments) plus a 53-filer evidence tier (49 Canada Resources
issuers + 4 SMH-lens foreign filers: ASML, NXPI, STM, TSM) — ingested and
dashboarded, never scored; the boundary is machine-enforced.

Deep dives: [system architecture, operations, hardware](docs/architecture.md) ·
[OpenClaw / MCP integration](docs/openclaw.md) ·
[methodology](docs/methodology/backfill.md).

---

## Signal Validation Lab

A decile-cohort event study of whether YUCLAW's composite score carries forward
information — built from feedback by **Prof. Deng Shijie (Georgia Tech)**:

- **Regenerated daily** after U.S. market close, freshness-stamped, with a
  staleness alarm in the health monitor.
- **Statistical rigor panel:** bootstrap confidence intervals, Newey–West and
  clustered inference, market-model alpha, and a statistical power meter that
  quantifies what the current n can and cannot detect.
- **Statistics computed per-regime** (in-sample vs forward) and never blended
  across the boundary.
- **Reproduce this page:** `yuclaw replay-lab` or the standalone stdlib script.

In the Lab's own words: *"No forward alpha has been statistically proven yet."*

🔬 **Live:** [Signal Validation Lab](https://yuclaw.ca/validation_lab.html)
· [Today's Evidence Digest](https://yuclaw.ca/todays_evidence.html)
· [Independent Replication Log](https://yuclaw.ca/replication.html)
· **Methodology:** [docs/methodology/validation_lab.md](docs/methodology/validation_lab.md)

*Hypothetical research illustration — not investment advice, not performance advertising.*

---

## Methodology & honest limitations

Full methodology lives in [docs/methodology/backfill.md](docs/methodology/backfill.md).
The honest limits, stated up front:

- **The forward record is young.** Forward tracking began 2026-05-20; roughly
  50 trading days of look-ahead-free history exist as of early August 2026 —
  enough to display, not enough for statistical significance; the Lab's power
  meter quantifies this.
- **In-sample is replay reconstruction, not a live backtest.** The in-sample
  panel was materialized after the fact by the replay engine; the canonical
  look-ahead statement below says exactly what the extraction model could and
  could not have seen, and why in-sample results stay systematically optimistic.
- **C6 risk channel is partially confirmed.** Rareness confirmed OOS; the sign
  question remains open — the first read under the registered v2 protocol
  printed INCONCLUSIVE (2026-07-30) and accrual continues. The sign
  confirmation is the gate for Layers 2–10, and it has not been met.
- **C4 macro regime is temporarily frozen as of 2026-05-18** with a staleness
  disclosure, pending macro-engine restoration. C1/C3/C5/C7 read live
  `price_history`; C6/C8/C9 remain point-in-time exact.
- **Jun 26 – Jul 3, 2026 outage — disclosed, not patched.** A network outage
  froze price-derived inputs at Jun 25 closes while snapshots continued
  point-in-time on-box. No snapshot or ledger row was retroactively edited.
- **No table of headline % returns appears in this README.** Hit rates are
  reported alongside their *n* on the
  [live validation page](https://yuclaw.ca/validation.html); small-*n* panels
  are tagged.

**Look-ahead statement** — canonical text, byte-identical on every surface
(README, methodology, Validation Lab page; checked by the copy-consistency gate):

<!-- LOOKAHEAD-CANONICAL BEGIN -->
In-sample look-ahead statement. The in-sample replay rows (signal dates 2026-02-18
to 2026-05-13, evidence window 2026-02-18 to 2026-05-17) were built from evidence
events extracted by one language model, Meta Llama 3.1 70B Instruct (served
locally as yuclaw-llm-70b), whose published pretraining cutoff is December 2023
(Meta model card). Form 4 events in the window come from a deterministic XML
parser with no language model. The earliest in-sample date is about 26 months
after that cutoff, so no filing text in the window could have been seen in
training: there is no parametric look-ahead from the filings themselves, and the
model's general market knowledge also ends before the window begins. The replay
engine flags any as-of date before 2024-07-01 as inside the model's training
window; no in-sample date triggers it. In-sample results nonetheless remain a
replay reconstruction, not a live record: the scoring design was finalized in May
2026, after the window it is replayed over, market-layer components read
approximated inputs, and no in-sample signal was exposed to external challenge in
real time. In-sample results are therefore treated as systematically optimistic
and educational only; the forward record (signal dates from 2026-05-20) is the
look-ahead-free record.
<!-- LOOKAHEAD-CANONICAL END -->

---

## Community

| | |
|---|---|
| **Live site** | [yuclaw.ca](https://yuclaw.ca) |
| **Validation Lab** | [validation_lab.html](https://yuclaw.ca/validation_lab.html) |
| **SMH Evidence Lens** | [etf_evidence.html](https://yuclaw.ca/etf_evidence.html) |
| **XLK Evidence Lens** | [xlk_evidence.html](https://yuclaw.ca/xlk_evidence.html) |
| **📖 User Guide (EN / FR)** | [EN](https://yuclaw.ca/YUCLAW_User_Guide.pdf) · [FR](https://yuclaw.ca/YUCLAW_Guide_Utilisateur_FR.pdf) |
| **Twitter** | [@Vincenzhang2026](https://twitter.com/Vincenzhang2026) |
| **GitHub** | [YuClawLab](https://github.com/YuClawLab) |
| **PyPI** | [pypi.org/project/yuclaw](https://pypi.org/project/yuclaw) |
| **Methodology** | [docs/methodology/backfill.md](docs/methodology/backfill.md) |

---

## ⚠️ Disclaimer

YUCLAW is open-source research and educational software. It is **NOT financial advice,
investment advice, or a recommendation to buy, sell, or hold any security.** All signals,
scores, and analyses are generated by automated AI models and may contain errors.

Past performance does not guarantee future results. Trading involves substantial risk of loss.
You are solely responsible for your own investment decisions. Consult a licensed financial
advisor before making any investment.

YuClawLab, its contributors, and affiliates accept no liability for any losses arising from use
of this software.

For educational and research purposes only. See
[docs/methodology/backfill.md](docs/methodology/backfill.md) and
[DISCLAIMER.md](DISCLAIMER.md) for the long-form versions.

---

## For AI agents & researchers

The open evidence layer for financial AI.

Agents citing YUCLAW inherit accession-verified, point-in-time, hash-anchored
evidence. Start at [capabilities.json](https://yuclaw.ca/capabilities.json) — one URL discovers
the why-JSON API, the Evidence Passport, the schemas, EvidenceBench, and the MCP tools
([full pitch](https://yuclaw.ca/for_ai_builders.html)).

- **Start here**: [`llms.txt`](https://yuclaw.ca/llms.txt) and the
  machine-readable [`evidence_index.json`](https://yuclaw.ca/evidence_index.json)
  (every page, packet, and protocol with stable URLs and data-through dates).
- **Objects**: the five frozen v1 JSON Schemas — SignalSnapshot, EvidenceEvent,
  ResearchProtocol, RobustnessCell, ResearchMemo — at [/schemas/](https://yuclaw.ca/schemas/SignalSnapshot.v1.json);
  today's real outputs validate against them in the daily gate suite.
- **Consume**: evidence packets (derived statistics, event CSVs, engine run
  JSONs, metadata + citation snippets) from `/packets/`; the MCP server
  exposes `why / memo / events / lens / universe / validation / verify` as
  tools with friendly no-backend behavior.
- **Cite**: use the `CITATION.txt` inside any packet; event-level citations
  use event IDs resolvable in the packet CSVs.
- **Verify**: `pip install yuclaw && yuclaw replay-lab` recomputes the
  published Lab statistics from the public bundle; the protocol registry
  ([registry/protocols.jsonl](registry/protocols.jsonl)) is hash-chained and
  append-only.
- **Rules**: derived statistics only; preserve the disclaimers and the
  frozen implication line when quoting inference; nothing here is advice
  or a recommendation.
<div align="center">

**Released under the Apache License 2.0 — free for everyone.**

`pip install yuclaw`

</div>
