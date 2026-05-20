"""
`yuclaw profile` — inspect and update the local user profile.

CLI:
    python3 -m v3.cli profile show
    python3 -m v3.cli profile set alert_threshold 0.20
    python3 -m v3.cli profile set channels.telegram false
    python3 -m v3.cli profile set display.top_n 15
"""
from __future__ import annotations

import argparse
import json
import sys

from v3.profile.store import PROFILE_PATH, ProfileError, load_profile, set_value


def _show() -> int:
    prof = load_profile()
    print(f"profile: {PROFILE_PATH}")
    print(json.dumps(prof, indent=2, sort_keys=True))
    return 0


def _set(key: str, value: str) -> int:
    try:
        k, v = set_value(key, value)
    except ProfileError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"OK  {k} = {v}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw profile",
                                description="Inspect / update local user profile")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("show")
    set_p = sub.add_parser("set")
    set_p.add_argument("key")
    set_p.add_argument("value")
    args = p.parse_args(argv)

    if args.cmd in (None, "show"):
        return _show()
    if args.cmd == "set":
        return _set(args.key, args.value)
    return 2


if __name__ == "__main__":
    sys.exit(main())
