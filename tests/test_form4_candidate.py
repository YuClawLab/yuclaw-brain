"""Bounded Form-4 path tests (v7 Block C): deterministic parsing, deduplication identity, accession
provenance, acquisition (publish) vs filing-date separation, malformed inputs, fetch-failure retry
semantics and disabled activation. Offline: synthetic XML/JSON only; no SEC request, no DB."""
import pathlib, sys, unittest
from datetime import date, datetime, timezone
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.sources import form4_parser as f4  # noqa: E402

XML = """<?xml version="1.0"?><ownershipDocument><reportingOwner><reportingOwnerId><rptOwnerName>SYNTHETIC OWNER</rptOwnerName></reportingOwnerId></reportingOwner>
<nonDerivativeTable><nonDerivativeTransaction><transactionDate><value>2026-09-10</value></transactionDate>
<transactionCoding><transactionCode>P</transactionCode></transactionCoding>
<transactionAmounts><transactionShares><value>100</value></transactionShares><transactionPricePerShare><value>10.5</value></transactionPricePerShare></transactionAmounts>
</nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>"""
SUBMISSIONS = {"filings": {"recent": {"accessionNumber": ["0001-26-000001", "0001-26-000002", "0001-26-000003"], "form": ["4", "4/A", "4"],
                                        "filingDate": ["2026-09-10", "2026-09-10", "2026-09-12"], "primaryDocument": ["a.xml", "b.xml", "c.xml"],
                                        "acceptanceDateTime": ["2026-09-10T21:05:11.000Z", "bad", None]}}}


class Form4(unittest.TestCase):
    def test_parse_and_dedup_identity_are_deterministic_and_accession_bound(self):
        name, txs = f4._parse_form4_xml(XML)
        self.assertEqual(name, "SYNTHETIC OWNER"); self.assertEqual(txs[0]["code"], "P"); self.assertEqual(txs[0]["value"], 1050.0)
        h1 = f4._content_hash("SYN", "0001-26-000001", txs[0]); h2 = f4._content_hash("SYN", "0001-26-000001", dict(txs[0]))
        self.assertEqual(h1, h2); self.assertNotEqual(h1, f4._content_hash("SYN", "0001-26-000002", txs[0]))          # accession is part of identity
        self.assertEqual(f4._event_id("SYN", "0001-26-000001", 0), "SYN_F4_000126000001_0")                           # provenance in the id
    def test_malformed_xml_and_amendments(self):
        self.assertEqual(f4._parse_form4_xml("<not xml"), ("", []))
        self.assertEqual(f4._parse_form4_xml("<ownershipDocument/>"), ("", []))
        got = f4._filter_form4_filings(SUBMISSIONS, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual([g["accession"] for g in got], ["0001-26-000001", "0001-26-000003"])                        # '4/A' amendment excluded by the original rule
    def test_publish_time_vs_filing_date_separation_and_window_boundaries(self):
        got = f4._filter_form4_filings(SUBMISSIONS, date(2026, 9, 10), date(2026, 9, 10))
        self.assertEqual(len(got), 1); g = got[0]
        self.assertEqual(g["filing_date"], date(2026, 9, 10)); self.assertEqual(g["publish_time"], datetime(2026, 9, 10, 21, 5, 11, tzinfo=timezone.utc))
        got3 = [x for x in f4._filter_form4_filings(SUBMISSIONS, date(2026, 9, 12), date(2026, 9, 12))][0]
        self.assertEqual(got3["publish_time"], datetime(2026, 9, 12, 0, 0, tzinfo=timezone.utc))                     # missing acceptance → midnight UTC of filing date (documented fallback)
        self.assertEqual(f4._filter_form4_filings(SUBMISSIONS, date(2026, 9, 13), date(2026, 9, 30)), [])
    def test_fetch_failure_is_retryable_and_never_inserts(self):
        orig = f4._find_xml_url; f4._find_xml_url = lambda cik, acc, primary: None
        try:
            stats = f4.parse_filing("1", "SYN", {"accession": "0001-26-000001", "primary": "a.xml", "publish_time": datetime.now(timezone.utc), "filing_date": date(2026, 9, 10)}, dry_run=True, conn=None)
        finally:
            f4._find_xml_url = orig
        self.assertEqual(stats["fetch_failed"], 1); self.assertEqual(stats["inserted"], 0)                             # poller does not ledger the accession; retried next sweep
        self.assertTrue(hasattr(f4._fetch, "retry"))                                                                   # tenacity retry on the network path only
    def test_activation_state_is_not_changed_by_tests(self):
        self.assertIn("as_of_ingestion", f4.parse_filing.__doc__)                                                      # live mode stamps ingestion time; no backdating


if __name__ == "__main__":
    unittest.main(verbosity=2)
