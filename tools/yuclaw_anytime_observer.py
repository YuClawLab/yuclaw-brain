#!/usr/bin/env python3
"""
ANYTIME OBSERVER — nightly observation admission for the Anytime Evidence
Record v1 (order 2026-08-12a; method protocol e99eb4d335fe, enrollments
06721f08a792 / 84187c7ea6e7 / bca373c95f68).
===========================================================================
Admits observations for enrolled instruments at the nightly chain close,
exactly per the registered METHOD_SPEC and each enrollment's declared
cadence:

  C-1 (prospective-only): an observation is admitted ONLY for a signal
      whose issuance timestamp (signal_snapshots.available_as_of — the
      information-set availability stamp) is STRICTLY AFTER the
      enrollment's start_time. No information-set timestamp <= start_time
      is ever admitted; violations are REFUSED, never adjusted.
  Maturity: only fully matured 20d outcomes (track_record.return_20d
      NOT NULL, plus hit_20d NOT NULL where the transform needs it) are
      observable; immature rows are REFUSED tonight and become eligible
      only when the forward-ledger outcome updater matures them.
  E-process: wealth updates use the locked formula in-hash at
      tools/yuclaw_anytime_record.py (K=20 grid, lambda_k = k/((K+1)*m0),
      mixture e-value; thresholds theta_supported=20 / theta_weak=5).
      Direction 'less' reduces by x -> 1-x, m0 -> 1-m0 per the spec.

Observations are appended to a dedicated append-only chained JSONL —
registry/anytime_observations.jsonl — using the SAME chain mechanics as
the registered protocol registry (prev_hash/line_hash via
yuclaw_protocol_registry.Registry; kind = anytime_observation). The
canonical chain registry/protocols.jsonl is NEVER written by this tool.
On every load the full observation chain is replayed through the locked
e-process and each stored e_value_after must match the replay
digit-for-digit — any divergence fails closed.

Idempotent: a (enrollment_id, snapshot_id) pair is admitted at most once;
re-running a night admits nothing new. Non-fatal in the nightly chain by
design (order 2026-08-12a): an observer failure must never block the
page pipeline.

Modes:
  --nightly    admit newly eligible observations, print the nightly line
  --status     per-enrollment e-value / state / observation count
  --fixtures   the five registered fixtures on synthetic data only
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "tools"))
sys.path.insert(0, str(_REPO))

from yuclaw_protocol_registry import Registry  # noqa: E402
from yuclaw_anytime_record import (  # noqa: E402
    CHAIN, ENROLLMENT_KIND, GRID_K, PROTOCOL_ID, THETA_SUPPORTED,
    THETA_WEAK, e_update, state_of,
)

OBS_CHAIN = _REPO / "registry" / "anytime_observations.jsonl"
OBSERVATION_KIND = "anytime_observation"

# The only observation transforms registered in the three enrollment
# lines. Unknown transform text is REFUSED (fail closed) — a new
# transform arrives only with a new enrollment line that declares it.
_KNOWN_TRANSFORMS = {
    "indicator: hit_20d -> 1 else 0": "hit_20d",
    "indicator: return_20d < 0 -> 1 else 0": "return_20d_neg",
}


class Refused(Exception):
    """An observation candidate that violates the registered admission
    rules. Refusal is terminal for tonight; a candidate refused for
    immaturity re-enters when the forward ledger matures it, a candidate
    refused for C-1 never re-enters."""


# ------------------------------------------------------------ enrollments
def _parse_labels(registered_null: str) -> list[str]:
    """Label set from the registered null text, e.g.
    '... for signals labeled BULLISH or STRONG_BULLISH issued strictly
    after start_time' -> ['BULLISH', 'STRONG_BULLISH']."""
    text = registered_null
    lo = text.find("labeled ")
    hi = text.find(" issued strictly after")
    if lo < 0 or hi < 0 or hi <= lo:
        raise Refused(f"registered_null carries no parseable label set: "
                      f"{registered_null!r}")
    labels = [t.strip() for t in text[lo + len("labeled "):hi].split(" or ")]
    if not labels or not all(l and l == l.upper() for l in labels):
        raise Refused(f"unparseable label set in {registered_null!r}")
    return labels


def load_enrollments(chain_path: Path = CHAIN) -> list[dict]:
    reg = Registry(str(chain_path))          # verifies the chain on load
    reg.assert_registered(PROTOCOL_ID)       # method must be registered
    out = []
    for line in reg._lines:
        if line["kind"] != ENROLLMENT_KIND:
            continue
        p = line["payload"]
        params = p["parameters"]
        transform_key = _KNOWN_TRANSFORMS.get(params.get("transform"))
        if transform_key is None:
            raise Refused(f"enrollment {p['enrollment_id']}: transform "
                          f"{params.get('transform')!r} is not a "
                          f"registered observation transform — refused")
        out.append({
            "enrollment_id": p["enrollment_id"],
            "instrument": p["instrument"],
            "labels": _parse_labels(p["registered_null"]),
            "m0": float(params["m0"]),
            "direction": params.get("direction", "greater"),
            "transform": transform_key,
            "start_time": datetime.fromisoformat(str(p["start_time"])),
            "maturity_n": 30,
            "maturity_days": 60,
        })
    return out


# -------------------------------------------------------------- admission
def admit_observation(enr: dict, cand: dict) -> float:
    """Registered admission rules, in order, fail closed. Returns the
    bounded observation x in [0,1] (post direction reduction) or raises
    Refused. cand: {snapshot_id, signal_label, is_backfill,
    available_as_of, return_20d, hit_20d}."""
    if cand.get("is_backfill"):
        raise Refused(f"{cand['snapshot_id']}: backfill rows are never "
                      f"observations")
    if cand.get("signal_label") not in enr["labels"]:
        raise Refused(f"{cand['snapshot_id']}: label "
                      f"{cand.get('signal_label')!r} outside the "
                      f"instrument's registered set {enr['labels']}")
    issued = cand.get("available_as_of")
    if issued is None:
        raise Refused(f"{cand['snapshot_id']}: no issuance timestamp — "
                      f"C-1 cannot be proven, refused")
    if issued <= enr["start_time"]:
        raise Refused(f"{cand['snapshot_id']}: issued {issued.isoformat()} "
                      f"<= start_time {enr['start_time'].isoformat()} — "
                      f"C-1 refuses every pre-start information set")
    if cand.get("return_20d") is None:
        raise Refused(f"{cand['snapshot_id']}: 20d outcome not matured — "
                      f"refused tonight, eligible when the forward ledger "
                      f"matures it")
    if enr["transform"] == "hit_20d":
        if cand.get("hit_20d") is None:
            raise Refused(f"{cand['snapshot_id']}: hit_20d undefined — "
                          f"transform input not matured")
        x = 1.0 if cand["hit_20d"] else 0.0
    elif enr["transform"] == "return_20d_neg":
        x = 1.0 if float(cand["return_20d"]) < 0.0 else 0.0
    else:  # structurally unreachable: load_enrollments refuses unknowns
        raise Refused(f"unregistered transform {enr['transform']!r}")
    if enr["direction"] == "less":       # spec reduction to 'greater'
        x = 1.0 - x
    return x


def effective_m0(enr: dict) -> float:
    return 1.0 - enr["m0"] if enr["direction"] == "less" else enr["m0"]


# ----------------------------------------------------- observation chain
def load_obs_chain(obs_path: Path = OBS_CHAIN,
                   enrollments: list[dict] | None = None) -> dict:
    """Load + verify the observation chain, replay every enrollment's
    e-process from its raw x sequence, and require each stored
    e_value_after to match the replay digit-for-digit. Returns per-
    enrollment state: {eid: {wealth, e_value, t, seen:set(snapshot_id)}}."""
    enrollments = enrollments if enrollments is not None else \
        load_enrollments()
    state = {e["enrollment_id"]: {"wealth": [1.0] * GRID_K, "e_value": 1.0,
                                  "t": 0, "seen": set(), "m0":
                                  effective_m0(e)}
             for e in enrollments}
    if not obs_path.exists():
        return state
    reg = Registry(str(obs_path))            # hash-chain verified on load
    for i, line in enumerate(reg._lines, start=1):
        if line["kind"] != OBSERVATION_KIND:
            raise ValueError(f"observation chain line {i}: foreign kind "
                             f"{line['kind']!r}")
        p = line["payload"]
        st = state.get(p["enrollment_id"])
        if st is None:
            raise ValueError(f"observation chain line {i}: unknown "
                             f"enrollment {p['enrollment_id']!r}")
        if p["snapshot_id"] in st["seen"]:
            raise ValueError(f"observation chain line {i}: duplicate "
                             f"observation {p['snapshot_id']}")
        if p["t"] != st["t"] + 1:
            raise ValueError(f"observation chain line {i}: ordinal "
                             f"{p['t']} != expected {st['t'] + 1}")
        st["wealth"], st["e_value"] = e_update(st["wealth"], float(p["x"]),
                                               st["m0"])
        if st["e_value"] != p["e_value_after"]:
            raise ValueError(
                f"observation chain line {i}: stored e_value_after "
                f"{p['e_value_after']!r} != replayed {st['e_value']!r} — "
                f"wealth arithmetic must match the locked formula "
                f"digit-for-digit")
        st["t"] = p["t"]
        st["seen"].add(p["snapshot_id"])
    return state


def _append_observation(reg: Registry, enr: dict, st: dict, cand: dict,
                        x: float, observed_at: str) -> None:
    st["wealth"], st["e_value"] = e_update(st["wealth"], x, st["m0"])
    st["t"] += 1
    st["seen"].add(cand["snapshot_id"])
    reg._append(OBSERVATION_KIND, {
        "enrollment_id": enr["enrollment_id"],
        "t": st["t"],
        "snapshot_id": cand["snapshot_id"],
        "ticker": cand.get("ticker"),
        "signal_date": str(cand.get("signal_date")),
        "signal_label": cand.get("signal_label"),
        "issued_at": cand["available_as_of"].isoformat(),
        "x": x,
        "m0": st["m0"],
        "e_value_after": st["e_value"],
        "observed_at": observed_at,
    })


# ---------------------------------------------------------------- nightly
def _db_candidates(enr: dict) -> list[dict]:
    import psycopg2
    import psycopg2.extras
    from v3.sources.edgar_poll import DB_DSN
    conn = psycopg2.connect(DB_DSN)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # The WHERE mirrors the admission rules for efficiency only;
        # admit_observation() re-verifies every rule on every candidate.
        cur.execute("""
            SELECT t.snapshot_id, t.ticker, t.signal_date, t.signal_label,
                   t.is_backfill, t.return_20d, t.hit_20d,
                   s.available_as_of
            FROM track_record t
            JOIN signal_snapshots s USING (snapshot_id)
            WHERE t.is_backfill = false
              AND t.signal_label = ANY(%s)
              AND t.return_20d IS NOT NULL
              AND s.available_as_of > %s
            ORDER BY t.signal_date, t.snapshot_id
        """, (enr["labels"], enr["start_time"]))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def run_nightly() -> int:
    enrollments = load_enrollments()
    state = load_obs_chain(enrollments=enrollments)
    reg = Registry(str(OBS_CHAIN)) if OBS_CHAIN.exists() else None
    observed_at = datetime.now(timezone.utc).replace(
        microsecond=0).isoformat()
    admitted_total = 0
    for enr in enrollments:
        st = state[enr["enrollment_id"]]
        admitted = 0
        for cand in _db_candidates(enr):
            if cand["snapshot_id"] in st["seen"]:
                continue
            try:
                x = admit_observation(enr, cand)
            except Refused as exc:
                print(f"[anytime-observer] REFUSED "
                      f"({enr['enrollment_id']}): {exc}")
                continue
            if reg is None:
                reg = Registry(str(OBS_CHAIN))
            _append_observation(reg, enr, st, cand, x, observed_at)
            admitted += 1
        admitted_total += admitted
        print(f"[anytime-observer] {enr['enrollment_id']} "
              f"({enr['instrument'][:40]}…): {admitted} admitted tonight, "
              f"{st['t']} total, e={st['e_value']:.6g}, "
              f"state={_state(enr, st)}")
    print(f"[anytime-observer] {admitted_total} eligible observations")
    return 0


def _state(enr: dict, st: dict) -> str:
    now = datetime.now(timezone.utc)
    maturity_met = (st["t"] >= enr["maturity_n"] and
                    now >= enr["start_time"] +
                    timedelta(days=enr["maturity_days"]))
    return state_of(st["e_value"], maturity_met=maturity_met,
                    started=now > enr["start_time"])


def run_status() -> int:
    enrollments = load_enrollments()
    state = load_obs_chain(enrollments=enrollments)
    n_lines = sum(1 for _ in open(CHAIN)) if CHAIN.exists() else 0
    print(f"[anytime-observer] canonical chain: {n_lines} lines · "
          f"observation chain: "
          f"{sum(s['t'] for s in state.values())} observations")
    for enr in enrollments:
        st = state[enr["enrollment_id"]]
        print(f"  {enr['enrollment_id']} m0={st['m0']} t={st['t']} "
              f"e={st['e_value']:.6g} state={_state(enr, st)} "
              f"labels={enr['labels']}")
    return 0


# --------------------------------------------------------------- fixtures
def run_fixtures() -> int:
    """The five registered fixtures (order 2026-08-12a). Synthetic data
    only; the real observation chain and the canonical chain are never
    written."""
    import math
    import tempfile

    start = datetime(2026, 8, 10, 2, 20, 59, tzinfo=timezone.utc)
    enr = {"enrollment_id": "fixture000000", "instrument": "fixture",
           "labels": ["BULLISH", "STRONG_BULLISH"], "m0": 0.5,
           "direction": "greater", "transform": "hit_20d",
           "start_time": start, "maturity_n": 30, "maturity_days": 60}
    base = {"snapshot_id": "snap_FIX_0001", "ticker": "FIX",
            "signal_date": "2026-08-11", "signal_label": "BULLISH",
            "is_backfill": False, "return_20d": 0.03, "hit_20d": True,
            "available_as_of": start + timedelta(days=1)}

    # F1 — pre-start refused (issuance at and before start_time).
    for bad_ts in (start, start - timedelta(days=3)):
        try:
            admit_observation(enr, dict(base, available_as_of=bad_ts))
            raise AssertionError("F1: pre-start observation was admitted")
        except Refused as exc:
            assert "C-1" in str(exc)
    print("[fixture 1/5] pre-start refused: OK (issuance <= start_time "
          "is REFUSED with a C-1 refusal, at and before the boundary)")

    # F2 — immature refused (return_20d NULL; hit_20d NULL likewise).
    try:
        admit_observation(enr, dict(base, return_20d=None, hit_20d=None))
        raise AssertionError("F2: immature observation was admitted")
    except Refused as exc:
        assert "not matured" in str(exc)
    try:
        admit_observation(enr, dict(base, hit_20d=None))
        raise AssertionError("F2: NULL-transform-input was admitted")
    except Refused:
        pass
    print("[fixture 2/5] immature refused: OK (NULL return_20d and NULL "
          "hit_20d both REFUSED)")

    # F3 — high-signal synthetic crosses theta_supported = 20.
    w, e = [1.0] * GRID_K, 1.0
    first_cross = None
    for t in range(1, 21):
        w, e = e_update(w, 1.0, 0.5)
        if first_cross is None and e >= THETA_SUPPORTED:
            first_cross = t
    assert first_cross is not None, "F3: high-signal never crossed 20"
    assert state_of(e, maturity_met=False) == "SUPPORTED_NOT_MATURE"
    print(f"[fixture 3/5] high-signal synthetic crosses 20: OK (all-hit "
          f"stream at m0=0.5 first crosses at t={first_cross}, "
          f"e={e:.4g} after t=20)")

    # F4 — null synthetic stays under theta_weak = 5 (deterministic
    # alternating hit/miss stream at exactly the null rate m0=0.5).
    w, e = [1.0] * GRID_K, 1.0
    e_max = 1.0
    for t in range(40):
        w, e = e_update(w, 1.0 if t % 2 == 0 else 0.0, 0.5)
        e_max = max(e_max, e)
    assert e_max < THETA_WEAK, f"F4: null stream reached e={e_max}"
    assert state_of(e, maturity_met=False) == "ACCUMULATING"
    print(f"[fixture 4/5] null synthetic stays under 5: OK (40-step "
          f"alternating stream at the null rate: running max "
          f"e={e_max:.4g} < {THETA_WEAK}, final e={e:.4g})")

    # F5 — wealth arithmetic digit-for-digit, through the REAL append/
    # replay path on a scratch chain. Independent recomputation of the
    # spec formula: lambda_k = k/((K+1)*m0), W_t(lambda_k) =
    # prod(1 + lambda_k*(X_i - m0)), E_t = mean_k W_t(lambda_k).
    m0 = 0.467304                      # E2's registered m0, verbatim
    xs = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0]
    with tempfile.TemporaryDirectory() as td:
        scratch = Path(td) / "obs_fixture.jsonl"
        reg = Registry(str(scratch))
        st = {"wealth": [1.0] * GRID_K, "e_value": 1.0, "t": 0,
              "seen": set(), "m0": m0}
        fenr = dict(enr, m0=m0, transform="return_20d_neg",
                    labels=["RISK_ALERT"])
        for i, x in enumerate(xs):
            cand = dict(base, snapshot_id=f"snap_FIX_{i:04d}",
                        signal_label="RISK_ALERT",
                        return_20d=-0.02 if x else 0.02, hit_20d=None)
            assert admit_observation(fenr, cand) == x
            _append_observation(reg, fenr, st, cand, x,
                                "2026-08-12T00:00:00+00:00")
        # Independent spec-formula recomputation (same left-to-right
        # association as the locked update; equality is exact, not
        # approximate).
        lam = [k / ((GRID_K + 1) * m0) for k in range(1, GRID_K + 1)]
        wealth = [1.0] * GRID_K
        expected = []
        for x in xs:
            wealth = [w * (1.0 + l * (x - m0))
                      for w, l in zip(wealth, lam)]
            expected.append(sum(wealth) / GRID_K)
        stored = [json.loads(l)["payload"]["e_value_after"]
                  for l in open(scratch)]
        assert stored == expected, (
            f"F5: stored e-values {stored} != independent spec "
            f"recomputation {expected}")
        # And the replay path itself must accept the chain verbatim.
        replayed = load_obs_chain(scratch, enrollments=[fenr])
        assert replayed[fenr["enrollment_id"]]["e_value"] == expected[-1]
        assert not math.isnan(expected[-1])
    print(f"[fixture 5/5] wealth arithmetic digit-for-digit: OK "
          f"({len(xs)} observations appended via the real chain path at "
          f"m0={m0}; every stored e_value_after exactly equals the "
          f"independent spec-formula recomputation; replay accepts; "
          f"final e={expected[-1]!r})")

    print("[anytime-observer] fixtures: 5/5 OK (synthetic only; no real "
          "chain touched)")
    return 0


if __name__ == "__main__":
    if "--nightly" in sys.argv:
        sys.exit(run_nightly())
    elif "--fixtures" in sys.argv:
        sys.exit(run_fixtures())
    else:
        sys.exit(run_status())
