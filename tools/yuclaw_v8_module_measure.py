#!/usr/bin/env python3
"""V8-014 §9 — reproducible workload measurements for the four modules (release tooling; not packaged).

    python3 tools/yuclaw_v8_module_measure.py --out <file.json> [--seed 20260920]

Measures, on THIS machine, with fixed seeds and stated denominators: (1) SHD protected-operation latency and the restricted
worker's peak resident memory at two bundle sizes, and the refusal time of an over-limit upload; (2) COM capacity
conservation over seeded concurrent operation sequences at two sizes; (3) EVO targeted reevaluation against a
repeat-everything baseline on REAL controlled file changes at two protocol counts, with missed changes and unnecessary
reruns counted against ground truth. It states no universal target and no improvement where no comparable measurement
exists; zero-violation statements cover the enumerated runs only. Fictional data; automated fixture principals."""
import argparse, hashlib, io, json, os, pathlib, platform, random, resource, statistics, sys, tempfile, threading, time, zipfile
from datetime import timedelta

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from v8.workbench import schema, store                                                      # noqa: E402
from v8.workbench.modules import authz, commons as com, core, evolution as evo, sandbox, shield   # noqa: E402
from v8.workbench.modules.core import ModuleError                                          # noqa: E402
from v8.workbench.modules.shield_worker import MAX_BUNDLE                                  # noqa: E402


def ws_with(*principals):
    ws = store.Workspace(pathlib.Path(tempfile.mkdtemp(prefix="v14m-")) / "ws"); P = authz.Principals(ws); out = {}
    for pid, caps in principals:
        _, c = P.enroll(pid, caps, op_id=f"op:enroll-{pid}", by=None); out[pid] = P.authenticate(pid, c)
    return ws, out


def bundle(n_files, size, rng):
    files = {f"evidence/f{i:02d}.bin": rng.randbytes(size) for i in range(n_files)}
    man = {"schema": "yuclaw.shd-bundle/1", "purpose": "evidence.reference", "evidence": [{"path": p, "sha256": hashlib.sha256(b).hexdigest(), "size": len(b)} for p, b in sorted(files.items())], "payload": {}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        z.writestr("bundle.json", json.dumps(man))
        for p, b in files.items():
            z.writestr(p, b)
    return buf.getvalue(), sorted(hashlib.sha256(b).hexdigest() for b in files.values())


def measure_shd(rng, runs=10):
    ws, p = ws_with(("owner", ["admin"]), ("alice", ["submit"])); shield.enroll_root(ws, p["owner"], label="m", op_id="op:root-000001"); out = {}
    far = (core.now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for label, n_files, size in (("small: 1 file x 1 KiB", 1, 1024), ("large: 32 files x 128 KiB", 32, 128 * 1024)):
        walls, worker_ms = [], []; rss0 = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        for i in range(runs):
            data, srcs = bundle(n_files, size, rng); h = hashlib.sha256(data).hexdigest()
            sid = shield.submit(ws, p["alice"], data, title=label, op_id=f"op:sub-{h[:14]}")["payload"]["submission_id"]
            shield.issue_approval(ws, p["owner"], bundle_sha256=h, source_sha256s=srcs, purpose="evidence.reference", expires_at=far, op_id=f"op:apr-{h[:14]}")
            t0 = time.perf_counter(); d = shield.admit(ws, p["alice"], sid, op_id=f"op:adm-{h[:14]}")["payload"]; walls.append((time.perf_counter() - t0) * 1000)
            assert d["result"] == "ADMITTED", d; worker_ms.append(d["isolation"]["milliseconds"])
        out[label] = {"runs": runs, "bundle_bytes": len(data), "admit_wall_ms": {"median": round(statistics.median(walls), 1), "max": round(max(walls), 1)},
                      "of_which_worker_ms": {"median": statistics.median(worker_ms), "max": max(worker_ms)},
                      "children_peak_rss_kib_so_far": resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss, "children_peak_rss_kib_before": rss0,
                      "declared_budgets": {"wall_seconds": sandbox.WALL_SECONDS, "address_space_bytes": 1024 ** 3, "stdout_bytes": sandbox.MAX_STDOUT, "bundle_bytes": MAX_BUNDLE}}
    t0 = time.perf_counter()
    try:
        shield.submit(ws, p["alice"], b"\0" * (MAX_BUNDLE + 1), title="over", op_id="op:sub-overlimit01"); over = "ACCEPTED (unexpected)"
    except ModuleError as exc:
        over = exc.code
    out["over-limit upload (8 MiB + 1 byte)"] = {"outcome": over, "refused_in_ms": round((time.perf_counter() - t0) * 1000, 2), "worker_started": False}
    out["journal_events_at_end"] = len(ws.load()["events"]); out["note"] = "admit latency grows with the journal because every decision replays it (no index); the journal here held the runs above"
    return out


def measure_com(rng, sizes=(200, 600), threads=4):
    out = {}
    for n_ops in sizes:
        ws, p = ws_with(("owner", ["admin"]), ("alice", ["submit"]), ("bob", ["submit"]), ("rita", ["review"]), ("ravi", ["review"]))
        claims = []
        for i in range(6):
            fx = json.loads((REPO / "v8" / "workbench" / "resources" / "fixtures" / "001_base.json").read_text()); fx["claim"]["claim_id"] = f"ZZFX-MEASURE-{i}"; rec = schema.from_fixture(fx); s0 = rec["claim"]["source"]
            ws.register_source(s0, op_id=f"op:src-{i:04d}", observed_at=s0["available_as_of"]); ws.freeze_claim(rec["claim"], op_id=f"op:frz-{i:04d}", observed_at=s0["available_as_of"]); claims.append(rec["claim"]["claim_id"])
        budget = 150; com.set_budget(ws, p["owner"], period_id="m1", review_minutes=budget, practice_minutes=30, contributor_packet_cap=1000, max_open_tasks=100, op_id="op:budget-0001")
        plan = [(rng.choice(["submit", "submit", "assign", "assign", "release", "finish", "cancel"]), rng.randrange(6), rng.choice(["alice", "bob"]), rng.choice(["rita", "ravi"])) for _ in range(n_ops)]
        violations, refused, done = [], 0, 0; lock = threading.Lock(); counter = [0]

        def worker(chunk):
            nonlocal refused, done
            for act, ci, sub, rev in chunk:
                with lock:
                    counter[0] += 1; op = f"op:m-{n_ops}-{counter[0]:06d}"
                try:
                    if act == "submit":
                        com.submit_direct(ws, p[sub], claim_id=claims[ci], kind="SUMMARY", ancestry="KNOWN", derived_from=[], proposed_cost_minutes=rng.choice([1, 30, 600]), asserts_withdrawn=False, client_packet_id=None, op_id=op)
                    else:
                        groups = sorted(com.state(ws)["groups"])
                        if not groups:
                            continue
                        g = groups[ci % len(groups)]
                        if act == "assign":
                            com.assign(ws, p[rev], g, op_id=op)
                        else:
                            st = com.state(ws)["groups"][g]
                            if act == "finish" and st["state"] == "ASSIGNED":
                                com.work(ws, p[rev], g, "start", op_id=op + "s")
                            com.work(ws, p[rev], g, {"release": "release", "finish": "finish", "cancel": "cancel"}[act], note="measure", op_id=op)
                    with lock:
                        done += 1
                except ModuleError:
                    with lock:
                        refused += 1
                cap = com.capacity(com.state(ws))
                if cap["reserved"] + cap["consumed"] > budget or cap["remaining"] < 0 or cap["overrun"] != 0:
                    with lock:
                        violations.append({"op": op, "capacity": {k: cap[k] for k in ("reserved", "consumed", "remaining", "overrun")}})
        t0 = time.perf_counter(); chunks = [plan[i::threads] for i in range(threads)]; ts = [threading.Thread(target=worker, args=(c,)) for c in chunks]; [t.start() for t in ts]; [t.join() for t in ts]
        s = com.state(ws); cap = com.capacity(s); held = sum(g["reservation"]["minutes"] for g in s["groups"].values() if g["reservation"])
        out[f"{n_ops} operations, {threads} threads"] = {"applied": done, "refused_by_rule": refused, "capacity_violations_observed": len(violations), "first_violations": violations[:3], "final": {k: cap[k] for k in ("review_minutes", "reserved", "consumed", "remaining", "overrun")},
                                                      "reservations_equal_sum_over_holding_tasks": held == cap["reserved"], "packets": len(s["packets"]), "groups": len(s["groups"]), "seconds": round(time.perf_counter() - t0, 1)}
    return out


def measure_evo(rng, protocol_counts=(3, 6), changes=6):
    out = {}
    comps = ["agent_code", "tool_policy", "memory", "data"]
    for n_proto in protocol_counts:
        ws, p = ws_with(("owner", ["admin"]), ("imp", ["submit"]), ("rita", ["review"])); root = pathlib.Path(tempfile.mkdtemp(prefix="v14evo-"))
        for d in comps + ["grader", "evaluation_data"]:
            (root / d).mkdir()
        for d in ("agent_code", "memory", "data"):
            (root / d / "x.json").write_text(json.dumps({"rev": 0}))
        (root / "tool_policy" / "policy.json").write_text(json.dumps({"tools": {"read_filing": "allow"}, "default": "deny"})); (root / "grader" / "g.json").write_text(json.dumps({"required_deny": ["place_order"], "required_allow": ["read_filing"]}))
        (root / "evaluation_data" / "cases.json").write_text(json.dumps({"cases": []}))
        scopes = [["tool_policy"], ["memory"], ["data"], ["agent_code"], ["memory", "data"], ["tool_policy", "agent_code"]][:n_proto]
        cfg = {"roots": [str(root)], "components": {**{c: {"mode": "path", "path": str(root / c)} for c in comps + ["grader", "evaluation_data"]}, "model": {"mode": "declared", "value": "alias"}, "runtime": {"mode": "runtime"}},
               "depends_on": {"tool_policy": ["agent_code"]}, "protocols": {f"p{i}": {"scope": s, "job": "policy_conformance" if "tool_policy" in s else "json_wellformed"} for i, s in enumerate(scopes)}, "authority": {}}
        evo.set_config(ws, p["owner"], cfg, op_id="op:evo-config1"); closures = {pid: set(evo.closure(pr["scope"], cfg["depends_on"])) for pid, pr in cfg["protocols"].items()}
        evo.register_version(ws, p["imp"], version_id="v0", parent_version_id=None, label="base", op_id="op:evo-reg-v0")
        for i, pid in enumerate(cfg["protocols"]):
            evo.run_evaluation(ws, p["rita"], version_id="v0", protocol_id=pid, op_id=f"op:evo-base-{i:03d}")
        targeted = baseline = missed = unnecessary = 0; t_targeted = t_baseline = 0.0
        for k in range(1, changes + 1):
            comp = rng.choice(["agent_code", "memory", "data"]); (root / comp / "x.json").write_text(json.dumps({"rev": k}))                     # a REAL file change observed by the collector
            evo.register_version(ws, p["imp"], version_id=f"v{k}", parent_version_id=f"v{k - 1}", label=f"change {comp}", op_id=f"op:evo-reg-v{k}")
            plan = evo.reevaluation_plan(evo.state(ws), f"v{k}"); truth = {pid for pid, cl in closures.items() if comp in cl}
            missed += len(truth - set(plan["targeted"])); unnecessary += len(set(plan["targeted"]) - truth); baseline += len(plan["baseline_repeat_everything"])
            t0 = time.perf_counter()
            for j, pid in enumerate(plan["targeted"]):
                evo.run_evaluation(ws, p["rita"], version_id=f"v{k}", protocol_id=pid, op_id=f"op:evo-t-{k:02d}-{j:02d}")
            t_targeted += time.perf_counter() - t0; targeted += len(plan["targeted"])
        per_run = t_targeted / max(targeted, 1)
        out[f"{n_proto} protocols, {changes} real single-component changes"] = {"targeted_reevaluations": targeted, "repeat_everything_reevaluations": baseline, "missed_material_changes": missed, "unnecessary_targeted_reruns": unnecessary,
                                                                              "targeted_seconds": round(t_targeted, 2), "repeat_everything_seconds_estimate": round(per_run * baseline, 2), "estimate_basis": "measured mean seconds per trusted evaluation x baseline count (the baseline was not executed)",
                                                                              "ground_truth": "a protocol is affected when the changed component is in its configured closure"}
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--seed", type=int, default=20260920); a = ap.parse_args(); rng = random.Random(a.seed)
    cap = sandbox.capability()
    rec = {"record": "v8-module-measurements/1", "seed": a.seed, "measured_utc": core.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
           "machine": {"platform": f"{platform.system()} {platform.release()} {platform.machine()}", "cpus": os.cpu_count(), "python": sys.version.split()[0], "cryptography": __import__("cryptography").__version__, "isolation_backend": cap["backend"]},
           "shd": measure_shd(rng), "com": measure_com(rng), "evo": measure_evo(rng),
           "reading": "one machine, fixed seeds, synthetic fictional inputs; no universal latency target is stated and no claim is made beyond the enumerated runs; zero violations means none in these runs",
           "not_advice": "Research and education only. Not investment advice."}
    pathlib.Path(a.out).write_text(json.dumps(rec, indent=1) + "\n"); print(json.dumps({k: rec[k] for k in ("machine",)}, indent=1)); print("written", a.out)


if __name__ == "__main__":
    main()
