# YUCLAW v5.0.0 — Evidence-First Financial Research (L0 + L1 in production)

> Research and education only. Not investment advice. Research classifications,
> not recommendations. Past results — in-sample or forward-tracked — do not
> predict future performance.

## What v5.0 is

Layers 0 and 1 of the evidence engine are complete and running in production:
every signal traces to SEC filings through a deterministic, replayable pipeline,
and every public statistic reproduces with one command.

- **10 event-type extraction specialists** (earnings, guidance, M&A, financing,
  governance, regulatory, insider, macro, geopolitical, earnings-quality) over a
  model-agnostic worker — currently Gemma 4 26B MoE, selected by A/B
  (commits `1b2b2e07`, `745df911`, `21bdbc17`).
- **Live reclassify rescue** at ingestion — the corrected-type layer reproduces
  the stored corpus exactly: **97/97** (commit `67487eb2`,
  `docs/ingestion_live_reclassify.md`).
- **Prose-first ingestion, live**: the production worker persists exhibit /
  MD&A prose so the swarm reads filing prose, not XBRL cover soup. Measured on
  the L1 corpus: **grounding 0.52 → 0.75, citation fidelity 0.66 → 0.85**
  (fix `f130983e`, production port `b1b153a0`). Definitions are the
  deterministic verifier's rubric, footnoted on the Lab.
- **C6 risk channel**: rare-by-construction confirmed out-of-sample (22% fire
  rate, n=9 held-out); sign positive at n=2 elevated — accruing.
  (`c28f8542` recalibration, `aba72e89` OOS re-run.)

## The public evidence surface

The **[Signal Validation Lab](https://yuclawlab.github.io/yuclaw-brain/validation_lab.html)**
is the release's proof page, regenerated daily after U.S. market close:

- rolling record with the in-sample → forward regime boundary marked (statistics
  never blended across it);
- **reproducibility bundle + one-command replay** — `pip install yuclaw &&
  yuclaw replay-lab` (or the standalone stdlib script) recomputes every
  statistic and re-derives every ledger hash root;
- Panel 4: evidence-qualified candidate cohort (forward-only by construction);
- **maturity gates: 1–3 passed, 4–6 not yet** — stated on the page;
- an honest-reading box that says plainly what is and is not proven.

## Infrastructure (numbers/status only)

- systemd-supervised ingestion stack (poller always-on; worker GPU-guarded) — live
- GPU mutex (`gpu-lock`) + memory-cap contract (MemoryMax=100G scope) — live
- off-box dead-man heartbeat (gist + GitHub Actions watcher, 5-min cadence) — live
- network link self-heal (Jun-26 root cause closed, 1 attempt/30min, never
  touches a healthy link) — live
- health watchdog every 30 min (prices, ingestion sweep, Lab build age, disk) — live

## Roadmap (gated)

**Layers 2/3 are explicitly gated: the gate is out-of-sample sign confirmation
for the risk channel**, which is pending (elevated arm n=2 and accruing).
Forward alpha is unproven — in the Lab's own words: at current sample sizes, no
forward spread, IC, or alpha is statistically significant at the 5% level once
overlap is corrected. Research-only.

## What v5.0 does NOT claim

- No proven forward alpha.
- No investable methodology — nothing here is a strategy, a portfolio, or advice.
- No trade-direction language anywhere in the public surface; research
  classifications only.

---
Install: `pip install yuclaw` · Reproduce: `yuclaw replay-lab` ·
Ledger: [yuclaw-trust](https://github.com/YuClawLab/yuclaw-trust) ·
Lab: [validation_lab.html](https://yuclawlab.github.io/yuclaw-brain/validation_lab.html)
