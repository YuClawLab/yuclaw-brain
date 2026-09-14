"""V7-005 focused closure: export boundary sweep/policy, state-specific board schema, minimum-Python grammar scan,
v7 public notes composed from and checked against the recorded release policy."""
import contextlib, io, json, os, pathlib, subprocess, sys, tempfile, unittest
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.receipts import scoreboard, target as tgt, verify  # noqa: E402
from v3.receipts.store import Store  # noqa: E402
from v3.cli import receipts as receipts_cli  # noqa: E402
from v3.web import render_scoreboard  # noqa: E402
from v3.release import notes_v7  # noqa: E402

T0 = datetime(2026, 9, 20, 12, 0, 0, 1, tzinfo=timezone.utc)
WHEEL = b"SYNTHETIC-PROVENANCE wheel bytes for the closure tests\n"


def run(main, argv, env=None):
    out, err = io.StringIO(), io.StringIO(); old = dict(os.environ)
    try:
        os.environ.update(env or {})
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = main(argv)
    except SystemExit as e:
        rc = e.code
    finally:
        os.environ.clear(); os.environ.update(old)
    return rc, out.getvalue(), err.getvalue()


def submission(aid, note=None):
    h, n = verify.sha256_len(WHEEL)
    d = {"schema_version": "receipt-1", "attempt_id": aid, "activity_id": "act", "participant_id": "P-A", "group_id": "G-A", "relationship": "UNRELATED",
         "execution_control": "SELF", "assistance": "NONE", "incentive_outcome_dependent": False, "activity_type": "REPLICATION", "outcome": "REPRODUCED",
         "observed_at": T0.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "artifact_binding": {"artifact_type": "wheel", "sha256": h, "size_bytes": n},
         "release_identity": {"tag": "v7.0.0", "source_sha": "5" * 40}, "environment": {"os": "SynOS", "python": "3.12"}, "protocol_id": "prog"}
    if note is not None:
        d["public_note"] = note; d["disclosure_permitted"] = True
    return d


class Fixture:
    def __init__(self, tmp):
        self.d = pathlib.Path(tmp); self.root = self.d / "s"; self.st = Store(self.root); self.st.designate_reviewer("rev", "R", designated=True)
        self.deny = self.d / "deny.txt"; self.deny.write_text("# private\nforbiddenword\n")
    def full(self, aid, note=None):
        r = self.st.import_submission(submission(aid, note), synthetic=False, received_at=T0)
        self.st.add_observation(r["digest"], verify.observe(submission(aid)["artifact_binding"], data=WHEEL, now=T0))
        self.st.add_review(r["digest"], "QUALIFIED", reviewer_role="rev", token="R", now=T0); return r


class ExportBoundary(unittest.TestCase):
    def test_export_refuses_without_policy_and_sweeps_with_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Fixture(tmp); f.full("a1")
            rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "export", "--out", str(f.d / "x.json")], env={"YUCLAW_PUBLICATION_DENYLIST": str(f.d / "missing.txt")})
            self.assertEqual(rc, 1); self.assertIn("E_POLICY_UNAVAILABLE", err); self.assertFalse((f.d / "x.json").exists())         # missing denylist ≠ empty denylist
            rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "export", "--out", str(f.d / "x.json")], env={"YUCLAW_PUBLICATION_DENYLIST": str(f.deny)})
            self.assertEqual(rc, 0, err); rows = json.loads((f.d / "x.json").read_text()); self.assertEqual(len(rows), 1)
            f.full("a2", note="contains forbiddenword here")
            rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "export"], env={"YUCLAW_PUBLICATION_DENYLIST": str(f.deny)})
            self.assertEqual(rc, 0); self.assertNotIn("forbiddenword", out); self.assertEqual(len(json.loads(out)), 2)                 # projection already drops an unpublishable note
            real = receipts_cli.export.project_many
            def leaky(*a, **k):
                rows = real(*a, **k); rows[0]["public_note"] = "leak forbiddenword"; return rows                                        # a projection gap: the boundary sweep must still refuse
            receipts_cli.export.project_many = leaky
            try:
                rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "export", "--out", str(f.d / "y.json")], env={"YUCLAW_PUBLICATION_DENYLIST": str(f.deny)})
            finally:
                receipts_cli.export.project_many = real
            self.assertEqual(rc, 1); self.assertIn("publication sweep", err); self.assertNotIn("forbiddenword", err); self.assertEqual(out, ""); self.assertFalse((f.d / "y.json").exists())   # field path only; nothing written
            rc, out, err = run(receipts_cli.main, ["--store", str(f.root), "--synthetic", "export"], env={"YUCLAW_PUBLICATION_DENYLIST": str(f.d / "missing.txt")})
            self.assertEqual(rc, 0)                                                                                                    # synthetic export needs no policy (never public)


class StateSpecificSchema(unittest.TestCase):
    def board(self, f, target=None):
        return scoreboard.build(f.root, synthetic=False, target=target, now=T0)
    def test_target_and_coverage_keys_by_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["YUCLAW_PUBLICATION_DENYLIST"] = str(pathlib.Path(tmp) / "deny.txt")
            try:
                f = Fixture(tmp); f.full("a1")
                h, n = verify.sha256_len(WHEEL)
                t = tgt.build_target(label="REHEARSAL", generated_from="rehearsal-record", tag="v7.0.0", version="7.0.0", source_sha="5" * 40, source_tree="6" * 40, now=T0,
                                     artifacts=[{"artifact_type": "wheel", "filename": "yuclaw-7.0.0-py3-none-any.whl", "sha256": h, "size_bytes": n}])
                unbound = self.board(f); bound = self.board(f, target=t)
                self.assertEqual(unbound["target"]["state"], "UNBOUND"); self.assertEqual(bound["target"]["state"], "BOUND")
                for b in (unbound, bound):
                    scoreboard.validate_board(b); render_scoreboard.render(b, "OK")                                                    # complete keys → the renderer never KeyErrors
                cov_path = ("columns", "replications", "exact_release_evidence", "exact_target_evidence")
                def cov(b):
                    cur = b
                    for k in cov_path: cur = cur[k]
                    return cur
                self.assertEqual(cov(bound)["state"], "BOUND"); self.assertIn("release", cov(bound)); self.assertIn("note", cov(unbound))
                cases = []
                b = json.loads(json.dumps(bound)); del b["target"]["label"]; cases.append((b, "target"))
                b = json.loads(json.dumps(bound)); del cov(b)["release"]; cases.append((b, "exact_target_evidence"))
                b = json.loads(json.dumps(bound)); cov(b)["label"] = "FINAL"; cases.append((b, "exact_target_evidence"))                 # coverage label must equal target label
                b = json.loads(json.dumps(unbound)); del b["target"]["note"]; cases.append((b, "target"))
                b = json.loads(json.dumps(unbound)); cov(b)["artifacts_total"] = 2; cases.append((b, "exact_target_evidence"))         # UNBOUND carries no counts
                b = json.loads(json.dumps(unbound)); b["target"]["label"] = "FINAL"; cases.append((b, "target"))                       # UNBOUND carries no label
                for b, field in cases:
                    with self.assertRaises(scoreboard.BoardError) as cm: scoreboard.validate_board(b)
                    self.assertIn(field, cm.exception.field)
            finally:
                os.environ.pop("YUCLAW_PUBLICATION_DENYLIST", None)


class MinimumPython(unittest.TestCase):
    def test_no_312_only_fstring_grammar(self):
        r = subprocess.run([sys.executable, str(REPO / "tools" / "check_py_minimum.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


V6_STYLE = """Research & education only. Not investment advice.

### YUCLAW 7.0.0 — Evidence-First Financial AI

Tagline paragraph.

#### Shipped objects — name · receipt · status

- Object one · sha256 abc… · GREEN
- yuclaw 7.0.0 package · wheel + sdist sha256 attached to this release

#### Not in this release

- N_eff PENDING

#### Made in Canada

Built in Canada.
"""
EXC = ("I, the owner, accept for the 7.0.0 release only an explicit release-policy exception for Gate #15 (user comprehension test passes): the requirement is not satisfied because no authorized, completed, eligible human comprehension study exists; "
       "the gate remains MANUAL_REVIEW and is not waived; the study kit ships only when actually complete and the human study remains pending; the release notes and release-state record disclose this exception verbatim. Authorized by the owner as release-policy actor. Date 2026-09-20.")


class NotesV7(unittest.TestCase):
    def policy(self, route="B"):
        p = {"version": "7.0.0", "allocation": {"accepted": True, "decision": "D1-ACCEPT", "document_id": "V7-ALLOC-C1", "sha256": "ab" * 32}, "gate15": {"route": route}, "activations_active": []}
        if route == "B": p["gate15"].update(exception_text=EXC)
        else: p["gate15"].update(gate_input="CANDIDATE_GATE_INPUT", gate_15_proposed="GREEN", coverage={"materials_manifest_sha256": "c" * 64, "wheel_sha256": "d" * 64})
        return p
    def test_compose_and_correspondence(self):
        board = json.loads((REPO / "docs" / "receipts" / "scoreboard.json").read_text())
        notes = notes_v7.compose(V6_STYLE, version="7.0.0", policy=self.policy("B"), board=board)
        self.assertEqual(notes_v7.check_correspondence(notes, self.policy("B")), [])
        self.assertIn("#### New in 7.0.0", notes); self.assertIn("#### Continuing objects (unchanged from 6.0)", notes); self.assertIn("- Object one", notes); self.assertIn("#### Made in Canada", notes)
        self.assertIn(f"  > {EXC}", notes); self.assertIn("NOT SATISFIED", notes); self.assertIn("V7-ALLOC-C1", notes); self.assertIn("Phase-5 contribution anatomy: a READER", notes)
        for name, _ in notes_v7.ACTIVATIONS: self.assertIn(f"- {name}: INACTIVE", notes)
        for banned in ("docs/", "registry/", "output/", "tools/", "check_", ".py", "seed", "bootstrap", "CI [", "{'", "generated"):
            self.assertNotIn(banned, notes, banned)                                                                                    # the generator's Tier-2 rule
        self.assertNotIn("independently replicated", notes.lower())
        other = self.policy("B"); other["gate15"]["exception_text"] = EXC.replace("2026-09-20", "2026-09-21")
        self.assertIn("route B: the owner's exception text is not quoted verbatim", notes_v7.check_correspondence(notes, other))         # a different sentence never corresponds
        other = self.policy("B"); other["activations_active"] = ["sentinel policy"]
        self.assertTrue(any("sentinel policy" in p for p in notes_v7.check_correspondence(notes, other)))
        notes_a = notes_v7.compose(V6_STYLE, version="7.0.0", policy=self.policy("A"), board=board)
        self.assertEqual(notes_v7.check_correspondence(notes_a, self.policy("A")), []); self.assertIn("covers materials manifest cccccccccccccccc", notes_a)
        draft = notes_v7.compose(V6_STYLE, version="7.0.0", policy=None, board=None)
        self.assertIn("NOT RECORDED", draft); self.assertEqual(notes_v7.check_correspondence(draft, None), ["no release-policy record"])
        self.assertIn("no totals are stated", draft)


if __name__ == "__main__":
    unittest.main(verbosity=2)
