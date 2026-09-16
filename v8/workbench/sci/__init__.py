"""YUCLAW v8 scientific kernel, adapted into the workbench (V8-005).

Adapted from the owner's uncommitted local preview (reference bundle YUCLAW-V8-005-SCI-inputs, base commit
c34e19bffb1a9f8851bf03ac1e64b68be3bcb710; the base commit does not contain these files). Apache License 2.0 notices of
the source checkout are retained (reference/LICENSE in the private input record). The supported statistical contract is
unchanged: paired binary-probability predictions scored by Brier improvement, sequential evidence as a fixed mixture of
Hoeffding test supermartingales, a frozen family alpha allocation, pending outcomes, invalidation and exploratory status.
No new statistical method is introduced. The preview's SQLite journal and CLI are deliberately not adapted: the workbench
never opens caller-supplied database files; a science journal reaches it as a bounded JSON event list and its replays are
recorded in the workspace's own append-only journal. Research and education only. Not investment advice.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

SCHEMA_VERSION = "yuclaw.science.v8.1"
ADAPTED_FROM = {"bundle": "YUCLAW-V8-005-SCI-inputs.zip", "bundle_sha256": "194143f33775ab8c547a0f03d8a5d2f9317c7c32612a455c7d400db9a3b31a77", "base_commit": "c34e19bffb1a9f8851bf03ac1e64b68be3bcb710",
                "reference_sha256": {"v4/science/__init__.py": "46abfce46bd9", "v4/science/contracts.py": "884c11885518", "v4/science/statistics.py": "2de25c69a1da", "v4/science/store.py": "7a02e27acf7e", "v4/science/evidence.py": "f66cc226ec1b"},
                "reference_sha256_note": "12-hex prefixes of the reference files' SHA-256 as listed in the bundle manifest; full digests in the private input record"}
_KERNEL_FILES = ("contracts.py", "statistics.py", "store.py")


def kernel_identity() -> dict:
    """Identity of the adapted kernel as installed: sha256 over the packaged kernel module sources (in a fixed order)."""
    here = Path(__file__).resolve().parent
    parts = [(f, hashlib.sha256((here / f).read_bytes()).hexdigest()) for f in _KERNEL_FILES]
    return {"schema": SCHEMA_VERSION, "modules": dict(parts), "kernel_sha256": hashlib.sha256("\n".join(f"{f} {h}" for f, h in parts).encode()).hexdigest(),
            "method": "paired_brier_improvement scored per unit; sequential log e-value = log of a fixed mixture (lambdas 1/16..1) of Hoeffding test supermartingales under a bounded conditional-mean null; a claim's threshold is -log(alpha) with a frozen family allocation"}
