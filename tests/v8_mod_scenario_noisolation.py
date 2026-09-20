"""Scenario run UNDER tests/v8_mod_oldkernel.py: a host whose kernel offers no Landlock and that has no bubblewrap. Prints one
JSON object. Fictional data, temporary principals. The product code is imported and used exactly as shipped."""
import json, pathlib, subprocess, sys, tempfile
from datetime import timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from v8_mod_helpers import Client, Server, bundle, load_fixture, principal, workspace       # noqa: E402
from v8.workbench.modules import commons as com, core, evolution as evo, modexport as mx, practice as prc, sandbox, shield   # noqa: E402

out = {}; cap = sandbox.capability(); out["backend"] = cap["backend"]; out["closed_reason"] = cap["closed_reason"]; out["probe_reasons"] = {p["backend"]: p.get("reason") for p in cap["probes"]}
ws = workspace("noiso"); cid, sid = load_fixture(ws); adm, acred = principal(ws, "owner", ["admin"]); al, lcred = principal(ws, "alice", ["submit"], by=adm); rita, _ = principal(ws, "rita", ["review"], by=adm); pat, _ = principal(ws, "pat", ["practice"], by=adm)
shield.enroll_root(ws, adm, label="root", op_id="op:root-000001"); data, h, srcs = bundle(); sub = shield.submit(ws, al, data, title="t", op_id="op:sub-000001")["payload"]["submission_id"]
future = (core.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"); shield.issue_approval(ws, adm, bundle_sha256=h, source_sha256s=srcs, purpose="evidence.reference", expires_at=future, op_id="op:apr-000001")
d = shield.admit(ws, al, sub, op_id="op:admit-00001")["payload"]; out["decision"] = {k: d.get(k) for k in ("result", "code", "byte_integrity", "authority_approval")}
try:
    com.set_budget(ws, adm, period_id="p1", review_minutes=60, practice_minutes=60, contributor_packet_cap=5, max_open_tasks=5, op_id="op:budget-001")
    out["intake_of_the_refused_decision"] = "ACCEPTED"; com.intake_from_shield(ws, al, d["decision_id"], op_id="op:intake-0001")
except core.ModuleError as exc:
    out["intake_of_the_refused_decision"] = exc.code
g = com.submit_direct(ws, al, claim_id=cid, kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=10, asserts_withdrawn=False, client_packet_id=None, op_id="op:pk-0000001")["payload"]["group_id"]
com.assign(ws, rita, g, op_id="op:assign-0001"); com.work(ws, rita, g, "start", note="", op_id="op:work-00001"); com.work(ws, rita, g, "finish", note="reviewed the fictional packet", op_id="op:work-00002"); out["com_task"] = com.state(ws)["groups"][g]["state"]
t = prc.freeze_task(ws, rita, title="t", question="q?", claim_id=cid, source_ids=[sid], labels=["A", "B"], reference_label="A", reference_answer="REF", rationale="", provenance="MODEL_ANSWER", declared_curator_qualification="",
                    public_example=True, session_minutes=5, evo_version_id=None, op_id="op:task-00001")["payload"]["task_id"]
ss = prc.open_session(ws, pat, task_id=t, assistance="NONE", assistance_note="", prior_exposure="NOT_SEEN", op_id="op:sess-00001")["payload"]["session_id"]
prc.commit_attempt(ws, pat, ss, judgment="A", reasoning="because", source_refs=[sid], unresolved_note="", op_id="op:attempt-001"); out["prc_reveal"] = prc.reveal(ws, pat, ss)["reference_answer"]
root = pathlib.Path(tempfile.mkdtemp(prefix="v16-evo-")); (root / "data").mkdir(); (root / "data" / "d.json").write_text("{}")
comp = {k: {"mode": "not_applicable", "justification": "not part of this demonstration"} for k in evo.COMPONENTS}; comp["data"] = {"mode": "path", "path": str(root / "data")}
evo.set_config(ws, adm, {"roots": [str(root)], "components": comp, "depends_on": {}, "protocols": {"data-only": {"scope": ["data"], "job": "json_wellformed"}}, "authority": {}}, op_id="op:evo-config1")
evo.register_version(ws, al, version_id="v1", parent_version_id=None, label="v1", op_id="op:evo-reg-v1"); out["evo_evaluation"] = evo.run_evaluation(ws, rita, version_id="v1", protocol_id="data-only", op_id="op:evo-run-001")["payload"]["result"]
pk = pathlib.Path(mx.build_packet(ws, adm, modules=["SHD", "COM", "EVO"], prc_sessions=[ss], withhold_text=False, op_id="op:export-0001")["zip_path"]).read_bytes(); out["fresh_receiver_verification"] = mx.verify_packet(workspace("noiso-recv"), pk)["result"]
srv = Server(ws.root); c = Client(srv); c.login("owner", acred); st, setup, _ = c.get("/setup"); out["setup_page"] = {"status": st, "names_the_closed_route": "REFUSED_ISOLATION_UNAVAILABLE" in setup or "no isolation backend passed" in setup}
st, page, _ = c.get(f"/shd/decision/{d['decision_id']}"); out["decision_page"] = {"status": st, "shows_code": "REFUSED_ISOLATION_UNAVAILABLE" in page}; out["pages"] = {u: c.get(u)[0] for u in ("/modules", "/shd", "/shd/trust", "/evo", "/com", "/prc", "/modx", "/help")}; srv.close()
cli = subprocess.run([sys.executable, "-m", "v8.workbench", "modules", "--workspace", str(ws.root)], cwd=str(pathlib.Path(__file__).resolve().parents[1]), capture_output=True, text=True, timeout=120)
out["cli_modules"] = {"rc": cli.returncode, "isolation_backend": json.loads(cli.stdout)["isolation_backend"] if cli.returncode == 0 else cli.stderr[-300:]}
print(json.dumps(out))
