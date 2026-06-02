<div align="center">

# YUCLAW

**Evidence-first financial research — every signal traced to its filings, verifiable by anyone.**

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/badge/PyPI-yuclaw-orange.svg)](https://pypi.org/project/yuclaw)
[![Agent-native](https://img.shields.io/badge/Agents-MCP%20%C2%B7%20LangChain%20%C2%B7%20LlamaIndex-7c4dff.svg)](#use-it-from-an-agent)

> An open-source research engine that turns SEC filings into **research
> classifications** (never buy/sell calls). Every signal links to its source
> filings, carries an Evidence Quality grade, and is hash-anchored in a public,
> git-anchored ledger so anyone can independently verify it.
>
> **Research and education only. Not investment advice.**

[Quickstart](docs/getting-started/quickstart.md) · [Methodology](docs/methodology/backfill.md) · [Disclaimer](DISCLAIMER.md) · [Public ledger](https://github.com/YuClawLab/yuclaw-trust) · [PyPI](https://pypi.org/project/yuclaw)

</div>

---

## Try it in 3 minutes

```bash
pip install yuclaw
yuclaw demo
```

`yuclaw demo` is a guided, ~3-minute journey on a real, frozen signal: it shows the
structured signal and what drives it, the full research memo with every claim linked to
an SEC filing (accession number + ledger hash), a deterministic point-in-time replay, and
an independent verification against the public ledger. Raw scores are hidden by default —
**research, not numeric recommendations**.

**Zero config** — the demo runs entirely offline against a bundled, frozen capture of the
canonical AMD signal, including the byte-identical ledger-hash check. Running signals for
**any** ticker or date (live `why`/`memo`/`share`/`cascade`) needs a local backend — see
[`docs/v4/backend_setup.md`](docs/v4/backend_setup.md).

```bash
yuclaw why     AMD --as-of 2026-05-20   # structured signal (add --include-score for the composite)
yuclaw memo    AMD --as-of 2026-05-20   # full research memo with evidence trail
yuclaw cascade AMD --as-of 2026-05-20   # supply-chain cascade that propagated into AMD
yuclaw verify  AMD --date 2026-05-20    # re-verify the hash against the public ledger
yuclaw share   AMD --as-of 2026-05-20   # a self-contained, independently-verifiable HTML card
```

The CLI (and the in-process SDK / MCP) is **never metered** — self-hosting is unlimited and
offline. The hosted REST API works anonymously (20 req/day/IP); a key raises the quota to
100/day (`yuclaw keys create`).

---

## What YUCLAW is — and is not

- It produces **research classifications**: `STRONG_BULLISH · BULLISH · NEUTRAL · WATCH ·
  WEAKENING · NEGATIVE_EVENT · BEARISH_WATCH · RISK_ALERT`. There is **no SELL/SHORT/BUY**
  vocabulary — these are research labels, not recommendations.
- Every signal is **explainable and verifiable**: a 9-component anatomy with rationale, an
  evidence trail where each item carries a `source_url` + SEC `accession_number` +
  `ledger_hash`, and a point-in-time `replay_id`.
- A **tamper-evidence record**: signal content hashes are committed to a public,
  **git-anchored** Verified Research Ledger ([yuclaw-trust](https://github.com/YuClawLab/yuclaw-trust)).
  Anyone can recompute a hash from the public filings and confirm a signal was unaltered.
- It is **not** a trading bot, **not** investment advice, and makes **no** zero-knowledge or
  cryptographic proof of strategy correctness — the ledger proves *integrity & timing*, nothing more.

---

## Capabilities

| Surface | What you get |
|---|---|
| **CLI** | `yuclaw demo · why · memo · cascade · share · verify · keys` |
| **REST** | `GET /v1/{why,signal,memo,cascade,verify}/{ticker}` → one unified `ResearchResponse`; `/v1/share`, `/v1/keys/*` |
| **MCP** | `yuclaw_why` (structured), `yuclaw_memo` (markdown) + `yuclaw_universe/validation/verify` — drop into Claude Desktop |
| **Agents** | LangChain `YuclawWhyTool`/`YuclawMemoTool`; LlamaIndex `YuclawRetriever` (each evidence item → a citable node) |
| **SDK** | `yuclaw_py.Client` (local Postgres or hosted API) |

Every surface returns the **same contract** — see [docs/v4/openapi.yaml](docs/v4/openapi.yaml)
and [docs/v4/migration.md](docs/v4/migration.md).

### Use it from an agent
```python
from v4.integrations.langchain_yuclaw import YuclawWhyTool, YuclawMemoTool
agent = create_react_agent(llm, [YuclawWhyTool(), YuclawMemoTool()])

from v4.integrations.llamaindex_yuclaw import YuclawRetriever
nodes = YuclawRetriever().retrieve("AMD")   # one citable node per source filing
```
See [docs/v4/mcp_v2.md](docs/v4/mcp_v2.md), [docs/v4/langchain.md](docs/v4/langchain.md),
[docs/v4/llamaindex.md](docs/v4/llamaindex.md), [docs/v4/api_keys.md](docs/v4/api_keys.md).

---

## Why a bounded ~80-name universe?

YUCLAW tracks **~80 names** (49 equities + 15 sector ETFs + 5 broad ETFs + 10 macro indices),
not the whole market. The thesis is depth over breadth: a bounded universe lets every signal
be backed by **actually-read primary filings** and a curated supply-chain influence graph,
rather than thin coverage across thousands of tickers. The universe is explicit in
`v3/universe.json` and expands deliberately (see Roadmap).

---

## Verification

Every signal's content hash is committed to the public git-anchored ledger. To verify:

```bash
yuclaw verify AMD --date 2026-05-20
# ✓ VERIFIED — recomputed hash matches the public ledger entry (commit 8a67ba7).
```

The `yuclaw share` card embeds the same hash + a "Verify independently →" link, so a
recipient can confirm a signal without trusting us. See
[yuclaw-trust](https://github.com/YuClawLab/yuclaw-trust) for the honest framing of what
hash-anchoring does (integrity & timing) and does not (it is **not** a proof of strategy merit).

---

## Compliance

> **YUCLAW research output. Not investment advice. Past performance does not guarantee
> future results. Signal labels are research classifications, not buy/sell recommendations.**

This notice is the single source of truth (`v4/api/schema.py::COMPLIANCE_NOTICE`, tag
`draft-v0`) and is attached to every signal-data response (including denials). See
[DISCLAIMER.md](DISCLAIMER.md). Full disclosure: the wording is a conservative placeholder
pending a post-funding securities-law review.

---

## Roadmap

- **v4 (shipped):** unified `ResearchResponse`, REST + MCP + LangChain/LlamaIndex, Memo
  Generator, Cascade History View, Share-this-Signal card, API keys + lite metering, the
  3-minute demo, and the compliance regression guard.
- **v4.1 (deferred):** multi-LLM extraction & cross-checking, Whisper audio ingestion, a
  larger universe, hosted share links, and a public bearish/short research lane (carefully
  scoped — still research classifications, never recommendations).

---

## License & contributing

MIT. Issues and PRs welcome at
[github.com/YuClawLab/yuclaw-brain](https://github.com/YuClawLab/yuclaw-brain). The compliance
regression test (`tests/test_compliance_regression.py`) runs on every PR — new endpoints must
keep the compliance block on signal responses.

*Built with local Llama 3.1 70B inference (Ollama) on NVIDIA GB10. Research and education only — not investment advice.*
