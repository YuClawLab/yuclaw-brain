# YUCLAW × LangChain

Ultra-thin LangChain tools over the YUCLAW v4 REST API
(`v4/integrations/langchain_yuclaw.py`). They return the **structured
ResearchResponse** so an agent can reason over signal + components + evidence,
with every evidence item carrying a source filing + ledger hash for citation.

## Install / configure
```bash
pip install langchain-core            # (plus your agent framework / LLM provider)
export YUCLAW_API_URL=http://127.0.0.1:8088   # default; point at your YUCLAW API
# start the API:  python3 -m uvicorn v3.api.server:app --port 8088
```

## Tools
| Tool | Returns | Args |
|---|---|---|
| `YuclawWhyTool` | `ResearchResponse` dict | `ticker`, `as_of?`, `include_score=False`, `include_memo=False` |
| `YuclawMemoTool` | `MemoOutput` dict (markdown + response) | `ticker`, `as_of?`, `include_score=False`, `n_evidence=20` |

- **`include_score`** (Q3) — default **off**; the label + grade lead.
- **`include_memo`** (Q2) — `YuclawWhyTool` only; when True, attaches rendered memo under `memo_markdown`.
- A missing ticker returns a `status:"no_data"` envelope (Q4) — branch on `status`, don't expect an exception.

## Copy-paste example
```python
from langchain.agents import create_react_agent           # or your agent factory
from langchain_openai import ChatOpenAI                    # or any LangChain LLM
from v4.integrations.langchain_yuclaw import YuclawWhyTool, YuclawMemoTool

llm = ChatOpenAI(model="gpt-4o-mini")
agent = create_react_agent(llm, [YuclawWhyTool(), YuclawMemoTool()])

# Direct tool call (no agent):
resp = YuclawWhyTool().invoke({"ticker": "AMD"})
print(resp["signal"], resp["confidence"]["grade"])        # e.g. NEUTRAL B
for e in resp["evidence"]:
    print(e["event_type"], e["source_url"], e["ledger_hash"][:12])

# With the rendered memo attached:
resp = YuclawWhyTool().invoke({"ticker": "AMD", "include_memo": True})
print(resp["memo_markdown"])
```

## Notes
- Tools are pydantic-v2 `BaseTool` subclasses; `args_schema` validates inputs.
- `base_url` / `timeout` are constructor fields: `YuclawWhyTool(base_url="https://api.yuclaw.com")`.
- The tool descriptions advertise the evidence-first, research-only posture so the agent
  surfaces sources and caveats. Preserve the `compliance` block when displaying results.
