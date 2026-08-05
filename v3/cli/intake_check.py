"""
yuclaw intake-check — client-side pre-check of a signal CSV against the
SAME rules the Signal Review intake enforces server-side (the packaged
tools.yuclaw_client_intake is the single shared implementation, so the
two can never drift): required columns date,ticker,signal_value (optional
as_of/generated_at, nothing else), ISO dates, finite values, no duplicate
ticker-days, nothing future-dated, nothing dated after its own
as_of/generated_at (lookahead-suspicious).

Runs entirely locally. The file is read, checked, and reported — it is
never transmitted anywhere by this command.
"""
from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: yuclaw intake-check YOUR_SIGNALS.csv\n"
              "Checks a signal file locally against the Signal Review "
              "intake rules.\nExit 0 = would be accepted; exit 2 = fix the "
              "listed rows first.")
        return 0 if argv else 2
    from tools.yuclaw_client_intake import IntakeError, validate
    path = argv[0]
    try:
        rows, report = validate(path)
    except IntakeError as exc:
        print(f"INTAKE-CHECK: {path} would be REFUSED:")
        for p in exc.problems:
            print(f"  · {p}")
        print("\nFix the rows above and re-run. Nothing was transmitted — "
              "this check ran entirely on your machine.")
        return 2
    print(f"INTAKE-CHECK OK: {path}")
    print(f"  {report['n_rows']} clean rows · {report['n_tickers']} tickers "
          f"· {report['n_dates']} signal dates · "
          f"{report['date_range'][0]} → {report['date_range'][1]}")
    print("\nNext step: request a Signal Review slot "
          "(https://yuclaw.ca/signal_review.html). Your protocol is "
          "registered and hash-locked before any computation touches this "
          "file. Nothing was transmitted — this check ran entirely on "
          "your machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
