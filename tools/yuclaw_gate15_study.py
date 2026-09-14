#!/usr/bin/env python3
"""Gate #15 study tooling (v7 candidate; protocol UNADOPTED) — builds the participant packet the script
promises, binds materials from COMMITTED blobs and delivered bytes, evaluates reviewer forms deterministically
and produces the gate-evidence adapter output. It never enrols, contacts or scores real people.

  schema                         print the unified kit/scoring-key/form schema
  check-docs                     check that the participant script and scoring key agree with the schema
  build-packet OUT --source CHK  --mode EXECUTION|TRANSCRIPT [--wheel FILE --wheel-label REHEARSAL|RC|FINAL]
                                 assemble the participant distribution (NO scoring key): participant script, README,
                                 site inputs, verification packet with VERIFY.md + recorded verify output + challenge template
  manifest --commit SHA --packet DIR --out FILE [--wheel FILE --wheel-label L]
                                 private study manifest from the commit's blobs (git show) + the delivered packet bytes
  evaluate FORMS_DIR [--out FILE]   score reviewer forms (JSON) → per-session results + per-mode aggregates
  gate-evidence EVAL.json [--adoption FILE --applicability FILE --reviewer FILE --human-records]"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))
from v3.study import gate15_schema as S  # noqa: E402
from v3.study import evaluate as E  # noqa: E402

SCRIPT = "docs/methodology/gate15_participant_script.md"
KEY = "docs/methodology/gate15_reviewer_scoring_key.md"
KIT = "docs/methodology/gate15_formative_study_kit.md"
SITE_INPUTS = ("docs/index.html", "docs/evidence_scoreboard.html", "docs/receipts/scoreboard.json", "docs/capabilities.json", "README.md")


def _sl(b: bytes): return hashlib.sha256(b).hexdigest(), len(b)


def cmd_schema(a) -> int:
    print(json.dumps(S.as_dict(), indent=1)); return 0


def cmd_check_docs(a) -> int:
    key = (_REPO / KEY).read_text(); script = (_REPO / SCRIPT).read_text(); problems = []
    for t, spec in S.TASKS.items():
        for eid in list(spec["elements"]) + list(spec["critical"]):
            if eid not in key:
                problems.append(f"scoring key lacks {eid}")
        if f"## Task {t}" not in script:
            problems.append(f"participant script lacks Task {t}")
    for eid in re.findall(r"\b[EC]\d\.\d\b", script):
        problems.append(f"participant script exposes scoring id {eid}")
    if "[claim text]" in script or "…" in re.sub(r"`[^`]*`", "", script).replace("…", "…") and "create …" in script:
        problems.append("participant script has a placeholder")
    print(json.dumps({"ok": not problems, "problems": problems, "schema_status": S.PROTOCOL_STATUS}, indent=1)); return 0 if not problems else 1


def cmd_build_packet(a) -> int:
    src = Path(a.source).resolve(); out = Path(a.out); (out / "materials").mkdir(parents=True, exist_ok=True)
    if a.mode == "EXECUTION" and not a.wheel:
        print("[gate15] EXECUTION mode needs --wheel", file=sys.stderr); return 2
    from v3.receipts import packet as P
    from v3.cli import packet as packet_cli
    delivered = {}
    for rel in (SCRIPT,) + SITE_INPUTS:
        b = (src / rel).read_bytes(); dst = out / "materials" / rel; dst.parent.mkdir(parents=True, exist_ok=True); dst.write_bytes(b); delivered[rel] = _sl(b)
    pk = out / "verification_packet"; man = P.build(pk, repo=src)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = packet_cli.main(["verify", str(pk)])
    verify_out = buf.getvalue().strip()
    bundle = [f for f in man["files"] if f["path"] == "docs/replay/lab_replay_bundle.json"][0]
    template = ("\n\n## Recorded verify output (TRANSCRIPT mode reads this; EXECUTION mode runs the command)\n\n```\n$ yuclaw packet verify <this packet directory>\n" + verify_out + f"\n[exit {rc}]\n```\n\n"
                "## Challenge template (TRANSCRIPT mode fills this on the answer sheet; EXECUTION mode runs the command in the participant script)\n\n"
                f"artifact_type: bundle\nsha256: {bundle['sha256']}\nsize_bytes: {bundle['size_bytes']}\nclaim_id: study-claim-1\nexpected: <what you expected to see>\nobserved: <what you actually saw>\n\n"
                "Recording a challenge creates a LOCAL record in your own store. It does not change the published evidence: a designated reviewer disposes challenges; public aggregation shows dispositions; the original finding is never erased.\n")
    with (pk / P.INSTRUCTIONS).open("a") as fh: fh.write(template)
    for f in pk.rglob("*"):
        if f.is_file(): delivered["verification_packet/" + str(f.relative_to(pk))] = _sl(f.read_bytes())
    wheel = None
    if a.wheel:
        w = Path(a.wheel); b = w.read_bytes(); (out / "materials" / w.name).write_bytes(b); wheel = {"filename": w.name, "sha256": _sl(b)[0], "size_bytes": len(b), "label": a.wheel_label or "REHEARSAL"}
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=src, capture_output=True, text=True).stdout.strip()
    pm = {"packet_format": "yuclaw-gate15-participant-packet/1", "mode": a.mode, "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "source_head": head,
          "delivered_files": {k: {"sha256": v[0], "size_bytes": v[1]} for k, v in delivered.items()}, "wheel": wheel, "scoring_key_included": False,
          "note": "participant distribution; contains no scoring key; the key is published under docs/methodology — participants are instructed not to read docs/methodology during the session (contamination policy in the kit)"}
    (out / "participant_manifest.json").write_text(json.dumps(pm, indent=1, sort_keys=True) + "\n")
    assert not any("scoring_key" in str(p) for p in out.rglob("*"))
    print(f"[gate15] participant packet {out}: {len(delivered)} delivered files; mode {a.mode}; wheel {wheel['label'] if wheel else 'none'}; verify exit {rc}"); return 0


def cmd_manifest(a) -> int:
    """Private final study manifest from COMMITTED blobs (never the working tree) + delivered packet bytes."""
    def blob(rel):
        r = subprocess.run(["git", "show", f"{a.commit}:{rel}"], cwd=_REPO, capture_output=True)
        if r.returncode != 0:
            raise SystemExit(f"[gate15] {rel} is not in commit {a.commit}")
        return r.stdout
    tree = subprocess.run(["git", "rev-parse", f"{a.commit}^{{tree}}"], cwd=_REPO, capture_output=True, text=True).stdout.strip()
    mats = {}
    for rel in (KIT, SCRIPT, KEY) + SITE_INPUTS:
        b = blob(rel); mats[rel] = {"sha256": _sl(b)[0], "size_bytes": len(b), "binding": "committed-blob", "commit": a.commit}
    pk = Path(a.packet); pm = json.loads((pk / "participant_manifest.json").read_text())
    for rel, v in pm["delivered_files"].items():
        p = pk / ("materials/" + rel if not rel.startswith("verification_packet/") else rel)
        b = p.read_bytes(); h, n = _sl(b)
        if (h, n) != (v["sha256"], v["size_bytes"]):
            raise SystemExit(f"[gate15] delivered file changed since the packet was built: {rel}")
        mats["delivered:" + rel] = {"sha256": h, "size_bytes": n, "binding": "delivered-bytes"}
    wheel = None
    if a.wheel:
        b = Path(a.wheel).read_bytes(); wheel = {"filename": Path(a.wheel).name, "sha256": _sl(b)[0], "size_bytes": len(b), "label": a.wheel_label or "REHEARSAL",
                                               "note": "coverage transfers to a final artifact only when the final bytes hash identically"}
    out = {"manifest_format": "yuclaw-gate15-study-manifest/1", "protocol_id": S.PROTOCOL_ID, "protocol_status": S.PROTOCOL_STATUS, "source": {"commit": a.commit, "tree": tree},
           "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "materials": mats, "wheel": wheel, "mode": pm["mode"],
           "self_reference": "this manifest is private and is not committed, so it can bind the exact commit without a self-reference loop"}
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n"); os.chmod(a.out, 0o600)
    print(f"[gate15] study manifest {a.out}: {len(mats)} materials bound to commit {a.commit[:12]}; wheel {wheel['label'] if wheel else 'none'}"); return 0


def cmd_evaluate(a) -> int:
    forms = sorted(Path(a.forms).glob("*.json")); sessions = []
    for f in forms:
        try:
            sessions.append(E.score_session(json.loads(f.read_text())))
        except (E.FormError, ValueError) as exc:
            print(f"[gate15] form {f.name} rejected: {exc}", file=sys.stderr); return 1
    try:
        agg = E.aggregate(sessions)
    except E.FormError as exc:
        print(f"[gate15] {exc}", file=sys.stderr); return 1
    res = {"sessions": sessions, "aggregate": agg}
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1) + "\n"); os.chmod(a.out, 0o600); print(f"[gate15] evaluated {len(sessions)} forms → {a.out}")
    else:
        print(json.dumps(agg, indent=1))
    return 0


def cmd_gate_evidence(a) -> int:
    ev = json.loads(Path(a.evaluation).read_text())["aggregate"]
    load = lambda p: json.loads(Path(p).read_text()) if p else None
    out = E.gate_evidence(ev, protocol_adoption=load(a.adoption), applicability=load(a.applicability), reviewer_appointment=load(a.reviewer), human_records=a.human_records)
    print(json.dumps({k: v for k, v in out.items() if k != "evaluation"}, indent=1)); return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw_gate15_study"); s = p.add_subparsers(dest="cmd", required=True)
    s.add_parser("schema"); s.add_parser("check-docs")
    b = s.add_parser("build-packet"); b.add_argument("out"); b.add_argument("--source", required=True); b.add_argument("--mode", required=True, choices=S.MODES); b.add_argument("--wheel"); b.add_argument("--wheel-label", choices=("REHEARSAL", "RC", "FINAL"))
    m = s.add_parser("manifest"); m.add_argument("--commit", required=True); m.add_argument("--packet", required=True); m.add_argument("--out", required=True); m.add_argument("--wheel"); m.add_argument("--wheel-label", choices=("REHEARSAL", "RC", "FINAL"))
    e = s.add_parser("evaluate"); e.add_argument("forms"); e.add_argument("--out")
    g = s.add_parser("gate-evidence"); g.add_argument("evaluation"); g.add_argument("--adoption"); g.add_argument("--applicability"); g.add_argument("--reviewer"); g.add_argument("--human-records", action="store_true")
    a = p.parse_args(argv)
    return {"schema": cmd_schema, "check-docs": cmd_check_docs, "build-packet": cmd_build_packet, "manifest": cmd_manifest, "evaluate": cmd_evaluate, "gate-evidence": cmd_gate_evidence}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
