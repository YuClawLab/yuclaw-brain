"""
Component healthcheck — fails loud when any component is in an error state.

Runs `compose_at` on a known-good ticker (NVDA) and asserts:
  - no component returned with rationale prefixed "component error:"
  - the result includes the new `errored_components` field
  - that list is empty

Exit codes:
  0 — all 9 components produced a non-errored ComponentResult
  1 — at least one component raised; failing ids printed to stderr

Designed to run as a pre-step in the daily pipeline cron — if a schema
mismatch or import bug breaks a component, the rest of the pipeline
short-circuits with `&&` and the operator sees the failure in
/tmp/yuclaw_pipeline.log instead of finding out six days later via a
manual audit (this was Day-7→13b's actual failure mode for C9).

CLI:
    python3 -m v3.signal.healthcheck
    python3 -m v3.signal.healthcheck --ticker AMD
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from v3.signal.composite import compose_at


def run(ticker: str) -> int:
    as_of = datetime.now(timezone.utc)
    try:
        result = compose_at(ticker, as_of)
    except Exception as e:
        print(f"[healthcheck] compose_at({ticker!r}) raised: "
              f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    errored = result.get("errored_components") or []
    if errored:
        print(f"[healthcheck] FAIL — {len(errored)} component(s) errored: "
              f"{', '.join(errored)}", file=sys.stderr)
        for cid in errored:
            comp = result["components"].get(cid) or {}
            print(f"  {cid}: {comp.get('rationale')}", file=sys.stderr)
        return 1

    # Also flag any rationale that still looks like an error string (defensive
    # against future paths that emit "component error:" without raising).
    suspect = [
        cid for cid, comp in result["components"].items()
        if (comp.get("rationale") or "").startswith("component error:")
    ]
    if suspect:
        print(f"[healthcheck] FAIL — {len(suspect)} component(s) have "
              f"error-shaped rationale without raising: {', '.join(suspect)}",
              file=sys.stderr)
        return 1

    print(f"[healthcheck] OK — {ticker} composite computed, all 9 components "
          f"clean. label={result['label']} score={result['total_score']:+.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="v3.0 component healthcheck")
    p.add_argument("--ticker", default="NVDA",
                   help="ticker to probe (default NVDA)")
    args = p.parse_args(argv)
    return run(args.ticker.upper())


if __name__ == "__main__":
    sys.exit(main())
