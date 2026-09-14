"""Adversarial tests for the v7 receipt engine (Block A). Synthetic fixtures only; no DB, no network.
Exercises the public library path (store → verify → derive → counts → export) — the same functions the
CLI/API/MCP call — not private helpers."""
import copy, json, os, pathlib, sys, tempfile, unittest
from datetime import datetime, timedelta, timezone

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from v3.receipts.contracts import ContractError, validate_submission, digest  # noqa: E402
from v3.receipts.store import Store, ReviewAuthorityError  # noqa: E402
from v3.receipts import verify, counting, export, legacy  # noqa: E402

WHEEL = b"SYNTHETIC wheel bytes v7 A\n"; SDIST = b"SYNTHETIC sdist bytes v7 A\n"; WHEEL_B = b"SYNTHETIC wheel bytes v7 B (rebuilt)\n"
T0 = datetime(2026, 9, 14, 12, 0, 0, 123456, tzinfo=timezone.utc)


def bind(t, b): h, n = verify.sha256_len(b); return {"artifact_type": t, "sha256": h, "size_bytes": n}


def sub(aid, pid="P-A", grp="G-A", rel="UNRELATED", ctrl="SELF", assist="NONE", outcome="REPRODUCED", binding=None, act="act-1", obs=T0, incentive=False, **extra):
    d = {"schema_version": "receipt-1", "attempt_id": aid, "activity_id": act, "participant_id": pid, "group_id": grp, "relationship": rel,
         "execution_control": ctrl, "assistance": assist, "incentive_outcome_dependent": incentive, "outcome": outcome,
         "observed_at": obs.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "artifact_binding": binding or bind("wheel", WHEEL),
         "release_identity": {"tag": "v7.0.0-synthetic", "source_sha": "5" * 40}, "environment": {"os": "SyntheticOS 1", "python": "3.12-syn"},
         "protocol_id": "synthetic-receipts-2026", "limitations": ["synthetic fixture"], "private": {"contact": "SYNTHETIC-SECRET"}}
    d.update(extra); return d


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.store = Store(pathlib.Path(self.tmp.name) / "store")
        self.store.designate_reviewer("reviewer-synthetic", "TOKEN-SYN", designated=False)
    def tearDown(self): self.tmp.cleanup()
    def imp(self, raw, synthetic=True): return self.store.import_submission(raw, synthetic=synthetic, received_at=T0)
    def observe(self, rec, data): self.store.add_observation(rec["digest"], verify.observe(rec["submission"]["artifact_binding"], data=data, now=T0))
    def review(self, rec, state="QUALIFIED", role="reviewer-synthetic", token="TOKEN-SYN"):
        return self.store.add_review(rec["digest"], state, reviewer_role=role, token=token, now=T0)
    def derived(self, synthetic=True): return counting.derive(self.store, synthetic=synthetic)
    def full(self, raw, data=WHEEL, state="QUALIFIED"):
        rec = self.imp(raw); self.observe(rec, data); self.review(rec, state); return rec


class TrustBoundaries(Base):
    def test_submission_cannot_self_qualify_or_assert_verification(self):
        raw = sub("a1", review={"state": "QUALIFIED"}, binding_completeness="FULL", qualified=True, verified=True, reviewer_authority="DESIGNATED", relationship_approved=True)
        rec = self.imp(raw)
        self.assertTrue(any("ignored forgeable field 'review'" in d for d in rec["diagnostics"]))
        row = self.derived()[0]
        self.assertFalse(row["qualified"]); self.assertEqual(row["binding_completeness"], "NONE"); self.assertIn("review state RECEIVED", row["reasons"])
    def test_review_requires_authorized_role_and_binds_to_digest(self):
        rec = self.imp(sub("a1")); self.observe(rec, WHEEL)
        with self.assertRaises(ReviewAuthorityError): self.review(rec, role="participant", token="anything")
        with self.assertRaises(ReviewAuthorityError): self.review(rec, token="WRONG")
        self.review(rec); self.assertTrue(self.derived()[0]["qualified"])
        # altered receipt after approval → new version, review binding invalid
        corr = sub("a1", outcome="FAILED", supersedes={"digest": rec["digest"], "reason": "synthetic correction"})
        rec2 = self.imp(corr); self.assertEqual(rec2["version"], 2); self.observe(rec2, WHEEL)
        row = self.derived()[0]; self.assertFalse(row["qualified"]); self.assertIn("review state RECEIVED", row["reasons"]); self.assertEqual(len(self.store.history("a1")), 2)
    def test_real_qualification_pending_without_designated_authority(self):
        rec = self.imp(sub("r1"), synthetic=False); self.observe(rec, WHEEL); self.review(rec)
        row = self.derived(synthetic=False)[0]
        self.assertFalse(row["qualified"]); self.assertIn("review authority not designated (real qualification pending)", row["reasons"])
        self.store.designate_reviewer("reviewer-designated", "TOKEN-D", designated=True)
        self.store.add_review(rec["digest"], "QUALIFIED", reviewer_role="reviewer-designated", token="TOKEN-D", now=T0)
        self.assertTrue(self.derived(synthetic=False)[0]["qualified"])
    def test_exact_bytes_wheel_vs_sdist_vs_rebuilt_and_absent(self):
        rec = self.imp(sub("w1")); self.observe(rec, SDIST); self.review(rec)                    # wrong artifact bytes
        self.assertEqual(self.derived()[0]["binding_completeness"], "UNVERIFIED"); self.assertFalse(self.derived()[0]["qualified"])
        rec2 = self.imp(sub("w2")); self.observe(rec2, WHEEL_B); self.review(rec2)                # rebuilt final ≠ RC
        self.assertFalse([r for r in self.derived() if r["attempt_id"] == "w2"][0]["qualified"])
        rec3 = self.imp(sub("w3")); self.store.add_observation(rec3["digest"], verify.observe(rec3["submission"]["artifact_binding"], now=T0)); self.review(rec3)
        r3 = [r for r in self.derived() if r["attempt_id"] == "w3"][0]; self.assertEqual(r3["observation"]["source"], "unavailable"); self.assertFalse(r3["qualified"])
        obs = verify.observe(bind("wheel", WHEEL), data=WHEEL, now=T0); tam = dict(obs, observed_size_bytes=obs["observed_size_bytes"] + 1)
        self.assertFalse(verify.same_artifact(obs, tam))
        with self.assertRaises(ContractError): verify.observe(bind("wheel", WHEEL), path="/etc/hostname", allowed_roots=[self.tmp.name])
    def test_duplicates_and_conflicts(self):
        a = self.imp(sub("d1")); b = self.imp(sub("d1")); self.assertTrue(b.get("duplicate")); self.assertEqual(len(self.store.history("d1")), 1)
        with self.assertRaises(ContractError): self.imp(sub("d1", outcome="FAILED"))            # conflicting content without supersedes
        with self.assertRaises(ContractError): self.imp(sub("d1", outcome="FAILED", supersedes={"digest": "0" * 64, "reason": "x"}))
    def test_relationship_control_incentive_rules(self):
        cases = {"o": sub("o", rel="OWNER-AFFILIATED"), "u": sub("u", rel="UNKNOWN"), "op": sub("op", ctrl="OPERATOR-RUN", assist="LIVE-HELP"),
                 "inc": sub("inc", incentive=True), "rd": sub("rd", rel="RELATED-DISCLOSED", ctrl="ASSISTED", assist="PUBLIC-DOCS-ONLY")}
        for raw in cases.values(): self.full(raw)
        q = {r["attempt_id"]: r["qualified"] for r in self.derived()}
        self.assertEqual(q, {"o": False, "u": False, "op": False, "inc": False, "rd": True})
        with self.assertRaises(ContractError): validate_submission(sub("x", ctrl="ASSISTED", assist="NONE"))


class TypedExport(Base):
    def test_nested_injection_and_free_text_rejected(self):
        with self.assertRaises(ContractError): validate_submission(sub("e1", environment={"os": {"private_contact": "SYNTHETIC-SECRET"}}))
        with self.assertRaises(ContractError): validate_submission(sub("e2", environment={"os": "x", "hostname": "SYNTHETIC-HOST"}))
        with self.assertRaises(ContractError): validate_submission(sub("e3", notes="free text"))
        with self.assertRaises(ContractError): validate_submission(sub("e4", artifact_binding={"artifact_type": "wheel", "sha256": "0" * 64, "size_bytes": True}))
        with self.assertRaises(ContractError): validate_submission(sub("e5", artifact_binding={"artifact_type": "wheel", "sha256": "0" * 64, "size_bytes": float("nan")}))
    def test_projection_is_typed_and_leaks_nothing(self):
        rec = self.full(sub("p1", public_note="SYNTHETIC public note ok", disclosure_permitted=True))
        pub = export.project(self.derived()[0], self.store, mode="synthetic")
        self.assertTrue(pub["synthetic"]); self.assertTrue(set(pub) <= set(export.PUBLIC_SHAPE))
        s = json.dumps(pub); self.assertNotIn("SYNTHETIC-SECRET", s); self.assertNotIn("P-A", s); self.assertNotIn("G-A", s); self.assertNotIn("limitations", s)
        self.assertTrue(pub["participant"].startswith("p-")); self.assertEqual(pub["review_authority"], "SYNTHETIC")
        rec2 = self.full(sub("p2", public_note="SYNTHETIC note", disclosure_permitted=False))
        pub2 = export.project([r for r in self.derived() if r["attempt_id"] == "p2"][0], self.store, mode="synthetic"); self.assertNotIn("public_note", pub2)
    def test_denylisted_permitted_string_is_not_published(self):
        ok, why = export.text_publishable("a validated mathematical verification proof")   # language rail forbidden words
        self.assertFalse(ok)
    def test_synthetic_never_enters_public_export_and_provenance_is_import_bound(self):
        rec = self.full(sub("s1", synthetic=False))                        # participant says 'not synthetic' → ignored; import said synthetic
        row = self.derived()[0]; self.assertTrue(row["synthetic"])
        with self.assertRaises(ContractError): export.project(row, self.store, mode="public")
        real = self.store.import_submission(sub("s2"), synthetic=False, received_at=T0)   # body carries no marker; provenance real
        rrow = self.derived(synthetic=False)[0]
        with self.assertRaises(ContractError): export.project(rrow, self.store, mode="synthetic")
        self.assertFalse(export.project(rrow, self.store, mode="public")["synthetic"])
    def test_public_shape_rejects_unregistered_values_even_if_smuggled(self):
        row = self.derived() if self.derived() else None
        with self.assertRaises(ContractError): export.PUBLIC_SHAPE["relationship"]("FRIEND", "relationship")
        with self.assertRaises(ContractError): export.PUBLIC_SHAPE["environment"]({"os": {"x": 1}}, "environment")
        with self.assertRaises(ContractError): export.PUBLIC_SHAPE["artifact_binding"]({"artifact_type": "wheel", "sha256": "abc", "size_bytes": 1}, "b")


class Counting(Base):
    def test_primary_qualified_vs_successful_3_3_vs_1_1(self):
        self.full(sub("A1", "P-A", "G-A", outcome="REPRODUCED")); self.full(sub("B1", "P-B", "G-B", outcome="FAILED")); self.full(sub("C1", "P-C", "G-C", outcome="INCONCLUSIVE"))
        self.full(sub("A2", "P-A", "G-A", binding=bind("sdist", SDIST), act="act-2"), data=SDIST)        # repeat on another artifact
        self.full(sub("D1", "P-D", "G-D"), state="HELD"); self.full(sub("E1", "P-E", "G-E", incentive=True))
        c = counting.counts(self.derived())
        self.assertEqual((c["attempts"], c["qualified"], c["successful"]), (6, 4, 2))
        w = c["windows"]["unwindowed"]; self.assertEqual((w["primary_distinct_persons"], w["primary_distinct_groups"]), (3, 3)); self.assertEqual((w["successful_distinct_persons"], w["successful_distinct_groups"]), (1, 1))
        self.assertEqual(c["registration"]["status"], "PENDING"); self.assertEqual(c["artifacts"]["successful_cohort_artifacts"], 2); self.assertEqual(c["artifacts"]["package_reproductions_successful"], 2)
        self.assertEqual(c["visible"]["qualified_failed"], 1); self.assertEqual(c["visible"]["qualified_inconclusive"], 1)
        from v3.receipts.contracts import POLICY_VERSION
        reg = {"protocol_id": "synthetic-receipts-2026", "anchor": "2026-09-01", "registered_at": "2026-09-01T00:00:00.000000Z", "policy_version": POLICY_VERSION}
        c2 = counting.counts(self.derived(), registration=reg)
        self.assertIn("synthetic-receipts-2026/w0", c2["windows"]); self.assertEqual(c2["registration"]["status"], "REGISTERED")
        with self.assertRaises(ContractError): counting.counts(self.derived(), registration={"protocol_id": "x", "anchor": "2026-12-01"})   # anchor alone is not adoption (V3)
        c3 = counting.counts(self.derived(), registration=dict(reg, protocol_id="x", anchor="2026-12-01", registered_at="2026-12-01T00:00:00.000000Z"))
        self.assertNotIn("x/w0", c3["windows"]); self.assertEqual(c3["excluded_from_primary"]["other_protocols"], {"synthetic-receipts-2026": 4})   # never reassigned (V3)
    def test_site_check_is_not_package_reproduction_and_movement_undefined_on_zero(self):
        self.full(sub("s1", binding=bind("site-page", b"<html>synthetic</html>")), data=b"<html>synthetic</html>")
        c = counting.counts(self.derived()); self.assertEqual(c["artifacts"]["package_reproductions_successful"], 0); self.assertEqual(c["successful"], 1)
        m = counting.movement(None, c); self.assertEqual(m["successful"]["growth_multiplier"], "UNDEFINED (zero baseline)"); self.assertEqual(m["successful"]["delta"], 1)
    def test_legacy_adapter_prefix_only(self):
        log = json.loads((REPO / "docs/replication/replication_log.json").read_text())
        rows = legacy.adapt_log(log); self.assertEqual(len(rows), len(log["replications"]))
        self.assertEqual(rows[0]["binding_completeness"], "PREFIX_ONLY"); self.assertTrue(rows[0]["program_evidence"]); self.assertFalse(rows[0]["exact_release_evidence"])
        self.assertEqual(len(rows[0]["legacy_prefix"]), 16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
