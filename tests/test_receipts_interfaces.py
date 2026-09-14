"""V7-004-V1 interface checks: the REST route and MCP tool reach the same loader and refuse synthetic
boards; check-claim's shipped command wires support_limits. Uses the real handlers with a local test
client; no listener, no DB (scoreboard path needs none)."""
import contextlib, io, json, os, pathlib, sys, tempfile, unittest
REPO = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(REPO))
from v3.receipts import scoreboard  # noqa: E402


class Interfaces(unittest.TestCase):
    def test_rest_route_reads_shared_loader(self):
        from fastapi.testclient import TestClient
        from v3.api import server
        board_path = REPO / "docs" / "receipts" / "scoreboard.json"
        with TestClient(server.app) as c:
            r = c.get("/v1/receipts/scoreboard"); self.assertEqual(r.status_code, 200); body = r.json()
            self.assertIn("columns", body); self.assertFalse(body.get("synthetic", True)); self.assertEqual(body["columns"]["replications"]["attempts"], 0)
            self.assertEqual(body["columns"]["replications"]["program_evidence_legacy"]["entries"], 1)
            shared = scoreboard.load_public(board_path); self.assertEqual(body["columns"], shared["columns"])          # same derived file, same loader
    def test_mcp_tool_reads_shared_loader(self):
        from v3.mcp import server as mcp_server
        tool = mcp_server.get_evidence_scoreboard
        fn = getattr(tool, "fn", None) or getattr(tool, "__wrapped__", None) or tool
        body = fn(); self.assertIn("columns", body); self.assertFalse(body.get("synthetic", True))
        self.assertEqual(body["columns"], scoreboard.load_public(REPO / "docs/receipts/scoreboard.json")["columns"])
    def test_public_loader_refuses_synthetic_board_for_both_surfaces(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "scoreboard.json"; p.write_text(json.dumps(scoreboard.build(pathlib.Path(d) / "s", synthetic=True)))
            self.assertIsNone(scoreboard.load_public(p))
    def test_check_claim_shipped_command_emits_support_limits(self):
        from v3.cli import check_claim
        out = io.StringIO()
        with contextlib.redirect_stdout(out): rc = check_claim.main(["--text", "the sky is blue"])
        doc = json.loads(out.getvalue()); self.assertEqual(doc["status"], "NOT_PARSEABLE"); self.assertEqual(doc["support_limits"]["research_interpretation"], "NONE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
