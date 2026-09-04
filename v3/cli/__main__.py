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
    # v5.0: one-command Validation Lab reproduction (packaged mirror of
    # tools/replay_lab.py — the standalone stdlib script keeps working as-is)
    "replay-lab": "v3.lab.replay_check:main",
    # usefulness build (2026-07-16): derived-data exports + lens summaries
    "events": "v3.cli.events:main",
    # 5.2: Signal Review client-side pre-check (local-only, never transmits)
    "intake-check": "v3.cli.intake_check:main",
    # 5.3: Evidence Passport — deterministic claim check
    "check-claim": "v3.cli.check_claim:main",
    "lens": "v3.cli.lens:main",
    "export": "v3.cli.export:main",
    # legacy v3 helpers (kept available; not part of the documented v4 surface)
    "replay": "v3.cli.replay:main",
    "validation": "v3.cli.validation:main",
    "profile": "v3.cli.profile:main",
    "watch": "v3.cli.watch:main",
    "brief": "v3.cli.brief:main",
}


# One-line descriptions for `yuclaw --help` (ORDER 2026-09-05B D1). Every
# command in COMMANDS has one; the help gate in the abuse matrix asserts it.
DESCRIPTIONS: dict[str, str] = {
    "why": "composite classification + ranked evidence with SEC source URLs for one ticker",
    "memo": "evidence memo for a ticker — grounded, citation-verified, language-linted",
    "cascade": "supply-chain cascade view for a ticker (deterministic, evidence-backed)",
    "share": "share a research view (derived data only)",
    "keys": "manage API keys for the REST server",
    "demo": "3-minute guided offline journey — zero config, no backend",
    "verify": "Verified Research Ledger integrity check for a ticker/date",
    "replay-lab": "reproduce the Validation Lab from the public bundle (exit 0 = reproduced)",
    "events": "accepted-events export (derived data only)",
    "intake-check": "client-side pre-check of a signal CSV for Signal Review (never transmits)",
    "check-claim": "Evidence Passport — deterministic claim check (--text, --ticker/--type/--date-range, --accession)",
    "lens": "lens summary-card data as JSON (the numbers the page renders)",
    "export": "lens events export (--format csv|json; --page builds the evidence packet)",
    "replay": "point-in-time classification for a ticker at end of a date",
    "validation": "in-sample event validation + forward tracking ledger (text)",
    "profile": "ticker profile (legacy v3 helper)",
    "watch": "watch a ticker for new evidence (legacy v3 helper)",
    "brief": "evidence brief (legacy v3 helper)",
}
EXIT_CODES = ("Exit codes: 0 = success · 1 = operation ran, negative result "
              "(e.g. verify mismatch, replay-lab mismatch) · "
              "2 = usage/validation error · 3 = environment unsupported")


def help_text() -> str:
    width = max(len(c) for c in COMMANDS)
    lines = [f"yuclaw {_version()} — evidence-first financial research CLI "
             f"(research and education only; not investment advice)",
             "", "usage: yuclaw <command> [args]   ·   yuclaw <command> --help", "", "commands:"]
    for name in sorted(COMMANDS):
        lines.append(f"  {name.ljust(width)}  {DESCRIPTIONS.get(name, '')}")
    lines += ["", EXIT_CODES]
    return "\n".join(lines)


def _resolve(spec: str):
    mod, attr = spec.split(":")
    return getattr(importlib.import_module(mod), attr)


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("yuclaw")
    except Exception:
        return "unknown (not installed as a distribution)"


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] in ("--version", "version", "-V"):
        print(f"yuclaw {_version()}")
        return 0
    if argv and argv[0] in ("--help", "-h", "help"):
        print(help_text())
        return 0
    if not argv:
        print(f"usage: yuclaw <command> [args]   (yuclaw --help lists the commands)\n"
              f"commands: {', '.join(sorted(COMMANDS))}\n{EXIT_CODES}",
              file=sys.stderr)
        return 2
    cmd, *rest = argv
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd!r}\ncommands: {', '.join(sorted(COMMANDS))}\n"
              f"(yuclaw --help lists them with one-line descriptions)", file=sys.stderr)
        return 2
    return _resolve(COMMANDS[cmd])(rest)


if __name__ == "__main__":
    sys.exit(main())
