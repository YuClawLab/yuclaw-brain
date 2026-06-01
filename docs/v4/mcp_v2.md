# YUCLAW MCP v2 — Tool Reference

`v3/mcp/server.py` — stdio MCP server on the unified v4 schema. Every research
response is produced by the single assembler `v4.api.builder.build_response`
(no local stamping). Signal labels are research classifications — never SELL/SHORT.

Run: `python3 -m v3.mcp.server`

Server-level instructions (sent to the client) reinforce: evidence-first,
research-only, preserve `compliance`/`limitations`, and say so plainly on `no_data`.

## Primary research tools

### `yuclaw_why(ticker, as_of=None, include_score=False)`
Structured `ResearchResponse`: signal label, graded confidence (A/B/C/Insufficient),
9 component anatomies with rationale, and an `evidence` array where every item carries
`source_url` + `accession_number` + `ledger_hash` (independently verifiable).
- `as_of` — ISO-8601 instant for point-in-time replay (default: latest).
- `include_score` — default **False**; the label + grade lead. True adds the raw composite.
- Missing data → full `status:"no_data"` envelope (with compliance), not an error.

### `yuclaw_memo(ticker, as_of=None, include_score=False, n_evidence=20)`
`MemoOutput` = `{ticker, signal, grade, mode, markdown, response}` — a ready-to-read
Markdown memo plus the compact `ResearchResponse`. Insufficient grade → "evidence-limited
research note"; RISK_ALERT → leads with the triggering event. `n_evidence` default 20 (max 50).

## Auxiliary tools (retained from v3)
- `yuclaw_universe()` — tracked tickers.
- `yuclaw_validation()` — in-sample + forward panels (always show hit rates with their `n`).
- `yuclaw_verify(ticker, date)` — Verified Research Ledger integrity check (VERIFIED / INTEGRITY_FAILURE / NOT_FOUND).

> Dropped from v3 (subsumed by the unified schema): `yuclaw_signal` → use `yuclaw_why`;
> `yuclaw_replay` → `yuclaw_why(as_of=…)`; `yuclaw_events` → the `evidence` array.

## Claude Desktop config
```json
{
  "mcpServers": {
    "yuclaw": { "command": "python3", "args": ["-m", "v3.mcp.server"],
                "cwd": "/home/zhangd2/yuclaw-v3" }
  }
}
```

## Compliance
Every response includes the required `compliance` block (`not_advice`, `research_only`,
`not_registered_adviser`, `notice`, `model_id`, `prompt_version`, `compliance_text_version`).
The notice is the `draft-v0` placeholder pending securities review.
