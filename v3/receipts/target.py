"""Release TARGET manifest (v7, V5): the independently supplied set of exact artifacts that exact-release
coverage is measured against. It is RELEASE EVIDENCE, separate from the packaged source: it is generated
from a release record (rehearsal/RC record → label REHEARSAL/RC; the frozen Phase-2 record → FINAL) and is
never embedded in the artifacts it describes. Coverage counts only qualified, successful attempts whose
observed (artifact_type, sha256, size_bytes) equals a target artifact — tags, source labels, prefixes or a
matching hash with a different length never qualify. Without a target manifest the exact-target coverage
is UNBOUND, not a measured zero."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts.contracts import ContractError, PACKAGE_ARTIFACTS, format_ts, parse_ts

TARGET_FORMAT = "yuclaw-release-target/1"
LABELS = ("REHEARSAL", "RC", "FINAL")
SOURCES = ("rehearsal-record", "phase2-release-record")
_HEX64 = re.compile(r"^[0-9a-f]{64}$"); _SHA40 = re.compile(r"^[0-9a-f]{40}$"); _TAG = re.compile(r"^v?[0-9][A-Za-z0-9.\-]{0,31}$"); _FN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,127}$")


def validate_target(obj) -> dict:
    if not isinstance(obj, dict):
        raise ContractError("target: object required")
    want = {"target_format", "label", "release", "artifacts", "generated_from", "generated_at"}
    if set(obj) != want:
        raise ContractError("target: keys must be exactly " + ", ".join(sorted(want)))
    if obj["target_format"] != TARGET_FORMAT:
        raise ContractError("target: unknown target_format")
    if obj["label"] not in LABELS:
        raise ContractError("target: label must be REHEARSAL, RC or FINAL")
    if obj["generated_from"] not in SOURCES:
        raise ContractError("target: generated_from must be rehearsal-record or phase2-release-record")
    if obj["label"] == "FINAL" and obj["generated_from"] != "phase2-release-record":
        raise ContractError("target: a FINAL target may only be generated from the frozen Phase-2 release record")
    parse_ts(obj["generated_at"], "target.generated_at")
    rel = obj["release"]
    if not isinstance(rel, dict) or set(rel) != {"tag", "version", "source_sha", "source_tree"}:
        raise ContractError("target.release: {tag, version, source_sha, source_tree} required")
    if not (isinstance(rel["tag"], str) and _TAG.match(rel["tag"]) and isinstance(rel["version"], str) and 1 <= len(rel["version"]) <= 32):
        raise ContractError("target.release: tag/version shape")
    if not (isinstance(rel["source_sha"], str) and _SHA40.match(rel["source_sha"]) and isinstance(rel["source_tree"], str) and _SHA40.match(rel["source_tree"])):
        raise ContractError("target.release: source_sha/source_tree must be 40 lowercase hex")
    arts = obj["artifacts"]
    if not isinstance(arts, list) or not arts or len(arts) > 16:
        raise ContractError("target.artifacts: 1..16 entries required")
    seen = set(); out = []
    for i, a in enumerate(arts):
        if not isinstance(a, dict) or set(a) != {"artifact_type", "filename", "sha256", "size_bytes"}:
            raise ContractError(f"target.artifacts[{i}]: {{artifact_type, filename, sha256, size_bytes}} required")
        if a["artifact_type"] not in PACKAGE_ARTIFACTS:
            raise ContractError(f"target.artifacts[{i}]: artifact_type must be wheel or sdist")
        if not (isinstance(a["filename"], str) and _FN.match(a["filename"])):
            raise ContractError(f"target.artifacts[{i}]: filename shape")
        if not (isinstance(a["sha256"], str) and _HEX64.match(a["sha256"])):
            raise ContractError(f"target.artifacts[{i}]: sha256 must be 64 lowercase hex")
        n = a["size_bytes"]
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            raise ContractError(f"target.artifacts[{i}]: size_bytes must be a positive integer")
        key = (a["artifact_type"], a["sha256"], n)
        if key in seen:
            raise ContractError(f"target.artifacts[{i}]: duplicate artifact")
        seen.add(key); out.append({"artifact_type": a["artifact_type"], "filename": a["filename"], "sha256": a["sha256"], "size_bytes": n})
    return {"target_format": TARGET_FORMAT, "label": obj["label"], "release": dict(rel), "artifacts": out, "generated_from": obj["generated_from"], "generated_at": obj["generated_at"]}


def build_target(*, label: str, generated_from: str, tag: str, version: str, source_sha: str, source_tree: str, artifacts: list[dict], now: datetime | None = None) -> dict:
    return validate_target({"target_format": TARGET_FORMAT, "label": label, "generated_from": generated_from,
                            "release": {"tag": tag, "version": version, "source_sha": source_sha, "source_tree": source_tree},
                            "artifacts": artifacts, "generated_at": format_ts(now or datetime.now(timezone.utc))})


def load_target(path) -> dict:
    """{'status': 'OK'|'ABSENT'|'INVALID', 'target': dict|None, 'code': str}"""
    p = Path(path)
    if not p.exists():
        return {"status": "ABSENT", "target": None, "code": "E_ABSENT"}
    try:
        return {"status": "OK", "target": validate_target(json.loads(p.read_text(encoding="utf-8"))), "code": "OK"}
    except (OSError, ValueError, UnicodeDecodeError):
        return {"status": "INVALID", "target": None, "code": "E_UNREADABLE"}
    except ContractError:
        return {"status": "INVALID", "target": None, "code": "E_SCHEMA"}


def coverage(derived: list[dict], target: dict | None) -> dict:
    """Exact-target coverage from derived rows. Only qualified AND successful rows with FULL binding count,
    and only when (artifact_type, sha256, size_bytes) equals a target artifact exactly."""
    if target is None:
        return {"state": "UNBOUND", "note": "no target manifest supplied; exact-target coverage is not measured (not zero)", "per_artifact": [], "artifacts_covered": None, "artifacts_total": None, "successful_package_reproductions": None}
    rows = [r for r in derived if r["qualified"] and r["successful"] and r["binding_completeness"] == "FULL"]
    per = []
    for a in target["artifacts"]:
        hits = [r for r in rows if (r["submission"]["artifact_binding"]["artifact_type"], r["submission"]["artifact_binding"]["sha256"], r["submission"]["artifact_binding"]["size_bytes"]) == (a["artifact_type"], a["sha256"], a["size_bytes"])]
        per.append({"artifact_type": a["artifact_type"], "filename": a["filename"], "sha256": a["sha256"], "size_bytes": a["size_bytes"],
                    "qualified_successful_attempts": len(hits), "distinct_persons": len({r["submission"]["participant_id"] for r in hits}),
                    "distinct_groups": len({r["submission"]["group_id"] for r in hits if r["submission"]["group_id"]}), "covered": bool(hits)})
    return {"state": "BOUND", "label": target["label"], "release": dict(target["release"]), "per_artifact": per,
            "artifacts_covered": sum(1 for p in per if p["covered"]), "artifacts_total": len(per),
            "successful_package_reproductions": sum(p["qualified_successful_attempts"] for p in per),
            "note": "counts only qualified successful attempts whose observed bytes equal a target artifact (type, sha256 and length); a wheel never covers its sdist; a rehearsal/RC target never impersonates the final target"}
