# v4 Agent Research API — Migration Sketch (Day 1, NO CODE)

Target: every entry point returns the single `ResearchResponse`
(`v4/api/schema.py`). This is a written plan only — tomorrow's order builds the
REST endpoint against the locked schema.

## Shared core (build this first — all four adapters depend on it)
One assembler, `v4/api/assemble.py::build_response(ticker, as_of=None) -> ResearchResponse`,
maps v3 DB rows → the schema. Each entry point becomes a thin adapter that calls
it and serializes. This is the bulk of the work; the four adapters are trivial
once it exists.

### Data gaps the assembler must close (v3 doesn't persist these today)
These are shared blockers, not per-entry-point:
1. **Per-component anatomy.** `signal_snapshots` stores only 9 component floats.
   The schema needs each component's `confidence`, `rationale`, and `evidence_ids`.
   These exist transiently in `composite.py` `ComponentResult.{confidence,rationale,details.contributors}`
   but are dropped at snapshot time. → Persist them (new `signal_snapshots` JSONB
   column, e.g. `component_anatomy`) OR recompute via `compose_at()` at request
   time. **Recommend recompute-at-request for live, persist for replay.** Effort: **L**.
2. **composite_confidence.** Computed in `compose_at()` but not stored. Same fix as (1). Effort: **S** (rides along).
3. **ledger_hash (signal-level).** New. `ResearchResponse.compute_ledger_hash()` already
   defines it; the assembler just calls `.with_sealed_ledger_hash()`. Anchor it to
   the git-anchored ledger (`v3/proof/`) for external verification. Effort: **M**.
4. **evidence.accession_number.** `events` has no column; derive from `source_url`
   (regex `/data/\d+/(\d{18})/`, same as the 2026-05-30 migration) or join `events_raw`. Effort: **S**.
5. **evidence.ledger_hash.** Map to `events.content_hash` (already present). Effort: **S**.
6. **compliance.model_id / prompt_version.** From `events.llm_model` / `events.prompt_version`
   of the contributing evidence (use the dominant/latest). Effort: **S**.
7. **confidence.grade / limitations.** Pure functions of data already in the response
   (`Confidence.grade_for`, `DEFAULT_LIMITATIONS` + per-signal additions). Effort: **S**.

---

## 1. REST — `v3/api/server.py`  ·  ✅ **COMPLETE (Day 2)**
- DONE: `GET /v1/why/{ticker}` and `/v1/signal/{ticker}` return `ResearchResponse` via
  `build_response(...)` with FastAPI `response_model=ResearchResponse`.
- DONE: v3 `/signal` `/why` kept alive, marked `deprecated=True` + RFC 8594 headers
  (`Deprecation: true`, `Link: …; rel="successor-version"`).
- DONE: Q2 score gating via `?include_score=true`; `?as_of=` for point-in-time replay on `/v1/why`.
- Smoke-tested AMD/NVDA/ABT: schema-valid, ledger_hash recomputes, evidence_ids resolve, compliance present.
- TODO (later): 404 currently returns FastAPI's default detail; add a compliance-bearing error envelope.

## 2. MCP — `v3/mcp/server.py` → MCP v2  ·  Effort: **S** (after core)
- `yuclaw_why` / `yuclaw_signal` tools return `build_response(...).model_dump(mode="json")`.
- Drop the local `_stamp()`/`_validate_label()`; the schema's `SignalLabel` enum enforces vocab.
- Update tool docstrings to advertise `replay_id`, `ledger_hash`, `confidence.grade`, `limitations`.
- Agents gain a self-contained, verifiable answer (evidence + hashes) with no second call.
- Keep tool names stable; only the payload shape grows (additive for existing consumers).

## 3. Python SDK — `sdk/yuclaw_py/` → v4  ·  Effort: **M**
- `Client.why()/signal()` return a typed `ResearchResponse` (import the Pydantic model) instead of a raw dict.
- `PostgresBackend` + `ApiBackend` both delegate to the shared assembler (postgres) / pass-through (api).
- `_compliance.PUBLIC_LABELS` stays as the cross-check; `SignalLabel` becomes the canonical source.
- Back-comat: offer `.model_dump()` and keep dict-style access via a thin shim for one minor version.
- `client.events()` DataFrame is unaffected (separate surface).

## 4. CLI — `v3/cli/why.py`  ·  Effort: **M** (most divergent today)
- `--json` must emit `ResearchResponse` (today it emits raw `signal_snapshots` columns:
  `signal_label`/`total_score`/`c1_price_momentum...`, evidence key `type`). This is a breaking
  rename → gate behind `--schema v4` for one release, then flip default.
- Text renderer reads from the `ResearchResponse` object (components now carry real rationale +
  evidence_ids — fixes the current empty-rationale placeholder at `why.py:138-146`).
- Add a `Grade: A/B/C` line and the `limitations` list to the text output.
- Reuse the assembler; drop the bespoke `_fetch_latest_snapshot` / `_fetch_top_events` SQL.

---

## New v4 consumers (build directly on the schema — no migration, just adoption)
- **Memo Generator** — ✅ **COMPLETE (Day 3)**: `v4/memo/generator.py::generate_memo()` renders Markdown from one
  `ResearchResponse` (full / evidence-limited / no_data / RISK_ALERT modes). Entry points: CLI
  `python3 -m v3.cli memo TICKER` and REST `GET /v1/memo/{ticker}` (→ `MemoOutput` wrapper). Score-off validated.
- **LangChain tool wrapper** — wrap `build_response`; return `.model_dump_json()`; map `limitations`+`compliance`
  into the tool description so the agent surfaces caveats. Effort: **S**.
- **LlamaIndex tool wrapper** — same as LangChain; expose `ledger_hash`/`replay_id` as node metadata for citations. Effort: **S**.

## Suggested sequencing
1. Shared assembler + data-gap fixes (1–7 above) — the real work.
2. REST `/v1` (tomorrow's order) — validates the contract end-to-end.
3. MCP v2 + SDK — thin adapters.
4. CLI `--schema v4`, then Memo Generator + agent wrappers.

## Rollout / safety
- All v3 paths stay until v4 is proven; `/v1` is additive.
- `schema_version` field lets consumers detect the contract.
- No change to the `events` table contract or SourceLock; the assembler is read-only over v3 data.
