# C6 Evidence-Component Deep Dive — why event_impact is negatively correlated with near-term return

> **Hypothetical research illustration. Not investment advice, not performance
> advertising, not an offer of any product. Research classifications, not
> recommendations. Descriptive statistics on an internal research universe.**
>
> *Terminology note: "insider-sell" / `INSIDER_SELL` below refers to the factual
> SEC Form 4 event category (a corporate insider's disclosed share disposal). It
> is a descriptive event-type label, not a recommendation or a trade direction.*

## Plain-language summary (read this at the airport)

C6 is **not buggy** — its sign and aggregation reproduce exactly when recomputed
by hand. C6's negative correlation with near-term return is real but **explained**:
the event feed is **93% insider-sell events**, and insider-sell-heavy names tend
to *bounce* over the following 1–8 weeks (a well-documented short-term reversal),
which drags C6's unconditional return-correlation negative. Two findings rescue
the component: (1) when there is a **material non-insider event** (8-K / M&A /
guidance), C6's correlation with return is strongly **positive (+0.36)** — the
evidence works as designed but is drowned out by the insider mass; and (2) C6 is
a genuine **risk predictor** — low C6 reliably precedes **higher realized
volatility (IC −0.32)** and **deeper drawdowns (IC +0.22)**. So C6's most
defensible role is a **risk gate, not a near-term return signal.**

## THE VERDICT (one line)

**NOT a bug. Mixed mechanism — (i) insider-sell short-term contrarian drag on the
return-IC, (ii) C6 is correctly-signed *positive* for material non-insider events
and once conditioned on momentum, and (iii) C6 is a real risk gate (volatility /
drawdown) rather than a near-term return alpha.** Re-weighting is **deferred** to
a forward-validated, three-AI-reviewed design (see closing section).

---

## 1. Sign / aggregation audit — bug ruled out

For five names we re-derived C6 from its linked events
(`impact = direction × magnitude × confidence × recency`, insider sum clamped to
±0.5, `tanh` squash) and compared to the stored `c6_event_impact`:

| Name | Date | Events | insider sum → capped | other sum | recomputed | stored | match |
|---|---|---|---|---|---|---|---|
| AMD | 2026-02-18 | 5× INSIDER_SELL | −0.621 → **−0.500** | 0 | −0.4621 | −0.4621 | ✅ |
| AAPL | 2026-04-08 | 5× INSIDER_SELL | −2.286 → **−0.500** | 0 | −0.4621 | −0.4621 | ✅ |
| NVDA | 2026-03-11 | 2× INSIDER_SELL, 1× EXEC_CHANGE | −1.899 → −0.500 | 0 | −0.4621 | −0.4621 | ✅ |
| INTC | 2026-04-29 | 1× EXEC_CHANGE | 0 | −0.432 | −0.4071 | −0.4071 | ✅ |
| MSFT | 2026-02-18 | 1× INSIDER_BUY | +0.396 | 0 | +0.3766 | +0.3766 | ✅ |

**All five reproduce to <1e-3.** The convention is correct and intentional:
negative-direction events (insider sells, guidance cuts) produce negative C6;
positive events produce positive C6. AMD/AAPL show the documented behaviour where
a Form-4 cluster saturates the insider cap at exactly `tanh(−0.5) = −0.4621`.
**There is no sign or aggregation bug.**

## 2. Horizon sweep — the drag is short-horizon and reverses

C6 IC vs forward return at increasing horizons (in-sample, tie-aware):

| Horizon | mean IC | Kendall τ-b | hit | n rebalances |
|---|---|---|---|---|
| 1w (5td) | −0.069 | −0.052 | 46% | 13 |
| 2w (10td) | −0.113 | −0.085 | 31% | 13 |
| **4w (20td)** | **−0.155** | −0.119 | 15% | 13 |
| 8w (40td) | −0.068 | −0.054 | 44% | 9 |
| **13w (65td)** | **+0.044** | +0.031 | 67% | 3 (weak) |

The negative IC **peaks at ~4 weeks and then decays, flipping slightly positive
by 13 weeks**. The 13w sign-flip is suggestive of the evidence direction
reasserting at longer horizons, but rests on only 3 rebalances — **not
conclusive**. The robust read is: C6's return-drag is a **short-to-medium-horizon
(2–4 week) phenomenon**, consistent with post-event mean reversion rather than a
persistent anti-signal.

## 3. Event-type breakdown — insider sells drive the negative; material events are positive

Classifying each C6≠0 name-rebalance by event composition (h = 20td):

| Class | n | mean C6 | mean fwd return | within-class IC |
|---|---|---|---|---|
| insider-sell-only | 318 | −0.300 | **+0.092** | −0.117 |
| has-material-non-insider | 38 | −0.108 | +0.077 | **+0.358** |
| insider-buy-only | 7 | +0.196 | −0.008 | (n too small) |

This is the core finding. **Insider-sell-only names** (the dominant population)
carry strongly negative C6 yet earned **positive** forward returns — the classic
short-term contrarian pattern (insider disposals are frequently liquidity- or
diversification-driven and not predictive of near-term weakness). In contrast,
**names with a material non-insider event** (8-K, M&A, guidance) show a **+0.36
within-class IC** — when the evidence is genuinely informational, C6 predicts
return with the *correct* sign. The composite C6 mixes a small, correctly-signed
material-event population into a large, contrarian insider-sell population, and
the latter dominates the aggregate IC.

## 4. Risk view — C6 is a risk gate

C6 vs subsequent realized risk (in-sample, h = 20td, 13 rebalances):

| Relationship | IC | Interpretation |
|---|---|---|
| IC(C6, realized volatility) | **−0.317** | lower C6 → **higher** future volatility |
| IC(C6, max drawdown) | **+0.216** | lower C6 → **deeper** drawdown (maxdd ≤ 0) |
| IC(C6, return) | −0.155 | lower C6 → higher mean return (contrarian) |

Even though low-C6 names had higher *mean* return (the contrarian bounce), they
also experienced **materially higher volatility and deeper drawdowns**. C6 thus
carries real, correctly-signed **risk** information — negative evidence flags
turbulence — which a mean-return IC entirely misses. **This is C6's most valuable
and defensible role: a risk gate, not a near-term return alpha.**

## 5. Conditional view — C6 adds correctly-signed information given momentum

Double-sort: within each C1 (price-momentum) quintile, split by C6 and measure
the high-C6-minus-low-C6 forward-return spread (h = 20td, 65 observations):

| C1 quintile | hi-C6 − lo-C6 forward spread |
|---|---|
| q1 (low momentum) | −0.001 |
| q2 | +0.002 |
| q3 | **+0.019** |
| q4 | **+0.020** |
| q5 (high momentum) | +0.011 |
| **mean** | **+0.010** |

Conditioned on momentum, **higher C6 → higher forward return (≈ +1pp)**, strongest
in the mid/upper momentum quintiles. So C6 *does* add positive, correctly-signed
information once C1 is controlled — the negative *unconditional* IC is partly a
confound (insider-sell names skew toward particular momentum states that
mean-revert). C6 is not redundant with C1.

## Forward panel

Sign-audit reproduces exactly forward (NVDA/INTC mixed-event cases match). The
return horizon sweep is negative at 1–2w forward (−0.030 / −0.075) consistent with
in-sample, but the 20-day-horizon risk/event-type/conditional views are **not
evaluable forward** — the ~16-trading-day forward window is shorter than the 20td
horizon. Forward confirmation must wait for the record to lengthen.

## What this means for the composite and for v5 Layer 1

**For the current composite.** C6's contribution to `total_score` is dominated by
an insider-sell population that is contrarian over 2–4 weeks, so as a *return*
input C6 currently subtracts at short horizons. But C6 holds genuine value as a
**risk descriptor** and as a **conditional, material-event** signal. The honest
present-state reading is: C6 is mis-cast if treated as a near-term directional
return component; it is well-cast as a risk/▾-volatility gate and as an
information source on material (non-insider) events.

**For v5 Layer 1 specialist design (observations, not prescriptions):**
- The evidence specialist would likely benefit from **separating the two event
  populations** — insider-transaction flow vs material corporate events — because
  they behave oppositely over 2–4 weeks. Pooling them into one signed scalar
  destroys the material-event information (+0.36 IC) by averaging it against the
  contrarian insider mass.
- C6's **risk-gating** behaviour (vol IC −0.32, drawdown IC +0.22) suggests an
  evidence specialist could contribute a **risk/uncertainty channel** distinct
  from a return channel.
- The **horizon dependence** (negative at 2–4w, reverting by 13w) argues for an
  explicitly horizon-aware specialist rather than a single next-period score.

**Re-weighting is explicitly deferred.** This memo makes **no** recommendation to
re-weight, flip, or drop C6. Any change to component weighting or sign must go
through a **forward-validated, three-AI-reviewed design** with out-of-sample
confirmation — the in-sample findings here carry the same parametric look-ahead
caveat as the rest of the Lab, the forward window is too short to confirm, and
several cells (13w horizon n=3, insider-buy n=7) are thin. These are diagnostic
observations to inform that future design, not a mandate to act now.

## Reproducibility

Engine: `v3/lab/c6_investigation.py` (read-only on `signal_snapshots`, `events`,
`price_history`; deterministic — no randomness). Run
`python3 -m v3.lab.c6_investigation` to regenerate every number above. The
sign-audit independently recomputes C6 from the C6 component's documented formula
(`v3/signal/components/c6_event_impact.py`). Descriptive statistics only; no raw
prices are printed or exported.
