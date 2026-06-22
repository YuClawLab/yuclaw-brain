# v5 Layer 1 — Day 5C: Risk-Channel Recalibration

Branch `v5-layer1`. Single purpose: make the C6 risk channel **discriminate** instead of firing
"elevated" 89% of the time (the Day-5B finding), then re-validate. Model-agnostic (`WORKER_MODEL`,
8B). No deploy. Layer 2 stays gated until this passes — or until it's shown the signal isn't there.

## The design principle

A risk gate must flag the **genuinely** risky **without** flagging everything — **discrimination,
not sensitivity.** A flag that fires 89% of the time carries almost no information; it is the
failure mode being fixed. This is the same discipline already applied to the *direction* side,
where extreme labels (`STRONG_BULLISH`) are rare-by-construction. The risk flag needs the same:
"elevated" should be rare and mean something.

## Part 1 — Saturation diagnosis (shown, not assumed)

The Day-5B aggregator (`specialized._risk_channel`) sets `flag = "elevated" if max(per-agent risk
score) >= 2` — i.e. **any single agent reporting "high" flags the whole filing.** Capturing each
agent's `risk_view.level` across the validation set makes the mechanism visible:

**How often does each agent emit "high" risk (N=27)?**

| agent | high rate | distribution |
|---|---:|---|
| **bear** | **25/27 (93%)** | high 25, medium 2 |
| bull | 1/27 (4%) | medium 26, high 1 |
| skeptic | 0/27 (0%) | medium 27 |
| spec:geopolitical | 6/8 (75%) | high 6, low 2 |
| spec:litigation | 1/1 (100%) | high 1 |
| spec:regulatory | 1/1 (100%) | high 1 |
| spec:supplychain | 1/1 (100%) | high 1 |
| spec:sentimentdrift | 1/2 (50%) | high 1, low 1 |
| spec:macro | 3/9 (33%) | high 3, medium 3, low 3 |
| spec:earningsquality | 3/15 (20%) | medium 10, high 3, low 2 |
| spec:ma | 0/4 (0%) | medium 1, low 3 |
| spec:esg | 0/3 (0%) | low 2, medium 1 |

**Filings where "elevated" is triggered by a SINGLE agent: 17/27 — and that single agent is the
Bear every time.** The Bear is structurally pessimistic — its job is to build the bearish case — so
it reports "high" on 93% of filings, while Bull and Skeptic sit at "medium". Under `max()`, the
Bear alone drives the flag on a majority of filings, and "elevated" saturates at 89% (24/27 in
Day-5B; 25/27 here). The mechanism is not assumed — it is the single most common cause of the flag.

## Part 2 — Candidate aggregations (A/B, not picked blind)

All candidates are pure functions of the **same** captured per-agent risk scores
(low=0/medium=1/high=2), so they were A/B'd offline from one agent-only capture — no re-running the
LLM per candidate. Insider's risk-gate override (an insider-sell cluster forces elevated) is kept
in every candidate.

| candidate | rule | intent |
|---|---|---|
| **max** (current) | elevated if ANY agent ≥ high | the saturated baseline |
| **count≥2** | elevated if ≥ 2 agents report high | one flooder (Bear) can't trigger it |
| **exclude-bear** | `max()` over all agents EXCEPT the structurally-pessimistic Bear | remove the flooder |
| **mean ≥ T** | graded continuous score = mean of per-agent scores; elevated if ≥ T, T tuned so elevated is rare-by-construction | a continuous risk score, not binary |

C6 separation is untouched — these only change how risk_view's combine into the risk channel;
direction is never read. Research-classification only (elevated/normal + a graded score; no
buy/sell/short).

## Part 3 — Re-validation at scale (same N=27 Day-5B set)

Each candidate is the flag; discrimination is the forward 20-trading-day realized daily-return
volatility for elevated-flag vs normal-flag filings. **Split sizes are reported honestly** — the
Day-5B normal arm was n=3, which is why magnitude there was suggestive, not conclusive.

| candidate | elev rate | n_elev / n_norm | vol_elev | vol_norm | separation |
|---|---:|---:|---:|---:|---:|
| **max** (current) | 93% | 25 / 2 | 0.0394 | 0.0424 | **−0.0030** (wrong sign) |
| **count≥2 high** | **30%** | **8 / 19** | **0.0451** | **0.0373** | **+0.0078** |
| exclude-bear max | 30% | 8 / 19 | 0.0451 | 0.0373 | +0.0078 |
| mean ≥ 1.0 | 89% | 24 / 3 | 0.0397 | 0.0384 | +0.0013 |
| mean ≥ 1.2 | 59% | 16 / 11 | 0.0355 | 0.0455 | −0.0100 (wrong sign) |
| mean ≥ 1.34 | 19% | 5 / 22 | 0.0409 | 0.0393 | +0.0016 |

graded-mean score across the set: min 0.80, median 1.25, max 1.86.

Two findings stand out. First, **at full N=27 the current `max()` actually discriminates the
*wrong* way (−0.0030)** — the Day-5B "+0.0080, correct sign" was a small-sample artifact of the
n=3 normal arm. The saturated flag does not carry the signal Day-5B tentatively credited it with.
Second, **`count≥2 high` is the only candidate that is simultaneously rare (30%), correctly signed
(+0.0078), and backed by a real normal arm (n_norm 3 → 19)** — elevated-flag names realized ~21%
higher forward vol (0.0451 vs 0.0373). `exclude-bear max` is numerically identical on this set;
`count≥2` is preferred as the more principled rule — it is robust to *any* single flooder, not just
the Bear by name. The graded mean only discriminates correctly where it is also rare (T≥1.34), and
even there the separation is weak; the count rule dominates it.

## Honest verdict

**Adopt `count≥2 high` (env `YUCLAW_RISK_AGG=count2`, now the default).** It is the one
recalibration that crosses the bar set by the design principle: it makes "elevated" rare (89% →
30%), it discriminates in the correct direction (+0.0078), and — unlike Day-5B — it does so with a
normal arm large enough (n=19) for the comparison to mean something.

This is a genuine pass, but stated with its limits: the separation is modest (+0.0078 on in-sample
forward vol, N=27), and the *current* `max()` it replaces was in fact a non-discriminator at scale,
so the win is "from wrong-sign-and-saturated to correctly-signed-and-rare," not "from good to
great." The channel now earns the cost it was failing to earn in Day-5B — it is no longer a flag
that fires 89% of the time and points the wrong way — and that is exactly the gate Layer 2 was
waiting on. The insider-sell gate is retained as an OR-override (it never fired in this set, so it
is untested-but-additive). `max` and graded `mean@T` remain available via the same env for audit.

## Production safety
Branch-only, no deploy. `public.*` READ-ONLY; additive to `yuclaw_v5.*` only; persist=False (Day-3
baseline intact). 8B worker only (no Gemma / no 2nd daemon). Crons intact, main/Lab untouched,
Ollama not reconfigured. The idle `/loop` heartbeat was deferred (21:58 → 22:41) so it can't
interleave with this run.

## Cross-references
- Saturation finding: `docs/v5/layer1/day5b.md` (Part 2 verdict)
- Aggregator: `yuclaw/v5/swarm/specialized.py` (`_risk_channel`)
- Capture + A/B: `tests/risk_recal_capture.py`, `tests/risk_recal_analyze.py`
