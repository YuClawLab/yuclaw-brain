"""Sentinel lifecycle model: synthetic preflight/postflight cases mirroring the launcher's recorded rules; no session is touched."""
import pathlib, sys, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.ops import sentinel_lifecycle as sl  # noqa: E402

PIN = "a" * 64


class Lifecycle(unittest.TestCase):
    def test_preflight_order_and_supervised_bypass(self):
        self.assertEqual(sl.preflight(live_sessions=1, supervised=False, lock_held=False, prompt_sha256=PIN, prompt_pin=PIN).outcome, "REFUSED_SOLO_SESSION")
        self.assertIsNone(sl.preflight(live_sessions=1, supervised=True, lock_held=False, prompt_sha256=PIN, prompt_pin=PIN))                    # operator-present bypass only
        self.assertEqual(sl.preflight(live_sessions=0, supervised=False, lock_held=True, prompt_sha256=PIN, prompt_pin=PIN).outcome, "REFUSED_LOCK_HELD")
        d = sl.preflight(live_sessions=0, supervised=False, lock_held=False, prompt_sha256="b" * 64, prompt_pin=PIN); self.assertEqual((d.outcome, d.exit_code), ("REFUSED_PROMPT_TAMPER", 1)); self.assertIn("prompt hash", d.alert)
        self.assertEqual(sl.preflight(live_sessions=1, supervised=False, lock_held=True, prompt_sha256="b" * 64, prompt_pin=PIN).outcome, "REFUSED_SOLO_SESSION")   # first rule wins
    def test_postflight_authority_and_push(self):
        self.assertEqual(sl.postflight(runtime_s=100, head_moved=False, changed_paths=[], push_ok=None).outcome, "RAN_NO_COMMITS")
        d = sl.postflight(runtime_s=100, head_moved=True, changed_paths=["docs/index.html", "registry/protocols.jsonl"], push_ok=True); self.assertEqual(d.outcome, "AUTHORITY_VIOLATION_REVERTED"); self.assertIn("CRITICAL", d.alert)
        self.assertEqual(sl.postflight(runtime_s=100, head_moved=True, changed_paths=["tools/check_language.py"], push_ok=True).outcome, "AUTHORITY_VIOLATION_REVERTED")
        self.assertEqual(sl.postflight(runtime_s=100, head_moved=True, changed_paths=["docs/index.html"], push_ok=True).outcome, "RAN_PUSHED")
        self.assertEqual(sl.postflight(runtime_s=100, head_moved=True, changed_paths=["docs/index.html"], push_ok=False).outcome, "RAN_PUSH_FAILED")
        self.assertEqual(sl.postflight(runtime_s=1500, head_moved=False, changed_paths=[], push_ok=None).outcome, "TIMED_OUT")
    def test_log_classification_without_content(self):
        self.assertEqual(sl.classify_log_entry({"msg": "refusing: 1 live Claude session(s) — solo-session rule"}), "REFUSED_SOLO_SESSION")
        self.assertEqual(sl.classify_log_entry({"pushed": "yes", "n_commits": 2}), "RAN_PUSHED"); self.assertEqual(sl.classify_log_entry({"pushed": "no", "n_commits": 0}), "RAN_NO_COMMITS")
        self.assertEqual(sl.classify_log_entry({"msg": "AUTHORITY VIOLATION — forbidden paths touched"}), "AUTHORITY_VIOLATION_REVERTED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
