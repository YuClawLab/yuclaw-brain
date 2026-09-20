"""The trusted parent's launcher for the restricted worker, and the capability check that decides whether one may be used.

A backend is AVAILABLE only when a live probe run under it, on this host, right now, shows every required denial
(canary secret unreadable, forbidden path unwritable, canary TCP and UDP endpoints unreachable, no unix socket, no fork,
no signal to the parent, no 2 GiB allocation, empty environment, no inherited descriptor) AND the worker still read its
one staged input. There is NO unconfined fallback: when no backend passes, `run_worker` raises E_ISOLATION_UNAVAILABLE and
every route that depends on the protected promise stays closed. A same-user subprocess and file mode 0600 are not a
security boundary and are never presented as one.

The parent never parses a bundle. It receives bounded bytes, stores and hashes them, and hands the staged file to the
worker; it parses only the worker's bounded output (strict JSON, then shield_worker.validate_result)."""
from __future__ import annotations

import contextlib
import json
import os
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from v8.workbench.modules import core
from v8.workbench.modules.core import ModuleError

_DIR = Path(__file__).resolve().parent
BOOTSTRAP, WORKER = _DIR / "sandbox_bootstrap.py", _DIR / "shield_worker.py"
BACKENDS = ("bwrap", "landlock")                       # preference order: namespaces first, process confinement second
WALL_SECONDS, MAX_STDOUT, MAX_STDERR = 30, 2 * 1024 * 1024, 16 * 1024
REQUIRED_DENIALS = {"landlock": ("read_canary_secret", "read_home_listing", "read_etc_passwd", "write_forbidden_path", "write_tmp", "tcp_connect_canary", "udp_send_canary", "unix_socket",
                                 "fork_process", "signal_parent", "allocate_2GiB"),
                    "bwrap": ("read_canary_secret", "read_home_listing", "read_etc_passwd", "write_forbidden_path", "tcp_connect_canary", "udp_send_canary", "fork_process", "allocate_2GiB")}
_cache_lock = threading.Lock(); _cache: dict = {}


def _run(backend: str, mode: str, input_path: Path, *, worker: Path = WORKER, wall: int = WALL_SECONDS) -> dict:
    """One confined run with a FIXED executable and argument structure, an empty environment, no inherited descriptors,
    its own session, and bounded stdout/stderr/wall time. Returns {'rc','stdout','stderr','status'}."""
    argv = [os.path.realpath(sys.executable), "-I", "-S", "-B", str(BOOTSTRAP), backend, str(worker), mode, str(input_path)]
    t0 = time.monotonic()
    p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={}, cwd="/", close_fds=True, start_new_session=True)
    out_buf, err_buf = bytearray(), bytearray()
    sel = selectors.DefaultSelector(); bufs = {p.stdout: out_buf, p.stderr: err_buf}; caps = {p.stdout: MAX_STDOUT, p.stderr: MAX_STDERR}
    for f in bufs:
        os.set_blocking(f.fileno(), False); sel.register(f, selectors.EVENT_READ)
    status = "OK"
    try:
        while sel.get_map():
            left = wall - (time.monotonic() - t0)
            if left <= 0:
                status = "WALL_TIME_EXCEEDED"; break
            for key, _ in sel.select(min(left, 0.5)):
                chunk = key.fileobj.read(65536)
                if not chunk:
                    sel.unregister(key.fileobj); continue
                bufs[key.fileobj] += chunk
                if len(bufs[key.fileobj]) > caps[key.fileobj]:
                    status = "OUTPUT_LIMIT_EXCEEDED"; break
            if status != "OK":
                break
    finally:
        if p.poll() is None and status != "OK":
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(p.pid, signal.SIGKILL)
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(p.pid, signal.SIGKILL)
            p.wait()
        for f in bufs:
            f.close()
        sel.close()
    return {"rc": p.returncode, "stdout": bytes(out_buf[:MAX_STDOUT]), "stderr": bytes(err_buf[:MAX_STDERR]), "status": status, "seconds": round(time.monotonic() - t0, 3)}


def probe(backend: str) -> dict:
    """Run the worker's probe mode under `backend` with live canaries and report what was denied. Never raises."""
    rec = {"backend": backend, "available": False, "platform": f"{os.uname().sysname} {os.uname().release} {os.uname().machine}", "python": sys.version.split()[0], "checked_at": core.now().strftime("%Y-%m-%dT%H:%M:%SZ")}
    if sys.platform != "linux":
        rec["reason"] = "the restricted worker is supported on Linux only"; return rec
    if backend == "bwrap" and not shutil.which("bwrap"):
        rec["reason"] = "bubblewrap (bwrap) is not installed"; return rec
    tmp = Path(tempfile.mkdtemp(prefix="yuclaw-shd-probe-"))
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM); udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        tcp.bind(("127.0.0.1", 0)); tcp.listen(1); tcp.settimeout(0.2); udp.bind(("127.0.0.1", 0)); udp.settimeout(0.2)
        secret = tmp / "canary-secret.txt"; secret.write_text("CANARY-SECRET-DO-NOT-READ\n"); target = tmp / "canary-written.txt"
        spec = tmp / "probe.json"
        spec.write_text(json.dumps({"canary_read": str(secret), "canary_write": str(target), "home": str(Path.home()), "tcp_port": tcp.getsockname()[1], "udp_port": udp.getsockname()[1]}))
        r = _run(backend, "probe", spec, wall=20)
        rec["run"] = {"rc": r["rc"], "status": r["status"], "seconds": r["seconds"], "stderr": r["stderr"].decode("utf-8", "replace")[-400:]}
        if r["status"] != "OK" or r["rc"] != 0:
            rec["reason"] = f"the probe worker did not run under this backend (rc {r['rc']}, {r['status']}): {rec['run']['stderr'].strip()[-200:]}"; return rec
        try:
            out = core.strict_json(r["stdout"], max_bytes=64 * 1024, code="PROBE")
        except ModuleError as exc:
            rec["reason"] = f"probe output unreadable: {exc.code}"; return rec
        rec["observed"] = {k: v for k, v in out.items() if k not in ("worker", "mode")}
        got_tcp = got_udp = False
        with contextlib.suppress(OSError):
            c, _ = tcp.accept(); c.close(); got_tcp = True
        with contextlib.suppress(OSError):
            udp.recvfrom(64); got_udp = True
        rec["parent_observed"] = {"canary_tcp_connection_received": got_tcp, "canary_udp_datagram_received": got_udp, "forbidden_file_created": target.exists()}
        failed = [k for k in REQUIRED_DENIALS[backend] if not str(out.get(k, "")).startswith("DENIED")]
        if out.get("read_staged_input") != "ALLOWED":
            failed.append("read_staged_input (the worker must be able to read its one input)")
        # The worker is started with an EMPTY environment. The interpreter itself may then add LC_CTYPE (PEP 538 locale
        # coercion); that one self-set name is tolerated, anything else means the launcher leaked a variable.
        if set(out.get("environment_names") or []) - {"LC_CTYPE"} or out.get("open_descriptors_above_2"):
            failed.append("clean environment and descriptors")
        if got_tcp or got_udp or target.exists():
            failed.append("parent-side canary observation")
        rec["failed_requirements"] = failed
        for mode, want in (("spin", "WALL_TIME_EXCEEDED"), ("flood", "OUTPUT_LIMIT_EXCEEDED")):
            rr = _run(backend, mode, spec, wall=4 if mode == "spin" else 20)
            rec.setdefault("bounds", {})[mode] = {"status": rr["status"], "rc": rr["rc"], "seconds": rr["seconds"]}
            if rr["status"] != want and not (mode == "spin" and rr["rc"] not in (0, None)):
                failed.append(f"{mode} bound")
        rec["available"] = not failed
        if failed:
            rec["reason"] = "required denials not observed: " + ", ".join(failed)
        return rec
    finally:
        tcp.close(); udp.close(); shutil.rmtree(tmp, ignore_errors=True)


def capability(refresh: bool = False) -> dict:
    """{'backend': name|None, 'probes': [...]} — the first backend whose live probe passed. Cached per process; the
    Setup page and the tests can refresh it."""
    with _cache_lock:
        if refresh or "v" not in _cache:
            probes = []; chosen = None
            forced = os.environ.get("YUCLAW_SHD_BACKEND")                # an operator may pin a backend; pinning never skips its probe
            for b in ([forced] if forced in BACKENDS else BACKENDS):
                pr = probe(b); probes.append(pr)
                if pr["available"] and chosen is None:
                    chosen = b
            _cache["v"] = {"backend": chosen, "probes": probes,
                           "closed_reason": None if chosen else "no isolation backend passed its live probe on this host; the protected SHD route is closed: " + "; ".join(f"{p['backend']}: {p.get('reason')}" for p in probes)}
        return _cache["v"]


def run_worker(staged: Path, expected_sha256: str) -> dict:
    """Verify one staged bundle inside the restricted worker and return the RE-VALIDATED typed result. Raises
    ModuleError(E_ISOLATION_UNAVAILABLE | E_WORKER_FAILED | E_WORKER_OUTPUT_REJECTED). No other code path parses a bundle."""
    from v8.workbench.modules import shield_worker
    cap = capability()
    if not cap["backend"]:
        raise ModuleError("E_ISOLATION_UNAVAILABLE", cap["closed_reason"])
    r = _run(cap["backend"], "verify", staged)
    if r["status"] != "OK" or r["rc"] != 0:
        raise ModuleError("E_WORKER_FAILED", f"the restricted worker ended with {r['status']} (exit {r['rc']}); nothing was admitted")
    try:
        obj = core.strict_json(r["stdout"], max_bytes=MAX_STDOUT, code="WORKER_OUTPUT")
        obj = shield_worker.validate_result(obj, expected_sha256)
    except (ModuleError, shield_worker.Rejected) as exc:
        raise ModuleError("E_WORKER_OUTPUT_REJECTED", f"the worker's output failed the parent's re-validation ({getattr(exc, 'code', exc)}); nothing was admitted") from None
    obj["_isolation"] = {"backend": cap["backend"], "milliseconds": int(r["seconds"] * 1000)}      # integers only: module events travel in packets whose parser refuses floats
    return obj
