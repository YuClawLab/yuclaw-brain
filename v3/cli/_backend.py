"""Backend-unavailable convention shared by backend-connected commands (5.1.0 pattern; 8.0.1 C02/C03).

Exit-code contract: 0 = success · 1 = ran, negative result · 2 = usage or validation error · 3 = environment
unsupported. A research backend that cannot be reached is 3, with a message — never a traceback, and never an empty
"success": "the backend could not be asked" is a different fact from "the backend was asked and had nothing".

Only EXPECTED connection failures are recognized here (the database driver's OperationalError and the evidence
core's BackendUnavailable). Bad arguments, absent data and internal failures keep their own paths; nothing else is caught.
"""
from __future__ import annotations

import json
import re
import sys

EXIT_BACKEND_UNAVAILABLE = 3
STATUS = "BACKEND_UNAVAILABLE"
_SECRET = re.compile(r"(?i)(password|passwd|pwd|sslpassword)\s*=\s*\S+|(?<=://)[^/\s:@]+:[^@\s]+(?=@)")


def is_backend_unavailable(exc: BaseException) -> bool:
    from v3.evidence import BackendUnavailable
    if isinstance(exc, BackendUnavailable):
        return True
    try:
        import psycopg2
    except ImportError:
        return False
    return isinstance(exc, psycopg2.OperationalError)


def detail(exc: BaseException, limit: int = 200) -> str:
    """Bounded, single-line, with anything that looks like a credential removed (connection errors name hosts and
    socket paths; they must never carry a password)."""
    text = _SECRET.sub("<redacted>", " ".join(str(exc).split()))
    return f"{type(exc).__name__}: {text[:limit]}"


def report(command: str, exc: BaseException, *, as_json: bool = False, offline: str = "") -> int:
    """The message on stderr; with --json also a structured status on stdout. Returns the exit code (3)."""
    msg = (f"backend unavailable: `yuclaw {command}` reads the YUCLAW research backend (Postgres evidence store), "
           f"which could not be reached from this machine. This is NOT a result: nothing was queried.\n"
           f"  detail: {detail(exc)}\n")
    if offline:
        msg += f"  offline instead: {offline}\n"
    msg += "  to connect a backend: docs/v4/backend_setup.md"
    print(msg, file=sys.stderr)
    if as_json:
        print(json.dumps({"status": STATUS, "command": command, "queried": False, "result": None, "detail": detail(exc),
                          "exit_code": EXIT_BACKEND_UNAVAILABLE}, indent=2))
    return EXIT_BACKEND_UNAVAILABLE
