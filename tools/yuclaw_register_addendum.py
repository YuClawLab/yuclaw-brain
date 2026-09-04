#!/usr/bin/env python3
"""
Register a clarification ADDENDUM to a LOCKED protocol on the canonical
chain (ORDER 2026-09-03B, step 1a). The addendum's full text is embedded
in the chain line; its method hash is the sha256 of the text file's exact
bytes (the file is committed first; the hash binds the file). The parent
METHOD_SPEC is never edited.

Usage:
  python3 tools/yuclaw_register_addendum.py --protocol bace258b0bbb \
      --file tools/A1_layered_dependency_v1.txt \
      --name "Layered Evidence Dependency v1 — Clarification Addendum A1 (FINAL v2)" \
      --scope "SMH pilot FIRST READ only; READ_SCOPE = STRUCTURAL_ONLY"
Prints the new line number, line hash, method hash and registration UTC.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "tools"))
from yuclaw_protocol_registry import Registry  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--scope", default="")
    a = ap.parse_args()
    path = (_REPO / a.file).resolve()
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    file_sha = hashlib.sha256(raw).hexdigest()
    if hashlib.sha256(text.encode("utf-8")).hexdigest() != file_sha:
        raise SystemExit("text re-encode does not reproduce file bytes")
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    before = len(reg._lines)
    t_reg = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f+00:00")
    line_hash = reg.register_addendum(
        a.protocol, text, a.name,
        source_file=str(path.relative_to(_REPO)),
        registered_utc=t_reg, scope=a.scope)
    Registry(str(_REPO / "registry" / "protocols.jsonl"))  # re-verify chain
    print(f"[register-addendum] line {before + 1} · line_hash {line_hash} · "
          f"method_hash(sha256 of {path.name}) {file_sha} · "
          f"addendum_id {file_sha[:12]} · registered_utc {t_reg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
