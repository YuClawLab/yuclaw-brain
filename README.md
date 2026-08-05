<div align="center">

# YUCLAW

**The open evidence layer for financial research — every claim carries its own audit trail.**

Statistics pre-registered before data. Adverse results published. Every number reproducible by strangers.

![PyPI](https://img.shields.io/pypi/v/yuclaw)
![License Apache--2.0](https://img.shields.io/badge/License-Apache--2.0-green)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![Ledger git-anchored](https://img.shields.io/badge/Ledger-git--anchored-blue)

</div>

**Verify us before you read us — three commands:**

```bash
pip install yuclaw && yuclaw replay-lab     # rebuilds every published Lab statistic — exit 0 = reproduced
curl -sO https://raw.githubusercontent.com/YuClawLab/yuclaw-brain/main/registry/protocols.jsonl   # the protocol chain — statistics locked BEFORE computation, tamper-evident
make replicate                              # full clean-environment replication
```

**[How we compare →](COMPARISON.md)**

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
[📖 User Guide (EN)](https://yuclaw.ca/YUCLAW_User_Guide_v5.1.pdf) ·
[📖 Guide (FR)](https://yuclaw.ca/YUCLAW_Guide_Utilisateur_v5.1_FR.pdf) ·
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
commands work anywhere with no backend. At the v5.1.0 release, `replay-lab`
ran from a fresh venv with nothing but `pip install yuclaw` and reproduced
**33 daily ledger roots exactly (2,926 leaf hashes recomputed)** and every
published statistic, exit 0. It exits non-zero on any mismatch.

---

## What shipped in v5.1

| Component | Measured / Shipped | Status |
|---|---|---|
| **Full command surface on PyPI** | `events` / `lens` / `export` / `memo` subcommands ship in the published wheel (previously main-checkout only) | Live |
| **Protocol registry** | hash-chained, append-only pre-registration ledger; 60+ entries; supersession-only edits; chain-verified in the daily gate suite | Live |
| **Public engine panels** | evidence structure, context robustness, evidence lifecycle — derived from run artifacts, regenerated daily | Live |
| **Champion-challenger baselines** | pre-registered; the persistence baseline finished ahead of the composite at the primary horizon at current n — published as measured | Published |
| **Label calibration** | pooled consistency with CIs; panels state where directional meaning is not yet demonstrated | Published |
| **SMH + XLK evidence lenses** | both passed the published admission standard; foreign-filer 6-K/20-F/40-F prose paths live | Live |
| **Layer 0/1 evidence swarm** | 10 event-type specialists on local models; prose-first ingestion (grounding 0.52 → 0.75, citation fidelity 0.66 → 0.85) | Live |
| **C6 risk channel** | rareness confirmed OOS (22.2% fire rate, n=9 held-out); sign unconfirmed — first read under the v2 protocol printed INCONCLUSIVE (2026-07-30); accrual continues | Partial — sign pending |
| **Layers 2–10** | roadmap — **explicitly gated on out-of-sample sign confirmation** for the risk channel | Gated, not built |
| **Canada Resources evidence tier** | 49 SEC filers across XEG/ZEO/GDX/URNM; 6-K/40-F prose path; evidence-only, never scored ([live page](https://yuclaw.ca/canada_resources.html)) | Live |

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
broad ETFs + macro instruments) plus a 53-filer evidence tier — ingested and
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
  panel was materialized after the fact by the replay engine, and the
  extraction model's training cutoff overlaps that window, so in-sample
  results carry a parametric look-ahead bias and are systematically optimistic.
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

---

## Community

| | |
|---|---|
| **Live site** | [yuclaw.ca](https://yuclaw.ca) |
| **Validation Lab** | [validation_lab.html](https://yuclaw.ca/validation_lab.html) |
| **SMH Evidence Lens** | [etf_evidence.html](https://yuclaw.ca/etf_evidence.html) |
| **XLK Evidence Lens** | [xlk_evidence.html](https://yuclaw.ca/xlk_evidence.html) |
| **📖 User Guide (EN / FR)** | [EN](https://yuclaw.ca/YUCLAW_User_Guide_v5.1.pdf) · [FR](https://yuclaw.ca/YUCLAW_Guide_Utilisateur_v5.1_FR.pdf) |
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

YUCLAW is the open evidence layer underneath AI research tools.

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
