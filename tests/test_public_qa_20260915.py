"""Public-QA corrections (ORDER 2026-09-15A-FINAL): focused acceptance tests for A (coverage consistency), B (historical
completeness contract), C/D (benchmark rubrics + CLI identity contract), E (excerpt quality rules), F (table wrappers),
G (freshness formatter, placeholder detection, brand-avoid claims)."""
import contextlib, io, json, os, pathlib, subprocess, sys, tempfile, unittest
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "tools"))
from v3.evidence import history as H  # noqa: E402
from v3.bench import evidencebench as B  # noqa: E402
from v3.extract import excerpt_quality as Q  # noqa: E402
from v3.web import useful_blocks as UB  # noqa: E402
import check_coverage_consistency as CC  # noqa: E402
import check_language as CL  # noqa: E402


def obj(t, avail, acc, h):
    return {"ticker": t, "evidence_type": "INSIDER_SELL", "filing_date": avail[:10], "accession_number": acc, "excerpt": "x", "source_hash": h, "available_as_of": avail, "protocol_id": None}


class HistoryContract(unittest.TestCase):
    """B5: dates before/inside/after a capped preview; ties; complete small collection; missing page; mismatched build; DELL Sept 9."""
    def preview(self, objs, total):
        return H.collection_metadata(objs, scope="DELL accepted objects", total_available=total, cap=100, ordering=H.ORDERING_PREVIEW, build_id="b1", completeness="PREVIEW", corpus_start="2026-01-01T00:00:00+00:00", corpus_end="2026-09-15T00:00:00+00:00")
    def test_preview_never_claims_completeness(self):
        # newest-100 slice spans Sept 10–11 while 1332 older objects exist (the DELL Sept 9 example)
        objs = sorted([obj("DELL", f"2026-09-1{d}T1{i}:00:00+00:00", f"acc{d}{i}", f"h{d}{i}") for d in (0, 1) for i in range(5)], key=lambda o: H.sort_key(o), reverse=True)
        meta = self.preview(objs, total=1459)
        for D in ("2026-09-09", "2026-09-10T15:00:00+00:00", "2026-09-12"):          # before, inside, after the preview's window
            r = H.as_of_query(meta, objs, D); self.assertEqual(r["status"], "INCOMPLETE", D); self.assertIn("complete history", r["reason"])
        self.assertEqual(H.as_of_query(meta, objs, "2026-09-09")["objects"], [])          # partial result is returned with the status, never as a complete empty answer
        self.assertEqual(len(H.as_of_query(meta, objs, "2026-09-10T15:00:00+00:00")["objects"]), 5)
    def test_complete_small_collection_and_ties(self):
        objs = [obj("HPE", "2026-03-16T10:00:00+00:00", "a1", "h1"), obj("HPE", "2026-03-23T10:00:00+00:00", "a2", "h2"), obj("HPE", "2026-03-23T10:00:00+00:00", "a3", "h3")]   # tie on available_as_of
        meta = H.collection_metadata(objs, scope="HPE", total_available=3, cap=None, ordering=H.ORDERING_HISTORY, build_id="b1", completeness="COMPLETE", corpus_start="2026-01-01T00:00:00+00:00", corpus_end="2026-09-15T00:00:00+00:00")
        self.assertEqual(H.validate_collection(meta, objs), [])
        self.assertEqual(H.as_of_query(meta, objs, "2026-03-20")["status"], "COMPLETE"); self.assertEqual(len(H.as_of_query(meta, objs, "2026-03-20")["objects"]), 1)
        self.assertEqual(H.as_of_query(meta, objs, "2026-03-23")["status"], "COMPLETE"); self.assertEqual(len(H.as_of_query(meta, objs, "2026-03-23")["objects"]), 3)   # date-only D = end of day; both tied objects included
        self.assertEqual(H.as_of_query(meta, objs, "2026-02-01")["status"], "COMPLETE_EMPTY")
        self.assertEqual(H.as_of_query(meta, objs, "2025-12-31")["status"], "OUT_OF_RANGE"); self.assertEqual(H.as_of_query(meta, objs, "2026-10-01")["status"], "OUT_OF_RANGE")
        bad = list(reversed(objs)); self.assertIn("declared ordering", H.validate_collection(meta, bad)[0]); self.assertEqual(H.as_of_query(meta, bad, "2026-03-20")["status"], "INVALID")
        m2 = dict(meta, total_available=None); self.assertEqual(H.as_of_query(m2, objs, "2026-03-20")["status"], "INVALID")        # unknown count is never complete or zero
        m3 = dict(meta, total_available=5); self.assertEqual(H.as_of_query(m3, objs, "2026-03-20")["status"], "INVALID")           # COMPLETE must hold every object in scope
    def test_missing_page_and_mismatched_build(self):
        import check_history_completeness as HC
        with tempfile.TemporaryDirectory() as d:
            docs = pathlib.Path(d); (docs / "why").mkdir()
            objs = [obj("HPE", "2026-03-16T10:00:00+00:00", "a1", "h1")]
            hist = {"schema": "WhyHistory.v1", "ticker": "HPE", "build_id": "b1", "generated": "x", "collection": H.collection_metadata(objs, scope="HPE", total_available=1, cap=None, ordering=H.ORDERING_HISTORY, build_id="b1", completeness="COMPLETE", corpus_start=None, corpus_end=None), "evidence_objects": objs, "not_advice": "n"}
            (docs / "why" / "HPE.history.json").write_text(json.dumps(hist))
            prev = {"ticker": "HPE", "build_id": "b1", "evidence_objects": objs, "evidence_objects_collection": H.collection_metadata(objs, scope="HPE", total_available=1, cap=100, ordering=H.ORDERING_PREVIEW, build_id="b1", completeness="PREVIEW", corpus_start=None, corpus_end=None)}
            (docs / "why" / "HPE.json").write_text(json.dumps(prev))
            import hashlib
            man = {"build_id": "b1", "files": {"HPE": {"sha256": hashlib.sha256((docs / "why" / "HPE.history.json").read_bytes()).hexdigest(), "count": 1}}}
            (docs / "why" / "history_manifest.json").write_text(json.dumps(man))
            self.assertEqual(HC.check(docs, tickers=["HPE"]), [])
            (docs / "why" / "HPE.history.json").unlink(); self.assertTrue(any("missing" in x for x in HC.check(docs, tickers=["HPE"])))      # missing page = incomplete
            (docs / "why" / "HPE.history.json").write_text(json.dumps(dict(hist, build_id="b2"))); self.assertTrue(any("build" in x for x in HC.check(docs, tickers=["HPE"])))   # mixed builds rejected


class CoverageConsistency(unittest.TestCase):
    """A3: the known defect (homepage 68 vs Explorer 75 for TSLA from different artifact generations) fails; a consistent render passes."""
    def fixture(self, d, home_val, ident_home, ident_cov=("2026-09-14T23:01:55+00:00", "a" * 64)):
        docs = pathlib.Path(d); (docs / "why").mkdir(parents=True)
        cov = {"schema": "coverage/1", "metric_id": "ecs", "as_of": ident_cov[0], "source_identity": {"sha256": ident_cov[1]}, "tickers": {"TSLA": {"ecs": 75}}}
        (docs / "coverage.json").write_text(json.dumps(cov))
        (docs / "explorer_data.json").write_text(json.dumps({"generated": "x", "coverage_source": {"as_of": ident_cov[0], "source_sha256": ident_cov[1], "metric_id": "ecs"}, "rows": [{"ticker": "TSLA", "ecs": 75}]}))
        (docs / "index.html").write_text(f'<table data-coverage-metric="ecs" data-coverage-as-of="{ident_home[0]}" data-coverage-sha256="{ident_home[1]}"><tr><td>TSLA</td><td>NEUTRAL</td><td>+0.3</td><td>{home_val}</td></tr></table>')
        (docs / "why" / "TSLA.json").write_text(json.dumps({"ticker": "TSLA", "evidence_coverage": {"ecs": 75, "as_of": ident_cov[0], "source_sha256": ident_cov[1]}}))
        (docs / "why" / "TSLA.html").write_text('<div data-ecs="75">75</div>')
        return docs
    def test_defect_fails_and_corrected_render_passes(self):
        real = CC.__dict__["check"].__globals__
        import v3.universe_tiers as U
        orig = U.scoring_universe; U.scoring_universe = lambda: {"TSLA"}
        try:
            with tempfile.TemporaryDirectory() as d:
                docs = self.fixture(d, home_val=68, ident_home=("2026-09-13T23:01:00+00:00", "b" * 64))
                f = CC.check(docs); self.assertTrue(any("index.html: TSLA ecs 68 != artifact 75" in x for x in f)); self.assertTrue(any("different artifact identity" in x for x in f))
            with tempfile.TemporaryDirectory() as d:
                docs = self.fixture(d, home_val=75, ident_home=("2026-09-14T23:01:55+00:00", "a" * 64)); self.assertEqual(CC.check(docs), [])
        finally:
            U.scoring_universe = orig


class BenchRubrics(unittest.TestCase):
    ITEMS = [{"item_id": "t1", "template": "T1", "question": "What does the excerpt say about TSLA in accession 0001-26-000001?", "key": {"excerpt": "Wilson-Thompson Kathleen S 7501 shares @ $414.85 on 2026-02-25 ($3,111,790)", "accession": "0001-26-000001", "event_type": "INSIDER_SELL", "shares": 7501, "price": 414.85, "date": "2026-02-25"}},
             {"item_id": "t2", "template": "T2", "question": "What type of event is filing 0001-26-000001?", "key": {"event_type": "INSIDER_SELL", "accession": "0001-26-000001"}}]
    def test_v1_reproduces_the_echo_defect(self):
        preds = {"t1": self.ITEMS[0]["question"], "t2": self.ITEMS[1]["question"]}
        r = B.score(self.ITEMS, preds, rubric="v1", label="echo", items_sha256="x")
        self.assertEqual(r["per_type"]["T1"], 1.0); self.assertEqual(r["per_type"]["T2"], 0.0); self.assertIn("not validated", r["limitation"])
    def test_v2_contract_cases(self):
        def s(ans, item=0):
            return B._score_v2_item(self.ITEMS[item], ans)
        self.assertEqual(s(self.ITEMS[0]["question"])[0], 0.0)                                                                      # question echo
        self.assertEqual(s("0001-26-000001")[1], "EVENT_TYPE_MISSING")                                                            # accession only
        self.assertEqual(s("The weather was nice. See 0001-26-000001.")[1], "EVENT_TYPE_MISSING")                                    # unrelated prose + valid accession
        self.assertEqual(s("In 0001-26-000001 Kathleen Wilson-Thompson sold 7,501 shares at $414.85 on 2026-02-25.")[0], 1.0)      # supported
        self.assertEqual(s("In 0001-26-000001 Kathleen Wilson-Thompson bought 7,501 shares at $414.85 on 2026-02-25.")[1], "CONTRADICTION_DIRECTION")
        self.assertEqual(s("In 0001-26-000001 she sold 9,999 shares at $414.85 on 2026-02-25.")[1], "CONTRADICTION_VALUE:shares")
        self.assertEqual(s("cannot verify from the evidence provided")[1], "ABSTAIN"); self.assertEqual(s("")[1], "MISSING")
        self.assertEqual(s("sold", 1)[0], 0.0); self.assertEqual(s("insider sale, filing 0001-26-000001", 1)[0], 1.0)
        with self.assertRaises(B.BenchError): B._score_v2_item({"item_id": "e", "template": "T1", "question": "q", "key": {}}, "anything")    # empty key: never a silent zero
        with self.assertRaises(B.BenchError): B.score(self.ITEMS, {}, rubric="v9", label="x", items_sha256="x")
    def test_cli_reads_the_supplied_items_and_enforces_identity(self):
        from v3.cli import evidencebench as CLI
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d); a = d / "a.jsonl"; b = d / "b.jsonl"; p = d / "p.json"
            a.write_text(json.dumps(self.ITEMS[0]) + "\n"); b.write_text(json.dumps(self.ITEMS[1]) + "\n"); p.write_text(json.dumps({"t1": "x", "t2": "insider sale 0001-26-000001"}))
            def run(argv):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err): rc = CLI.main(argv)
                return rc, out.getvalue(), err.getvalue()
            rc, out, _ = run(["score", str(p), "m", "--items", str(a)]); self.assertEqual(rc, 0); self.assertEqual(json.loads(out)["n_items"], 1); self.assertIn("T1", json.loads(out)["per_type"])
            rc, out, _ = run(["score", str(p), "m", "--items", str(b), "--rubric", "v2"]); self.assertEqual(rc, 0); self.assertEqual(json.loads(out)["per_type"]["T2"], 1.0)   # a different file is really read
            rc, _, err = run(["score", str(p), "m", "--items", str(d / "missing.jsonl")]); self.assertEqual(rc, 2)
            rc, _, err = run(["score", str(p), "m", "--items", str(a), "--expect-items-sha256", "0" * 64]); self.assertEqual(rc, 3); self.assertIn("identity mismatch", err)
            (d / "meta.json").write_text(json.dumps({"item_set_hash": B.items_identity(a)["item_set_hash"]})); rc, out, _ = run(["score", str(p), "m", "--items", str(a)]); self.assertEqual(rc, 0)   # canonical set hash (the generator's)
            (d / "meta.json").write_text(json.dumps({"item_set_hash": "f" * 64})); rc, _, err = run(["score", str(p), "m", "--items", str(a)]); self.assertEqual(rc, 3); self.assertIn("item_set_hash", err)
            self.assertEqual(B.item_set_hash([json.loads(l) for l in (REPO / "docs" / "evidencebench" / "items.jsonl").read_text().splitlines() if l.strip()]), json.loads((REPO / "docs" / "evidencebench" / "meta.json").read_text())["item_set_hash"])   # reproduces the published identity


class ExcerptQuality(unittest.TestCase):
    def test_rules_finalizer_and_gate(self):
        self.assertIn("entity_fragment_end", Q.assess("On March 23, 2026, the Company entered into the &"))
        self.assertIn("xbrl_context", Q.assess("StockMember 2026-03-31 0000001800 us-gaap:CommonStockMember 2025-03-31"))
        self.assertFalse(Q.is_event_bearing("StockMember 2026-03-31 0000001800 us-gaap:CommonStockMember 2025-03-31"))
        self.assertTrue(Q.is_event_bearing("On March 23, 2026, Hewlett Packard Enterprise Company priced a public offering of notes."))
        self.assertEqual(Q.finalize_display("Sales of R&amp;D services rose; the Company entered into the &"), "Sales of R&D services rose;")
        self.assertEqual(Q.finalize_display("plain sentence."), "plain sentence.")
        self.assertEqual(Q.strip_ix_data_blocks("<p>prose</p><ix:hidden><xbrli:context id='c'>us-gaap:X</xbrli:context></ix:hidden><p>more</p>"), "<p>prose</p> <p>more</p>")   # unwired forward repair callable
        os.environ.pop(Q.GATE_ENV, None); self.assertEqual(Q.gate("us-gaap:CommonStockMember 2025-03-31"), (True, None))          # OFF by default: no runtime effect
        os.environ[Q.GATE_ENV] = "reject"
        try:
            ok, why = Q.gate("us-gaap:CommonStockMember 2025-03-31"); self.assertFalse(ok); self.assertTrue(why.startswith("R9_excerpt_quality"))
            self.assertEqual(Q.gate("On March 23, 2026, the Company priced notes.")[0], True)
        finally:
            os.environ.pop(Q.GATE_ENV, None)


class SiteCorrections(unittest.TestCase):
    def test_freshness_formatter_is_per_artifact(self):
        gen = datetime(2026, 9, 15, 2, 0, tzinfo=timezone.utc)                                  # Tuesday 02:00 UTC → last completed session = Mon 2026-09-14
        self.assertEqual(UB.freshness_strip("2026-09-14", gen), "Data through 2026-09-14 (last completed U.S. trading day); generated at 2026-09-15 02:00 UTC.")
        self.assertEqual(UB.freshness_strip("2026-09-11", gen), "Data through 2026-09-11; generated at 2026-09-15 02:00 UTC.")                 # old data built today is never called current
        self.assertEqual(UB.freshness_strip("2026-09-11", datetime(2026, 9, 12, 3, 0, tzinfo=timezone.utc)), "Data through 2026-09-11 (last completed U.S. trading day); generated at 2026-09-12 03:00 UTC.")
        import check_site_walk as SW, check_header_layout as HL
        stamp = UB.freshness_strip("2026-09-14", gen); self.assertEqual(len(SW.RE_STRIP_PHRASE.findall(stamp)), 1); self.assertEqual(len(HL.RE_STRIP_PHRASE.findall(stamp)), 1)
        self.assertEqual(len(SW.RE_RAW_TS.findall(SW.RE_STRIP_PHRASE.sub(" ", stamp))), 0)
    def test_table_wrapper_and_placeholder_and_claims(self):
        html = "<p>a</p><table><tr><td>1</td></tr></table><table><tr><td>2</td></tr></table>"
        w = UB.wrap_tables(html); self.assertEqual(w.count('class="table-wrap"'), 2); self.assertEqual(UB.wrap_tables(w), w)      # idempotent
        self.assertIn('tabindex="0"', w); self.assertIn("overflow-x:auto", UB.TABLE_WRAP_CSS)
        import check_site_walk as SW
        self.assertTrue(SW.RE_PLACEHOLDER.search("x — [CONTACT CHANNEL PLACEHOLDER — published after] y")); self.assertIsNone(SW.RE_PLACEHOLDER.search("No other contact channel is published"))
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "c.json"; f.write_text(json.dumps({"former_name": "YUCLAW Ground Truth API", "description": "Ground Truth JSON"}))
            probs = CL.lint_claims(f); self.assertEqual(len(probs), 1); self.assertIn("description", probs[0])                  # compat key excluded, descriptive copy flagged


if __name__ == "__main__":
    unittest.main(verbosity=2)
