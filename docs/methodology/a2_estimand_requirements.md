# Phase 6 · A2 — estimand and pooled-statistic requirements (for Astra's decision; v7)

What exists (stored, `output/oie/layered_dependency_first_read.json`, sha256 `0b2ac8a5967b13aa30841ab5f7508192f3abc9db420bdcd68389f8ffa9cac925`): verdict STRUCTURE_PRINTED; 421 eligible events; 9 clusters (34,831 unique edges; 43,507 rule-edge entries, rule 4 = 33,823); rules executable [1,2,3,4,5,7,11,12,14], absent [6,8,9,10,13,15,16]; `n_eff = PENDING — no pooled statistic designated (A1.7)`.

What A2 must supply before any numeric N_eff:
1. **Designated pooled statistic S** with units (e.g., mean CAR at horizon h over an event set E), the event-set definition, the horizon and the aggregation weights; the estimand must be a quantity whose sampling variance the dependency structure can inflate.
2. **Variance decomposition contract**: N_eff = N_raw · V_indep / (V_indep + Σ_t C_t) is DERIVED from S's variance under the printed edge structure; V_indep and C_t must be computed for S, not asserted. Components/clusters are not independent samples.
3. **Rule 4 decision** (the dominant edge source, 33,823 entries): keep as a dependency rule, down-weight by a justified kernel, or replace by a peer-correlation rule — chosen by scientific reasoning about the mechanism, never by which option raises N_eff. Alternatives to state: (a) rule 4 as-is; (b) rule 4 with a time-decay kernel; (c) rule 4 replaced by C7 peer-correlation edges (structurally inactive today).
4. **Validation prerequisites**: (i) the second read's registration line; (ii) a placebo where S is computed on a null event set (date-shuffled) to check N_eff behaves sensibly; (iii) unit test that absent S or unit mismatch yields "PENDING", never a number (candidate test: `tests/test_calendar_and_neff_guards.py`).
5. **Incident disposition**: the Falsification Battery third-run incident (chain line 80) must have a recorded disposition before further reads.
Nothing here designates S; the decision and the registration remain Astra's/owner's.
