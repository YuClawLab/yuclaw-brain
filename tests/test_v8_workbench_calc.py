"""V8-002 §2/§3: typed schema and deterministic calculator. Pure functions; no store, no server, no browser.
Reproduces every fixture's expected block, the quarterly fixture, period mismatches, exact arithmetic and explicit blocking reasons."""
import json, pathlib, unittest
from decimal import Decimal

from v3.receipts.contracts import ContractError
from v8.workbench import calc, money, schema

D = pathlib.Path(__file__).resolve().parent / "fixtures" / "v8" / "commitments"


def _load(name):
    return json.loads((D / name).read_text())


class TestMoney(unittest.TestCase):
    def test_floats_and_exponents_refused(self):
        for bad in (1.5, True, "1e6", "NaN", "inf", "1.", ".5", "1,0"):
            with self.assertRaises(ContractError):
                money.parse_amount(bad)

    def test_exact_midpoint_and_delta(self):
        self.assertEqual(money.midpoint(Decimal(110000000), Decimal(120000000)), Decimal(115000000))
        self.assertEqual(money.midpoint(Decimal(27000000), Decimal(30000001)), Decimal("28500000.5"))
        self.assertEqual(money.to_json(Decimal("28500000.5")), "28500000.5"); self.assertEqual(money.to_json(Decimal("115000000.00")), 115000000)
        self.assertEqual(money.delta(money.parse_amount("0.30"), money.parse_amount("0.10")), Decimal("0.20"))   # no binary-float drift
        self.assertEqual(money.as_stated(Decimal(112000000), "millions"), "112 millions")


class TestSchema(unittest.TestCase):
    def test_every_blocking_reason_is_listed(self):
        raw = {"schema": schema.SCHEMA, "claim_id": "X", "issuer": {"name": "A", "ticker": "AAA", "cik": "0000000001"}, "metric": "revenue", "kind": "commitment", "statement": "s",
               "range": {"low": 1.5, "high": 2}, "unit": "USD", "currency": "usd", "scale_as_stated": "m", "basis": "gaap", "fiscal_period": "FY2026", "resolution_rule": "", "stated_at": "2026-1-1", "source": {}, "fictional": True}
        c, reasons = schema.check_claim(raw)
        self.assertIsNone(c)
        joined = "\n".join(reasons)
        for needle in ("range.low: floating point", "currency:", "scale_as_stated", "basis:", "fiscal_period: object", "resolution_rule", "source.kind", "source.rights"):
            self.assertIn(needle, joined)
        self.assertGreaterEqual(len(reasons), 10)

    def test_missing_period_currency_basis_rule_block_freeze(self):
        rec = schema.from_fixture(_load("001_base.json")); base = rec["claim"]
        for field in ("fiscal_period", "currency", "basis", "resolution_rule"):
            raw = dict(base); del raw[field]
            with self.assertRaises(ContractError) as cm:
                schema.validate_claim(raw)
            self.assertIn(field, str(cm.exception))

    def test_period_sanity(self):
        p, r = schema.check_period({"label": "Q3 FY2026", "type": "Q", "start": "2026-07-01", "end": "2026-12-31"}); self.assertIsNone(p); self.assertIn("spans", r[0])
        p, r = schema.check_period({"label": "FY2026", "type": "FY", "start": "2026-01-01", "end": "2026-12-31"}); self.assertEqual(p["type"], "FY")
        p, r = schema.check_period({"label": "Q3", "type": "Q", "start": "2026-09-30", "end": "2026-07-01"}); self.assertIn("before start", r[0])

    def test_source_hash_binds_excerpt_and_rights_agree(self):
        rec = schema.from_fixture(_load("001_base.json")); s = dict(rec["claim"]["source"]); s["excerpt"] = s["excerpt"] + " "
        _, r = schema.check_source(s); self.assertTrue(any("source_hash" in x for x in r))
        s = dict(rec["claim"]["source"], rights="UNKNOWN"); _, r = schema.check_source(s); self.assertTrue(any("rights" in x for x in r))

    def test_schema_file_matches_validator(self):
        js = json.loads((pathlib.Path(__file__).resolve().parents[1] / "schemas" / "CommitmentClaim.v1.json").read_text())
        self.assertEqual(tuple(js["required"]), schema.REQUIRED_CLAIM); self.assertEqual(tuple(js["$defs"]["source"]["required"]), schema.REQUIRED_SOURCE)
        self.assertEqual(tuple(js["$defs"]["period"]["required"]), schema.REQUIRED_PERIOD)


class TestCalc(unittest.TestCase):
    def _state(self, name):
        return calc.state_from_fixture_records(schema.from_fixture(_load(name)))

    def test_every_fixture_expected_block_is_reproduced(self):
        for e in json.loads((D / "manifest.json").read_text())["files"]:
            fx = _load(pathlib.Path(e["path"]).name); r = calc.adjudicate(self._state(pathlib.Path(e["path"]).name)); exp = fx["expected"]
            self.assertEqual(r["result"], exp["adjudication"], e["path"]); self.assertEqual(r["comparison_permitted"], exp["comparison_permitted"], e["path"])
            for k in ("original_contains_actual", "revised_contains_actual", "delta_vs_original_midpoint", "delta_vs_revised_midpoint"):
                self.assertEqual(r.get(k), exp[k], f"{e['path']}:{k}")
            if exp.get("uses_corrected_range"):
                self.assertTrue(r["uses_corrected_range"])

    def test_both_calculations_are_separate_and_no_inference(self):
        r = calc.adjudicate(self._state("001_base.json"))
        self.assertEqual((r["original"]["result"], r["revised"]["result"]), ("IN_RANGE", "IN_RANGE"))
        self.assertEqual((r["original"]["delta_vs_midpoint"], r["revised"]["delta_vs_midpoint"]), (-3000000, 2000000))
        self.assertEqual(r["original"]["midpoint"], 115000000); self.assertEqual(r["revised"]["midpoint"], 110000000)
        self.assertIn("not evidence of improved accuracy", r["no_inference"]); self.assertIn("formula", r["original"]); self.assertEqual(r["original"]["inputs"]["actual"], 112000000)

    def test_quarterly_fixture_and_period_mismatches(self):
        fx = _load("008_quarterly.json"); st = self._state("008_quarterly.json"); r = calc.adjudicate(st)
        self.assertEqual(r["result"], "IN_RANGE"); self.assertEqual(st["versions"][0]["claim"]["fiscal_period"], {"label": "Q3 FY2026", "type": "Q", "start": "2026-07-01", "end": "2026-09-30"})
        self.assertEqual((r["delta_vs_original_midpoint"], r["delta_vs_revised_midpoint"]), (-500000, 500000))
        for case in (fx["period_mismatch_case"], fx["period_mismatch_case"]["date_only_mismatch"]):
            r2 = calc.adjudicate(dict(st, outcome=dict(st["outcome"], fiscal_period=case["outcome_fiscal_period"])))
            self.assertEqual(r2["result"], "PERIOD_MISMATCH"); self.assertFalse(r2["comparison_permitted"]); self.assertIn("fiscal period", r2["reasons"][0]["reason"])
            self.assertIsNone(r2["original"]["delta_vs_midpoint"])
        # a full-year actual against the quarterly claim can never silently pass
        fy = _load("001_base.json"); fy_out = schema.from_fixture(fy)["outcome"]
        self.assertEqual(calc.adjudicate(dict(st, outcome=dict(fy_out, claim_id=st["versions"][0]["claim"]["claim_id"])))["result"], "PERIOD_MISMATCH")

    def test_mismatch_codes_are_explicit(self):
        st = self._state("001_base.json"); out = st["outcome"]
        self.assertEqual(calc.adjudicate(dict(st, outcome=dict(out, currency="EUR", unit="EUR")))["result"], "UNIT_MISMATCH")
        self.assertEqual(calc.adjudicate(dict(st, outcome=dict(out, basis="non-GAAP adjusted")))["result"], "INCOMPATIBLE_BASIS")
        self.assertEqual(calc.adjudicate(dict(st, outcome=dict(out, metric="operating income")))["result"], "METRIC_MISMATCH")
        self.assertEqual(calc.adjudicate(dict(st, outcome=dict(out, comparable=False)))["result"], "NOT_COMPARABLE_DECLARED")
        both = calc.adjudicate(dict(st, outcome=dict(out, basis="IFRS", currency="EUR", unit="EUR")))
        self.assertEqual(both["result"], "INCOMPATIBLE_BASIS"); self.assertEqual([x["code"] for x in both["reasons"]], ["INCOMPATIBLE_BASIS", "UNIT_MISMATCH"])

    def test_comparison_incomparable_on_basis_change(self):
        st = self._state("001_base.json"); a = st["versions"][0]["claim"]; b = dict(st["versions"][1]["claim"], basis="non-GAAP")
        c = calc.compare_versions(a, b); self.assertEqual(c["result"], "INCOMPARABLE"); self.assertEqual(c["reasons"][0]["field"], "basis"); self.assertNotIn("midpoint_delta", c)
        c2 = calc.compare_versions(a, st["versions"][1]["claim"]); self.assertEqual((c2["direction"], c2["midpoint_delta"], c2["overlap"]), ("LOWERED", -5000000, {"low": 110000000, "high": 115000000}))

    def test_out_of_range_is_distinct_and_distance_signed(self):
        r = calc.adjudicate(self._state("006_out_of_range.json"))
        self.assertEqual(r["result"], "OUT_OF_RANGE"); self.assertEqual(r["revised"]["distance_outside"], -7000000); self.assertEqual(r["original"]["distance_outside"], -12000000)


if __name__ == "__main__":
    unittest.main()
