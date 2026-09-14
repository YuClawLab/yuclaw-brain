"""Reviewer credential input (v7, V3): a token never travels as a process argument.

Accepted sources, in order of explicitness:
  * a protected file (regular file, owner-only mode 0600/0400, first line);
  * an inherited file descriptor (e.g. a pipe or `<(printf ...)`), read to EOF;
  * an interactive no-echo prompt when stdin is a terminal.
A token given on the command line is refused with actionable usage text. Tokens are never printed
and never included in exception messages. Real token custody remains an owner decision."""
from __future__ import annotations

import getpass
import os
import stat
import sys

from v3.receipts.contracts import ContractError

USAGE = ("reviewer token must not be a process argument (visible in `ps` and shell history); "
         "use --token-file <owner-only file, mode 0600>, --token-fd <inherited descriptor>, "
         "or run interactively to be prompted without echo")


def add_token_arguments(parser) -> None:
    parser.add_argument("--token-file", help="owner-only regular file (mode 0600) whose first line is the reviewer token")
    parser.add_argument("--token-fd", type=int, help="inherited file descriptor to read the reviewer token from (to EOF)")
    parser.add_argument("--token", help=argparse_suppress(), dest="_token_refused")


def argparse_suppress():
    import argparse
    return argparse.SUPPRESS


def read_token(args) -> str:
    """Resolve the token from the parsed arguments. Raises ContractError with usage text (never the token)."""
    if getattr(args, "_token_refused", None) is not None:
        raise ContractError("--token is not accepted: " + USAGE)
    tf, fd = getattr(args, "token_file", None), getattr(args, "token_fd", None)
    if tf is not None and fd is not None:
        raise ContractError("give either --token-file or --token-fd, not both")
    if tf is not None:
        return _from_file(tf)
    if fd is not None:
        return _from_fd(fd)
    if sys.stdin is not None and sys.stdin.isatty():
        tok = getpass.getpass("reviewer token (no echo): ")
        if not tok.strip():
            raise ContractError("empty token")
        return tok.strip()
    raise ContractError("no token source: " + USAGE)


def _from_file(path: str) -> str:
    try:
        st = os.lstat(path)
    except OSError as exc:
        raise ContractError(f"--token-file: cannot stat ({exc.__class__.__name__})") from None
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise ContractError("--token-file: must be a regular file (symlinks refused)")
    if st.st_mode & 0o077:
        raise ContractError("--token-file: file is readable by group/others; chmod 0600 it first")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            line = fh.readline()
    except OSError as exc:
        raise ContractError(f"--token-file: cannot read ({exc.__class__.__name__})") from None
    tok = line.strip()
    if not tok:
        raise ContractError("--token-file: first line is empty")
    return tok


def _from_fd(fd: int) -> str:
    try:
        chunks = []
        while True:
            b = os.read(fd, 4096)
            if not b:
                break
            chunks.append(b)
            if sum(len(c) for c in chunks) > 4096:
                raise ContractError("--token-fd: token too long")
    except OSError as exc:
        raise ContractError(f"--token-fd: cannot read descriptor ({exc.__class__.__name__})") from None
    tok = b"".join(chunks).decode("utf-8", "strict").strip()
    if not tok:
        raise ContractError("--token-fd: empty token")
    return tok
