---
name: yuclaw
version: 3.0.0
description: Evidence-first financial research — composite signals tied to SEC filings, time-machine replay, and a git-anchored Verified Research Ledger. Research/education only — not investment advice.
license: MIT
homepage: https://github.com/YuClawLab/yuclaw-brain
---

> **Disclaimer — read before using.** YUCLAW is a research and education tool. It is **not** investment advice. Signal labels (`STRONG_BULLISH`, `BULLISH`, `NEUTRAL`, `WATCH`, `WEAKENING`, `NEGATIVE_EVENT`, `BEARISH_WATCH`, `RISK_ALERT`) are **research classifications**, not buy/sell recommendations — and YUCLAW deliberately publishes **no `SELL` or `SHORT` label**. Past results — in-sample or forward-tracked — do not predict future performance. YUCLAW is **not a registered investment adviser**.

## What YUCLAW is

YUCLAW is an open-source financial research platform. Its v3.0 release is built around an **evidence layer**: every composite signal traces back to a source SEC filing or deterministic supply-chain cascade. There is no opaque "model said so" — the SDK / API / MCP tools surface the raw events, with `available_as_of` timestamps and SEC archive URLs.

Three pillars:

1. **Composite scoring (C1–C9).** Nine independent components (momentum, sector velocity, macro regime, event impact, cascade, etc.) combine via a locked confidence-weighted formula. Component C6 (event impact) carries the highest weight — by design.
2. **Time-machine replay.** Any signal can be re-derived as of a past date with point-in-time filtering: only events with `available_as_of ≤ as_of` feed the computation. A leak audit confirms zero future-event leakage.
3. **Verified Research Ledger.** Each day's published signals have their content hashes appended to a JSONL file in a public git repo (`yuclaw-trust`). Anyone can call `verify` and confirm a snapshot hasn't been edited since publication.

## Three ways to connect

| surface | install | usage |
|---|---|---|
| **Python SDK** | `pip install yuclaw-evidence` | `Client(source="postgres" or "api")` |
| **REST API** | hosted at YuClawLab (or self-host on `:8088`) | `GET /signal/{ticker}` etc. |
| **MCP server** | `python3 -m v3.mcp.server` (stdio) | 7 tools in any FastMCP-compatible client |

All three surfaces share the same query layer — they cannot diverge.

## The seven capabilities

1. **`signal(ticker)`** — latest composite signal label + score + 9 component scores.
2. **`why(ticker)`** — signal plus the top-N evidence events that informed it, each with `event_type`, `magnitude`, `direction`, `raw_excerpt`, and `source_url` (SEC archive link).
3. **`replay(ticker, date)`** — point-in-time signal at the end of `date` (YYYY-MM-DD).
4. **`validation()`** — two panels: in-sample replay (Feb–May 2026) and forward-tracking ledger (live since 2026-05-20). Returns hit rates by horizon and excess return vs SPY.
5. **`events(ticker, since)`** — raw evidence events (insider trades, M&A, earnings, etc.) with timestamps and source URLs.
6. **`universe()`** — the 79 tickers v3.0 tracks.
7. **`verify(ticker, date)`** — Verified Research Ledger integrity check; returns `VERIFIED` / `INTEGRITY_FAILURE` / `NOT_FOUND`.

## Worked examples

### `yuclaw why NVDA`

```text
NVDA composite score: +0.312  (signal label: NEUTRAL)

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
              CASCADE d1 via HPE→NVDA(supply,w=0.15) from HPE: H3C divestiture
              source: https://www.sec.gov/Archives/edgar/data/1645590/...

Compliance: Research only. Not financial advice.
```

### Time-machine replay

```python
>>> client.replay("AMD", date="2026-03-01")
{"label": "WATCH", "score": 0.079, ..., "compliance": {"not_advice": True, ...}}
```

### Verified Research Ledger check

```text
$ python3 -m v3.cli verify NVDA --date 2026-05-20
OK  VERIFIED: signal unaltered since ledger commit   NVDA @ 2026-05-20
    ledger commit:   2379ac8  (2026-05-20 12:43:23 -0600)
    ledger label:    NEUTRAL  (current: NEUTRAL)
    content_hash:    5e1897907999...
Verifies record integrity and timing — not investment merit.
```

## Methodology + caveats

The full methodology — data window, LLM training cutoff (Llama 3.1 70B, December 2023, well before the 2026 backfill window), in-sample reconstruction limits, hit/return definitions — lives in [`docs/methodology/backfill.md`](https://github.com/YuClawLab/yuclaw-brain/blob/v3.0-evidence/docs/methodology/backfill.md).

The single most important caveat: **the in-sample event validation panel was reconstructed via point-in-time replay, with market components (C1/C3/C4/C5/C7) running at 0.3 confidence** because the upstream market-data cache holds only the latest snapshot. The in-sample numbers therefore primarily reflect the **evidence layer** (C6/C8/C9). v3.1 will land historical market data so the full composite runs point-in-time.

## Locked vocabulary

The only labels YUCLAW publishes — anywhere, in any surface, ever — are:

```
STRONG_BULLISH · BULLISH · NEUTRAL · WATCH · WEAKENING · NEGATIVE_EVENT · BEARISH_WATCH · RISK_ALERT
```

There is no `SELL`. There is no `SHORT`. The SDK, the REST API, and the MCP server all run the same `_validate_label()` check before any signal leaves the system — anything outside the locked set is treated as a bug and surfaces an error.

## License

MIT. See [`LICENSE`](https://github.com/YuClawLab/yuclaw-brain/blob/main/LICENSE).

---

> **Disclaimer.** Research and education only. Not investment advice. Signal labels are research classifications, not buy/sell recommendations. YUCLAW is not a registered investment adviser. Past results — in-sample or forward-tracked — do not predict future performance.
