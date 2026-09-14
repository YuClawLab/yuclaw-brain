"""Journey tests (v7 Block B): check → reproduce → challenge → document use, through the REAL entry
points (CLI mains and shared modules). Synthetic fixtures; the only 'real' inputs are the public
frozen artifacts already on disk in this checkout (read-only). No DB, no network."""
import contextlib, hashlib, io, json, os, pathlib, sys, tempfile, unittest
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from v3.cli import packet as packet_cli, challenge as challenge_cli, decision as decision_cli, receipts as receipts_cli, check_claim  # noqa: E402
from v3.receipts import packet, scoreboard  # noqa: E402
from v3.receipts.challenge import ChallengeStore  # noqa: E402
from v3.receipts.contracts import ContractError  # noqa: E402


def run(main, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


class CheckClaim(unittest.TestCase):
    def test_support_limits_present_and_no_prediction(self):
        for status, claim in (("UNSUPPORTED", {"ticker": "AAPL", "type": None, "accession": None, "date_range": None}),
                              ("NOT_PARSEABLE", {}), ("NOT_IN_COVERAGE", {"ticker": "ZZZZ"}), ("SOURCE_MATCHED", {"ticker": "AAPL", "date_range": ("2026-01-01", "2026-02-01")})):
            lim = check_claim.support_limits(status, claim, [], [])
            self.assertEqual(lim["research_interpretation"], "NONE")
            self.assertIn(lim["source_match"], ("EXACT", "PARTIAL", "NONE", "NOT_EVALUATED"))
            # no directional/financial language in any field except the explicit disclaimer note
            s = json.dumps({k: v for k, v in lim.items() if k != "research_interpretation_note"}).lower()
            for w in ("buy", "sell", "alpha", "return", "predict", "outperform"): self.assertNotIn(w, s)
            self.assertIn("never states a truth verdict", lim["research_interpretation_note"])
        self.assertIn("coverage statement", check_claim.support_limits("UNSUPPORTED", {"ticker": "AAPL"}, [], [])["unsupported_conclusion"])
        self.assertEqual(check_claim.support_limits("SOURCE_MATCHED", {"ticker": "AAPL", "date_range": ("2026-01-01", "2026-02-01")}, [{}], [])["temporal_eligibility"], "EVALUATED")
        self.assertEqual(check_claim.support_limits("NOT_PARSEABLE", {}, [], [])["replay_status"], "NOT_APPLICABLE")
    def test_passport_document_carries_limits_for_unparseable_and_coverage_paths(self):
        d = check_claim.passport("nonsense", None, None); self.assertEqual(d["status"], "NOT_PARSEABLE"); self.assertIn("support_limits", d)
        d2 = check_claim.passport('{"ticker":"ZZZZ"}', {"ticker": "ZZZZ", "type": None, "accession": None, "date_range": None}, False)
        self.assertEqual(d2["status"], "NOT_IN_COVERAGE"); self.assertEqual(d2["support_limits"]["source_match"], "NOT_EVALUATED")


class Reproduce(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.dir = pathlib.Path(self.tmp.name) / "pk"
    def tearDown(self): self.tmp.cleanup()
    def test_build_verify_tamper_and_first_discrepancy(self):
        rc, out, err = run(packet_cli.main, ["build", str(self.dir)]); self.assertEqual(rc, 0, err)
        man = json.loads((self.dir / packet.MANIFEST).read_text()); self.assertTrue(any(f["path"] == "docs/replay/lab_replay_bundle.json" and f["status"] == "INCLUDED" for f in man["files"]))
        self.assertTrue((self.dir / packet.INSTRUCTIONS).exists()); self.assertNotIn("internal/", json.dumps(man))
        rc, out, err = run(packet_cli.main, ["verify", str(self.dir), "--json"]); res = json.loads(out)
        self.assertEqual(rc, 0, out); self.assertEqual(res["result"], "SUCCESS"); self.assertEqual(res["replay"]["exit"], 0); self.assertIn("not an outsider receipt", res["meaning"])
        # tamper one byte of an artifact → fails BEFORE replay
        art = self.dir / "artifacts" / "docs/capabilities.json"; b = bytearray(art.read_bytes()); b[0] ^= 1; art.write_bytes(bytes(b))
        rc, out, err = run(packet_cli.main, ["verify", str(self.dir), "--json"]); res = json.loads(out)
        self.assertEqual(rc, 1); self.assertEqual(res["result"], "MISMATCH"); self.assertIn("byte mismatch at docs/capabilities.json", res["first_discrepancy"]); self.assertEqual(res["replay"], "NOT RUN (integrity failed first)")
        rc, out, err = run(packet_cli.main, ["verify", str(self.dir / "nope"), "--json"]); self.assertEqual(rc, 3)


class Challenge(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory(); self.store = str(pathlib.Path(self.tmp.name) / "s")
    def tearDown(self): self.tmp.cleanup()
    def test_adverse_findings_survive_and_resolution_needs_revised_artifact(self):
        from v3.receipts.store import Store
        h = hashlib.sha256(b"SYNTHETIC artifact").hexdigest()
        rc, out, err = run(challenge_cli.main, ["--store", self.store, "--synthetic", "create", "ch-1", "--artifact-type", "wheel", "--sha256", h, "--size-bytes", "18", "--claim-id", "claim-synthetic-1", "--expected", "replay exit 0", "--observed", "replay exit 1 at root day 3", "--criterion", "artifact-reproduction-by-qualified-receipt"])
        self.assertEqual(rc, 0, err)
        cs = ChallengeStore(self.store); Store(self.store).designate_reviewer("rev-syn", "T", designated=False)
        tok = pathlib.Path(self.tmp.name) / "tok"; tok.write_text("T\n"); os.chmod(tok, 0o600)
        with self.assertRaises(ContractError): cs.dispose("ch-1", "RESOLVED", reviewer_role="rev-syn", token="T", revised_artifact={"artifact_type": "wheel", "sha256": h, "size_bytes": 18}, revised_bytes=b"SYNTHETIC artifact", verification_id="c" * 64)   # same bytes cannot resolve
        rc, out, err = run(challenge_cli.main, ["--store", self.store, "--synthetic", "dispose", "ch-1", "CONFIRMED", "--reason", "synthetic confirmation"]); self.assertEqual(rc, 1)   # V3: challenger cannot confirm (no authority)
        rc, out, err = run(challenge_cli.main, ["--store", self.store, "--synthetic", "dispose", "ch-1", "CONFIRMED", "--role", "rev-syn", "--token-file", str(tok), "--reason", "synthetic confirmation"]); self.assertEqual(rc, 0, err)
        revised = pathlib.Path(self.tmp.name) / "revised.bin"; revised.write_bytes(b"SYNTHETIC artifact revised"); h2 = hashlib.sha256(revised.read_bytes()).hexdigest()
        # V4: the resolution test is EXECUTED by the store (receipt method: a qualified successful synthetic receipt binding the revised artifact)
        from v3.receipts import verify as _v
        sp = pathlib.Path(self.tmp.name) / "sub.json"
        sp.write_text(json.dumps({"schema_version": "receipt-1", "attempt_id": "rev-1", "activity_id": "act", "participant_id": "P-R", "group_id": None, "relationship": "UNRELATED", "execution_control": "SELF", "assistance": "NONE",
                                  "incentive_outcome_dependent": False, "outcome": "REPRODUCED", "observed_at": "2026-09-14T01:00:00.000000Z", "artifact_binding": {"artifact_type": "wheel", "sha256": h2, "size_bytes": 26}, "release_identity": None, "environment": {}, "protocol_id": "syn"}))
        rc, out, err = run(receipts_cli.main, ["--store", self.store, "--synthetic", "import", str(sp)]); self.assertEqual(rc, 0, err); dig = json.loads(out)["digest"]
        rc, out, err = run(receipts_cli.main, ["--store", self.store, "--synthetic", "observe", dig, "--path", str(revised), "--allowed-root", self.tmp.name]); self.assertEqual(rc, 0, err)
        rc, out, err = run(receipts_cli.main, ["--store", self.store, "--synthetic", "review", dig, "QUALIFIED", "--role", "rev-syn", "--token-file", str(tok)]); self.assertEqual(rc, 0, err)
        rc, out, err = run(challenge_cli.main, ["--store", self.store, "--synthetic", "verify-revision", "ch-1", "--revised-type", "wheel", "--revised-sha256", h2, "--revised-size-bytes", "26", "--method", "receipt", "--receipt-digest", dig]); self.assertEqual(rc, 0, err); vid = json.loads(out)["verification_id"]
        rc, out, err = run(challenge_cli.main, ["--store", self.store, "--synthetic", "dispose", "ch-1", "RESOLVED", "--role", "rev-syn", "--token-file", str(tok), "--revised-type", "wheel", "--revised-sha256", h2, "--revised-size-bytes", "26", "--verification-id", vid]); self.assertEqual(rc, 1)   # V3: digest alone is not a test
        rc, out, err = run(challenge_cli.main, ["--store", self.store, "--synthetic", "dispose", "ch-1", "RESOLVED", "--role", "rev-syn", "--token-file", str(tok), "--revised-type", "wheel", "--revised-sha256", h2, "--revised-size-bytes", "26", "--revised-path", str(revised), "--allowed-root", self.tmp.name, "--verification-id", vid]); self.assertEqual(rc, 0, err)
        view = cs.public_view(synthetic=True)[0]; self.assertEqual(view["disposition"], "RESOLVED"); self.assertTrue(view["resolution"]["original_finding_retained"]); self.assertEqual(len(cs.history("ch-1")), 3)
        self.assertNotIn("private", json.dumps(view)); self.assertEqual(cs.public_view(synthetic=False), [])

class DocumentUse(unittest.TestCase):
    def test_decision_bound_to_packet_digest_and_export_needs_permission(self):
        with tempfile.TemporaryDirectory() as d:
            st = str(pathlib.Path(d) / "s"); dig = hashlib.sha256(b"SYNTHETIC manifest").hexdigest()
            rc, out, err = run(decision_cli.main, ["--store", st, "--synthetic", "record", "dec-1", "REQUEST_EVIDENCE", "--packet-manifest-digest", dig, "--claim-id", "claim-synthetic-1", "--context", '{"note": "SYNTHETIC private context"}'])
            self.assertEqual(rc, 0, err)
            rc, out, err = run(decision_cli.main, ["--store", st, "--synthetic", "export"]); self.assertEqual(json.loads(out), [])
            rc, out, err = run(decision_cli.main, ["--store", st, "--synthetic", "record", "dec-2", "DISCARD_CLAIM", "--packet-manifest-digest", dig, "--claim-id", "claim-synthetic-1", "--export-permitted"])
            rc, out, err = run(decision_cli.main, ["--store", st, "--synthetic", "export"]); ex = json.loads(out); self.assertEqual(len(ex), 1); self.assertNotIn("context", ex[0]); self.assertTrue(ex[0]["synthetic"])
            rc, out, err = run(decision_cli.main, ["--store", st, "--synthetic", "record", "dec-3", "INVESTIGATE_FURTHER", "--packet-manifest-digest", "abc", "--claim-id", "c"]); self.assertEqual(rc, 1)


class ScoreboardAndParity(unittest.TestCase):
    def test_scoreboard_zero_pending_states_and_history(self):
        with tempfile.TemporaryDirectory() as d:
            board = scoreboard.build(pathlib.Path(d) / "s", synthetic=True, now=datetime(2026, 9, 14, tzinfo=timezone.utc))
            c = board["columns"]; self.assertEqual(c["witnesses"]["state"], "ZERO"); self.assertEqual(c["replications"]["state"], "PENDING_REGISTRATION"); self.assertEqual(c["replications"]["attempts"], 0)
            self.assertNotIn("trust score", json.dumps(board).lower().replace("no composite trust score", ""))
            board2 = scoreboard.build(pathlib.Path(d) / "s", synthetic=True, now=datetime(2026, 9, 15, tzinfo=timezone.utc))
            h = scoreboard.history(board, board2); self.assertEqual(h["movement"]["attempts"]["growth_multiplier"], "UNDEFINED (zero baseline)")
    def test_public_loader_refuses_synthetic_board_and_surfaces_share_it(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "scoreboard.json"; p.write_text(json.dumps(scoreboard.build(pathlib.Path(d) / "s", synthetic=True)))
            self.assertIsNone(scoreboard.load_public(p))
            p.write_text(json.dumps(scoreboard.build(pathlib.Path(d) / "s", synthetic=False))); self.assertIsNotNone(scoreboard.load_public(p))
        # API and MCP read through the same loader (source text check: no separate hard-coded examples)
        for f in ("v3/api/server.py", "v3/mcp/server.py"):
            t = (REPO / f).read_text(); self.assertIn("from v3.receipts.scoreboard import inspect_public", t); self.assertIn('"docs" / "receipts" / "scoreboard.json"', t)
    def test_cli_receipts_end_to_end_synthetic(self):
        with tempfile.TemporaryDirectory() as d:
            st = str(pathlib.Path(d) / "s"); art = pathlib.Path(d) / "wheel.bin"; art.write_bytes(b"SYNTHETIC wheel bytes")
            h = hashlib.sha256(art.read_bytes()).hexdigest()
            sub = {"schema_version": "receipt-1", "attempt_id": "cli-1", "activity_id": "act", "participant_id": "P-CLI", "group_id": "G-CLI", "relationship": "UNRELATED", "execution_control": "SELF", "assistance": "NONE",
                   "incentive_outcome_dependent": False, "outcome": "REPRODUCED", "observed_at": "2026-09-14T01:00:00.000000Z", "artifact_binding": {"artifact_type": "wheel", "sha256": h, "size_bytes": 21},
                   "release_identity": None, "environment": {"os": "SyntheticOS", "python": "3.12"}, "protocol_id": "synthetic", "review": {"state": "QUALIFIED"}}
            sp = pathlib.Path(d) / "sub.json"; sp.write_text(json.dumps(sub))
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "import", str(sp)]); self.assertEqual(rc, 0, err); dig = json.loads(out)["digest"]; self.assertTrue(json.loads(out)["diagnostics"])
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "observe", dig, "--path", str(art), "--allowed-root", d]); self.assertEqual(rc, 0, err); self.assertTrue(json.loads(out)["verified"])
            tok = pathlib.Path(d) / "tok"; tok.write_text("x\n"); os.chmod(tok, 0o600)
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "review", dig, "QUALIFIED", "--role", "nobody", "--token-file", str(tok)]); self.assertEqual(rc, 1)   # unauthorized
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "review", dig, "QUALIFIED", "--role", "nobody", "--token", "x"]); self.assertEqual(rc, 1); self.assertIn("--token-file", err)   # V3: no process-argument token
            from v3.receipts.store import Store; Store(st).designate_reviewer("rev-syn", "T", designated=False); tok.write_text("T\n")
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "review", dig, "QUALIFIED", "--role", "rev-syn", "--token-file", str(tok)]); self.assertEqual(rc, 0, err)
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "counts"]); c = json.loads(out); self.assertEqual((c["attempts"], c["qualified"], c["successful"]), (1, 1, 1))
            rc, out, err = run(receipts_cli.main, ["--store", st, "export"]); self.assertEqual(json.loads(out), [])                # public export excludes synthetic
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "export"]); ex = json.loads(out); self.assertEqual(len(ex), 1); self.assertNotIn("P-CLI", out); self.assertTrue(ex[0]["synthetic"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
