"""Console entry point for the `yuclaw` command (v4).

`yuclaw <cmd> …` resolves here → the v4 command dispatcher
(why · memo · cascade · share · verify · keys · demo + legacy v3 helpers).
"""
from __future__ import annotations

import sys

from v3.cli.__main__ import main as _dispatch


def main(argv: list[str] | None = None) -> int:
    return _dispatch(argv)


if __name__ == "__main__":
    sys.exit(main())
