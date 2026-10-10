"""`brief selftest` — a bounded self-check of the INSTALLED package in a temporary fictional workspace (no pytest, no
repository files): compose the acceptance brief, inspect it, edit it with a protected-fact change, translate it, export a
packet, verify the packet in a second fresh workspace, and refuse hostile inputs. Prints one line per check; exit 0 when
every check passes, 1 otherwise. It checks this installation, not the development test suite."""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from v8.workbench import store
from v8.workbench.server import load_fixture
from v9.brief import compose, contracts, finance, packet, reducer, reports, templates
from v9.brief.sidecar import Sidecar


def main(as_json: bool = False) -> int:
    checks = []
    def ok(name, cond, note=""):
        checks.append({"check": name, "ok": bool(cond), "note": note}); return bool(cond)
    tmp = Path(tempfile.mkdtemp(prefix="yuclaw-brief-selftest-"))
    try:
        ws = store.Workspace(tmp / "research"); sc = Sidecar(ws)
        cid = load_fixture(ws, "001_base"); ok("fixture loaded (fictional)", cid.endswith("--FIX-COMMIT-001-base"), cid)
        rec, dup = compose.create_from_template(ws, sc, claim_id=cid, sections=list(templates.TEMPLATES), lang="en", op_id="selftest:create-0001", actor="selftest")
        bid = rec["brief_id"]; view = reducer.brief_view(ws, sc, bid, None, "en")
        s3 = view["statements"][2]["substantive_support"]["calculation"]
        ok("acceptance arithmetic: midpoints 115/110 million, change -5 million, -4.35%", s3["midpoint_original"] == 115000000 and s3["midpoint_revised"] == 110000000 and s3["absolute_change"] == -5000000 and s3["relative_change"]["value_percent"] == "-4.35")
        ok("both containments IN_RANGE", view["statements"][3]["substantive_support"]["calculation"]["original"]["result"] == "IN_RANGE" and view["statements"][3]["substantive_support"]["calculation"]["revised"]["result"] == "IN_RANGE")
        ok("demand-collapse sentence stays UNRESOLVED", any(s["role"] == "unresolved_claim" and s["substantive_support"]["status"] == "UNRESOLVED" for s in view["statements"]))
        ok("every statement byte-bound", all(s["byte_integrity"]["status"] == "VERIFIED" for s in view["statements"]))
        rec2, _ = compose.create_from_template(ws, sc, claim_id=cid, sections=list(templates.TEMPLATES), lang="en", op_id="selftest:create-0001", actor="selftest")
        ok("retry with the same op_id is a duplicate, not a second brief", _ and rec2["record_hash"] == rec["record_hash"])
        text = sc.get_bytes(rec["payload"]["text_view"]["view_sha256"]).decode()
        edited = text.replace("USD 110–120 million in its 8-K", "CAD 110–120 million in its 8-K")
        rec3, _ = compose.revise(ws, sc, brief_id=bid, parent_version_id="B1", text=edited.encode(), kind="edit", lang_to=None, actor="selftest", provenance="selftest", op_id="selftest:edit-0001")
        v2 = reducer.brief_view(ws, sc, bid, "B2", "en")
        ok("protected-fact change (USD→CAD) invalidates the statement and opens review items", v2["statements"][0]["substantive_support"]["status"] == "INVALIDATED" and v2["open_review_items"] >= 2)
        ok("parent version preserved", reducer.brief_view(ws, sc, bid, "B1", "en")["text"] == text)
        rec4, _ = compose.retranslate_template(ws, sc, brief_id=bid, parent_version_id="B1", lang_to="fr", actor="selftest", op_id="selftest:tr-0001")
        v3 = reducer.brief_view(ws, sc, bid, "B3", "fr")
        ok("deterministic French edition binds every statement", len(v3["statements"]) == len(view["statements"]) and all(s["byte_integrity"]["status"] == "VERIFIED" for s in v3["statements"]) and "−4,35 %" in v3["text"])
        # hostile inputs
        fr_bytes = v3["text"].encode("utf-8"); cont = next(i for i, b in enumerate(fr_bytes) if (b & 0xC0) == 0x80)      # the first continuation byte of a multi-byte character
        try:
            compose.link_span(ws, sc, brief_id=bid, version_id="B3", start=cont, end=cont + 2, role="analyst_interpretation", claim_id=None, version_ref=None, actor="selftest", note="", op_id="selftest:link-bad")
            ok("offset inside a multi-byte UTF-8 sequence refused", False)
        except Exception as exc:
            ok("offset inside a multi-byte UTF-8 sequence refused", "UTF-8" in str(exc) or "inside" in str(exc), str(exc)[:80])
        bad = json.dumps({"schema": contracts.DETECTION_REPORT, "execution": "FAILED", "signal": "NOT_DETECTED", "calibration": "APPLICABLE", "detector": "x", "view_sha256": "0" * 64, "span": {"start": 0, "end": 1, "span_sha256": "0" * 64}, "origin": "operator_assertion", "observed_at": "2026-10-01T00:00:00Z"}).encode()
        try:
            reports.import_record(ws, sc, kind="report", data=bad, actor="selftest", op_id="selftest:rep-bad")
            ok("FAILED + NOT_DETECTED + APPLICABLE report refused", False)
        except Exception as exc:
            ok("FAILED + NOT_DETECTED + APPLICABLE report refused", "cannot become" in str(exc) or "APPLICABLE" in str(exc), str(exc)[:100])
        try:
            reports.parse_import(b'{"a":1,"a":2}'); ok("duplicate JSON keys refused", False)
        except Exception as exc:
            ok("duplicate JSON keys refused", "DUPLICATE" in str(exc))
        # export + verify in a fresh workspace
        r = packet.build_packet(ws, sc, bid, "B1", op_id="selftest:exp-0001")
        fresh = Sidecar(store.Workspace(tmp / "fresh"))
        res = packet.verify_packet(r["zip_path"], receiver=fresh)
        ok("packet verifies SUCCESS in a fresh workspace", res["result"] == "SUCCESS", json.dumps(res.get("outcome_counts")))
        with zipfile.ZipFile(r["zip_path"]) as z:
            names = z.namelist(); htm = z.read("brief.html"); rj = z.read("records.json") + z.read("brief.json") + z.read("appendix.md")
        ok("packet carries no private material or local paths", not any("private" in n or n.endswith(".pem") for n in names) and b"<script" not in htm.lower() and str(tmp).encode() not in rj)
        raw = Path(r["zip_path"]).read_bytes(); i = raw.find(b"Management cut guidance")
        if i > 0:
            tampered = bytearray(raw); tampered[i] ^= 0x01
        else:
            with zipfile.ZipFile(r["zip_path"]) as z:
                members = {n: z.read(n) for n in z.namelist()}
            tname = next(n for n in members if n.startswith("text/")); members[tname] = members[tname][:-1] + bytes([members[tname][-1] ^ 1])
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z2:
                for n, b in members.items():
                    z2.writestr(n, b)
            tampered = buf.getvalue()
        tp = tmp / "tampered.zip"; tp.write_bytes(bytes(tampered))
        ok("one-byte tampering is detected", packet.verify_packet(tp, receiver=fresh)["result"] != "SUCCESS")
        ok("v8 journal untouched by v9 writes", all(e["kind"] in store.KINDS for e in ws.load()["events"]) and (tmp / "research" / "v9" / "brief.jsonl").is_file())
        ok("relative change rounding rule stated", finance.ROUNDING["rule"] == "ROUND_HALF_EVEN" and finance.ROUNDING["decimals"] == 2)
    except Exception as exc:
        checks.append({"check": "selftest ran to completion", "ok": False, "note": f"{exc.__class__.__name__}: {exc}"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    passed = sum(1 for c in checks if c["ok"]); total = len(checks)
    if as_json:
        print(json.dumps({"result": "PASS" if passed == total else "FAIL", "passed": passed, "total": total, "checks": checks,
                          "not_run_here": "the repository test suite, the browser journeys, live provider connectors (none exist in 9.0), real sources"}, indent=1))
    else:
        for c in checks:
            print(f"  [{'ok' if c['ok'] else 'FAIL'}] {c['check']}" + (f" — {c['note']}" if c["note"] and not c["ok"] else ""))
        print(f"  not run here: the repository test suite (developers: python -m pytest tests/test_v9_*.py), the browser journeys, live provider connectors (none exist in 9.0), real sources")
        print(f"[brief selftest] {'PASS' if passed == total else 'FAIL'} — {passed}/{total} checks")
    return 0 if passed == total else 1
