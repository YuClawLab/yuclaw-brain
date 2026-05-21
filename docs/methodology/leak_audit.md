# Point-in-time leak audit — Day 13b

**Audit date:** 2026-05-20
**Method:** for each replay component, fetch the underlying data rows and assert `max(available_as_of) <= as_of`. Cross-check against three Gemini-flagged edge cases.
**Test ticker × component matrix:** 5 tickers (NVDA, AMD, HPE, JPM, XOM) × 9 components × 1 replay date (D = 2026-03-15 23:59:59 UTC) + 2 edge-date pairs.

## Verdict matrix (45 cells)

| component | mechanism | verdict | evidence |
|---|---|---|---|
| **C1** momentum | reads `dashboard_state.json` (latest snapshot) | **STALE-PROXY** | Conf clamped to 0.3 by `is_historical()` whenever `as_of < now - 24h`. Acceptable trade-off until historical market data lands (v3.1). |
| **C2** volume | placeholder, returns 0/0 | **CLEAN** | No data read; conf=0. |
| **C3** sector velocity | reads `dashboard_state.json` | **STALE-PROXY** | Same masking as C1. |
| **C4** macro regime | reads `dashboard_state.json` | **STALE-PROXY** | Replays on 2026-03-01 vs 2026-05-01 both show "today's" RISK_ON regime at conf 0.3. Contained. |
| **C5** oil/rates/FX | reads `dashboard_state.json` | **STALE-PROXY** | Same masking. |
| **C6** event impact | `events` table filter `available_as_of <= as_of` | **CLEAN** | NVDA latest 2026-03-11 ; AMD 2026-03-13 ; JPM 2026-02-19 ; XOM 2026-03-03 — all < D=2026-03-15. |
| **C7** peer correlation | reads `dashboard_state.json` | **STALE-PROXY** | Same masking. |
| **C8** cascade impact | `events` table filter `available_as_of <= as_of`, `parent_event_id IS NOT NULL` | **CLEAN** | All inputs empty for D=2026-03-15 across all 5 tickers (cascade-eligible roots in the DB only land post-Day-11 HPE event). No future leakage possible. |
| **C9** model trust | `track_record` table filter `signal_time <= as_of` | **🔴 BROKEN** | Production code references columns `signal_time`, `forward_return`, `outcome_status` — none of which exist in the Day-7 wide-row schema. Silently returns `0/0` via `compose_at`'s `try/except`, so composite scores are mildly inflated in absolute value (denominator missing the ~0.04 cold-start contribution). |

**Tally:**

- 15 CLEAN cells (C2 × 5, C6 × 5, C8 × 5)
- 20 STALE-PROXY cells (C1/C3/C4/C5/C7 × 5, minus the C9 row)
- 0 LEAK cells (no component reads future-dated DB rows)
- 5 BROKEN cells (C9 × 5 — schema mismatch)

## Edge cases

### 3a · Good Friday weekend (2026-04-03 → 2026-04-05)

Markets closed Apr 3-5 (NYSE observes Good Friday); SEC EDGAR did **not** observe — 20 Form 4 filings landed on Apr 3. Replays:

- `compose_at("AMD", 2026-04-02 23:59 UTC)` ↔ `compose_at("AMD", 2026-04-05 23:59 UTC)`: C6 event_ids **identical** (no new AMD events filed Apr 3-5).
- Same result for NVDA.

If an affected ticker had filed on Apr 3, the Sun-Apr-5 replay would correctly include it (it's public record by then) and the Thu-Apr-2 replay would correctly exclude it. No leak.

### 3b · Post-market earnings

No EARNINGS_BEAT / EARNINGS_MISS events present in the current `events` table (only M_AND_A_CLOSE, EXEC_CHANGE, DIVIDEND_CHANGE, OTHER_MATERIAL, INSIDER_BUY/SELL). Test skipped pending real earnings ingestion via the LLM pipeline.

### 3c · Macro regime boundary

C4 reads the latest dashboard regime regardless of `as_of`. Replays on 2026-03-01 and 2026-05-01 both return "RISK_ON" at confidence 0.3 — the STALE-PROXY contract working as designed. A true regime-boundary test requires historical regime data (v3.1 scope).

## Findings

1. **C9 broken** (severity: medium). Mathematically: composite scores are slightly inflated because C9 was supposed to contribute `weight × score × confidence = 0.08 × 0 × 0.5 = 0` to the numerator and `0.08 × 0.5 = 0.04` to the denominator (cold start). Today it contributes `0/0` due to the schema mismatch. The bias is small but uniform. **Fix in the next order.**

2. **No actual leaks.** Every DB-backed component (C6/C8) honors its `available_as_of <= as_of` filter. The maximum-timestamp instrumentation found no row with `ts > D` in any component's input set.

3. **Dashboard-backed components are stale-proxy by design.** The `is_historical()` guard at `data_loader.py:HISTORICAL_CUTOFF_SECONDS = 24h` works: every replay older than 24h returns those components at conf 0.3. This is acceptable for the v3.0 launch ("the in-sample event validation primarily reflects the evidence layer" — already documented in `backfill.md` §4). v3.1 will land historical market data so C1/C3/C4/C5/C7 can run point-in-time.

4. **Five "missing historical_approximation flag" false positives.** These are early-return paths in C1/C5/C7 (no data available for the ticker) that exit before setting the flag. They already return confidence 0 — no leak risk, just an audit-script artifact.

## Recommendations (for the next fix order)

1. **Patch C9** to query the actual Day-7 schema: replace `signal_time` → `signal_date`, replace `forward_return / outcome_status` with `return_1d / hit_1d` (or the 5d/20d variants — the existing function uses a single forward-return value, which the Day-7 schema represents per-horizon). Smoke-test with a 100% hit rate ticker.
2. **Defensive:** add a v3 startup probe that runs each component on a fixed ticker and `assert` no `component_error` rationale comes back. Would have caught this on Day 7 launch.

**Status (Day 13c):** both recommendations shipped. C9 was rewritten against the Day-7 schema (commit `9f49e1f6`) and `v3/signal/healthcheck.py` was added as a pre-step in the daily pipeline cron — any component that raises now short-circuits the chain via `&&` and surfaces in `/tmp/yuclaw_pipeline.log`.

---

> Research and education only. Not investment advice. Signal labels are research classifications, not buy/sell recommendations. YUCLAW is not a registered investment adviser. Past results — in-sample or forward-tracked — do not predict future performance.
