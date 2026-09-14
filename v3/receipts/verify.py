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

from v3.receipts import safeio
from v3.receipts.contracts import ContractError, format_ts, validate_binding_claim

ARTIFACT_READ_BOUND = 256 << 20        # safety bound on one artifact read (not a data cap): larger files are refused, never truncated


def sha256_len(data: bytes) -> tuple[str, int]:
    return hashlib.sha256(data).hexdigest(), len(data)


def read_under_root(path: str | os.PathLike, allowed_roots: list[str | os.PathLike]) -> bytes:
    """Read a regular file only if it lies under one of the allowed roots — through the SHARED
    descriptor-relative, no-follow reader (safeio): the relative path is computed textually, then every
    component is opened relative to the previous descriptor, so a swapped ancestor cannot redirect the read."""
    last = None
    for root in allowed_roots:
        rel = safeio.rel_under_root(root, path)
        if rel is None:
            continue
        try:
            return safeio.read_under_root(path, root, max_bytes=ARTIFACT_READ_BOUND)
        except safeio.SafeReadError as exc:
            last = exc
            if exc.code == "E_OUTSIDE_ROOT":
                continue
            raise
    if last is not None:
        raise last
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
