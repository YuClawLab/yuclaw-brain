"""V8-014 PRC (P-01…P-07), the browser surface (X-01…X-06) and module packets (X-08, S-08, P-06) over REAL HTTP against a
loopback server, with separate cookie jars per principal. The leak sweep fetches every URL a practitioner can reach before
its attempt and asserts the reference text is in none of them. Principals are automated fixtures, never people."""
import hashlib, io, json, pathlib, re, sys, threading, unittest, zipfile
from datetime import timedelta
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from v8_mod_helpers import Client, Server, bundle, load_fixture, principal, workspace   # noqa: E402
from v8.workbench import store                                                          # noqa: E402
from v8.workbench.modules import commons as com, core, modexport as mx, practice as prc, shield   # noqa: E402
from v8.workbench.modules.core import ModuleError                                       # noqa: E402

SECRET = "REFERENCE-ANSWER-7c1f-the-range-is-110-to-120"
FUTURE = (core.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")


def code(fn, *a, **k):
    try:
        fn(*a, **k)
    except ModuleError as exc:
        return exc.code
    return "NO_ERROR"


class Base(unittest.TestCase):
    def setUp(self):
        self.ws = workspace(); self.cid, self.sid = load_fixture(self.ws); self.creds = {}
        self.admin = self.mk("owner", ["admin"]); self.cur = self.mk("curator", ["review"]); self.pat = self.mk("pat", ["practice"]); self.pia = self.mk("pia", ["practice"]); self.alice = self.mk("alice", ["submit"])
        com.set_budget(self.ws, self.admin, period_id="p1", review_minutes=120, practice_minutes=60, contributor_packet_cap=10, max_open_tasks=20, op_id="op:budget-001"); self.n = 0

    def mk(self, pid, caps):
        p, c = principal(self.ws, pid, caps, by=getattr(self, "admin", None)); self.creds[pid] = c; return p

    def op(self):
        self.n += 1; return f"op:prc-{self.n:05d}"

    def task(self, **kw):
        a = dict(title="Guidance range reading", question="Is an actual of 112 million inside the stated range?", claim_id=self.cid, source_ids=[self.sid], labels=["IN_RANGE", "OUT_OF_RANGE"], reference_label="IN_RANGE",
                 reference_answer=SECRET, rationale="read from the fictional source", provenance="UNADJUDICATED_REFERENCE", declared_curator_qualification="declares: ten years of filings work", public_example=False, session_minutes=20, evo_version_id=None)
        a.update(kw); return prc.freeze_task(self.ws, self.cur, op_id=self.op(), **a)["payload"]

    def session(self, who, tid, assistance="NONE", exposure="NOT_SEEN"):
        return prc.open_session(self.ws, who, task_id=tid, assistance=assistance, assistance_note="", prior_exposure=exposure, op_id=self.op())["payload"]

    def attempt(self, who, ssid, judgment="IN_RANGE", op=None):
        return prc.commit_attempt(self.ws, who, ssid, judgment=judgment, reasoning="112 lies between 110 and 120", source_refs=[self.sid], unresolved_note="need the outcome filing" if judgment == "UNRESOLVED" else "", op_id=op or self.op())


class Practice(Base):
    def test_P01_frozen_task_identity_and_curator_conflict(self):
        t = self.task(); self.assertEqual(t["claim"]["claim_id"], self.cid); self.assertEqual(t["source_scope"][0]["source_id"], self.sid); self.assertTrue(t["qualification_status"].startswith("DECLARED"))
        raw = self.ws.log.read_text(); self.assertNotIn(SECRET, raw); self.assertIn(t["comparison_commitment"], raw)                                   # only the salted commitment is in the journal
        t2 = self.task(); self.assertNotEqual(t["comparison_commitment"], t2["comparison_commitment"])                                                # same low-entropy answer, different salt: not enumerable
        self.assertEqual(code(prc.freeze_task, self.ws, self.pat, title="x", question="q", claim_id=None, source_ids=[self.sid], labels=["A", "B"], reference_label="A", reference_answer="a", rationale="", provenance="MODEL_ANSWER",
                              declared_curator_qualification="", public_example=True, session_minutes=20, evo_version_id=None, op_id=self.op()), "E_FORBIDDEN")
        both = self.mk("curprac", ["review", "practice"]); t3 = prc.freeze_task(self.ws, both, title="own", question="q", claim_id=None, source_ids=[self.sid], labels=["A", "B"], reference_label="A", reference_answer="a", rationale="",
                                                                               provenance="MODEL_ANSWER", declared_curator_qualification="", public_example=True, session_minutes=20, evo_version_id=None, op_id=self.op())["payload"]
        self.assertEqual(code(prc.open_session, self.ws, both, task_id=t3["task_id"], assistance="NONE", assistance_note="", prior_exposure="NOT_SEEN", op_id=self.op()), "E_CONFLICT")   # the curator knows the answer
        self.assertEqual(code(prc.freeze_task, self.ws, self.cur, title="x", question="q", claim_id=None, source_ids=["no-such-source"], labels=["A", "B"], reference_label="A", reference_answer="a", rationale="", provenance="MODEL_ANSWER",
                              declared_curator_qualification="", public_example=True, session_minutes=20, evo_version_id=None, op_id=self.op()), "E_UNKNOWN_SOURCE")

    def test_P03_only_a_committed_attempt_unlocks_and_retries_are_idempotent(self):
        t = self.task(); ss = self.session(self.pat, t["task_id"])["session_id"]
        self.assertEqual(code(prc.reveal, self.ws, self.pat, ss), "E_ATTEMPT_FIRST"); self.assertIsNone(prc.session_view(self.ws, self.pat, ss)["comparison"])
        self.assertEqual(code(prc.commit_attempt, self.ws, self.pat, ss, judgment="IN_RANGE", reasoning="", source_refs=[self.sid], unresolved_note="", op_id=self.op()), "E_REQUIRED")
        self.assertEqual(code(prc.commit_attempt, self.ws, self.pat, ss, judgment="IN_RANGE", reasoning="r", source_refs=["out-of-scope"], unresolved_note="", op_id=self.op()), "E_SOURCE_REFS")
        a = self.attempt(self.pat, ss, op="op:attempt-same1"); b = self.attempt(self.pat, ss, op="op:attempt-same1"); self.assertEqual(a["event_hash"], b["event_hash"])       # a retry is the same event
        self.assertEqual(code(prc.commit_attempt, self.ws, self.pat, ss, judgment="OUT_OF_RANGE", reasoning="changed my mind", source_refs=[self.sid], unresolved_note="", op_id=self.op()), "E_ALREADY_COMMITTED")
        r = prc.reveal(self.ws, self.pat, ss); self.assertEqual(r["reference_answer"], SECRET); self.assertIn("not ground truth", r["provenance_meaning"]); prc.reveal(self.ws, self.pat, ss)
        self.assertEqual(sum(1 for e in self.ws.load()["events"] if e["kind"] == "PRC_COMPARISON_REVEALED"), 1); v = prc.session_view(self.ws, self.pat, ss)
        self.assertEqual(v["attempt"]["judgment"], "IN_RANGE"); self.assertNotIn("112 lies between", self.ws.log.read_text())                                                   # the original attempt is preserved, its text is private

    def test_P03_concurrent_attempt_and_reveal_are_deterministic(self):
        t = self.task(); ss = self.session(self.pat, t["task_id"])["session_id"]; out = {}

        def go(tag, fn):
            out[tag] = code(fn)
        ts = [threading.Thread(target=go, args=(f"r{i}", lambda: prc.reveal(self.ws, self.pat, ss))) for i in range(4)] + [threading.Thread(target=go, args=(f"a{i}", lambda i=i: self.attempt(self.pat, ss, judgment=("IN_RANGE", "OUT_OF_RANGE")[i % 2], op=f"op:attempt-c{i}00"))) for i in range(4)]
        [x.start() for x in ts]; [x.join() for x in ts]
        self.assertEqual(sum(1 for e in self.ws.load()["events"] if e["kind"] == "PRC_ATTEMPT_COMMITTED"), 1)                                                                # exactly one attempt wins
        evs = self.ws.load()["events"]; att = next(e["seq"] for e in evs if e["kind"] == "PRC_ATTEMPT_COMMITTED"); self.assertTrue(all(e["seq"] > att for e in evs if e["kind"] == "PRC_COMPARISON_REVEALED"))   # no reveal before it

    def test_P04_assisted_exposed_and_unresolved_sessions_are_accepted_with_truthful_labels(self):
        t = self.task(); a = self.session(self.pat, t["task_id"], assistance="AI_ASSISTED", exposure="NOT_SEEN"); b = self.session(self.pia, t["task_id"], assistance="NONE", exposure="SEEN_ANSWER")
        self.assertEqual((a["category"], b["category"]), ("ASSISTED", "ALREADY_EXPOSED")); self.attempt(self.pia, b["session_id"], judgment="UNRESOLVED")
        self.assertEqual(prc.session_view(self.ws, self.pia, b["session_id"])["attempt"]["unresolved_note"], "need the outcome filing")
        self.assertEqual(code(prc.open_session, self.ws, self.pat, task_id=t["task_id"], assistance="NONE", assistance_note="", prior_exposure="NOT_SEEN", op_id=self.op()), "E_SESSION_EXISTS")
        self.assertEqual(code(prc.open_session, self.ws, self.mk("pam", ["practice"]), task_id=t["task_id"], assistance="maybe", assistance_note="", prior_exposure="NOT_SEEN", op_id=self.op()), "E_DECLARATION")

    def test_P05_reflection_feedback_followup_and_the_practice_reserve(self):
        t = self.task(); t2 = self.task(title="follow-up"); ss = self.session(self.pat, t["task_id"])["session_id"]
        self.assertEqual(code(prc.reflect, self.ws, self.pat, ss, text_="early", op_id=self.op()), "E_REVEAL_FIRST"); self.attempt(self.pat, ss); prc.reveal(self.ws, self.pat, ss)
        prc.reflect(self.ws, self.pat, ss, text_="cite the range line", op_id=self.op()); prc.feedback(self.ws, self.cur, ss, text_="name the unit", op_id=self.op())
        self.assertEqual(code(prc.feedback, self.ws, self.pat, ss, text_="self", op_id=self.op()), "E_FORBIDDEN"); v = prc.session_view(self.ws, self.pat, ss)
        self.assertEqual((v["attempt"]["judgment"], len(v["reflections"]), len(v["feedback"])), ("IN_RANGE", 1, 1))                                                          # later records never rewrite the attempt
        prc.schedule_followup(self.ws, self.cur, session_id=ss, followup_task_id=t2["task_id"], due_at=FUTURE, op_id=self.op()); self.assertEqual(prc.due_state(prc.state(self.ws), "pat")[0]["state"], "NOT_YET_DUE")
        real = core.now
        with mock.patch.object(core, "now", lambda: real() + timedelta(days=9)):
            self.assertEqual(prc.due_state(prc.state(self.ws), "pat")[0]["state"], "DUE")
        self.session(self.pat, t2["task_id"]); self.assertEqual(prc.due_state(prc.state(self.ws), "pat")[0]["state"], "COMPLETED")
        cap = com.capacity(com.state(self.ws)); self.assertEqual((cap["practice_reserved"], cap["practice_remaining"], cap["reserved"]), (40, 20, 0))                       # practice minutes are their own reserve
        self.session(self.pia, t["task_id"]); self.assertEqual(code(prc.open_session, self.ws, self.mk("pam", ["practice"]), task_id=t["task_id"], assistance="NONE", assistance_note="", prior_exposure="NOT_SEEN", op_id=self.op()), "E_NO_PRACTICE_CAPACITY")
        self.assertEqual(com.capacity(com.state(self.ws))["remaining"], 120)                                                                                                  # review capacity was never borrowed

    def test_P07_later_source_and_claim_changes_annotate_without_rewriting(self):
        t = self.task(); ss = self.session(self.pat, t["task_id"])["session_id"]; self.attempt(self.pat, ss); before = prc.session_view(self.ws, self.pat, ss)["attempt"]
        src = self.ws.claim_state(self.cid)["versions"][0]["claim"]["source"]
        self.ws.correct_source_availability(self.sid, {"corrected_available_as_of": "2027-03-01T00:00:00Z", "reason": "wrong time", "evidence_ref": "fictional", "actor": "test fixture", "simulated": True}, expected_prior=src["available_as_of"], op_id="op:availcorr-01")
        v = prc.session_view(self.ws, self.pat, ss); self.assertEqual(v["attempt"], before); self.assertTrue(any("availability time was corrected" in n for n in v["current_interpretation"]))
        g = com.submit_direct(self.ws, self.alice, claim_id=self.cid, kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=5, asserts_withdrawn=False, client_packet_id=None, op_id=self.op())["payload"]["group_id"]
        self.assertEqual(com.dashboard(self.ws)["upstream_flags"][g], ["SOURCE_TIME_CORRECTED"])                                                           # the COM queue shows the same correction on the group (found missing by the V8-014 claim check, fixed)
        self.assertEqual(prc.state(self.ws)["tasks"][t["task_id"]]["comparison_commitment"], t["comparison_commitment"])


class Surface(Base):
    def setUp(self):
        super().setUp(); self.srv = Server(self.ws.root); self.addCleanup(self.srv.close)

    def client(self, pid):
        c = Client(self.srv); st, _, _ = c.login(pid, self.creds[pid]); self.assertEqual(st, 200); return c

    def test_P02_no_early_answer_on_any_surface_a_practitioner_can_reach(self):
        t = self.task(); c = self.client("pat"); st, body, loc = c.post("/prc/open", {"task_id": t["task_id"], "assistance": "NONE", "assistance_note": "", "prior_exposure": "NOT_SEEN"}, page="/prc"); self.assertEqual(st, 200)
        ssid = loc.rsplit("/", 1)[1]; urls = ["/", "/prc", "/modules", "/help", "/help/data", "/static/style.css", "/journal", "/dataset", "/dataset.json", "/notes", "/sci", "/verify", "/source", "/claim/new", f"/claim/{self.cid}",
                                               f"/claim/{self.cid}?as_of=2030-01-01T00:00:00Z", "/com", "/shd", "/shd/trust", "/evo", "/setup", "/modx", f"/prc/session/{ssid}", f"/prc/session/{ssid}?as_of=2030-01-01T00:00:00Z",
                                               f"/prc/session/{ssid}/source?id={self.sid}", "/prc/session/SS999", "/prc/checkpoint/1.json", "/modx/modx-0000000000000000.zip", "/exports/exp-0000000000000000.zip", f"/prc/session/{ssid}/reveal", "/nope"]
        for u in urls:
            st, body, _ = c.get(u); self.assertNotIn(SECRET, body, u); self.assertNotIn(t["comparison_commitment"], body, u)
        st, body, _ = c.post(f"/prc/session/{ssid}/reveal", {}, page=f"/prc/session/{ssid}"); self.assertEqual(st, 422); self.assertIn("E_ATTEMPT_FIRST", body); self.assertNotIn(SECRET, body)      # direct POST, error page included
        st, body, _ = c.post("/modx/build", {"prc_sessions": ssid}, page="/modx", follow=False); exp = re.search(r"built=(modx-[0-9a-f]{16})", _ or "")
        self.assertIsNotNone(exp); raw = c._req("GET", f"/modx/{exp.group(1)}.zip")[1]; self.assertNotIn(SECRET, raw)                                                        # an export before the attempt carries no answer
        other = self.client("pia"); st, body, _ = other.get(f"/prc/session/{ssid}"); self.assertEqual(st, 404); self.assertNotIn(SECRET, body)                               # cross-session access
        st, body, _ = c.post(f"/prc/session/{ssid}/attempt", {"judgment": "IN_RANGE", "reasoning": "112 is inside", f"ref_{self.sid}": "1", "unresolved_note": ""}, page=f"/prc/session/{ssid}"); self.assertEqual(st, 200)
        st, body, _ = c.post(f"/prc/session/{ssid}/reveal", {}, page=f"/prc/session/{ssid}"); self.assertIn(SECRET, body); self.assertIn("not ground truth", body)             # POSITIVE counterpart: after the attempt it opens
        st, body, _ = other.get(f"/prc/session/{ssid}"); self.assertNotIn(SECRET, body)

    def test_P02_X11_sensitivity_disabling_the_reveal_rule_is_detected_by_the_leak_check(self):
        t = self.task(); ss = self.session(self.pat, t["task_id"])["session_id"]; c = self.client("pat")
        with mock.patch.object(prc, "_may_reveal", lambda s: True):
            st, body, _ = c.post(f"/prc/session/{ss}/reveal", {}, page=f"/prc/session/{ss}")
            with self.assertRaises(AssertionError):
                self.assertNotIn(SECRET, body)                                                                                                                                # with the rule off the same assertion fails: the test sees the leak

    def test_X03_roles_objects_sessions_csrf_host_and_forged_actor(self):
        pre = Client(self.srv); before = pre.cookies.get("wb_session"); pre.login("owner", self.creds["owner"]); self.assertNotEqual(pre.cookies.get("wb_session"), before)   # the form-token session is replaced at sign-in
        a, s = self.client("owner"), self.client("alice")
        for path, fields in (("/shd/root", {"label": "mine"}), ("/shd/policy", {"max_approval_days": "300", "purpose_com.packets": "1"}), ("/setup/enroll", {"principal_id": "mallory", "cap_admin": "1"}), ("/com/budget", {"period_id": "p9", "review_minutes": "9", "practice_minutes": "9", "contributor_packet_cap": "9", "max_open_tasks": "9"})):
            st, body, _ = s.post(path, fields, page="/com"); self.assertEqual(st, 403, path); self.assertIn("E_FORBIDDEN", body)
        self.assertNotIn("mallory", [p for p in self.srv.srv.principals.state()]); n = len(self.ws.load()["events"])
        st, body, _ = s.post("/com/submit", {"claim_id": self.cid, "kind": "SUMMARY", "ancestry": "KNOWN", "derived_from": "", "proposed_cost_minutes": "10", "actor": "owner", "principal": "owner", "submitter": "owner", "principal_id": "owner"}, page="/com")
        self.assertEqual(st, 200); ev = self.ws.load()["events"][-1]; self.assertEqual((ev["actor"], ev["payload"]["submitter"]), ("principal:alice", "alice"))               # a form field never becomes the actor
        bad = Client(self.srv); bad.cookies = dict(s.cookies); st, body, _ = bad._req("POST", "/com/submit", "claim_id=x&csrf=deadbeef&op_id=op:forged-0001", {"Content-Type": "application/x-www-form-urlencoded"}); self.assertEqual(st, 403); self.assertIn("CSRF", body)
        st, body, _ = s._req("POST", "/com/submit", "x=1", {"Content-Type": "application/x-www-form-urlencoded", "Origin": "http://evil.example"}); self.assertEqual(st, 403)
        st, body, _ = s._req("GET", "/com", None, {"Host": "evil.example"}); self.assertEqual(st, 400)
        anon = Client(self.srv); st, _, hd = anon._req("GET", "/com"); self.assertEqual((st, hd["location"]), (303, "/login?next=%2Fcom")); anon.cookies["wb_auth"] = "0" * 64; self.assertEqual(anon._req("GET", "/com")[0], 303)   # a made-up session id
        stolen = Client(self.srv); stolen.cookies["wb_auth"] = a.cookies["wb_auth"]; self.assertEqual(stolen.get("/setup")[0], 200); a.get("/logout"); self.assertEqual(stolen._req("GET", "/setup")[0], 303)                 # sign-out ends the server-side session
        self.srv.srv.principals.revoke("alice", "test", op_id="op:revoke-alice", by=None); self.assertEqual(s._req("GET", "/com")[0], 303)                                   # revocation takes effect on the next request
        for _ in range(6):
            bad.login("owner", "wrong-credential-xx")
        st, body, _ = bad.login("owner", self.creds["owner"]); self.assertEqual(st, 403); self.assertIn("too many failed attempts", body)                                       # bounded guessing

    def test_X06_unsafe_text_is_rendered_inert_and_uploads_are_bounded_before_reading(self):
        x = '<script>alert("x")</script><img src=x onerror=alert(1)>'; c = self.client("curator"); a = self.client("owner")
        prc.freeze_task(self.ws, self.cur, title=x, question=x, claim_id=None, source_ids=[self.sid], labels=["A", "B"], reference_label="A", reference_answer="a", rationale="", provenance="MODEL_ANSWER", declared_curator_qualification=x,
                        public_example=True, session_minutes=20, evo_version_id=None, op_id=self.op())
        com.record_dispute(self.ws, self.cur, target_type="claim", target=self.cid, dispute_type="DISPUTED", reason=x, op_id=self.op())
        for u in ("/prc", "/com", "/modules"):
            body = c.get(u)[1]; self.assertNotIn("<script>alert", body, u); self.assertNotIn("<img src=x", body, u)
        self.assertIn("&lt;script&gt;", c.get("/prc")[1]); hd = c.get("/prc")[2]; self.assertIn("default-src 'none'", hd["content-security-policy"]); self.assertEqual(hd["cache-control"], "no-store")
        s = self.client("alice"); st, body, _ = s._req("POST", "/shd/submit", b"x", {"Content-Type": "multipart/form-data; boundary=x", "Content-Length": str(64 * 1024 * 1024)}); self.assertEqual(st, 413)     # refused on the header alone
        st, body, _ = s.upload("/shd/submit", {"title": "ok"}, {"bundle": ("b.zip", bundle()[0])}, page="/shd"); self.assertEqual(st, 200); self.assertIn("SB1", body)     # positive counterpart
        self.assertNotIn(self.creds["owner"], self.ws.log.read_text()); self.assertNotIn("credential=", self.ws.log.read_text())

    def test_X01_X05_unconfigured_workspace_shows_the_setup_step_and_state_survives_restart(self):
        fresh = workspace("fresh"); srv = Server(fresh.root); self.addCleanup(srv.close); c = Client(srv)
        for u in ("/modules", "/setup", "/shd", "/evo", "/com", "/prc", "/modx"):
            st, body, _ = c.get(u); self.assertEqual(st, 200, u); self.assertIn("principals init", body, u)                                                                   # discoverable, never hidden, exact setup step
        self.assertEqual(c.get("/")[0], 200); self.assertIn('href="/modules"', c.get("/")[1])                                                                                 # the ordinary workbench is unchanged without principals
        t = self.task(); ss = self.session(self.pat, t["task_id"])["session_id"]; self.attempt(self.pat, ss); self.srv.close()
        again = Server(self.ws.root); self.addCleanup(again.close); c = Client(again); self.assertEqual(c.login("pat", self.creds["pat"])[0], 200); self.assertIn("IN_RANGE", c.get(f"/prc/session/{ss}")[1])


class Packets(Base):
    def build(self, who, **kw):
        a = dict(modules=[], prc_sessions=[], withhold_text=False); a.update(kw); r = mx.build_packet(self.ws, who, op_id=self.op(), **a); return pathlib.Path(r["zip_path"]).read_bytes()

    def repack(self, raw, mutate, resign=True):
        p = json.loads(zipfile.ZipFile(io.BytesIO(raw)).read("packet.json")); mutate(p)
        if resign:
            body = {k: v for k, v in p.items() if k not in ("packet_digest", "packet_signature")}; p["packet_digest"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest(); p["packet_signature"] = None
        b = io.BytesIO(); zipfile.ZipFile(b, "w").writestr("packet.json", json.dumps(p)); return b.getvalue()

    def test_X08_P06_fresh_receiver_recomputes_distinguishes_trust_and_rejects_forgeries(self):
        shield.enroll_root(self.ws, self.admin, label="root", op_id="op:root-000001"); data, bh, bsrc = bundle(); sb = shield.submit(self.ws, self.alice, data, title="b", op_id="op:sub-packet01")["payload"]["submission_id"]
        shield.issue_approval(self.ws, self.admin, bundle_sha256=bh, source_sha256s=bsrc, purpose="evidence.reference", expires_at=FUTURE, op_id="op:apr-packet01"); self.assertEqual(shield.admit(self.ws, self.alice, sb, op_id="op:adm-packet01")["payload"]["result"], "ADMITTED")
        com.submit_direct(self.ws, self.alice, claim_id=self.cid, kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=10, asserts_withdrawn=False, client_packet_id=None, op_id=self.op())
        t = self.task(); ss = self.session(self.pat, t["task_id"])["session_id"]; early = self.build(self.pat, prc_sessions=[ss]); self.assertNotIn(SECRET.encode(), zipfile.ZipFile(io.BytesIO(early)).read("packet.json"))
        self.assertEqual(code(mx.build_packet, self.ws, self.pia, modules=[], prc_sessions=[ss], withhold_text=False, op_id=self.op()), "E_NOT_FOUND")                          # another practitioner's session
        self.assertEqual(code(mx.build_packet, self.ws, self.pat, modules=["COM"], prc_sessions=[], withhold_text=False, op_id=self.op()), "E_FORBIDDEN")
        self.attempt(self.pat, ss); prc.reveal(self.ws, self.pat, ss); cp = json.dumps(prc.issue_checkpoint(self.ws, self.admin, op_id=self.op())["payload"]["checkpoint"]).encode()
        raw = self.build(self.admin, modules=["SHD", "EVO", "COM"], prc_sessions=[ss]); pkt = zipfile.ZipFile(io.BytesIO(raw)).read("packet.json").decode()
        for never in (self.creds["owner"], "BEGIN PRIVATE KEY", "scrypt"):
            self.assertNotIn(never, pkt)
        fresh = workspace("receiver"); v = mx.verify_packet(fresh, raw, op_id="op:verify-0001")
        self.assertEqual((v["result"], v["trust"]["packet_signature"]["integrity"], v["trust"]["packet_signature"]["trust"]), ("SUCCESS", "VALID", "UNKNOWN_SIGNER"))          # integrity holds; an unknown signer stays unknown
        self.assertEqual(v["recompute"], ["recompute-com: MATCH", "recompute-evo: MATCH", "recompute-shd: MATCH"]); self.assertIn("UNKNOWN", v["freshness"]["current_authorization"])
        self.assertEqual(shield.state(fresh)["roots"], {}); self.assertEqual(com.state(fresh)["packets"], {}); self.assertFalse(authz_configured(fresh))                       # verification installs nothing
        radmin, _ = principal(fresh, "rowner", ["admin"]); key = json.loads(pkt)["trust_snapshot"]["roots"][0]["public_key"]; shield.enroll_root(fresh, radmin, label="origin root, enrolled by THIS receiver", public_key=key, op_id="op:root-recv001")
        self.assertEqual(mx.verify_packet(fresh, raw)["trust"]["packet_signature"]["trust"], "TRUSTED")                                                                        # POSITIVE counterpart: the receiver's own administrator enrolled it
        self.assertEqual(mx.verify_packet(fresh, raw, checkpoint=cp)["checkpoint"], "CONSISTENT"); old = mx.verify_packet(fresh, early, checkpoint=cp)
        self.assertEqual((old["result"], old["checkpoint"]), ("MISMATCH", "TRUNCATED_OR_ALTERED"))                                                                             # truncation against a SEPARATELY held checkpoint
        comp = core.Vault(self.ws).get(t["comparison_commitment"])
        cases = {"UNAUTHORIZED_PRIVATE_ANSWER": self.repack(early, lambda p: p["objects"].__setitem__(t["comparison_commitment"], comp)), "FORGED_LINK": self.repack(raw, lambda p: p["objects"].__setitem__(hashlib.sha256(b'{"x":1}').hexdigest(), {"x": 1})),
                 "does not re-hash": self.repack(raw, lambda p: p["events"][0]["payload"].__setitem__("injected", True)), "differs from the packet": self.repack(raw, lambda p: p["derived"]["com"].__setitem__("packets", 99)),
                 "packet_digest does not match": self.repack(raw, lambda p: p.__setitem__("built_by", "mallory"), resign=False), "skeleton breaks": self.repack(raw, lambda p: p["journal_skeleton"].pop(2))}
        for expect, data in cases.items():
            r = mx.verify_packet(fresh, data); self.assertEqual(r["result"], "MISMATCH", expect); self.assertIn(expect, r["first_discrepancy"], expect)
        self.assertEqual(mx.verify_packet(fresh, self.repack(raw, lambda p: p.__setitem__("format", "yuclaw-module-packet/9")))["result"], "UNSUPPORTED")                       # a future version is refused clearly
        self.assertEqual(mx.verify_packet(fresh, b"not a zip")["result"], "UNSUPPORTED"); wh = self.build(self.pat, prc_sessions=[ss], withhold_text=True); self.assertNotIn(b"112 lies between", zipfile.ZipFile(io.BytesIO(wh)).read("packet.json"))
        self.assertEqual(mx.verify_packet(fresh, wh)["result"], "SUCCESS")

    def test_S08_an_older_trust_snapshot_and_a_locally_revoked_root_are_discrepancies_not_state_changes(self):
        shield.enroll_root(self.ws, self.admin, label="root", op_id="op:root-000001"); kid = next(iter(shield.state(self.ws)["roots"])); old = self.build(self.admin, modules=["SHD"])
        shield.set_policy(self.ws, self.admin, max_approval_days=10, allowed_purposes=["com.packets"], op_id="op:policy-0001"); new = self.build(self.admin, modules=["SHD"])
        recv = workspace("receiver"); radmin, _ = principal(recv, "rowner", ["admin"]); key = shield.state(self.ws)["roots"][kid]["public_key"]
        shield.enroll_root(recv, radmin, label="origin", public_key=key, op_id="op:root-recv001"); self.assertEqual(mx.verify_packet(recv, new, op_id="op:verify-new01")["discrepancies"], [])
        r = mx.verify_packet(recv, old, op_id="op:verify-old01"); self.assertEqual(r["result"], "SUCCESS"); self.assertTrue(r["discrepancies"][0].startswith("TRUST_STATE_ROLLBACK"))
        shield.revoke_root(recv, radmin, kid, "compromised", op_id="op:rootrev-recv"); r = mx.verify_packet(recv, new, op_id="op:verify-new02")
        self.assertTrue(any(d.startswith("REVOKED_HERE_TRUSTED_THERE") for d in r["discrepancies"])); self.assertEqual(r["trust"]["packet_signature"]["trust"], "REVOKED_ROOT")
        st = shield.state(recv); self.assertTrue(st["roots"][kid]["revoked"]); self.assertEqual(st["policy"]["policy_version"], 1); self.assertEqual(len(st["discrepancies"]), 2)   # an import never revives a root or installs a policy
        self.assertEqual(code(mx.resolve_discrepancy, recv, None, packet_sha256=r["packet_sha256"], resolution="x", op_id="op:resolve-0001"), "E_SIGN_IN")
        mx.resolve_discrepancy(recv, radmin, packet_sha256=r["packet_sha256"], resolution="confirmed with the origin's owner by phone; our revocation stands", op_id="op:resolve-0002"); self.assertEqual(len(shield.state(recv)["discrepancies"]), 3)


def authz_configured(ws) -> bool:
    from v8.workbench.modules import authz
    return authz.Principals(ws).configured()


if __name__ == "__main__":
    unittest.main()
