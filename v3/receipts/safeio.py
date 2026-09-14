"""Shared safe byte reads (v7, V5): ONE descriptor-relative, no-follow implementation used by packet
verification, packet BUILD, artifact observation and challenge resolution.

Contract: a caller names a ROOT (a directory it is allowed to read under) and a RELATIVE path. The root is
opened once as a directory descriptor; every directory component of the relative path is opened with
O_NOFOLLOW|O_DIRECTORY relative to the previous descriptor; the file is opened with O_NOFOLLOW|O_NONBLOCK
relative to the last directory descriptor (a FIFO never blocks and is rejected as not-regular); bytes are
read from that descriptor. Swapping any ancestor after its descriptor was taken cannot redirect the chain.
Reads are bounded: a file larger than the caller's bound is refused with E_TOO_LARGE before it is read in
full. Platforms without descriptor-relative no-follow opens are refused (E_PLATFORM); the protection is
never silently dropped. Nothing is executed, imported or unpacked."""
from __future__ import annotations

import errno
import os
import posixpath
import stat
import unicodedata
from pathlib import Path

from v3.receipts.contracts import ContractError

_O_DIR = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
_O_FILE = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
_CHUNK = 1 << 20
_TEST_HOOK = None          # tests only: _TEST_HOOK(stage, rel) at "dir-opened" / "file-opened"


class SafeReadError(ContractError):
    """Read refused. `code` is stable; the message names only the relative path and the code."""
    def __init__(self, code: str, rel: str, detail: str = ""):
        self.code = code; self.rel = rel
        super().__init__(f"{code}: {rel}" + (f" ({detail})" if detail else ""))


def platform_supported() -> tuple[bool, str]:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        return False, "platform lacks O_NOFOLLOW/O_DIRECTORY"
    if os.open not in os.supports_dir_fd:
        return False, "platform lacks descriptor-relative open (dir_fd)"
    return True, "ok"


def canonical_relpath(p) -> str | None:
    """A canonical, unambiguous, relative POSIX path (no '.', '..', empty or whitespace-padded components,
    no absolute/home prefix, NFC, no control characters or backslashes); else None."""
    if not isinstance(p, str) or not p or len(p) > 512:
        return None
    if "\x00" in p or "\\" in p or any(ord(c) < 0x20 or ord(c) == 0x7F for c in p):
        return None
    if p.startswith(("/", "~")) or unicodedata.normalize("NFC", p) != p or posixpath.normpath(p) != p:
        return None
    parts = p.split("/")
    if any(part in ("", ".", "..") or part != part.strip() for part in parts):
        return None
    return p


def rel_under_root(root, path) -> str | None:
    """The canonical relative path of `path` under `root` computed TEXTUALLY on absolute, normalized paths
    (no symlink resolution — the read itself is what refuses links); None when not under the root."""
    r = os.path.normpath(os.path.abspath(os.fspath(root))); p = os.path.normpath(os.path.abspath(os.fspath(path)))
    if p == r or not p.startswith(r.rstrip(os.sep) + os.sep):
        return None
    rel = p[len(r.rstrip(os.sep)) + 1:]
    return canonical_relpath(rel)


def _is_link(name: str, dir_fd: int | None) -> bool:
    try:
        return stat.S_ISLNK(os.stat(name, dir_fd=dir_fd, follow_symlinks=False).st_mode)
    except OSError:
        return False


def _classify(exc: OSError, name: str, dir_fd: int | None, rel: str, what: str) -> SafeReadError:
    if exc.errno == errno.ENOENT:
        return SafeReadError("E_MISSING", rel)
    if exc.errno in (errno.ELOOP, errno.ENOTDIR) and _is_link(name, dir_fd):
        return SafeReadError("E_SYMLINK", rel, "links are never followed")
    if exc.errno == errno.ELOOP:
        return SafeReadError("E_SYMLINK", rel, "links are never followed")
    if exc.errno == errno.ENOTDIR:
        return SafeReadError("E_NOT_DIR", rel)
    if exc.errno in (errno.EACCES, errno.EPERM):
        return SafeReadError("E_UNREADABLE", rel)
    return SafeReadError("E_IO", rel, f"{what}: {exc.__class__.__name__}")


def open_root(path) -> int:
    """Open a caller-selected root directory (the caller's own path; it may be reached through links, the
    contained reads below never follow any)."""
    ok, why = platform_supported()
    if not ok:
        raise SafeReadError("E_PLATFORM", os.fspath(path), why)
    try:
        fd = os.open(os.fspath(path), os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0))
    except OSError as exc:
        raise _classify(exc, os.fspath(path), None, os.fspath(path), "root") from None
    return fd


def open_dir(name: str, dir_fd: int | None, rel: str = "") -> int:
    ok, why = platform_supported()
    if not ok:
        raise SafeReadError("E_PLATFORM", rel or name, why)
    try:
        return os.open(name, _O_DIR, dir_fd=dir_fd)
    except OSError as exc:
        raise _classify(exc, name, dir_fd, rel or name, "directory") from None


def read_fd(fd: int, *, max_bytes: int, rel: str = "") -> bytes:
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        raise SafeReadError("E_NOT_REGULAR", rel)
    if st.st_size > max_bytes:
        raise SafeReadError("E_TOO_LARGE", rel, f"bound {max_bytes} bytes")
    chunks, total = [], 0
    while True:
        b = os.read(fd, _CHUNK)
        if not b:
            break
        total += len(b)
        if total > max_bytes:
            raise SafeReadError("E_TOO_LARGE", rel, f"bound {max_bytes} bytes")
        chunks.append(b)
    return b"".join(chunks)


def read_contained(root_fd: int, rel: str, *, max_bytes: int) -> bytes:
    """Read <root>/<rel> through a pinned descriptor chain (see module docstring)."""
    if canonical_relpath(rel) is None:
        raise SafeReadError("E_PATH", rel, "not a canonical relative path")
    ok, why = platform_supported()
    if not ok:
        raise SafeReadError("E_PLATFORM", rel, why)
    parts = rel.split("/"); fds = []
    try:
        cur = root_fd
        for part in parts[:-1]:
            cur = open_dir(part, cur, rel); fds.append(cur)
            if _TEST_HOOK is not None:
                _TEST_HOOK("dir-opened", rel)
        try:
            fd = os.open(parts[-1], _O_FILE, dir_fd=cur)
        except OSError as exc:
            raise _classify(exc, parts[-1], cur, rel, "artifact") from None
        fds.append(fd)
        if _TEST_HOOK is not None:
            _TEST_HOOK("file-opened", rel)
        try:
            return read_fd(fd, max_bytes=max_bytes, rel=rel)
        except OSError as exc:
            raise SafeReadError("E_IO", rel, exc.__class__.__name__) from None
    finally:
        for f in fds:
            try:
                os.close(f)
            except OSError:
                pass


def read_under_root(path, root, *, max_bytes: int) -> bytes:
    """Convenience: open `root`, compute the textual relative path of `path` under it, read contained."""
    rel = rel_under_root(root, path)
    if rel is None:
        raise SafeReadError("E_OUTSIDE_ROOT", os.path.basename(os.fspath(path)))
    fd = open_root(root)
    try:
        return read_contained(fd, rel, max_bytes=max_bytes)
    finally:
        os.close(fd)
