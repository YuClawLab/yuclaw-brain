"""8.0.1 C08 — the EvidenceBench page gives the current instruction, separates what exists from what does not, and
publishes the item-set identity and lineage it can actually establish.

8.0.0's page still said the scorer was not shipped (a 7.0.0 fact) and that rubric v2 came "in the next patch release".
The question-echo control is COMPUTED on the release's own items (never typed): v1 credits an echo on T1 (its disclosed
flaw, preserved), v2 rejects it — one negative control, not a validation. Lineage entries come from the repository
history of meta.json or from the generator; a weekly regeneration is a different item set, not a migration."""
import json, pathlib, re, sys, tempfile, unittest

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.web import render_evidencebench as R                                    # noqa: E402

BENCH = REPO / "docs" / "evidencebench"


class Page(unittest.TestCase):
    def test_the_echo_control_is_computed_v1_credits_an_echo_and_v2_rejects_it(self):
        c = R.echo_control(BENCH / "items.jsonl"); meta = json.loads((BENCH / "meta.json").read_text())
        self.assertEqual(c["n_items"], meta["n_items"]); self.assertEqual(c["item_set_hash"], meta["item_set_hash"])
        self.assertEqual(c["v1"]["T1"], 1.0); self.assertGreater(c["v1"]["aggregate"], 0.0)                     # the disclosed v1 flaw is reproduced, not hidden
        self.assertEqual((c["v2"]["T1"], c["v2"]["aggregate"]), (0.0, 0.0))                                      # v2 does not share it
        self.assertNotEqual(c["items_sha256"], c["item_set_hash"])                                               # file digest and canonical hash are different things

    def test_lineage_appends_a_release_once_keeps_history_and_invents_nothing(self):
        real = json.loads(R.LINEAGE.read_text()); counts = {r["generated"][:10]: r["n_items"] for r in real["releases"]}
        self.assertEqual((counts.get("2026-09-11"), counts.get("2026-09-18")), (872, 750))                       # two weekly item sets, both on record …
        self.assertEqual(len({r["item_set_hash"] for r in real["releases"]}), len(real["releases"]))             # … with different identities
        self.assertTrue(all("commit" in r["source"] or "generator" in r["source"] for r in real["releases"]))
        keep, R.LINEAGE = R.LINEAGE, pathlib.Path(tempfile.mkdtemp()) / "lineage.json"
        try:
            m1 = {"generated": "2026-10-02T00:00:00+00:00", "version": "0.1", "protocol_id": "p", "window": "w", "n_items": 5, "item_set_hash": "a" * 64}
            one = R.lineage(m1, {"items_sha256": "f" * 64}); two = R.lineage(m1, {"items_sha256": "f" * 64}); self.assertEqual(len(one["releases"]), 1); self.assertEqual(two["releases"], one["releases"])
            three = R.lineage(dict(m1, generated="2026-10-09T00:00:00+00:00", n_items=9, item_set_hash="b" * 64), {"items_sha256": "e" * 64})
            self.assertEqual([r["n_items"] for r in three["releases"]], [5, 9]); self.assertIn("not the sha256 of the items.jsonl file", three["rule"].replace("NOT", "not"))
        finally:
            R.LINEAGE = keep

    def test_the_staged_page_states_the_current_instruction_and_the_separate_statuses(self):
        html = (REPO / "docs" / "evidencebench.html").read_text(); text = " ".join(re.sub(r"<[^>]+>", " ", html).split()); meta = json.loads((BENCH / "meta.json").read_text())
        for gone in ("in the next patch release", "does not ship the scorer module", "How to run (v1 rubric — checkout method)"):
            self.assertNotIn(gone, text)
        for needle in ("pip install yuclaw", "yuclaw evidencebench score predictions.json", "Historical reproduction only", "Candidate", "not registered", "No v2 item set exists", "None is claimed",
                       "not semantic verification", "Canonical item-set hash", "Raw file SHA-256", "regenerated every week", meta["item_set_hash"], f"{meta['n_items']} items"):
            self.assertIn(needle, text)
        self.assertRegex(text, r"rubric v1 gives T1 = 1\.0 and aggregate 0\.\d+; rubric v2 gives T1 = 0\.0 and aggregate 0\.0")


if __name__ == "__main__":
    unittest.main()
