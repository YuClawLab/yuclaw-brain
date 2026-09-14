#!/usr/bin/env python3
"""Gate #15 materials manifest (v7): bind the comprehension-study materials by SHA-256 + byte length and
source identity. Generated, never typed. Writes docs/methodology/gate15_materials_manifest.json.

  python3 tools/yuclaw_gate15_materials.py --write [--wheel FILE --wheel-label REHEARSAL|RC|FINAL] [--packet DIR]

The manifest is descriptive: it does not adopt the protocol, designate a reviewer or change Gate #15."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
OUT = _REPO / "docs" / "methodology" / "gate15_materials_manifest.json"
MATERIALS = [
    ("docs/methodology/gate15_formative_study_kit.md", "task script, rubric, scoring key"),
    ("README.md", "Task 1 input: frozen CLI transcript block"),
    ("docs/evidence_scoreboard.html", "Task 3 input"),
    ("docs/receipts/scoreboard.json", "Task 3 input (machine copy)"),
    ("docs/index.html", "Task 4 input"),
    ("docs/capabilities.json", "Task 4 input (version + endpoints)"),
    ("docs/replay/lab_replay_bundle.json", "Task 2 replay target (as packaged)"),
]
WHEEL_LABELS = ("REHEARSAL", "RC", "FINAL")


def _git(*a) -> str:
    r = subprocess.run(["git", "--no-optional-locks", *a], cwd=_REPO, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _sha_len(p: Path) -> tuple[str, int]:
    b = p.read_bytes(); return hashlib.sha256(b).hexdigest(), len(b)


def build(wheel: Path | None, wheel_label: str | None, packet: Path | None) -> dict:
    head, tree = _git("rev-parse", "HEAD"), _git("rev-parse", "HEAD^{tree}")
    mats = []
    for rel, role in MATERIALS:
        p = _REPO / rel
        if not p.is_file():
            mats.append({"path": rel, "role": role, "status": "ABSENT"}); continue
        h, n = _sha_len(p); mats.append({"path": rel, "role": role, "sha256": h, "size_bytes": n, "status": "PRESENT", "source_head": head, "source_tree": tree})
    out = {"manifest_format": "yuclaw-gate15-materials/1", "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": {"head": head, "tree": tree}, "materials": mats,
           "wheel": None, "packet": None,
           "meaning": "descriptive binding of study materials; adopts nothing, designates nobody, changes no gate; a session against different hashes is a different study"}
    if wheel is not None:
        if wheel_label not in WHEEL_LABELS:
            raise SystemExit(f"--wheel-label must be one of {WHEEL_LABELS}")
        h, n = _sha_len(wheel)
        out["wheel"] = {"filename": wheel.name, "sha256": h, "size_bytes": n, "label": wheel_label,
                        "note": ("NOT the final artifact; a study on this wheel covers only these bytes" if wheel_label != "FINAL" else "final frozen artifact")}
    if packet is not None:
        mp = packet / "PACKET_MANIFEST.json"
        if not mp.is_file():
            raise SystemExit("--packet: PACKET_MANIFEST.json missing")
        h, n = _sha_len(mp); out["packet"] = {"manifest_sha256": h, "manifest_size_bytes": n}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); ap.add_argument("--wheel"); ap.add_argument("--wheel-label"); ap.add_argument("--packet")
    a = ap.parse_args(argv)
    man = build(Path(a.wheel) if a.wheel else None, a.wheel_label, Path(a.packet) if a.packet else None)
    txt = json.dumps(man, indent=1, sort_keys=True) + "\n"
    if a.write:
        OUT.write_text(txt); print(f"[gate15-materials] wrote {OUT.relative_to(_REPO)} ({len(man['materials'])} materials; wheel {man['wheel']['label'] if man['wheel'] else 'none'})")
    else:
        print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
