# API Keys & Metering (v4 Day 8)

YUCLAW's REST API is **usable without a key** (anonymous tier). A key only raises your
daily quota. The CLI, MCP (stdio), and in-process SDK (`build_response`) are **never
metered** — self-hosting stays unlimited and offline.

## Tiers & quotas (per UTC day)
| Tier | Limit | How |
|---|---|---|
| Anonymous | **20 req/day per IP** | no key needed |
| Keyed (free) | **100 req/day per key** | `Authorization: Bearer <key>` |

## Which endpoints are metered
| Always free, no auth | Metered (key optional, raises quota) | Account (key required) |
|---|---|---|
| `GET /health` | `GET /v1/why/{ticker}` | `GET /v1/keys/info` |
| `GET /v1/universe` | `GET /v1/signal/{ticker}` | `GET /v1/keys/usage` |
| `GET /v1/openapi.json` | `GET /v1/memo/{ticker}` | |
| | `GET /v1/cascade/{ticker}` | |
| | `GET /v1/verify/{ticker}` | |

## Getting a key
Keys are issued via the CLI (no public self-service signup in v4):
```bash
yuclaw keys create --owner-email you@example.com --notes "my app"
#   key_id : key_4afb289a76df6ce7
#   secret : yks_…                         ← shown ONCE, never recoverable
#   Use it as:  Authorization: Bearer yks_…
```
Only the **SHA-256 hash** of the secret is stored — a database leak can't expose usable keys.
```bash
yuclaw keys list                    # key_id, owner, created, active/revoked (never secrets)
yuclaw keys usage key_4afb…         # daily request counts
yuclaw keys revoke key_4afb…        # deactivate
```

## Using a key
```bash
curl -H "Authorization: Bearer yks_…" https://api.yuclaw.com/v1/why/AMD
```
SDK / agent wrappers accept it directly:
```python
from yuclaw_py import Client
Client(source="api", base_url="https://api.yuclaw.com", api_key="yks_…")

from v4.integrations.langchain_yuclaw import YuclawWhyTool
YuclawWhyTool(api_key="yks_…")

from v4.integrations.llamaindex_yuclaw import YuclawRetriever
YuclawRetriever(api_key="yks_…")
```

## Rate-limit behavior (HTTP 429)
Over quota, a metered endpoint returns **429** with a full `ResearchResponse`-shaped envelope —
**the compliance block is always present** (it's a denied *signal* request), plus a `Retry-After`
header:
```json
{
  "status": "rate_limited",
  "retry_after": 36249,
  "ticker": "AMD",
  "limitations": ["Daily request quota exceeded.", "Retry after 36249s.", …],
  "compliance": { "not_advice": true, … },
  …
}
```
Handle it by reading `retry_after` (seconds until the UTC-midnight reset) or the `Retry-After`
header and backing off. An **invalid** key returns **401** (also compliance-bearing). Account
endpoints (`/v1/keys/*`) and pure metadata return **no** compliance block (Q5).

## Storage
Postgres tables `api_keys` (key_hash, owner, expiry, active) and `request_logs`
(key_id / client_ip, endpoint, ticker, status_code, ts), indexed for fast UTC-daily counts.
No server-side persistence of *signals* — only keys + request metadata.
