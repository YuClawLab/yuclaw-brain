"""EVO — Evolution Evidence Audit: which review evidence still applies after an AI system changed.

It AUDITS. It is not a detector of self-improvement, not a deployment controller, and not a proof that an evaluator, an
inventory or a financial record is truthful. The eligibility answer is read-only and names the exact evaluated subject;
nothing here gates an external deployment (a separately trusted controller would need its own authorized integration).

Eight components: model · agent_code · tool_policy · memory · data · runtime · grader · evaluation_data. Each is
  MEASURED        this process hashed bytes it read from an administrator-configured location (or its own runtime);
  DECLARED        a string somebody supplied (a provider alias is NOT a measurement of model weights; its hash names the string);
  UNKNOWN         required but unavailable — it stays an open finding and blocks reuse of anything that depends on it;
  NOT_APPLICABLE  with the administrator's written justification.
The administrator's configuration — not the submitter — fixes the measurement roots, the dependency edges and each
protocol's component scope. Dropping an edge from submitted metadata therefore changes nothing: reuse is decided on the
CONFIGURED closure. Evidence is reusable for a version only when, across that closure, every component is resolved and
byte-identical to the evaluated subject, the protocol definition and the authority state are unchanged, the subject is an
ancestor (or the version itself), and the validity period has not ended. Each decision carries its reasons.

A trusted local evaluation runs a built-in, typed job on an IMMUTABLE SNAPSHOT: scope files are copied into the private
area, the copy is hashed, and the copy is what the job reads. If the copy's digest is not the registered version's digest
the run is refused (REJECTED_SUBJECT_CHANGED) — a file swapped between collection and execution is never evaluated under
the old identity. No payload names an executable. Imported, declared evaluations (through SHD) are stored as DECLARED_IMPORT
and never counted as trusted-runner evidence.

Failures persist: a FAIL opens an issue with a stable identity; it applies to the failing version and every descendant
until an authorized, evidence-backed resolution event closes it. A later pass, a new label, a renamed protocol, an expiry
or a new digest closes nothing. A version on an unrelated lineage is not held by it. Historical views are cut by the
server-recorded time of each event: a review recorded later never appears as known earlier, and an asserted earlier time
is kept only as a labelled assertion."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import sys
from datetime import timedelta
from pathlib import Path

from v3.receipts.contracts import canonical_json
from v8.workbench.modkinds import EVO_KINDS
from v8.workbench.modules import authz, core, shield
from v8.workbench.modules.core import ModuleError
from v8.workbench.store import Workspace

COMPONENTS = ("model", "agent_code", "tool_policy", "memory", "data", "runtime", "grader", "evaluation_data")
STATUSES = ("MEASURED", "DECLARED", "UNKNOWN", "NOT_APPLICABLE")
AUTHORITY_FIELDS = ("grader_writer_ids", "evidence_writer_ids", "release_authorizer_ids", "hidden_test_reader_ids")
JOBS = ("policy_conformance", "json_wellformed")
JOB_NEEDS = {"policy_conformance": ("tool_policy",), "json_wellformed": ()}      # components a job READS beyond grader and evaluation data: they must be in the protocol scope
MAX_FILES, MAX_BYTES, MAX_FILE = 5000, 256 * 1024 * 1024, 64 * 1024 * 1024
_SECRETISH = (".env", ".pem", ".key", ".p12", ".pfx", "id_rsa", "id_ed25519", "credentials", "secret", ".git", "__pycache__", ".ssh", ".gnupg")


def _d(obj) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


# ------------------------------------------------------------------ measurement (bounded, configured roots only, no secret values)
def _within(path: Path, roots: list) -> Path:
    rp = Path(os.path.realpath(path))
    for r in roots:
        rr = Path(os.path.realpath(r))
        if rp == rr or rr in rp.parents:
            return rp
    raise ModuleError("E_OUTSIDE_ROOTS", "the path is not inside a configured measurement root")


def measure_path(path: Path) -> dict:
    """{'digest','files','bytes','skipped'} over a file or a directory tree: sorted (relative path, sha256) pairs. Symbolic
    links and secret-looking names are skipped and counted, never read. Bounds exceeded → ModuleError (the component is then UNKNOWN)."""
    files, total, skipped, rows = 0, 0, 0, []

    def one(p: Path, rel: str):
        nonlocal files, total
        st = p.stat()
        if st.st_size > MAX_FILE:
            raise ModuleError("E_MEASURE_BOUNDS", f"{rel}: larger than {MAX_FILE // (1024 * 1024)} MiB")
        files += 1; total += st.st_size
        if files > MAX_FILES or total > MAX_BYTES:
            raise ModuleError("E_MEASURE_BOUNDS", f"more than {MAX_FILES} files or {MAX_BYTES // (1024 * 1024)} MiB")
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        rows.append([rel, h.hexdigest(), st.st_size])
    if path.is_file() and not path.is_symlink():
        one(path, path.name)
    elif path.is_dir():
        stack = [path]
        while stack:
            d = stack.pop()
            for e in sorted(os.scandir(d), key=lambda e: e.name):
                if e.is_symlink() or any(s in e.name.lower() for s in _SECRETISH):
                    skipped += 1; continue
                if e.is_dir(follow_symlinks=False):
                    stack.append(Path(e.path))
                elif e.is_file(follow_symlinks=False):
                    one(Path(e.path), str(Path(e.path).relative_to(path)))
    else:
        raise ModuleError("E_MEASURE_MISSING", "nothing measurable at the configured path")
    rows.sort()
    return {"digest": _d(rows), "files": files, "bytes": total, "skipped_links_or_secret_names": skipped}


def measure_runtime() -> dict:
    dists = sorted({(d.metadata["Name"] or "").lower(): d.version for d in importlib.metadata.distributions() if d.metadata["Name"]}.items())
    ident = {"python": sys.version.split()[0], "implementation": platform.python_implementation(), "machine": platform.machine(), "system": platform.system(), "distributions": dists}
    return {"digest": _d(ident), "python": ident["python"], "machine": ident["machine"], "distributions": len(dists)}


# ------------------------------------------------------------------ configuration (admin): roots, components, edges, protocols, authority
def set_config(ws: Workspace, principal, cfg: dict, *, op_id: str) -> dict:
    authz.require(principal, "admin")
    if not isinstance(cfg, dict) or set(cfg) - {"roots", "components", "depends_on", "protocols", "authority"}:
        raise ModuleError("E_CONFIG", "configuration keys: roots, components, depends_on, protocols, authority")
    roots = cfg.get("roots") or []
    if not isinstance(roots, list) or len(roots) > 8 or not all(isinstance(r, str) and os.path.isabs(r) and os.path.isdir(r) for r in roots):
        raise ModuleError("E_CONFIG", "roots: up to 8 existing absolute directories")
    comps = {}
    for name in COMPONENTS:
        c = (cfg.get("components") or {}).get(name) or {"mode": "unknown"}
        mode = c.get("mode")
        if mode == "path":
            _within(Path(c.get("path", "")), roots); comps[name] = {"mode": "path", "path": os.path.realpath(c["path"])}
        elif mode == "runtime" and name == "runtime":
            comps[name] = {"mode": "runtime"}
        elif mode == "declared":
            comps[name] = {"mode": "declared", "value": core.text(c.get("value"), f"{name} declared value", maxlen=300)}
        elif mode == "not_applicable":
            comps[name] = {"mode": "not_applicable", "justification": core.text(c.get("justification"), f"{name} justification", maxlen=500)}
        elif mode == "unknown":
            comps[name] = {"mode": "unknown"}
        else:
            raise ModuleError("E_CONFIG", f"{name}: mode is path, declared, unknown, not_applicable (or runtime for the runtime component)")
    edges = {}
    for a, bs in (cfg.get("depends_on") or {}).items():
        if a not in COMPONENTS or not isinstance(bs, list) or any(b not in COMPONENTS or b == a for b in bs):
            raise ModuleError("E_CONFIG", "depends_on: component → list of other components")
        edges[a] = sorted(set(bs))
    protos = {}
    for pid, p in (cfg.get("protocols") or {}).items():
        core.ident(pid, "protocol id")
        scope = sorted(set(p.get("scope") or []))
        if not scope or any(s not in COMPONENTS for s in scope) or p.get("job") not in JOBS + (None,):
            raise ModuleError("E_CONFIG", f"protocol {pid}: a non-empty component scope and an optional built-in job ({', '.join(JOBS)})")
        missing = [c for c in JOB_NEEDS.get(p.get("job"), ()) if c not in scope]
        if missing:
            raise ModuleError("E_CONFIG", f"protocol {pid}: job {p.get('job')} reads {', '.join(missing)}, so the scope must name it (a job never reads outside its protocol's closure)")
        protos[pid] = {"scope": scope, "job": p.get("job"), "validity_days": int(p.get("validity_days", 90))}
    auth = {f: sorted({core.ident(x, f, core.PRINCIPAL_ID) for x in (cfg.get("authority") or {}).get(f, [])}) for f in AUTHORITY_FIELDS}
    payload = {"roots": [os.path.realpath(r) for r in roots], "components": comps, "depends_on": edges, "protocols": protos, "authority": auth}
    payload["config_digest"] = _d(payload)
    return core.append(ws, "EVO_CONFIG_SET", payload, op_id=op_id, principal=principal)[0]


def closure(scope, edges: dict) -> list:
    """The configured transitive dependency closure. The grader and the evaluation data always belong to it: a change of
    either invalidates what was graded with it."""
    seen, stack = set(), list(scope) + ["grader", "evaluation_data"]
    while stack:
        c = stack.pop()
        if c not in seen:
            seen.add(c); stack.extend(edges.get(c, []))
    return sorted(seen)


# ------------------------------------------------------------------ state
def state(ws: Workspace, as_of: str | None = None, evs: list | None = None) -> dict:
    s = {"config": None, "versions": {}, "evaluations": {}, "reviews": [], "failures": {}, "test_access": [], "requests": {}, "commitments": []}
    for e in core.events(ws, EVO_KINDS, as_of=as_of, evs=evs):
        k, p, at = e["kind"], e["payload"], e["time"]["recorded_at"]
        if k == "EVO_CONFIG_SET":
            s["config"] = {**p, "set_at": at, "set_by": e["actor"]}
        elif k == "EVO_VERSION_REGISTERED":
            s["versions"][p["version_id"]] = {**p, "recorded_at": at}
        elif k == "EVO_EVALUATION_RECORDED":
            s["evaluations"][p["evaluation_id"]] = {**p, "recorded_at": at}
        elif k == "EVO_REVIEW_RECORDED":
            s["reviews"].append({**p, "recorded_at": at})
        elif k == "EVO_FAILURE_RECORDED":
            s["failures"][p["issue_id"]] = {**p, "recorded_at": at, "resolution": None}
        elif k == "EVO_FAILURE_RESOLVED" and p["issue_id"] in s["failures"]:
            s["failures"][p["issue_id"]]["resolution"] = {**p, "recorded_at": at}
        elif k == "EVO_TEST_ACCESS_RECORDED":
            s["test_access"].append({**p, "recorded_at": at})
        elif k == "EVO_REEVAL_REQUESTED":
            s["requests"][p["request_id"]] = {**p, "recorded_at": at}
        elif k == "EVO_COMMITMENT_LINKED":
            s["commitments"].append({**p, "recorded_at": at})
    return s


def lineage(versions: dict, vid: str) -> list:
    """[vid, parent, grandparent, …] — ancestry through recorded parents."""
    out, seen = [], set()
    while vid and vid in versions and vid not in seen:
        out.append(vid); seen.add(vid); vid = versions[vid].get("parent_version_id")
    return out


# ------------------------------------------------------------------ registration = measurement by the configured collector
def collect(cfg: dict, declared: dict | None = None) -> dict:
    out = {}
    for name in COMPONENTS:
        c = cfg["components"][name]
        if c["mode"] == "runtime":
            m = measure_runtime(); out[name] = {"status": "MEASURED", "digest": m["digest"], "detail": f"python {m['python']} on {m['machine']}, {m['distributions']} installed distributions"}
        elif c["mode"] == "path":
            try:
                m = measure_path(_within(Path(c["path"]), cfg["roots"]))
                out[name] = {"status": "MEASURED", "digest": m["digest"], "detail": f"{m['files']} file(s), {m['bytes']} bytes, {m['skipped_links_or_secret_names']} link/secret-named entries skipped unread"}
            except (ModuleError, OSError) as exc:
                out[name] = {"status": "UNKNOWN", "digest": None, "detail": f"configured for measurement but not measurable: {getattr(exc, 'code', type(exc).__name__)}"}
        elif c["mode"] == "declared":
            val = (declared or {}).get(name) or c["value"]
            out[name] = {"status": "DECLARED", "digest": _d({"declared": val}), "detail": f"declared string {val!r}; its hash names the string, not any underlying bytes"}
        elif c["mode"] == "not_applicable":
            out[name] = {"status": "NOT_APPLICABLE", "digest": None, "detail": c["justification"]}
        else:
            out[name] = {"status": "UNKNOWN", "digest": None, "detail": "no measurement location or declaration is configured: an open inventory finding"}
    return out


def register_version(ws: Workspace, principal, *, version_id: str, parent_version_id: str | None, label: str, declared: dict | None = None, op_id: str) -> dict:
    authz.require(principal, "submit")
    core.ident(version_id, "version id")
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "EVO_VERSION_REGISTERED":
            return done
        st = state(ws, evs=evs); cfg = st["config"]
        if cfg is None:
            raise ModuleError("E_NOT_CONFIGURED", "an administrator records the EVO configuration (measurement roots, components, dependency edges, protocols) first")
        if version_id in st["versions"]:
            raise ModuleError("E_VERSION_EXISTS", "a version id is never reused")
        if parent_version_id and parent_version_id not in st["versions"]:
            raise ModuleError("E_UNKNOWN_PARENT", "the parent version is not registered here")
        comps = collect(cfg, {k: core.text(v, k, maxlen=300) for k, v in (declared or {}).items() if k in COMPONENTS and v})
        parent = st["versions"].get(parent_version_id) if parent_version_id else None
        changed = sorted(c for c in COMPONENTS if parent is None or parent["components"][c]["digest"] != comps[c]["digest"] or parent["components"][c]["status"] != comps[c]["status"])
        auth_changed = parent is not None and parent["authority_digest"] != _d(cfg["authority"])
        payload = {"version_id": version_id, "parent_version_id": parent_version_id or None, "label": core.text(label, "label", maxlen=120, required=False), "improver": principal["principal_id"],
                   "components": comps, "changed_components": changed, "config_digest": cfg["config_digest"], "depends_on": cfg["depends_on"], "authority": cfg["authority"],
                   "authority_digest": _d(cfg["authority"]), "authority_changed_from_parent": auth_changed,
                   "inventory": {"measured": sorted(c for c in COMPONENTS if comps[c]["status"] == "MEASURED"), "declared": sorted(c for c in COMPONENTS if comps[c]["status"] == "DECLARED"),
                                 "unknown": sorted(c for c in COMPONENTS if comps[c]["status"] == "UNKNOWN"), "not_applicable": sorted(c for c in COMPONENTS if comps[c]["status"] == "NOT_APPLICABLE")}}
        ev, _ = ws._append_unlocked("EVO_VERSION_REGISTERED", None, payload, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


# ------------------------------------------------------------------ trusted runner on an immutable snapshot (built-in typed jobs only)
def _snapshot(ws: Workspace, cfg: dict, comps: list) -> tuple[Path, dict]:
    base = ws.root / "private" / "evo_snapshots"; base.mkdir(parents=True, exist_ok=True); os.chmod(base, 0o700)
    tmp = base / f".tmp-{os.getpid()}-{core.now().strftime('%H%M%S%f')}"; tmp.mkdir(mode=0o700); digests = {}
    for name in comps:
        c = cfg["components"][name]
        if c["mode"] != "path":
            continue
        src = _within(Path(c["path"]), cfg["roots"]); dst = tmp / name
        if src.is_dir():
            shutil.copytree(src, dst, symlinks=False, ignore=lambda d, names: [n for n in names if any(s in n.lower() for s in _SECRETISH) or os.path.islink(os.path.join(d, n))])
        else:
            dst.mkdir(); shutil.copy2(src, dst / src.name)
        digests[name] = measure_path(dst if src.is_dir() else dst / src.name)["digest"]            # the digest of the COPY: what will actually be executed
    final = base / _d(digests)[:24]
    if final.exists():
        shutil.rmtree(tmp)
    else:
        os.replace(tmp, final)
    for root, dirs, files in os.walk(final):
        for f in files:
            os.chmod(os.path.join(root, f), 0o400)
    return final, digests


def _load_json_file(d: Path, limit=1 << 20):
    files = sorted(p for p in d.rglob("*.json") if p.is_file())
    if len(files) != 1:
        raise ModuleError("E_JOB_INPUT", f"{d.name}: the policy_conformance job reads exactly one .json file in this component")
    return core.strict_json(files[0].read_bytes(), max_bytes=limit, code="JOB_INPUT")


def _job_policy_conformance(snap: Path) -> tuple[str, list]:
    """Built-in job. tool_policy: {"tools": {name: "allow"|"deny"}, "default": "deny"}; grader: {"required_deny": [..], "required_allow": [..]};
    evaluation_data: {"cases": [{"case_id","tool","expect":"allow"|"deny"}]}. Data only — nothing in these files is executed."""
    pol, grd, data = _load_json_file(snap / "tool_policy"), _load_json_file(snap / "grader"), _load_json_file(snap / "evaluation_data")
    tools, default = pol.get("tools", {}), pol.get("default", "deny"); failing = []
    decide = lambda t: tools.get(t, default)
    for t in grd.get("required_deny", []):
        if decide(t) != "deny":
            failing.append(f"required-deny:{t}")
    for t in grd.get("required_allow", []):
        if decide(t) != "allow":
            failing.append(f"required-allow:{t}")
    for c in data.get("cases", []):
        if decide(c.get("tool")) != c.get("expect"):
            failing.append(f"case:{c.get('case_id')}")
    return ("FAIL" if failing else "PASS"), sorted(set(map(str, failing)))[:20]


def _job_json_wellformed(snap: Path, scope: list) -> tuple[str, list]:
    """Built-in job. Every .json file of the protocol's scoped components parses under the strict bounded parser (no duplicate
    keys, no floats, bounded depth and size). Data only."""
    failing = []
    for comp in scope:
        for f in sorted((snap / comp).rglob("*.json")) if (snap / comp).is_dir() else []:
            try:
                core.strict_json(f.read_bytes(), max_bytes=1 << 20, code="JOB_INPUT")
            except ModuleError as exc:
                failing.append(f"{comp}/{f.name}:{exc.code}")
    return ("FAIL" if failing else "PASS"), failing[:20]


def run_evaluation(ws: Workspace, principal, *, version_id: str, protocol_id: str, op_id: str) -> dict:
    """Trusted-runner evaluation of one registered version under one configured protocol. Grader conflicts are checked on
    THIS task: the grading principal must not be an improver anywhere in the version's ancestry."""
    authz.require(principal, "review")
    evs = ws.load()["events"]; done = core.prior(evs, op_id)
    if done is not None and done["kind"] == "EVO_EVALUATION_RECORDED":
        return done
    st = state(ws, evs=evs); cfg, v = st["config"], st["versions"].get(version_id)
    if cfg is None or v is None or protocol_id not in cfg["protocols"]:
        raise ModuleError("E_UNKNOWN", "unknown version or protocol")
    proto = cfg["protocols"][protocol_id]
    if proto["job"] not in JOBS:
        raise ModuleError("E_NO_JOB", "this protocol has no built-in job; only supported local job types can be run (no executable is ever taken from a request)")
    improvers = {st["versions"][a]["improver"] for a in lineage(st["versions"], version_id)}
    authz.conflict(principal, improvers, "improved this version or one of its ancestors and cannot grade it")
    cl = closure(proto["scope"], cfg["depends_on"])
    unknown = [c for c in cl if v["components"][c]["status"] == "UNKNOWN"]
    snap, digests = _snapshot(ws, cfg, cl)
    moved = sorted(c for c, dg in digests.items() if v["components"][c]["digest"] != dg)
    if moved:
        raise ModuleError("REJECTED_SUBJECT_CHANGED", f"the bytes now at the configured location differ from registered version {version_id} for: {', '.join(moved)}. Register the new state as a new version; nothing was evaluated under the old identity")
    result, failing = _job_policy_conformance(snap) if proto["job"] == "policy_conformance" else _job_json_wellformed(snap, proto["scope"])
    now = core.now()
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None:
            return done
        payload = {"evaluation_id": core.next_id(evs, "EVO_EVALUATION_RECORDED", "EV", "evaluation_id"), "origin": "TRUSTED_RUNNER", "version_id": version_id, "protocol_id": protocol_id,
                   "protocol_digest": _d(proto), "job": proto["job"], "result": result, "failing": failing, "grader_principal": principal["principal_id"],
                   "subject": {"version_id": version_id, "closure": cl, "executed_digests": digests, "snapshot": snap.name, "unknown_in_closure": unknown},
                   "authority_digest": v["authority_digest"], "evaluated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "valid_until": (now + timedelta(days=proto["validity_days"])).strftime("%Y-%m-%dT%H:%M:%SZ")}
        ev, _ = ws._append_unlocked("EVO_EVALUATION_RECORDED", None, payload, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        if result == "FAIL":
            _open_failure(ws, evs + [ev], payload, proto["job"] + ":" + hashlib.sha256("|".join(failing).encode()).hexdigest()[:12], op_id, principal)
        return ev


def _open_failure(ws, evs, evaluation: dict, issue_key: str, op_id: str, principal):
    issue_id = "IS-" + hashlib.sha256(f"{issue_key}|{','.join(evaluation['subject']['closure'])}".encode()).hexdigest()[:12]
    if issue_id in state(ws, evs=evs)["failures"]:
        return
    ws._append_unlocked("EVO_FAILURE_RECORDED", None, {"issue_id": issue_id, "issue_key": issue_key, "first_failed_version": evaluation["version_id"], "evaluation_id": evaluation["evaluation_id"],
                        "scope_closure": evaluation["subject"]["closure"], "protocol_id": evaluation["protocol_id"],
                        "applicability": "this version and every descendant, until an authorized evidence-backed resolution; a later pass, label, protocol name, expiry or digest closes nothing"},
                        op_id=op_id + ":issue", observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))


def import_declared(ws: Workspace, principal, decision_id: str, *, op_id: str) -> list:
    """Declared evaluations from an SHD-admitted bundle (purpose evo.evaluations). Stored as DECLARED_IMPORT; the SHD approval
    is re-validated inside this commit."""
    authz.require(principal, "submit")
    with ws._locked():
        evs = ws.load()["events"]
        typed = shield.require_current(ws, evs, decision_id, "evo.evaluations"); st = state(ws, evs=evs); out = []
        for i, r in enumerate(typed["payload"]["evaluations"]):
            if r["version_id"] not in st["versions"]:
                raise ModuleError("E_UNKNOWN", f"declared evaluation names version {r['version_id']!r}, which is not registered here")
            cfg = st["config"]; proto = (cfg or {}).get("protocols", {}).get(r["protocol_id"])
            cl = closure(proto["scope"] if proto else r["scope_components"], cfg["depends_on"] if cfg else {})
            payload = {"evaluation_id": f"DV-{decision_id}-{i + 1}", "origin": "DECLARED_IMPORT", "shd_decision_id": decision_id, "declared_evaluation_id": r["evaluation_id"], "version_id": r["version_id"],
                       "protocol_id": r["protocol_id"], "protocol_digest": _d(proto) if proto else None, "job": None, "result": r["result"], "failing": [r["issue_key"]] if r["issue_key"] else [],
                       "grader_principal": None, "declared_by": principal["principal_id"],
                       "subject": {"version_id": r["version_id"], "closure": cl, "executed_digests": {}, "snapshot": None, "unknown_in_closure": [],
                                   "note": "declared scope was " + ",".join(r["scope_components"]) + "; the CONFIGURED closure is what reuse is decided on"},
                       "authority_digest": st["versions"][r["version_id"]]["authority_digest"], "evaluated_at": r["evaluated_at"], "valid_until": r["valid_until"],
                       "meaning": "a declaration admitted byte-for-byte through SHD; this workspace did not run it and does not count it as trusted-runner evidence"}
            ev, _ = ws._append_unlocked("EVO_EVALUATION_RECORDED", None, payload, op_id=f"{op_id}:{i + 1}", observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
            out.append(ev)
            if r["result"] == "FAIL":
                _open_failure(ws, ws.load()["events"], payload, r["issue_key"], f"{op_id}:{i + 1}", principal)
        return out


# ------------------------------------------------------------------ review, test access, failure resolution, requests, commitments
def record_review(ws: Workspace, principal, *, version_id: str, decision: str, note: str, asserted_review_time: str | None = None, op_id: str) -> dict:
    authz.require(principal, "review")
    if decision not in ("REVIEWED_ACCEPTABLE", "REVIEWED_CONCERNS"):
        raise ModuleError("E_DECISION", "decision: REVIEWED_ACCEPTABLE or REVIEWED_CONCERNS")
    with ws._locked():
        evs = ws.load()["events"]; st = state(ws, evs=evs)
        if version_id not in st["versions"]:
            raise ModuleError("E_UNKNOWN", "unknown version")
        reviewed = {r["version_id"] for r in st["reviews"]}
        window = []
        for a in lineage(st["versions"], version_id):
            if a != version_id and a in reviewed:
                break
            window.append(a)
        authz.conflict(principal, {st["versions"][a]["improver"] for a in window}, "improved a version inside the transition under review and cannot review it")
        asserted, label = None, None
        if asserted_review_time:
            asserted = core.norm_time(asserted_review_time, "asserted review time")
            if core.parse_time(asserted) < core.now() - timedelta(minutes=5):
                label = "BACKDATED_ASSERTION — kept as the reviewer's statement only; every historical view uses the server-recorded time of this event"
        ev, _ = ws._append_unlocked("EVO_REVIEW_RECORDED", None, {"version_id": version_id, "reviewer": principal["principal_id"], "decision": decision, "note": core.text(note, "note", maxlen=2000),
                                    "covers_versions": window, "asserted_review_time": asserted, "asserted_time_label": label}, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return ev


def record_test_access(ws: Workspace, principal, *, subject_principal: str, action: str, op_id: str) -> dict:
    authz.require(principal, "admin")
    if action not in ("GRANTED", "REVOKED"):
        raise ModuleError("E_ACTION", "action: GRANTED or REVOKED")
    core.ident(subject_principal, "principal", core.PRINCIPAL_ID)
    if subject_principal not in authz.Principals(ws).state():                 # revoked principals stay known: their earlier exposure is still recorded against them
        raise ModuleError("E_UNKNOWN_PRINCIPAL", f"{subject_principal!r} was never enrolled in this workspace")
    return core.append(ws, "EVO_TEST_ACCESS_RECORDED", {"principal_id": subject_principal, "action": action,
                       "meaning": "revoking access ends future access; it does not erase that the principal could read the protected tests before"}, op_id=op_id, principal=principal)[0]


def resolve_failure(ws: Workspace, principal, *, issue_id: str, evidence_evaluation_id: str, reason: str, op_id: str) -> dict:
    authz.require(principal, "admin")
    with ws._locked():
        evs = ws.load()["events"]; st = state(ws, evs=evs); f = st["failures"].get(issue_id); ev_ = st["evaluations"].get(evidence_evaluation_id)
        if f is None or f["resolution"]:
            raise ModuleError("E_UNKNOWN", "no such open issue")
        if ev_ is None or ev_["origin"] != "TRUSTED_RUNNER" or ev_["result"] != "PASS":
            raise ModuleError("E_EVIDENCE", "a resolution needs a PASS produced by the trusted runner in this workspace")
        if f["first_failed_version"] not in lineage(st["versions"], ev_["version_id"]) or not set(f["scope_closure"]) <= set(ev_["subject"]["closure"]):
            raise ModuleError("E_EVIDENCE", "the supporting evaluation must be on the failing version's lineage and cover the failure's whole scope")
        authz.conflict(principal, {st["versions"][a]["improver"] for a in lineage(st["versions"], ev_["version_id"])}, "improved a version on this lineage and cannot resolve its failure")
        e, _ = ws._append_unlocked("EVO_FAILURE_RESOLVED", None, {"issue_id": issue_id, "resolved_by": principal["principal_id"], "evidence_evaluation_id": evidence_evaluation_id,
                                   "resolved_from_version": ev_["version_id"], "reason": core.text(reason, "reason", maxlen=2000),
                                   "meaning": "the original failure event is unchanged; versions before the resolving version on this lineage remain failed"},
                                   op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return e


def request_reevaluation(ws: Workspace, principal, *, version_id: str, protocol_id: str, reason: str, op_id: str) -> dict:
    if principal is None or not ({"review", "submit", "admin"} & set(principal["caps"])):
        raise ModuleError("E_FORBIDDEN", "requesting a reevaluation needs the submit, review or admin capability")
    with ws._locked():
        evs = ws.load()["events"]; st = state(ws, evs=evs)
        if version_id not in st["versions"] or not st["config"] or protocol_id not in st["config"]["protocols"]:
            raise ModuleError("E_UNKNOWN", "unknown version or protocol")
        e, _ = ws._append_unlocked("EVO_REEVAL_REQUESTED", None, {"request_id": core.next_id(evs, "EVO_REEVAL_REQUESTED", "RQ", "request_id"), "version_id": version_id, "protocol_id": protocol_id,
                                   "job": st["config"]["protocols"][protocol_id]["job"], "reason": core.text(reason, "reason", maxlen=500), "requested_by": principal["principal_id"],
                                   "note": "a typed request for a built-in local job; it names no executable and runs only when a reviewer starts it"},
                                   op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        return e


def link_commitment(ws: Workspace, principal, *, version_id: str, claim_id: str, amount: str | None, currency: str | None, op_id: str) -> dict:
    authz.require(principal, "submit")
    ref = core.claim_ref(ws, claim_id)
    if version_id not in state(ws)["versions"]:
        raise ModuleError("E_UNKNOWN", "unknown version")
    amt = None
    if amount not in (None, ""):
        if not str(amount).lstrip("-").isdigit() or len(str(amount)) > 16:
            raise ModuleError("E_AMOUNT", "amount: a whole number in the claim's stated currency and scale, or empty for unknown")
        amt = int(amount)
    cur = (currency or ref["contract"].get("currency") or "").strip().upper() or None
    return core.append(ws, "EVO_COMMITMENT_LINKED", {"version_id": version_id, "claim_id": claim_id, "claim_version_digest": ref["version_digest"], "amount": amt, "currency": cur if amt is not None else (cur or None),
                       "note": "as supplied; no currency conversion, avoided loss or trading decision is derived"}, op_id=op_id, principal=principal)[0]


# ------------------------------------------------------------------ the audit: reuse decisions, gaps, eligibility (read-only)
def reuse_decisions(st: dict, version_id: str, at=None) -> dict:
    """{protocol_id: {'decision': REUSE|REEVALUATE, 'evaluation_id', 'reasons': [...]}} for every configured protocol."""
    at = at or core.now(); cfg, versions = st["config"], st["versions"]; v = versions[version_id]; anc = lineage(versions, version_id); out = {}
    for pid, proto in sorted((cfg or {}).get("protocols", {}).items()):
        cl = closure(proto["scope"], v["depends_on"]); best = None; why_not = []
        unknown = [c for c in cl if v["components"][c]["status"] == "UNKNOWN"]
        if unknown:
            out[pid] = {"decision": "REEVALUATE", "evaluation_id": None, "closure": cl, "reasons": [f"required inventory unknown: {', '.join(unknown)} — an unknown component is never assumed unchanged"]}; continue
        for e in sorted(st["evaluations"].values(), key=lambda e: e["recorded_at"], reverse=True):
            if e["protocol_id"] != pid or e["result"] != "PASS":
                continue
            tag = f"{e['evaluation_id']} on {e['version_id']}"
            if e["origin"] != "TRUSTED_RUNNER":
                why_not.append(f"{tag}: a declared import, not trusted-runner evidence"); continue
            if e["version_id"] not in anc:
                why_not.append(f"{tag}: its subject is not this version or an ancestor"); continue
            if e["protocol_digest"] != _d(proto):
                why_not.append(f"{tag}: the protocol definition changed since"); continue
            if e["authority_digest"] != v["authority_digest"]:
                why_not.append(f"{tag}: the authority state (graders, evidence writers, release authorizers, test readers) changed since"); continue
            if core.parse_time(e["valid_until"]) <= at:
                why_not.append(f"{tag}: validity ended {e['valid_until']}"); continue
            subj = versions[e["version_id"]]
            diff = [c for c in cl if subj["components"][c]["digest"] != v["components"][c]["digest"] or subj["components"][c]["status"] != v["components"][c]["status"]]
            if diff:
                why_not.append(f"{tag}: changed inside the configured dependency closure: {', '.join(diff)}"); continue
            best = e; break
        if best:
            same = best["version_id"] == version_id
            out[pid] = {"decision": "REUSE", "evaluation_id": best["evaluation_id"], "closure": cl,
                        "reasons": [f"{best['evaluation_id']} evaluated {'this version' if same else 'ancestor ' + best['version_id']}; every component of the configured closure ({', '.join(cl)}) is byte-identical, "
                                    f"the protocol and authority state are unchanged, valid until {best['valid_until']}"] + ([] if same else [f"changes outside the closure do not affect it: {', '.join(c for c in v['changed_components'] if c not in cl) or 'none'}"])}
        else:
            out[pid] = {"decision": "REEVALUATE", "evaluation_id": None, "closure": cl, "reasons": why_not or ["no passing trusted-runner evaluation exists for this protocol on this lineage"]}
    return out


def audit(ws: Workspace, version_id: str, as_of: str | None = None) -> dict:
    st = state(ws, as_of=as_of); v = st["versions"].get(version_id)
    if v is None:
        raise ModuleError("E_UNKNOWN", "unknown version (at this cutoff)" if as_of else "unknown version")
    at = core.parse_time(core.norm_time(as_of, "as of")) if as_of else core.now(); anc = lineage(st["versions"], version_id)
    reuse = reuse_decisions(st, version_id, at)
    open_failures = [f for f in st["failures"].values() if f["first_failed_version"] in anc and not (f["resolution"] and f["resolution"]["resolved_from_version"] in anc)]
    reviewed = [r for r in st["reviews"] if version_id in r["covers_versions"] or r["version_id"] == version_id]
    exposed = {}
    for a in st["test_access"]:
        if a["action"] == "GRANTED":
            exposed.setdefault(a["principal_id"], a["recorded_at"])
    improvers = {st["versions"][x]["improver"] for x in anc}
    exposure = sorted(p for p in improvers if p in exposed)
    gaps = []
    if not reviewed:
        gaps.append("UNREVIEWED_TRANSITION: no review covers this version")
    gaps += [f"REEVALUATE {pid}: {d['reasons'][0]}" for pid, d in reuse.items() if d["decision"] == "REEVALUATE"]
    gaps += [f"OPEN_FAILURE {f['issue_id']} ({f['issue_key']}) first failed on {f['first_failed_version']}" for f in open_failures]
    gaps += [f"UNKNOWN_INVENTORY {c}: {v['components'][c]['detail']}" for c in v["inventory"]["unknown"]]
    gaps += [f"TEST_EXPOSURE: improver {p} could read the protected tests (access recorded {exposed[p]}); revoking access later does not erase this, and a new test digest alone does not show fresh content" for p in exposure]
    if v["authority_changed_from_parent"]:
        gaps.append("AUTHORITY_CHANGED from the parent version: evidence recorded under the earlier authority state is not reused")
    money: dict = {}
    for c in st["commitments"]:
        if c["version_id"] in anc:
            k = c["currency"] or "UNKNOWN_CURRENCY"; m = money.setdefault(k, {"known_total": 0, "known_count": 0, "unknown_amount_count": 0, "claims": []})
            m["claims"].append(c["claim_id"])
            if c["amount"] is None:
                m["unknown_amount_count"] += 1
            else:
                m["known_total"] += c["amount"]; m["known_count"] += 1
    evidence_age = {e["evaluation_id"]: (at - core.parse_time(e["evaluated_at"])).days for e in st["evaluations"].values() if e["version_id"] in anc}
    return {"version": v, "lineage": anc, "as_of": as_of, "view": "historical cutoff (server-recorded times)" if as_of else "present", "reuse": reuse, "open_failures": open_failures,
            "reviews": reviewed, "test_exposure": exposure, "gaps": gaps, "evidence_age_days": evidence_age, "linked_commitments_by_currency": money,
            "eligibility": {"subject": {"version_id": version_id, "component_digests": {c: v["components"][c]["digest"] for c in COMPONENTS}},
                            "status": "NO_OPEN_FINDINGS" if not gaps else "HOLD_FOR_REVIEW", "findings": len(gaps),
                            "scope": "a read-only answer about recorded evidence for exactly this subject; it controls no external deployment and asserts nothing about truth or safety"}}


def reevaluation_plan(st: dict, version_id: str) -> dict:
    """Targeted plan vs the repeat-everything baseline, for the comparison the order asks to disclose."""
    reuse = reuse_decisions(st, version_id); protos = sorted(reuse)
    return {"targeted": [p for p in protos if reuse[p]["decision"] == "REEVALUATE"], "baseline_repeat_everything": protos,
            "reused": {p: reuse[p]["evaluation_id"] for p in protos if reuse[p]["decision"] == "REUSE"}}
