"""Dispatch entry point so `yuclaw <cmd>` / `python3 -m v3.cli <cmd>` works.

Commands are imported LAZILY (only when invoked) so the CLI starts fast and a
single command's optional deps never block the others.
"""
from __future__ import annotations

import importlib
import sys

# name -> "module:attr" of a `main(argv) -> int` callable.
COMMANDS: dict[str, str] = {
    # v4 surface
    "why": "v4.api.why_cli:main",
    "memo": "v4.memo.cli:main",
    "cascade": "v4.api.cascade_cli:main",
    "share": "v4.share.cli:main",
    "keys": "v4.auth.cli:main",
    "demo": "v4.demo.cli:main",
    "verify": "v3.cli.verify:main",
    # legacy v3 helpers (kept available; not part of the documented v4 surface)
    "replay": "v3.cli.replay:main",
    "validation": "v3.cli.validation:main",
    "profile": "v3.cli.profile:main",
    "watch": "v3.cli.watch:main",
    "brief": "v3.cli.brief:main",
}


def _resolve(spec: str):
    mod, attr = spec.split(":")
    return getattr(importlib.import_module(mod), attr)


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(f"usage: yuclaw <command> [args]\ncommands: {', '.join(sorted(COMMANDS))}",
              file=sys.stderr)
        return 2
    cmd, *rest = argv
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}\ncommands: {', '.join(sorted(COMMANDS))}", file=sys.stderr)
        return 2
    return _resolve(COMMANDS[cmd])(rest)


if __name__ == "__main__":
    sys.exit(main())
