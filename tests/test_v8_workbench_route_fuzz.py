"""V8-010 §3: every form route answers hostile or malformed field values with a response — a redirect, a refusal page or a
plain refusal — and never with a dropped connection (an unhandled exception in the handler); every 422 says nothing was
written; the journal stays intact. A compact deterministic sweep, not a security review."""
import json, pathlib, tempfile, threading, unittest

from tests.test_v8_workbench_server import CLAIM, Client, _src
from v8.workbench import server as S

WEIRD = ["", " ", "\x00", "\U0001F642" * 50, "x" * 5000, "<script>alert(1)</script>", "9" * 400, "-1", "1e9", "NaN", "2026-02-30", "2026-02-30T00:00:00Z", "null", "[]", "{}", "'\"><", "\r\n\r\nX: y", "001_" + "a" * 5000]
RECORDS = [json.dumps(x) for x in ({"excerpt": 123}, {"kind": [], "form": {}, "accession": None, "url": 5, "filed_at": [], "available_as_of": {}, "excerpt": [], "source_hash": 1, "fictional": "yes", "rights": None},
           {"kind": "filing", "form": "x", "accession": "0000000000-26-000077", "url": None, "filed_at": "2026-01-01", "available_as_of": "2026-01-01T00:00:00Z", "excerpt": "e", "source_hash": "zz", "fictional": True, "rights": "FICTIONAL"}, 1, "s", None, True)]


class TestRouteFuzz(unittest.TestCase):
    def test_no_route_drops_the_connection(self):
        S.Handler.log_message = lambda *a, **k: None
        srv = S.WorkbenchServer(pathlib.Path(tempfile.mkdtemp(prefix="wb-fuzz-")) / "ws", 0); threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            c = Client(srv.server_address[1])
            self.assertEqual(c.post("/source/register", _src("0000000000-26-000001", "2026-02-10", "2026-02-10T21:05:00Z", "passage one"))[0], 303)
            self.assertEqual(c.post("/claim/freeze", dict(CLAIM, source_id=c.sid("0000000000-26-000001")))[0], 303); cid = CLAIM["claim_id"]
            routes = {"/source/register": ["kind", "form", "accession", "url", "filed_at", "available_as_of", "observed_at", "excerpt", "rights"], "/source/import": ["record", "record_observed_at"],
                      "/claim/freeze": ["claim_id", "issuer_cik", "range_low", "range_high", "scale_as_stated", "currency", "basis", "fp_start", "fp_type", "source_id", "resolution_rule"],
                      f"/claim/{cid}/amend": ["amend_type", "range_low", "basis", "fp_end", "source_id", "reason"], f"/claim/{cid}/outcome": ["actual", "currency", "fp_start", "source_id"],
                      f"/claim/{cid}/adjudicate": ["reviewer", "label", "evidence", "reason"], f"/claim/{cid}/note": ["category", "actor", "version_ref", "supersedes_note", "evidence", "reason"],
                      "/sci/replay": ["example", "claim_id", "actor", "input"], "/fixtures/load": ["fixture"], "/claim/NOPE/amend": ["reason"]}
            problems = []
            for path, fields in routes.items():
                for f in fields:
                    for w in (RECORDS if f == "record" else WEIRD):
                        try:
                            st, _, page = c.post(path, {f: w})
                        except Exception as exc:                                       # a dropped connection = an unhandled exception in the handler
                            problems.append((path, f, w[:24], repr(exc)[:80])); continue
                        if st not in (303, 422, 404, 400, 403, 413):
                            problems.append((path, f, w[:24], st))
                        if st == 422 and b"nothing was written" not in page:
                            problems.append((path, f, w[:24], "422 without 'nothing was written'"))
            for q in ("/source?as_of=" + "9" * 300, "/claim/" + "A" * 200, "/claim/%00", "/sci/S99999", "/exports/exp-0000000000000000.zip", f"/claim/{cid}?as_of=2026-02-30T00:00:00Z", f"/claim/{cid}?as_of=%F0%9F%99%82"):
                try:
                    st = c.req("GET", q)[0]
                except Exception as exc:
                    problems.append((q, repr(exc)[:80])); continue
                if st not in (200, 404, 400):
                    problems.append((q, st))
            self.assertEqual(problems, [])
            self.assertEqual(srv.ws.status()["integrity"], "OK")
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
