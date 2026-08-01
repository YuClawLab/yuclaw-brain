<div align="center">

# YUCLAW

**Open-Source Evidence-First Financial Research Platform**

![License MIT](https://img.shields.io/badge/License-MIT-green)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![PyPI yuclaw 5.0.0](https://img.shields.io/badge/PyPI-yuclaw%205.0.0-orange)
![Hardware DGX Spark GB10](https://img.shields.io/badge/Hardware-DGX%20Spark%20GB10-76B900)
![Ledger git-anchored](https://img.shields.io/badge/Ledger-git--anchored-blue)

Composite research signals tied to SEC filings, a specialist evidence swarm running on
local models, and a public git-anchored Verified Research Ledger for tamper evidence.

**Research and education only — not investment advice.**
Signal labels are research classifications, not buy/sell recommendations.

[Live Dashboard](https://yuclawlab.github.io/yuclaw-brain) ·
[Validation Lab](https://yuclawlab.github.io/yuclaw-brain/validation_lab.html) ·
[Canada Resources Evidence](https://yuclawlab.github.io/yuclaw-brain/canada_resources.html) ·
[Open Index Evidence](https://yuclawlab.github.io/yuclaw-brain/etf_evidence.html) ·
[Quickstart](#sixty-seconds) ·
[📖 User Guide (PDF)](https://yuclawlab.github.io/yuclaw-brain/YUCLAW_User_Guide.pdf) ·
[Methodology](docs/methodology/backfill.md) ·
[**⚠️ Disclaimer**](#%EF%B8%8F-disclaimer) ·
[PyPI](https://pypi.org/project/yuclaw)

</div>

> [!IMPORTANT]
> **Research and education only — not investment advice.** Signal labels are research
> classifications, not buy/sell recommendations. Hypothetical research; past results do
> not predict future performance.

---

## What YUCLAW does

- **Every signal traces to a filing.** Each composite score decomposes into nine components,
  and every evidence event links to the SEC document it was extracted from — checked
  against the source text before any signal sees it.
- **Every snapshot is hashed to a public, tamper-evident ledger — git-anchored, never
  edited.** Daily signal sets are content-hashed and committed to
  [yuclaw-trust](https://github.com/YuClawLab/yuclaw-trust) before pages publish.
  Outages are disclosed, never backfilled.
- **Every Lab chart is reproducible bit-for-bit.** `yuclaw replay-lab` (or a standalone
  stdlib script) rebuilds the cohorts, recomputes every statistic, and re-derives every
  ledger hash root from published derived data.

---

## Sixty seconds

```bash
pip install yuclaw
yuclaw demo                        # 3-minute guided journey — works offline, zero config
yuclaw why AMD --as-of 2026-05-20  # bundled offline signal, no backend needed
```

Live signals for **all** tickers need the local backend
([docs/v4/backend_setup.md](docs/v4/backend_setup.md)); the published-data
commands — `yuclaw replay-lab`, `yuclaw verify`, `yuclaw validation` — work
anywhere with no backend.

With the backend running, `yuclaw why NVDA` looks like this (backend-mode
output):

```text
NVDA composite score: +0.299  (signal label: NEUTRAL)

Components (score × weight × confidence):
  C1 Momentum        +0.46   (weight 0.12)
  C2 Volume          +0.00   (weight 0.08)
  C3 Sector          -0.15   (weight 0.12)
  C4 Macro           +0.60   (weight 0.15)
  C5 Oil/Rates/FX    -0.47   (weight 0.05)
  C6 Event Impact    +0.16   (weight 0.18)
  C7 Peer Corr       +0.95   (weight 0.10)
  C8 Cascade         +0.00   (weight 0.12)
  C9 Model Trust     +0.00   (weight 0.08)

Top contributing events (last 7 days):
  ↑  +0.02  2026-05-14  M_AND_A_CLOSE (d1 cascade)
              CASCADE d1 via HPE→NVDA (supply, w=0.15) from HPE: H3C divestiture
              source: https://www.sec.gov/Archives/edgar/data/1645590/...

Compliance: Research only. Not financial advice. Not a registered investment advisor.
```

Then, check the receipts yourself:

```bash
yuclaw replay-lab
```

Fetches the public replay bundle and reproduces the Validation Lab off-box. At the v5.1.0
release this ran from a brand-new environment — a fresh venv with nothing but
`pip install yuclaw` — and reproduced **33 daily ledger roots exactly (2,926 leaf hashes
recomputed)** and every published statistic, exit 0. It exits non-zero on any mismatch.

---

## What shipped in v5.0

| Component | Measured / Shipped | Status |
|---|---|---|
| **Layer 0 — evidence job queue** | 281-filing real-data backfill: 281/281 succeeded, 0 dead-letter (`90f23392`) | Complete |
| **Layer 1 — specialist evidence swarm** | 10 event-type specialists: ma, insider, regulatory, supplychain, macro, geopolitical, earningsquality, litigation, sentimentdrift, esg (`1b2b2e07`, `745df911`) | Complete, in production |
| **Two-tier local inference** | Gemma 4 26B A4B worker (specialists/debate) + Llama 3.1 70B (extraction/synthesis), both via local Ollama (`21bdbc17`) | Live — zero cloud LLM dependency |
| **Prose-first ingestion** | worker persists exhibit/MD&A prose; corpus grounding 0.52 → 0.75, citation fidelity 0.66 → 0.85 (`f130983e`, live port `b1b153a0`) | Live |
| **Live reclassify rescue** | corrected event-type layer reproduces the stored corpus 97/97 (`67487eb2`) | Live |
| **C6 risk channel** | rareness confirmed OOS 2026-07-06 (22% fire rate, n=9 held-out); sign confirmation pending (elevated arm n=2; accrual live from 2026-07-16) (`c28f8542`, `aba72e89`) | Partial — sign pending |
| **Layers 2–10** | roadmap — **explicitly gated on out-of-sample sign confirmation** for the risk channel | Gated, not built |
| **Canada Resources evidence tier** | 49 SEC filers across XEG/ZEO/GDX/URNM; 6-K/40-F prose path; evidence-only, never scored; MJDS insider scope disclosed ([live dashboard](https://yuclawlab.github.io/yuclaw-brain/canada_resources.html)) | Live |

---

### Command surface

```bash
yuclaw why TICKER                  # Composite signal + ranked evidence w/ SEC source URLs
yuclaw replay TICKER --date DATE   # Point-in-time signal at end of date
yuclaw replay-lab                  # Reproduce the Validation Lab from the public bundle
yuclaw validation                  # In-sample event validation + forward tracking ledger
yuclaw events --ticker SU --since 2026-05-01   # Accepted-events export (derived data only)
yuclaw lens canada --lens XEG      # Lens summary-card data as JSON (same numbers the page renders)
yuclaw export --lens GDX --format csv          # Lens events export; --page builds the evidence packet
yuclaw memo --ticker SU --days 30  # Evidence memo — grounded, citation-verified, linted (docs/usage.md)
yuclaw brief                       # Personalized digest (uses ~/.yuclaw/profile.json)
yuclaw watch add TICKER            # Manage local watchlist
yuclaw verify TICKER --date DATE   # Verified Research Ledger integrity check
yuclaw profile show                # Local preferences
```

Worked examples with real output: [docs/usage.md](docs/usage.md).

> **PyPI 5.0.x note:** the `events` / `lens` / `export` / `memo` subcommands ship in
> v5.1; until then run them from a main checkout (`python3 -m v3.cli ...`;
> memo: `python3 -m v4.memo.cli ...`). Everything else above works in the published 5.0.x.

**Public signal vocabulary:** `STRONG_BULLISH`, `BULLISH`, `NEUTRAL`, `WATCH`,
`WEAKENING`, `NEGATIVE_EVENT`, `BEARISH_WATCH`, `RISK_ALERT`.
There is no `SELL` or `SHORT` label — these are research classifications, not trade directions.

---

## How it works

```
SEC EDGAR (Form 4 / 8-K / 10-Q / 10-K / 6-K / 40-F)
        │
        ▼
systemd poller (always-on, 5-min sweep)
        │
        ├──▶  Form 4 → deterministic XML parser (no LLM, zero GPU) → events table
        │
        ▼
prose-first text acquisition  ← exhibit / MD&A prose persisted; XBRL cover is the fallback
        │
        ▼
Llama 3.1 70B extraction  +  SourceLock Guard   ← every extraction checked against source text
        │
        ▼
live event-type rescue (corrected-type layer, reproduction 97/97)
        │
        ▼
events table  (the evidence layer)
        │
        ▼
Layer-1 specialist swarm (10 specialists, Gemma worker)
  — risk channel (C6, count≥2) kept SEPARATE from direction
        │
        ▼
9-component composite  (C1..C9 — C6 event impact carries the highest single weight, 0.18)
        │
        ▼
signal_snapshots  (content-hashed)
        │
        ├──▶  Verified Research Ledger  (git-anchored, public)
        ├──▶  Forward Tracking Ledger   (outcomes vs SPY at 1 / 5 / 20 days)
        ├──▶  Live landing + Validation Lab pages  (regenerated daily)
        └──▶  SDK / REST / MCP server
```

---

## Core capabilities

**Evidence-first composite signals.** The 9-component composite — momentum, volume,
sector velocity, macro regime, oil/rates/FX, event impact, peer correlation, supply-chain
cascade, model trust — is confidence-weighted. C6 event impact carries the highest single
weight (0.18), by design: evidence is meant to correct price-only signals, not echo them.

**Two-tier local inference.** Extraction and synthesis run on Llama 3.1 70B; the Layer-1
specialist swarm runs on Gemma 4 26B A4B (selected by A/B against the 8B baseline). Both
are served by one local Ollama daemon on the DGX Spark — zero cloud LLM dependency. SEC
EDGAR is the only external data source for the evidence layer.

**Grounded, measured extraction.** A deterministic verifier checks that every agent claim
carries a verbatim quote from the filing and that every number in the claim appears in
those quotes. No LLMs are in the loop for this verification. Measured on the L1 corpus:
grounding 0.52 → 0.75 and citation fidelity 0.66 → 0.85 after the prose-first fix
(measurement commit `f130983e`; production port `b1b153a0`).

**Time-machine replay.** Any signal can be recomputed as of a past date with point-in-time
filtering (`available_as_of <= as_of`). Leak-audited and reproducible via the `replay` CLI,
the REST `/replay` endpoint, or the MCP `yuclaw_replay` tool.

**Verified Research Ledger.** Each day's signal hashes are committed to a public git repo
(`yuclaw-trust`). Run `yuclaw verify TICKER --date DATE` to independently confirm a signal
hasn't been edited since publication. This checks record integrity and timing — not
investment merit.

**Multi-surface access.** Python SDK (`pip install yuclaw`), REST API, FastMCP stdio server
(7 tools), and CLI.

**128-name universe.** A 79-name scoring universe (equities + sector ETFs + broad ETFs +
macro instruments) plus a 49-filer Canada Resources evidence tier — ingested and
dashboarded, never scored; the boundary is machine-enforced
(`verify_evidence_tier_boundary`, 21 regression tests).

**Evidence memos.** `yuclaw memo` produces a citable research memo where every sentence
cites an event ID; a deterministic verifier checks each citation against source text and a
linter enforces the restricted conclusion vocabulary.
[Approved demo](docs/examples/evidence_memo_su.md).

---

## Signal Validation Lab (v2)

A Fama–French-style decile-cohort event study of whether YUCLAW's composite score carries
forward information — built from feedback by **Prof. Deng Shijie (Georgia Tech)**, upgraded
to protocol grade in v5.0:

- **Regenerated daily** after U.S. market close, with a freshness stamp on the page and a
  staleness alarm in the health monitor.
- **Rolling charts to the latest trading day** with the in-sample → forward regime boundary
  drawn on-chart; statistics are computed per-regime and **never blended** across it.
- **Statistical rigor panel:** bootstrap confidence intervals, Newey–West-corrected
  information coefficients, market-model alpha with its p-value, and a statistical power
  meter that quantifies what the current n can and cannot detect.
- **Panel 4 — evidence-qualified candidate cohort**, forward-only by construction, with its
  honest small-n stated (decile cohort of 2–4 names: "too small for inference").
- **Maturity gates: 1–3 passed, 4–6 not yet** — printed on the page.
- **Reproduce this page:** `yuclaw replay-lab` or the standalone stdlib script.

In the Lab's own words: *"No forward alpha has been statistically proven yet."*

🔬 **Live:** [Signal Validation Lab](https://yuclawlab.github.io/yuclaw-brain/validation_lab.html)
· [Today's Evidence Digest](https://yuclawlab.github.io/yuclaw-brain/todays_evidence.html)
· [Independent Replication Log](https://yuclawlab.github.io/yuclaw-brain/replication.html)
· **Methodology:** [docs/methodology/validation_lab.md](docs/methodology/validation_lab.md)

*Hypothetical research illustration — not investment advice, not performance advertising.*

---

## Methodology & honest limitations

Full methodology lives in [docs/methodology/backfill.md](docs/methodology/backfill.md).
The honest limits, stated up front:

- **The forward record is young.** Forward tracking began 2026-05-20 (forward Day 0 =
  2026-05-18). Roughly 30 trading days of look-ahead-free history exist as of v5.0 — enough
  to display, not enough for statistical significance; the Lab's power meter quantifies this.

- **In-sample is replay reconstruction, not a live backtest.** The In-Sample Event Validation
  panel was materialized after the fact by the replay engine — not emitted live — and the
  evidence-extraction model's training cutoff overlaps that window, so in-sample results
  carry a parametric look-ahead bias and are systematically optimistic.

- **C6 risk channel is partially confirmed.** rareness confirmed OOS 2026-07-06 (22% fire rate, n=9 held-out); sign confirmation pending (elevated arm n=2; accrual live from 2026-07-16).
  The sign confirmation is the gate for Layers 2–10, and it has not been met.

- **C4 macro regime is temporarily frozen as of 2026-05-18** with a staleness disclosure,
  pending macro-engine restoration — its only upstream is the retired v2.3 macro engine, and
  it cannot be price-derived without changing the component's math. C1/C3/C5/C7 read live
  `price_history`; C6/C8/C9 remain point-in-time exact.

- **Extreme labels are rare by construction.** `STRONG_BULLISH` and `BEARISH_WATCH` require
  broad component agreement plus at least one material non-insider event. Day-0 OOS 99th
  percentile sat at +0.531, just below the +0.55 `STRONG_BULLISH` floor. See backfill.md §8.

- **Jun 26 – Jul 3, 2026 outage — disclosed, not patched.** A network outage froze
  price-derived inputs at Jun 25 closes while snapshots continued point-in-time on-box.
  Feeds were restored and re-checked against EDGAR (no missing filings); **no snapshot or
  ledger row was retroactively edited.** The full log is on the Lab page.

- **No table of headline % returns appears in this README.** Hit rates in both panels are
  reported alongside their *n*; small-*n* panels are tagged. See the
  [live validation page](https://yuclawlab.github.io/yuclaw-brain/validation.html) for
  current numbers.

---

## System architecture

```
v3/
  signal/      9-component composite (C1..C9), supply-chain graph, cascade engine
  sources/     SEC EDGAR poller + backfill + Form 4 deterministic parser
  extract/     LLM extraction + SourceLock Guard + prose-first acquisition + live reclassify
  lab/         Validation Lab engines: cohorts, rigor stats, event study, replay bundle
  replay/      Time-machine replay engine
  track/       price_history + outcome_updater + In-Sample Validation panels
  proof/       Verified Research Ledger writer + verifier
  radar/       Change detector + Telegram / Email / Slack adapters
  api/         FastAPI REST server
  mcp/         FastMCP stdio server (7 tools)
  cli/         why / replay / replay-lab / validation / brief / watch / verify / profile
yuclaw/v5/     ClawFactory Layers 0–1: job queue, specialist swarm, grounding verifier
services/      systemd units + guarded worker + heartbeat + network self-heal
sdk/           yuclaw — public SDK (pip install yuclaw)
tools/         replay_lab.py — standalone stdlib reproduction script
docs/methodology/   Methodology + limitations + leak audit + Lab methodology
```

---

## Operations — what's actually running

Read from the live systemd units and `crontab -l`, not aspirational:

- **EDGAR poller** — systemd, always-on; 5-minute submissions sweep across 127 universe
  tickers resolving to 112 distinct EDGAR CIKs (79-name scoring universe + 49-filer Canada
  Resources evidence tier; ETF share classes share issuer-trust CIKs, and one macro
  instrument has no EDGAR CIK).
- **Event worker** — systemd timer, every 15 min, GPU-guarded: 70B extraction + SourceLock +
  live reclassify + prose-first persistence. Exits cleanly when the box is busy.
- **Daily pipeline** — weekdays 17:00 MDT: healthcheck → snapshots → outcomes → radar →
  ledger → page regeneration (landing, validation, **Lab, Open Index Evidence, replay bundle**).
- **Health monitor** — every 30 min: prices, ingestion sweep age, **Lab build age
  (staleness alarm)**, disk; writes an alert file on any failure.
- **Off-box heartbeat** — every 5 min: gist check-in + GitHub Actions dead-man watcher.
- **Network self-heal** — every 5–10 min: link/tailscale recovery; never touches a healthy link.
- **Telegram broadcast** — daily 07:35 MDT signal digest to `@yuclaw_signals`.
- **Research crons** — hourly–nightly: oil intelligence, sentiment archive, swarm debate
  (research-side, orthogonal to the signal pipeline).

---

## Hardware

- **GPU:** NVIDIA Grace Blackwell GB10 (128 GB unified memory), single box.
- **Models resident:** Llama 3.1 70B (Q4_K_M, 42 GB weights, ≈46 GB resident with its
  pinned context budget) + Gemma 4 26B A4B (17 GB weights, ≈20 GB resident) — both served
  by one local Ollama daemon under an explicit GPU mutex + memory-cap contract.
- **All local.** No cloud LLM calls anywhere in the pipeline.

---

## OpenClaw integration

```bash
# As an OpenClaw skill
bash <(curl -s https://raw.githubusercontent.com/YuClawLab/yuclaw-brain/main/yuclaw/openclaw/install.sh)

# Or as an MCP server
python3 yuclaw/openclaw/mcp_server.py     # listens on port 8002
```

---

## Community

| | |
|---|---|
| **Dashboard** | [yuclawlab.github.io/yuclaw-brain](https://yuclawlab.github.io/yuclaw-brain) |
| **Validation Lab** | [validation_lab.html](https://yuclawlab.github.io/yuclaw-brain/validation_lab.html) |
| **Open Index Evidence** | [etf_evidence.html](https://yuclawlab.github.io/yuclaw-brain/etf_evidence.html) |
| **📖 User Guide (PDF)** | [YUCLAW_User_Guide.pdf](https://yuclawlab.github.io/yuclaw-brain/YUCLAW_User_Guide.pdf) |
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

<div align="center">

**Released under the MIT License — free for everyone.**

Built on NVIDIA DGX Spark GB10 · Llama 3.1 70B + Gemma 4 26B via Ollama · Local inference · Git-anchored Verified Research Ledger

`pip install yuclaw`

</div>

## For AI agents & researchers

YUCLAW is the open evidence layer underneath AI research tools.

- **Start here**: [`llms.txt`](https://yuclawlab.github.io/yuclaw-brain/llms.txt)
  and the machine-readable
  [`evidence_index.json`](https://yuclawlab.github.io/yuclaw-brain/evidence_index.json)
  (every page, packet, and protocol with stable URLs and data-through dates).
- **Consume**: evidence packets (derived statistics, event CSVs, engine run
  JSONs, metadata + citation snippets) from `/packets/`; the MCP server
  exposes `why / memo / events / lens / universe / validation / verify` as
  tools with friendly no-backend behavior.
- **Cite**: use the `CITATION.txt` inside any packet; event-level citations
  use event IDs resolvable in the packet CSVs.
- **Verify**: `pip install yuclaw && yuclaw replay-lab` recomputes the
  published Lab statistics from the public bundle; the protocol registry
  (`registry/protocols.jsonl`) is hash-chained and append-only.
- **Rules**: derived statistics only; preserve the disclaimers and the
  frozen implication line when quoting inference; nothing here is advice
  or a recommendation.
