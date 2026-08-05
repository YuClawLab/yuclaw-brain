<div align="center">

# How YUCLAW Compares

**One dimension matters here: can a stranger verify the research claims?**

*Different products serve different jobs — scoring apps, pick subscriptions, backtesting engines, and filing assistants all do things YUCLAW doesn't. This table maps the one dimension YUCLAW exists for: the verifiability of published research claims. As of August 2026, based on each product's public documentation. Corrections welcome — [open an issue](../../issues) and we'll fix any cell we got wrong, with credit.*

</div>

| Verifiability dimension | **YUCLAW** | AI stock scorers¹ | Pick subscriptions² | Open algo platforms³ | Signal tournaments⁴ | AI filing assistants⁵ |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Fully open source — pipeline, methodology, and derived data | ✅ Apache-2.0 | ❌ | ❌ | 🔶 engine only | ❌ | ❌ |
| Statistics **pre-registered before computation**, in a public tamper-evident chain | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Publishes adverse results about its own signals** (baseline losses, failed hypotheses, retired ideas — preserved, not deleted) | ✅ | ❌ | 🔶 losing picks visible | n/a⁶ | ❌ | n/a |
| One-command **independent replication** of every published statistic (`yuclaw replay-lab`, exit 0) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Point-in-time forward record, **hash-anchored to public git daily** (retroactive edits break the chain for everyone) | ✅ | ❌ | 🔶 3rd-party calculated⁷ | n/a | 🔶 out-of-sample scored⁸ | n/a |
| Every accepted claim **traces to a primary SEC filing** (accession number + verified excerpt, machine-checked citations) | ✅ | ❌ | ❌ | n/a | ❌ | 🔶 links, not verified |
| **Multiple-testing count published** — expected false positives printed beside results | ✅ | ❌ | ❌ | ❌ | ❌ | n/a |
| **Robustness grids published** — where results *break*, by regime, horizon, era | ✅ | ❌ | ❌ | ❌ | ❌ | n/a |
| Sample anatomy disclosed (effective independent observations, story concentration) | ✅ | ❌ | ❌ | ❌ | ❌ | n/a |
| Research classifications only — **no buy/sell recommendations, ever** | ✅ | ❌ scores imply action | ❌ explicit picks | n/a | n/a | 🔶 varies |
| **No performance advertising** (no win rates, no "+X% alpha" marketing) | ✅ | ❌ | ❌ | ✅ | 🔶 | ✅ |
| Machine-readable evidence layer for AI agents (`llms.txt`, evidence index, MCP tools) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| All inference on **sovereign local hardware** — your queries never train someone's cloud | ✅ | ❌ | n/a | 🔶 local option | ❌ | ❌ |
| Cost to verify everything above | **$0** | — | — | — | — | — |

<div align="center">

**The row that matters most is the second one.** Everyone's methodology can look rigorous *after* the results are in. Only a specification hash-locked into a public chain *before* the data arrives proves the criteria never moved. Check ours:

</div>

```bash
curl -sO https://raw.githubusercontent.com/YuClawLab/yuclaw-brain/main/registry/protocols.jsonl
curl -sO https://raw.githubusercontent.com/YuClawLab/yuclaw-brain/main/tools/yuclaw_protocol_registry.py
python3 -c "import yuclaw_protocol_registry as r; print('chain OK:', r.Registry('protocols.jsonl').verify_chain())"
```

---

### Fair notes — competitors' real strengths, stated plainly

**¹ AI stock scorers** (e.g., Danelfin, Kavout, Prospero-class): polished products with broad coverage (thousands of tickers), daily updates, and accessible pricing; Danelfin's explainable-factor display is genuinely better than a black box. Their published performance figures are predominantly backtested and self-reported.
**² Pick subscriptions** (e.g., Alpha Picks-class): to their credit, some maintain live track records calculated by third parties with losing positions visible — meaningfully more honest than backtest marketing. Methodology remains closed; the product is explicit recommendations.
**³ Open algo platforms** (e.g., QuantConnect LEAN, backtrader, vectorbt): LEAN is real open source (Apache 2.0) with excellent point-in-time backtesting infrastructure. They are *tools for your private research* — the platform publishes no research record of its own to verify, which is why several rows read n/a rather than ❌.
**⁴ Signal tournaments** (Numerai): genuine out-of-sample scoring of submitted signals is a real epistemic contribution. The meta-model, the signals, and the evidence basis remain closed.
**⁵ AI filing assistants** (AlphaSense-class, terminal AI): strong retrieval and summarization over filings; claims are sourced by link but not statistically disciplined or independently replicable.
**⁶ n/a** means the dimension doesn't apply to that product category — absence of a research record is not a flaw in a backtesting engine.
**⁷** Third-party calculation is a real control, but readers cannot re-derive the numbers themselves from published data.
**⁸** Out-of-sample scoring exists, but the record is not independently reconstructible by outsiders.

---

<div align="center">

*YUCLAW is research and education only — not investment advice. Signal labels are research classifications, not recommendations. Our own forward record is young; most of our forward statistics are honestly labeled DESCRIPTIVE or UNDERPOWERED at current sample sizes — that's printed on every page, which is rather the point.*

**[yuclaw.ca](https://yuclaw.ca)** · **[Validation Lab](https://yuclaw.ca/validation_lab.html)** · **[User Guide](https://yuclaw.ca/YUCLAW_User_Guide_v5.1.pdf)** · `pip install yuclaw`

*Comparison table v1.2 · August 2026.*

</div>
