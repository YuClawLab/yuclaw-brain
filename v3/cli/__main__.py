"""Dispatch entry point so `python3 -m v3.cli why TICKER` works."""
from __future__ import annotations

import sys

from v3.cli import why as why_cmd
from v3.cli import replay as replay_cmd
from v3.cli import validation as validation_cmd
from v3.cli import profile as profile_cmd
from v3.cli import watch as watch_cmd
from v3.cli import brief as brief_cmd
from v3.cli import verify as verify_cmd

COMMANDS = {
    "why": why_cmd.main,
    "replay": replay_cmd.main,
    "validation": validation_cmd.main,
    "profile": profile_cmd.main,
    "watch": watch_cmd.main,
    "brief": brief_cmd.main,
    "verify": verify_cmd.main,
}


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print(f"usage: python3 -m v3.cli <command> [args]\n"
              f"commands: {', '.join(sorted(COMMANDS))}", file=sys.stderr)
        return 2
    cmd, *rest = argv
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}\n"
              f"commands: {', '.join(sorted(COMMANDS))}", file=sys.stderr)
        return 2
    return COMMANDS[cmd](rest)


if __name__ == "__main__":
    sys.exit(main())
