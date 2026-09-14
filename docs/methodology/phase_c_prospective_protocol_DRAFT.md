# Phase-C compatibility read before Phase B — prospective protocol DRAFT (v7; UNREGISTERED)

Status: draft for registration. Not registered, not run. Promotion of any shadow rung to canonical scoring requires this protocol (or a superseding one) to be registered before its observation window, an authorized study, and compatible results.

Population: the U350 Phase-A shadow sleeve (71 admitted names; admission manifest sha256 `f8c2e4c6834ef8a61d7fd1f77f718def01fc7dd013f42e7832148b4bdb20f545`), compared with the U79 canonical scoring universe under the same components and thresholds (unchanged; no tuning to historical outcomes).

Disclosure of prior observation: the Phase-A guard log (28 rows, 2026-08-02 → 2026-09-04) recorded 10 label-anomaly days (rule: shadow extreme-label share > max(3 × U79, 0.10) with ≥10 labels) and one drain-budget breach (2026-08-28). These observations pre-date this protocol and are disclosed; they cannot be used as the compatibility evidence.

Primary endpoint (pre-registered): over a fresh window of ≥ 20 trading sessions after registration, the shadow sleeve's extreme-label share must stay within the anomaly rule on ≥ 90% of sessions AND the composite-score distribution per component must not differ from U79 beyond the existing threshold table (`tools/check_universe_integrity.py` "thresholds match the live scorer").
Secondary: scoring completeness ≥ 95% issuer-days (constitution GATE 5); zero starvation days; drain GPU minutes within 48.0 per run.
Controls: C7 stays structurally inactive for the sleeve; no threshold, cap or exclusion enum changes during the window (truncation ledger anchors enforce this).
Stop/failure: any registered endpoint failure → NOT COMPATIBLE; no re-window without a superseding registration.
Outputs: a chain `run` line with the result hash; per-session table; no returns or performance metrics (structurally excluded from Phase-B admission).
Dependency test: candidate admission logic must refuse promotion when no registered Phase-C protocol id is present (see `tests/test_ladder_readiness.py`).
