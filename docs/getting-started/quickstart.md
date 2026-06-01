# YUCLAW — Getting Started

A few-minute introduction to evidence-first financial research. **For research and
education only — not investment advice.**

---

## Try it in 3 minutes

Two commands from nothing:

```bash
pip install yuclaw
yuclaw demo
```

`yuclaw demo` is a guided journey on a real, frozen signal: the structured signal and its
drivers, the full research memo with every claim linked to an SEC filing
(`accession_number` + `ledger_hash`), a deterministic point-in-time replay, and an
independent verification against the public, git-anchored Verified Research Ledger.

---

## What YUCLAW is

- An **open-source research engine** for a bounded ~80-name universe (49 equities, 15
  sector ETFs, 5 broad ETFs, 10 macro indices — see `v3/universe.json`).
- It reads **SEC filings** (8-K / 10-Q / 10-K / 6-K), extracts material events with a local
  LLM, and combines a 9-component anatomy into a **research classification** — never a
  buy/sell call.
- Every signal is **traceable** (source filing + accession per evidence item) and
  **verifiable** (content hash committed to a public git-anchored ledger).

## What YUCLAW is not

- **Not** a trading bot — it produces research classifications; what you do is your decision.
- **Not** investment advice, and **not** a recommendation to buy, sell, or hold anything.
- **Not** a cryptographic/zero-knowledge proof of strategy correctness — the ledger proves a
  signal's **integrity and timing**, nothing more.

---

## The core commands

```bash
yuclaw why     AMD --as-of 2026-05-20   # structured signal: label + grade + 9 components + evidence
yuclaw why     AMD --as-of 2026-05-20 --include-score   # opt in to the raw composite score
yuclaw memo    AMD --as-of 2026-05-20   # a full Markdown research memo
yuclaw cascade AMD --as-of 2026-05-20   # supply-chain cascade that propagated into AMD
yuclaw verify  AMD --date 2026-05-20    # re-verify the integrity hash against the public ledger
yuclaw share   AMD --as-of 2026-05-20   # generate a self-contained, verifiable HTML card
```

Every response carries a required compliance block and explicit limitations; a missing
ticker returns a `status: "no_data"` envelope, never a fabricated signal. Signal labels are
limited to: `STRONG_BULLISH · BULLISH · NEUTRAL · WATCH · WEAKENING · NEGATIVE_EVENT ·
BEARISH_WATCH · RISK_ALERT` (no SELL/SHORT/BUY).

---

## Agents, REST, and MCP

- **MCP** (Claude Desktop, etc.): `python3 -m v3.mcp.server` exposes `yuclaw_why` and
  `yuclaw_memo`. See [../v4/mcp_v2.md](../v4/mcp_v2.md).
- **LangChain / LlamaIndex**: ultra-thin tools + a citing retriever. See
  [../v4/langchain.md](../v4/langchain.md) and [../v4/llamaindex.md](../v4/llamaindex.md).
- **REST**: `GET /v1/why/{ticker}` and friends return one unified `ResearchResponse`. The
  hosted API works anonymously (20 req/day/IP); request a key for 100/day. See
  [../v4/api_keys.md](../v4/api_keys.md).

---

## Verify it yourself

```bash
yuclaw verify AMD --date 2026-05-20
```
Recomputes the signal's content hash from the public SEC filings and compares it to the
entry in the public git-anchored ledger ([yuclaw-trust](https://github.com/YuClawLab/yuclaw-trust)).
Anyone can re-run this — that is the point.

---

**Compliance:** YUCLAW research output. Not investment advice. Past performance does not
guarantee future results. Signal labels are research classifications, not buy/sell
recommendations. See [../../DISCLAIMER.md](../../DISCLAIMER.md).
