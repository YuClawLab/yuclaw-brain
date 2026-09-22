"""8.0.1 — the release-state preflight runs in TWO database environments and never lets one leak into the other.

The generator (tools/yuclaw_release_state_v6.py) declares, per check, where it runs: production-data checks in a
read-only session; the write-requiring test suite on a disposable PostgreSQL node (tools/yuclaw_disposable_pg.py); the
production write probe (gate 4) NOT RUN unless explicitly allowed. These tests prove, without ever touching a
production database:

  * routing is declared and stable — the same answer whatever is reachable; the probe is not run by default;
  * the read-only guard is appended to the ambient libpq options (ours last, so it wins) and the ambient settings stay;
  * the disposable environment carries no production connection material (every libpq variable removed, no password
    file reachable, DATABASE_URL gone) and a description of any environment never contains a secret value;
  * an UNAVAILABLE disposable node means the write-requiring check is recorded NOT RUN and its command is never
    executed — no fallback to the ambient environment;
  * with a node available, a subprocess given only the disposable environment connects to THAT node through the
    product's fixed DSN (`dbname=yuclaw_events`), not to the bogus "production" the ambient environment names;
  * a session opened with the read-only guard cannot INSERT, cannot run DDL, and leaves row counts unchanged — shown
    on a disposable node standing in for production (SQLSTATE 25006), never on production.

Unavailable PostgreSQL 16 runtime → the node-backed tests are SKIPPED with the observed reason (never mock-green)."""
import json, os, pathlib, subprocess, sys, tempfile, textwrap, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
for p in (str(REPO), str(REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)
import yuclaw_disposable_pg as dpg          # noqa: E402
import yuclaw_release_state_v6 as gen       # noqa: E402

BOGUS_PRODUCTION = {"PGHOST": "/no/such/production/socket", "PGPORT": "1", "PGUSER": "prod_owner", "PGPASSWORD": "S3CRET-canary-value",
                    "PGPASSFILE": "/no/such/.pgpass", "PGSERVICE": "prod", "DATABASE_URL": "postgresql://prod_owner:S3CRET-canary-value@prod.example/yuclaw_events",
                    "PGOPTIONS": "-c application_name=ambient"}


def _node():
    try:
        return dpg.DisposableNode(REPO).start(), None
    except dpg.DisposableUnavailable as exc:
        return None, str(exc)


class DeclaredRouting(unittest.TestCase):
    def test_every_nightly_check_is_production_read_only_except_the_declared_probe(self):
        names = [gen._key(t, args) if False else t for t, args in gen.CHECKS]     # routing is by tool name
        self.assertIn("check_u350_isolation.py", names)
        self.assertEqual(set(gen.PRODUCTION_WRITE_PROBE_CHECKS), {"check_u350_isolation.py"})
        for t in names:
            expected = gen.ROUTE_PROBE_NOT_RUN if t in gen.PRODUCTION_WRITE_PROBE_CHECKS else gen.ROUTE_PRODUCTION_RO
            self.assertEqual(gen.route_for(t), expected, t)
            self.assertEqual(gen.route_for(t, node_available=False), expected, t)          # a missing node changes nothing here
        self.assertEqual(gen.route_for("check_u350_isolation.py", allow_probe=True), gen.ROUTE_PROBE_ALLOWED)

    def test_only_the_test_suite_is_write_requiring_and_it_never_falls_back(self):
        names = [n for n, _ in gen.EXTRA_CHECKS]
        self.assertEqual(set(gen.WRITE_REQUIRING_EXTRA), {"pytest tests"}); self.assertIn("pytest tests", names)
        self.assertEqual(gen.route_for("pytest tests", extra=True), gen.ROUTE_DISPOSABLE)
        self.assertEqual(gen.route_for("pytest tests", extra=True, node_available=False), gen.ROUTE_DISPOSABLE_UNAVAILABLE)
        for n in names:
            if n not in gen.WRITE_REQUIRING_EXTRA:
                self.assertEqual(gen.route_for(n, extra=True, node_available=False), gen.ROUTE_PRODUCTION_RO, n)

    def test_the_probe_is_not_run_by_default_and_its_record_says_so(self):
        marker = pathlib.Path(tempfile.mkdtemp(prefix="v8-probe-")) / "ran"
        rec = gen.run_check("check_u350_isolation.py", [], "deadbeef")
        self.assertEqual(rec["rc"], gen.RC_NOT_RUN_PROBE); self.assertTrue(rec["last"].startswith("NOT RUN"))
        self.assertEqual(rec["database"], gen.ROUTE_PROBE_NOT_RUN); self.assertEqual(rec["candidate_sha"], "deadbeef")
        self.assertIn("u350.manifest", rec["last"]); self.assertFalse(marker.exists())
        self.assertNotEqual(rec["rc"], 0)                                                   # gate 4 reads rc == 0 only


class Environments(unittest.TestCase):
    def test_read_only_guard_is_appended_last_and_keeps_the_ambient_settings(self):
        env = dpg.readonly_env(BOGUS_PRODUCTION)
        self.assertTrue(env["PGOPTIONS"].endswith(dpg.READ_ONLY_OPTION)); self.assertIn("-c application_name=ambient", env["PGOPTIONS"])
        self.assertEqual(env["PGHOST"], BOGUS_PRODUCTION["PGHOST"])                        # production is still where the check reads
        self.assertEqual(dpg.readonly_env({})["PGOPTIONS"], dpg.READ_ONLY_OPTION)
        self.assertTrue(dpg.describe_libpq(env)["read_only_guard"])

    def test_disposable_environment_has_no_production_material(self):
        env = dpg.disposable_env(dict(BOGUS_PRODUCTION, PATH="/usr/bin", HOME="/home/x"), "/tmp/v8pg-x/s", 55001, "/tmp/v8pg-x")
        for k, v in BOGUS_PRODUCTION.items():
            self.assertNotEqual(env.get(k), v, k)
        for k in ("PGPASSWORD", "DATABASE_URL", "PGSERVICE", "PGHOSTADDR"):
            self.assertNotIn(k, env)
        self.assertEqual((env["PGHOST"], env["PGPORT"], env["PGUSER"], env["PGCLIENTENCODING"]), ("/tmp/v8pg-x/s", "55001", dpg.NODE_USER, "UTF8"))
        self.assertTrue(env["PGPASSFILE"].startswith("/tmp/v8pg-x/")); self.assertFalse(os.path.exists(env["PGPASSFILE"]))
        self.assertEqual((env["PATH"], env["HOME"]), ("/usr/bin", "/home/x"))              # the process environment otherwise stays
        self.assertNotIn(dpg.READ_ONLY_OPTION, env.get("PGOPTIONS", ""))                    # the node is meant to be written to

    def test_descriptions_never_carry_a_secret(self):
        for env in (BOGUS_PRODUCTION, dpg.readonly_env(BOGUS_PRODUCTION), dpg.disposable_env(BOGUS_PRODUCTION, "/tmp/s", 1, "/tmp")):
            d = json.dumps(dpg.describe_libpq(env))
            self.assertNotIn("S3CRET", d); self.assertNotIn("prod.example", d)
        self.assertTrue(dpg.describe_libpq(BOGUS_PRODUCTION)["password_material_reachable"])
        self.assertIn("PGPASSWORD", dpg.describe_libpq(BOGUS_PRODUCTION)["variables_set"])   # the NAME is recorded, the value is not


class UnavailableNode(unittest.TestCase):
    def test_write_requiring_check_is_not_run_and_its_command_is_never_executed(self):
        marker = pathlib.Path(tempfile.mkdtemp(prefix="v8-norun-")) / "executed"
        argv = ["-c", f"import pathlib; pathlib.Path({str(marker)!r}).write_text('ran')"]
        rec = gen.run_extra("pytest tests", argv, "deadbeef", node=None, node_error="PostgreSQL 16 initdb/pg_ctl not present")
        self.assertEqual(rec["rc"], gen.RC_NOT_RUN_DISPOSABLE); self.assertEqual(rec["database"], gen.ROUTE_DISPOSABLE_UNAVAILABLE)
        self.assertIn("initdb/pg_ctl not present", rec["last"]); self.assertIn("never run against the ambient environment", rec["last"])
        self.assertFalse(marker.exists(), "the write-requiring command must not run when the node is unavailable")

    def test_missing_binaries_raise_instead_of_starting_anything(self):
        n = dpg.DisposableNode(REPO); n.bindir = None
        with self.assertRaises(dpg.DisposableUnavailable):
            n.start()
        self.assertFalse(n.started)


class WithANode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node, cls.why = _node()

    @classmethod
    def tearDownClass(cls):
        if cls.node is not None:
            cls.node.stop()

    def setUp(self):
        if self.node is None:
            self.skipTest("disposable PostgreSQL 16 node unavailable: " + self.why)

    def test_seeded_like_hosted_ci(self):
        ident = self.node.identity()
        files = [f["file"] for f in ident["seed"]["files"]]
        self.assertEqual(files[0], "v3/schema.sql"); self.assertEqual(files[-1], "tests/fixtures/v4_seed.sql")
        self.assertTrue(all(f["errors"] == 0 for f in ident["seed"]["files"] if not f["tolerated"]))
        self.assertTrue(all(len(f["sha256"]) == 64 for f in ident["seed"]["files"]))

    def test_a_subprocess_with_the_disposable_environment_reaches_the_node_not_the_ambient_host(self):
        env = self.node.env(dict(os.environ, **BOGUS_PRODUCTION))                          # the ambient names a bogus production
        before = self.node.connections()
        code = textwrap.dedent("""
            import psycopg2, json
            cn = psycopg2.connect("dbname=yuclaw_events"); cur = cn.cursor()
            cur.execute("select current_setting('unix_socket_directories'), current_user, (select count(*) from api_keys)")
            print(json.dumps(cur.fetchone())); cn.close()""")
        rec = gen.run_extra("pytest tests", ["-c", code], "deadbeef", node=self.node)
        self.assertEqual(rec["rc"], 0, rec["last"]); sock, user, n = json.loads(rec["last"])
        self.assertEqual((sock, user), (self.node.socket_dir, dpg.NODE_USER)); self.assertGreaterEqual(self.node.connections(), before + 1)
        self.assertEqual(rec["database"], gen.ROUTE_DISPOSABLE); self.assertFalse(rec["libpq"]["password_material_reachable"])
        self.assertNotIn("S3CRET", json.dumps(rec))

    def test_read_only_guard_blocks_insert_and_ddl_on_a_stand_in_for_production(self):
        import psycopg2
        base = dpg.disposable_env({}, self.node.socket_dir, self.node.port, self.node.dir)   # the node stands in for production
        guarded = dpg.readonly_env(base)
        def connect(env):
            return psycopg2.connect(host=env["PGHOST"], port=env["PGPORT"], user=env["PGUSER"], dbname="yuclaw_events", options=env.get("PGOPTIONS", ""))
        cn = connect(guarded); cur = cn.cursor()
        cur.execute("select count(*) from api_keys"); n0 = cur.fetchone()[0]
        with self.assertRaises(psycopg2.errors.ReadOnlySqlTransaction):
            cur.execute("insert into api_keys (key_id, key_hash, owner_email, notes) values ('ro-probe', 'x', 'ro@test', 'ro-probe')")
        cn.rollback()
        with self.assertRaises(psycopg2.errors.ReadOnlySqlTransaction):
            cur.execute("create table ro_probe (x int)")
        cn.rollback()
        cur.execute("select count(*) from api_keys"); self.assertEqual(cur.fetchone()[0], n0); cn.close()
        cn = connect(base); cur = cn.cursor(); cur.execute("select count(*) from api_keys"); self.assertEqual(cur.fetchone()[0], n0)   # nothing slipped through
        cur.execute("select to_regclass('ro_probe')"); self.assertIsNone(cur.fetchone()[0]); cn.close()

    def test_read_only_guarded_subprocess_cannot_write_through_the_product_dsn(self):
        base = dpg.disposable_env({}, self.node.socket_dir, self.node.port, self.node.dir)
        code = textwrap.dedent("""
            import psycopg2, sys
            cn = psycopg2.connect("dbname=yuclaw_events"); cur = cn.cursor()
            try:
                cur.execute("insert into request_logs (key_id, endpoint, ticker, status_code) values ('ro', '/x', 'X', 200)"); cn.commit(); print("WROTE"); sys.exit(1)
            except psycopg2.errors.ReadOnlySqlTransaction as e:
                print("refused", e.pgcode); sys.exit(0)""")
        rec = gen._run_argv(["-c", code], dpg.readonly_env(base), gen.ROUTE_PRODUCTION_RO, "deadbeef")
        self.assertEqual(rec["rc"], 0, rec["last"]); self.assertIn("refused 25006", rec["last"]); self.assertTrue(rec["libpq"]["read_only_guard"])


if __name__ == "__main__":
    unittest.main()
