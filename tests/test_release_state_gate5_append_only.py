"""Gate 5 ('no v1 historical silent rewrite') on the protocol chain: byte-identical to base passes; an append-only extension (base
bytes a prefix of the candidate bytes, whole JSON lines appended) passes — that is the registry's documented append-only process;
any edited, reordered, truncated or removed historical byte fails."""
import pathlib, subprocess, sys, unittest

R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "tools")); sys.path.insert(0, str(R))
import yuclaw_release_state_v6 as gen  # noqa: E402

BASE = b'{"kind": "protocol", "line_hash": "a", "prev_hash": null}\n{"kind": "run", "line_hash": "b", "prev_hash": "a"}\n'
ADD = b'{"kind": "addendum", "line_hash": "c", "prev_hash": "b"}\n'


class Gate5(unittest.TestCase):
    def test_identical_and_append_only_pass(self):
        self.assertEqual(gen.chain_relation(BASE, BASE), {"identical": True, "append_only": True, "appended_lines": 0})
        r = gen.chain_relation(BASE, BASE + ADD); self.assertEqual((r["identical"], r["append_only"], r["appended_lines"]), (False, True, 1))
        r = gen.chain_relation(BASE, BASE + ADD + ADD.replace(b'"c"', b'"d"')); self.assertEqual((r["append_only"], r["appended_lines"]), (True, 2))

    def test_any_historical_change_fails(self):
        for cand in (BASE.replace(b'"run"', b'"question"'),                       # edited historical line
                     BASE.replace(b'"prev_hash": "a"', b'"prev_hash": "x"'),     # edited link
                     b"".join(reversed(BASE.splitlines(keepends=True))),         # reordered
                     BASE.splitlines(keepends=True)[0],                          # truncated
                     BASE[:-1],                                                  # trailing newline removed
                     BASE[:-1] + b' ' + ADD,                                     # history byte changed before the append
                     BASE + b'{"kind": "addendum", "line_hash": "c"'):           # incomplete appended line
            self.assertFalse(gen.chain_relation(BASE, cand)["append_only"], cand[:60])

    def test_this_tree_extends_origin_main_append_only(self):
        base = subprocess.run(["git", "-C", str(R), "show", "origin/main:registry/protocols.jsonl"], capture_output=True).stdout
        r = gen.chain_relation(base, (R / "registry" / "protocols.jsonl").read_bytes())
        self.assertTrue(r["append_only"], r)


if __name__ == "__main__":
    unittest.main()
