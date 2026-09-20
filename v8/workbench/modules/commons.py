"""COM — Research Commons Guard: a durable, duplicate-aware evidence-review queue with authenticated admission and budgets.

One review TASK per exact duplicate GROUP. A group is keyed by the canonical claim id, the claim-version digest, the
financial contract digest (metric · currency · unit · scale · accounting basis · fiscal period) and the known source roots:
packets that differ in any of these stay separate. Exact identity only — semantic similarity is never computed, and neither
a shared root nor a duplicate is called plagiarism or misconduct. Many summaries of one source are one root, not
independent corroboration; unknown ancestry stays unknown and is shown.

Authority. Admission limits count the AUTHENTICATED principal, so a new display name resets nothing (local credentials do
not solve collusion or real-world Sybil identity — documented, not claimed). A submitter's cost estimate is a PROPOSAL;
the scheduling cost of a group is a built-in default until a reviewer or administrator sets it, and a duplicate can neither
inflate nor reduce it. A dispute, withdrawal or source correction changes queue handling only when a reviewer or
administrator records it; a submitter asserting "withdrawn" is kept as an assertion and quarantines nothing. Quarantine is
a handling state with an appeal and a resolution, each a new event; original source bytes and earlier review history are
never edited.

Capacity. Every reservation, assignment and completion is decided and appended under the one workspace lock, so two
workers cannot spend the same minutes. Review minutes and the separately reserved PRACTICE minutes never borrow from each
other. A task that does not fit is deferred with its reason while smaller fitting tasks proceed; an aged task then HOLDS
the remaining capacity so that small arrivals cannot starve it; an oversized task escalates to the administrator — no
rule manufactures budget. A budget cut below recorded consumption shows the overrun and stops new reservations; recorded
consumption is never rewritten and remaining capacity never goes negative. Estimated minutes, server-observed session
seconds and manually declared effort are three different numbers; a timer is not proof of attentive human work."""
from __future__ import annotations

import hashlib
from datetime import timedelta

from v3.receipts.contracts import canonical_json
from v8.workbench.modkinds import COM_KINDS
from v8.workbench.modules import authz, core, shield
from v8.workbench.modules.core import ModuleError
from v8.workbench.store import Workspace

DEFAULT_COST_MINUTES, LEASE_MINUTES, AGED_AFTER_HOURS, MAX_PACKETS, RATE_PER_MINUTE = 30, 120, 24, 5000, 30
OPEN_STATES = ("QUEUED", "ASSIGNED", "ACTIVE", "PAUSED", "DEFERRED")
HOLDING = ("ASSIGNED", "ACTIVE", "PAUSED")                       # states that hold a reservation
EFFORT_CATEGORIES = ("triage", "review", "quarantine_investigation", "correction", "coordination")
TRANSITIONS = {("QUEUED", "ASSIGNED"), ("DEFERRED", "ASSIGNED"), ("ASSIGNED", "ACTIVE"), ("ACTIVE", "PAUSED"), ("PAUSED", "ACTIVE"), ("ACTIVE", "COMPLETED"), ("PAUSED", "COMPLETED"),
               ("ASSIGNED", "QUEUED"), ("ACTIVE", "QUEUED"), ("PAUSED", "QUEUED"), ("QUEUED", "DEFERRED"), ("DEFERRED", "QUEUED"),
               ("QUEUED", "CANCELED"), ("DEFERRED", "CANCELED"), ("ASSIGNED", "CANCELED"), ("ACTIVE", "CANCELED"), ("PAUSED", "CANCELED")}


def group_id(claim: dict, roots: list, ancestry: str) -> str:
    return "G-" + hashlib.sha256(canonical_json([claim["claim_id"], claim["version_digest"], claim["contract_digest"], sorted(roots), ancestry])).hexdigest()[:16]


# ------------------------------------------------------------------ state (journal replay)
def state(ws: Workspace, as_of: str | None = None, evs: list | None = None) -> dict:
    evs_all = ws.load()["events"] if evs is None else evs
    s = {"budgets": {}, "period": None, "packets": {}, "groups": {}, "disputes": {}, "overrides": [], "efforts": [], "practice_reserved": {}}
    for e in core.events(ws, COM_KINDS + ("PRC_SESSION_OPENED",), as_of=as_of, evs=evs_all):
        k, p, at = e["kind"], e["payload"], e["time"]["recorded_at"]
        if k == "COM_BUDGET_SET":
            b = s["budgets"].setdefault(p["period_id"], {"revisions": []}); b.update(p); b["revisions"].append({"at": at, "by": e["actor"], "review_minutes": p["review_minutes"], "practice_minutes": p["practice_minutes"]})
            s["period"] = p["period_id"]
        elif k == "COM_PACKET_SUBMITTED":
            s["packets"][p["packet_id"]] = {**p, "recorded_at": at}
            g = s["groups"].setdefault(p["group_id"], {"group_id": p["group_id"], "claim": p["claim"], "source_roots": p["source_roots"], "unknown_roots": p["unknown_roots"], "ancestry": p["ancestry"],
                                                       "packets": [], "contributors": [], "first_at": at, "state": "QUEUED", "cost_minutes": DEFAULT_COST_MINUTES, "cost_authority": "built-in default",
                                                       "proposed_costs": [], "reservation": None, "assignee": None, "lease_until": None, "observed_seconds": 0, "active_since": None, "history": [],
                                                       "skips": 0, "urgent": False, "period_consumed": None, "consumed_minutes": 0})
            g["packets"].append(p["packet_id"]); g["proposed_costs"].append(p["proposed_cost_minutes"])
            if p["submitter"] not in g["contributors"]:
                g["contributors"].append(p["submitter"])
        elif k == "COM_COST_SET" and p["group_id"] in s["groups"]:
            s["groups"][p["group_id"]].update(cost_minutes=p["minutes"], cost_authority=f"{e['actor']} at {at}: {p['rule']}")
        elif k == "COM_TASK_TRANSITION" and p["group_id"] in s["groups"]:
            g = s["groups"][p["group_id"]]; g["history"].append({**p, "at": at, "by": e["actor"]})
            if g["active_since"] and p["from"] == "ACTIVE":
                g["observed_seconds"] += max(0, int((core.parse_time(at) - core.parse_time(g["active_since"])).total_seconds())); g["active_since"] = None
            g["state"] = p["to"]
            if p["to"] == "ACTIVE":
                g["active_since"] = at
            if p["to"] == "ASSIGNED":
                g["reservation"] = {"minutes": p["reservation_minutes"], "period_id": p["period_id"]}; g["assignee"] = p.get("assignee"); g["lease_until"] = p.get("lease_until")
            elif p["to"] == "COMPLETED":
                g["consumed_minutes"] = (g["reservation"] or {}).get("minutes", 0); g["period_consumed"] = (g["reservation"] or {}).get("period_id"); g["reservation"] = None
            elif p["to"] in ("QUEUED", "CANCELED", "DEFERRED"):
                g["reservation"] = None; g["assignee"] = None; g["lease_until"] = None
            if p.get("reason", "").startswith("SKIPPED"):
                g["skips"] += 1
        elif k == "COM_OVERRIDE_RECORDED" and p["group_id"] in s["groups"]:
            s["groups"][p["group_id"]]["urgent"] = True; s["overrides"].append({**p, "at": at, "by": e["actor"]})
        elif k == "COM_EFFORT_DECLARED":
            s["efforts"].append({**p, "at": at, "by": e["actor"]})
        elif k == "COM_DISPUTE_RECORDED":
            s["disputes"][p["dispute_id"]] = {**p, "at": at, "by": e["actor"], "appeals": [], "resolution": None}
        elif k == "COM_APPEAL_RECORDED" and p["dispute_id"] in s["disputes"]:
            s["disputes"][p["dispute_id"]]["appeals"].append({**p, "at": at, "by": e["actor"]})
        elif k == "COM_DISPUTE_RESOLVED" and p["dispute_id"] in s["disputes"]:
            s["disputes"][p["dispute_id"]]["resolution"] = {**p, "at": at, "by": e["actor"]}
        elif k == "PRC_SESSION_OPENED" and p.get("practice_minutes_reserved"):
            s["practice_reserved"][p["period_id"]] = s["practice_reserved"].get(p["period_id"], 0) + p["practice_minutes_reserved"]
    _quarantine(s)
    return s


def _quarantine(s: dict):
    """Effective quarantine: an UNRESOLVED (or upheld) authorized dispute on a source root, a claim, a packet, or anything a
    packet declares it derives from. The task's own state underneath is untouched, so lifting the dispute restores it."""
    live = [d for d in s["disputes"].values() if d["resolution"] is None or d["resolution"]["outcome"] == "UPHELD"]
    for g in s["groups"].values():
        hits = []
        derived = {x for pid in g["packets"] for x in s["packets"][pid]["derived_from"]}
        for d in live:
            t = d["target"]
            if (d["target_type"] == "source" and (t in g["source_roots"] or t in g["unknown_roots"] or t in derived)) or (d["target_type"] == "claim" and t == g["claim"]["claim_id"]) \
                    or (d["target_type"] == "packet" and (t in g["packets"] or t in derived)):
                hits.append(d["dispute_id"])
        g["quarantined_by"] = hits


def capacity(s: dict, period_id: str | None = None) -> dict:
    pid = period_id or s["period"]; b = s["budgets"].get(pid)
    if b is None:
        return {"period_id": pid, "configured": False}
    reserved = sum(g["reservation"]["minutes"] for g in s["groups"].values() if g["reservation"] and g["reservation"]["period_id"] == pid)
    consumed = sum(g["consumed_minutes"] for g in s["groups"].values() if g["period_consumed"] == pid)
    used = reserved + consumed; practice_used = s["practice_reserved"].get(pid, 0)
    return {"period_id": pid, "configured": True, "review_minutes": b["review_minutes"], "reserved": reserved, "consumed": consumed, "remaining": max(0, b["review_minutes"] - used),
            "overrun": max(0, used - b["review_minutes"]), "practice_minutes": b["practice_minutes"], "practice_reserved": practice_used, "practice_remaining": max(0, b["practice_minutes"] - practice_used),
            "practice_overrun": max(0, practice_used - b["practice_minutes"]), "contributor_packet_cap": b["contributor_packet_cap"], "max_open_tasks": b["max_open_tasks"], "revisions": b["revisions"]}


# ------------------------------------------------------------------ administration
def set_budget(ws: Workspace, principal, *, period_id: str, review_minutes: int, practice_minutes: int, contributor_packet_cap: int, max_open_tasks: int, op_id: str) -> dict:
    authz.require(principal, "admin"); core.ident(period_id, "period id")
    for name, v, lo, hi in (("review minutes", review_minutes, 0, 100000), ("practice minutes", practice_minutes, 0, 100000), ("contributor packet cap", contributor_packet_cap, 1, 1000), ("maximum open tasks", max_open_tasks, 1, 5000)):
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise ModuleError("E_BUDGET", f"{name}: a whole number from {lo} to {hi}")
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "COM_BUDGET_SET":
            return done
        s = state(ws, evs=evs); new_period = s["period"] is not None and s["period"] != period_id
        ev, _ = ws._append_unlocked("COM_BUDGET_SET", None, {"period_id": period_id, "review_minutes": review_minutes, "practice_minutes": practice_minutes, "contributor_packet_cap": contributor_packet_cap,
                                    "max_open_tasks": max_open_tasks, "note": "a change never rewrites recorded consumption; a cut below it shows as an overrun and stops new reservations"},
                                    op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
        if new_period:                                                       # rollover: unfinished work returns to the queue with its history and observed seconds; nothing is erased
            for i, g in enumerate(sorted(s["groups"].values(), key=lambda g: g["group_id"])):
                if g["state"] in HOLDING:
                    _transition(ws, g, "QUEUED", principal, f"{op_id}:roll{i}", reason=f"ROLLOVER from period {s['period']}: reservation released there; re-reserve in {period_id}", period_id=period_id)
        return ev


def _transition(ws, g, to, principal, op_id, *, reason, period_id, reservation=0, assignee=None, lease_until=None):
    if (g["state"], to) not in TRANSITIONS:
        raise ModuleError("E_TRANSITION", f"a task cannot go from {g['state']} to {to}")
    return ws._append_unlocked("COM_TASK_TRANSITION", None, {"group_id": g["group_id"], "from": g["state"], "to": to, "reason": reason[:300], "period_id": period_id, "reservation_minutes": reservation,
                               "assignee": assignee, "lease_until": lease_until}, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))[0]


# ------------------------------------------------------------------ admission
def _admit_packet(ws, evs, s, principal, row: dict, admission: dict, op_id: str) -> dict:
    cap = capacity(s)
    if not cap["configured"]:
        raise ModuleError("E_NOT_CONFIGURED", "an administrator sets a review budget (period, review and practice minutes, contributor cap) first")
    me = principal["principal_id"]; now = core.now()
    mine = [p for p in s["packets"].values() if p["submitter"] == me and p["period_id"] == cap["period_id"]]
    if len(mine) >= cap["contributor_packet_cap"]:
        raise ModuleError("E_CONTRIBUTOR_CAP", f"{me!r} reached the contributor cap of {cap['contributor_packet_cap']} packets for period {cap['period_id']}; the cap counts the authenticated principal, not a display name")
    if len([p for p in mine if core.parse_time(p["recorded_at"]) > now - timedelta(minutes=1)]) >= RATE_PER_MINUTE:
        raise ModuleError("E_RATE", f"more than {RATE_PER_MINUTE} submissions in a minute")
    if len(s["packets"]) >= MAX_PACKETS:
        raise ModuleError("E_STORAGE_BOUND", f"the queue holds its maximum of {MAX_PACKETS} packets")
    ref = core.claim_ref(ws, row["claim_id"])
    if row.get("claim_version_digest") and row["claim_version_digest"] != ref["version_digest"]:
        versions = {v["claim"].get("_digest") for v in ws.claim_state(row["claim_id"])["versions"]}
        if row["claim_version_digest"] not in versions:
            raise ModuleError("E_CLAIM_VERSION", "the packet names a claim-version digest that this workspace never recorded")
        ref = {**ref, "version_digest": row["claim_version_digest"], "note": "an earlier version of the claim"}
    known = core.source_ids(ws); roots = sorted(set(row.get("source_roots") or ref["source_roots"]))
    unknown = [r for r in roots if r not in known]; roots = [r for r in roots if r in known]
    ancestry = "UNKNOWN" if (row.get("ancestry") == "UNKNOWN" or unknown or not roots) else "KNOWN"
    claim = {"claim_id": ref["claim_id"], "version_digest": ref["version_digest"], "contract_digest": ref["contract_digest"], "contract": ref["contract"]}
    gid = group_id(claim, roots, ancestry)
    if gid not in s["groups"] and sum(1 for g in s["groups"].values() if g["state"] in OPEN_STATES) >= cap["max_open_tasks"]:
        raise ModuleError("E_QUEUE_BOUND", f"the queue already holds its maximum of {cap['max_open_tasks']} open tasks")
    payload = {"packet_id": core.next_id(evs, "COM_PACKET_SUBMITTED", "PK", "packet_id"), "client_packet_id": row.get("packet_id"), "submitter": me, "period_id": cap["period_id"], "claim": claim,
               "source_roots": roots, "unknown_roots": unknown, "ancestry": ancestry, "kind": row.get("kind", "SUMMARY"), "derived_from": list(row.get("derived_from") or []), "group_id": gid,
               "proposed_cost_minutes": int(row.get("proposed_cost_minutes") or DEFAULT_COST_MINUTES), "submitter_asserts_withdrawn": bool(row.get("asserts_withdrawn")), "admission": admission,
               "duplicate_of_group": gid in s["groups"], "note": "a proposal and an assertion by the submitter change neither the group's scheduling cost nor its handling"}
    ev, _ = ws._append_unlocked("COM_PACKET_SUBMITTED", None, payload, op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))
    return ev


def submit_direct(ws: Workspace, principal, *, claim_id: str, kind: str, ancestry: str, derived_from: list, proposed_cost_minutes: int, asserts_withdrawn: bool, client_packet_id: str | None, op_id: str) -> dict:
    """A packet that REFERENCES objects already in this workspace (no external bytes): admission label DIRECT_REFERENCE."""
    authz.require(principal, "submit")
    if kind not in ("PRIMARY", "SUMMARY") or ancestry not in ("KNOWN", "UNKNOWN"):
        raise ModuleError("E_PACKET", "kind: PRIMARY or SUMMARY; ancestry: KNOWN or UNKNOWN")
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "COM_PACKET_SUBMITTED":
            return done
        s0 = state(ws, evs=evs); known_refs = set(core.source_ids(ws)) | set(s0["packets"])
        unknown = [x for x in derived_from if x not in known_refs]
        if unknown:
            raise ModuleError("E_UNKNOWN_LINEAGE", "derived-from names something that is neither a registered source nor a packet of this queue: " + ", ".join(map(str, unknown))[:200])
        row = {"claim_id": claim_id, "kind": kind, "ancestry": ancestry, "derived_from": [core.ident(x, "derived from") for x in derived_from][:8], "proposed_cost_minutes": proposed_cost_minutes,
               "asserts_withdrawn": asserts_withdrawn, "packet_id": client_packet_id}
        return _admit_packet(ws, evs, state(ws, evs=evs), principal, row, {"route": "DIRECT_REFERENCE", "shd_decision_id": None}, op_id)


def intake_from_shield(ws: Workspace, principal, decision_id: str, *, op_id: str) -> list:
    """Packets from an SHD-admitted bundle (purpose com.packets). The approval is re-validated INSIDE this commit: a bundle
    refused by SHD, or admitted under an approval since revoked or expired, reaches no queue."""
    authz.require(principal, "submit")
    with ws._locked():
        evs = ws.load()["events"]; typed = shield.require_current(ws, evs, decision_id, "com.packets"); out = []
        for i, row in enumerate(typed["payload"]["packets"]):
            evs = ws.load()["events"]; done = core.prior(evs, f"{op_id}:{i + 1}")
            out.append(done if done is not None else _admit_packet(ws, evs, state(ws, evs=evs), principal, row, {"route": "SHD_ADMITTED", "shd_decision_id": decision_id}, f"{op_id}:{i + 1}"))
        return out


# ------------------------------------------------------------------ scheduling authority, allocation, work
def set_cost(ws: Workspace, principal, *, group_id_: str, minutes: int, rule: str, op_id: str) -> dict:
    if principal is None or not ({"review", "admin"} & set(principal["caps"])):
        raise ModuleError("E_FORBIDDEN", "setting a scheduling cost needs the review or admin capability; a submitter's estimate stays a proposal")
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 2400:
        raise ModuleError("E_COST", "minutes: 1 to 2400")
    with ws._locked():
        g = state(ws)["groups"].get(group_id_)
        if g is None:
            raise ModuleError("E_UNKNOWN", "no such group")
        if g["reservation"]:
            raise ModuleError("E_RESERVED", "the cost of a task that holds a reservation is changed after it returns to the queue")
        return ws._append_unlocked("COM_COST_SET", None, {"group_id": group_id_, "minutes": minutes, "previous_minutes": g["cost_minutes"], "rule": core.text(rule, "estimation rule", maxlen=300)},
                                   op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))[0]


def plan(s: dict, now=None) -> dict:
    """Read-only: which queued tasks the remaining review capacity admits, and why the others wait. Order: urgent overrides,
    then oldest first. A task that does not fit is skipped so that smaller ones proceed; once the OLDEST waiting task is aged
    (older than AGED_AFTER_HOURS or skipped three times) the remaining capacity is HELD for it; a task larger than the whole
    budget is escalated instead of blocking anything. No rule creates capacity."""
    now = now or core.now(); cap = capacity(s)
    if not cap["configured"]:
        return {"capacity": cap, "selected": [], "deferred": []}
    left = 0 if cap["overrun"] else cap["remaining"]; sel, deferred, hold = [], [], None
    waiting = sorted((g for g in s["groups"].values() if g["state"] in ("QUEUED", "DEFERRED")), key=lambda g: (not g["urgent"], g["first_at"]))
    for g in waiting:
        age_h = (now - core.parse_time(g["first_at"])).total_seconds() / 3600; aged = age_h >= AGED_AFTER_HOURS or g["skips"] >= 3
        row = {"group_id": g["group_id"], "cost_minutes": g["cost_minutes"], "age_hours": round(age_h, 1), "urgent": g["urgent"], "aged": aged}
        if g["quarantined_by"]:
            deferred.append({**row, "reason": "QUARANTINED by " + ", ".join(g["quarantined_by"]) + " — a handling state pending resolution, not a verdict"})
        elif cap["overrun"]:
            deferred.append({**row, "reason": f"BUDGET_OVERRUN: recorded use exceeds the budget by {cap['overrun']} minutes; no new reservation until an administrator changes the budget"})
        elif g["cost_minutes"] > cap["review_minutes"]:
            deferred.append({**row, "reason": f"OVERSIZED_FOR_BUDGET: {g['cost_minutes']} minutes exceed the whole period budget ({cap['review_minutes']}); escalated to the administrator (split the work or change the budget)"})
        elif hold is not None:
            deferred.append({**row, "reason": f"HELD: remaining capacity is kept for aged task {hold}"})
        elif g["cost_minutes"] <= left:
            sel.append(row); left -= g["cost_minutes"]
        else:
            deferred.append({**row, "reason": ("URGENT_WAITING_FOR_CAPACITY" if g["urgent"] else "NO_REMAINING_CAPACITY") + f": needs {g['cost_minutes']}, {left} left" + ("; aged — smaller tasks now wait behind it" if aged else "")})
            if aged:
                hold = g["group_id"]
    return {"capacity": cap, "selected": sel, "deferred": deferred, "unspent_after_plan": left}


def assign(ws: Workspace, principal, group_id_: str, *, op_id: str) -> dict:
    """Reserve the group's scheduling cost and take the task. Decided and appended under the lock: no double spend."""
    authz.require(principal, "review")
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "COM_TASK_TRANSITION":
            return done
        s = state(ws, evs=evs); g = s["groups"].get(group_id_)
        if g is None:
            raise ModuleError("E_UNKNOWN", "no such group")
        authz.conflict(principal, g["contributors"], "contributed a packet to this group and cannot review it")
        p = plan(s); ok = next((r for r in p["selected"] if r["group_id"] == group_id_), None)
        if ok is None:
            why = next((r["reason"] for r in p["deferred"] if r["group_id"] == group_id_), f"the task is {g['state']}")
            if g["state"] == "QUEUED" and not g["quarantined_by"]:
                _transition(ws, g, "DEFERRED", principal, op_id + ":defer", reason="SKIPPED " + why, period_id=s["period"])
            raise ModuleError("E_NO_CAPACITY", why)
        lease = (core.now() + timedelta(minutes=LEASE_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return _transition(ws, g, "ASSIGNED", principal, op_id, reason="reserved by the assignee", period_id=s["period"], reservation=g["cost_minutes"], assignee=principal["principal_id"], lease_until=lease)


def work(ws: Workspace, principal, group_id_: str, action: str, *, note: str = "", op_id: str) -> dict:
    """start | pause | resume | finish | release | cancel. Observed seconds accrue between ACTIVE transitions (server clock)."""
    to = {"start": "ACTIVE", "pause": "PAUSED", "resume": "ACTIVE", "finish": "COMPLETED", "release": "QUEUED", "cancel": "CANCELED"}.get(action)
    if to is None:
        raise ModuleError("E_ACTION", "action: start, pause, resume, finish, release or cancel")
    if principal is None or not ({"review", "admin"} & set(principal["caps"])):
        raise ModuleError("E_FORBIDDEN", "review work needs the review capability (cancel: review or admin)")
    with ws._locked():
        evs = ws.load()["events"]; done = core.prior(evs, op_id)
        if done is not None and done["kind"] == "COM_TASK_TRANSITION":
            return done
        s = state(ws, evs=evs); g = s["groups"].get(group_id_)
        if g is None:
            raise ModuleError("E_UNKNOWN", "no such group")
        if action != "cancel" and g["assignee"] != principal["principal_id"]:
            raise ModuleError("E_FORBIDDEN", "only the assignee works on a task; an administrator or reviewer may cancel it")
        if action == "cancel" and g["assignee"] not in (None, principal["principal_id"]) and "admin" not in principal["caps"]:
            raise ModuleError("E_FORBIDDEN", "cancelling another reviewer's task needs the admin capability")
        if g["quarantined_by"] and action in ("start", "resume", "finish"):
            raise ModuleError("E_QUARANTINED", "the group is quarantined by " + ", ".join(g["quarantined_by"]) + "; resolve or appeal the dispute first")
        res = g["reservation"] or {}
        return _transition(ws, g, to, principal, op_id, reason=f"{action}: {core.text(note, 'note', maxlen=250, required=action in ('finish', 'cancel'))}", period_id=s["period"],
                           reservation=res.get("minutes", 0), assignee=g["assignee"] if to in ("ACTIVE", "PAUSED") else None, lease_until=g["lease_until"] if to in ("ACTIVE", "PAUSED") else None)


def recover_leases(ws: Workspace, principal, *, op_id: str) -> list:
    """After a crash, a restart or an abandoned session: tasks whose lease ended return to the queue with their observed
    seconds and history; their reservations are released."""
    if principal is None or not ({"review", "admin"} & set(principal["caps"])):
        raise ModuleError("E_FORBIDDEN", "lease recovery needs the review or admin capability")
    out = []
    with ws._locked():
        s = state(ws); now = core.now()
        for i, g in enumerate(sorted(s["groups"].values(), key=lambda g: g["group_id"])):
            if g["state"] in HOLDING and g["lease_until"] and core.parse_time(g["lease_until"]) <= now:
                out.append(_transition(ws, g, "QUEUED", principal, f"{op_id}:{i}", reason=f"LEASE_EXPIRED at {g['lease_until']} (assignee {g['assignee']}); partial work kept", period_id=s["period"]))
    return out


def declare_effort(ws: Workspace, principal, *, group_id_: str, minutes: int, category: str, op_id: str) -> dict:
    if principal is None or not ({"review", "admin"} & set(principal["caps"])):
        raise ModuleError("E_FORBIDDEN", "declaring effort needs the review or admin capability")
    if category not in EFFORT_CATEGORIES or isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= 2400:
        raise ModuleError("E_EFFORT", f"minutes 1–2400 and a category from {', '.join(EFFORT_CATEGORIES)}")
    if group_id_ not in state(ws)["groups"]:
        raise ModuleError("E_UNKNOWN", "no such group")
    return core.append(ws, "COM_EFFORT_DECLARED", {"group_id": group_id_, "minutes": minutes, "category": category, "declared_by": principal["principal_id"],
                       "meaning": "a manual declaration; neither it nor a server timer proves attentive human work"}, op_id=op_id, principal=principal)[0]


def override_urgent(ws: Workspace, principal, *, group_id_: str, reason: str, op_id: str) -> dict:
    authz.require(principal, "admin")
    if group_id_ not in state(ws)["groups"]:
        raise ModuleError("E_UNKNOWN", "no such group")
    return core.append(ws, "COM_OVERRIDE_RECORDED", {"group_id": group_id_, "reason": core.text(reason, "reason", maxlen=500), "effect": "ordered first; creates no capacity"}, op_id=op_id, principal=principal)[0]


# ------------------------------------------------------------------ disputes, appeals, resolution
def record_dispute(ws: Workspace, principal, *, target_type: str, target: str, dispute_type: str, reason: str, op_id: str) -> dict:
    if principal is None or not ({"review", "admin"} & set(principal["caps"])):
        raise ModuleError("E_FORBIDDEN", "recording a dispute, withdrawal or source correction that changes queue handling needs the review or admin capability; a submitter's assertion is kept on its packet and quarantines nothing")
    if target_type not in ("source", "claim", "packet") or dispute_type not in ("DISPUTED", "WITHDRAWN", "SOURCE_CORRECTED"):
        raise ModuleError("E_DISPUTE", "target type: source, claim or packet; type: DISPUTED, WITHDRAWN or SOURCE_CORRECTED")
    with ws._locked():
        evs = ws.load()["events"]; s = state(ws, evs=evs); core.ident(target, "target")
        exists = {"claim": target in ws.status()["claims"], "packet": target in s["packets"],
                  "source": target in core.source_ids(ws) or any(target in g["source_roots"] + g["unknown_roots"] for g in s["groups"].values()) or any(target in p_["derived_from"] for p_ in s["packets"].values())}[target_type]
        if not exists:                                                            # a selected option or a hidden field is not authority: the named object must exist in THIS workspace
            raise ModuleError("E_UNKNOWN_TARGET", f"{target_type} {target!r} is not an object of this workspace (a claim frozen here, a source registered or named by a packet here, or a packet of this queue)")
        return ws._append_unlocked("COM_DISPUTE_RECORDED", None, {"dispute_id": core.next_id(evs, "COM_DISPUTE_RECORDED", "DP", "dispute_id"), "target_type": target_type, "target": core.ident(target, "target"),
                                   "dispute_type": dispute_type, "reason": core.text(reason, "reason", maxlen=1000), "recorded_by": principal["principal_id"],
                                   "meaning": "affected groups are quarantined (a handling state, not a finding of misconduct); source bytes and earlier reviews are untouched; an appeal and a resolution are new events"},
                                   op_id=op_id, observed_at=None, source_available_as_of=None, actor=core.actor_of(principal))[0]


def appeal(ws: Workspace, principal, *, dispute_id: str, reason: str, op_id: str) -> dict:
    if principal is None:
        raise ModuleError("E_SIGN_IN", "sign in to appeal")
    if dispute_id not in state(ws)["disputes"]:
        raise ModuleError("E_UNKNOWN", "no such dispute")
    return core.append(ws, "COM_APPEAL_RECORDED", {"dispute_id": dispute_id, "reason": core.text(reason, "reason", maxlen=1000), "appellant": principal["principal_id"]}, op_id=op_id, principal=principal)[0]


def resolve_dispute(ws: Workspace, principal, *, dispute_id: str, outcome: str, reason: str, op_id: str) -> dict:
    authz.require(principal, "admin")
    if outcome not in ("UPHELD", "LIFTED"):
        raise ModuleError("E_OUTCOME", "outcome: UPHELD or LIFTED")
    d = state(ws)["disputes"].get(dispute_id)
    if d is None:
        raise ModuleError("E_UNKNOWN", "no such dispute")
    authz.conflict(principal, [d["recorded_by"]] if d["appeals"] else [], "recorded this dispute and cannot decide the appeal against it")
    return core.append(ws, "COM_DISPUTE_RESOLVED", {"dispute_id": dispute_id, "outcome": outcome, "reason": core.text(reason, "reason", maxlen=1000), "resolved_by": principal["principal_id"],
                       "meaning": "the dispute and its appeals stay in the record; LIFTED ends the quarantine from now, and a new dispute can be recorded later"}, op_id=op_id, principal=principal)[0]


# ------------------------------------------------------------------ dashboard and the controlled FIFO comparison
def dashboard(ws: Workspace, as_of: str | None = None) -> dict:
    s = state(ws, as_of=as_of); now = core.parse_time(core.norm_time(as_of, "as of")) if as_of else core.now(); groups = list(s["groups"].values())
    root_use: dict = {}
    for g in groups:
        for r in g["source_roots"]:
            root_use.setdefault(r, []).append(g["group_id"])
    ages = sorted((now - core.parse_time(g["first_at"])).total_seconds() / 3600 for g in groups if g["state"] in OPEN_STATES)
    declared: dict = {}
    for e in s["efforts"]:
        declared[e["category"]] = declared.get(e["category"], 0) + e["minutes"]
    upstream = {}
    for g in groups:
        st = ws.claim_state(g["claim"]["claim_id"]); flags = []
        if st is not None:
            if st.get("withdrawn"):
                flags.append("CLAIM_WITHDRAWN in the workbench")
            if st["versions"][-1]["claim"].get("_digest") != g["claim"]["version_digest"]:
                flags.append("NEWER_CLAIM_VERSION exists")
            if any(a.get("applied") or a.get("later") for a in (st.get("availability") or {}).values() if isinstance(a, dict)):
                flags.append("SOURCE_TIME_CORRECTED")                          # a linked availability correction exists on a source this claim cites (the registration itself is unchanged)
        upstream[g["group_id"]] = flags
    return {"as_of": as_of, "capacity": capacity(s), "plan": plan(s, now), "unique_claims": len({g["claim"]["claim_id"] for g in groups}), "groups": len(groups), "packets": len(s["packets"]),
            "duplicate_volume": len(s["packets"]) - len(groups), "shared_roots": {r: gs for r, gs in root_use.items() if len(gs) > 1}, "unknown_ancestry_groups": sum(1 for g in groups if g["ancestry"] == "UNKNOWN"),
            "by_state": {st_: sum(1 for g in groups if g["state"] == st_) for st_ in OPEN_STATES + ("COMPLETED", "CANCELED")}, "quarantined": sum(1 for g in groups if g["quarantined_by"]),
            "backlog_age_hours": {"oldest": round(ages[-1], 1) if ages else 0, "median": round(ages[len(ages) // 2], 1) if ages else 0, "open_tasks": len(ages)},
            "effort": {"estimated_minutes_completed": sum(g["consumed_minutes"] for g in groups), "server_observed_seconds": sum(g["observed_seconds"] for g in groups), "declared_minutes_by_category": declared,
                       "note": "three different numbers; document volume is not productivity and a timer is not proof of attentive work"},
            "upstream_flags": upstream, "state": s}


def simulate(arrivals: list, review_minutes: int) -> dict:
    """A CONTROLLED SIMULATION on identical synthetic arrivals and effort assumptions: (a) plain FIFO, one task per packet;
    (b) FIFO with exact de-duplication; (c) this queue's rule (exact groups, fit-smaller, aged hold). `arrivals` =
    [{'key','minutes'}] in arrival order. It shows arithmetic on assumptions, never human productivity, error rates or fairness."""
    def run(tasks, fit_smaller):
        left, done, spent_dupes, waited = review_minutes, [], 0, None
        seen = set()
        for i, t in enumerate(tasks):
            if t["minutes"] <= left:
                left -= t["minutes"]; done.append(t["key"])
                if t["key"] in seen:
                    spent_dupes += t["minutes"]
                seen.add(t["key"])
            else:
                waited = i if waited is None else waited
                if not fit_smaller:
                    break
        return {"completed_tasks": len(done), "completed_unique_keys": len(set(done)), "minutes_spent_on_duplicates": spent_dupes, "minutes_unspent": left, "first_blocked_position": waited}
    seen, dedup = set(), []
    for a in arrivals:
        if a["key"] not in seen:
            seen.add(a["key"]); dedup.append(a)
    return {"label": "controlled simulation on synthetic arrivals; establishes nothing about human productivity, error reduction or fairness", "arrivals": len(arrivals), "unique_keys": len(seen),
            "review_minutes": review_minutes, "plain_fifo": run(arrivals, False), "fifo_exact_dedup": run(dedup, False), "commons_rule": run(dedup, True)}
