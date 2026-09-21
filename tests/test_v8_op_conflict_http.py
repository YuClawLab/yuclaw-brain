"""8.0.1 C04 — an operation identifier reused with DIFFERENT content is an ordinary conflict, answered over real HTTP.

In 8.0.0 `POST /verify` with a reused op_id and different uploaded bytes dropped the connection (StoreIntegrityError
E_OP_CONFLICT escaped the route), and other forms answered a conflict with the chain-failure page. A conflict is not
corruption: the response is a bounded, escaped 409 refusal with the reason and a next step; nothing is written; an
identical retry still returns normally without a second event; a new action needs an explicit resubmission with a fresh
identifier. Genuine chain damage and a torn tail keep their own fail-closed pages. Fictional data only."""
import pathlib, re, tempfile, threading, unittest, urllib.parse

from v8.workbench import server as S
from tests.test_v8_workbench_server import Client, _src

BAD_ZIP_A, BAD_ZIP_B = b"not a zip: fictional bytes A", b"not a zip: fictional bytes B (different)"
CT = {"Content-Type": "application/x-www-form-urlencoded"}


def serve(root):
    s = S.WorkbenchServer(root, 0, candidate_commit="cand-test"); threading.Thread(target=s.serve_forever, daemon=True).start(); S.Handler.log_message = lambda *a, **k: None
    return s


class OpConflictOverHttp(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="wb-conflict-")); self.srv = serve(self.tmp / "W"); self.c = Client(self.srv.server_address[1]); self.c.req("GET", "/verify")

    def tearDown(self):
        self.srv.shutdown(); self.srv.server_close()

    def log(self) -> bytes:
        return self.srv.ws.log.read_bytes() if self.srv.ws.log.exists() else b""

    def kinds(self):
        return [e["kind"] for e in self.srv.ws.load()["events"]]

    def assert_conflict_page(self, st, page):
        self.assertEqual(st, 409, page[:300]); text = page.decode()
        self.assertIn("E_OP_CONFLICT", text); self.assertIn("Nothing was written", text); self.assertIn("fresh operation identifier", text)
        for wrong in ("fails its chain check", "Run recovery", "action=\"/recover\"", "Traceback"):
            self.assertNotIn(wrong, text)
        self.assertLess(len(page), 20000)

    def test_verify_upload_identical_retry_then_conflict(self):
        op = "ui:conflict-verify-1"
        st, _, page = self.c.upload({"csrf": self.c.csrf, "op_id": op}, BAD_ZIP_A); self.assertEqual(st, 200); self.assertIn(b">UNSUPPORTED<", page); after_first = self.log()
        self.assertEqual(self.kinds().count("PACKET_VERIFIED"), 1)
        st, _, page = self.c.upload({"csrf": self.c.csrf, "op_id": op}, BAD_ZIP_A); self.assertEqual(st, 200); self.assertIn(b">UNSUPPORTED<", page); self.assertEqual(self.log(), after_first)   # identical retry: normal answer, no second event
        st, _, page = self.c.upload({"csrf": self.c.csrf, "op_id": op}, BAD_ZIP_B); self.assert_conflict_page(st, page)                                     # 8.0.0: RemoteDisconnected
        self.assertIn(b"choose the file again", page); self.assertEqual(self.log(), after_first); self.assertEqual(self.kinds().count("PACKET_VERIFIED"), 1)
        self.assertEqual(self.c.req("GET", "/verify")[0], 200); self.assertEqual(self.c.req("GET", "/")[0], 200)                                           # the server survived and the workspace serves
        _, _, pg = self.c.req("GET", "/verify"); fresh = re.search(rb'name="op_id" value="([^"]+)"', pg).group(1).decode(); self.assertNotEqual(fresh, op)
        st, _, page = self.c.upload({"csrf": self.c.csrf, "op_id": fresh}, BAD_ZIP_B); self.assertEqual(st, 200); self.assertEqual(self.kinds().count("PACKET_VERIFIED"), 2)   # an explicit resubmission with a fresh identifier

    def test_a_form_mutation_conflict_is_a_409_and_a_hostile_identifier_is_escaped(self):
        op = "ui:conflict-source-1"; a = _src("0000000000-26-000101", "2026-03-01", "2026-03-01T00:00:00Z", "Fictional passage one."); b = dict(a, excerpt="Fictional passage two — different content.")
        body = lambda f, o=op: urllib.parse.urlencode(dict(f, csrf=self.c.csrf, op_id=o))
        self.assertEqual(self.c.req("POST", "/source/register", body(a), CT)[0], 303); n1 = self.kinds().count("SOURCE_REGISTERED"); first = self.log(); self.assertEqual(n1, 1)
        self.assertEqual(self.c.req("POST", "/source/register", body(a), CT)[0], 303); self.assertEqual(self.log(), first)                                   # identical retry
        st, _, page = self.c.req("POST", "/source/register", body(b), CT); self.assert_conflict_page(st, page); self.assertEqual(self.log(), first)
        hostile = "ui:<b>x</b>&amp;--conflict"                                                                                                               # refused by the identifier pattern before any store call
        self.assertEqual(self.c.req("POST", "/source/register", body(a, hostile), CT)[0], 400)
        self.assertEqual(self.c.req("POST", "/source/register", body(b, "ui:conflict-source-2"), CT)[0], 303); self.assertEqual(self.kinds().count("SOURCE_REGISTERED"), 2)

    def test_after_a_restart_a_fresh_csrf_token_meets_the_same_rule_and_an_expired_token_is_refused_first(self):
        op = "ui:conflict-restart-1"; a = _src("0000000000-26-000102", "2026-03-02", "2026-03-02T00:00:00Z", "Fictional passage before the restart.")
        self.assertEqual(self.c.req("POST", "/source/register", urllib.parse.urlencode(dict(a, csrf=self.c.csrf, op_id=op)), CT)[0], 303); first = self.log(); old_csrf, old_cookie = self.c.csrf, self.c.cookie
        self.srv.shutdown(); self.srv.server_close(); self.srv = serve(self.tmp / "W"); c2 = Client(self.srv.server_address[1])
        c2.cookie = old_cookie; st, _, page = c2.req("POST", "/source/register", urllib.parse.urlencode(dict(a, csrf=old_csrf, op_id=op)), CT)
        self.assertEqual(st, 403); self.assertIn(b"CSRF token invalid", page); self.assertEqual(self.log(), first)                                           # expired token: refused on its own, before the store
        c2 = Client(self.srv.server_address[1]); c2.req("GET", "/source")
        self.assertEqual(c2.req("POST", "/source/register", urllib.parse.urlencode(dict(a, csrf=c2.csrf, op_id=op)), CT)[0], 303); self.assertEqual(self.log(), first)   # same content after a reload: idempotent
        st, _, page = c2.req("POST", "/source/register", urllib.parse.urlencode(dict(a, excerpt="Fictional, changed after the restart.", csrf=c2.csrf, op_id=op)), CT)
        self.assert_conflict_page(st, page); self.assertEqual(self.log(), first)

    def test_chain_damage_and_a_torn_tail_keep_their_own_fail_closed_pages(self):
        a = _src("0000000000-26-000103", "2026-03-03", "2026-03-03T00:00:00Z", "Fictional passage for the damage check.")
        self.assertEqual(self.c.req("POST", "/source/register", urllib.parse.urlencode(dict(a, csrf=self.c.csrf, op_id="ui:damage-0001")), CT)[0], 303); good = self.log()
        self.srv.ws.log.write_bytes(good + b'{"torn": ')                                                                                                     # an interrupted append
        st, _, page = self.c.req("POST", "/source/register", urllib.parse.urlencode(dict(a, excerpt="Fictional, after the torn tail.", csrf=self.c.csrf, op_id="ui:damage-0002")), CT)
        self.assertNotEqual(st, 409); self.assertIn(b"E_TORN_TAIL", page); self.assertIn(b'action="/recover"', page); self.assertNotIn(b"E_OP_CONFLICT", page)
        self.srv.ws.log.write_bytes(good.replace(b"Fictional passage for the damage check.", b"Fictional passage for the DAMAGE check."))                 # an edited durable record
        st, _, page = self.c.req("POST", "/source/register", urllib.parse.urlencode(dict(a, excerpt="Fictional, after the edit.", csrf=self.c.csrf, op_id="ui:damage-0003")), CT)
        self.assertNotEqual(st, 409); self.assertIn(b"fails its chain check", page); self.assertNotIn(b"E_OP_CONFLICT", page); self.assertNotIn(b'action="/recover"', page)


if __name__ == "__main__":
    unittest.main()
