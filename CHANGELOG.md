# Changelog

All notable changes to YUCLAW. Format follows [keepachangelog](https://keepachangelog.com/en/1.1.0/).

## [6.0.1] — 2026-09-04

_Release date corrected to actual publish date (2026-09-04 10:07 UTC)._

Research & education only. Not investment advice.

### YUCLAW 6.0.1 — patch: public synchronization and CLI first-touch

patch — public synchronization and CLI first-touch; no methodology change; chain unchanged at 82.

#### Look-ahead statement — reconciled from retained records

A2 state (ii) — FACT ESTABLISHED, surfaces conflicted. From retained records only (the per-row llm_model tag on every evidence row, the local model manifest for that tag dated before the rows, the model blob's own GGUF header, the ingestion log and the worker configuration history), the only language model behind the governed in-sample rows is yuclaw-llm-70b = Meta Llama 3.1 70B Instruct, whose published pretraining cutoff is December 2023 (Meta model card); Form 4 rows come from a deterministic XML parser. The earliest in-sample date (2026-02-18) is about 26 months after that cutoff, so no filing text in the window could have been seen in training and the model's general market context also ends before the window — the README and Validation Lab wording that the cutoff "overlaps" the window was unsupported, while the methodology page's wording was correct. The supported conservative statement now stands on every surface: no parametric look-ahead from filings or market context; in-sample results remain a replay reconstruction (scoring design finalized after the window, market-layer inputs approximated, never exposed to real-time challenge) and stay disclosed as systematically optimistic and educational only. No disclosure was silently weakened: the optimism caveat is retained; only its unsupported mechanism was corrected. The registry chain records no look-ahead claim, so no registered statement is reinterpreted.

> In-sample look-ahead statement. The in-sample replay rows (signal dates 2026-02-18
> to 2026-05-13, evidence window 2026-02-18 to 2026-05-17) were built from evidence
> events extracted by one language model, Meta Llama 3.1 70B Instruct (served
> locally as yuclaw-llm-70b), whose published pretraining cutoff is December 2023
> (Meta model card). Form 4 events in the window come from a deterministic XML
> parser with no language model. The earliest in-sample date is about 26 months
> after that cutoff, so no filing text in the window could have been seen in
> training: there is no parametric look-ahead from the filings themselves, and the
> model's general market knowledge also ends before the window begins. The replay
> engine flags any as-of date before 2024-07-01 as inside the model's training
> window; no in-sample date triggers it. In-sample results nonetheless remain a
> replay reconstruction, not a live record: the scoring design was finalized in May
> 2026, after the window it is replayed over, market-layer components read
> approximated inputs, and no in-sample signal was exposed to external challenge in
> real time. In-sample results are therefore treated as systematically optimistic
> and educational only; the forward record (signal dates from 2026-05-20) is the
> look-ahead-free record.

#### Changed (copy and CLI ergonomics only)

- README and PyPI description: current-release framing (6.0.x → the GitHub Release), a first-touch command block with expected exit codes and a transcript from the release-candidate wheel, and the replication sentence derived from the public log (External-machine reproduction completed by an affiliated operator; unaffiliated replications: 0).
- Canada Resources: the evidence-tier count reads 53 = 49 Canada Resources issuers + 4 SMH-lens foreign filers (ASML, NXPI, STM, TSM), mirrored in the page's JSON.
- Today's Evidence: the two visible hashes carry distinct labels for the two distinct objects they are — "evidence-ledger root" (the Verified Research Ledger daily root) and "daily evidence block root" (the per-day public block root); no value, machine field or ledger meaning changed.
- SMH and XLK lenses: "effective evidence count" keeps its registered meaning; the line "Not the Phase-6 N_eff, which is PENDING." now sits beside it.
- Discovery: the capabilities name is "YUCLAW Evidence API" (former name recorded); the evidence index and llms.txt declare the version, the canonical base URL https://yuclaw.ca and every machine surface, all from one release manifest.
- Homepage: "Built in Canada — from Lake Ontario to Lake Louise and Kananaskis Lake — with gratitude to the country whose land and light frame this work."
- CLI: `yuclaw --help` / `-h` / `help` list every command with a one-line description (exit 0); `yuclaw check-claim --accession N` alone resolves the name from the same corpus the ticker path uses (one name → the existing passport; several → exit 2 with the candidates; none → UNSUPPORTED; malformed → exit 2); never a bare usage dump. Twelve first-touch cases are recorded against the built wheel.
- Release gates added: copy-consistency (canonical blocks byte-identical), version, base URL and endpoint inventory.

#### Unchanged

- Protocol registry: 82 chained lines, tip ac51ddfe…, byte-identical to 6.0.0. No statistic, estimator, threshold, artifact hash or ledger row changed.

#### Not in this release

- N_eff PENDING (the Phase-6 pooled-statistic N_eff — not the lens pages' effective evidence count)
- Phase-5 contribution anatomy NOT YET
- user-comprehension study NOT YET
- unaffiliated replications 0

## [6.0.0] — 2026-09-04

Research & education only. Not investment advice.

### YUCLAW 6.0.0 — Evidence-First Financial AI · The Science Trust Layer for Financial AI

Financial AI normally gives you an answer. YUCLAW gives you the evidence, what that evidence can support, what it cannot support, and whether that conclusion survived time.

#### Shipped objects — name · receipt · status

- Layered Evidence Dependency v1, first read · chain lines 81–82, sha256 0b2ac8a5967b13aa… · STRUCTURE_PRINTED — structural_completeness = PARTIAL; N_eff PENDING (the Phase-6 pooled-statistic N_eff — not the lens pages' effective evidence count); READ_SCOPE = STRUCTURAL_ONLY (chain 81–82)
- Science Trust surfaces — per-name research-state cards + machine JSON, 132 names · anchor ac51ddfe97eb… · gate GREEN (machine JSON equals the human card, byte-reproducible); staged preview, not linked from the live navigation
- Research states · sha256 0163fe63f72bb13f… · 132 names: INSUFFICIENT_EVIDENCE 132 — derived, never hand-maintained
- Discovery Ledger · sha256 4951bd6ade88722a… · 37 hypotheses in bijection with 37 registered protocol lines; status counts ACCRUING 18, INCONCLUSIVE 1, OPEN 7, REGISTERED 7, SUPERSEDED 4 — negative and inconclusive findings preserved
- Anytime Evidence Record · sha256 ac37757aa2fb8f62… · 3 prospective enrollments — ACCRUING, not adjudicated
- Evidence Completeness Profiles · sha256 3c3b4f0e6e494dfa… · 132 names; ETF class membership BLOCKED_BY_REGISTRATION
- Protocol registry · 82 chained lines, tip ac51ddfe…, chain-verified
- Public daily evidence ledger · 77 daily blocks, latest 2026-09-03 root 501adb8ec42e… · append-only, replayable
- C6 risk channel: rare-by-construction confirmed OOS (22% fire rate, n=9 held-out); sign positive at n=2 elevated — accruing · fourth read chain line 77 (98dcf74a827a…): DESCRIPTIVE
- Cross-lens reversal coherence · chain line 79 (be05bf7a9dc8…) · INSUFFICIENT — accruing, no coherence claim (chain 79)
- Consumer-posture gate · five deterministic stranger personas · GREEN (scaffold); full-form user-comprehension study NOT YET
- Replication · public log 1 entry, bundle sha256 f431f9c629ac38b5… · REPRODUCED — External-machine reproduction completed by an affiliated operator; unaffiliated replications: 0
- yuclaw 6.0.0 package · wheel + sdist sha256 attached to this release · CLI · REST · MCP · SDK

#### Not in this release

- N_eff PENDING (the Phase-6 pooled-statistic N_eff — not the lens pages' effective evidence count)
- Phase-5 contribution anatomy NOT YET
- user-comprehension study NOT YET
- unaffiliated replications 0

#### Made in Canada

Built in Canada — from Lake Ontario to Lake Louise and Kananaskis Lake — with gratitude to the country whose land and light frame this work.

## [5.3.3] — 2026-08-06

### Fixed

- **Passport status semantics**: `PARTIAL_MATCH` now requires at least
  one matched EvidenceObject (with some claim elements not matched). A
  claim that matches ZERO objects is `UNSUPPORTED` — the caption is
  unchanged: "not found in YUCLAW's corpus — never a truth verdict".
  The trigger was the empty-corpus-name case (DIA-style: a universe
  name with no evidence objects), which 5.3.2 stamped `PARTIAL_MATCH`
  with an empty `matched_evidence` array. As a side effect of the fix,
  a genuine partial match (e.g. type matched, window missed) now LISTS
  the objects that matched the matched elements instead of an empty
  array. Spec + PassportResult schema note updated; committed unit
  self-tests in `tests/test_passport_semantics.py`; the abuse matrix
  gains the empty-corpus case (32 → 33).
- **MCP offline fallback** (5.3.2's flagged same-class bug): MCP
  `get_evidence` now resolves via the bundled published-corpus snapshot
  when no research node is reachable (loud `corpus` scope block — the
  scope-block builder is shared with the CLI in
  `v3.evidence.snapshot.snapshot_corpus`, so the two surfaces cannot
  diverge). MCP `check_claim` — which already inherited the CLI's
  snapshot fallback through `passport()` — now uppercases
  `event_type`/`ticker` (case-sensitive matching made lowercase input
  silently miss) and returns the friendly public-JSON pointer instead
  of a generic "backend unavailable" when no corpus exists at all.
  MCP tools smoke-tested in the backend-less isolation suite.

### Changed

- `capabilities.json` `version` is derived from the package version at
  generation time (was hardcoded `v5.3`).
- The `why` no-backend hint gains the public-JSON pointer line
  (`https://yuclaw.ca/why/{TICKER}.json` — no backend needed).

## [5.3.2] — 2026-08-05

### Fixed

- **check-claim no-backend crash** (today's bug-class, closed): a valid
  structured or --text claim on a machine without a research node now
  resolves OFFLINE against a bundled published-corpus snapshot
  (`v3/evidence/corpus_snapshot.json.gz` — the same evidence_objects
  served at `why/{TICKER}.json`; 79 names, up to the published 100
  most-recent objects each, ~113 KB in the wheel). The passport carries
  an explicit `corpus` scope block (mode, snapshot date, per-name cap,
  live-URL confirm note); on-box passports are byte-identical to 5.3.1.
  Only when the snapshot itself is unreadable: friendly exit 3 pointing
  at the public JSON and the capabilities.json as-of recipe — never a
  traceback.
- **intake-check BOM**: CSVs are read as utf-8-sig, so Excel-exported
  files (BOM + CRLF + quoted fields) pass clean; non-UTF-8 bytes get a
  friendly refusal instead of a UnicodeDecodeError. The Excel-flavored
  fixture joins tests/fixtures.
- **Abuse-matrix gap closed**: the matrix now also feeds WELL-FORMED
  inputs under stranger conditions (run backend-less in the isolation
  suite) — a correct structured claim and a correct --text claim must
  produce a passport (offline) or the friendly research-node pointer,
  and the Excel-flavored CSV must pass intake-check clean. 28 → 32
  cases (29 hostile incl. new non-UTF-8 file + 3 well-formed).

### Changed

- CLI uppercases ticker arguments everywhere (why / verify / memo /
  check-claim; replay / events already did) and capabilities.json now
  states that JSON endpoints are case-sensitive uppercase
  (`why/NVDA.json`, not `why/nvda.json`).

## [5.3.1] — 2026-08-05

### Fixed

- **check-claim input hardening**: reversed date ranges, unknown event
  types, and bare invocations now return friendly one-liners with exit 2
  (previously a reversed range or unknown type silently produced an
  UNSUPPORTED passport — a validation error is never a corpus verdict);
  --type lists the valid taxonomy on rejection.
- **Exit-code contract** stated in help and enforced: 0 success · 1 ran
  with negative result · 2 usage/validation · 3 environment unsupported
  (verify's bad-date moved from 1 to 2).
- **Abuse matrix**: a permanent pre-release test feeds every subcommand
  the hostile input set (no/unknown args, reversed ranges, invalid dates,
  unknown types, empty/missing/garbage files) asserting zero tracebacks
  and contract-correct exits — runs in the isolation suite before every
  upload.
- **EvidenceBench items path**: format note (JSONL framing) published in
  capabilities.json, llms.txt, and the page; the index-completeness gate
  now also asserts every capabilities.json endpoint resolves.

## [5.3.0] — 2026-08-05

### Added — "Ground Truth"

- **Evidence Layer JSON API**: `why/{TICKER}.json` for all 79 names
  (anatomy + frozen EvidenceObjects + label history + the as-of
  reconstruction recipe), `capabilities.json` one-URL discovery,
  `evidence/verify.json` + per-day `ledger/{DATE}.json` for offline
  snapshot-integrity checks. Three new frozen schemas (EvidenceObject,
  WhyAnatomy, PassportResult) — eight total.
- **Evidence Passport**: `yuclaw check-claim` — deterministic claim check
  with five mechanical statuses; UNSUPPORTED means "not found in YUCLAW's
  corpus — never a truth verdict"; NOT_PARSEABLE guards against false
  denials on unstructurable text.
- **MCP v2**: get_evidence, get_signal_anatomy, check_claim,
  verify_snapshot, get_protocol — friendly no-backend behavior preserved.
- **EvidenceBench v0.1**: contamination-resistant groundedness benchmark —
  items regenerate weekly from post-cutoff evidence (generation spec
  registered, uncomputed-standard class); abstention outscores confident
  fabrication by construction; honest leaderboard opens with our own
  loudly-labeled self-evaluation row.
- **Dataset citability**: CITATION.cff, weekly dataset snapshot tags,
  release notes, "For researchers" on the replication page.

## [5.2.0] — 2026-08-05

### Added

- **`yuclaw intake-check`** — client-side pre-check of a signal CSV against
  the exact Signal Review intake rules (shared packaged module — client and
  server cannot drift). Runs entirely locally and says so; exit 0/2.
- **Five frozen v1 JSON Schemas** (SignalSnapshot, EvidenceEvent,
  ResearchProtocol, RobustnessCell, ResearchMemo) derived from live
  artifacts, served at /schemas/, checked against real outputs by a daily
  chain gate.
- **Evidence Coverage v1** (registered protocol `e3d51f5b0ca3`,
  descriptive/coverage class — explicitly not a return predictor) rendered
  on the home table and lens constituent tables with its locked caption.
- **Signal Review** product page (five-step no-upload flow, fixed founding
  tiers, EXPLORATORY (CLIENT) ceiling stated) + tier fulfillment profiles
  with a page-promise self-test; a no-form/upload/payment gate enforces the
  counsel-armed surface mechanically.
- **Universe Surface**: Explorer (client-side filter/sort over published
  data), 79 per-name Why pages (pinned template + nightly spot-walk),
  Sector overview (descriptive medians, display not inference), and the
  5-minute tour with build-captured command output.
- Nightly gate additions: schema validation, no-form, index-completeness,
  membership-drift, U350 isolation — the institutional-gates line
  continues to grow rather than shrink.

### Changed

- **License: Apache-2.0** (releases ≤5.1.x remain MIT as published);
  NOTICE ships in the wheel per Apache §4(d).
- README + comparison refresh: verify-first hero, yuclaw.ca links, honest
  v5.1 shipped-table; COMPARISON.md v1.3.

## [5.1.0] — 2026-07-31

### Added

- **The held subcommands ship**: `events` (accepted-event export, table/JSON/CSV),
  `lens` (lens summary JSON), `export` (derived-data packets), and the evidence
  memo interface (`memo --ticker/--days`, citation-verified) are now supported,
  documented surface. Backend-connected commands fail friendly without a local
  backend (message + exit 3, never a traceback — the 5.0.1 replay-lab pattern).
- **Public research panels (site)**: the SMH lens page now carries the
  four-estimand table with the conservative envelope AND a formal two-way
  cluster interval side by side, falsification battery, Form-4 transaction
  taxonomy, evidence structure/context robustness/evidence lifecycle panels,
  and the clustered decile panel on the Validation Lab — every statistic under
  a pre-registered protocol with cluster-aware inference. Headline updated to
  the completed-confirmation wording; adverse results reported as measured.
- **Evidence packets** now include the engine run artifacts
  (evidence_geometry / robustness_profile / evidence_lifecycle JSONs).

### Fixed

- Version coherence: site badge, README, User Guide, usage caveats, and the
  packaged metadata all say 5.1.0 (they disagreed across 5.0.0/5.0.1/v5.1).

## [5.0.1] — 2026-07-23

Bugs-only patch release. **No new subcommands; no scoring, methodology, or number
changes.** The pip CLI surface is identical to 5.0.0.

### Fixed

- **`replay-lab`: friendly network-error handling.** A failed bundle fetch now prints
  the URL tried, the HTTP code or reason, and the manual-download path
  (`yuclaw replay-lab /path/to/lab_replay_bundle.json`), and exits with a distinct
  code 3 (0 = reproduced, 1 = mismatch, 2 = usage, 3 = fetch failed) — no tracebacks.
- **`verify`: WARN wording.** A date/ticker with no ledger entry on this machine now
  says: "no ledger entry available on this machine — bundled demo: AMD @ 2026-05-20;
  full-record checks: yuclaw replay-lab or clone yuclaw-trust" (was a bare
  "no ledger entry", which read as a data problem on fresh installs).
- **`memo`: help text** clarifies that 5.0.x ships the earlier memo interface
  (positional ticker, `--as-of`); the evidence-memo CLI (`--ticker`/`--days`,
  citation-verified) ships in v5.1.

### Changed

- Docs only: caveats that said the `events` / `lens` / `export` / `memo` subcommands
  ship in "the next PyPI release" now say **v5.1** (5.0.1 ships without them). The
  packaged README refresh (Canada Resources links, User Guide, Forward Tracking
  naming) reaches the PyPI project page with this release.

## [4.0.1] — 2026-06-02

### Added

- **Bundled zero-backend demo.** `pip install yuclaw && yuclaw demo` now runs the full
  ~3-minute guided journey **offline** against the canonical **AMD @ 2026-05-20** signal —
  including the ledger-verification step, which recomputes the **byte-identical**
  `content_hash` (`fe7ca6df…`) committed to the public ledger. No local Postgres required.
  The demo-targeted commands (`why`, `memo`, `share`, `verify`, `cascade`) also resolve this
  one signal offline; any other ticker/date prints a clear backend-setup hint instead of an error.
  - New `v4/demo/fixtures/` (snapshot + events + ledger entry, ~10 KB) and
    `v4/demo/fixture_loader.py` (a read-only psycopg2-shaped shim).
  - Fallback triggers **only** when Postgres is unreachable — the live backend path is unchanged.

### Changed

- README: the demo is now presented as truly zero-config; the Postgres requirement is noted only
  for live signals across the full universe (`docs/v4/backend_setup.md`).

> 4.0.0 was functional but required a local backend for the demo; **4.0.1 is the recommended install.**

## [4.0.0] — 2026-06-03

v4.0 is the **Agent Research API** release. YUCLAW reads SEC filings and turns them
into *research classifications* with linked source evidence, an evidence-quality grade,
and a point-in-time hash anchored in a public git ledger — never buy/sell calls. This is
a major version: the package now installs the v3 evidence pipeline + the v4 API/CLI/SDK,
and the legacy v2.x momentum/trading stack is archived (see "Removed").

### Added

- **Unified response contract** (`v4/api/schema.py`) — a single Pydantic v2 `ResearchResponse`
  every surface returns: signal label (8-label locked vocabulary, no buy/sell), per-component
  anatomy (C1–C9 with score/confidence/rationale/evidence/`not_implemented`), composite
  confidence, evidence list, cascade, compliance block, and a `ledger_hash`. `no_data()` /
  `rate_limited()` factories; `extra="forbid"`.
- **REST API** (`v3/api/server.py`) — `/v1/signal`, `/v1/why`, `/v1/cascade`, `/v1/memo`,
  `/v1/share`, plus `/v1/verify`, `/v1/universe`, `/v1/openapi.json`, `/health`. Built on the
  shared `build_response()` builder so REST/CLI/MCP/SDK never diverge.
- **Memo Generator** — narrative research memo rendered from the locked schema (CLI `yuclaw memo`).
- **Agent-native interfaces** — MCP v2 server (`mcp.server.fastmcp.FastMCP`) plus
  LangChain (`BaseTool`) and LlamaIndex (`BaseRetriever` / `FunctionTool`) wrappers, so a signal
  is a first-class tool/retriever for AI agents.
- **`yuclaw demo`** — a ~3-minute guided "Why AMD?" journey on a real frozen signal: traced to
  its filings, point-in-time replayed, and verified against the public ledger.
- **Cascade History View** (`yuclaw cascade`) — supply/peer/cohort/etf/macro propagation across
  a hardcoded public edge graph, with decay and a de-minimis filter.
- **Share-this-Signal** (`yuclaw share`) — a self-contained, compliance-carrying HTML card.
- **API keys + metering** (`v4/auth/`) — SHA-256-hashed keys, free/anon daily tiers,
  per-request logging, `/v1/keys/info` + `/v1/keys/usage`, `429` with `retry_after`.
- **Single-source compliance** — canonical `COMPLIANCE_NOTICE` constant (version `draft-v0`);
  present on every signal response (including `401`/`429`), absent on metadata/account responses.
  Guarded by `tests/test_compliance_regression.py` (21 assertions).
- **Self-contained packaging** — `pip install yuclaw` now installs v3 + v4 + the `yuclaw_py` SDK;
  entry point `yuclaw` → `v4.cli:main`. Optional extras: `[api]`, `[mcp]`, `[agents]`.

### Changed

- `yuclaw` console entry point repointed from the v2.x trading CLI to the v4 research CLI.
- README / quickstart / DISCLAIMER reconciled to the canonical compliance wording; ~80-name
  research universe; all surfaces inherit the one `COMPLIANCE_NOTICE` constant.
- GitHub-Pages landing replaced with a minimal v4 page (`pip install yuclaw && yuclaw demo`).

### Removed

- The legacy **v2.x momentum/trading stack** (the `yuclaw/` monolith, `engines/`, `output/`,
  `data/`, `finclaw/`, `rebuild_html.py`, marketing one-pagers) is moved to `archive/v2/`
  (history preserved) and is **not** packaged or served. It used the older buy/sell vocabulary
  and on-chain anchoring framing that v4.0 deliberately moved away from.

### Verification posture

- Verification is **integrity, not merit**: a signal's content hash is committed to the public,
  git-anchored Verified Research Ledger (`yuclaw-trust`). This proves a signal existed at a given
  time and is unaltered since publication — it does **not** validate the underlying analytical claim.

## [2.3.0] — 2026-05-14

### Added

- **`yuclaw paper` command** — live Alpaca paper-trading path, distinct from
  the `yuclaw trade` campus simulation (which is untouched). Seven safety
  nets: paper-URL guard, validation ping with regenerate-keys guidance,
  `/v2/clock` market-hours check, $10k notional cap with `--force` override,
  first-run consent prompt, append-only audit log at `~/.yuclaw/orders.jsonl`,
  drawdown kill switch (HALT at −3% intraday, LIQUIDATE at −8%).
  ([`6bfe7e3`](../../commit/6bfe7e3), [`d83f102`](../../commit/d83f102))
- **`yuclaw/edge/broker_gateway.py`** — abstract broker interface, contract
  for future Robinhood/IB integrations.
- **`yuclaw/edge/alpaca_gateway.py`** — concrete REST client targeting
  `paper-api.alpaca.markets`. Hard-fails on init against live endpoints.
  Hand-rolled `requests`; no alpaca-py SDK dependency.
- **`yuclaw/edge/risk_gates.py`** — `RiskGate.check(current, baseline)`
  returns `ALLOW`/`HALT`/`LIQUIDATE` based on intraday drawdown against
  Alpaca's `account.last_equity` (auto-resets daily).
- **Live `Tok/s` and `Signal cycle` stat cards** on the dashboard via new
  `yuclaw/utils/inference_speed.py`, replacing the previously hardcoded
  "18.9 TOK/S" and "1.37ms LATENCY" strings. Measurements written to
  `output/inference_stats.json` by the nightly cron.
  ([`43c4cec`](../../commit/43c4cec))
- **`docs/methodology/backtest.md`** — transparency page covering what the
  dashboard's BACKTEST RESULTS card does and does not represent. Linked
  from dashboard footer, README, and DISCLAIMER.
  ([`eee2f84`](../../commit/eee2f84))
- **Aggregator v2.4 — 6-component per-ticker scoring**:
  `factor` 0.05 / `momentum` 0.40 / `ticker_calmar` 0.30 / `rsi_health` 0.15
  / `universe_calmar` 0.05 / `portfolio_risk` 0.05. Top STRONG_BUY tickers
  now have differentiated composites instead of tying at 0.708. Old
  implementation preserved at `yuclaw/modules/signal_aggregator_legacy.py`;
  set `YUCLAW_AGGREGATOR=legacy` to revert.
  ([`928bdae`](../../commit/928bdae))
- **Leveraged-ETF universe blocklist** (`SOXL/SOXS/TQQQ/SQQQ/UPRO/SPXU/`
  `FNGU/FNGD/BOIL/KOLD/NUGT/DUST/LABU/LABD/TNA/TZA`) so 3x/inverse products
  cannot distort momentum-weighted composites.
  ([`a013e2f`](../../commit/a013e2f))
- **Hourly oil intelligence cron** + nightly Nemotron brief split off the
  hourly fast path.
  ([`e3d40fb`](../../commit/e3d40fb), [`19bb90e`](../../commit/19bb90e))
- **Mobile-responsive dashboard CSS** — stack cards under 768px viewport
  for X traffic. Desktop ≥769px unchanged.
  ([`e30987b`](../../commit/e30987b))
- **Standalone `DISCLAIMER.md`** + disclaimer banner on every release notes
  page + repo description tightened (research only — not financial advice).
  ([`89742b1`](../../commit/89742b1), [`54c2b09`](../../commit/54c2b09))

### Changed

- **Renamed "Track Record" → "Backtest Results"** across dashboard card,
  CLI output, README, README_PACKAGE, and the one-pager (renamed from
  `institutional_onepager.md` to `onepager.md` in v2.3.0).
  Internal identifiers (`cmd_track`, `'track'` argparse dispatch,
  `output/track_record_*.json` file paths) unchanged.
  ([`f967ab5`](../../commit/f967ab5))
- **EIA oil-inventory query** now uses `facets[series][]=WCESTUS1`
  (U.S. weekly ending stocks of crude oil), where it had been picking
  the first unfiltered record (gasoline blending components imports,
  rendered as a bogus 0.1M bbl). Real inventory now reports ~452.9M.
  ([`26ab23b`](../../commit/26ab23b))
- **Nightly score regeneration cron** (`cron/nightly_score_refresh.sh`)
  now also captures pipeline runtime and Ollama inference speed via
  `yuclaw.utils.inference_speed`.
- **`health_monitor.sh` zombie alert threshold** raised from `>0` to
  `>5` to skip the benign baseline-zombie noise.
  ([`a0523a5`](../../commit/a0523a5))

### Fixed

- **48-day signal-freeze bug** in `signal_aggregator.py` — the upstream
  engines (factor_scan, backtest, risk, screener) were not in cron, so
  `aggregated_signals.json` had been showing March-23 scores dressed up
  with daily-fresh prices. The nightly refresh cron (also added) now
  regenerates scores every weekday after market close.
- **44-day oil-staleness bug** — `oil_engine.py` was not scheduled; the
  oil card on the dashboard had been rendering 2026-03-31 prices for
  six weeks. Now hourly.
  ([`e3d40fb`](../../commit/e3d40fb))
- **60-hour silent dashboard freeze** — `refresh_dashboard.sh` had been
  swallowing `git push` errors via `2>/dev/null`. After a v2.0.0 push
  from a sibling clone shifted `origin/main`, the cron's pushes were
  silently rejected as non-fast-forward and 88 commits piled up locally.
  Fixed by removing the muting and adding `git fetch + rebase --autostash`
  before push, so the cron self-heals from divergence.
  ([`bf12ef8`](../../commit/bf12ef8))
- **`health_monitor.sh` path bug** — was checking
  `/home/zhangd2/Yuclaw/docs/data/dashboard_state.json` (capital Y, the
  rarely-updated publishable clone) instead of `/home/zhangd2/yuclaw/...`
  (lowercase, the cron's working copy). Result: continuous STALE alerts
  against a file nothing was keeping fresh.
  ([`bf12ef8`](../../commit/bf12ef8))
- **`source ~/.yuclaw_env` env-export gap** — six cron wrappers were
  sourcing the env file without `set -a`, so `KEY=value` lines became
  shell-local and never reached Python subprocesses. Standardized to
  `{ set -a; source "$HOME/.yuclaw_env"; set +a; }` across all 7 cron
  scripts.
  ([`bf12ef8`](../../commit/bf12ef8))
- **News-sentiment parser** in `yuclaw/modules/news_sentiment.py` —
  Nemotron's reasoning content was leaking into the dashboard's
  `reason` field as raw thinking text ("We need to output JSON…").
  Parser now tries `content` then `reasoning_content`, attempts JSON
  parse on each, returns a clean "Unable to parse model response"
  fallback on failure.

### Removed

- **Hardcoded "18.9 TOK/S" and "1.37ms LATENCY"** stat cards.
  See "Added — live Tok/s and Signal cycle" above.

### Honest disclosures

- The dashboard's hardcoded `LUNR +14.68% | ASTS +10.44% | DELL +4.01%`
  row was **removed** during this release (see fix `ec444da`). The
  methodology page (`docs/methodology/backtest.md`) documents what the
  BACKTEST RESULTS panel does and does not represent.
- Real-measured Tok/s on the DGX Spark with the local LLM is **~2.2–2.7
  tok/s** on a 50-token generation, **not 18.9**. The previous marketing
  figure is now gone from the dashboard.
- **Model identity correction.** The Ollama tag `nemotron-3-super-local`
  is **Llama 3.1 70B (Q4_K_M, ~42 GB)** with a financial-analyst system
  prompt, **not** Nemotron 3 Super 120B. The actual Nemotron 3 Super 120B
  is wired in `yuclaw/core/router.py` as a dormant OpenRouter fallback
  (the real model is sm_121a-blocked on the vLLM path on this hardware,
  hence the Ollama-served Llama is the active production LLM). All
  public-facing surfaces (README, PyPI long_description, dashboard, repo
  descriptions, org bio) corrected in this release. Audit-log payloads
  schema-upgraded from `'model': 'nemotron-3-super-120B'` (string literal)
  to a structured object capturing both the Ollama tag and actual model
  metadata — see `yuclaw/memory/portfolio_memory_*.py` and
  `yuclaw/finclaw/full_pipeline.py`. Old on-chain anchors continue to
  encode the legacy literal; new anchors use the upgraded schema.

## [2.2.0] — 2026-05-12

See [v2.2.0 release notes](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v2.2.0).

## [2.1.0] — 2026-05-11

See [v2.1.0 release notes](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v2.1.0).

## [2.0.0] — 2026-05-10

See [v2.0.0 release notes](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v2.0.0).
