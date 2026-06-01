# YUCLAW v4 — Compliance Audit (Day 9, pre-ship gate)

**Date:** 2026-06-01 · **Gate for:** June 10 v4 ship · **Author:** Day-9 audit pass

## Verdict
The **v4 product surfaces** (CLI, REST, MCP, SDK, agent wrappers, memo, share card, docs)
are compliance-clean: no buy/sell vocabulary, git-anchored (not Sepolia) framing, canonical
not-advice wording on every signal response, enforced by an automated regression test.

The **legacy v2.3 layer still committed in this repo** (the GitHub-Pages dashboard, the
`engines/` + `output/` pipeline, and the `yuclaw` PyPI package entry point) is **NOT
v4-clean** and is the remaining ship-blocker — it needs a product/release decision, not just
text edits. Details in §5.

## Canonical not-advice wording (single source of truth)
Defined once at `v4/api/schema.py::COMPLIANCE_NOTICE` (tag `draft-v0`):
> **YUCLAW research output. Not investment advice. Past performance does not guarantee future
> results. Signal labels are research classifications, not buy/sell recommendations.**

`draft-v0` is a deliberate, conservative **placeholder** (Q3). It is NOT blocking the ship;
the version tag exists so a post-funding lawyer-reviewed swap to `v1` is a one-line change.

---

## 1. Buy/sell vocabulary scan (`STRONG_BUY|BUY|SELL|SHORT|HOLD`)
| Location | Finding | Decision | Status |
|---|---|---|---|
| `README.md` | v2.3 `STRONG_BUY score:+0.736` sample, prose | Full rewrite to v4 voice | ✅ FIXED |
| `docs/getting-started/quickstart.md` | v2.3 framing | Full rewrite | ✅ FIXED |
| v4 code (`v3/`, `v4/`) | none (locked `SignalLabel` enum; no SELL/SHORT) | — | ✅ clean |
| `output/*.json` (dashboard_state, screener_latest, competitive_intel, finclaw_brief) | v2.3 `STRONG_BUY/STRONG_SELL`, `"action":"BUY — high conviction"` | Legacy data — **archive/remove** | ⛔ SHIP-BLOCKER (§5) |
| `docs/index.html`, `docs/app.html` (GitHub Pages) | live v2.3 dashboard, buy/sell cards | **Take down or rebuild for v4** | ⛔ SHIP-BLOCKER (§5) |
| `engines/run_brief.py`, `rebuild_html.py` | v2.3 generators emit BUY/SELL | Legacy code — archive | ⛔ SHIP-BLOCKER (§5) |
| `CHANGELOG.md` | historical mention of `STRONG_BUY` | Keep (historical record) | ✅ keep |

## 2. Sepolia / Ethereum / ZKP scan
v3.0 claimed to remove Sepolia anchoring (the ledger is git-anchored) but stragglers remain.
| Location | Finding | Decision | Status |
|---|---|---|---|
| `README.md` | Sepolia badge, prose, mermaid, footer, "ZKP module" | Rewrite (git-anchored) | ✅ FIXED |
| `pyproject.toml` | `keywords = […, "zkp", …]` | Remove `zkp` | ✅ FIXED |
| `docs/onepager.md` | 3× "Ethereum Sepolia", "on-chain anchor" | De-linked marketing — **update or archive** | ⛔ open (§5) |
| `README_PACKAGE.md` | "Hash anchor on Ethereum Sepolia" | Legacy package readme — archive | ⛔ open (§5) |
| `yuclaw/openclaw_plugin/README.md` | Sepolia | Legacy plugin — archive | ⛔ open (§5) |
| `rebuild_html.py`, `docs/*.html` | "Hash-Anchored — Ethereum Sepolia" badge | Part of dashboard takedown (§5) | ⛔ SHIP-BLOCKER |
| `v4/`, `v3/proof/`, `yuclaw-trust` | git-anchored ledger, honest framing | — | ✅ clean |

## 3. Universe-size language
v4 tracks **~80 names** (49 equities + 15 sector ETFs + 5 broad ETFs + 10 macro = 79 active,
1 deferred). Stale "39 tickers" / "20 stocks" found in:
| Location | Decision | Status |
|---|---|---|
| `README.md` mermaid "39 tickers" | Rewrite → ~80 universe section | ✅ FIXED |
| `README_PACKAGE.md` "39 tickers" | Legacy — archive | ⛔ open (§5) |
| `output/signal_log.txt` "39 tickers" | Legacy data — archive | ⛔ open (§5) |

## 4. Not-advice wording consistency (Q5)
| Surface | Before | After | Status |
|---|---|---|---|
| `v4/api/schema.py` | 3 divergent strings (sdk / Day-2 placeholder / Q5) | `COMPLIANCE_NOTICE` constant; `Compliance.notice` defaults to it | ✅ FIXED |
| Memo footer | rendered `compliance.notice` | == canonical (no change needed) | ✅ |
| Share card footer | hardcoded subset | renders `COMPLIANCE_NOTICE` | ✅ FIXED |
| OpenAPI description | bespoke | prefixed with `COMPLIANCE_NOTICE` | ✅ FIXED |
| FastAPI app description | "not a registered investment adviser" variant | `COMPLIANCE_NOTICE` | ✅ FIXED |
| `DISCLAIMER.md` | dashboard ref, older wording | canonical notice + reference to the constant | ✅ FIXED |
| `sdk/yuclaw_py/_compliance.py` | older wording | matches canonical verbatim (duplicated, standalone pkg) | ✅ FIXED |
| `sdk/README.md` (PyPI) | "registered investment adviser" variant | canonical | ✅ FIXED |
| `sdk/pyproject.toml` description | v4 voice (Day 5/7) | verified clean | ✅ |

## 4a. Compliance-on-metadata (Q2)
| Endpoint class | Rule | Status |
|---|---|---|
| Signal (`/v1/why,signal,memo,cascade,verify`) incl. 401/429 denials | compliance **present** | ✅ enforced + tested |
| Metadata (`/health`, `/v1/universe`, `/v1/openapi.json`) | compliance **absent** | ✅ removed from `/health`, `/universe` |
| Account (`/v1/keys/info`, `/v1/keys/usage`) | compliance **absent** | ✅ |
Guarded by `tests/test_compliance_regression.py` (21 assertions, all passing).

---

## 5. Ship-blockers requiring a decision (NOT fixed by text edits)
These are real, and they're the reason `pip install yuclaw && yuclaw demo` does **not** yet
deliver the v4 experience. Each needs a VinZhang call before June 10.

1. **PyPI packaging / entry point.** The `yuclaw` console script maps to `yuclaw.cli_v2:main`
   (v2.x), and the published `yuclaw` package contains the `yuclaw/` (v2.x) tree — **not** `v3/`
   or `v4/`. So `pip install yuclaw; yuclaw demo` runs the *old* CLI today. The v4 docs use the
   target UX (`yuclaw demo`). **Decision:** repoint the entry point to the v4 dispatcher and
   package `v3/`+`v4/` (or publish a new package) so the README is true at ship.
2. **GitHub-Pages dashboard.** `docs/index.html` ("YUCLAW OS") + `docs/app.html` are the live
   public dashboard — full of `STRONG_BUY` cards and an "Ethereum Sepolia" badge. They are
   **frozen** (the v2.3 cron was removed; the active crons belong to a different project). This
   is the most visible non-compliant surface. **Decision:** take it down, or rebuild it from v4
   data as a research-only view (v4.1). It cannot ship as-is.
3. **Legacy `engines/` + `output/` + `README_PACKAGE.md` + `onepager.md` + `openclaw_plugin/`.**
   v2.3 code/data/marketing carrying buy/sell + Sepolia. They don't drive the v4 product but
   they're committed and discoverable. **Decision:** move to an `archive/` tree or delete.

> I did not unilaterally take down the live dashboard or repoint the published package —
> those are outward-facing release decisions. They are surfaced here and in the Day-9 report.

---

## 6. What Day 9 fixed (in-scope, done)
- Canonical `COMPLIANCE_NOTICE` constant + every v4 surface reconciled to it.
- Compliance removed from metadata endpoints; **compliance regression test** added (21 assertions
  passing) + a CI workflow stub (`.github/workflows/compliance.yml`).
- Full README + quickstart rewrite to v4 voice (no buy/sell, no Sepolia, ~80 universe, v4
  commands, git-anchored verification, roadmap).
- DISCLAIMER, sdk readme, sdk compliance constant, pyproject keywords reconciled.
