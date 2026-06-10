# YuClaw v4 — Agent Research API (Day 1: schema design)

The single unified response contract that every v4 surface returns —
Memo Generator, MCP v2, REST `/v1/why/{ticker}`, LangChain, LlamaIndex.

| Artifact | Path | Role |
|---|---|---|
| Pydantic models (source of truth) | `v4/api/schema.py` | `ResearchResponse` + nested |
| OpenAPI 3.1 (generated mirror) | `docs/v4/openapi.yaml` | language-neutral contract |
| Migration sketch | `docs/v4/migration.md` | per-entry-point plan (no code) |

## Required top-level fields (all enforced)
`ticker, as_of, replay_id, signal, components, evidence, confidence, limitations, ledger_hash, compliance`
Optional: `score` (composite −1..1), `is_backfill`, `schema_version`.

## Architectural-safety review — PASS (no STOP)
- **No internal-only bearish score exists** in v3 (audited `v3/signal/`): bearish info is already public via
  negative component scores and the negative labels. The schema introduces none.
- **SourceLock not loosened**: `evidence.raw_excerpt` is the same R1–R8-verified text v3 already exposes; the
  schema transports it, adds integrity (`ledger_hash`) and provenance (`accession_number`), relaxes nothing.
- **events table contract untouched**: the future assembler is read-only over v3 data.
- **Signal vocabulary** == locked `PUBLIC_LABELS`; no SELL/SHORT/BUY. `compliance` is a required field;
  `not_advice/research_only/not_registered_adviser` validate-fail if set false.

## Self-review (PHASE 5)
1. **Memo Generator from this schema alone?** Yes — signal+score, 9 scored components with rationale and
   `evidence_ids` that resolve into the response's own `evidence` (excerpt+source_url+accession), graded
   confidence, explicit limitations, compliance. No second DB query. The `evidence_ids`↔`event_id` invariant
   is enforced by a model validator, guaranteeing self-containment.
2. **Verifiable answer for an MCP agent?** Yes — per-evidence `source_url`+`accession_number`+`ledger_hash`,
   a signal-level `ledger_hash`, and a `replay_id` for point-in-time reproduction.
3. **Compliance strong enough?** Required block + research-only label semantics + limitations that disclaim
   recommendation/price-target/solicitation + provenance (`model_id`,`prompt_version`,`jurisdiction`). See
   open question (4) — final wording is a securities-lawyer call.
4. **Redundant/vestigial?** Minimal. `score` and `Component.weight` are arguably derivable/static but are kept
   so a consumer needs nothing beyond the response. Nothing removed as dead.

## Open questions — RESOLVED in Day 2 (decisions applied)
1. **RISK_ALERT trigger** → *risk overlay*: recent (≤30d) REGULATORY_ACTION/LAWSUIT events force RISK_ALERT,
   overriding the score band. `signal` can diverge from `score`; transparency via `signal_overlay`. (builder.py)
2. **Expose raw `score`** → optional, **gated**: default OFF for REST/MCP (`include_score`), ON for SDK/CLI. (Q2)
3. **ledger_hash anchoring** → keep self-computed SHA-256 **and** add `ledger_anchor_url` to the git-anchored
   ledger (`v3/proof/`). Both, no external timestamping yet. Anchor URL excluded from the content hash.
4. **Compliance text** → conservative **PLACEHOLDER** wording now ("not investment advice / past performance /
   not a recommendation"), tagged `compliance_text_version="draft-v0"` for a trivial post-legal swap. Not blocking.
5. **Component anatomy** → **PERSIST** (replay fidelity > storage). Added `signal_snapshots.component_anatomy`
   (jsonb) + `composite_confidence` (migration 2026-05-31); writer populates going forward; builder recomputes
   via `compose_at` for pre-v4 rows.

No feature code yet — tomorrow's order builds the REST endpoint against this locked schema.
