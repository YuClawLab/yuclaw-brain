"""SHD restricted worker: ALL archive extraction and complex parsing of an untrusted evidence bundle happens here.

Run only by sandbox_bootstrap.py, already confined, as:  <python> -I -S -B shield_worker.py <mode> <input>
Standard library only and importable without side effects (the trusted parent imports `validate_result` to re-check what
this process printed). Modes: `verify` (the product path) and `probe` / `spin` / `flood` (the capability check: attempt
forbidden operations and report what the confinement denied). The mode comes from the parent's fixed argument list —
nothing inside a bundle can select it, name a host path, a module, a command or a URL.

A bundle is a zip: `bundle.json` (schema yuclaw.shd-bundle/1) plus the evidence files it lists under `evidence/`.
Evidence bytes are hashed and measured, never interpreted: instruction-like text inside them is inert data. The result is
a narrow typed document with FIXED codes; an excerpt for the separate, escaped human inspection view travels as base64
and is never part of what a privileged consumer reads. VERIFIED means these bytes are well-formed and self-consistent.
It never means a statement in them is true."""
import base64
import hashlib
import io
import json
import os
import re
import stat
import sys
import zipfile

WORKER = "yuclaw-shd-worker/1"
BUNDLE_SCHEMA = "yuclaw.shd-bundle/1"
PURPOSES = ("com.packets", "evo.evaluations", "evidence.reference")
MAX_BUNDLE = 8 * 1024 * 1024
MAX_MEMBERS, MAX_MEMBER, MAX_TOTAL, MAX_MANIFEST, MAX_RATIO = 64, 4 * 1024 * 1024, 16 * 1024 * 1024, 256 * 1024, 200
MAX_ITEMS, EXCERPT = 50, 2048
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_HEX = re.compile(r"^[0-9a-f]{64}$")
_MEMBER = re.compile(r"^(bundle\.json|evidence/[A-Za-z0-9][A-Za-z0-9._-]{0,99})$")
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
CODES = ("INPUT_NOT_REGULAR_SINGLE_LINK", "INPUT_TOO_LARGE", "INPUT_CHANGED_DURING_READ", "ARCHIVE_INVALID", "ARCHIVE_TOO_MANY_MEMBERS", "ARCHIVE_MEMBER_NAME_REJECTED",
         "ARCHIVE_DUPLICATE_MEMBER", "ARCHIVE_LINK_OR_SPECIAL_MEMBER", "ARCHIVE_ENCRYPTED_MEMBER", "ARCHIVE_COMPRESSION_REJECTED", "ARCHIVE_MEMBER_TOO_LARGE", "ARCHIVE_TOTAL_TOO_LARGE",
         "ARCHIVE_RATIO_REJECTED", "ARCHIVE_SIZE_MISMATCH", "MANIFEST_MISSING", "MANIFEST_TOO_LARGE", "MANIFEST_INVALID_JSON", "MANIFEST_DUPLICATE_KEY", "MANIFEST_TOO_DEEP",
         "MANIFEST_NONINTEGER_NUMBER", "MANIFEST_INTEGER_TOO_LARGE", "MANIFEST_SCHEMA_REJECTED", "EVIDENCE_UNLISTED_MEMBER", "EVIDENCE_MISSING_MEMBER", "EVIDENCE_DIGEST_MISMATCH",
         "EVIDENCE_SIZE_MISMATCH", "PAYLOAD_REJECTED")


class Rejected(Exception):
    def __init__(self, code):
        assert code in CODES, code
        self.code = code; super().__init__(code)


# ------------------------------------------------------------------ bounded, stable read of the one staged input
def read_input(path: str) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise Rejected("INPUT_NOT_REGULAR_SINGLE_LINK")
        if before.st_size > MAX_BUNDLE:
            raise Rejected("INPUT_TOO_LARGE")
        chunks, remaining = [], MAX_BUNDLE + 1
        while remaining:
            part = os.read(fd, min(65536, remaining))
            if not part:
                break
            chunks.append(part); remaining -= len(part)
        data = b"".join(chunks); after = os.fstat(fd)
        if len(data) > MAX_BUNDLE:
            raise Rejected("INPUT_TOO_LARGE")
        same = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if same(before) != same(after) or len(data) != before.st_size:
            raise Rejected("INPUT_CHANGED_DURING_READ")
        return data
    finally:
        os.close(fd)


def strict_json(data: bytes):
    try:
        text = data.decode("utf-8")
    except UnicodeError:
        raise Rejected("MANIFEST_INVALID_JSON") from None
    depth, quoted, escaped = 0, False, False
    for ch in text:
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
        elif ch in "[{":
            depth += 1
            if depth > 16:
                raise Rejected("MANIFEST_TOO_DEEP")
        elif ch in "]}":
            depth -= 1

    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise Rejected("MANIFEST_DUPLICATE_KEY")
            out[k] = v
        return out

    def whole(num):
        if len(num.lstrip("-")) > 16:
            raise Rejected("MANIFEST_INTEGER_TOO_LARGE")
        return int(num)

    def refuse(_):
        raise Rejected("MANIFEST_NONINTEGER_NUMBER")
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_int=whole, parse_float=refuse, parse_constant=refuse)
    except Rejected:
        raise
    except (ValueError, RecursionError):
        raise Rejected("MANIFEST_INVALID_JSON") from None


# ------------------------------------------------------------------ archive
def read_archive(data: bytes) -> dict:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
    except (zipfile.BadZipFile, ValueError, OSError, NotImplementedError):
        raise Rejected("ARCHIVE_INVALID") from None
    if len(infos) > MAX_MEMBERS:
        raise Rejected("ARCHIVE_TOO_MANY_MEMBERS")
    seen, total, out = set(), 0, {}
    for i in infos:
        name = i.filename
        if not isinstance(name, str) or not _MEMBER.match(name) or ".." in name.split("/"):
            raise Rejected("ARCHIVE_MEMBER_NAME_REJECTED")
        if name.casefold() in seen:
            raise Rejected("ARCHIVE_DUPLICATE_MEMBER")
        seen.add(name.casefold())
        mode = (i.external_attr >> 16) & 0o170000
        if mode not in (0, stat.S_IFREG) or i.is_dir():
            raise Rejected("ARCHIVE_LINK_OR_SPECIAL_MEMBER")
        if i.flag_bits & 0x1:
            raise Rejected("ARCHIVE_ENCRYPTED_MEMBER")
        if i.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise Rejected("ARCHIVE_COMPRESSION_REJECTED")
        if i.file_size > (MAX_MANIFEST if name == "bundle.json" else MAX_MEMBER):
            raise Rejected("MANIFEST_TOO_LARGE" if name == "bundle.json" else "ARCHIVE_MEMBER_TOO_LARGE")
        total += i.file_size
        if total > MAX_TOTAL:
            raise Rejected("ARCHIVE_TOTAL_TOO_LARGE")
        if i.file_size > 1024 and i.compress_size and i.file_size // max(i.compress_size, 1) > MAX_RATIO:
            raise Rejected("ARCHIVE_RATIO_REJECTED")
    for i in infos:                                                       # bounded reads: the declared size is not trusted
        try:
            with zf.open(i) as fh:
                body = fh.read(i.file_size + 1)
        except (zipfile.BadZipFile, ValueError, OSError, RuntimeError, NotImplementedError, EOFError):
            raise Rejected("ARCHIVE_INVALID") from None
        if len(body) != i.file_size:
            raise Rejected("ARCHIVE_SIZE_MISMATCH")
        out[i.filename] = body
    return out


# ------------------------------------------------------------------ typed schema (shared by the worker and by the parent's re-check)
def _obj(v, keys, required):
    if not isinstance(v, dict) or not set(v) <= set(keys) or not set(required) <= set(v):
        raise Rejected("MANIFEST_SCHEMA_REJECTED")
    return v


def _id(v):
    if not isinstance(v, str) or not _ID.match(v):
        raise Rejected("PAYLOAD_REJECTED")
    return v


def _ids(v, maximum):
    if not isinstance(v, list) or len(v) > maximum or len(set(map(str, v))) != len(v):
        raise Rejected("PAYLOAD_REJECTED")
    return [_id(x) for x in v]


def _int(v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
        raise Rejected("PAYLOAD_REJECTED")
    return v


def _payload(purpose, p, evidence_paths):
    def evp(v):
        if v is None:
            return None
        if v not in evidence_paths:
            raise Rejected("PAYLOAD_REJECTED")
        return v
    try:
        if purpose == "evidence.reference":
            _obj(p, (), ()); return {}
        if purpose == "com.packets":
            _obj(p, ("packets",), ("packets",)); rows = p["packets"]
            if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ITEMS:
                raise Rejected("PAYLOAD_REJECTED")
            out = []
            for r in rows:
                _obj(r, ("packet_id", "claim_id", "claim_version_digest", "source_roots", "kind", "ancestry", "derived_from", "evidence_path", "proposed_cost_minutes"),
                     ("packet_id", "claim_id", "claim_version_digest", "source_roots", "kind", "ancestry"))
                if r["kind"] not in ("PRIMARY", "SUMMARY") or r["ancestry"] not in ("KNOWN", "UNKNOWN") or not isinstance(r["claim_version_digest"], str) or not _HEX.match(r["claim_version_digest"]):
                    raise Rejected("PAYLOAD_REJECTED")
                out.append({"packet_id": _id(r["packet_id"]), "claim_id": _id(r["claim_id"]), "claim_version_digest": r["claim_version_digest"], "source_roots": _ids(r["source_roots"], 8),
                            "kind": r["kind"], "ancestry": r["ancestry"], "derived_from": _ids(r.get("derived_from", []), 8), "evidence_path": evp(r.get("evidence_path")),
                            "proposed_cost_minutes": _int(r.get("proposed_cost_minutes", 30), 1, 600)})
            if len({r["packet_id"] for r in out}) != len(out):
                raise Rejected("PAYLOAD_REJECTED")
            return {"packets": out}
        if purpose == "evo.evaluations":
            _obj(p, ("evaluations",), ("evaluations",)); rows = p["evaluations"]
            if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ITEMS:
                raise Rejected("PAYLOAD_REJECTED")
            out = []
            for r in rows:
                _obj(r, ("evaluation_id", "version_id", "protocol_id", "result", "issue_key", "scope_components", "evaluated_at", "valid_until", "evidence_path"),
                     ("evaluation_id", "version_id", "protocol_id", "result", "scope_components", "evaluated_at", "valid_until"))
                if r["result"] not in ("PASS", "FAIL") or not all(isinstance(r[k], str) and _TS.match(r[k]) for k in ("evaluated_at", "valid_until")):
                    raise Rejected("PAYLOAD_REJECTED")
                if r["result"] == "FAIL" and not r.get("issue_key"):
                    raise Rejected("PAYLOAD_REJECTED")
                out.append({"evaluation_id": _id(r["evaluation_id"]), "version_id": _id(r["version_id"]), "protocol_id": _id(r["protocol_id"]), "result": r["result"],
                            "issue_key": _id(r["issue_key"]) if r.get("issue_key") else None, "scope_components": _ids(r["scope_components"], 8), "evaluated_at": r["evaluated_at"],
                            "valid_until": r["valid_until"], "evidence_path": evp(r.get("evidence_path"))})
            return {"evaluations": out}
    except (KeyError, TypeError):
        raise Rejected("PAYLOAD_REJECTED") from None
    raise Rejected("MANIFEST_SCHEMA_REJECTED")


def verify_bytes(data: bytes) -> dict:
    """The whole verification of one bundle's bytes → the typed result. Pure: no file, clock, network or environment access."""
    members = read_archive(data)
    if "bundle.json" not in members:
        raise Rejected("MANIFEST_MISSING")
    m = _obj(strict_json(members["bundle.json"]), ("schema", "purpose", "title", "evidence", "payload"), ("schema", "purpose", "evidence", "payload"))
    if m["schema"] != BUNDLE_SCHEMA or m["purpose"] not in PURPOSES or not isinstance(m["evidence"], list) or len(m["evidence"]) > MAX_MEMBERS:
        raise Rejected("MANIFEST_SCHEMA_REJECTED")
    if "title" in m and (not isinstance(m["title"], str) or len(m["title"]) > 200):
        raise Rejected("MANIFEST_SCHEMA_REJECTED")
    listed = {}
    for e in m["evidence"]:
        _obj(e, ("path", "sha256", "size", "source_id"), ("path", "sha256", "size"))
        if not isinstance(e["path"], str) or not _MEMBER.match(e["path"]) or e["path"] == "bundle.json" or e["path"] in listed or not isinstance(e["sha256"], str) or not _HEX.match(e["sha256"]):
            raise Rejected("MANIFEST_SCHEMA_REJECTED")
        if isinstance(e["size"], bool) or not isinstance(e["size"], int) or not 0 <= e["size"] <= MAX_MEMBER:
            raise Rejected("MANIFEST_SCHEMA_REJECTED")
        if "source_id" in e and (not isinstance(e["source_id"], str) or not _ID.match(e["source_id"])):
            raise Rejected("MANIFEST_SCHEMA_REJECTED")
        listed[e["path"]] = e
    for name in members:
        if name != "bundle.json" and name not in listed:
            raise Rejected("EVIDENCE_UNLISTED_MEMBER")
    evidence, excerpts = [], []
    for path in sorted(listed):
        if path not in members:
            raise Rejected("EVIDENCE_MISSING_MEMBER")
        body = members[path]
        if len(body) != listed[path]["size"]:
            raise Rejected("EVIDENCE_SIZE_MISMATCH")
        if hashlib.sha256(body).hexdigest() != listed[path]["sha256"]:
            raise Rejected("EVIDENCE_DIGEST_MISMATCH")
        evidence.append({"path": path, "sha256": listed[path]["sha256"], "size": len(body), "source_id": listed[path].get("source_id")})
        excerpts.append({"path": path, "truncated": len(body) > EXCERPT, "base64": base64.b64encode(body[:EXCERPT]).decode("ascii")})
    payload = _payload(m["purpose"], m["payload"], set(listed))
    return {"worker": WORKER, "result": "VERIFIED", "code": "OK", "bundle_sha256": hashlib.sha256(data).hexdigest(), "manifest_sha256": hashlib.sha256(members["bundle.json"]).hexdigest(),
            "purpose": m["purpose"], "title": m.get("title", ""), "evidence": evidence, "payload": payload, "excerpts": excerpts,
            "meaning": "bytes well-formed and self-consistent; no statement in them was assessed for truth"}


def validate_result(obj, expected_bundle_sha256: str) -> dict:
    """The trusted parent's re-check of what the worker printed. Anything unexpected is a forged or broken output."""
    if not isinstance(obj, dict) or obj.get("worker") != WORKER or obj.get("result") not in ("VERIFIED", "REJECTED"):
        raise Rejected("PAYLOAD_REJECTED")
    if obj["result"] == "REJECTED":
        if set(obj) != {"worker", "result", "code"} or obj["code"] not in CODES:
            raise Rejected("PAYLOAD_REJECTED")
        return obj
    want = {"worker", "result", "code", "bundle_sha256", "manifest_sha256", "purpose", "title", "evidence", "payload", "excerpts", "meaning"}
    if set(obj) != want or obj["code"] != "OK" or obj["bundle_sha256"] != expected_bundle_sha256 or obj["purpose"] not in PURPOSES:
        raise Rejected("PAYLOAD_REJECTED")
    if not isinstance(obj["manifest_sha256"], str) or not _HEX.match(obj["manifest_sha256"]) or not isinstance(obj["title"], str) or len(obj["title"]) > 200:
        raise Rejected("PAYLOAD_REJECTED")
    if not isinstance(obj["evidence"], list) or len(obj["evidence"]) > MAX_MEMBERS or not isinstance(obj["excerpts"], list) or len(obj["excerpts"]) != len(obj["evidence"]):
        raise Rejected("PAYLOAD_REJECTED")
    paths = set()
    for e in obj["evidence"]:
        if not isinstance(e, dict) or set(e) != {"path", "sha256", "size", "source_id"} or not isinstance(e["path"], str) or not _MEMBER.match(e["path"]) or e["path"] == "bundle.json":
            raise Rejected("PAYLOAD_REJECTED")
        if not isinstance(e["sha256"], str) or not _HEX.match(e["sha256"]) or isinstance(e["size"], bool) or not isinstance(e["size"], int) or not 0 <= e["size"] <= MAX_MEMBER:
            raise Rejected("PAYLOAD_REJECTED")
        if e["source_id"] is not None and (not isinstance(e["source_id"], str) or not _ID.match(e["source_id"])):
            raise Rejected("PAYLOAD_REJECTED")
        paths.add(e["path"])
    for x in obj["excerpts"]:
        if not isinstance(x, dict) or set(x) != {"path", "truncated", "base64"} or x["path"] not in paths or not isinstance(x["truncated"], bool) or not isinstance(x["base64"], str) or len(x["base64"]) > 4 * EXCERPT:
            raise Rejected("PAYLOAD_REJECTED")
    if _payload(obj["purpose"], obj["payload"], paths) != obj["payload"]:              # the payload must already be in its normal typed form
        raise Rejected("PAYLOAD_REJECTED")
    return obj


# ------------------------------------------------------------------ capability-check modes (input written by the trusted parent, never a bundle)
def _probe(spec: dict) -> dict:
    import socket
    out = {"worker": WORKER, "mode": "probe", "environment_names": sorted(os.environ), "open_descriptors_above_2": []}
    for fd in range(3, 64):
        try:
            os.fstat(fd); out["open_descriptors_above_2"].append(fd)
        except OSError:
            pass

    def attempt(name, fn):
        try:
            fn(); out[name] = "ALLOWED"
        except MemoryError:
            out[name] = "DENIED:MemoryError"
        except OSError as exc:
            out[name] = "DENIED:" + (os.strerror(exc.errno) if exc.errno else type(exc).__name__)
        except Exception as exc:                                        # noqa: BLE001 - a probe reports whatever stopped it
            out[name] = "DENIED:" + type(exc).__name__

    def connect(kind, port):
        s = socket.socket(socket.AF_INET, kind)
        try:
            s.settimeout(2)
            s.connect(("127.0.0.1", port)) if kind == socket.SOCK_STREAM else s.sendto(b"canary", ("127.0.0.1", port))
        finally:
            s.close()
    attempt("read_canary_secret", lambda: open(spec["canary_read"], "rb").read())
    attempt("read_home_listing", lambda: os.listdir(spec["home"]))
    attempt("read_etc_passwd", lambda: open("/etc/passwd", "rb").read(1))
    attempt("write_forbidden_path", lambda: open(spec["canary_write"], "wb").write(b"escaped"))
    attempt("write_tmp", lambda: open("/tmp/yuclaw-shd-probe-write", "wb").write(b"x"))
    attempt("tcp_connect_canary", lambda: connect(socket.SOCK_STREAM, spec["tcp_port"]))
    attempt("udp_send_canary", lambda: connect(socket.SOCK_DGRAM, spec["udp_port"]))
    attempt("unix_socket", lambda: socket.socket(socket.AF_UNIX, socket.SOCK_STREAM).close())
    attempt("fork_process", lambda: os._exit(0) if os.fork() == 0 else None)
    attempt("signal_parent", lambda: os.kill(os.getppid(), 0))
    attempt("allocate_2GiB", lambda: bytearray(2 * 1024 * 1024 * 1024))
    attempt("read_staged_input", lambda: open(sys.argv[2], "rb").read(1))
    attempt("open_beyond_descriptor_limit", lambda: [open(sys.argv[2], "rb") for _ in range(1024)])     # the one readable file, opened until the descriptor limit stops it
    return out


def main(argv) -> int:
    if len(argv) != 3 or argv[1] not in ("verify", "probe", "spin", "flood"):
        sys.stderr.write("usage: shield_worker.py <verify|probe|spin|flood> <input>\n"); return 96
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))               # before any input byte: no new process or thread
    except (ImportError, ValueError, OSError):
        pass
    mode, path = argv[1], argv[2]
    if mode == "spin":
        while True:
            pass
    if mode == "flood":
        chunk = "x" * 65536
        while True:
            sys.stdout.write(chunk)
    if mode == "probe":
        out = _probe(json.loads(open(path, "rb").read().decode("utf-8")))
    else:
        try:
            out = verify_bytes(read_input(path))
        except Rejected as exc:
            out = {"worker": WORKER, "result": "REJECTED", "code": exc.code}
        except MemoryError:
            out = {"worker": WORKER, "result": "REJECTED", "code": "ARCHIVE_TOTAL_TOO_LARGE"}
    sys.stdout.write(json.dumps(out, sort_keys=True, separators=(",", ":"), ensure_ascii=True)); sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
