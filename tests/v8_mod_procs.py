"""Child-process entry points for the V8-016 cross-process and crash tests. Every function here runs in its OWN interpreter
process (multiprocessing 'spawn', or `python -c`), opens the workspace from disk and authenticates with a credential — the
parent test only synchronizes it through OS-level barriers and events and reads the durable state afterwards.
Fictional data and temporary principals only."""
import json, os, pathlib, signal, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1])); sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


def _open(root, pid, cred):
    from v8.workbench import store
    from v8.workbench.modules import authz
    ws = store.Workspace(root); return ws, authz.Principals(ws).authenticate(pid, cred)


def _code(fn):
    from v8.workbench.modules.core import ModuleError
    try:
        return "OK", fn()
    except ModuleError as exc:
        return exc.code, None


def assign(root, pid, cred, gid, op, barrier, q):
    from v8.workbench.modules import commons
    ws, p = _open(root, pid, cred); barrier.wait(60); c, _ = _code(lambda: commons.assign(ws, p, gid, op_id=op)); q.put((pid, gid, c))


def submit_packet(root, pid, cred, claim_id, op, barrier, q):
    from v8.workbench.modules import commons
    ws, p = _open(root, pid, cred); barrier.wait(60)
    c, _ = _code(lambda: commons.submit_direct(ws, p, claim_id=claim_id, kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=10, asserts_withdrawn=False, client_packet_id=None, op_id=op)); q.put((pid, c))


def admit(root, pid, cred, sid, op, barrier, after_worker, revoked, q):
    """`after_worker`/`revoked` given: the REAL worker runs, then this process waits until the other process has revoked the
    approval, and only then reaches the commit. Without them: a free race from the barrier."""
    from v8.workbench.modules import sandbox, shield
    ws, p = _open(root, pid, cred)
    if after_worker is not None:
        real = sandbox.run_worker

        def held(staged, digest):
            out = real(staged, digest); after_worker.set(); revoked.wait(60); return out
        sandbox.run_worker = held
    barrier.wait(60); c, ev = _code(lambda: shield.admit(ws, p, sid, op_id=op)); q.put(("admit", c, ev["payload"]["code"] if ev else None))


def revoke(root, pid, cred, approval_id, op, barrier, after_worker, revoked, q):
    from v8.workbench.modules import shield
    ws, p = _open(root, pid, cred); barrier.wait(60)
    if after_worker is not None:
        after_worker.wait(60)
    c, _ = _code(lambda: shield.revoke_approval(ws, p, approval_id, "raced by another process", op_id=op))
    if revoked is not None:
        revoked.set()
    q.put(("revoke", c, None))


def attempt(root, pid, cred, session, judgment, refs, op, barrier, q):
    from v8.workbench.modules import practice
    ws, p = _open(root, pid, cred); barrier.wait(60)
    c, _ = _code(lambda: practice.commit_attempt(ws, p, session, judgment=judgment, reasoning=f"reasoning of {judgment}", source_refs=refs, unresolved_note="", op_id=op)); q.put(("attempt", judgment, c))


def reveal(root, pid, cred, session, barrier, q):
    from v8.workbench.modules import practice
    ws, p = _open(root, pid, cred); barrier.wait(60); c, r = _code(lambda: practice.reveal(ws, p, session)); q.put(("reveal", (r or {}).get("reference_answer"), c))


def hammer(path, a_hex, b_hex, stop, started):
    """Rewrite the staged file IN PLACE, alternating two complete same-size contents, until told to stop."""
    a, b = bytes.fromhex(a_hex), bytes.fromhex(b_hex); assert len(a) == len(b); n = 0; started.set()
    while not stop.is_set():
        with open(path, "r+b") as f:
            f.write(b if n % 2 == 0 else a); f.flush()
        n += 1
    with open(path, "r+b") as f:
        f.write(a)


def verify_loop(path, expected_sha, expected_evidence, rounds, q):
    """Run the REAL restricted worker on a file another process keeps rewriting; validate each result the way the parent does."""
    from v8.workbench.modules import core, sandbox, shield_worker
    backend = sandbox.capability()["backend"]; seen = {"accepted_expected": 0, "rejected_or_failed": 0, "ACCEPTED_OTHER_BYTES": 0}
    for _ in range(rounds):
        r = sandbox._run(backend, "verify", pathlib.Path(path))
        try:
            obj = shield_worker.validate_result(core.strict_json(r["stdout"], max_bytes=sandbox.MAX_STDOUT, code="WORKER_OUTPUT"), expected_sha)
            same = obj["bundle_sha256"] == expected_sha and sorted(e["sha256"] for e in obj["evidence"]) == sorted(expected_evidence)
            seen["accepted_expected" if same else "ACCEPTED_OTHER_BYTES"] += 1
        except Exception:                                                      # noqa: BLE001 - torn, other or rejected bytes never validate
            seen["rejected_or_failed"] += 1
            try:
                why = json.loads(r["stdout"]).get("code", "OTHER_BYTES_REPORTED")
            except ValueError:
                why = f"worker rc {r['rc']} {r['status']}"
            seen.setdefault("why", {}); seen["why"][why] = seen["why"].get(why, 0) + 1
    q.put(seen)


def stale_form(root, pid, cred, claim_id, captured, amended, q):
    """A real server process: show the form (capturing the claim version it names), wait for ANOTHER process to amend the
    claim, then submit the captured form."""
    import re
    from v8_mod_helpers import Client, Server
    srv = Server(root); c = Client(srv); c.login(pid, cred); html_ = c.get(f"/com?claim={claim_id}")[1]
    ref = re.search(r'value="(' + re.escape(claim_id) + r'\|[0-9a-f]{64})"', html_).group(1); captured.set(); amended.wait(60)
    st, body, _ = c.post("/com/submit", {"claim_ref": ref, "kind": "SUMMARY", "ancestry": "KNOWN"}, page="/com"); srv.close(); q.put((st, "E_STALE_SELECTION" in body, ref))


def amend(root, claim_id, captured, amended):
    from v8.workbench import schema, store
    ws = store.Workspace(root); captured.wait(60)
    rev = schema.from_fixture(json.loads((pathlib.Path(__file__).resolve().parents[1] / "v8/workbench/resources/fixtures/001_base.json").read_text()))["revisions"][0]
    ws.register_source(rev["source"], op_id="op:src-rev0001", observed_at=rev["source"]["available_as_of"])
    ws.amend_claim(claim_id, rev["type"], changes={"range": rev["claim"]["range"]}, reason="per fixture", source=rev["source"], op_id="op:amend-000001", observed_at=rev["source"]["available_as_of"]); amended.set()


# ---------------------------------------------------------------- crash boundaries: SIGKILL inside the journal append
def crash(root, pid, cred, target_kind, mode, call):
    """Perform one operation and SIGKILL this process at a chosen boundary of the journal append of `target_kind`:
    BEFORE (nothing written) · TORN (half the line written, no newline) · AFTER (line written and fsynced, caller never told).
    Private objects written before the append (vault, staged bytes, packet files) are on disk in every mode."""
    import v8.workbench.store as store
    ws, p = _open(root, pid, cred); real_write = os.write; marker = ('"kind":"' + target_kind + '"').encode()

    def write(fd, data):
        if isinstance(data, (bytes, bytearray)) and marker in data and data.endswith(b"\n"):
            if mode == "BEFORE":
                os.kill(os.getpid(), signal.SIGKILL)
            if mode == "TORN":
                real_write(fd, data[: len(data) // 2]); os.fsync(fd); os.kill(os.getpid(), signal.SIGKILL)
            n = real_write(fd, data); os.fsync(fd); os.kill(os.getpid(), signal.SIGKILL); return n
        return real_write(fd, data)
    store.os.write = write
    call(ws, p); os._exit(0)                                                   # reaching here means the boundary was never hit: the parent treats rc 0 as a test error


def crash_main(argv):
    """python v8_mod_procs.py crash <root> <pid> <kind> <mode> <json call>   (credential in V8_TEST_CRED)"""
    from v8.workbench.modules import commons, evolution, modexport, practice, shield
    root, pid, kind, mode, spec = argv[2], argv[3], argv[4], argv[5], json.loads(argv[6]); a = spec["args"]
    calls = {"shd.admit": lambda ws, p: shield.admit(ws, p, a["submission_id"], op_id=a["op"]), "com.assign": lambda ws, p: commons.assign(ws, p, a["group_id"], op_id=a["op"]),
             "com.submit": lambda ws, p: commons.submit_direct(ws, p, claim_id=a["claim_id"], kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=10, asserts_withdrawn=False, client_packet_id=None, op_id=a["op"]),
             "prc.attempt": lambda ws, p: practice.commit_attempt(ws, p, a["session"], judgment="A", reasoning="because", source_refs=a["refs"], unresolved_note="", op_id=a["op"]),
             "prc.reveal": lambda ws, p: practice.reveal(ws, p, a["session"]), "evo.evaluate": lambda ws, p: evolution.run_evaluation(ws, p, version_id=a["version_id"], protocol_id=a["protocol_id"], op_id=a["op"]),
             "modx.build": lambda ws, p: modexport.build_packet(ws, p, modules=["COM"], prc_sessions=[], withhold_text=False, op_id=a["op"])}
    crash(root, pid, os.environ["V8_TEST_CRED"], kind, mode, calls[spec["call"]])


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "crash":
    crash_main(sys.argv)
