# v5 Layer 1 — Day 4 writeup: Event-Type Specialists + C6 Risk Channel

Branch `v5-layer1`. Extends the grounded swarm (Day 2/3) beyond the 4 always-on agents
(Bull/Bear/Skeptic + 70B Synthesis) with **event-type specialists** spawned deterministically by
filing/event type, and wires in the **C6 risk channel** so direction and risk are separate.
Built **model-agnostic** — the worker model is a single config value (8B today; Gemma after the
Ollama upgrade), validated on 8B.

## Model-agnostic worker config (Phase 1)

`yuclaw/v5/swarm/worker.py` — every worker-tier agent (base swarm AND specialists) calls
`call_worker()`, which uses the universal `/api/chat` path with `think:false`:

- **`WORKER_MODEL`** (`YUCLAW_V5_WORKER_MODEL`, default `llama3.1:8b`) is the single config value.
- `think:false` is a no-op for non-thinking models and REQUIRED for thinking models (Gemma 4) —
  the Day-3.5 A/B confound. So swapping to Gemma after the Ollama-≥0.20 upgrade is a one-line
  config change, not a rebuild.
- The 70B Synthesis adjudicator is a separate model on its own path, unchanged.

Regression (AAPL, base-only, no events): the base Bull/Bear/Skeptic ran identically through the
new config — all three **grounding 1.0**, well-formed.

## Event-type specialists (Phase 2)

`yuclaw/v5/swarm/specialists.py` — four worker-tier specialists, each a typed lens with the SAME
grounded schema + SAME citation verifier as the base swarm:

| specialist | fires on (event_type) | lens |
|---|---|---|
| **M&A** | M_AND_A_ANNOUNCE, M_AND_A_CLOSE | deal terms, financing, closing/regulatory/integration risk |
| **Insider** | INSIDER_SELL, INSIDER_BUY | insider flow — **risk-only** (see C6 split) |
| **Regulatory** | REGULATORY_ACTION | exposure, quantified vs open-ended, usually direction-neutral |
| **SupplyChain** | cascade_depth ≥ 1 (supply cascade) | supplier/customer dependency, disruption risk |

**Spawn is DETERMINISTIC and model-free:** `spawn_specialists(accession)` reads the v4-extracted
`public.events.event_type` for the filing (READ-ONLY, joined via source_url) and maps it to
specialists. A filing with no matching event type spawns none (base swarm only). The model never
decides which specialists fire.

### The C6 Insider-vs-Material split (the locked design)

From the C6 investigation: insider-SELL clusters are a **RISK** signal, not a directional return
signal — heavy insider selling reliably precedes higher volatility and deeper drawdowns
(IC(C6,vol) = −0.317, IC(C6,maxDD) = +0.216) but does NOT predict return direction. So the Insider
specialist's prompt **forces `return_view.direction = neutral` for insider selling** and puts the
signal in `risk_view` (elevated). Material non-insider events (M&A, regulatory, supply-chain) DO
carry directional content and are handled by their own specialists. This split is the whole point
of separating Insider from the material-event specialists.

**Demonstrated on a real DELL insider-sell cluster (275 sells):** the Insider specialist returned
`direction=neutral`, `risk=high`, stance verbatim *"Heavy insider selling precedes higher
volatility and deeper drawdowns, but does not predict return direction."* — C6 split **PASS**.
(No corpus filing carries both insider events and MD&A prose — insider events come from Form 4,
which has no events_raw row — so the Insider specialist is demonstrated on the transaction facts.)

## C6 risk channel into synthesis (Phase 3)

`yuclaw/v5/swarm/specialized.py` — every base agent and specialist emits a `risk_view`; these are
aggregated into ONE **risk channel** separate from direction: `{level, flag(elevated/normal),
drivers, contributors, insider_gate}`. The Insider specialist acts as a risk **gate** — if it
fires with high risk, the flag is elevated regardless of direction.

The 70B Synthesis consumes DIRECTION and RISK as **separate channels**. Its prompt is explicit:
an elevated risk flag may demote/flag a name (lower confidence, raise risk level) but must NOT
flip its direction; an insider-sell cluster must not make the direction bearish. **Research
classification only** — the risk channel emits an elevated/normal flag, never buy/sell/short.

Validated on AAPL (base-only): synthesis returned `direction=positive` **and**
`risk_channel.flag=elevated` — *"positive direction, elevated risk."* The high risk demoted/flagged
without flipping the direction. This operationalizes the README's "C6 corrects price-only signals"
inside the swarm.

## One-filing smoke (Phase 4, HARD GATE: PASS)

AMD 8-K (`0001193125-26-226746`), event_type M_AND_A_ANNOUNCE:

- **Spawn:** `ma <- M_AND_A_ANNOUNCE` (deterministic). *(The filing is actually a $5B revolving
  credit facility that the v4 extractor tagged M_AND_A_ANNOUNCE; the spawn is faithful to the tag —
  event_type accuracy is a v4 concern, not a Day-4 spawn bug.)*
- Base swarm grounded (bear/skeptic 1.0, bull 0.5) + **M&A specialist grounded 1.0**.
- **Risk channel** separate: aggregate level=high, flag=elevated, contributors
  {bull:medium, bear:high, skeptic:medium, ma:low}, insider_gate=false.
- **Synthesis kept direction & risk separate:** `direction=neutral` + `risk flag=elevated` — the
  elevated risk did not flip direction. specialist_notes attribute each agent.
- Cost **196s** (= Day-3 baseline; the 4th agent ran concurrently with the base three, so no added
  worker wall-time; synthesis slightly longer on the richer brief).

## Validation batch (Phase 5)

6 filings spanning M&A / Regulatory / base (5 Day-3 filings + the HPE Regulatory 10-Q):

| filing | spawned (why) | base grounding (b/b/s) | risk channel | synth direction |
|--------|---------------|------------------------|--------------|-----------------|
| HPE 8-K (M&A)        | `ma` ← M_AND_A_ANNOUNCE | 0.67/0.67/0.67 | medium / **normal** | positive |
| AMD 8-K (M&A)        | `ma` ← M_AND_A_ANNOUNCE | 1.0/0.33/1.0 | high / **elevated** | positive |
| AAPL 10-Q (base)     | — (no events) | 1.0/1.0/1.0 | high / **elevated** | mixed |
| TMO 10-K (base)      | — (no events) | 0.5/0.67/0.75 | high / **elevated** | positive |
| JNJ 10-Q (base)      | — (no events) | — | high / **elevated** | mixed |
| HPE 10-Q (Regulatory)| `regulatory` ← REGULATORY_ACTION | — | high / **elevated** | positive |

**Read-out:**

- **Spawn is correct and deterministic:** 3/6 spawned (2× M&A, 1× Regulatory), 3 base-only —
  exactly matching the `event_type`s on record. No spurious or missed spawns.
- **Direction and risk stayed separate on every filing.** Four filings are
  **positive/positive-leaning direction WITH an elevated risk flag** — the C6 channel demoted/
  flagged the name (elevated risk) without flipping its direction. This is the operational goal.
- **The risk flag discriminates:** HPE's M&A 8-K came out medium/**normal** while the others were
  elevated — the channel isn't stuck-on.
- Grounding held at Day-2/3 levels (8B variance present, e.g. AMD bear 0.33); the specialists
  grounded comparably to the base agents.

## Cost/filing

**182s/filing** (worker_wall 57s + synthesis 125s), batch_wall 1095s for 6 filings — actually
slightly UNDER the Day-3 baseline (~196s). Adding specialists did **not** add latency: the
specialists run CONCURRENTLY with the base Bull/Bear/Skeptic in one ThreadPoolExecutor, so the
worker wall-clock is still `max(agent)` not `sum(agent)`, and a spawned filing just has 4-5
workers overlapping instead of 3. The synthesis is the dominant cost and is unchanged in shape.
So event-type specialists + the risk channel are essentially **free on wall-clock** at this
worker count — the cost is GPU throughput (more concurrent 8B calls), not latency.

## Production safety

Branch-only, no deploy. `public.*` read-only (events + events_raw for spawn, swarm_inputs for
narrative; persist=False — no swarm_outputs writes). 8B worker only this run (no Gemma / no second
daemon); 70B+8B resident only. Crons intact, main/Lab untouched, Ollama not reconfigured.

## Cross-references
- Worker config: `yuclaw/v5/swarm/worker.py`
- Specialists + spawn: `yuclaw/v5/swarm/specialists.py`
- Risk channel + synthesis: `yuclaw/v5/swarm/specialized.py`
- Harnesses: `tests/smoke_specialized.py`, `tests/batch_specialized.py`, `tests/demo_insider_c6.py`
- C6 risk-gate design: `docs/v5/layer1/design_inputs.md` (amendments 1 & 3)
