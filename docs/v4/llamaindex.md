# YUCLAW × LlamaIndex

Ultra-thin LlamaIndex tools + a **citing retriever** over the YUCLAW v4 REST API
(`v4/integrations/llamaindex_yuclaw.py`). `YuclawRetriever` turns each evidence
item into a `TextNode` with citation metadata, so YUCLAW becomes a first-class
retrievable source: an agent can answer "why is AMD neutral?" and cite the
individual SEC filings behind each point.

## Install / configure
```bash
pip install llama-index-core
export YUCLAW_API_URL=http://127.0.0.1:8088   # default; point at your YUCLAW API
# start the API:  python3 -m uvicorn v3.api.server:app --port 8088
```

## Surface
| Object | Purpose |
|---|---|
| `YuclawRetriever(...)` | `BaseRetriever`; `query_str` = ticker → one `NodeWithScore` per evidence item |
| `yuclaw_function_tools()` | `[FunctionTool(yuclaw_why), FunctionTool(yuclaw_memo)]` for an agent |
| `YuclawTool(...)` | convenience: the `yuclaw_why` FunctionTool |

Each retrieved node's metadata (the citation surface):
```json
{
  "source_url": "https://www.sec.gov/Archives/edgar/data/2488/000119312526226746/d118163d8k.htm",
  "accession_number": "0001193125-26-226746",
  "ledger_hash": "da5ffb3da4f3954ba8ae5f0e8e50fdbd09e1991bcc27e4eaae5864c3f0d08f6f",
  "event_type": "M_AND_A_ANNOUNCE",
  "available_as_of": "2026-05-15T14:12:53-06:00",
  "ticker": "AMD",
  "as_of": "2026-05-31T19:29:05.535959-06:00"
}
```
`ledger_hash`/`accession_number`/`source_url` are excluded from the embedding text
(`excluded_embed_metadata_keys`) but kept in metadata for citation/display.

## Copy-paste example
```python
from v4.integrations.llamaindex_yuclaw import YuclawRetriever, yuclaw_function_tools

# Retrieve citable evidence nodes for a ticker:
nodes = YuclawRetriever().retrieve("AMD")          # NodeWithScore per filing
for n in nodes:
    md = n.node.metadata
    print(n.node.text[:60], "—", md["source_url"], md["ledger_hash"][:12])

# Use as agent tools (e.g. with FunctionAgent / ReActAgent):
from llama_index.core.agent.workflow import FunctionAgent   # example
from llama_index.llms.openai import OpenAI
agent = FunctionAgent(tools=yuclaw_function_tools(), llm=OpenAI(model="gpt-4o-mini"))

# Citation pattern: build a query engine over the retriever and cite sources.
from llama_index.core.query_engine import RetrieverQueryEngine
qe = RetrieverQueryEngine.from_args(YuclawRetriever())
# qe.query("AMD")  -> response.source_nodes carry source_url + accession_number + ledger_hash
```

## Notes
- Score gated OFF by default (Q3); pass `include_score=True` to the retriever/tools to include it.
- A missing ticker returns a `status:"no_data"` envelope → the retriever yields zero nodes.
- `base_url`/`timeout` are constructor args for pointing at a hosted API.
