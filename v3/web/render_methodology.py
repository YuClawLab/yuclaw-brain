"""
Methodology page (docs/methodology.html) — generated FROM
docs/methodology/backfill.md in the daily chain, never hand-edited. The
.md stays the canonical source (the U1 threshold-match gate keeps reading
it, and it remains served raw for machines); this page is its styled
render with anchors preserved (attr_list handles {#thresholds}-style
heading ids).
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import markdown

from v3.web.useful_blocks import (footer_stamp_html, build_footer, site_header_html,
                                  updated_strip)

SRC = _REPO / "docs" / "methodology" / "backfill.md"
OUT = _REPO / "docs" / "methodology.html"


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    # Canonical copy block (ORDER 2026-09-05B PART A / G1): the marker-
    # delimited look-ahead statement passes through VERBATIM — markdown
    # never rewraps or escapes it — so the rendered page carries the same
    # bytes as backfill.md and the canonical file, and the copy-
    # consistency gate can extract it between the same markers.
    import re as _re
    src = SRC.read_text()
    BEGIN, END = "<!-- LOOKAHEAD-CANONICAL BEGIN -->", "<!-- LOOKAHEAD-CANONICAL END -->"
    m = _re.search(_re.escape(BEGIN) + r"\n(.*?)\n" + _re.escape(END), src, _re.S)
    if not m:
        raise SystemExit("render_methodology: LOOKAHEAD canonical markers missing in backfill.md")
    token = "@@LOOKAHEAD-CANONICAL-BLOCK@@"
    src = src[:m.start()] + token + src[m.end():]
    body = markdown.markdown(
        src,
        extensions=["tables", "attr_list", "fenced_code", "toc"])
    wrapped = f'<p class="canonical">{BEGIN}\n{m.group(1)}\n{END}</p>'
    if body.count(f"<p>{token}</p>") != 1:
        raise SystemExit("render_methodology: canonical placeholder did not render as one paragraph")
    body = body.replace(f"<p>{token}</p>", wrapped)
    header = site_header_html(subtitle="Methodology",
                              active="methodology.html")
    OUT.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>YUCLAW Methodology — backfill, policies, thresholds</title>
<meta name="description" content="The canonical methodology: backfill construction, price and corporate-action policies, the locked score-to-label thresholds, estimator ladder, limitations. Research only — not investment advice.">
<style>
 *{{margin:0;padding:0;box-sizing:border-box}}
 body{{background:#0B0E14;font-family:Inter,system-ui,sans-serif;color:#CBD5E1;line-height:1.7}}
 .container{{max-width:900px;margin:0 auto;padding:24px}}
 .md h1{{font-size:24px;color:#FFF;margin:26px 0 12px}}
 .md h2{{font-size:18px;color:#FFF;margin:24px 0 10px;border-bottom:1px solid #1E232D;padding-bottom:6px}}
 .md h3{{font-size:15px;color:#E2E8F0;margin:18px 0 8px}}
 .md p{{margin:10px 0;font-size:14px}}
 .md ul,.md ol{{margin:10px 0 10px 22px;font-size:14px}}
 .md li{{margin:5px 0}}
 .md table{{border-collapse:collapse;margin:12px 0;width:100%}}
 .md th,.md td{{border:1px solid #1E232D;padding:8px 12px;font-size:13px;text-align:left}}
 .md th{{background:#151A23;color:#718096;font-size:11px;text-transform:uppercase}}
 .md code{{background:#151A23;padding:2px 6px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#00E676}}
 .md pre{{background:#10141C;border:1px solid #1E232D;border-radius:8px;padding:12px;overflow-x:auto;margin:12px 0}}
 .md pre code{{background:none;padding:0}}
 .md a{{color:#00E676}}
 .md blockquote{{border-left:3px solid #1E232D;padding-left:14px;color:#718096}}
 .amber{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;font-size:12px;color:#A0AEC0;margin:14px 0}}
 .amber strong{{color:#FBA94B}}
 .muted{{color:#718096;font-size:12px}}
</style>
</head>
<body><div class="container">
{header}
<div class="amber"><strong>Research and education only — not investment advice.</strong>
Signal labels are research classifications, not buy/sell recommendations.
This page is generated from the canonical source
<a href="methodology/backfill.md" style="color:#FBA94B">methodology/backfill.md</a> (served raw for machines);
the source is what the threshold-match gate reads.</div>
<div class="md">{body}</div>
<div class="amber"><strong>Research and education only — not investment advice.</strong>
Past results — in-sample or forward-tracked — do not predict future performance.</div>
<p class="muted">YUCLAW · <a href="index.html" style="color:#A0AEC0">Home</a> ·
canonical source: <a href="methodology/backfill.md" style="color:#A0AEC0">methodology/backfill.md</a></p>
{footer_stamp_html(updated_strip())}
{build_footer()}
</div></body></html>""")
    print(f"[render_methodology] {OUT.stat().st_size} bytes from "
          f"{SRC.relative_to(_REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
