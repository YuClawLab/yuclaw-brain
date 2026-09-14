"""Artifact verification from ACTUAL bytes (v7 receipts).

An observation records what the verifier established: artifact type as declared, sha256 and byte
length computed from bytes it actually read, and whether they equal the participant's claim. A
structurally valid hash in a submission is NOT verification. Bytes come only from (a) a bytes object
handed in by the caller or (b) a regular file under an explicitly allowed root (symlink escapes and
outside-root paths are refused). Nothing is fetched, executed, imported or unpacked."""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from v3.receipts.contracts import ContractError, format_ts, validate_binding_claim


def sha256_len(data: bytes) -> tuple[str, int]:
    return hashlib.sha256(data).hexdigest(), len(data)


def read_under_root(path: str | os.PathLike, allowed_roots: list[str | os.PathLike]) -> bytes:
    """Read a regular file only if its resolved path is inside one of the allowed roots."""
    p = Path(path)
    if p.is_symlink():
        raise ContractError(f"refusing symlink artifact path: {p.name}")
    rp = p.resolve(strict=True)
    if not rp.is_file():
        raise ContractError("artifact path is not a regular file")
    for root in allowed_roots:
        r = Path(root).resolve()
        try:
            rp.relative_to(r)
            return rp.read_bytes()
        except ValueError:
            continue
    raise ContractError("artifact path is outside every allowed root")


def observe(binding_claim: dict, *, data: bytes | None = None, path=None, allowed_roots=(), now: datetime | None = None) -> dict:
    """Build an OBSERVATION for a claimed binding. verified=True only when the actual bytes' sha256 AND
    length equal the claim. Unavailable bytes → verified=False, source='unavailable' (never a guess)."""
    claim = validate_binding_claim(binding_claim)
    ts = format_ts(now or datetime.now(timezone.utc))
    if data is None and path is not None:
        data = read_under_root(path, list(allowed_roots))
        source = "path"
    elif data is not None:
        source = "bytes"
    else:
        return {"artifact_type": claim["artifact_type"], "claimed_sha256": claim["sha256"], "claimed_size_bytes": claim["size_bytes"],
                "observed_sha256": None, "observed_size_bytes": None, "verified": False, "source": "unavailable", "observed_at": ts}
    h, n = sha256_len(data)
    return {"artifact_type": claim["artifact_type"], "claimed_sha256": claim["sha256"], "claimed_size_bytes": claim["size_bytes"],
            "observed_sha256": h, "observed_size_bytes": n, "verified": (h == claim["sha256"] and n == claim["size_bytes"]),
            "source": source, "observed_at": ts}


def same_artifact(obs_a: dict, obs_b: dict) -> bool:
    """Two observations concern the same artifact only if type, sha256 and length all match."""
    return all(obs_a.get(k) == obs_b.get(k) for k in ("artifact_type", "observed_sha256", "observed_size_bytes")) and obs_a.get("observed_sha256") is not None
