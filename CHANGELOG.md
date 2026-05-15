# Changelog

All notable changes to YUCLAW. Format follows [keepachangelog](https://keepachangelog.com/en/1.1.0/).

## [2.3.0] — 2026-05-14

### Added

- **`yuclaw paper` command** — live Alpaca paper-trading path, distinct from
  the `yuclaw trade` campus simulation (which is untouched). Seven safety
  nets: paper-URL guard, validation ping with regenerate-keys guidance,
  `/v2/clock` market-hours check, $10k notional cap with `--force` override,
  first-run consent prompt, append-only audit log at `~/.yuclaw/orders.jsonl`,
  drawdown kill switch (HALT at −3% intraday, LIQUIDATE at −8%).
  ([`6bfe7e3`](../../commit/6bfe7e3), [`d83f102`](../../commit/d83f102))
- **`yuclaw/edge/broker_gateway.py`** — abstract broker interface, contract
  for future Robinhood/IB integrations.
- **`yuclaw/edge/alpaca_gateway.py`** — concrete REST client targeting
  `paper-api.alpaca.markets`. Hard-fails on init against live endpoints.
  Hand-rolled `requests`; no alpaca-py SDK dependency.
- **`yuclaw/edge/risk_gates.py`** — `RiskGate.check(current, baseline)`
  returns `ALLOW`/`HALT`/`LIQUIDATE` based on intraday drawdown against
  Alpaca's `account.last_equity` (auto-resets daily).
- **Live `Tok/s` and `Signal cycle` stat cards** on the dashboard via new
  `yuclaw/utils/inference_speed.py`, replacing the previously hardcoded
  "18.9 TOK/S" and "1.37ms LATENCY" strings. Measurements written to
  `output/inference_stats.json` by the nightly cron.
  ([`43c4cec`](../../commit/43c4cec))
- **`docs/methodology/backtest.md`** — transparency page covering what the
  dashboard's BACKTEST RESULTS card does and does not represent. Linked
  from dashboard footer, README, and DISCLAIMER.
  ([`eee2f84`](../../commit/eee2f84))
- **Aggregator v2.4 — 6-component per-ticker scoring**:
  `factor` 0.05 / `momentum` 0.40 / `ticker_calmar` 0.30 / `rsi_health` 0.15
  / `universe_calmar` 0.05 / `portfolio_risk` 0.05. Top STRONG_BUY tickers
  now have differentiated composites instead of tying at 0.708. Old
  implementation preserved at `yuclaw/modules/signal_aggregator_legacy.py`;
  set `YUCLAW_AGGREGATOR=legacy` to revert.
  ([`928bdae`](../../commit/928bdae))
- **Leveraged-ETF universe blocklist** (`SOXL/SOXS/TQQQ/SQQQ/UPRO/SPXU/`
  `FNGU/FNGD/BOIL/KOLD/NUGT/DUST/LABU/LABD/TNA/TZA`) so 3x/inverse products
  cannot distort momentum-weighted composites.
  ([`a013e2f`](../../commit/a013e2f))
- **Hourly oil intelligence cron** + nightly Nemotron brief split off the
  hourly fast path.
  ([`e3d40fb`](../../commit/e3d40fb), [`19bb90e`](../../commit/19bb90e))
- **Mobile-responsive dashboard CSS** — stack cards under 768px viewport
  for X traffic. Desktop ≥769px unchanged.
  ([`e30987b`](../../commit/e30987b))
- **Standalone `DISCLAIMER.md`** + disclaimer banner on every release notes
  page + repo description tightened (research only — not financial advice).
  ([`89742b1`](../../commit/89742b1), [`54c2b09`](../../commit/54c2b09))

### Changed

- **Renamed "Track Record" → "Backtest Results"** across dashboard card,
  CLI output, README, README_PACKAGE, and institutional one-pager.
  Internal identifiers (`cmd_track`, `'track'` argparse dispatch,
  `output/track_record_*.json` file paths) unchanged.
  ([`f967ab5`](../../commit/f967ab5))
- **EIA oil-inventory query** now uses `facets[series][]=WCESTUS1`
  (U.S. weekly ending stocks of crude oil), where it had been picking
  the first unfiltered record (gasoline blending components imports,
  rendered as a bogus 0.1M bbl). Real inventory now reports ~452.9M.
  ([`26ab23b`](../../commit/26ab23b))
- **Nightly score regeneration cron** (`cron/nightly_score_refresh.sh`)
  now also captures pipeline runtime and Ollama inference speed via
  `yuclaw.utils.inference_speed`.
- **`health_monitor.sh` zombie alert threshold** raised from `>0` to
  `>5` to skip the benign baseline-zombie noise.
  ([`a0523a5`](../../commit/a0523a5))

### Fixed

- **48-day signal-freeze bug** in `signal_aggregator.py` — the upstream
  engines (factor_scan, backtest, risk, screener) were not in cron, so
  `aggregated_signals.json` had been showing March-23 scores dressed up
  with daily-fresh prices. The nightly refresh cron (also added) now
  regenerates scores every weekday after market close.
- **44-day oil-staleness bug** — `oil_engine.py` was not scheduled; the
  oil card on the dashboard had been rendering 2026-03-31 prices for
  six weeks. Now hourly.
  ([`e3d40fb`](../../commit/e3d40fb))
- **60-hour silent dashboard freeze** — `refresh_dashboard.sh` had been
  swallowing `git push` errors via `2>/dev/null`. After a v2.0.0 push
  from a sibling clone shifted `origin/main`, the cron's pushes were
  silently rejected as non-fast-forward and 88 commits piled up locally.
  Fixed by removing the muting and adding `git fetch + rebase --autostash`
  before push, so the cron self-heals from divergence.
  ([`bf12ef8`](../../commit/bf12ef8))
- **`health_monitor.sh` path bug** — was checking
  `/home/zhangd2/Yuclaw/docs/data/dashboard_state.json` (capital Y, the
  rarely-updated publishable clone) instead of `/home/zhangd2/yuclaw/...`
  (lowercase, the cron's working copy). Result: continuous STALE alerts
  against a file nothing was keeping fresh.
  ([`bf12ef8`](../../commit/bf12ef8))
- **`source ~/.yuclaw_env` env-export gap** — six cron wrappers were
  sourcing the env file without `set -a`, so `KEY=value` lines became
  shell-local and never reached Python subprocesses. Standardized to
  `{ set -a; source "$HOME/.yuclaw_env"; set +a; }` across all 7 cron
  scripts.
  ([`bf12ef8`](../../commit/bf12ef8))
- **News-sentiment parser** in `yuclaw/modules/news_sentiment.py` —
  Nemotron's reasoning content was leaking into the dashboard's
  `reason` field as raw thinking text ("We need to output JSON…").
  Parser now tries `content` then `reasoning_content`, attempts JSON
  parse on each, returns a clean "Unable to parse model response"
  fallback on failure.

### Removed

- **Hardcoded "18.9 TOK/S" and "1.37ms LATENCY"** stat cards.
  See "Added — live Tok/s and Signal cycle" above.

### Honest disclosures

- The dashboard's hardcoded `LUNR +14.68% | ASTS +10.44% | DELL +4.01%`
  row was **removed** during this release (see fix `ec444da`). The
  methodology page (`docs/methodology/backtest.md`) documents what the
  BACKTEST RESULTS panel does and does not represent.
- Real-measured Tok/s on the DGX Spark with the local LLM is **~2.2–2.7
  tok/s** on a 50-token generation, **not 18.9**. The previous marketing
  figure is now gone from the dashboard.
- **Model identity correction.** The Ollama tag `nemotron-3-super-local`
  is **Llama 3.1 70B (Q4_K_M, ~42 GB)** with a financial-analyst system
  prompt, **not** Nemotron 3 Super 120B. The actual Nemotron 3 Super 120B
  is wired in `yuclaw/core/router.py` as a dormant OpenRouter fallback
  (the real model is sm_121a-blocked on the vLLM path on this hardware,
  hence the Ollama-served Llama is the active production LLM). All
  public-facing surfaces (README, PyPI long_description, dashboard, repo
  descriptions, org bio) corrected in this release. Audit-log payloads
  schema-upgraded from `'model': 'nemotron-3-super-120B'` (string literal)
  to a structured object capturing both the Ollama tag and actual model
  metadata — see `yuclaw/memory/portfolio_memory_*.py` and
  `yuclaw/finclaw/full_pipeline.py`. Old on-chain anchors continue to
  encode the legacy literal; new anchors use the upgraded schema.

## [2.2.0] — 2026-05-12

See [v2.2.0 release notes](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v2.2.0).

## [2.1.0] — 2026-05-11

See [v2.1.0 release notes](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v2.1.0).

## [2.0.0] — 2026-05-10

See [v2.0.0 release notes](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v2.0.0).
