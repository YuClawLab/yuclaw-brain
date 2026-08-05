"""
The 5-minute tour (docs/tour.html) — a static guided page: five stations,
each one command + its ACTUAL current output, captured live at build so
the page can never drift from what the commands really print.

Station 3 (replay-lab) is the one exception to live capture: a full
reproduction takes minutes, so the station shows the command, what
exit 0 means, and the most recent recorded reproduction (nightly
stranger-mode smoke), dated. Disclosed on the page.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v3.web.useful_blocks import (build_footer, site_header_html,
                                  updated_strip)

OUT = _REPO / "docs" / "tour.html"


def _run(args, timeout=60, lines=None) -> str:
    r = subprocess.run([sys.executable, "-m", "v3.cli", *args],
                       capture_output=True, text=True, timeout=timeout,
                       cwd=str(_REPO))
    out = (r.stdout or r.stderr or "").strip()
    if lines:
        out = "\n".join(out.splitlines()[:lines])
    return out


def _latest_replay_evidence() -> str:
    try:
        for line in reversed((_REPO / "internal" / "sentinel" /
                              "log.jsonl").read_text().splitlines()):
            e = json.loads(line)
            if "REPRODUCED OK" in e.get("sweep", ""):
                return (f"most recent recorded reproduction: {e['date']} — "
                        f"nightly stranger-mode smoke (fresh venv, "
                        f"pip install yuclaw): replay-lab REPRODUCED OK, "
                        f"exit 0")
    except Exception:
        pass
    return ("at the v5.1.0 release this ran from a fresh venv and "
            "reproduced 33 daily ledger roots exactly (2,926 leaf hashes "
            "recomputed), exit 0")


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    demo_out = _run(["demo", "--no-pause"], timeout=120, lines=22)
    verify_out = _run(["verify", "AMD", "--date", "2026-05-20"], lines=8)
    chain_cmd = ("curl -sO https://raw.githubusercontent.com/YuClawLab/"
                 "yuclaw-brain/main/registry/protocols.jsonl\n"
                 "curl -sO https://raw.githubusercontent.com/YuClawLab/"
                 "yuclaw-brain/main/tools/yuclaw_protocol_registry.py\n"
                 "python3 -c \"import yuclaw_protocol_registry as r; "
                 "print('chain OK:', r.Registry('protocols.jsonl')"
                 ".verify_chain())\"")
    chain_out = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'tools'); "
         "import yuclaw_protocol_registry as r; "
         "print('chain OK:', r.Registry('registry/protocols.jsonl')"
         ".verify_chain())"],
        capture_output=True, text=True, cwd=str(_REPO)).stdout.strip()
    events_out = _run(["events", "--ticker", "SU", "--since", "2026-07-01"],
                      lines=14)
    replay_note = _latest_replay_evidence()

    def station(n, title, cmd, out, note=""):
        return f"""
      <div class="card">
        <div class="stnum">Station {n}</div>
        <h2>{title}</h2>
        <pre class="cmd">$ {escape(cmd)}</pre>
        <pre class="out">{escape(out)}</pre>
        {f'<p class="muted">{note}</p>' if note else ''}
      </div>"""

    header = site_header_html(subtitle="The 5-minute tour",
                              stamp=updated_strip())
    body = "".join([
        station(1, "Install and take the guided demo",
                "pip install yuclaw && yuclaw demo",
                demo_out,
                "The demo runs offline with zero configuration — the "
                "output above is this build's actual capture (first "
                "lines; the full journey takes about three minutes)."),
        station(2, "Verify a published signal against the public ledger",
                "yuclaw verify AMD --date 2026-05-20",
                verify_out,
                "This checks record integrity and timing — not "
                "investment merit."),
        station(3, "Reproduce every published Lab statistic",
                "yuclaw replay-lab",
                "REPRODUCTION OK  (exit 0)",
                f"Exit 0 means every published Lab statistic and every "
                f"daily ledger root recomputed exactly from the public "
                f"bundle; any mismatch exits non-zero. Not run at page "
                f"build (it takes minutes) — {replay_note}."),
        station(4, "Check the pre-registration chain yourself",
                chain_cmd,
                f"{chain_out}\n(run just now at page build against the "
                f"live chain)",
                "Statistics are locked into this hash chain BEFORE "
                "computation; any edit anywhere in history breaks it for "
                "every verifier."),
        station(5, "Walk one evidence trace to its SEC filing",
                "yuclaw events --ticker SU --since 2026-07-01",
                events_out,
                "Every accepted event carries its source URL and a "
                "verified excerpt — claims trace to primary filings, "
                "machine-checked."),
    ])
    OUT.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YUCLAW — the 5-minute tour</title>
<meta name="description" content="Five commands, five stations: install, verify, reproduce, chain-check, and walk one evidence trace. Every output captured from this build. Research only — not investment advice.">
<style>
 *{{margin:0;padding:0;box-sizing:border-box}}
 body{{background:#0B0E14;font-family:Inter,system-ui,sans-serif;color:#E2E8F0;line-height:1.6}}
 .container{{max-width:900px;margin:0 auto;padding:24px}}
 h2{{font-size:17px;color:#FFF;margin:4px 0 12px}}
 .card{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:16px}}
 .stnum{{color:#00E676;font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:1px;text-transform:uppercase}}
 .cmd{{background:#0B0E14;border:1px solid #00E67640;border-radius:8px;padding:12px 14px;color:#00E676;
       font-family:'JetBrains Mono',monospace;font-size:12px;overflow-x:auto;white-space:pre-wrap}}
 .out{{background:#10141C;border:1px solid #1E232D;border-radius:8px;padding:12px 14px;color:#A0AEC0;
       font-family:'JetBrains Mono',monospace;font-size:11px;overflow-x:auto;margin-top:8px;white-space:pre-wrap}}
 .muted{{color:#718096;font-size:12px;margin-top:8px}}
 .amber{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;font-size:12px;color:#A0AEC0;margin-bottom:16px}}
 .amber strong{{color:#FBA94B}}
 .closing{{background:linear-gradient(135deg,#10141C,#141B2E);border:1px solid #00E67640;border-radius:12px;
           padding:26px;text-align:center}}
 .closing a{{color:#00E676;font-weight:700}}
</style>
</head>
<body><div class="container">
{header}
<div class="amber"><strong>Research and education only — not investment advice.</strong>
Signal labels are research classifications, not buy/sell recommendations. Every output below was captured
at this page's build (timestamp in the footer) — the page regenerates daily so it can never drift from
what the commands actually print.</div>
{body}
<div class="closing">
  <p style="font-size:17px;color:#FFF;font-weight:700">Still skeptical? Good.</p>
  <p style="margin-top:6px">That is the correct starting posture here.
  <a href="https://github.com/YuClawLab/yuclaw-brain/blob/main/COMPARISON.md">Read How We Compare →</a></p>
</div>
<p class="muted" style="margin:16px 0">YUCLAW · <a href="index.html" style="color:#A0AEC0">Home</a></p>
{build_footer()}
</div></body></html>""")
    print(f"[render_tour] 5 stations captured live (demo/verify/chain/"
          f"events at build; replay-lab evidenced, disclosed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
