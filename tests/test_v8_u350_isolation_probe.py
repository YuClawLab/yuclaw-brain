"""8.0.1 gate 4 repair — the U350 isolation check verifies WITHOUT provisioning and owns exactly one row per run.

Everything here runs against a DISPOSABLE PostgreSQL 16 node (tools/yuclaw_disposable_pg.py seeds the public schema like
hosted CI; v3.u350.ensure_namespace provisions the U350 role/schema/tables on that node — provisioning belongs to test
setup, never to the check). Production is never touched. The REAL check runs as a subprocess with only the node in its
environment. Proven:

  * correct configuration → the check passes and changes NOTHING (role attributes, every ACL, table structures identical
    before and after); exactly one row of this run was inserted and deleted; pre-existing rows — a legacy `_probe` row,
    another run's `_probe_…` row, the real manifest — are untouched;
  * an unexpected write privilege on a public table → the check FAILS at I0 before any DML and does NOT repair it;
  * schema drift (an extra column, a trigger on the probe table) → FAILS at I0 before any DML;
  * a concurrent, uncommitted probe row of another run is not blocked and survives;
  * a failure or a disconnection after the insert leaves no committed row of that run (rollback); the other rows stay;
  * a read-only session cannot turn a refused write into a pass (the error class differs → FAIL);
  * an unreachable database is a clean failure (rc 1, one line, no traceback);
  * the positive control refuses to run as anything but the U350 role.

Unavailable PostgreSQL 16 runtime → SKIPPED with the observed reason (never mock-green)."""
import json, os, pathlib, re, subprocess, sys, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
for p in (str(REPO), str(REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)
import yuclaw_disposable_pg as dpg     # noqa: E402

CHECK = REPO / "tools" / "check_u350_isolation.py"


def _node():
    try:
        return dpg.DisposableNode(REPO).start(), None
    except dpg.DisposableUnavailable as exc:
        return None, str(exc)


class U350Probe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node, cls.why = _node()
        if cls.node is None:
            return
        cls.env = cls.node.env(os.environ)                                 # only the node; no production connection material
        cls.saved = {k: os.environ.get(k) for k in dpg.LIBPQ_VARS + ("PGCLIENTENCODING",)}
        for k in dpg.LIBPQ_VARS + ("PGCLIENTENCODING",):
            os.environ.pop(k, None)
        os.environ.update({k: cls.env[k] for k in ("PGHOST", "PGPORT", "PGUSER", "PGCLIENTENCODING", "PGPASSFILE", "PGSERVICEFILE", "PGSYSCONFDIR")})
        import psycopg2
        from v3.u350 import ensure_namespace
        ensure_namespace()                                                  # PROVISIONING — test setup on the disposable node only
        cls.psycopg2 = psycopg2
        with psycopg2.connect("dbname=yuclaw_events") as cn, cn.cursor() as cur:
            cur.execute("INSERT INTO u350.manifest (phase, manifest_hash, members) VALUES ('A', 'real-manifest', %s)", (json.dumps([{"ticker": "SHADOWX"}, {"ticker": "NVDA"}]),))
            cur.execute("INSERT INTO u350.manifest (phase, manifest_hash, members) VALUES ('_probe', '_probe', '[]')")             # a legacy shared-identifier row
            cur.execute("INSERT INTO u350.manifest (phase, manifest_hash, members) VALUES ('_probe_other-run', 'other-run', '[]')")  # another run's row
            cn.commit()

    @classmethod
    def tearDownClass(cls):
        if cls.node is not None:
            cls.node.stop()
            for k, v in cls.saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def setUp(self):
        if self.node is None:
            self.skipTest("disposable PostgreSQL 16 node unavailable: " + self.why)

    # -- helpers -------------------------------------------------------------------------------------------------------
    def q(self, sql, *args):
        with self.psycopg2.connect("dbname=yuclaw_events") as cn, cn.cursor() as cur:
            cur.execute(sql, args or None)
            return cur.fetchall() if cur.description else None

    def x(self, sql):
        with self.psycopg2.connect("dbname=yuclaw_events") as cn, cn.cursor() as cur:
            cur.execute(sql)
            cn.commit()

    def config_snapshot(self):
        return {
            "role": self.q("SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolinherit FROM pg_roles WHERE rolname='u350_writer'"),
            "acls": self.q("SELECT n.nspname||'.'||c.relname, c.relacl::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','u350') AND c.relkind IN ('r','p') ORDER BY 1"),
            "schema_acl": self.q("SELECT nspname, nspacl::text, pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname IN ('public','u350') ORDER BY 1"),
            "columns": self.q("SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema='u350' ORDER BY 1,2"),
        }

    def counters(self):
        return self.q("SELECT n_tup_ins, n_tup_del FROM pg_stat_user_tables WHERE schemaname='u350' AND relname='manifest'")[0]

    def rows(self):
        return sorted(self.q("SELECT phase, manifest_hash FROM u350.manifest"))

    def run_check(self, extra_env=None):
        env = dict(self.env, **(extra_env or {}))
        r = subprocess.run([sys.executable, str(CHECK)], capture_output=True, text=True, timeout=300, cwd=str(REPO), env=env)
        return r.returncode, (r.stdout + r.stderr)

    # -- tests -----------------------------------------------------------------------------------------------------------
    def test_correct_configuration_passes_and_changes_nothing(self):
        before, rows0, (ins0, del0) = self.config_snapshot(), self.rows(), self.counters()
        rc, out = self.run_check()
        self.assertEqual(rc, 0, out)
        self.assertIn("configuration inspected, not changed", out); self.assertIn("both write refusals proven by attempt", out)
        m = re.search(r"run (\S+): row (_probe_\S+)/(\S+) inserted 1 and deleted 1 in one transaction, (\d+) other probe row", out)
        self.assertIsNotNone(m, out); run_id, phase, mhash, others = m.groups()
        self.assertEqual((phase, mhash), (f"_probe_{run_id}", run_id)); self.assertEqual(int(others), 2)            # the legacy row and the other run's row
        self.assertEqual(self.config_snapshot(), before)                                                              # nothing created, granted or revoked
        self.assertEqual(self.rows(), rows0)                                                                          # every pre-existing row untouched, no residue
        self.q("SELECT pg_stat_clear_snapshot()")
        ins1, del1 = self.counters(); self.assertEqual((ins1 - ins0, del1 - del0), (1, 1))                            # exactly this run's row

    def test_unexpected_write_privilege_fails_at_i0_and_is_not_repaired(self):
        self.x("GRANT INSERT ON public.events TO u350_writer")
        try:
            rows0, (ins0, _) = self.rows(), self.counters()
            rc, out = self.run_check()
            self.assertEqual(rc, 1, out); self.assertIn("FAILED at I0", out); self.assertIn("public.events:INSERT", out); self.assertIn("nothing was created, granted, revoked or written", out)
            self.assertTrue(self.q("SELECT has_table_privilege('u350_writer', 'public.events', 'INSERT')")[0][0], "the check must report drift, not repair it")
            self.q("SELECT pg_stat_clear_snapshot()"); self.assertEqual(self.counters()[0], ins0)                 # no DML happened
            self.assertEqual(self.rows(), rows0); self.assertEqual(self.q("SELECT count(*) FROM public.events WHERE event_id LIKE 'U350_ISOLATION_PROBE%'")[0][0], 0)
        finally:
            self.x("REVOKE INSERT ON public.events FROM u350_writer")

    def test_schema_drift_fails_at_i0_before_any_dml(self):
        self.x("ALTER TABLE u350.manifest ADD COLUMN drifted integer")
        try:
            ins0 = self.counters()[0]
            rc, out = self.run_check()
            self.assertEqual(rc, 1, out); self.assertIn("structure differs", out); self.assertIn("drifted", out)
            self.q("SELECT pg_stat_clear_snapshot()"); self.assertEqual(self.counters()[0], ins0)
        finally:
            self.x("ALTER TABLE u350.manifest DROP COLUMN drifted")
        self.x("CREATE FUNCTION u350.noop_trg() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$; CREATE TRIGGER t_noop BEFORE INSERT ON u350.manifest FOR EACH ROW EXECUTE FUNCTION u350.noop_trg()")
        try:
            rc, out = self.run_check()
            self.assertEqual(rc, 1, out); self.assertIn("user trigger", out)
        finally:
            self.x("DROP TRIGGER t_noop ON u350.manifest; DROP FUNCTION u350.noop_trg()")
        self.assertEqual(self.run_check()[0], 0)                                                                   # back to the registered configuration

    def test_concurrent_uncommitted_probe_row_is_neither_blocked_nor_touched(self):
        other = self.psycopg2.connect("dbname=yuclaw_events"); cur = other.cursor()
        cur.execute("INSERT INTO u350.manifest (phase, manifest_hash, members) VALUES ('_probe_concurrent', 'concurrent', '[]')")   # open transaction
        try:
            rc, out = self.run_check()
            self.assertEqual(rc, 0, out)                                                                             # different key: no lock conflict
            other.commit()
            self.assertEqual(self.q("SELECT count(*) FROM u350.manifest WHERE phase='_probe_concurrent'")[0][0], 1)
        finally:
            other.close(); self.x("DELETE FROM u350.manifest WHERE phase='_probe_concurrent'")

    def test_fault_after_insert_leaves_no_committed_row(self):
        from v3.u350 import ProbeFailure, positive_control, u350_connection
        rows0 = self.rows()
        cn = u350_connection()
        def boom():
            raise RuntimeError("injected fault after the insert")
        with self.assertRaises(ProbeFailure) as ctx:
            positive_control(cn, "fault-run", fault=boom)
        cn.close(); self.assertIn("injected fault", str(ctx.exception))
        self.assertEqual(self.rows(), rows0); self.assertEqual(self.q("SELECT count(*) FROM u350.manifest WHERE manifest_hash='fault-run'")[0][0], 0)

    def test_disconnection_after_insert_leaves_no_committed_row(self):
        from v3.u350 import ProbeFailure, positive_control, u350_connection
        rows0 = self.rows(); cn = u350_connection()
        with self.assertRaises(ProbeFailure):
            positive_control(cn, "interrupted-run", fault=cn.close)                                                  # the session ends mid-transaction
        self.assertEqual(self.rows(), rows0); self.assertEqual(self.q("SELECT count(*) FROM u350.manifest WHERE manifest_hash='interrupted-run'")[0][0], 0)

    def test_positive_control_refuses_a_non_u350_role(self):
        from v3.u350 import ProbeFailure, positive_control
        cn = self.psycopg2.connect("dbname=yuclaw_events")                                                          # the node superuser, not the U350 role
        with self.assertRaises(ProbeFailure) as ctx:
            positive_control(cn, "wrong-role")
        cn.close(); self.assertIn("must run as u350_writer", str(ctx.exception)); self.assertEqual(self.q("SELECT count(*) FROM u350.manifest WHERE manifest_hash='wrong-role'")[0][0], 0)

    def test_read_only_session_cannot_pass_and_writes_nothing(self):
        rows0, (ins0, _) = self.rows(), self.counters()
        rc, out = self.run_check({"PGOPTIONS": dpg.READ_ONLY_OPTION})
        self.assertEqual(rc, 1, out); self.assertIn("unexpected error class ReadOnlySqlTransaction", out)
        self.assertEqual(self.rows(), rows0); self.q("SELECT pg_stat_clear_snapshot()"); self.assertEqual(self.counters()[0], ins0)

    def test_unreachable_database_is_a_clean_failure(self):
        rc, out = self.run_check({"PGHOST": str(REPO / "no-such-socket-dir"), "PGPORT": "1"})
        self.assertEqual(rc, 1); self.assertIn("research database unreachable", out); self.assertNotIn("Traceback", out)


if __name__ == "__main__":
    unittest.main()
