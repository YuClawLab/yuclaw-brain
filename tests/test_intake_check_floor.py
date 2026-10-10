"""intake-check on the declared minimum runtime: a CSV with NUL bytes (the abuse matrix's garbage case) is REFUSED with a
friendly message and exit 2 on every supported Python — never a traceback. Python 3.10's csv module raises
`_csv.Error: line contains NUL`, 3.11+ reads on; the validator refuses the same way before csv sees the bytes, and any
other csv.Error (malformed quoting) is turned into a refusal too. Found by the 9.0.0 publisher's floor-runtime check; the
published 8.0.1 leaks the traceback on 3.10."""
import contextlib, csv, io, pathlib, sys, tempfile, unittest
from unittest import mock

R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R))
from tools.yuclaw_client_intake import IntakeError, validate  # noqa: E402
from v3.cli import intake_check  # noqa: E402


class TestIntakeCheckFloor(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())

    def _run(self, path):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            rc = intake_check.main([str(path)])
        return rc, out.getvalue()

    def test_nul_bytes_are_refused_without_a_traceback_on_every_runtime(self):
        p = self.tmp / "garbage.csv"; p.write_text("\x00\x01\x02 not,a,csv\nat all")          # the abuse matrix's exact file
        with self.assertRaises(IntakeError) as cm:
            validate(p)
        self.assertIn("NUL", cm.exception.problems[0])
        rc, out = self._run(p)
        self.assertEqual(rc, 2); self.assertIn("would be REFUSED", out); self.assertNotIn("Traceback", out); self.assertNotIn("_csv.Error", out)

    def test_a_csv_error_from_the_reader_becomes_a_refusal(self):
        p = self.tmp / "ok.csv"; p.write_text("date,ticker,signal_value\n2026-01-05,NVDA,1.0\n")
        real = csv.DictReader

        class Broken(real):
            @property
            def fieldnames(self):
                raise csv.Error("line contains NUL")

        with mock.patch("tools.yuclaw_client_intake.csv.DictReader", Broken):
            with self.assertRaises(IntakeError) as cm:
                validate(p)
        self.assertIn("not a parseable CSV", cm.exception.problems[0]); self.assertIn("line contains NUL", cm.exception.problems[0])

    def test_a_malformed_quoted_row_is_refused_not_raised(self):
        p = self.tmp / "quote.csv"; p.write_text('date,ticker,signal_value\n2026-01-05,"NV"DA,1.0\n2026-01-06,AMD,"1\n')
        try:
            validate(p)
        except IntakeError as exc:                                                                   # either a parse refusal or a row refusal — never csv.Error
            self.assertTrue(exc.problems)
        rc, out = self._run(p)
        self.assertIn(rc, (0, 2)); self.assertNotIn("Traceback", out)

    def test_a_clean_file_still_passes(self):
        p = self.tmp / "clean.csv"; p.write_text("date,ticker,signal_value\n2026-01-05,NVDA,1.0\n2026-01-06,AMD,-0.5\n")
        rows, report = validate(p)
        self.assertEqual(len(rows), 2); self.assertEqual(report["n_tickers"], 2)
        rc, out = self._run(p); self.assertEqual(rc, 0); self.assertIn("INTAKE-CHECK OK", out)


if __name__ == "__main__":
    unittest.main()
