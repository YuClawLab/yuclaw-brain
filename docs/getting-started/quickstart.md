# YUCLAW v3.0 — Quickstart

> Research and education only. Not investment advice. Signal labels are research classifications, not buy/sell recommendations. YUCLAW is not a registered investment adviser.

---

## What you get in five minutes

A composite signal for any ticker in the YUCLAW universe (~80 names — equities, sector ETFs, broad ETFs, macro), plus the chain of SEC filings and supply-chain cascades that justify it.

The signal is built from nine independent components (momentum, sector velocity, macro regime, oil/rates/FX, event impact, peer correlation, supply-chain cascade, model trust, volume). Every score traces to publicly verifiable evidence (SEC EDGAR URLs, content hashes anchored in the public [Verified Research Ledger](https://github.com/YuClawLab/yuclaw-trust)).

## Install

```bash
pip install yuclaw
```

The package distribution is named `yuclaw`; the import is `yuclaw_py`. (Common pattern — `pip install Pillow` → `import PIL`.)

## Core commands

```bash
python3 -m v3.cli why TICKER
#   composite signal label + score + 9-component breakdown
#   + the top-5 evidence events with SEC source URLs

python3 -m v3.cli replay TICKER --date YYYY-MM-DD
#   point-in-time signal as it would have looked at the end of that date
#   (only data available on or before that date feeds the composite)

python3 -m v3.cli validation
#   In-Sample Event Validation panel + Forward Tracking Ledger
#   hit rates always shown alongside their n; small samples tagged "preliminary"

python3 -m v3.cli verify TICKER --date YYYY-MM-DD
#   verify a published signal against the git-anchored Verified Research Ledger
#   confirms record integrity and timing — not investment merit

python3 -m v3.cli brief
#   personalized digest based on ~/.yuclaw/profile.json (watchlist, alert threshold)
```

## SDK

```python
import yuclaw_py

client = yuclaw_py.Client(source="postgres")   # local Postgres mode
# or
client = yuclaw_py.Client(source="api", base_url="http://localhost:8088")

sig = client.signal("NVDA")
print(sig["label"], sig["score"])                 # e.g. NEUTRAL  0.295

why = client.why("NVDA")
for ev in why["evidence"]:
    print(ev["event_type"], ev["raw_excerpt"][:80], ev["source_url"])

panels = client.validation()
panels["in_sample"]   # pandas DataFrame
panels["forward"]
```

Every signal-bearing return carries a `compliance` dict (`{not_advice, research_only, not_registered_adviser}`).

## Sentiment vocabulary

YUCLAW publishes one of the following labels — and only these — for any signal:

```
STRONG_BULLISH · BULLISH · NEUTRAL · WATCH · WEAKENING · NEGATIVE_EVENT · BEARISH_WATCH · RISK_ALERT
```

There is no `SELL` and no `SHORT` label. The SDK's `_validate_label()` is invoked on every signal-bearing return; a non-public label raises `AssertionError`.

## Surfaces

| surface | URL / how |
|---|---|
| Live landing page | <https://yuclawlab.github.io/yuclaw-brain/> |
| In-Sample Validation + Forward Tracking | <https://yuclawlab.github.io/yuclaw-brain/validation.html> |
| Verified Research Ledger (git-anchored) | <https://github.com/YuClawLab/yuclaw-trust> |
| Methodology | [`docs/methodology/backfill.md`](../methodology/backfill.md) |
| REST API terms | [`docs/API_TERMS.md`](../API_TERMS.md) |
| MCP server | [`v3/mcp/README.md`](https://github.com/YuClawLab/yuclaw-brain/blob/main/v3/mcp/README.md) — 7 tools, stdio transport |
| Issues + source | <https://github.com/YuClawLab/yuclaw-brain> |

## Honest limits at launch

- The **in-sample validation panel** was reconstructed via point-in-time replay, not emitted live. Five of nine components (C1 momentum, C3 sector, C4 macro, C5 oil/rates/FX, C7 peer) run at 0.3 confidence on historical replays because the upstream market-data cache holds only the latest snapshot. The in-sample numbers primarily reflect the evidence layer (C6 events / C8 cascade / C9 model trust). v3.1 will land historical market data so the full composite runs point-in-time.
- The **Forward Tracking Ledger** begins at the launch-day cron run. It will look sparse for the first few weeks (1-day outcomes mature next trading day; 5-day a week later; 20-day a month later). This is correct, not a bug.
- Extreme labels (STRONG_BULLISH, BEARISH_WATCH) are rare by construction — they require broad component agreement plus at least one material non-insider event. See `docs/methodology/backfill.md` §8.

---

> Research and education only. Not investment advice. Signal labels are research classifications, not buy/sell recommendations. YUCLAW is not a registered investment adviser. Past results — in-sample or forward-tracked — do not predict future performance.
