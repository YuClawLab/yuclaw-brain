"""`python -m v8.workbench selftest` / `yuclaw workbench selftest` — a bounded self-check that runs FROM THE INSTALLED PACKAGE.

8.0.0's selftest started pytest on repository test files: neither pytest nor those files are in the distribution, so
the documented command failed on every fresh installation. This check needs nothing outside the package. It uses the
REAL code — the loopback server and its guards, the packaged fictional fixtures, the calculator, the export builder and
the verifier — in a TEMPORARY workspace that is removed afterwards, and it compares what the product computes with the
results the fixtures record, so it is not a demonstration that prints "ok".

What it does NOT do: it is not the repository test suite (developers: `python -m pytest tests` in a checkout), it starts
no browser, it touches no real workspace, and it never claims that protected SHD admission works where no isolation
backend passed its live probe — there it reports the route as CLOSED and checks that it really is closed. With
`--require-isolation` a missing backend is a FAILURE, never a skip.
"""
from __future__ import annotations

import hashlib
import http.client
import io
import json
import platform
import re
import shutil
import tempfile
import threading
import urllib.parse
import zipfile
from pathlib import Path

from v8.workbench import NOT_ADVICE, export

RESOURCES = Path(__file__).resolve().parent / "resources"
FIXTURES = ("001_base", "006_out_of_range", "004_incompatible_basis")


class _Client:
    """The smallest honest browser: cookie, CSRF token and Origin, over real loopback HTTP."""

    def __init__(self, port: int):
        self.port, self.cookie, self.csrf = port, None, None

    def req(self, method, path, body=None, headers=None):
        h = {"Host": f"127.0.0.1:{self.port}"}; h.update(headers or {})
        if self.cookie:
            h["Cookie"] = self.cookie
        if method == "POST":
            h.setdefault("Origin", f"http://127.0.0.1:{self.port}")
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            c.request(method, path, body=body, headers=h); r = c.getresponse(); data = r.read(); hdr = dict(r.getheaders())
        finally:
            c.close()
        if "Set-Cookie" in hdr:
            self.cookie = hdr["Set-Cookie"].split(";")[0]
        m = re.search(rb'name="csrf" value="([0-9a-f]+)"', data)
        if m:
            self.csrf = m.group(1).decode()
        return r.status, hdr, data

    def post(self, path, fields, op_id):
        return self.req("POST", path, urllib.parse.urlencode(dict(fields, csrf=self.csrf, op_id=op_id)), {"Content-Type": "application/x-www-form-urlencoded"})

    def upload(self, op_id, data: bytes):
        bd = "----yuclawselftest"; out = io.BytesIO()
        for k, v in (("csrf", self.csrf), ("op_id", op_id)):
            out.write(f"--{bd}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
        out.write(f"--{bd}\r\nContent-Disposition: form-data; name=\"packet\"; filename=\"x.zip\"\r\nContent-Type: application/zip\r\n\r\n".encode()); out.write(data); out.write(f"\r\n--{bd}--\r\n".encode())
        return self.req("POST", "/verify", out.getvalue(), {"Content-Type": f"multipart/form-data; boundary={bd}"})


def _serve(root: Path):
    from v8.workbench import server as S
    srv = S.WorkbenchServer(root, 0, candidate_commit="selftest"); srv.RequestHandlerClass.log_message = lambda *a, **k: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _bundle(files: dict, evidence_override: dict | None = None) -> tuple[bytes, str]:
    ev = [{"path": p, "sha256": (evidence_override or {}).get(p) or hashlib.sha256(b).hexdigest(), "size": len(b)} for p, b in sorted(files.items())]
    man = {"schema": "yuclaw.shd-bundle/1", "purpose": "evidence.reference", "title": "selftest (fictional)", "evidence": ev, "payload": {}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("bundle.json", json.dumps(man))
        for p, b in files.items():
            z.writestr(p, b)
    return buf.getvalue(), hashlib.sha256(buf.getvalue()).hexdigest()


def run(require_isolation: bool = False) -> dict:
    """{'result': PASS|FAIL, 'checks': [{'name','ok','detail'}], 'isolation': {...}, 'ran': [...], 'not_run': [...]}"""
    checks: list[dict] = []
    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:300]}); return bool(ok)
    tmp = Path(tempfile.mkdtemp(prefix="yuclaw-selftest-")); servers = []; iso: dict = {}
    try:
        man = json.loads((RESOURCES / "fixtures" / "manifest.json").read_text(encoding="utf-8"))
        bad = [f["path"].rsplit("/", 1)[-1] for f in man["files"] if hashlib.sha256((RESOURCES / "fixtures" / f["path"].rsplit("/", 1)[-1]).read_bytes()).hexdigest() != f["sha256"]]
        check("packaged fixtures equal their recorded digests", not bad and man.get("fictional") is True, f"{len(man['files'])} fictional fixtures; mismatching: {bad}")
        a = _serve(tmp / "research"); servers.append(a); ca = _Client(a.server_address[1]); st, hdr, _ = ca.req("GET", "/")
        check("server binds loopback only and sends its security headers", a.server_address[0] == "127.0.0.1" and st == 200 and "default-src 'none'" in hdr.get("Content-Security-Policy", "") and hdr.get("X-Frame-Options") == "DENY", a.server_address[0])
        st, _, _ = ca.req("POST", "/fixtures/load", urllib.parse.urlencode({"fixture": "001_base", "csrf": "0" * 32, "op_id": "selftest:bad-csrf"}), {"Content-Type": "application/x-www-form-urlencoded"})
        guard_csrf = st == 403 and not a.ws.load()["events"]
        st, _, _ = ca.req("POST", "/fixtures/load", urllib.parse.urlencode({"fixture": "001_base", "csrf": ca.csrf, "op_id": "selftest:bad-origin"}), {"Content-Type": "application/x-www-form-urlencoded", "Origin": "http://evil.example"})
        check("a write without a valid CSRF token or from another Origin is refused and writes nothing", guard_csrf and st == 403 and not a.ws.load()["events"], f"status {st}")
        claim_ids = {}
        for fid in FIXTURES:
            fx = json.loads((RESOURCES / "fixtures" / f"{fid}.json").read_text(encoding="utf-8")); st, hdr, _ = ca.post("/fixtures/load", {"fixture": fid}, f"selftest:load:{fid}")
            cid = urllib.parse.unquote(hdr.get("Location", "").rsplit("/", 1)[-1]); claim_ids[fid] = (cid, fx["expected"])
            check(f"fixture {fid} loads through the real form route", st == 303 and cid.endswith(fx["fixture_id"]), f"status {st}")
        n = len(a.ws.load()["events"]); ca.post("/fixtures/load", {"fixture": "001_base"}, "selftest:load:again")
        check("loading the same fixture again appends nothing (operation identifiers are idempotent)", len(a.ws.load()["events"]) == n, f"{n} events")
        for fid, (cid, expected) in claim_ids.items():
            r = export.build_export(a.ws, cid, candidate_commit="selftest"); v = export.verify_export(r["zip_path"]); rec = v.get("recompute") or {}
            got = json.dumps(rec, sort_keys=True)
            if expected.get("comparison_permitted") is False:
                check(f"{fid}: an incompatible comparison stays refused, and its export verifies", v["result"] == "SUCCESS" and expected["adjudication"] in got, f"expected {expected['adjudication']}; verify {v['result']}")
            else:
                check(f"{fid}: the computed result equals the fixture's recorded result ({expected['adjudication']}) and its export verifies", v["result"] == "SUCCESS" and expected["adjudication"] in got, f"verify {v['result']}; {v.get('first_discrepancy')}")
        cid = claim_ids["001_base"][0]; good = Path(export.build_export(a.ws, cid, candidate_commit="selftest")["zip_path"]).read_bytes()
        b = _serve(tmp / "fresh"); servers.append(b); cb = _Client(b.server_address[1]); cb.req("GET", "/verify")
        st, _, page = cb.upload("selftest:verify:good", good)
        check("the export verifies in a second, fresh workspace over HTTP", st == 200 and b">SUCCESS<" in page and b"IN_RANGE" in page, f"status {st}")
        tampered = tmp / "tampered.zip"; zin = zipfile.ZipFile(io.BytesIO(good)); buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for i in zin.infolist():
                d = zin.read(i); zout.writestr(i, d.replace(b"110000000", b"110000001") if i.filename == "canonical.json" else d)
        tampered.write_bytes(buf.getvalue()); v = export.verify_export(tampered)
        check("a packet with one changed figure is rejected", v["result"] != "SUCCESS", f"{v['result']}: {v.get('first_discrepancy')}")
        st, _, page = cb.upload("selftest:verify:good", b"different bytes under the same operation identifier")
        check("an operation identifier reused with different content is a 409 refusal, and the server keeps serving", st == 409 and b"Nothing was written" in page and cb.req("GET", "/")[0] == 200, f"status {st}")
        log = a.ws.log.read_bytes(); a.ws.log.write_bytes(log.replace(b"Fictional", b"Fictionel", 1)); st, _, page = ca.req("GET", "/")
        check("an edited journal is refused (the workspace fails closed)", b"fails its chain check" in page or st != 200, f"status {st}"); a.ws.log.write_bytes(log)
        # ---- protected intake (SHD): the restricted worker, or a verified CLOSED route
        from v8.workbench.modules import core, sandbox
        cap = sandbox.capability(refresh=True); iso = {"platform": f"{platform.system()} {platform.machine()}", "backend": cap["backend"], "closed_reason": cap.get("closed_reason"),
                                                        "probes": [{k: p.get(k) for k in ("backend", "available", "reason")} for p in cap["probes"]]}
        data, sha = _bundle({"evidence/note.txt": b"fictional selftest evidence\n"}); staged = tmp / "bundle.zip"; staged.write_bytes(data)
        if cap["backend"]:
            out = sandbox.run_worker(staged, sha)
            check(f"SHD: the restricted worker ({cap['backend']}) passed its live denial probes and verified a fictional bundle", out.get("code") == "OK" and out.get("bundle_sha256") == sha, cap["backend"])
            bad_data, bad_sha = _bundle({"evidence/note.txt": b"fictional selftest evidence\n"}, {"evidence/note.txt": "0" * 64}); (tmp / "bad.zip").write_bytes(bad_data)
            try:
                bad = sandbox.run_worker(tmp / "bad.zip", bad_sha); refused = bad.get("result") == "REJECTED" and bad.get("code") == "EVIDENCE_DIGEST_MISMATCH"; why = bad.get("code")
            except core.ModuleError as exc:
                refused, why = True, exc.code
            check("SHD: a bundle whose evidence digest is wrong is rejected by the worker", refused, why)
            iso["shd_admission_route"] = "OPEN on this host (worker verified; an admission still needs an administrator's signed approval)"
        else:
            try:
                sandbox.run_worker(staged, sha); closed = False
            except core.ModuleError as exc:
                closed = exc.code == "E_ISOLATION_UNAVAILABLE"
            iso["shd_admission_route"] = "CLOSED on this host: no isolation backend passed its live probe. Nothing was admitted and nothing is claimed; supported isolation is Linux with Landlock."
            check("SHD: with no verified isolation backend the protected route is CLOSED (fail-closed), not skipped", closed, cap.get("closed_reason"))
            if require_isolation:
                check("--require-isolation: a verified isolation backend is present", False, "none passed its live probe on this host; this is a failure, not a skip")
    except Exception as exc:                     # noqa: BLE001 — a selftest reports its own crash as a failed check
        check("selftest completed without an internal error", False, f"{type(exc).__name__}: {exc}")
    finally:
        for s in servers:
            s.shutdown(); s.server_close()
        shutil.rmtree(tmp, ignore_errors=True)
    check("temporary selftest state was removed", not tmp.exists(), str(tmp))
    return {"record": "yuclaw-workbench-selftest/1", "result": "PASS" if all(c["ok"] for c in checks) else "FAIL", "checks": checks, "isolation": iso,
            "ran": "packaged fixtures, loopback server guards, fixture loading, idempotence, calculator vs recorded results, export + verification (library and HTTP, fresh workspace), tamper rejection, operation-conflict refusal, journal fail-closed, SHD worker or verified closed route",
            "not_run": "the repository test suite (developers: `python -m pytest tests` in a checkout), the browser journeys, the COM/PRC/EVO workflows, real sources", "not_advice": NOT_ADVICE}


def main(as_json: bool = False, require_isolation: bool = False) -> int:
    r = run(require_isolation)
    if as_json:
        print(json.dumps(r, indent=1))
    else:
        for c in r["checks"]:
            print(f"  [{'ok' if c['ok'] else 'FAIL'}] {c['name']}" + (f" — {c['detail']}" if not c["ok"] and c["detail"] else ""))
        print(f"  isolation: {r['isolation'].get('platform')} · backend {r['isolation'].get('backend')} · {r['isolation'].get('shd_admission_route', 'not reached')}")
        print(f"  not run here: {r['not_run']}")
        print(f"[selftest] {r['result']} — {sum(c['ok'] for c in r['checks'])}/{len(r['checks'])} checks")
    return 0 if r["result"] == "PASS" else 1
