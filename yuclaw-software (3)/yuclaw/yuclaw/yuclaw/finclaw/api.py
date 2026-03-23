"""FINClaw REST API — serves real signals to external clients."""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, os
from datetime import datetime
from pathlib import Path

OUTPUT = Path(os.path.expanduser("~/yuclaw/output"))


class FINClawAPI(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _load(self, name):
        try:
            return json.load(open(OUTPUT / f"{name}.json"))
        except:
            return None

    def _respond(self, data, status=200):
        body = json.dumps({"data": data, "timestamp": datetime.now().isoformat(),
                           "source": "YUCLAW Engine", "is_real": True}, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        routes = {
            "/": lambda: {"status": "FINClaw API", "endpoints": ["/regime", "/signals", "/strategies", "/risk", "/factors"]},
            "/regime": lambda: self._load("macro_sector_latest"),
            "/signals": lambda: {"buy": [r for r in (self._load("screener_latest") or []) if r["signal"] in ("STRONG_BUY", "BUY")][:10],
                                 "sell": [r for r in (self._load("screener_latest") or []) if r["signal"] in ("STRONG_SELL", "SELL")][:5]},
            "/strategies": lambda: sorted(self._load("backtest_all") or [], key=lambda x: x["calmar"], reverse=True),
            "/risk": lambda: self._load("risk_analysis"),
            "/factors": lambda: (self._load("factor_scan_full") or [])[:20],
        }
        handler = routes.get(self.path)
        self._respond(handler() if handler else {"error": "Not found"}, 200 if handler else 404)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), FINClawAPI)
    print("FINClaw API at http://localhost:8080 — /regime /signals /strategies /risk /factors")
    server.serve_forever()
