# yuclaw-py

Python SDK for the [YUCLAW](https://github.com/YuClawLab/yuclaw-brain) open-source financial intelligence platform.

> **Disclaimer.** YUCLAW research output. Not investment advice. Past performance does not guarantee future results. Signal labels are research classifications, not buy/sell recommendations.

## Install

```bash
pip install yuclaw-py
# or, with notebook extras (matplotlib + jupyter for `04_backtest_analysis`):
pip install "yuclaw-py[notebooks]"
```

## Quickstart

```python
import yuclaw_py

# Two access modes:
#   source="postgres" — direct local read (requires the v3.0 stack)
#   source="api"      — REST API (Day 11+, hosted at YuClawLab)
client = yuclaw_py.Client(source="postgres", dsn="dbname=yuclaw_events")

# Latest composite signal for a ticker
sig = client.signal("NVDA")
print(sig["label"], sig["score"])
#> NEUTRAL 0.312

# Full `why` — signal + ranked evidence events with source URLs
why = client.why("NVDA")
for ev in why["evidence"]:
    print(ev["event_type"], ev["raw_excerpt"][:60])

# Point-in-time replay (must already be materialized via `python3 -m v3.cli replay`)
hist = client.replay("AMD", date="2026-03-01")
print(hist["label"], hist["score"])

# Backtest + Forward-tracking ledger as pandas DataFrames
panels = client.backtest()
panels["backtest"].head()
panels["forward"].head()

# Raw events for a ticker
df = client.events("AMD", since="2026-05-01")

# Universe
client.universe()  # list of 79 tickers
```

## What you get

Every signal-bearing return carries a `compliance` dict:

```python
{"not_advice": True, "research_only": True, "not_registered_adviser": True}
```

— and the public vocabulary is strictly:
`STRONG_BULLISH`, `BULLISH`, `NEUTRAL`, `WATCH`, `WEAKENING`, `NEGATIVE_EVENT`, `BEARISH_WATCH`, `RISK_ALERT`.

No `SELL`, no `SHORT`. Anywhere.

## Starter notebooks

`sdk/notebooks/` ships five self-contained notebooks:

1. `01_quickstart.ipynb` — install, connect, first signal
2. `02_evidence_layer.ipynb` — trace a signal to its SEC filings
3. `03_time_machine.ipynb` — replay across dates, verify point-in-time integrity
4. `04_backtest_analysis.ipynb` — load the two panels, plot hit rates (with in-sample caveats)
5. `05_signal_radar.ipynb` — change detection + custom watchlist alert

## License

MIT — see `LICENSE`.
