"""Note-snapshot coordinator against a DISPOSABLE PostgreSQL 16 instance (initdb + pg_ctl in a temp dir, private
socket, no listen address). Synthetic data only; production is never touched. If the runtime is unavailable the
test is reported as SKIPPED with the observed reason (never mock-green)."""
import os, pathlib, shutil, subprocess, sys, tempfile, unittest, uuid
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.ops.note_snapshot import Coordinator, SnapshotError  # noqa: E402

PGBIN = pathlib.Path("/usr/lib/postgresql/16/bin")


def pg_available():
    if not (PGBIN / "initdb").exists() or not (PGBIN / "pg_ctl").exists():
        return False, "PostgreSQL 16 initdb/pg_ctl not present"
    try:
        import psycopg2  # noqa: F401
    except ImportError:
        return False, "psycopg2 not importable"
    return True, "ok"


class DisposablePG16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ok, why = pg_available()
        if not ok:
            raise unittest.SkipTest(f"disposable PostgreSQL 16 unavailable: {why}")
        cls.tmp = tempfile.mkdtemp(prefix="yuclaw-pg16-"); cls.data = os.path.join(cls.tmp, "data"); cls.port = 54000 + (os.getpid() % 1000)
        r = subprocess.run([str(PGBIN / "initdb"), "-D", cls.data, "-A", "trust", "-U", "t", "--no-instructions"], capture_output=True, text=True)
        if r.returncode != 0:
            shutil.rmtree(cls.tmp, ignore_errors=True); raise unittest.SkipTest("initdb failed: " + r.stderr[-200:])
        r = subprocess.run([str(PGBIN / "pg_ctl"), "-D", cls.data, "-o", f"-p {cls.port} -k {cls.tmp} -c listen_addresses=''", "-l", os.path.join(cls.tmp, "log"), "start", "-w"], capture_output=True, text=True)
        if r.returncode != 0:
            shutil.rmtree(cls.tmp, ignore_errors=True); raise unittest.SkipTest("pg_ctl start failed: " + r.stderr[-200:])
        import psycopg2
        def _connect():
            cn = psycopg2.connect(host=cls.tmp, port=cls.port, user="t", dbname="postgres"); cn.set_client_encoding("UTF8"); return cn   # independent of the process locale (the generator runs with LC_ALL=C)
        cls.connect = staticmethod(_connect)
        cn = cls.connect(); cn.autocommit = True; cur = cn.cursor()
        cur.execute("CREATE TABLE events (id serial primary key, ticker text, event_status text, created_at timestamptz default now())")
        cur.execute("INSERT INTO events (ticker, event_status) VALUES ('AAA','accepted'), ('AAA','accepted'), ('BBB','accepted'), ('CCC','pending')"); cn.close()
        cls.reg = pathlib.Path(cls.tmp) / "protocols.jsonl"; cls.reg.write_text('{"kind": "synthetic"}\n')
    @classmethod
    def tearDownClass(cls):
        subprocess.run([str(PGBIN / "pg_ctl"), "-D", cls.data, "stop", "-m", "fast", "-w"], capture_output=True); shutil.rmtree(cls.tmp, ignore_errors=True)
    SQL = "SELECT ticker, count(*) FROM events WHERE event_status='accepted' GROUP BY ticker ORDER BY ticker"

    def test_concurrent_late_commit_is_invisible_and_paths_agree(self):
        with Coordinator(self.connect, registry_files=[self.reg], lifetime_s=60) as co:
            self.assertTrue(co.snapshot_id)
            late = self.connect(); late.autocommit = True; late.cursor().execute("INSERT INTO events (ticker, event_status) VALUES ('AAA','accepted')"); late.close()   # commits AFTER the export
            a = co.read("producer", self.SQL); b = co.read("checker", self.SQL)
            self.assertEqual(a["rows"], [("AAA", 2), ("BBB", 1)]); self.assertTrue(co.require_equal(a, b))
            lab = co.label(); self.assertIn("snapshot_id", lab); self.assertNotIn("created_at", lab["meaning"].replace("never a created_at cutoff", ""))
        live = self.connect(); cur = live.cursor(); cur.execute(self.SQL); self.assertEqual(cur.fetchall()[0], ("AAA", 3)); live.close()   # the late commit exists outside the snapshot
        self.assertEqual(co.connections, []); self.assertIsNone(co.exporter); self.assertTrue(co.closed)
    def open_connections(self):
        cn = self.connect(); cur = cn.cursor(); cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname='postgres' AND pid <> pg_backend_pid() AND application_name=''"); n = cur.fetchone()[0]; cn.close(); return n
    def test_setup_failure_cleans_up_and_slow_query_is_bounded(self):
        base = self.open_connections()
        bad = self.connect.__func__ if hasattr(self.connect, "__func__") else self.connect
        class BrokenCursorConn:
            def __init__(self, real): self.real = real; self.autocommit = False
            def cursor(self): return self.real.cursor()
            def close(self): self.real.close()
        calls = []
        def connect_then_fail():
            cn = self.connect(); calls.append(cn)
            class C:
                autocommit = False
                def cursor(_):
                    class Cur:
                        def execute(_, *a, **k): raise RuntimeError("SQL failure before the exporter is assigned")
                    return Cur()
                def close(_): cn.close()
            return C()
        with self.assertRaises(SnapshotError) as cm:
            Coordinator(connect_then_fail, registry_files=[self.reg], lifetime_s=60).__enter__()
        self.assertIn(cm.exception.code, ("E_CONNECT_FAILED", "E_EXPORT_FAILED")); self.assertEqual(self.open_connections(), base)         # the leaked-candidate connection was closed
        with Coordinator(self.connect, registry_files=[self.reg], lifetime_s=1.0) as co:                                                    # statement_timeout ≈ 1 s bounds a slow query
            with self.assertRaises(SnapshotError) as cm: co.read("producer", "SELECT pg_sleep(5)")
            self.assertEqual(cm.exception.code, "E_READ_TIMEOUT"); self.assertTrue(co.closed)
        self.assertEqual(self.open_connections(), base)
        co = Coordinator(self.connect, registry_files=[self.reg], lifetime_s=60).__enter__(); a = co.read("producer", self.SQL); co._t0 -= 120   # expiry at completion/equality
        with self.assertRaises(SnapshotError) as cm: co.require_equal(a, a)
        self.assertEqual(cm.exception.code, "E_SNAPSHOT_EXPIRED"); self.assertEqual(self.open_connections(), base)
    def test_snapshot_expiry_and_import_failure(self):
        co = Coordinator(self.connect, registry_files=[self.reg], lifetime_s=60).__enter__()
        co.exporter.cursor().execute("ROLLBACK"); co.exporter.close(); co.exporter = None                # exporter gone → readers cannot import
        with self.assertRaises(SnapshotError) as cm: co.read("producer", self.SQL)
        self.assertEqual(cm.exception.code, "E_SNAPSHOT_EXPIRED")
        co = Coordinator(self.connect, registry_files=[self.reg], lifetime_s=60).__enter__(); co.snapshot_id = "00000000-00000000-1"
        with self.assertRaises(SnapshotError) as cm: co.read("producer", self.SQL)
        self.assertEqual(cm.exception.code, "E_IMPORT_FAILED"); self.assertIsNone(co.exporter)                # cleaned up on failure
        with self.assertRaises(SnapshotError) as cm: Coordinator(self.connect, registry_files=[self.reg], lifetime_s=0.0).__enter__()   # exhausted lifetime: refused at setup
        self.assertEqual(cm.exception.code, "E_SNAPSHOT_EXPIRED")
    def test_registry_drift_and_strict_mismatch(self):
        with Coordinator(self.connect, registry_files=[self.reg], lifetime_s=60) as co:
            a = co.read("producer", self.SQL); self.reg.write_text('{"kind": "synthetic", "drift": true}\n')
            with self.assertRaises(SnapshotError) as cm: co.require_equal(a, a)
            self.assertEqual(cm.exception.code, "E_REGISTRY_DRIFT")
        self.reg.write_text('{"kind": "synthetic"}\n')
        with Coordinator(self.connect, registry_files=[self.reg], lifetime_s=60) as co:
            a = co.read("producer", self.SQL); b = co.read("checker", "SELECT ticker, count(*) FROM events GROUP BY ticker ORDER BY ticker")   # a different read (not the same SQL) → strict mismatch
            with self.assertRaises(SnapshotError) as cm: co.require_equal(a, b)
            self.assertEqual(cm.exception.code, "E_STRICT_MISMATCH")
        missing = pathlib.Path(self.tmp) / "nope.jsonl"
        with self.assertRaises(SnapshotError) as cm:
            with Coordinator(self.connect, registry_files=[missing]): pass
        self.assertEqual(cm.exception.code, "E_REGISTRY_MISSING")


if __name__ == "__main__":
    unittest.main(verbosity=2)
