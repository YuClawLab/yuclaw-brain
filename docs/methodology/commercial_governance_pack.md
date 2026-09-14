# Commercial / governance pack — data flow, retention, capability, clauses and outstanding ratifications (v7; factual)

**Purpose.** One factual reference for counsel's existing review route. It invents no legal determination, sovereign claim, outreach or grant eligibility; it cross-references the documents that actually govern the product today and lists what remains unratified.

## 1. Data flow (as implemented)
| flow | source → processing → output | governing text |
|---|---|---|
| Public filings | SEC EDGAR (public) → box-local extraction and a locked classification vocabulary → point-in-time snapshots, hash-chained ledger, Validation Lab, CLI/REST/MCP | `docs/API_TERMS.md` §1 (research/educational use only), §5 (data sources + attribution) |
| Market data | public derived market data → forward tracking → published statistics reproduced offline from the frozen Lab bundle | `docs/methodology/validation_lab.md`; `docs/replay/lab_replay_bundle.json` |
| BYOS Signal Review | a client CSV stays on the client's side (`yuclaw intake-check` transmits nothing); no upload endpoint (no-form gate); box-local analysis; deliverables are derived data only (export rule: no raw vendor rows) | `commercial_capability_brief.md`; `tools/check_no_forms.py` (release gate) |
| Receipt program (v7) | outsider verification packets, receipts, challenges and decisions in PRIVATE stores; public export only as typed pseudonymous rows after a designated review and the publication policy (denylist + language rail); refusal receipts never carry request text or identity | `receipts_program_spec.md` (candidate), `API_TERMS.md` §6 (privacy) |
| Telemetry | automated check-claim UNSUPPORTED / NOT_IDENTIFIABLE responses are private telemetry, never public refusal receipts | `receipts_program_spec.md` |

## 2. Retention (current state)
- Public artifacts: retained as published (ledger blocks, snapshots, releases); corrections supersede, never erase (`receipts_program_spec.md`; challenge dispositions retain the original finding).
- Private stores (receipts, challenges, decisions, appointments): append-only; no deletion path in the software; **retention period for private participant records: UNDECIDED (owner/counsel)** — listed as an outstanding item below.
- Study records (Gate #15 candidate protocol): proposed retention in `gate15_formative_study_kit.md` §6 (enrolment list destroyed at publication; reviewer forms 12 months) — **UNADOPTED**.
- Client BYOS material: never stored on the box by design (no upload path).

## 3. Capability statement (what the software establishes)
Exact-byte verification and offline reproduction of published statistics; derived counts with real zero/pending/UNBOUND states; no trust score; no financial statistic; no advice, execution or client positions. Evidence counts at this candidate: outsider receipts 0, human comprehension sessions 0, exact-target coverage UNBOUND. Research and education only (`API_TERMS.md` §1, §7).

## 4. Governance clauses cross-referenced
| clause | where it lives | status |
|---|---|---|
| Research/educational use only; no warranty; liability limits | `docs/API_TERMS.md` §1, §2, §7 | in force on the API surface |
| Acceptable use and rate limits | `docs/API_TERMS.md` §3, §4 | in force |
| Data sources and attribution | `docs/API_TERMS.md` §5 | in force |
| Privacy | `docs/API_TERMS.md` §6 | in force; receipt-program privacy contract is a candidate addition |
| Release gates (all required) and the A-6 authorization flow | master plan Phase 13; publisher preconditions | in force for releases; Gate #15 route = owner decision |
| Receipt program registration, reviewer appointment, floor | `receipts_program_spec.md` | proposal; D3 decisions pending |
| Canada Resources evidence-only tier (scoring = STOP) | `v3/universe_tiers.py`; `capacity_and_rtx_status.md` | in force |

## 5. Outstanding ratifications and blockers (candid)
1. **Counsel's data-versus-advice review** of the pilot engagement terms and the data-handling one-pager (drafts 2026-07-27) — the hard blocker for any real engagement; pilots stay at 0 with `PENDING_COUNSEL_REVIEW`.
2. Adviser-registration triggers — not determined here.
3. Retention period for private participant/receipt records — undecided.
4. Receipt-program registration record, reviewer appointment, floor disposition (D3) — pending.
5. Gate #15 release-policy route (D2) and the 7.0 allocation (D1) — pending.
6. Grant/sovereign-compute eligibility — no claim is made; nothing here supports one.
No commercial workflow is activated by this document.
