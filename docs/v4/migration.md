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

## 2. MCP — `v3/mcp/server.py`  ·  ✅ **COMPLETE (Day 4)** — see docs/v4/mcp_v2.md
- DONE: `yuclaw_why` (structured `ResearchResponse`) + `yuclaw_memo` (`MemoOutput`), both via
  `build_response`/`generate_memo`; local `_stamp()`/`_validate_label()` removed.
- DONE: both accept `ticker`, `as_of`, `include_score` (default off); `yuclaw_memo` also `n_evidence` (20/50).
- DONE: server-level instructions carry the evidence-first/compliance reminder; `no_data` envelope returned consistently.
- Dropped (subsumed): `yuclaw_signal`→`yuclaw_why`, `yuclaw_replay`→`yuclaw_why(as_of=)`, `yuclaw_events`→evidence array.
  Retained auxiliary: `yuclaw_universe`, `yuclaw_validation`, `yuclaw_verify`.

## 3. Python SDK — `sdk/yuclaw_py/`  ·  ⏳ **DEFERRED** (not in Day 4 scope)
- The legacy `yuclaw_py.Client.why()/signal()` dict API is **unchanged**. The MCP server uses the Client only
  for auxiliary `universe`/`validation` (not signals). The agent-facing "SDK" is now the LangChain/LlamaIndex
  wrappers in `v4/integrations/` (below), which return the unified schema. Migrating the Client itself to return
  a typed `ResearchResponse` (with a dict-shim for back-compat) remains a small, separate task.

## 4. CLI  ·  ✅ **COMPLETE (Day 3 + Day 5)**
- DONE: `python3 -m v3.cli why` is now the v4 structured renderer (`v4/api/why_cli.py`) over
  `build_response` — signal + grade + qualitative anatomy + evidence + ledger anchor; `--as-of`
  (bare date = end-of-day), `--include-score` (default off), `--n-evidence`, `--json`.
- DONE: `python3 -m v3.cli memo` (Day 3) and `python3 -m v3.cli demo` (Day 5, the 3-minute journey).
- The legacy `v3/cli/why.py` renderer is retired from dispatch (kept in-tree for reference).

---

## New v4 consumers (build directly on the schema — no migration, just adoption)
- **Memo Generator** — ✅ **COMPLETE (Day 3)**: `v4/memo/generator.py::generate_memo()` renders Markdown from one
  `ResearchResponse` (full / evidence-limited / no_data / RISK_ALERT modes). Entry points: CLI
  `python3 -m v3.cli memo TICKER` and REST `GET /v1/memo/{ticker}` (→ `MemoOutput` wrapper). Score-off validated.
- **LangChain tool wrapper** — ✅ **COMPLETE (Day 4)**: `v4/integrations/langchain_yuclaw.py` —
  `YuclawWhyTool` (structured) + `YuclawMemoTool`; HTTP over `/v1/why`, `/v1/memo`; `include_score`/`include_memo`
  args; evidence-first tool descriptions. See docs/v4/langchain.md.
- **LlamaIndex tool wrapper** — ✅ **COMPLETE (Day 4)**: `v4/integrations/llamaindex_yuclaw.py` —
  `YuclawRetriever` maps each evidence item → a `TextNode` with citation metadata (source_url, accession_number,
  ledger_hash, event_type, available_as_of, ticker, as_of) + `yuclaw_function_tools()`. See docs/v4/llamaindex.md.

## Suggested sequencing
1. Shared assembler + data-gap fixes (1–7 above) — the real work.
2. REST `/v1` (tomorrow's order) — validates the contract end-to-end.
3. MCP v2 + SDK — thin adapters.
4. CLI `--schema v4`, then Memo Generator + agent wrappers.

## Rollout / safety
- All v3 paths stay until v4 is proven; `/v1` is additive.
- `schema_version` field lets consumers detect the contract.
- No change to the `events` table contract or SourceLock; the assembler is read-only over v3 data.
