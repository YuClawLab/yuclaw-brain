# v7 capability matrix (candidate; updated at the end of V7-004)

Columns: **implementation** (code in the candidate) · **validation** (tests/gates actually run) · **authority** (protocol/owner decision that exists) · **observed evidence** (real, non-synthetic) · **activation** (what is switched on) · **release allocation** (7.0.0 ships / tooling only / deferred with owner decision). A disabled stub, a draft protocol or a green synthetic test is not a completed scientific capability.

| workstream | implementation | validation | authority | observed evidence | activation | release allocation |
|---|---|---|---|---|---|---|
| Outsider receipt program | engine `v3/receipts/` (submission/observation/review/export), CLI `receipts`, packet, challenge, decision, scoreboard; REST/MCP read surfaces | 14 adversarial + 8 journey tests (synthetic) | proposal only: no registration, no designated reviewer, no privacy review | 0 outsider receipts; 1 legacy affiliated program entry (PREFIX_ONLY) | local/synthetic; public scoreboard shows zero/pending | 7.0.0: tooling + scoreboard with real zero/pending; program registration = owner decision |
| Gate #15 | formative-study kit `docs/methodology/gate15_formative_study_kit.md` | n/a (document) | missing: ethics/privacy determination, protocol, reviewer, release-policy actor | none (scaffold GREEN only) | MANUAL_REVIEW unchanged | 7.0.0: kit shipped; gate stays MANUAL_REVIEW |
| U150→U250→U350→U550 | existing admission/membership machinery; readiness reporting (see §C notes) | existing constitution tests; boundary tests pending | GATE 5 shadow requirement; no promotion decision | Phase-A shadow evidence (10 anomaly days/25; 0 promotions) | shadow only | tooling; promotion = owner/protocol |
| Phase-C before Phase-B | prospective protocol draft (pending write) | admission-dependency test (pending) | no registration | none | none | draft only |
| Phase 6 / A2 / N_eff | existing structure exposed; N_eff guard test (pending) | pending | S undesignated; rule-4 decision pending | STRUCTURE_PRINTED, N_eff PENDING | none | tooling; A2 = Astra |
| C6 / Layer 2 / Form-4 accrual | existing deterministic path; bounded candidate tests (pending) | pending | registered C6 sign gate controls Layer 2 | sign UNCONFIRMED | live poller unchanged | tooling |
| ETF class membership | schema/admission validation (pending) | pending | addendum unapproved | ETF_SET empty | none | tooling |
| Phase-5 contribution anatomy | contract + fixtures (pending) | pending | registration pending | none | none | draft |
| Effective-evidence-count naming | UI label correction (pending) | pending | estimand pending | — | — | label only |
| Sentinel and nightly status | status adapter `v3/ops/nightly_status.py` (pending) | fixture logs (pending) | live delivery needs scoped order | 09-08…09-11 nightlies observed green | not activated | tooling |
| Note snapshot contract | contract v3 preserved; snapshot proposal (pending write) | 16 tests (b74676ae) | design = Astra | 4 green nightlies | v3 live | proposal |
| 2028 trading calendar | horizon inspection + boundary tests (pending) | pending | official dates unavailable | CALENDAR_RANGE 2026–2027 | — | explicit unsupported-horizon behavior |
| RTX capacity / evidence-only expansion | documentation (pending) | n/a | commissioning pending; owner disposition pending | measured capacity audit 2026-08-02 | — | doc only |
| Commercial readiness | capability/data-flow brief (pending) | n/a | counsel review = blocker | none | none | brief only |
| Governance and release | authority table (§2 delta); A-6 flow preserved | full gate run (Block D) | A-6 owner sentence required | — | — | Phase-1 handoff |
