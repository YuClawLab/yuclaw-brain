# Signal Granularity Investigation — resolving the spread-vs-IC puzzle

> **Hypothetical research illustration. Not investment advice, not performance
> advertising, not an offer of any product. Research classifications, not
> recommendations. Descriptive statistics on an internal research universe.**

## Plain-language summary (read this at the airport)

The top-decile cohort beats the bottom-decile cohort, yet the rank-correlation
(IC) of the score is ≈ 0 and the decile spectrum is not monotone. **This is not a
contradiction — it is a measurement artifact of a coarse score.** At every
rebalance about **40 of 79 names share tied composite scores**, because four of
the nine components are flat-lined (constant for all names), so the score lands
on a coarse grid and the tied "middle" of the distribution is statistical noise
that drags the whole-universe IC to zero. When we measure only the names with
*distinct* scores, the in-sample IC flips positive, and the information clearly
**concentrates at the differentiated extremes** (top/bottom names), which is
exactly where the decile spread comes from. **Verdict: Hypothesis A (quantization)
for in-sample; the forward window is too short to call and currently looks flat
(B-consistent).**

## THE VERDICT (one line)

**MIXED, leaning A:** in-sample, coarse score quantization (ties + four constant
components) masks a weak-but-real signal that lives at the differentiated
extremes; the forward window is currently flat/decayed and too small-N to
distinguish A from B.

---

## Phase 1 — Score granularity audit

| Metric | In-sample (13 rebalances) | Forward (18 dates) |
|---|---|---|
| Mean distinct scores / 79 names | **46.6** | 50.8 |
| Mean largest tie-group | **15.0 names** | 13.8 |
| Mean tied names / rebalance | **40.2** | 30.5 |
| Ties: mid-distribution vs extremes | 320 vs 202 | **403 vs 146** |

Roughly **half the universe is tied** at any rebalance, the single largest tied
block is ~14–15 names, and ties sit disproportionately in the **middle** of the
score distribution (≈2:1 in-sample, ≈2.7:1 forward). A 15-name tie cannot be
rank-ordered, so any rank statistic computed over it is pure noise.

**Quantization source — per-component distinct values (mean / max per rebalance):**

| Comp | Component | In-sample | Forward | Verdict |
|---|---|---|---|---|
| C1 | price_momentum | 11.0 / 11 | 9.4 / 39 | granular |
| C2 | volume_confirm | **1.0 / 1** | **1.0 / 1** | **constant (dead)** |
| C3 | sector_velocity | 12.0 / 12 | 11.3 / 20 | granular |
| C4 | macro_regime | **1.0 / 1** | **1.0 / 1** | **frozen (disclosed, 05-18)** |
| C5 | oil_rates_fx | 4.0 / 4 | 4.1 / 7 | coarse |
| C6 | event_impact | 18.4 / 27 | 25.9 / 31 | granular |
| C7 | peer_correlation | 10.0 / 10 | 11.4 / 27 | granular |
| C8 | cascade_effect | **1.0 / 1** | 1.3 / 7 | **near-constant** |
| C9 | model_trust | **1.0 / 1** | 16.9 / 32 | constant in-sample, live forward |

**Finding:** in-sample, **four of nine components (C2, C4, C8, C9) are constant**
across all names — they add a fixed offset to every score and contribute *zero*
differentiation. The live components are themselves coarse (C1≈11, C3≈12, C7≈10,
C5≈4 distinct levels). A sum of a handful of low-cardinality components inevitably
produces a small set of attainable totals → the heavy mid-distribution ties.
Forward, C9 (`model_trust`) has come alive (16.9 distinct), so forward scores are
slightly finer-grained (50.8 distinct) — but C2 and C4 remain dead.

## Phase 2 — Tie-aware statistics

| Statistic | In-sample | Forward |
|---|---|---|
| Spearman mean IC (tie-corrected) | −0.0114 (hit 54%) | −0.0187 (hit 29%) |
| Kendall τ-b mean | −0.0087 (hit 46%) | −0.0081 (hit 29%) |
| **Differentiated-subset IC** (distinct scores only) | **+0.0249** (hit 54%, n≈39) | −0.0081 (hit 43%, n≈45) |

Spearman and Kendall agree the *full-universe* IC is ≈ 0. But the
**differentiated-subset IC flips positive in-sample (−0.011 → +0.025)** when the
tied names are removed — direct evidence that ties are *masking* a weak positive
signal in-sample. Forward, the differentiated subset is still flat/slightly
negative (−0.008), so the masking effect does not rescue the forward window.

## Phase 3 — Decile robustness under 200 random tie-break seeds

| Quantity | In-sample mean [p05, p95], frac_pos | Forward mean [p05, p95], frac_pos |
|---|---|---|
| Monotonicity ρ | **−0.20** [−0.28, −0.13], **0.00** | −0.00 [−0.09, +0.08], 0.51 |
| D1−D10 spread | **+0.0119** [+0.009, +0.015], **1.00** | −0.0012 [—], 0.00 |
| Top-decile cumulative | **+0.272** [+0.225, +0.325], **1.00** | −0.0127 [—], 0.00 |

**Critical finding for the Pro page: the decile charts are NOT tie-break
artifacts.** Across 200 seeds the in-sample D1−D10 spread is **positive in 100% of
seeds** and the top-decile cumulative is **always positive (~27%)** — these are
robust. The non-monotonic ρ is *also* robust (negative in 100% of seeds, never
positive). So the two coexisting facts — "top beats bottom" **and** "spectrum not
monotone" — are both real and stable, not coin-flips. (Forward spread/top-cum
show ~zero variance across seeds because the extreme deciles are tie-free; only
the middle is tied.)

## Phase 4 — Extremes vs middle

| Slice | In-sample IC (hit) | Forward IC (hit) |
|---|---|---|
| Extremes (top 8 + bottom 8) | **+0.070 (62%)** | −0.122 (29%) |
| Middle (~63) | −0.030 (38%) | −0.006 (57%) |
| top8 − bot8 mean return | **+0.0074** | −0.0003 |

**In-sample, information concentrates at the differentiated tails** (extreme IC
+0.070, positive tail return spread) while the tied middle is noise (−0.030).
This is the mechanism behind the puzzle: a coarse score can still separate the
*best* from the *worst* names even when it cannot rank-order the indistinguishable
middle — and whole-universe IC, dominated by that middle, reads ≈ 0. **Forward,
the tails do not carry information** (extreme IC negative, tail spread ≈ 0), so
forward looks genuinely flat.

## Phase 5 — Period attribution

**In-sample** per-rebalance D1−D10 spread (sum = +0.1945):

```
02-18 -0.019  02-25 -0.012  03-04 +0.052  03-11 +0.037  03-18 +0.072
03-25 +0.019  04-01 +0.033  04-08 -0.057  04-15 -0.077  04-22 +0.105
04-29 -0.041  05-06 -0.008  05-13 +0.091
```

The spread is **concentrated and volatile**: the **top 3 weeks supply 61%** of the
cumulative spread (04-22 +10.5pp, 05-13 +9.1pp, 04-15 *−7.7pp*), and weekly
spreads range from −7.7pp to +10.5pp. The net-positive in-sample result is driven
by a handful of large, event-like weeks — not an even, persistent edge. (A dash
of Hypothesis B: period concentration.)

**Forward** per-rebalance spread (sum = −0.0201): bounded in ±3.5pp, net slightly
negative — noise around zero, no concentration of signal.

## Phase 6 — Component-level IC (the v5 Layer 1 input)

**In-sample, ranked by tie-aware Spearman:**

| Rank | Comp | Spearman | Kendall τ-b |
|---|---|---|---|
| 1 | **C1 price_momentum** | **+0.234** | +0.186 |
| 2 | **C7 peer_correlation** | **+0.210** | +0.164 |
| — | C2 / C4 / C8 / C9 | constant (no IC) | — |
| 7 | C3 sector_velocity | −0.058 | −0.046 |
| 8 | C5 oil_rates_fx | −0.058 | −0.046 |
| 9 | **C6 event_impact** | **−0.093** | −0.072 |

**Forward:** C5 +0.063, C7 +0.048, C1 +0.024 weakly positive; C9 −0.005,
C3 −0.047, **C6 event_impact −0.098** negative (C8 +0.166 ignored — only n=1
rebalance had any C8 variation).

**Finding (most actionable):** the **price-derived components C1 (momentum) and
C7 (peer correlation) carry the positive cross-sectional information** (in-sample
IC ~+0.21 to +0.23 — an order of magnitude above the composite). The **evidence
component C6 (event_impact) is consistently *negatively* correlated** with
next-period return in *both* panels (−0.09 to −0.10). The composite `total_score`
buries the informative price components by summing them with (a) four dead/frozen
components and (b) a counter-productive C6 — which, together with quantization, is
why the composite IC ≈ 0.

---

## What the Lab Pro page may truthfully claim — and what it must caveat

**May claim (supported, robust):**
- "In-sample, the top-decile cohort outperformed the bottom-decile cohort, and
  this spread is robust to 200 random tie-break reconstructions of the deciles."
- "Information concentrates at the differentiated extremes of the score."
- The decile-spectrum and cumulative-cohort charts **may stay** — they are not
  tie-break artifacts.

**Must caveat (or the page is misleading):**
- The near-zero Spearman IC and non-monotone spectrum are **substantially driven
  by score quantization**: ~40 of 79 names carry tied composite scores each
  rebalance (four components constant in-sample), so whole-universe rank
  statistics over the tied middle are ≈ 0 *by construction*. The page currently
  reads this as "weak/non-monotonic signal" without disclosing the quantization
  cause — that is technically true but incomplete, and reads as more damning than
  the evidence warrants.
- The forward window remains too short for inference; the early forward spread has
  **decayed toward zero** as the window extended — consistent with small-N luck.
  The page must not imply a forward edge.

## Recommendations

1. **Add a tie / quantization disclosure** to the Lab Pro page (a short note near
   the IC and decile panels): state the tied-name count, that four components are
   constant in-sample, and that rank statistics are therefore degraded — linking
   to this investigation. This converts a confusing "near-zero IC" into an honest,
   well-understood limitation.
2. **Report tie-robust estimators alongside Spearman** on the page: Kendall τ-b
   and the differentiated-subset IC. Showing diff-subset IC = +0.025 (in-sample)
   next to full IC = −0.011 is more honest than either number alone.
3. **Keep the decile charts** (robust under tie-breaking) but annotate that the
   *extremes* drive the spread while the *middle* deciles are tied/indistinct.
4. **Do not change the forward framing** — flat/decayed/too-short is the correct,
   honest read; if anything strengthen the small-N caveat.
5. **For v5 (Layer 1 / the swarm):** the composite is diluting its best inputs.
   - Up-weight or isolate **C1 (price_momentum)** and **C7 (peer_correlation)** —
     they carry the cross-sectional information.
   - Investigate **C6 (event_impact)**: it is *negatively* correlated with
     forward return in both panels. Either its sign/scaling is inverted or the
     evidence-extraction is anti-predictive; this is the single most important
     component to debug.
   - Revive or retire the **dead components** (C2 volume_confirm, C8
     cascade_effect — and C4 macro_regime is the known frozen input). Constant
     components add no information and worsen quantization.
   - Increasing score granularity (more live, finer components) would directly
     reduce ties and de-corrupt the rank statistics.

## Reproducibility

Engine: `v3/lab/granularity_investigation.py` (read-only on `signal_snapshots`
and `price_history`; reuses the cohort engine's point-in-time return convention).
Run `python3 -m v3.lab.granularity_investigation` to regenerate every number
above. Tie-break robustness uses seeded `random.Random(0..199)` for determinism.
Descriptive statistics only; no raw prices are printed or exported.
