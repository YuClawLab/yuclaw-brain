#!/usr/bin/env python3
"""
Monday board — internal status page (order of 2026-07-27).

Emits internal/status/YYYY-MM-DD.md from LIVE sources only: the canonical
registry (protocol table, runs, uncomputed guards), chain tip, fresh gate
results (the fast gates; deploy state via the push-failure marker), staging
branch vs main, the armed-dates calendar, and the counsel/customer gap list
verbatim from output/byos_dryrun/GAPS.md.

Runs as a non-fatal generate-only step in the daily chain — internal, never
deployed, gitignored under internal/.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from yuclaw_protocol_registry import Registry

OUT_DIR = _REPO / "internal" / "status"
GAPS = _REPO / "output" / "byos_dryrun" / "GAPS.md"

GUARDED = {"0df6fc002d79": "C6 Risk Gate — first read 2026-07-30",
           "ea120b0a6b52": "Reversal coherence — compute >= 2026-09-01",
           "cdd92e7b99bc": "Client admission standard — never computed (standard class)"}

CALENDAR = [
    ("2026-07-30", "C6 Risk Gate first read (protocol 0df6fc002d79) + accrual reading — kit: internal/orders/2026-07-30_c6_first_read.md"),
    ("2026-08-15", "Freeze end — merge v5.1-public-staging (one reviewed merge)"),
    ("2026-09-01", "Reversal coherence guard expiry (protocol ea120b0a6b52) — forward accrual from 2026-07-27"),
]


def _run(cmd, cwd=_REPO):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def gate_line(name, cmd):
    rc, _ = _run(cmd)
    return f"| {name} | {'PASS' if rc == 0 else 'FAIL'} |"


def u350_section() -> str:
    try:
        import psycopg2
        with psycopg2.connect("dbname=yuclaw_events") as cn:
            with cn.cursor() as cur:
                cur.execute("""SELECT manifest_hash,
                                      jsonb_array_length(members)
                               FROM u350.manifest WHERE phase='A'
                               ORDER BY locked_at DESC LIMIT 1""")
                row = cur.fetchone()
                if not row:
                    return "Phase A not yet ignited (no manifest)."
                mh, nm = row
                cur.execute("""SELECT min(signal_time::date),
                                      count(DISTINCT signal_time::date),
                                      count(*) FROM u350.shadow_snapshots""")
                first, ndays, nsnap = cur.fetchone()
        rc, out = _run(["python3", "v3/u350/shadow_ops.py", "guards"])
        guard = "green" if rc == 0 else "FLAGGED — see shadow log"
        return (f"- manifest `{mh[:16]}` · {nm} members (79 U79 + "
                f"{nm - 79} shadow)\n"
                f"- Phase-A clock: day {ndays or 0} of 15-20 trading days "
                f"(first snapshot {first}); {nsnap or 0} snapshots total\n"
                f"- guards: {guard} (completeness floor + label anomaly; "
                f"C7 structurally inactive for shadow names, disclosed)\n"
                f"- success criterion: system verification (isolation, "
                f"completeness, guards) — never performance")
    except Exception as exc:                          # noqa: BLE001
        return f"(u350 section unavailable: {exc})"


def main() -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    runs_by = {}
    for ln in reg._lines:
        if ln["kind"] == "run":
            runs_by[ln["payload"]["protocol_id"]] = \
                runs_by.get(ln["payload"]["protocol_id"], 0) + 1
    proto_rows = []
    for ln in reg._lines:
        if ln["kind"] != "protocol":
            continue
        p = ln["payload"]
        pid = p["protocol_id"]
        n = runs_by.get(pid, 0)
        guard = GUARDED.get(pid, "")
        proto_rows.append(f"| `{pid}` | {p['name']} | {p['lock_date']} | "
                          f"{n} | {guard or '—'} |")

    import glob as _g
    docs = sorted(str(p) for p in (_REPO / "docs").glob("*.html"))
    previews = sorted(str(p) for p in (_REPO / "docs" / "preview").glob("*.html"))
    gates = [
        gate_line("registry chain-verify",
                  ["python3", "-c",
                   "import sys; sys.path.insert(0,'tools'); "
                   "from yuclaw_protocol_registry import Registry; "
                   "Registry('registry/protocols.jsonl').verify_chain()"]),
        gate_line("language rail", ["python3", "tools/check_language.py",
                                    "--pages"] + docs + previews),
        gate_line("copy integrity", ["python3", "tools/check_copy_integrity.py"]
                  + docs + previews),
        gate_line("site walk", ["python3", "tools/check_site_walk.py"]),
        gate_line("client custody", ["python3", "tools/check_client_custody.py"]),
    ]
    push_marker = Path("/tmp/yuclaw_push_failed.marker")
    gates.append(f"| push/deploy marker | "
                 f"{'FAIL (undeployed build!)' if push_marker.exists() else 'PASS (no failure marker)'} |")

    _run(["git", "fetch", "origin", "-q"])
    rc, lr = _run(["git", "rev-list", "--left-right", "--count",
                   "main...v5.1-public-staging"])
    behind_ahead = lr.replace("\t", " behind-main / ") + " ahead" if rc == 0 else "?"
    _rc, stip = _run(["git", "log", "-1", "--format=%h %s",
                      "v5.1-public-staging"])

    cal = "".join(f"| {d} | {what} |\n" for d, what in CALENDAR)
    gaps = GAPS.read_text() if GAPS.exists() else "(GAPS.md missing)"

    md = f"""# YUCLAW board — {today}

Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} from live sources. Internal; never deployed.

## Registry (chain tip `{reg._tip()}`)

| protocol | name | locked | runs | guard |
|---|---|---|---|---|
{chr(10).join(proto_rows)}

## Research questions (hypothesis registry)

| question | status | linked protocols | grounds |
|---|---|---|---|
{chr(10).join(f"| {q['question']} | **{q['status']}** | {', '.join('`'+p+'`' for p in q['linked_protocols'])} | {'; '.join(q['grounds'])[:220]} |" for q in reg.questions().values())}

## Gates (fresh at generation time)

| gate | result |
|---|---|
{chr(10).join(gates)}

## Staging branch

`v5.1-public-staging`: {behind_ahead} · tip: {stip}

## U350 shadow program (Phase A — shadow data is never a forward record; no public claims)

{u350_section()}

## Standing rules

- Every newly registered primary result gets a Robustness Profile grid within one cycle (rule of 2026-08-01).

## Armed dates

| date | what |
|---|---|
{cal}
## Gap list (verbatim from output/byos_dryrun/GAPS.md)

{gaps}
"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{today}.md"
    out.write_text(md)
    print(f"[board] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
