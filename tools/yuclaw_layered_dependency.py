#!/usr/bin/env python3
"""
Layered Evidence Dependency Spec — pre-registered protocol (v1).
LOCKED WITHOUT COMPUTING (sleeping registration, order of 2026-08-06 P0-A).
===========================================================================
This module exists to LOCK the specification before any computation. It
deliberately contains NO analysis code (zero research runs, zero result
cells, zero statistical estimation — the order's definition). The first
computable read (SMH lens ONLY, owner-slotted date) must be implemented
behind run() below, which refuses to execute unless this exact spec (by
hash) is LOCKED in registry/protocols.jsonl AND the owner date slot is
filled and satisfied.

Citation lineage: witness methodology per the methodology reviewer's
published work (arXiv:2408.07818) + three-AI convergent review.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

METHOD_SPEC = """
LAYERED EVIDENCE DEPENDENCY SPEC (v1, locked 2026-08-07)

PURPOSE
Pooled statistics on this platform treat evidence units as if independent.
This spec locks, before any computation, the method by which cross-unit
dependence is made explicit, decomposed, and printed — so that every
pooled statistic can be read alongside its dependence anatomy and an
effective-independent-evidence count a stranger can recompute from the
printed page alone.

PIPELINE (fixed order)
filings -> events -> layered stories -> cross-story dependency graph ->
effective independent evidence -> conclusion contribution anatomy.

NODES
issuers, events, stories. An event is a persisted accepted row of the
evidence store (event_id, issuer, event date, source accession, source
URL, verified excerpt). A story is a maximal connected component of
events under the union of extracted-from-shared-filing edges and
same-issuer-continuation edges (constructed rules below); stories are
derived deterministically from persisted artifacts, never model opinions.

TEMPORAL LAYER CONVENTION
Every edge carries exactly one temporal layer: the U.S. trading day
(the same trading calendar the daily snapshots use) of the LATER of its
two endpoints; for edges joining same-day endpoints, that shared trading
day. Non-trading-day artifact dates roll forward to the next trading day.

EDGE VOCABULARY — LOCKED TIER
(Amendment A-1: only edge types whose deterministic construction rule is
written IN FULL here are locked; this hash is the lock. The first read
runs on this tier alone.)

 1. extracted-from — event -> filing. Exists iff the event's persisted
    source accession number equals the filing's accession number.
 2. same-story — event <-> event. Exists iff both events belong to the
    same story (story := maximal connected component under rules 1-shared
    -filing and 3). Printed for anatomy; redundant with the construction.
    Two events share a filing iff their persisted accessions are equal.
 3. same-issuer-continuation — event -> event. Exists iff both events
    have the same issuer and the later event's date is within 5 trading
    days strictly after the earlier event's date.
 4. same-day — event <-> event. Exists iff the two events' dates fall on
    the same trading day (any issuers).
 5. shared-source — event <-> event. Exists iff the two events' persisted
    normalized source URLs are byte-identical while their accession
    numbers differ.
 6. shared-exhibit — event <-> event. Exists iff the two events' persisted
    evidence objects reference an identical (accession, exhibit-id) pair.
 7. cascade-parent — event -> event. Exists iff the child event's
    persisted cascade record (C8 cascade engine artifacts) lists the
    parent event as its cascade origin.
 8. supports — event -> event. Exists iff a persisted rule-detected
    evidence relation of type SUPPORTS links the two events in the
    evidence store (read as stored; never recomputed at read time).
 9. contradicts — event -> event. Exists iff a persisted rule-detected
    evidence relation of type CONTRADICTS/TENSION links the two events.
10. supersedes — event -> event. Exists iff the later event's filing is
    the EDGAR amendment of the earlier event's filing: same issuer, form
    type equal to the earlier form plus "/A", per the persisted intake
    linkage.
11. affects-component — event -> component (C1..C8). Exists iff the
    event's persisted component-attribution record lists that component
    with a nonzero weight at scoring time.
12. changes-label — event -> issuer-day. Exists iff the issuer's
    published signal label on the event's trading day differs from that
    issuer's label on the immediately preceding trading day's persisted
    snapshot, and the event is dated that trading day.
13. tested-by — event -> registry run. Exists iff a recorded run entry in
    registry/protocols.jsonl has a data window containing the event's
    trading day and a protocol scoped to a universe containing the
    event's issuer.
14. matured-into — event -> forward outcome. Exists iff the persisted
    forward ledger contains a completed k-day outcome row for that
    (issuer, trading day), any k.
15. excluded-from — event -> surface. Exists iff a persisted exclusion
    record (tier boundary, corporate-action exclusion, arm exclusion)
    names that event or its issuer-day together with the excluding
    surface.
16. truncated-by — event/object -> truncation site. Exists iff a
    Truncation & Error Budget ledger site (companion spec, same order)
    records the event or its evidence object among its dropped/capped
    units in a persisted drop record.

EDGE VOCABULARY — FUTURE-EXTENSION TIER (outside this hash; candidates
only; admissible solely by registered addendum carrying full rule text;
named in this module below the spec, never in it).

SEVERITY STATISTIC
For each story-cluster (connected component of the cross-story dependency
graph restricted to locked-tier edges), build the cluster's issuer-event
graph: vertices = the cluster's issuers and events; edges = the
deduplicated undirected projection of all locked-tier edges between those
vertices. Severity = the circuit rank r = |E| - |V| + c (c = connected
components of that projection), PRINTED PER CLUSTER.

STRUCTURE CLASSES (descriptive labels only, no scoring consequence):
tree (r = 0); single-cycle (r = 1); multi-cycle (r >= 2 and below the
clique threshold); clique-like (|V| >= 4 and |E| >= 0.6 * |V|*(|V|-1)/2).

OUTPUTS PER POOLED STATISTIC
For every pooled statistic S published with a dependency anatomy:
  (a) the as-if-independent term: S's variance V_indep computed treating
      all units as independent (sum of w_i^2 * (x_i - xbar)^2);
  (b) one correction term PER LOCKED EDGE TYPE t, with magnitude:
      C_t = sum over unordered same-cluster unit pairs (i,j) whose
      highest-precedence connecting edge type is t, of
      2 * w_i * w_j * (x_i - xbar) * (x_j - xbar).
      Precedence = the enumeration order 1..16 above (a pair contributes
      to exactly one C_t; precedence is a double-counting guard only —
      every edge remains in the graph and in the printed anatomy);
  (c) N_eff DERIVED from the printed decomposition and never asserted:
      N_eff = N_raw * V_indep / (V_indep + sum_t C_t), computed from the
      printed values of (a) and (b) — a stranger recomputes it from the
      page with this formula, which is printed beside it. Signed C_t are
      printed as signed; if the derived N_eff exceeds N_raw it is capped
      at N_raw for display with the cap disclosed on the same line.

PERSISTENCE
Cluster membership STRUCTURE is stored per day (cluster id -> member node
ids + typed edge list, per trading day), never the scalar N_eff. Scalars
are always recomputed from stored structure by the printed formula.

SUPERSESSION RULE (in-spec)
Currently printed N_eff values (and any effective-independence language
already on the site) STAND until a registered v2 read completes. Any
change ships as a registry supersession with lineage to this protocol —
never as an in-place edit.

PRE-REGISTERED ADOPTION PROTOCOL (locked now, answered at the read):
  Q1. Does the read change any effective-independent-evidence judgment?
  Q2. Does it explain any interval where v1 clustering stays optimistic?
  Q3. Does it surface cross-story dependence v1 missed?
  Q4. Does it change any headline maturity label?
  Q5. Does a stranger understand the printed anatomy in ~3 minutes
      (guest-QA)?
Site-wide rollout only on favorable answers; otherwise the pilot prints
as its own inconclusive/negative read. No third option exists.

FIRST COMPUTABLE READ
SMH lens ONLY. Date: OWNER SLOT — unfilled at registration; suggested
after 2026-08-28 (Phase-A maturity); a date falling on the 8th of any
month is never valid. The guard below refuses to compute while the slot
is empty, before the slotted date arrives, on a slotted date violating
the never-the-8th constraint, or for any lens other than SMH.

COMPUTE DISCIPLINE
Registered BEFORE any computation (zero research runs, zero result
cells, zero statistical estimation at registration). Any edit to this
spec changes its hash and therefore requires supersession in the
registry — never amendment.
"""

# FUTURE-EXTENSION tier — outside the hash by construction (candidates
# only; each needs its own registered addendum with full rule text):
FUTURE_EDGE_CANDIDATES = [
    "supply-chain-link",
    "regulatory-common-cause",
    "management-transition",
    "shared-driver",
    # same-sector: a deterministic rule is available today (shared sector
    # label in the persisted universe sector map) but the locked tier was
    # enumerated at registration — admissible by addendum like the rest.
    "same-sector",
]

METHOD_HASH = hashlib.sha256(METHOD_SPEC.encode()).hexdigest()[:16]
PARAMS = {"first_read_lens": "SMH", "locked_edge_types": 16}
PROTOCOL_ID = hashlib.sha256(
    (METHOD_SPEC + json.dumps(PARAMS, sort_keys=True)).encode()).hexdigest()[:12]

# OWNER SLOT — fill with an ISO date to arm the first read. Filling this
# slot is an owner act; the METHOD_SPEC hash does not cover it, so arming
# does not require supersession. Constraints on the slotted value are
# in-spec and enforced below.
FIRST_READ_DATE: str | None = "2026-09-03"


def _registry_guard(pid: str) -> None:
    """REGISTRY-FIRST: refuse to compute unless the protocol is LOCKED in
    registry/protocols.jsonl (chain-verified on load). Fails closed when
    the registry file is absent."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    if str(root / "tools") not in sys.path:
        sys.path.insert(0, str(root / "tools"))
    from yuclaw_protocol_registry import Registry
    Registry(str(root / "registry" / "protocols.jsonl")).assert_registered(pid)


def _date_guard() -> None:
    """The order's early-refusal guard: empty slot, a slot on the 8th of
    any month, or a not-yet-arrived slot all refuse."""
    if FIRST_READ_DATE is None:
        raise RuntimeError(
            "Layered Evidence Dependency v1: OWNER SLOT for the first read "
            "date is unfilled — the guard refuses early (suggested: after "
            "2026-08-28 Phase-A maturity; never a date on the 8th).")
    slot = date.fromisoformat(FIRST_READ_DATE)
    if slot.day == 8:
        raise RuntimeError(
            f"Layered Evidence Dependency v1: slotted date {slot} falls on "
            f"the 8th — never valid, per the locked spec.")
    if date.today() < slot:
        raise RuntimeError(
            f"Layered Evidence Dependency v1: first read is slotted for "
            f"{slot}; today is earlier — the guard refuses early.")


# ===========================================================================
# FIRST COMPUTABLE READ — implementation (ORDER 2026-09-03B step 3).
# Transcribes the parent METHOD_SPEC (P) + registered Addendum A1
# (tools/A1_layered_dependency_v1.txt, chain kind=addendum, lineage to the
# protocol line). Every rule cites its source. READ_SCOPE = STRUCTURAL_ONLY.
# Nothing above this line was edited (METHOD_SPEC hash fc2779b55aee5f67).
# ===========================================================================
import os as _os
import re as _re
import subprocess as _subprocess
import sys as _sys
from datetime import datetime as _dt, timedelta as _td, timezone as _tz
from pathlib import Path as _Path

_ROOT = _Path(__file__).resolve().parents[1]
ADDENDUM_FILE = "tools/A1_layered_dependency_v1.txt"       # A1 (re-issue note)
CALENDAR_FILE = "v3/u350/market_calendar.py"               # A1.2
MEMBERSHIP_FILE = "v3/lab/etf_evidence.py"                 # A1.3
WINDOW_START_BOUND = "2026-07-03"                          # A1.4
READ_SCOPE = "STRUCTURAL_ONLY"                             # A1.0
N_EFF_PRINTED = "N_eff: PENDING — no pooled statistic designated (A1.7)"  # A1.7 verbatim
LABELS = ("STRUCTURE_PRINTED", "INSUFFICIENT", "NOT_EXECUTABLE")          # A1.8
EXECUTABLE_RULES = [1, 2, 3, 4, 5, 7, 11, 12, 14]          # A1.6 canonical field
ABSENT_RULES = [6, 8, 9, 10, 13, 15, 16]                   # A1.6 canonical field
EVENT_EDGE_RULES = [1, 2, 3, 4, 5, 7]                      # A1.5 executable event<->event among 1-10
ACCESSION_RE = _re.compile(r"/Archives/edgar/data/(\d+)/(\d{18})/")  # A1.1 locked regex
# RFC-3986 Appendix B split (A1.6 rule 5: "strict RFC-3986 split"; no urllib)
RFC3986_RE = _re.compile(r"^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?$")
OUT_DIR = _ROOT / "output" / "oie"
CANONICAL_NAME = "layered_dependency_first_read.json"
META_NAME = "layered_dependency_first_read.meta.json"
INPUTS_NAME = "layered_dependency_first_read.inputs.json"
MANIFEST_NAME = "layered_dependency_first_read.manifest.json"
DB_DSN = "dbname=yuclaw_events"                            # A1.1 store


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(rel: str) -> str:
    return _sha256_bytes((_ROOT / rel).read_bytes())


def _canonical_bytes(obj) -> bytes:
    """ORDER 03A 2b + A1.9: sorted keys, UTF-8, LF, fixed separators, no NaN."""
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=1,
                       allow_nan=False) + "\n").encode("utf-8")


def _now_utc() -> str:
    return _dt.now(_tz.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")


def _addendum_guard(reg):
    """A1.10: verify the A1 line hash before anything else. Returns the
    addendum line record (1-based line number, line_hash, payload)."""
    raw = (_ROOT / ADDENDUM_FILE).read_bytes()
    file_sha = _sha256_bytes(raw)
    hit = None
    for i, ln in enumerate(reg._lines, start=1):
        if ln["kind"] != "addendum":
            continue
        p = ln["payload"]
        if p["protocol_id"] == PROTOCOL_ID and p["method_hash"] == file_sha:
            hit = (i, ln["line_hash"], p)
    if hit is None:
        raise RuntimeError(
            f"Layered Evidence Dependency v1: Addendum A1 (sha256 {file_sha}) "
            f"is not registered on the chain for {PROTOCOL_ID} — refuse.")
    i, lh, p = hit
    if _sha256_bytes(p["text"].encode("utf-8")) != file_sha:
        raise RuntimeError("A1 embedded text does not hash to the file bytes")
    if p["parent_method_hash"] != METHOD_HASH:
        raise RuntimeError("A1 lineage does not point at this METHOD_HASH")
    body = json.dumps({"kind": "addendum", "payload": p,
                       "prev_hash": reg._lines[i - 1]["prev_hash"]},
                      sort_keys=True)
    if hashlib.sha256(body.encode()).hexdigest() != lh:
        raise RuntimeError("A1 line hash does not verify")
    return i, lh, p


# ---------------------------------------------------------------- calendar
class _Calendar:
    """A1.2: v3/u350/market_calendar.py adopted BY REGISTRATION."""

    def __init__(self):
        if str(_ROOT) not in _sys.path:
            _sys.path.insert(0, str(_ROOT))
        from v3.u350 import market_calendar as mc
        self.mc = mc
        self.NY = mc.NY
        lo, hi = mc.CALENDAR_RANGE
        self.lo, self.hi = lo, hi
        d, sessions = lo, []
        while d <= hi:
            if mc.is_session(d):
                sessions.append(d)
            d += _td(days=1)
        self.sessions = sessions
        self.index = {s: k for k, s in enumerate(sessions)}
        self.sha256 = _sha256_file(CALENDAR_FILE)

    def session_of(self, ts):
        """A1.2: EARLIEST session S with close(S) >= ts (America/New_York);
        boundary inclusive. Timestamps whose NY date lies outside the
        registered calendar range cannot map into any 2026-07..2027 window
        (session_of(ts) >= NY-date(ts); dates before the range map to a
        session <= the first 2026 session) — returned as None (out of
        window) without calling is_session outside its range."""
        ny = ts.astimezone(self.NY)
        d = ny.date()
        if d < self.lo or d > self.hi:
            return None
        while d <= self.hi:
            if self.mc.is_session(d) and self.mc.close_utc(d) >= ts:
                return d
            d += _td(days=1)
        return None

    def prev_session(self, s):
        k = self.index[s]
        return self.sessions[k - 1] if k > 0 else None


# ---------------------------------------------------------------- inputs
def _membership():
    """A1.3: ticker set of v3/lab/etf_evidence.SMH_HOLDINGS; 'SMH' excluded."""
    if str(_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_ROOT))
    from v3.lab import etf_evidence as ev
    tickers = sorted(set(ev.SMH_HOLDINGS.keys()) - {"SMH"})
    return tickers, ev.SMH_AS_OF, _sha256_file(MEMBERSHIP_FILE)


def _ts_out(ts):
    return None if ts is None else ts.astimezone(_tz.utc).isoformat()


def _ts_in(s):
    return None if s is None else _dt.fromisoformat(s)


def _freeze_inputs(cal, tickers, window_first, window_end):
    """4a: one REPEATABLE READ, read-only transaction over the three
    persisted artifacts named in A1.1 / A1.6 (rules 11, 12, 14). Projections
    carry only the columns the rules read. This is the first governed
    outcome access (T_access is stamped by the caller just before)."""
    import psycopg2
    import psycopg2.extras
    lo = _dt.combine(window_first - _td(days=10), _dt.min.time(), tzinfo=_tz.utc)
    hi = _dt.combine(window_end + _td(days=2), _dt.min.time(), tzinfo=_tz.utc)
    q_events = ("SELECT event_id, ticker, available_as_of, source_url, "
                "parent_event_id FROM public.events "
                "WHERE event_status = 'accepted' ORDER BY event_id")
    q_snaps = ("SELECT snapshot_id, ticker, signal_time, signal_label, "
               "evidence_event_ids, component_anatomy "
               "FROM public.signal_snapshots "
               "WHERE ticker = ANY(%s) AND signal_time >= %s AND signal_time < %s "
               "ORDER BY snapshot_id")
    q_track = ("SELECT snapshot_id, ticker, signal_date, "
               "(return_1d IS NOT NULL) AS k1, (return_5d IS NOT NULL) AS k5, "
               "(return_20d IS NOT NULL) AS k20 FROM public.track_record "
               "WHERE ticker = ANY(%s) AND signal_date >= %s AND signal_date <= %s "
               "ORDER BY ticker, signal_date, snapshot_id")
    conn = psycopg2.connect(DB_DSN)
    try:
        conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q_events)
            events = [{"event_id": r["event_id"], "ticker": r["ticker"],
                       "available_as_of": _ts_out(r["available_as_of"]),
                       "source_url": r["source_url"],
                       "parent_event_id": r["parent_event_id"]}
                      for r in cur.fetchall()]
            cur.execute(q_snaps, (tickers, lo, hi))
            snaps = []
            for r in cur.fetchall():
                ca = r["component_anatomy"] or {}
                snaps.append({
                    "snapshot_id": r["snapshot_id"], "ticker": r["ticker"],
                    "signal_time": _ts_out(r["signal_time"]),
                    "signal_label": r["signal_label"],
                    "evidence_event_ids": list(r["evidence_event_ids"] or []),
                    "component_evidence_ids": {
                        k: list((v or {}).get("evidence_ids") or [])
                        for k, v in sorted(ca.items()) if isinstance(v, dict)}})
            cur.execute(q_track, (tickers, window_first - _td(days=10),
                                  window_end + _td(days=2)))
            track = [{"snapshot_id": r["snapshot_id"], "ticker": r["ticker"],
                      "signal_date": r["signal_date"].isoformat(),
                      "k1": bool(r["k1"]), "k5": bool(r["k5"]),
                      "k20": bool(r["k20"])} for r in cur.fetchall()]
    finally:
        conn.close()
    return {"events": events, "snapshots": snaps, "track_record": track,
            "queries": {"events": q_events, "snapshots": q_snaps,
                        "track_record": q_track},
            "bounds": {"snapshots_signal_time": [_ts_out(lo), _ts_out(hi)],
                       "track_record_signal_date": [
                           (window_first - _td(days=10)).isoformat(),
                           (window_end + _td(days=2)).isoformat()]}}


# ---------------------------------------------------------------- rules
def _accession(url):
    """A1.1: locked regex; NONE when no match / null / empty."""
    if not url:
        return None
    m = ACCESSION_RE.search(url)
    if not m:
        return None
    d = m.group(2)
    return f"{d[0:10]}-{d[10:12]}-{d[12:18]}"


def _normalize_url(url):
    """A1.6 rule 5. Returns (state, value): ('NONE', None) | ('UNPARSED',
    None) | ('OK', normalized)."""
    if not url:
        return "NONE", None
    m = RFC3986_RE.match(url)
    if not m:
        return "UNPARSED", None
    scheme, authority = m.group(2), m.group(4)
    path, query = m.group(5) or "", m.group(7)
    if not scheme or authority is None or authority == "":
        return "UNPARSED", None          # relative / no host -> UNPARSED
    scheme = scheme.lower()
    host, port = authority, None
    if ":" in host:
        h, _, p = host.rpartition(":")
        if p.isdigit():
            host, port = h, p
    if not host:
        return "UNPARSED", None
    host = host.lower()
    default = {"http": "80", "https": "443"}.get(scheme)
    if port is not None and port == default:
        port = None
    if path.endswith("/"):
        path = path[:-1]                   # one trailing '/' removed
    out = f"{scheme}://{host}"
    if port is not None:
        out += f":{port}"
    out += path
    if query is not None:
        out += "?" + query                 # query retained byte-for-byte
    return "OK", out                       # fragment dropped


class _UF:
    def __init__(self, keys):
        self.p = {k: k for k in keys}

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if ra < rb:
            self.p[rb] = ra
        else:
            self.p[ra] = rb

    def components(self):
        groups = {}
        for k in sorted(self.p):
            groups.setdefault(self.find(k), []).append(k)
        return sorted(groups.values())


def _pair(a, b):
    return (a, b) if a < b else (b, a)


def _all_pairs(ids):
    ids = sorted(ids)
    return [(ids[i], ids[j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]


def _member_id(members):
    """A1.5: first 16 hex of sha256 of the sorted newline-joined event_ids."""
    return hashlib.sha256("\n".join(sorted(members)).encode("utf-8")).hexdigest()[:16]


def _structure_class(V, E, r):
    """A1.7: clique-like FIRST (integer arithmetic), else by r."""
    if V >= 4 and E >= (3 * V * (V - 1) + 9) // 10:   # ceil(0.6*V(V-1)/2)
        return "clique-like"
    if r == 0:
        return "tree"
    if r == 1:
        return "single-cycle"
    return "multi-cycle"


def _compute(inputs, cal, tickers, membership_sha, addendum_id, reg_utc):
    """The structural read. Pure function of (frozen inputs, calendar,
    membership, addendum id, registration timestamp)."""
    members = set(tickers)
    # --- window (A1.4)
    reg_ts = _dt.fromisoformat(reg_utc)
    reg_session = cal.session_of(reg_ts)
    if reg_session is None:
        raise RuntimeError("registration timestamp outside the calendar range")
    window_end = cal.prev_session(reg_session)
    if window_end is None or cal.mc.close_utc(window_end) > reg_ts:
        raise RuntimeError("window end is not a completed session")
    start_bound = date.fromisoformat(WINDOW_START_BOUND)
    window = [s for s in cal.sessions if start_bound <= s <= window_end]
    window_set = set(window)
    read_window = {"start_bound": WINDOW_START_BOUND,
                   "first_session": window[0].isoformat() if window else None,
                   "end_session": window_end.isoformat(),
                   "n_sessions": len(window),
                   "registration_session": reg_session.isoformat()}
    # --- eligibility (A1.4)
    inel = {"null_available_as_of": 0, "null_ticker": 0,
            "not_in_lens": 0, "out_of_window": 0}
    elig = []
    for row in inputs["events"]:
        if row["available_as_of"] is None:
            inel["null_available_as_of"] += 1
            continue
        if row["ticker"] is None:
            inel["null_ticker"] += 1
            continue
        if row["ticker"] not in members:
            inel["not_in_lens"] += 1
            continue
        s = cal.session_of(_ts_in(row["available_as_of"]))
        if s is None or s not in window_set:
            inel["out_of_window"] += 1
            continue
        elig.append({"event_id": row["event_id"], "ticker": row["ticker"],
                     "session": s, "source_url": row["source_url"],
                     "parent_event_id": row["parent_event_id"]})
    # --- identity (A1.1)
    ids = [e["event_id"] for e in elig]
    if any(i is None for i in ids) or len(set(ids)) != len(ids):
        return {"verdict": "NOT_EXECUTABLE", "reason": "event_id integrity"}, read_window
    elig.sort(key=lambda e: e["event_id"])
    by_id = {e["event_id"]: e for e in elig}
    # --- accession + URL (A1.1, A1.6 rule 5)
    unparsed = 0
    for e in elig:
        e["accession"] = _accession(e["source_url"])
        if e["accession"] is None:
            unparsed += 1
        e["url_state"], e["url_norm"] = _normalize_url(e["source_url"])
    # --- edges (rules 1, 3, 4, 5, 7 then 2)
    edges = {n: set() for n in EVENT_EDGE_RULES}
    grp = {}
    for e in elig:                                   # rule 1 (P + A1.1)
        if e["accession"] is not None:
            grp.setdefault(e["accession"], []).append(e["event_id"])
    for k in sorted(grp):
        edges[1].update(_all_pairs(grp[k]))
    grp = {}
    for e in elig:                                   # rule 3 (P + A1.2)
        grp.setdefault(e["ticker"], []).append(e)
    for t in sorted(grp):
        evs = sorted(grp[t], key=lambda e: (cal.index[e["session"]], e["event_id"]))
        for i in range(len(evs)):
            for j in range(i + 1, len(evs)):
                d = cal.index[evs[j]["session"]] - cal.index[evs[i]["session"]]
                if 1 <= d <= 5:
                    edges[3].add(_pair(evs[i]["event_id"], evs[j]["event_id"]))
    grp = {}
    for e in elig:                                   # rule 4 (P)
        grp.setdefault(e["session"], []).append(e["event_id"])
    for k in sorted(grp):
        edges[4].update(_all_pairs(grp[k]))
    grp = {}
    for e in elig:                                   # rule 5 (A1.6)
        if e["url_state"] == "OK":
            grp.setdefault(e["url_norm"], []).append(e)
    for k in sorted(grp):
        evs = sorted(grp[k], key=lambda e: e["event_id"])
        for i in range(len(evs)):
            for j in range(i + 1, len(evs)):
                a, b = evs[i], evs[j]
                if (a["accession"] is not None and b["accession"] is not None
                        and a["accession"] != b["accession"]):
                    edges[5].add(_pair(a["event_id"], b["event_id"]))
    for e in elig:                                   # rule 7 (A1.6)
        p = e["parent_event_id"]
        if p is not None and p in by_id and p != e["event_id"]:
            edges[7].add(_pair(e["event_id"], p))
    uf = _UF(ids)                                    # stories (A1.5: rules 1, 3)
    for n in (1, 3):
        for a, b in sorted(edges[n]):
            uf.union(a, b)
    stories = uf.components()
    for st in stories:                               # rule 2 (P)
        edges[2].update(_all_pairs(st))
    uf = _UF(ids)                                    # story-clusters (A1.5)
    for n in EVENT_EDGE_RULES:
        for a, b in sorted(edges[n]):
            uf.union(a, b)
    clusters = uf.components()
    # --- per-cluster structure (P severity; A1.5; A1.7)
    story_recs = []
    for st in stories:
        mset = set(st)
        typed = sorted((n, a, b) for n in (1, 3) for (a, b) in edges[n]
                       if a in mset and b in mset)
        story_recs.append({"story_id": _member_id(st), "members": sorted(st),
                           "edges": [[n, a, b] for n, a, b in typed]})
    story_recs.sort(key=lambda r: r["story_id"])
    cluster_recs = []
    for cl in clusters:
        mset = set(cl)
        typed = sorted((n, a, b) for n in EVENT_EDGE_RULES for (a, b) in edges[n]
                       if a in mset and b in mset)
        pairs = sorted({(a, b) for _, a, b in typed})
        V, E = len(cl), len(pairs)
        cuf = _UF(cl)
        for a, b in pairs:
            cuf.union(a, b)
        c = len(cuf.components())
        r = E - V + c
        issuers = sorted({by_id[i]["ticker"] for i in cl})
        Vp, Ep, cp = V + len(issuers), E, c + len(issuers)
        cluster_recs.append({
            "cluster_id": _member_id(cl), "members": sorted(cl),
            "edges": [[n, a, b] for n, a, b in typed],
            "V": V, "E": E, "c": c, "r": r,
            "structure_class": _structure_class(V, E, r),
            "projection": {"issuers": issuers, "V": Vp, "E": Ep, "c": cp,
                           "r": Ep - Vp + cp}})
    cluster_recs.sort(key=lambda r: r["cluster_id"])
    # --- annotations (A1.6 rules 11, 12, 14)
    snaps_by = {}
    for s in inputs["snapshots"]:
        if s["signal_time"] is None:
            continue                                 # never selected
        ses = cal.session_of(_ts_in(s["signal_time"]))
        if ses is None:
            continue
        snaps_by.setdefault((s["ticker"], ses), []).append(s)

    def _last(rows):
        return max(rows, key=lambda s: (_ts_in(s["signal_time"]), s["snapshot_id"]))

    track_by = {}
    for t in inputs["track_record"]:
        track_by.setdefault((t["ticker"], date.fromisoformat(t["signal_date"])), []).append(t)
    ann = {"11": {}, "12": {}, "14": {}}
    for e in elig:
        eid, t, D = e["event_id"], e["ticker"], e["session"]
        cand = [s for s in snaps_by.get((t, D), []) if eid in s["evidence_event_ids"]]
        if cand:
            s = _last(cand)
            comps = sorted(k for k, v in s["component_evidence_ids"].items() if eid in v)
            ann["11"][eid] = {"snapshot_id": s["snapshot_id"], "components": comps}
        else:
            ann["11"][eid] = "NONE"
        Dm1 = cal.prev_session(D)
        cur_rows, prev_rows = snaps_by.get((t, D), []), snaps_by.get((t, Dm1), []) if Dm1 else []
        if cur_rows and prev_rows:
            a, b = _last(prev_rows)["signal_label"], _last(cur_rows)["signal_label"]
            ann["12"][eid] = {"prev": a, "cur": b,
                              "state": "changed" if a != b else "unchanged"}
        else:
            ann["12"][eid] = "NONE"
        rows = track_by.get((t, D), [])
        ks = sorted({k for r_ in rows for k, f in ((1, "k1"), (5, "k5"), (20, "k20")) if r_[f]})
        ann["14"][eid] = ks if ks else "NONE"
    # --- rules block (A1.9) with coverage states (A1.6)
    rules = {}
    for n in range(1, 17):
        if n in EVENT_EDGE_RULES:
            rules[str(n)] = {"status": "EXECUTED",
                             "edges": [[a, b] for a, b in sorted(edges[n])]}
        elif n in (11, 12, 14):
            rules[str(n)] = {"status": "EXECUTED",
                             "edges": sorted(k for k, v in ann[str(n)].items() if v != "NONE")}
        else:
            rules[str(n)] = {"status": "ABSENT"}
    n_multi = sum(1 for c in cluster_recs if c["V"] >= 2)
    verdict = ("INSUFFICIENT" if (not elig or n_multi == 0) else "STRUCTURE_PRINTED")
    payload = {
        "protocol_id": PROTOCOL_ID,
        "addendum_id": addendum_id,
        "read_scope": READ_SCOPE,
        "read_window": read_window,
        "calendar_sha256": cal.sha256,
        "membership_sha256": membership_sha,
        "eligible_events": len(elig),
        "ineligible_counts": inel,
        "accession_unparsed_count": unparsed,
        "edge_rule_coverage": {"executable": EXECUTABLE_RULES,
                               "absent": ABSENT_RULES,
                               "structural_completeness": "PARTIAL"},
        "rules": rules,
        "stories": story_recs,
        "clusters": cluster_recs,
        "annotations": ann,
        "n_eff": "PENDING",
        "n_eff_printed": N_EFF_PRINTED,
        "adoption_protocol": {"Q1": "NOT_EVALUATED", "Q2": "NOT_EVALUATED",
                              "Q3": "NOT_EVALUATED", "Q4": "NOT_EVALUATED",
                              "Q5": "MANUAL_REVIEW"},
        "verdict": verdict,
    }
    return payload, read_window


def _env_manifest():
    import platform
    keys = ("TZ", "LC_ALL", "PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE",
            "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
    return {"python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "env": {k: _os.environ.get(k) for k in keys},
            "numpy_scipy_pandas": "not imported by this read"}


def _source_commit():
    try:
        return _subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(_ROOT),
                               capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def run(lens: str = "SMH", mode: str = "canonical", out_dir=None,
        frozen_dir=None, record: bool = False):
    """The first computable read enters HERE and nowhere else.

    mode='canonical' (Run #1): A1.10 sequence — chain verify, A1 line
        verify, record tip + source commit, T_access, freeze inputs (first
        governed access), compute, write canonical artifact + separate
        execution metadata + frozen inputs + manifest under output/oie/.
        record=True additionally appends exactly one chain run entry.
    mode='replay' (gate #6): NO-WRITE — no DB, no chain append, no ledger
        regeneration, no canonical-path writes; inputs = the frozen file
        (hashes asserted against the manifest first); outputs to out_dir.
    """
    _registry_guard(PROTOCOL_ID)
    if lens != "SMH":
        raise RuntimeError(
            f"Layered Evidence Dependency v1: first computable read is the "
            f"SMH lens ONLY (got {lens!r}); other lenses require the "
            f"registered adoption decision.")
    _date_guard()
    if mode not in ("canonical", "replay"):
        raise ValueError("mode must be canonical or replay")
    t0 = _dt.now(_tz.utc)
    from yuclaw_protocol_registry import Registry, Run
    reg = Registry(str(_ROOT / "registry" / "protocols.jsonl"))   # chain verify
    a_line, a_hash, a_payload = _addendum_guard(reg)
    chain = {"lines": len(reg._lines), "tip": reg._tip(),
             "addendum_line": a_line, "addendum_line_hash": a_hash,
             "addendum_id": a_payload["addendum_id"],
             "registered_utc": a_payload["registered_utc"]}
    cal = _Calendar()
    tickers, as_of, mem_sha = _membership()
    src = _source_commit()
    frozen_dir = _Path(frozen_dir) if frozen_dir else OUT_DIR
    if mode == "canonical":
        out = OUT_DIR
        out.mkdir(parents=True, exist_ok=True)
        # window needed for the freeze bounds only (dates; no outcome access)
        reg_ts = _dt.fromisoformat(chain["registered_utc"])
        reg_session = cal.session_of(reg_ts)
        window_end = cal.prev_session(reg_session)
        first = [s for s in cal.sessions
                 if date.fromisoformat(WINDOW_START_BOUND) <= s <= window_end][0]
        t_access = _now_utc()
        if not (chain["registered_utc"] < t_access):
            raise RuntimeError("A1.10: T_reg must be strictly earlier than T_access")
        inputs = _freeze_inputs(cal, tickers, first, window_end)
        inputs["registered_utc"] = chain["registered_utc"]
        inputs["addendum_line_hash"] = a_hash
        inputs_bytes = _canonical_bytes(inputs)
        (out / INPUTS_NAME).write_bytes(inputs_bytes)
        in_scope = {r["event_id"]: _sha256_bytes(_canonical_bytes(r))
                    for r in inputs["events"] if r["ticker"] in set(tickers)}
        out_scope = [r for r in inputs["events"] if r["ticker"] not in set(tickers)]
        manifest = {
            "frozen_utc": t_access, "t_access": t_access,
            "chain": chain, "source_commit": src,
            "inputs_file": INPUTS_NAME, "inputs_sha256": _sha256_bytes(inputs_bytes),
            "events_in_scope": in_scope, "events_in_scope_count": len(in_scope),
            "events_out_of_scope_count": len(out_scope),
            "events_out_of_scope_rowset_sha256": _sha256_bytes(_canonical_bytes(out_scope)),
            "snapshots_rowset_sha256": _sha256_bytes(_canonical_bytes(inputs["snapshots"])),
            "snapshots_count": len(inputs["snapshots"]),
            "track_record_rowset_sha256": _sha256_bytes(_canonical_bytes(inputs["track_record"])),
            "track_record_count": len(inputs["track_record"]),
            "calendar_file": CALENDAR_FILE, "calendar_sha256": cal.sha256,
            "membership_file": MEMBERSHIP_FILE, "membership_sha256": mem_sha,
            "membership_as_of": as_of, "membership_tickers": tickers,
            "addendum_file": ADDENDUM_FILE, "addendum_sha256": _sha256_file(ADDENDUM_FILE),
            "environment": _env_manifest(),
        }
        (out / MANIFEST_NAME).write_bytes(_canonical_bytes(manifest))
    else:
        out = _Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        if out.resolve() == OUT_DIR.resolve():
            raise RuntimeError("replay refuses to write to the canonical path")
        manifest = json.loads((frozen_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
        inputs_bytes = (frozen_dir / INPUTS_NAME).read_bytes()
        if _sha256_bytes(inputs_bytes) != manifest["inputs_sha256"]:
            raise RuntimeError("replay: frozen inputs hash mismatch")
        if cal.sha256 != manifest["calendar_sha256"]:
            raise RuntimeError("replay: calendar file hash mismatch")
        if mem_sha != manifest["membership_sha256"]:
            raise RuntimeError("replay: membership file hash mismatch")
        if a_hash != manifest["chain"]["addendum_line_hash"]:
            raise RuntimeError("replay: addendum line hash mismatch")
        inputs = json.loads(inputs_bytes.decode("utf-8"))
        if inputs["registered_utc"] != chain["registered_utc"]:
            raise RuntimeError("replay: registration timestamp mismatch")
        t_access = None
    payload, read_window = _compute(inputs, cal, tickers, mem_sha,
                                    chain["addendum_id"], chain["registered_utc"])
    if payload.get("verdict") == "NOT_EXECUTABLE" and "reason" in payload:
        payload = {"protocol_id": PROTOCOL_ID, "addendum_id": chain["addendum_id"],
                   "read_scope": READ_SCOPE, "read_window": read_window,
                   "verdict": "NOT_EXECUTABLE", "reason": payload["reason"],
                   "n_eff": "PENDING", "n_eff_printed": N_EFF_PRINTED}
    assert payload["verdict"] in LABELS
    canon = _canonical_bytes(payload)
    (out / CANONICAL_NAME).write_bytes(canon)
    canon_sha = _sha256_bytes(canon)
    t1 = _dt.now(_tz.utc)
    meta = {"mode": mode, "t_start_utc": t0.isoformat(), "t_end_utc": t1.isoformat(),
            "duration_s": (t1 - t0).total_seconds(), "t_access": t_access,
            "t_reg": chain["registered_utc"], "chain": chain,
            "source_commit": src, "host": _os.uname().nodename,
            "pid": _os.getpid(), "canonical_path": str(out / CANONICAL_NAME),
            "canonical_sha256": canon_sha, "environment": _env_manifest()}
    (out / META_NAME).write_bytes(_canonical_bytes(meta))
    result = {"verdict": payload["verdict"], "canonical_sha256": canon_sha,
              "canonical_path": str(out / CANONICAL_NAME), "chain": chain,
              "eligible_events": payload.get("eligible_events"),
              "n_clusters": len(payload.get("clusters", [])),
              "mode": mode}
    if mode == "canonical" and record:
        n_cl = len(payload.get("clusters", []))
        rw = payload["read_window"]
        line_hash = reg.record_run(Run(
            protocol_id=PROTOCOL_ID, run_date=date.today().isoformat(),
            data_window=(f"SMH lens (A1.3, 25 tickers), sessions "
                         f"{rw['first_session']}..{rw['end_session']} by "
                         f"session-of(available_as_of); frozen inputs "
                         f"{manifest['inputs_sha256'][:16]}"),
            n_primary_cells=n_cl, n_secondary_cells=n_cl,
            result_hash=canon_sha,
            note=(f"Layered Evidence Dependency v1 FIRST READ (structural) under "
                  f"Addendum A1 line {a_line} ({a_hash[:12]}). Verdict "
                  f"{payload['verdict']} (A1.8 label set); "
                  f"structural_completeness PARTIAL; N_eff PENDING; READ_SCOPE = "
                  f"STRUCTURAL_ONLY; eligible_events={payload.get('eligible_events')}; "
                  f"clusters={n_cl}; Q1-Q4 NOT_EVALUATED, Q5 MANUAL_REVIEW; no rollout.")))
        Registry(str(_ROOT / "registry" / "protocols.jsonl"))       # re-verify
        result["run_line_hash"] = line_hash
        result["chain_lines_after"] = len(reg._lines)
    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="canonical Run #1")
    ap.add_argument("--record", action="store_true", help="append the chain run entry")
    ap.add_argument("--replay", action="store_true", help="NO-WRITE replay")
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()
    if a.run:
        print(json.dumps(run("SMH", mode="canonical", record=a.record), indent=1))
    elif a.replay:
        if not a.out_dir:
            raise SystemExit("--replay requires --out-dir")
        print(json.dumps(run("SMH", mode="replay", out_dir=a.out_dir), indent=1))
    else:
        print(f"[layered-dependency] METHOD_HASH={METHOD_HASH} · "
              f"PROTOCOL_ID={PROTOCOL_ID} · params={PARAMS} · "
              f"first_read_date={FIRST_READ_DATE!r} (owner slot) · "
              f"LOCKED; first read implemented under Addendum A1")
