"""Private-store location boundary (v7, V5): ONE check for every store kind and every caller.

A receipt/challenge/decision store must never live inside a checkout's public tree (a `docs/` directory
whose parent holds `release_manifest.json`) — neither by its literal path nor through a symlink alias.
The check runs BEFORE any mkdir/chmod/key creation/append. An existing path that is not a readable and
writable directory is UNAVAILABLE (E_UNAVAILABLE): a new empty store is never created elsewhere to
disguise it. Temporary synthetic stores (any private directory the caller may create) are allowed."""
from __future__ import annotations

import os
from pathlib import Path

from v3.receipts.contracts import ContractError


class StorageError(ContractError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(f"{code}" + (f": {detail}" if detail else ""))


def _in_public_tree(p: Path) -> bool:
    for parent in [p] + list(p.parents):
        if parent.name == "docs" and (parent.parent / "release_manifest.json").exists():
            return True
    return False


def resolve_store_root(path, *, create: bool = True) -> Path:
    """Validate a store location and return its Path. Raises StorageError(E_PUBLIC_TREE | E_NOT_DIR |
    E_UNAVAILABLE | E_MISSING) — never creates anything when the location is refused or unavailable."""
    raw = Path(os.fspath(path))
    literal = Path(os.path.normpath(os.path.abspath(raw)))
    try:
        resolved = literal.resolve(strict=False)
    except (OSError, RuntimeError):
        raise StorageError("E_UNAVAILABLE", "store path cannot be resolved") from None
    for cand in (literal, resolved):
        if _in_public_tree(cand):
            raise StorageError("E_PUBLIC_TREE", "a private store must not live inside a public docs tree (literal path or symlink alias)")
    if literal.exists() or literal.is_symlink():
        if not literal.is_dir():
            raise StorageError("E_NOT_DIR", "store path exists but is not a directory")
        if not (os.access(literal, os.R_OK) and os.access(literal, os.W_OK) and os.access(literal, os.X_OK)):
            raise StorageError("E_UNAVAILABLE", "existing store is not readable/writable (a new store is never created in its place)")
        return literal
    if not create:
        raise StorageError("E_MISSING", "store does not exist")
    parent = literal.parent
    if parent.exists() and not (os.access(parent, os.W_OK) and os.access(parent, os.X_OK)):
        raise StorageError("E_UNAVAILABLE", "store parent is not writable")
    try:
        literal.mkdir(parents=True, exist_ok=True)
        os.chmod(literal, 0o700)
    except OSError as exc:
        raise StorageError("E_UNAVAILABLE", f"cannot create store ({exc.__class__.__name__})") from None
    return literal
