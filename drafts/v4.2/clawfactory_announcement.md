# ClawFactory (v5) — Announcement (DRAFT for review)

ClawFactory is YUCLAW v5: an **eleven-layer evidence-extraction architecture**,
cross-AI design-reviewed (ChatGPT + Gemini). Target: **July 1**.

**Layer 0 — Evidence Job Queue / Orchestrator — is complete and public** on
branch [`v5-layer0-foundation`](https://github.com/YuClawLab/yuclaw-brain/tree/v5-layer0-foundation):
a durable, observable, multi-node-capable PostgreSQL `SKIP LOCKED` job queue with
a worker that runs real SEC-filing extraction end-to-end. Proven on a **281-filing
real-data backfill: 281/281 succeeded, 0 dead-letter**, with parallel-claim
(SKIP LOCKED), retry, and dead-letter paths all validated. Layers 1–10 are the
roadmap below — designed, not yet built.

## The eleven layers

- **Layer 0 — Evidence Job Queue / Orchestrator.** Durable multi-node job queue + worker; **built and proven** (281/281 real filings).
- **Layer 1 — Dynamic Specialist Swarm.** Planned: a swarm of specialist extractors that adapt to each filing type.
- **Layer 2 — Executable Evidence Tokens.** Planned: every extracted claim becomes a re-runnable, independently verifiable token.
- **Layer 3 — SDI-Mx Disagreement Index.** Planned: a structured index of disagreement across specialists and sources.
- **Layer 4 — Continuous Self-Audit.** Planned: ongoing automated validation of every extraction against its source text.
- **Layer 5 — Streaming Mesh.** Planned: real-time streaming of evidence between layers and nodes.
- **Layer 6 — Sovereign ClawFactory Grid.** Planned: a self-hostable, multi-node extraction grid.
- **Layer 7 — Causal Knowledge Graph.** Planned: links events into a navigable causal graph.
- **Layer 8 — Methodology Transparency Suite.** Planned: public, reproducible methodology tooling.
- **Layer 9 — Evidence Marketplace.** Planned: an open exchange for evidence artifacts.
- **Layer 10 — Multilingual Evidence Layer.** Planned: extends evidence extraction beyond English-language filings.

## Three locked values

1. **Research-only positioning.** ClawFactory produces research and education
   output, never investment advice and never trade recommendations.
2. **Public-git-ledger anchoring only.** Tamper-evidence comes from a public git
   ledger ([yuclaw-trust](https://github.com/YuClawLab/yuclaw-trust)) — **no
   on-chain / blockchain anchoring**.
3. **Fully open-source, MIT-licensed.**

---

*Research and education only. Not investment advice. Signal labels are research
classifications, not buy/sell recommendations.*
