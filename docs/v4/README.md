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

## Open questions for VinZhang (could not resolve alone)
1. **RISK_ALERT trigger.** It's in the locked vocab but v3 never emits it (score→label table maps the other 7).
   In v4, is RISK_ALERT a *risk overlay* that overrides the score-based label on certain event types
   (REGULATORY_ACTION, LAWSUIT, …), or a score band? This decides whether `signal` can diverge from `score`.
2. **Expose raw `score`?** I kept the −1..1 composite as an optional field (memo headline, back-compat). Product/
   legal may prefer label+grade only (less "advice-like precision"). Easy to drop if so.
3. **ledger_hash anchoring.** Is a self-computed SHA-256 enough for "verifiable", or must the signal-level hash
   be anchored to the git-anchored ledger (`v3/proof/`) / an external timestamp (RFC3161 / chain)? Affects
   `replay_id` semantics.
4. **Compliance text sufficiency (legal).** Does the notice + limitations need an explicit "no fiduciary
   relationship / past performance is not indicative" clause and per-jurisdiction variants? Not mine to draft.
5. **Component anatomy: persist vs recompute.** For faithful point-in-time replay, per-component
   rationale/evidence_ids must be reconstructable as-of. Recompute-at-request can drift if component logic
   changes; persisting a `component_anatomy` JSONB guarantees fidelity but grows `signal_snapshots`. Tradeoff
   decision needed before replay is trusted.

No feature code yet — tomorrow's order builds the REST endpoint against this locked schema.
