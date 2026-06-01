"""Generate docs/v4/openapi.yaml from the Pydantic schema (run: python3 -m v4.api._gen_openapi)."""
import yaml
from v4.api.schema import ResearchResponse, SCHEMA_VERSION
from v4.memo.generator import MemoOutput

js = ResearchResponse.model_json_schema(ref_template="#/components/schemas/{model}")
defs = js.pop("$defs", {})
mjs = MemoOutput.model_json_schema(ref_template="#/components/schemas/{model}")
mdefs = mjs.pop("$defs", {})
schemas = {"ResearchResponse": js, "MemoOutput": mjs, **defs, **mdefs}

DESC = (
    "ONE response contract (ResearchResponse) for every v4 surface. Research "
    "classifications, NOT buy/sell. Required compliance block (draft-v0 wording pending legal). "
    "Q1: RISK_ALERT risk-overlay on recent REGULATORY_ACTION/LAWSUIT can diverge signal from score. "
    "Q2: score gated (REST/MCP opt-in via include_score; SDK/CLI on). Q3: ledger_hash (self SHA-256) "
    "+ ledger_anchor_url (git-anchored ledger). Grade: A=conf>=0.75 & >=3 strong events; B=conf>=0.55 "
    "& >=1; C=conf>=0.30; else Insufficient."
)
TICKER = {"type": "string", "pattern": "^[A-Z][A-Z0-9.\\-]{0,9}$"}
RESP200 = {"200": {"description": "Unified research response",
                   "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ResearchResponse"}}}}}

openapi = {
    "openapi": "3.1.0",
    "info": {"title": "YuClaw Agent Research API", "version": SCHEMA_VERSION,
             "summary": "Unified, point-in-time, evidence-anchored research signals.",
             "description": DESC,
             "x-not-advice": "Research and education only. Not investment advice."},
    "servers": [{"url": "https://api.yuclaw.com", "description": "production (planned)"}],
    "paths": {
        "/v1/why/{ticker}": {"get": {
            "operationId": "getWhy",
            "summary": "Full research signal + evidence + component anatomy.",
            "parameters": [
                {"name": "ticker", "in": "path", "required": True, "schema": TICKER},
                {"name": "include_score", "in": "query", "required": False,
                 "description": "Q2: expose composite score (default false).",
                 "schema": {"type": "boolean", "default": False}},
                {"name": "include_cascade", "in": "query", "required": False,
                 "description": "Day 6: attach the supply-chain cascade tree (default false).",
                 "schema": {"type": "boolean", "default": False}},
                {"name": "n_evidence", "in": "query", "required": False,
                 "schema": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50}},
                {"name": "as_of", "in": "query", "required": False,
                 "description": "ISO-8601 instant for point-in-time replay.",
                 "schema": {"type": "string", "format": "date-time"}}],
            "responses": {**RESP200, "404": {"description": "No snapshot for ticker"}}}},
        "/v1/cascade/{ticker}": {"get": {
            "operationId": "getCascade",
            "summary": "Supply-chain cascade tree that propagated into a ticker (Day 6). cascade=null if none.",
            "parameters": [
                {"name": "ticker", "in": "path", "required": True, "schema": TICKER},
                {"name": "depth", "in": "query", "required": False,
                 "schema": {"type": "integer", "default": 3, "minimum": 1, "maximum": 3}},
                {"name": "as_of", "in": "query", "required": False,
                 "schema": {"type": "string", "format": "date-time"}}],
            "responses": {"200": {"description": "Cascade tree wrapper (cascade may be null)",
                          "content": {"application/json": {"schema": {"type": "object", "properties": {
                              "ticker": {"type": "string"},
                              "cascade": {"oneOf": [{"$ref": "#/components/schemas/CascadeNode"}, {"type": "null"}]},
                              "compliance": {"type": "object"}}}}}}}}},
        "/v1/signal/{ticker}": {"get": {
            "operationId": "getSignal",
            "summary": "Same ResearchResponse; lightweight latest view.",
            "parameters": [
                {"name": "ticker", "in": "path", "required": True, "schema": TICKER},
                {"name": "include_score", "in": "query", "required": False,
                 "schema": {"type": "boolean", "default": False}}],
            "responses": RESP200}},
        "/v1/memo/{ticker}": {"get": {
            "operationId": "getMemo",
            "summary": "Markdown research memo + the full ResearchResponse (Day 3). no_data-safe.",
            "parameters": [
                {"name": "ticker", "in": "path", "required": True, "schema": TICKER},
                {"name": "include_score", "in": "query", "required": False,
                 "schema": {"type": "boolean", "default": False}},
                {"name": "n_evidence", "in": "query", "required": False,
                 "schema": {"type": "integer", "default": 20, "minimum": 1, "maximum": 50}},
                {"name": "as_of", "in": "query", "required": False,
                 "schema": {"type": "string", "format": "date-time"}}],
            "responses": {"200": {"description": "Memo wrapper (Markdown + ResearchResponse)",
                          "content": {"application/json": {"schema": {"$ref": "#/components/schemas/MemoOutput"}}}}}}},
    },
    "components": {"schemas": schemas},
}

with open("docs/v4/openapi.yaml", "w") as f:
    yaml.safe_dump(openapi, f, sort_keys=False, width=100, allow_unicode=True)
print("wrote docs/v4/openapi.yaml; schemas:", list(schemas))
