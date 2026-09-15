"""V8-002 §4: append-only version/history storage — chain integrity, operation identifiers and retries, torn-tail
recovery without duplicate durable events, three time axes and as-of visibility."""
import json, pathlib, tempfile, unittest

from v3.receipts.contracts import ContractError
from v8.workbench import calc, schema, store

D = pathlib.Path(__file__).resolve().parent / "fixtures" / "v8" / "commitments"


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-store-")); self.ws = store.Workspace(self.tmp / "ws")
        self.rec = schema.from_fixture(json.loads((D / "001_base.json").read_text())); self.cid = self.rec["claim"]["claim_id"]

    def _populate(self):
        r = self.rec["revisions"][0]
        self.ws.freeze_claim(self.rec["claim"], op_id="op:freeze-0001")
        self.ws.amend_claim(self.cid, "REVISED", changes={"range": r["claim"]["range"]}, reason="revised", source=r["source"], notes={"explanation_unresolved": "n/a", "next_evidence": "10-K"}, op_id="op:amend-0001")
        self.ws.record_outcome(self.cid, self.rec["outcome"], op_id="op:outcome-01")

    def test_public_tree_refused(self):
        repo = pathlib.Path(__file__).resolve().parents[1]
        with self.assertRaises(ContractError):
            store.Workspace(repo / "docs" / "should-never-exist")

    def test_retry_same_op_id_never_duplicates_and_conflicts_are_refused(self):
        ev, d = self.ws.freeze_claim(self.rec["claim"], op_id="op:freeze-0001"); ev2, d2 = self.ws.freeze_claim(self.rec["claim"], op_id="op:freeze-0001")
        self.assertFalse(d); self.assertTrue(d2); self.assertEqual(ev["event_hash"], ev2["event_hash"]); self.assertEqual(len(self.ws.load()["events"]), 1)
        with self.assertRaises(ContractError):
            self.ws.freeze_claim(self.rec["claim"], op_id="op:freeze-0002")          # a second freeze is an amendment, never a duplicate claim
        other = schema.from_fixture(json.loads((D / "008_quarterly.json").read_text()))["claim"]
        with self.assertRaises(store.StoreIntegrityError) as cm:
            self.ws.freeze_claim(other, op_id="op:freeze-0001")                      # same op id, different content
        self.assertEqual(cm.exception.code, "E_OP_CONFLICT")

    def test_history_is_append_only_and_chain_checked(self):
        self._populate(); st = self.ws.claim_state(self.cid)
        self.assertEqual([v["version_id"] for v in st["versions"]], ["V1", "R1"]); self.assertEqual(st["versions"][0]["claim"]["range"]["low"], 110000000)
        self.assertEqual(st["versions"][1]["supersedes"], st["versions"][0]["claim"]["_digest"])
        lines = self.ws.log.read_bytes().split(b"\n"); lines[0] = lines[0].replace(b"110000000", b"111000000"); self.ws.log.write_bytes(b"\n".join(lines))
        with self.assertRaises(store.StoreIntegrityError) as cm:
            self.ws.load()
        self.assertEqual(cm.exception.code, "E_HASH"); self.assertEqual(self.ws.status()["integrity"], "E_HASH")

    def test_deleting_or_reordering_a_line_breaks_the_chain(self):
        self._populate(); lines = self.ws.log.read_bytes().split(b"\n")
        self.ws.log.write_bytes(b"\n".join([lines[0]] + lines[2:]))
        self.assertEqual(self.ws.status()["integrity"], "E_CHAIN")

    def test_torn_tail_recovery_and_retry_produce_exactly_one_durable_event(self):
        self._populate(); n0 = len(self.ws.load()["events"])
        with open(self.ws.log, "ab") as f:
            f.write(b'{"seq": 4, "kind": "ADJUDICATION_RECORDED", "claim_id": "x"')      # interrupted append: no newline
        self.assertEqual(self.ws.status()["integrity"], "TORN_TAIL")
        with self.assertRaises(store.StoreIntegrityError) as cm:
            self.ws.record_outcome(self.cid, self.rec["outcome"], op_id="op:outcome-02")
        self.assertEqual(cm.exception.code, "E_TORN_TAIL")
        r = self.ws.recover(); self.assertTrue(r["recovered"]); self.assertEqual(r["event"]["kind"], "RECOVERY")
        side = [p for p in self.ws.root.iterdir() if ".torn." in p.name]; self.assertEqual(len(side), 1); self.assertIn(b'"seq": 4', side[0].read_bytes())
        events = self.ws.load()["events"]; self.assertEqual(len(events), n0 + 1); self.assertEqual(events[n0]["payload"]["torn_bytes"], r["torn"]["bytes"])
        ev, d = self.ws.record_outcome(self.cid, self.rec["outcome"], op_id="op:outcome-02"); ev2, d2 = self.ws.record_outcome(self.cid, self.rec["outcome"], op_id="op:outcome-02")
        self.assertFalse(d); self.assertTrue(d2); self.assertEqual(len(self.ws.load()["events"]), n0 + 2); self.assertEqual(ev["payload"]["supersedes"], ev2["payload"]["supersedes"])
        self.assertEqual(self.ws.recover(), {"recovered": False, "reason": "no torn tail"})

    def test_three_times_and_as_of_visibility(self):
        self._populate(); full = self.ws.claim_state(self.cid)
        v1 = full["versions"][0]; self.assertEqual(v1["time"]["source_available_as_of"], "2026-02-10T21:05:00Z"); self.assertNotEqual(v1["time"]["recorded_at"], v1["time"]["source_available_as_of"])
        self.assertTrue(v1["time"]["observed_at"] and v1["time"]["recorded_at"])
        early = self.ws.claim_state(self.cid, as_of="2026-03-01T00:00:00Z")
        self.assertEqual([v["version_id"] for v in early["versions"]], ["V1"]); self.assertIsNone(early["outcome"]); self.assertEqual(calc.adjudicate(early)["result"], "PENDING_OUTCOME")
        mid = self.ws.claim_state(self.cid, as_of="2026-06-01T00:00:00Z"); self.assertEqual([v["version_id"] for v in mid["versions"]], ["V1", "R1"]); self.assertIsNone(mid["outcome"])
        self.assertIsNone(self.ws.claim_state(self.cid, as_of="2026-01-01T00:00:00Z"))
        late = self.ws.claim_state(self.cid, as_of="2027-12-31T00:00:00Z"); self.assertEqual(calc.adjudicate(late)["result"], "IN_RANGE")
        self.assertEqual(early["versions"][0]["claim"]["range"], full["versions"][0]["claim"]["range"])      # the original is never rewritten by later events

    def test_withdrawn_claim_accepts_no_further_amendment_and_adjudication_binds_evidence(self):
        self._populate(); w = schema.from_fixture(json.loads((D / "003_withdrawal.json").read_text()))["revisions"][1]
        self.ws.amend_claim(self.cid, "WITHDRAWN", changes=None, reason="withdrawn", source=w["source"], op_id="op:withdraw-01")
        with self.assertRaises(ContractError):
            self.ws.amend_claim(self.cid, "REVISED", changes={"range": {"low": 1, "high": 2}}, reason="x", source=w["source"], op_id="op:amend-0002")
        st = self.ws.claim_state(self.cid); tip = st["events"][-1]["event_hash"]
        with self.assertRaises(ContractError):
            self.ws.record_adjudication(self.cid, reviewer="o", rule="r", evidence=["0" * 64], reason="x", conflicts="", label="IN_RANGE", disputed=False, op_id="op:adj-000001")
        with self.assertRaises(ContractError):                              # label differs from the computed result without the disputed flag
            self.ws.record_adjudication(self.cid, reviewer="o", rule="r", evidence=[tip], reason="x", conflicts="", label="IN_RANGE", disputed=False, op_id="op:adj-000002")
        ev, _ = self.ws.record_adjudication(self.cid, reviewer="o", rule="r", evidence=[tip], reason="I read the withdrawal differently", conflicts="calculator", label="IN_RANGE", disputed=True, op_id="op:adj-000003")
        self.assertTrue(ev["payload"]["disputed"]); self.assertEqual(ev["payload"]["computed_result"], "WITHDRAWN_BEFORE_OUTCOME")


if __name__ == "__main__":
    unittest.main()
