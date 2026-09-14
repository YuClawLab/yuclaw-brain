"""Form-4 accrual: fixture-backed END-TO-END integration through the REAL `backfill_form4`/`parse_filing` with a fake
HTTP layer (synthetic submissions JSON + XML) and a DISPOSABLE PostgreSQL 16 events table created from v3/schema.sql.
Covers accession identity, amendment exclusion, event/filing/acceptance time separation, dedup on rerun, cursor/retry
(fetch failure → no write, retry inserts), no write on parse failure, ingestion-time as-of never backdated, and that
no Layer-2/scoring field is written (C6 gate untouched). No SEC request, no production DB."""
import os, pathlib, re, shutil, subprocess, sys, tempfile, unittest
from datetime import date, datetime, timezone
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.sources import form4_parser as f4  # noqa: E402

PGBIN = pathlib.Path("/usr/lib/postgresql/16/bin")
XML = """<?xml version="1.0"?><ownershipDocument><reportingOwner><reportingOwnerId><rptOwnerName>SYNTHETIC OWNER</rptOwnerName></reportingOwnerId></reportingOwner>
<nonDerivativeTable><nonDerivativeTransaction><transactionDate><value>2026-09-10</value></transactionDate><transactionCoding><transactionCode>P</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>10000</value></transactionShares><transactionPricePerShare><value>10.5</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
<nonDerivativeTransaction><transactionDate><value>2026-09-10</value></transactionDate><transactionCoding><transactionCode>S</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>100</value></transactionShares><transactionPricePerShare><value>10.5</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction>
</nonDerivativeTable></ownershipDocument>"""
SUBMISSIONS = {"filings": {"recent": {"accessionNumber": ["0001-26-000001", "0001-26-000002", "0001-26-000003"], "form": ["4", "4/A", "4"], "filingDate": ["2026-09-10", "2026-09-10", "2026-09-12"],
                                        "primaryDocument": ["a.xml", "b.xml", "c.xml"], "acceptanceDateTime": ["2026-09-10T21:05:11.000Z", "2026-09-10T22:00:00.000Z", None]}}}


class FakeResp:
    def __init__(self, text=None, js=None): self.text = text; self._js = js
    def json(self): return self._js


class Form4EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (PGBIN / "initdb").exists():
            raise unittest.SkipTest("PostgreSQL 16 not present")
        try:
            import psycopg2  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("psycopg2 not importable")
        cls.tmp = tempfile.mkdtemp(prefix="yuclaw-f4pg-"); cls.data = os.path.join(cls.tmp, "data"); cls.port = 55000 + (os.getpid() % 1000)
        if subprocess.run([str(PGBIN / "initdb"), "-D", cls.data, "-A", "trust", "-U", "t", "--no-instructions"], capture_output=True).returncode != 0:
            shutil.rmtree(cls.tmp, ignore_errors=True); raise unittest.SkipTest("initdb failed")
        if subprocess.run([str(PGBIN / "pg_ctl"), "-D", cls.data, "-o", f"-p {cls.port} -k {cls.tmp} -c listen_addresses=''", "-l", os.path.join(cls.tmp, "log"), "start", "-w"], capture_output=True).returncode != 0:
            shutil.rmtree(cls.tmp, ignore_errors=True); raise unittest.SkipTest("pg_ctl start failed")
        import psycopg2
        def _connect():
            cn = psycopg2.connect(host=cls.tmp, port=cls.port, user="t", dbname="postgres"); cn.set_client_encoding("UTF8"); return cn   # independent of the process locale (the generator runs with LC_ALL=C)
        cls.connect = staticmethod(_connect)
        ddl = (REPO / "v3/schema.sql").read_text(); m = re.search(r"CREATE TABLE events \(.*?\);\n(?:CREATE (?:UNIQUE )?INDEX idx_events[^\n]*\n)+", ddl, re.S)
        cn = cls.connect(); cn.autocommit = True; cn.cursor().execute(m.group(0)); cn.close()
    @classmethod
    def tearDownClass(cls):
        subprocess.run([str(PGBIN / "pg_ctl"), "-D", cls.data, "stop", "-m", "fast", "-w"], capture_output=True); shutil.rmtree(cls.tmp, ignore_errors=True)
    def setUp(self):
        self.orig = (f4._fetch, f4._find_xml_url); self.calls = []
        f4._find_xml_url = lambda cik, acc, primary: f"https://synthetic.invalid/{acc}/{primary}"
        def fetch(url):
            self.calls.append(url)
            if url.startswith(f4.SUBMISSIONS_URL.format(cik="")) or "submissions" in url: return FakeResp(js=SUBMISSIONS)
            if "000003" in url: return FakeResp(text="<not xml")                      # parse failure filing
            return FakeResp(text=XML)
        f4._fetch = fetch
        cn = self.connect(); cn.autocommit = True; cn.cursor().execute("DELETE FROM events"); cn.close()
    def tearDown(self): f4._fetch, f4._find_xml_url = self.orig
    def rows(self):
        cn = self.connect(); cur = cn.cursor(); cur.execute("SELECT event_id, event_type, event_time, source_publish_time, available_as_of, source_url, content_hash, signal_impact, parent_event_id, attributes FROM events ORDER BY event_id"); r = cur.fetchall(); cn.close(); return r
    def test_end_to_end_accrual_identity_times_dedup_retry_and_no_layer2_write(self):
        cn = self.connect(); cn.autocommit = False
        st = f4.backfill_form4("SYN", "0000000001", date(2026, 9, 1), date(2026, 9, 30), False, cn)
        self.assertEqual(st["filings"], 2)                                                                             # the 4/A amendment is excluded by the registered original rule
        self.assertEqual((st["transactions"], st["trades"], st["kept"], st["de_minimis"], st["inserted"]), (2, 2, 1, 1, 1))   # the 100-share sale is de minimis → no row
        rows = self.rows(); self.assertEqual(len(rows), 1); r = rows[0]
        self.assertEqual(r[0], "SYN_F4_000126000001_0"); self.assertIn("0001-26-000001", r[5])                       # accession provenance in the id and the source url
        self.assertEqual(r[2], datetime(2026, 9, 10, 21, 5, 11, tzinfo=timezone.utc)); self.assertEqual(r[3], r[2]); self.assertEqual(r[4], r[3])   # batch mode: event/publish/as-of = acceptance time, not the filing date
        self.assertIsNone(r[7]); self.assertIsNone(r[8])                                                                # no Layer-2 / scoring field written by ingestion (signal_impact, parent_event_id)
        st2 = f4.backfill_form4("SYN", "0000000001", date(2026, 9, 1), date(2026, 9, 30), False, cn)                    # rerun → dedup, no new rows
        self.assertEqual((st2["inserted"], st2["dedup"]), (0, 1)); self.assertEqual(len(self.rows()), 1)
        # cursor/retry: a transient fetch failure of the XML → fetch_failed=1, no write; after the fetch recovers the same accession inserts once
        keep = f4._fetch
        def failing(url):
            if "000001" in url and "a.xml" in url: raise RuntimeError("transient")
            return keep(url)
        cn.cursor().execute("DELETE FROM events"); cn.commit(); f4._fetch = failing
        st3 = f4.backfill_form4("SYN", "0000000001", date(2026, 9, 1), date(2026, 9, 30), False, cn); self.assertEqual((st3["fetch_failed"], st3["inserted"]), (1, 0)); self.assertEqual(self.rows(), [])
        f4._fetch = keep; st4 = f4.backfill_form4("SYN", "0000000001", date(2026, 9, 1), date(2026, 9, 30), False, cn); self.assertEqual(st4["inserted"], 1)
        # parse failure (filing 3 returns non-XML) never writes; submissions fetch failure never writes
        self.assertEqual(sum(1 for r in self.rows() if "000003" in r[0]), 0)
        f4._fetch = lambda url: (_ for _ in ()).throw(RuntimeError("down")); st5 = f4.backfill_form4("SYN", "0000000001", date(2026, 9, 1), date(2026, 9, 30), False, cn); self.assertEqual(st5["filings"], 0); self.assertEqual(len(self.rows()), 1)
        f4._fetch = keep
        # ingestion-time as-of is never backdated (live/gap-backfill mode)
        cn.cursor().execute("DELETE FROM events"); cn.commit(); before = datetime.now(timezone.utc)
        f4.backfill_form4("SYN", "0000000001", date(2026, 9, 1), date(2026, 9, 30), False, cn, as_of_ingestion=True)
        r = self.rows()[0]; self.assertGreaterEqual(r[4], before); self.assertEqual(r[3], datetime(2026, 9, 10, 21, 5, 11, tzinfo=timezone.utc))
        # dry run writes nothing
        cn.cursor().execute("DELETE FROM events"); cn.commit(); f4.backfill_form4("SYN", "0000000001", date(2026, 9, 1), date(2026, 9, 30), True, cn); self.assertEqual(self.rows(), [])
        cn.close()
        self.assertTrue(all(u.startswith("https://synthetic.invalid/") or "submissions" in u for u in self.calls))       # no real SEC request


if __name__ == "__main__":
    unittest.main(verbosity=2)
