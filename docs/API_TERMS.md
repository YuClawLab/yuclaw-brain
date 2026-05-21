# YUCLAW API — Terms of Service

**Effective:** 2026-05-20 (v3.0 launch)
**API version:** 3.0.0

By calling the YUCLAW REST API (or using the `yuclaw-py` SDK in `source="api"` mode), you agree to these terms.

---

## 1. Research / educational use only

The YUCLAW API is an **open research tool**. It provides composite research signals, evidence event records, and a Verified Research Ledger. It is **not** investment advice, and **not** a recommendation to buy, sell, or hold any security.

YUCLAW is **not** a registered investment adviser, broker-dealer, exchange, or any other regulated financial entity. Signal labels are research classifications, not buy/sell recommendations. Past results — in-sample or forward-tracked — do not predict future performance.

If you intend to use API output in any decision involving real money, you are doing so **at your own risk** and should consult a licensed adviser first.

## 2. No warranty

The API is provided **"as is"**, without warranty of any kind. YuClawLab makes no representations or warranties about accuracy, completeness, timeliness, or fitness for any particular purpose. The API may go down, return stale data, or return signals that turn out to be wrong. You accept that risk by using it.

## 3. Acceptable use

You may:

- Call the API for personal research, education, or building open-source tools on top of it.
- Cache YUCLAW-generated output (signals, components, event excerpts, hashes, validation metrics) and redistribute it under MIT, provided this disclaimer travels with it.
- Operate trading or alerting systems against API output **at your own risk**, subject to the no-warranty clause above.

You may **not**:

- Bulk-export or redistribute the underlying market price data (Yahoo Finance terms forbid OHLCV redistribution — the API never returns raw `price_history` rows for this reason).
- Resell access to the YUCLAW API or rebrand its output as your own paid product without explicit written permission.
- Use the API to claim that YUCLAW endorses, recommends, or projects performance for any security.
- Use the API to violate any law, regulation, or third-party right.

## 4. Rate limits + acceptable load

The API is intended for low-rate research use. As a guideline:

- ≤ 30 requests per minute per IP (steady-state)
- ≤ 5 concurrent connections per IP
- Bulk operations (`/validation`, `/events?since=…`) — please cache, don't re-fetch each request

These limits may change. The API may rate-limit, throttle, or temporarily block clients that exceed them.

## 5. Data sources + attribution

| source | role | redistribution |
|---|---|---|
| **SEC EDGAR** (public domain) | Form 4 / 8-K / 10-Q / 10-K / 6-K filings | Excerpts ≤ 600 chars surfaced with full source URLs. SEC's `User-Agent` and 10-req/sec policy honored. |
| **Yahoo Finance** (via `yfinance`) | Daily close + volume for outcome computation | **Internal only.** Raw OHLCV is never exposed through any API endpoint, SDK method, or MCP tool. Only derived metrics (returns, hit rates, excess returns) are published. |
| **YUCLAW-generated** | Composite signals, components, supply-chain edges, cascades, content hashes, validation aggregations | MIT-licensed; freely redistributable with disclaimer. |

The Verified Research Ledger lives in a public git repo at `https://github.com/YuClawLab/yuclaw-trust`. Each day's signals are committed there as content hashes — anyone can call `yuclaw verify TICKER --date YYYY-MM-DD` (or the equivalent MCP tool / SDK method) to confirm a signal hasn't been edited since publication. The ledger verifies record integrity and timing — **not** investment merit.

## 6. Privacy

The API is GET-only and does not require authentication for v3.0 public endpoints. Server-side logs may record request IP, timestamp, and path for debugging / abuse prevention; logs are not sold or shared with third parties. Personally-identifiable information is not collected.

## 7. Liability

To the maximum extent permitted by applicable law, YuClawLab and its contributors are **not liable** for any damages — direct, indirect, incidental, consequential, special, or exemplary — arising from your use of the API. This includes trading losses, missed opportunities, data inaccuracies, downtime, or any other harm.

## 8. Changes

These terms may change. The current version is always at this path; the API's `/health` endpoint returns the API version string. Material changes will bump the major version (e.g. 3.x → 4.0).

## 9. Contact

GitHub issues: <https://github.com/YuClawLab/yuclaw-brain/issues>

---

**Reminder.** Research and education only. Not investment advice. Signal labels are research classifications, not buy/sell recommendations. YUCLAW is not a registered investment adviser. Past results — in-sample or forward-tracked — do not predict future performance.
