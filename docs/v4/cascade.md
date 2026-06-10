# Cascade History View (v4 Day 6)

When a material event hits one company, it can ripple to its supply-chain and
sector neighbors. YUCLAW models this as a **cascade**: a root event propagates to
related tickers along a public, weighted influence graph. The Cascade History View
shows, for a ticker, **which upstream event reached it and how** — with every edge
weight traceable to the open `v3/signal/supply_chain.py` graph.

## Where the numbers come from (all public)
- **Edges & weights** — hardcoded in `v3/signal/supply_chain.py` (e.g. `TSM→NVDA 0.45`,
  `HPE→AMD 0.10`). Transmission strengths in [0, 1].
- **Relationship types** — `supply` (same-sign propagation), `peer` (competitive, sign-flipped),
  `cohort` (same-sector co-movement), `etf` (sector ETF → member), `macro` (broad ETF → ticker).
- **Decay per hop** (locked in `cascade_engine.py`): depth-1 = **0.20**, depth-2 = **0.04**, depth 3+ dropped.
- **Contribution** of a child = `parent_magnitude × ∏(edge weights) × decay`. This is the cascade
  child event's magnitude — what it contributed to the child's C8 Cascade Effect component.

There is **no internal-only or proprietary scoring** in the cascade — audited Day 6.

## How to read it
A cascade for AMD on 2026-05-20:
```
Cascade into AMD
Root: M And A Close (HPE, 2026-05-14)
  > On May 13, 2026, the Company closed on the sale and disposition of 13.8% ...
  [source] · accession 0001645590-26-000045 · ledger 497eb270710a…
Propagation (depth · edge · weight × decay → contribution):
  d1  HPE → AMD   supply (sign +)  w=0.1 × decay 0.2 → contribution 0.0160
```
Reading: HPE's M&A close (magnitude 0.8) propagated to AMD along the **supply** edge
(weight 0.10), decayed by the depth-1 factor (0.20), contributing **0.016** to AMD's
cascade component. `0.8 × 0.10 × 0.20 = 0.016`.

## Surfaces
| Surface | Usage |
|---|---|
| CLI | `python3 -m v3.cli cascade AMD --as-of 2026-05-20 [--depth 3] [--json]` |
| REST | `GET /v1/cascade/{ticker}?as_of=…&depth=N` → `{ticker, cascade, compliance}` |
| `why` | `GET /v1/why/{ticker}?include_cascade=true` (and `build_response(..., include_cascade=True)`) |
| MCP | `yuclaw_why(ticker, include_cascade=True)` |
| Agents | LangChain `YuclawWhyTool(... include_cascade=True)`; LlamaIndex `yuclaw_why(..., include_cascade=True)` |
| Demo | `yuclaw demo --show-cascade` (adds an opt-in Step 3.5) |

Cascade is **opt-in** (like score and memo) — not auto-included in every `why` response.

## Schema (`v4/api/schema.py`)
- `CascadeEdge` — `parent/child_event_id`, `parent/child_ticker`, `parent/child_event_type`,
  `relationship_type`, `edge_weight`, `depth`, `decay_factor`, `contribution`.
- `CascadeNode` — `event` (the root, as an `Evidence`), `depth` (0), `edges` (flat list spanning the
  tree — reconstruct via parent/child ids + depth), `warnings`.
- `ResearchResponse.cascade: CascadeNode | None`.

## Point-in-time & integrity
The view is `as_of`-aware (Q5): it shows the cascade **as known at that instant** — only events
with `available_as_of ≤ as_of` are included. When `include_cascade=True`, the cascade is part of the
`ResearchResponse` and therefore covered by its `ledger_hash`.

## Cycle guard & depth
The traversal walks `events.parent_event_id` upward with a `visited` set; if it ever revisits an
event it **halts** and records `cycle detected at event X` in `cascade.warnings` (also logged) rather
than looping. Depth is capped at 3 (matching the decay schedule). `cascade: null` is returned cleanly
when no cascade reached the ticker.

## Limitations
- Day 6 walks the existing `parent_event_id` FK — no separate cascade-edge table (v4.1 work).
- Only depth-1 and depth-2 cascade *events* are ever materialized (the engine drops depth 3+), so
  trees are shallow by construction.
- The weights are design-doc transmission strengths, not estimated/learned coefficients.
