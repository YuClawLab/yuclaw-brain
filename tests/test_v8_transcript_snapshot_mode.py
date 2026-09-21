"""V8-017 — the README transcript runs in ONE environment: YUCLAW_CORPUS=snapshot.

The first hosted run of the exact transcript comparison failed because `check-claim` answers from a research node where
one is reachable and from the bundled snapshot elsewhere; the passports differ. The transcript workflow now selects the
bundled snapshot explicitly. These tests use the REAL command line of this checkout (no stand-in) and prove:

  * explicit snapshot mode prints the same bytes with NO reachable research node and with a USABLE disposable test node
    configured in the environment — and never connects to that node (its connection log stays unchanged), while the
    default invocation on the same host DOES answer from the node (normal behaviour unchanged, separately shown);
  * the answer states its source (`corpus.mode = offline_snapshot`) and the snapshot is identified by sha256 as the
    checkout's file — the backend is never inferred from a field count;
  * an unsupported YUCLAW_CORPUS value is a usage error (exit 2), never a silent fall-back to a node;
  * a transcript recorded from a research-node answer FAILS the byte-for-byte comparison (field count and corpus lines).

The test node is a disposable PostgreSQL 16 cluster in a temp dir (private socket, no listen address, synthetic row).
Production services are never touched. Unavailable runtime → SKIPPED with the observed reason (never mock-green)."""
import hashlib, json, os, pathlib, re, shutil, stat, subprocess, sys, tempfile, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO / "tools")); sys.path.insert(0, str(REPO))
import cli_transcript as ct                                                     # noqa: E402

PGBIN = pathlib.Path("/usr/lib/postgresql/16/bin")
ACC = ct.UNIQUE
MARKER = "SYNTHETIC-TEST-NODE-ROW (never real evidence)"
LIBPQ = ("PGHOST", "PGPORT", "PGUSER", "PGDATABASE", "PGSERVICE", "PGSERVICEFILE", "PGPASSWORD", "PGPASSFILE", "PGSSLMODE", "PGOPTIONS", "PGHOSTADDR", "DATABASE_URL")


def real_cli(where: pathlib.Path) -> pathlib.Path:
    """The checkout's real `yuclaw` entry point as an executable (what an installed console script does)."""
    exe = where / "yuclaw"
    exe.write_text(f"#!/bin/sh\nexec \"{sys.executable}\" -c \"import sys; sys.path.insert(0, '{REPO}'); from v4.cli import main; sys.exit(main())\" \"$@\"\n")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


def claim(exe, env, *args):
    r = subprocess.run([str(exe), "check-claim", *args], capture_output=True, text=True, timeout=600, cwd=str(pathlib.Path.home()), env=env)
    return r.returncode, r.stdout, r.stderr


def without_generated(out: str) -> dict:
    d = json.loads(out); d.pop("generated"); return d


class SnapshotMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = pathlib.Path(tempfile.mkdtemp(prefix="v17-snapshot-mode-")); cls.exe = real_cli(cls.tmp)
        cls.base = {k: v for k, v in os.environ.items() if k not in LIBPQ and k != ct.CORPUS_ENV}
        cls.nowhere = dict(cls.base, PGHOST=str(cls.tmp / "no-such-socket-dir"), PGPORT="1")            # no reachable research node
        cls.node_env, cls.node_why = None, "not started"
        if not (PGBIN / "initdb").exists() or not (PGBIN / "pg_ctl").exists():
            cls.node_why = "PostgreSQL 16 initdb/pg_ctl not present"; return
        try:
            import psycopg2
        except ImportError:
            cls.node_why = "psycopg2 not importable"; return
        cls.pg = tempfile.mkdtemp(prefix="v17pg-"); cls.data = os.path.join(cls.pg, "data"); cls.port = 55000 + (os.getpid() % 1000); cls.log = os.path.join(cls.pg, "log")
        r = subprocess.run([str(PGBIN / "initdb"), "-D", cls.data, "-A", "trust", "-U", "t", "--no-instructions"], capture_output=True, text=True)
        if r.returncode != 0:
            cls.node_why = "initdb failed: " + r.stderr[-200:]; return
        r = subprocess.run([str(PGBIN / "pg_ctl"), "-D", cls.data, "-o", f"-p {cls.port} -k {cls.pg} -c listen_addresses='' -c log_connections=on", "-l", cls.log, "start", "-w"], capture_output=True, text=True)
        if r.returncode != 0:
            cls.node_why = "pg_ctl start failed: " + r.stderr[-200:]; return
        cls.started = True
        cn = psycopg2.connect(host=cls.pg, port=cls.port, user="t", dbname="postgres"); cn.autocommit = True; cn.cursor().execute("CREATE DATABASE yuclaw_events"); cn.close()
        cn = psycopg2.connect(host=cls.pg, port=cls.port, user="t", dbname="yuclaw_events"); cn.autocommit = True; cur = cn.cursor()
        cur.execute("CREATE TABLE events (event_id text, ticker text, event_type text, source_publish_time timestamptz, source_url text, raw_excerpt text, content_hash text, available_as_of timestamptz, event_status text)")
        cur.execute("INSERT INTO events VALUES (%s, 'NVDA', 'INSIDER_SELL', '2026-05-12T00:00:00Z', %s, %s, 'synthetic-hash', '2026-05-12T00:00:00Z', 'accepted')",
                    (f"NVDA_F4_{ACC.replace('-', '')}_1", f"https://www.sec.gov/Archives/edgar/data/1045810/{ACC.replace('-', '')}/x.xml", MARKER)); cn.close()
        cls.node_env = dict(cls.base, PGHOST=cls.pg, PGPORT=str(cls.port), PGUSER="t")                  # what the product's DSN `dbname=yuclaw_events` resolves through

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "started", False):
            subprocess.run([str(PGBIN / "pg_ctl"), "-D", cls.data, "stop", "-m", "fast", "-w"], capture_output=True)
        shutil.rmtree(getattr(cls, "pg", ""), ignore_errors=True); shutil.rmtree(cls.tmp, ignore_errors=True)

    def node_connections(self) -> int:
        return len(re.findall(r"connection authorized: user=t database=yuclaw_events", pathlib.Path(self.log).read_text(errors="replace")))

    # ------------------------------------------------------------------ no node needed
    def test_snapshot_mode_states_its_source_and_the_snapshot_is_identified(self):
        rc, out, err = claim(self.exe, dict(self.nowhere, **{ct.CORPUS_ENV: "snapshot"}), "--accession", ACC); self.assertEqual(rc, 0, err)
        d = json.loads(out); self.assertEqual(d["corpus"]["mode"], "offline_snapshot"); self.assertEqual(d["status"], "SOURCE_MATCHED")
        py = self.tmp / "python"; py.write_text(f"#!/bin/sh\nPYTHONPATH=\"{REPO}\" exec \"{sys.executable}\" \"$@\"\n"); py.chmod(0o755)   # the interpreter of this "installation"
        ident = ct.snapshot_identity(str(py)); want = hashlib.sha256((REPO / ct.SNAPSHOT_FILE).read_bytes()).hexdigest()
        self.assertEqual(ident["sha256"], want); self.assertEqual(ident["generated"], d["corpus"]["snapshot_generated"]); self.assertGreater(ident["objects"], 0)
        saved = dict(os.environ)
        try:
            os.environ.clear(); os.environ.update(self.nowhere)
            block = ct.build(str(self.exe), "fictional.whl", REPO); r = ct.examine(f"{ct.BEGIN}\n{block}\n{ct.END}", str(self.exe), "fictional.whl", REPO, python=str(py))
        finally:
            os.environ.clear(); os.environ.update(saved)
        self.assertTrue(r["ok"] and r["byte_exact"] and r["answers_from_bundled_snapshot"]); self.assertEqual(r["mode"], "YUCLAW_CORPUS=snapshot")
        self.assertTrue(r["snapshot"]["is_the_commits_file"] and r["snapshot"]["passports_state_this_snapshot"]); self.assertEqual(r["snapshot"]["sha256"], want)
        self.assertEqual([c["exit"] for c in r["commands"]], [0] * len(ct.COMMANDS)); self.assertEqual({c.get("corpus_mode") for c in r["commands"] if "corpus_mode" in c}, {"offline_snapshot"})

    def test_an_unsupported_selection_is_a_usage_error_never_a_silent_fallback(self):
        for bad in ("snapshots", "node", "off"):
            rc, out, err = claim(self.exe, dict(self.nowhere, **{ct.CORPUS_ENV: bad}), "--accession", ACC)
            self.assertEqual(rc, 2, (bad, out, err)); self.assertEqual(out, ""); self.assertIn(ct.CORPUS_ENV, err)
        for same in ("", "auto", " Snapshot "):
            rc, out, err = claim(self.exe, dict(self.nowhere, **{ct.CORPUS_ENV: same}), "--accession", ACC); self.assertEqual(rc, 0, (same, err))

    def test_the_transcript_tool_runs_every_command_in_snapshot_mode_whatever_the_caller_set(self):
        saved = dict(os.environ)
        try:
            for caller in (None, "auto", "snapshot"):
                os.environ.pop(ct.CORPUS_ENV, None)
                if caller:
                    os.environ[ct.CORPUS_ENV] = caller
                self.assertEqual(ct.transcript_env()[ct.CORPUS_ENV], "snapshot")
        finally:
            os.environ.clear(); os.environ.update(saved)

    # ------------------------------------------------------------------ with the disposable test node
    def need_node(self):
        if self.node_env is None:
            self.skipTest(f"disposable PostgreSQL 16 test node unavailable: {self.node_why}")

    def test_same_bytes_with_no_node_and_with_a_usable_test_node_and_the_node_is_never_contacted(self):
        self.need_node()
        # 1. the node IS usable and the DEFAULT invocation answers from it — normal research-node behaviour, unchanged
        before = self.node_connections(); rc, out, err = claim(self.exe, self.node_env, "--ticker", "NVDA", "--accession", ACC); self.assertEqual(rc, 0, err)
        d = json.loads(out); self.assertNotIn("corpus", d); self.assertEqual(d["status"], "SOURCE_MATCHED"); self.assertIn(MARKER, json.dumps(d["matched_evidence"]))
        self.assertGreater(self.node_connections(), before, "the default invocation must have connected to the configured test node")
        # 2. explicit snapshot mode on the SAME host configuration: bundled snapshot, zero connections to the node
        snap_env = dict(self.node_env, **{ct.CORPUS_ENV: "snapshot"}); before = self.node_connections(); outs = {}
        for args in (("--ticker", "NVDA", "--accession", ACC), ("--accession", ACC), ("--text", "NVDA reported an insider sale in May 2026")):
            rc_n, out_n, err_n = claim(self.exe, snap_env, *args); rc_0, out_0, err_0 = claim(self.exe, dict(self.nowhere, **{ct.CORPUS_ENV: "snapshot"}), *args)
            self.assertEqual((rc_n, rc_0), (0, 0), (err_n, err_0)); self.assertEqual(without_generated(out_n), without_generated(out_0), args)     # identical but for the run's own timestamp
            self.assertEqual(json.loads(out_n)["corpus"]["mode"], "offline_snapshot"); self.assertNotIn(MARKER, out_n); outs[args] = out_n
        self.assertEqual(self.node_connections(), before, "snapshot mode contacted the configured test node")
        # 3. the whole transcript: byte-identical in the two environments, and again no connection
        home = str(pathlib.Path.home()); saved = dict(os.environ)
        try:
            os.environ.clear(); os.environ.update(self.node_env); with_node = ct.build(str(self.exe), "fictional.whl", REPO)
            os.environ.clear(); os.environ.update(self.nowhere); without_node = ct.build(str(self.exe), "fictional.whl", REPO)
        finally:
            os.environ.clear(); os.environ.update(saved)
        self.assertEqual(with_node, without_node); self.assertEqual(self.node_connections(), before); self.assertEqual(home, str(pathlib.Path.home()))
        self.assertIn('"mode": "offline_snapshot"', with_node); self.assertIn("YUCLAW_CORPUS=snapshot", with_node.splitlines()[0])

    def test_a_block_recorded_from_a_research_node_answer_fails_the_exact_comparison(self):
        self.need_node()
        saved = dict(os.environ)
        try:
            os.environ.clear(); os.environ.update(self.nowhere)
            good = ct.build(str(self.exe), "fictional.whl", REPO); readme = f"# x\n\n{ct.BEGIN}\n{good}\n{ct.END}\n"
            self.assertTrue(ct.examine(readme, str(self.exe), "fictional.whl", REPO)["ok"])
            rc, out, _ = claim(self.exe, self.node_env, "--accession", ACC); node_body = ct._trim(out); self.assertNotIn('"corpus"', node_body)   # what a research-node host prints by default
            snap_body = ct._trim(claim(self.exe, dict(self.nowhere, **{ct.CORPUS_ENV: "snapshot"}), "--accession", ACC)[1]); self.assertIn(snap_body, good)
            r = ct.examine(readme.replace(snap_body, node_body), str(self.exe), "fictional.whl", REPO)
            self.assertFalse(r["ok"]); self.assertFalse(r["byte_exact"]); self.assertIn("first_differing_line", r); self.assertTrue(r["expected"] and r["actual"])
            fields = re.search(r"<(\d+) fields total", snap_body).group(1)                                                          # a changed field count alone fails too
            r = ct.examine(readme.replace(f"<{fields} fields total", f"<{int(fields) - 1} fields total"), str(self.exe), "fictional.whl", REPO); self.assertFalse(r["ok"]); self.assertIn("fields total", " ".join(r["expected"]))
        finally:
            os.environ.clear(); os.environ.update(saved)


if __name__ == "__main__":
    unittest.main()
