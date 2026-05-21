# YUCLAW MCP server

Exposes seven read-only YUCLAW research tools over the Model Context Protocol (stdio transport).

> **Disclaimer.** Research and education only. Not investment advice. Signal labels are research classifications, not buy/sell recommendations. YUCLAW is not a registered investment adviser. Past results — backtested or forward-tracked — do not predict future performance.

## Tools

| name | summary |
|---|---|
| `yuclaw_signal(ticker)` | Latest composite signal + 9 component scores |
| `yuclaw_why(ticker, n_evidence=5)` | Signal + ranked evidence with source URLs |
| `yuclaw_replay(ticker, date)` | Point-in-time signal at the end of `date` |
| `yuclaw_backtest()` | In-sample + forward-tracking panels |
| `yuclaw_events(ticker, since=None)` | Raw evidence events for a ticker |
| `yuclaw_universe()` | The 79 tickers v3.0 tracks |
| `yuclaw_verify(ticker, date)` | Verified Research Ledger integrity check |

Each tool's MCP description ends with: *"Research/education only — not investment advice."*  
Each tool response embeds the locked compliance payload `{not_advice, research_only, not_registered_adviser}`.

The only labels that can appear in tool responses are: `STRONG_BULLISH`, `BULLISH`, `NEUTRAL`, `WATCH`, `WEAKENING`, `NEGATIVE_EVENT`, `BEARISH_WATCH`, `RISK_ALERT`. There is no `SELL` or `SHORT`. The SDK's `_validate_label()` is invoked on every signal-bearing return.

## Connecting a client

### Claude Desktop / any FastMCP-compatible client

Add this to your MCP servers config:

```json
{
  "mcpServers": {
    "yuclaw": {
      "command": "python3",
      "args": ["-m", "v3.mcp.server"],
      "cwd": "/home/zhangd2/yuclaw-v3"
    }
  }
}
```

The server needs to find:
- `yuclaw_py` (the SDK, `pip install yuclaw-evidence`)
- the `yuclaw_events` Postgres database (the v3.0 operator setup)
- the `v3.proof` module on its `PYTHONPATH` (running from `cwd=/home/zhangd2/yuclaw-v3` covers this)

### Standalone smoke test

```bash
cd /home/zhangd2/yuclaw-v3
python3 -m v3.mcp.server   # server runs over stdio; press ^C to exit
```

To verify the tool table without launching the full transport:

```bash
python3 -c "from v3.mcp.server import mcp; import asyncio; print(asyncio.run(mcp.list_tools()))"
```
