"""8.0.1 C02/C03 — "the backend could not be asked" is never reported as "the backend had nothing".

8.0.0: `PGHOST=<no such dir> yuclaw cascade AMD` printed "No supply-chain cascade reached AMD ." and exited 0;
`replay` / `validation` printed a driver traceback (exit 1); `memo` / `why` explained but exited 1 (the contract says
3 = environment unsupported). Now: backend unavailable → exit 3 with a message (and a JSON status with --json), a
confirmed zero-row answer → exit 0 and says it was queried, the bundled demo fixture says so, a real event renders,
bad arguments stay 2, and an unexpected internal error is NOT swallowed.

The "research node" here is a DISPOSABLE PostgreSQL 16 cluster in a temp dir (private socket, synthetic rows); the
commands reach it through PGHOST/PGPORT/PGUSER. Production is never addressed. Runtime absent → SKIPPED with the reason."""
import json, os, pathlib, shutil, socket, subprocess, sys, tempfile, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
PGBIN = pathlib.Path("/usr/lib/postgresql/16/bin")
LIBPQ = ("PGHOST", "PGPORT", "PGUSER", "PGDATABASE", "PGSERVICE", "PGSERVICEFILE", "PGPASSWORD", "PGPASSFILE", "PGSSLMODE", "PGOPTIONS", "PGHOSTADDR", "DATABASE_URL")
CANARY = "canary-password-never-print-7f3a"
COLS = ("event_id text, ticker text, event_type text, magnitude numeric, direction int, available_as_of timestamptz, raw_excerpt text, source_url text, llm_confidence numeric, "
        "cascade_depth int, content_hash text, parent_event_id text, event_status text")


def cli(env, *args):
    r = subprocess.run([sys.executable, "-m", "v3.cli", *args], capture_output=True, text=True, timeout=300, cwd=str(REPO), env=dict(env, PYTHONPATH=str(REPO)))
    return r.returncode, r.stdout, r.stderr


class BackendStates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="v801-states-"); base = {k: v for k, v in os.environ.items() if k not in LIBPQ}
        cls.nowhere = dict(base, PGHOST=os.path.join(cls.tmp, "no-such-socket-dir"), PGPASSWORD=CANARY)
        s = socket.socket(); s.bind(("127.0.0.1", 0)); closed_port = s.getsockname()[1]; s.close()
        cls.refused = dict(base, PGHOST="127.0.0.1", PGPORT=str(closed_port), PGPASSWORD=CANARY, PGCONNECT_TIMEOUT="5")
        cls.node, cls.why_no_node = None, "not started"
        if not (PGBIN / "initdb").exists():
            cls.why_no_node = "PostgreSQL 16 initdb/pg_ctl not present"; return
        try:
            import psycopg2
        except ImportError:
            cls.why_no_node = "psycopg2 not importable"; return
        cls.pg = tempfile.mkdtemp(prefix="v801pg-"); cls.data = os.path.join(cls.pg, "data"); cls.port = 57000 + (os.getpid() % 1000)
        if subprocess.run([str(PGBIN / "initdb"), "-D", cls.data, "-A", "trust", "-U", "t", "--no-instructions"], capture_output=True).returncode != 0:
            cls.why_no_node = "initdb failed"; return
        if subprocess.run([str(PGBIN / "pg_ctl"), "-D", cls.data, "-o", f"-p {cls.port} -k {cls.pg} -c listen_addresses=''", "-l", os.path.join(cls.pg, "log"), "start", "-w"], capture_output=True).returncode != 0:
            cls.why_no_node = "pg_ctl start failed"; return
        cls.started = True
        cn = psycopg2.connect(host=cls.pg, port=cls.port, user="t", dbname="postgres"); cn.autocommit = True; cn.cursor().execute("CREATE DATABASE yuclaw_events"); cn.close()
        cn = psycopg2.connect(host=cls.pg, port=cls.port, user="t", dbname="yuclaw_events"); cn.autocommit = True; cur = cn.cursor(); cur.execute(f"CREATE TABLE events ({COLS})")
        url = "https://www.sec.gov/Archives/edgar/data/1645590/000164559026000045/x.htm"
        cur.execute("INSERT INTO events VALUES ('HPE_SYN_1', 'HPE', 'M_AND_A_CLOSE', 0.5, 1, '2026-05-14T00:00:00Z', 'SYNTHETIC root event (fictional test row)', %s, 0.9, 0, 'synthetic-root-hash', NULL, 'accepted')", (url,))
        cur.execute("INSERT INTO events VALUES ('AMD_SYN_1', 'AMD', 'M_AND_A_CLOSE', 0.05, 1, '2026-05-14T00:00:00Z', 'via HPE→AMD(supply,w=0.10) from SYNTHETIC root (fictional test row)', %s, 0.9, 1, 'synthetic-leaf-hash', 'HPE_SYN_1', 'accepted')", (url,))
        cn.close(); cls.node = dict(base, PGHOST=cls.pg, PGPORT=str(cls.port), PGUSER="t", PGPASSWORD=CANARY)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "started", False):
            subprocess.run([str(PGBIN / "pg_ctl"), "-D", cls.data, "stop", "-m", "fast", "-w"], capture_output=True)
        shutil.rmtree(getattr(cls, "pg", ""), ignore_errors=True); shutil.rmtree(cls.tmp, ignore_errors=True)

    def clean(self, *texts):
        for t in texts:
            self.assertNotIn(CANARY, t); self.assertNotIn("Traceback", t)

    def test_cascade_unavailable_and_refused_are_exit_3_never_no_cascade(self):
        for env in (self.nowhere, self.refused):
            rc, out, err = cli(env, "cascade", "AMD"); self.assertEqual(rc, 3, err); self.assertEqual(out, ""); self.assertIn("backend unavailable", err); self.assertIn("NOT a result", err)
            self.assertNotIn("No supply-chain cascade", out + err); self.clean(out, err)
            rc, out, err = cli(env, "cascade", "AMD", "--json"); self.assertEqual(rc, 3); d = json.loads(out)
            self.assertEqual((d["status"], d["queried"], d["result"], d["exit_code"]), ("BACKEND_UNAVAILABLE", False, None, 3)); self.assertNotEqual(out.strip(), "null"); self.clean(out, err)

    def test_the_bundled_fixture_says_it_is_the_fixture(self):
        rc, out, err = cli(self.nowhere, "cascade", "AMD", "--as-of", "2026-05-20"); self.assertEqual(rc, 0, err); self.assertIn("Cascade into AMD", out); self.assertIn("source: bundled_demo_fixture", err); self.clean(out, err)
        rc, out, err = cli(self.nowhere, "cascade", "AMD", "--as-of", "2026-05-20", "--json"); self.assertEqual(rc, 0); self.assertIn("edges", json.loads(out))   # success payload unchanged: the tree itself

    def test_replay_validation_memo_why_follow_the_same_convention(self):
        for args in (("replay", "AMD", "--date", "2026-04-15"), ("validation",)):
            rc, out, err = cli(self.nowhere, *args); self.assertEqual(rc, 3, err); self.assertEqual(out, ""); self.assertIn("backend unavailable", err); self.clean(out, err)
            rc, out, err = cli(self.nowhere, *args, "--json"); self.assertEqual(rc, 3); self.assertEqual(json.loads(out)["status"], "BACKEND_UNAVAILABLE"); self.clean(out, err)
        for args in (("memo", "NVDA"), ("why", "NVDA")):
            rc, out, err = cli(self.nowhere, *args); self.assertEqual(rc, 3, err); self.assertIn("needs a local YUCLAW backend", err); self.clean(out, err)
        rc, out, err = cli(self.nowhere, "why", "AMD", "--as-of", "2026-05-20"); self.assertEqual(rc, 0, err)                                   # the cached demo signal still works offline

    def test_bad_arguments_stay_usage_errors_and_help_states_the_three_contracts(self):
        self.assertEqual(cli(self.nowhere, "replay", "AMD", "--date", "not-a-date")[0], 2); self.assertEqual(cli(self.nowhere, "cascade")[0], 2)
        rc, out, _ = cli(self.nowhere, "replay", "--help"); self.assertEqual(rc, 0)
        for needle in ("replay-lab", "why TICKER --as-of", "needs no database", "3 backend unavailable"):
            self.assertIn(needle, " ".join(out.split()))

    def test_an_unexpected_internal_error_is_not_swallowed(self):
        sys.path.insert(0, str(REPO)); from v4.api import cascade_cli
        orig = cascade_cli.build_cascade_with_source; cascade_cli.build_cascade_with_source = lambda *a, **k: (_ for _ in ()).throw(ValueError("synthetic internal defect"))
        try:
            with self.assertRaises(ValueError):
                cascade_cli.main(["AMD"])
        finally:
            cascade_cli.build_cascade_with_source = orig

    def test_a_reachable_node_zero_rows_is_a_result_and_a_real_event_renders(self):
        if self.node is None:
            self.skipTest(f"disposable PostgreSQL 16 test node unavailable: {self.why_no_node}")
        rc, out, err = cli(self.node, "cascade", "NVDA"); self.assertEqual(rc, 0, err); self.assertIn("No supply-chain cascade reached NVDA", out); self.assertIn("was queried: zero qualifying events", out)
        self.assertIn("source: research_node", err); self.clean(out, err)
        rc, out, err = cli(self.node, "cascade", "NVDA", "--json"); self.assertEqual((rc, out.strip()), (0, "null")); self.assertIn("queried, zero qualifying events", err)
        rc, out, err = cli(self.node, "cascade", "AMD", "--json"); self.assertEqual(rc, 0, err); d = json.loads(out); self.assertEqual(d["event"]["event_id"], "HPE_SYN_1")
        self.assertEqual([(e["parent_ticker"], e["child_ticker"]) for e in d["edges"]], [("HPE", "AMD")]); self.assertIn("source: research_node", err); self.clean(out, err)


if __name__ == "__main__":
    unittest.main()
