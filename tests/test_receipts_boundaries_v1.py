"""V7-004-V1 boundary tests: the smallest discriminating fixtures missing from V7-004 coverage.
Public entry points only; synthetic; no DB, no network."""
import contextlib, hashlib, io, json, pathlib, sys, tempfile, unittest
from datetime import datetime, timezone
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.receipts import contracts, counting, export, legacy, verify  # noqa: E402
from v3.receipts.store import Store, ReviewAuthorityError  # noqa: E402
from v3.receipts.contracts import ContractError  # noqa: E402
from v3.cli import packet as packet_cli, receipts as receipts_cli, challenge as challenge_cli, decision as decision_cli  # noqa: E402

T0 = datetime(2026, 9, 14, 12, 0, 0, 1, tzinfo=timezone.utc); WHEEL = b"SYNTHETIC wheel v1\n"


def run(main, argv):
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = main(argv)
    except SystemExit as e:
        rc = e.code
    return rc, out.getvalue(), err.getvalue()


def sub(aid, **extra):
    h, n = verify.sha256_len(WHEEL)
    d = {"schema_version": "receipt-1", "attempt_id": aid, "activity_id": "act", "participant_id": "P-V1", "group_id": "G-V1", "relationship": "UNRELATED",
         "execution_control": "SELF", "assistance": "NONE", "incentive_outcome_dependent": False, "outcome": "REPRODUCED", "observed_at": T0.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
         "artifact_binding": {"artifact_type": "wheel", "sha256": h, "size_bytes": n}, "release_identity": None, "environment": {"os": "SynOS", "python": "3.12"}, "protocol_id": "syn"}
    d.update(extra); return d


class TrustedReviewStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.st = Store(pathlib.Path(self.tmp.name) / "s"); self.st.designate_reviewer("rev", "T", designated=False)
    def tearDown(self): self.tmp.cleanup()
    def test_reviewer_shaped_json_in_submission_never_reaches_the_review_store(self):
        rec = self.st.import_submission(sub("r1", reviewer={"role": "rev", "token": "T", "state": "QUALIFIED"}, review={"state": "QUALIFIED", "reviewer_role": "rev", "authority": "DESIGNATED"}), synthetic=True, received_at=T0)
        self.assertIsNone(self.st.review_for(rec["digest"])); self.assertFalse((self.st.root / "reviews.jsonl").exists())
        self.assertTrue(any("'reviewer'" in d or "'review'" in d for d in rec["diagnostics"]))
    def test_review_binds_receipt_and_policy_version(self):
        rec = self.st.import_submission(sub("r2"), synthetic=True, received_at=T0); self.st.add_observation(rec["digest"], verify.observe(rec["submission"]["artifact_binding"], data=WHEEL, now=T0))
        self.st.add_review(rec["digest"], "QUALIFIED", reviewer_role="rev", token="T", now=T0)
        self.assertTrue(counting.derive(self.st, synthetic=True)[0]["qualified"])
        orig = contracts.POLICY_VERSION; counting.POLICY_VERSION = "receipt-policy-other"           # policy changed → review no longer applies
        try:
            row = counting.derive(self.st, synthetic=True)[0]; self.assertFalse(row["qualified"]); self.assertIn("review under a different policy version", row["reasons"])
        finally:
            counting.POLICY_VERSION = orig
        with self.assertRaises(ContractError): self.st.add_review("0" * 64, "QUALIFIED", reviewer_role="rev", token="T")   # must bind an existing receipt
    def test_legacy_prefix_and_caller_promotion_are_impossible(self):
        with self.assertRaises(ContractError): contracts.validate_binding_claim({"artifact_type": "bundle", "sha256": "f431f9c629ac38b5", "size_bytes": 10})
        with self.assertRaises(ContractError): contracts.validate_binding_claim({"artifact_type": "bundle", "sha256": "f431f9c629ac38b5" + "0" * 48, "size_bytes": None})
        leg = legacy.adapt_entry({"date": "2026-09-04", "operator_affiliation": "AFFILIATED", "bundle": "x sha256 f431f9c629ac38b5… (built)", "replication_result": "REPRODUCED"}, 0)
        self.assertEqual(leg["binding_completeness"], "PREFIX_ONLY"); self.assertIsNone(leg.get("artifact_binding"))
        # a caller cannot mark FULL: binding_completeness is derived from an observation with verified=True only
        rec = self.st.import_submission(sub("r3", binding_completeness="FULL"), synthetic=True, received_at=T0)
        self.assertEqual(counting.derive(self.st, synthetic=True)[-1]["binding_completeness"], "NONE")
        self.st.add_observation(rec["digest"], verify.observe(rec["submission"]["artifact_binding"], data=b"other bytes", now=T0))
        self.assertEqual([r for r in counting.derive(self.st, synthetic=True) if r["attempt_id"] == "r3"][0]["binding_completeness"], "UNVERIFIED")
    def test_synthetic_provenance_cannot_be_flipped_by_correction(self):
        rec = self.st.import_submission(sub("r4"), synthetic=True, received_at=T0)
        with self.assertRaises(ContractError):
            self.st.import_submission(sub("r4", outcome="FAILED", supersedes={"digest": rec["digest"], "reason": "flip"}), synthetic=False, received_at=T0)


class ExitCodeContract(unittest.TestCase):
    def test_packet_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            rc, out, err = run(packet_cli.main, ["verify", d]); self.assertEqual(rc, 3)                                  # unsupported (no manifest)
            rc, out, err = run(packet_cli.main, ["build", str(pathlib.Path(d) / "p"), "--source", d]); self.assertEqual(rc, 3)   # no checkout → unsupported environment
            rc, out, err = run(packet_cli.main, ["bogus"]); self.assertEqual(rc, 2)                                    # usage
            rc, out, err = run(packet_cli.main, ["build", str(pathlib.Path(d) / "p"), "--source", str(REPO)]); self.assertEqual(rc, 0)
            man = json.loads((pathlib.Path(d) / "p" / "PACKET_MANIFEST.json").read_text())
            man["files"][0]["size_bytes"] += 1; (pathlib.Path(d) / "p" / "PACKET_MANIFEST.json").write_text(json.dumps(man))      # wrong size in manifest
            rc, out, err = run(packet_cli.main, ["verify", str(pathlib.Path(d) / "p"), "--json"]); self.assertEqual(rc, 1); self.assertIn("byte mismatch", json.loads(out)["first_discrepancy"])
            man["files"][0]["size_bytes"] -= 1; man["files"][1]["path"] = "docs/absent.json"; (pathlib.Path(d) / "p" / "PACKET_MANIFEST.json").write_text(json.dumps(man))
            rc, out, err = run(packet_cli.main, ["verify", str(pathlib.Path(d) / "p"), "--json"]); self.assertEqual(rc, 1); self.assertIn("missing artifact", json.loads(out)["first_discrepancy"])
            man["files"][1]["path"] = "docs/packets/manifest.json"; man["files"][0]["path"] = "docs/renamed.json"; (pathlib.Path(d) / "p" / "PACKET_MANIFEST.json").write_text(json.dumps(man))
            rc, out, err = run(packet_cli.main, ["verify", str(pathlib.Path(d) / "p"), "--json"]); self.assertEqual(rc, 3); self.assertIn("replay_target", json.loads(out)["first_discrepancy"])   # V3: the target must be a listed INCLUDED entry
    def test_receipts_challenge_decision_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            st = str(pathlib.Path(d) / "s"); bad = pathlib.Path(d) / "bad.json"; bad.write_text(json.dumps({"schema_version": "receipt-9"}))
            rc, out, err = run(receipts_cli.main, ["--store", st, "--synthetic", "import", str(bad)]); self.assertEqual(rc, 1); self.assertIn("REJECTED", err)
            rc, out, err = run(receipts_cli.main, ["--store", st]); self.assertEqual(rc, 2)
            rc, out, err = run(challenge_cli.main, ["--store", st, "--synthetic", "dispose", "nope", "RESOLVED"]); self.assertEqual(rc, 1)
            h = hashlib.sha256(b"x").hexdigest()
            rc, out, err = run(challenge_cli.main, ["--store", st, "--synthetic", "create", "c1", "--artifact-type", "wheel", "--sha256", h, "--size-bytes", "1", "--claim-id", "k", "--expected", "a", "--observed", "b"]); self.assertEqual(rc, 0)
            rc, out, err = run(challenge_cli.main, ["--store", st, "--synthetic", "dispose", "c1", "RESOLVED"]); self.assertEqual(rc, 1)                 # supplied 'resolved' without tested revision
            rc, out, err = run(challenge_cli.main, ["--store", st, "--synthetic", "dispose", "c1", "RESOLVED", "--revised-type", "wheel", "--revised-sha256", h, "--revised-size-bytes", "1", "--verification", "v"]); self.assertEqual(rc, 1)   # same bytes
            rc, out, err = run(decision_cli.main, ["--store", st, "--synthetic", "record", "d1", "DISCARD_CLAIM", "--packet-manifest-digest", "short", "--claim-id", "k"]); self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
