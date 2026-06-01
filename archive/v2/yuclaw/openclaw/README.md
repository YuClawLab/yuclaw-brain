# YUCLAW x OpenClaw Integration

Use YUCLAW financial intelligence inside OpenClaw.

## Option 1: OpenClaw Skill (simplest)
```bash
cp yuclaw/openclaw/skill.js ~/.openclaw/skills/yuclaw-financial/index.js
openclaw restart
```

Then in any chat:
```
/yuclaw           — full financial briefing
/yuclaw signals   — top buy/sell signals
/yuclaw regime    — market regime
/yuclaw backtest NVDA — backtest any ticker
/yuclaw portfolio — optimal allocation
```

## Option 2: MCP Server (full integration)
```bash
# Start YUCLAW MCP server
python3 yuclaw/openclaw/mcp_server.py

# Add to OpenClaw MCP config
# URL: http://localhost:8002
```

OpenClaw will automatically use YUCLAW for financial questions.

## Option 3: REST API
```bash
# Start YUCLAW API
python3 yuclaw/api/server.py

# Endpoints
curl http://localhost:8000/signals
curl http://localhost:8000/regime
curl http://localhost:8000/risk
curl http://localhost:8000/brief
curl http://localhost:8000/health
```

## Requirements
```bash
pip install yuclaw
yuclaw start
```
