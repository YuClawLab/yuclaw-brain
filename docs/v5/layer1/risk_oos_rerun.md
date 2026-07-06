# Risk-channel OOS re-run — 2026-07-06 (June fuel matured)

**Verdict: INCONCLUSIVE, leaning positive — rare-by-construction CONFIRMED OOS;
sign positive but UNCONFIRMED (elevated arm n=2).** Not a PASS; not decorated.

Re-run of the exact frozen-config check from `130579a5` (which was INCONCLUSIVE for
lack of any same-regime held-out data). Config verified frozen: `YUCLAW_RISK_AGG`
defaults to `count2`, `specialized.py` has **zero diffs** since `c28f8542`, no env
overrides on the box. NOTHING was re-tuned.

## Held-out batch (honesty gate)

`HELD-OUT = L1-type filings (corrected types) with event date > 2026-06-02` — strictly
after the newest tuning-set event, disjoint from the 28-filing D5C set by construction.
No padding with tuning-set filings; the forward window was not shrunk (frozen
`_fwd_vol`: up to 20 trading days, ≥5 forward returns to score; per-row forward
trading-day counts disclosed below).

13 filings: FINANCING 7, GOVERNANCE 3, EARNINGS_RESULT 2, M_AND_A 1.
12 ran (UNH GOVERNANCE failed on a truncated agent JSON — the same failure family as
D5C's META case; reported, not retried). 9 scored (RKLB 3 fwd-td, AMD/DELL 1 fwd-td
are too young for the frozen outcome function). Only GS has the full 20-day window;
the rest are partially matured (6–17 td) and are scored per the frozen function.

## Pipeline as shipped (v5.0)

Full production shape: Gemma worker (`gemma4:26b-a4b-it-q4_K_M`) base agents +
spawned specialists + `count2` risk channel + 70B synthesis (12/12 synthesized OK).
**Text path = production post-`b1b153a0` (prose-first live ingestion): 10/12 filings
ran on persisted `swarm_inputs` prose (`existing`), 2 on `raw_cover` fallback (no
usable exhibit).** This check therefore validates the channel exactly as it ships in
v5.0, prose-first included. Specialists spawned where expected (MU→earningsquality,
RKLB→ma+geopolitical, AMD→earningsquality, DELL Jun-16→macro); no insider gate fired
(the Form-4 live stream is still pending — elevated-arm growth depends partly on it).

## Results (pre-committed arithmetic)

| arm | n | filings (fwd-td) | mean fwd 20d vol |
|---|---|---|---|
| elevated | **2** | DELL FINANCING 0.0366 (15), MU EARNINGS_RESULT 0.0528 (6) | **0.0447** |
| normal | **7** | GS 0.0214 (20), LUNR 0.0682 (17), GOOGL 0.0244 (14), DELL 0.0382 (13), DELL 0.0398 (11), AXP 0.0115 (10), NVDA 0.0205 (9) | **0.0320** |

- **Elevated rate 2/9 = 22.2%** — inside the pre-committed "rare" band (20–40%),
  with a REAL normal arm (n=7). The D5C rare-by-construction property **generalizes
  out-of-sample**. (Under Day-5B `max()` the Bear's 88–93% high rate would have
  saturated this batch; `count2` did not.)
- **Sign: elevated 0.0447 > normal 0.0320 (+)** — correctly signed, BUT the elevated
  arm is two filings; a Mann-Whitney rank test on the arms gives p ≈ 0.25 one-sided
  (elevated vols rank 5th and 8th of 9; LUNR, a normal, is the max). One of the two
  elevated outcomes (MU) is measured over only 6 forward days.
- **No sign flip.** FAIL criteria not met.

## Why INCONCLUSIVE and not PASS

The pre-committed PASS wording is literally satisfiable (rare ✓, signed ✓, real
normal arm ✓), but the same pre-commitment lists "arms too thin" as INCONCLUSIVE —
and an n=2 elevated arm cannot carry a sign claim (p ≈ 0.25). Splitting honestly:
the RARENESS component passes OOS on real data; the SIGN component remains open
until the elevated arm grows (more L1 filings maturing + live Form-4 ingestion
restoring the insider gate). We do not force the pass.

## Consequences (report only — no actions taken)

1. **v5.0 release notes**: may say "risk channel rare-by-construction confirmed
   out-of-sample (22% fire rate, n=9 held-out)"; must NOT say "OOS validated" or
   claim the vol sign is confirmed. Suggested line: "C6 risk channel: rare-by-
   construction confirmed OOS; sign positive at n=2 elevated — accruing."
2. **Lab page / Maturity Gate 6** ("C6 risk-gate OOS confirmation"): stays
   **NOT YET / pending**. The "OOS confirmation pending" text can honestly be
   refined to "rareness confirmed OOS 2026-07-06; sign confirmation pending
   (elevated arm n=2)" — a page edit for the next Lab build, not made here.
3. **Layer 2 gate**: NOT unlocked. The sign gate stays open. Rareness holding OOS
   removes one structural risk to Layer-2 design, but the pre-committed gate is the
   sign, and it is unconfirmed.

## Repro

`python3 -m yuclaw.v5.swarm.tests.risk_oos_rerun /tmp/oos_rerun.json` (harness in
this commit; capture JSON at `/tmp/oos_rerun.json`, wall 1,743s). Note: the run's
in-process SUMMARY block had a string-truthiness bug (counted "normal" flags as
elevated); fixed in the committed harness — verdict arithmetic above recomputed
from the captured per-row flags, which were correct throughout.

Safety: agent-only side effects (persist=False), public.* read-only, gpu-lock held
as `yuclaw` for the duration, worker timer stopped and re-armed after, only prod
Ollama used (check_nemotron confirmed no-op: sm_121a still unsupported).
