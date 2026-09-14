"""
Render the Evidence Scoreboard page (docs/evidence_scoreboard.html) — v7.

Reads ONLY the derived, non-synthetic scoreboard file docs/receipts/scoreboard.json (produced by
`yuclaw receipts --store <private store> scoreboard --out docs/receipts/scoreboard.json` in the daily
chain). Production never consumes demonstration fixtures: a synthetic board is refused by
load_public and the page then shows the explicit PENDING state. Zero and pending are real states.
No composite score, no financial statistic.

CLI: python3 -m v3.web.render_scoreboard
"""
from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

from v3.web.useful_blocks import footer_stamp_html, build_footer, freshness_strip, site_header_html
from v3.receipts.scoreboard import DEFINITIONS, load_public

_REPO = Path(__file__).resolve().parents[2]
OUT = _REPO / "docs" / "evidence_scoreboard.html"
SRC = _REPO / "docs" / "receipts" / "scoreboard.json"
DISCLAIMER = ("Research & education only. Not investment advice. The scoreboard counts receipts and dispositions; "
              "it computes no trust score and no financial statistic. Zero and pending are shown as such.")


def _cell(v) -> str:
    return escape(str(v))


def render(board: dict | None) -> str:
    if board is None:
        rows = "".join(f"<tr><td>{escape(k)}</td><td><span class='state pend'>PENDING</span></td><td>—</td><td>{escape(v)}</td></tr>" for k, v in DEFINITIONS.items())
        stamp, receipts_html, chal_html, hist = "no public scoreboard published yet", "", "", ""
    else:
        cols = board["columns"]
        def row(name, col):
            detail = {k: v for k, v in col.items() if k not in ("state",) and not isinstance(v, (dict, list))}
            return (f"<tr><td>{escape(name)}</td><td><span class='state {'zero' if col.get('state') in ('ZERO',) else 'pend' if 'PENDING' in str(col.get('state')) else 'obs'}'>{_cell(col.get('state'))}</span></td>"
                    f"<td class='mono'>{escape(', '.join(f'{k}={v}' for k, v in detail.items()) or '—')}</td><td>{escape(DEFINITIONS[name])}</td></tr>")
        rows = "".join(row(n, cols[n]) for n in DEFINITIONS)
        rep = cols["replications"]
        rows += (f"<tr><td>replications · artifact coverage</td><td><span class='state obs'>{_cell(rep['registration']['status'])}</span></td>"
                 f"<td class='mono'>successful-cohort artifacts={rep['artifacts']['successful_cohort_artifacts']}, attempted={rep['artifacts']['attempted_artifacts']}, "
                 f"verified={rep['artifacts']['verified_artifacts']}, exact-release package reproductions={rep['exact_release_evidence']['successful_package_reproductions']}, "
                 f"legacy program entries={rep['program_evidence_legacy']['entries']} (PREFIX_ONLY)</td>"
                 f"<td>{escape(rep['artifacts']['note'])}</td></tr>")
        stamp = f"source {escape(board['source_timestamp'])} · policy {escape(board['policy_version'])} · scoreboard {escape(board['scoreboard_version'])}"
        recs = board.get("receipts_public", [])
        receipts_html = ("<p class='muted'>No public receipts yet — this is a real zero, not a hidden count.</p>" if not recs else
                         "<table><thead><tr><th>attempt</th><th>artifact</th><th>outcome</th><th>review</th><th>qualified</th><th>successful</th></tr></thead><tbody>" +
                         "".join(f"<tr><td class='mono'>{escape(r['attempt_id'])}</td><td class='mono'>{escape(r['artifact_binding']['artifact_type'])} {escape(r['artifact_binding']['sha256'][:12])}…</td><td>{escape(r['outcome'])}</td><td>{escape(r['review_state'])} ({escape(r['review_authority'])})</td><td>{r['qualified']}</td><td>{r['successful']}</td></tr>" for r in recs) + "</tbody></table>")
        chal = board.get("challenges_public", [])
        chal_html = ("<p class='muted'>No challenges recorded.</p>" if not chal else
                     "<table><thead><tr><th>challenge</th><th>artifact</th><th>disposition</th><th>adverse</th></tr></thead><tbody>" +
                     "".join(f"<tr><td class='mono'>{escape(c['challenge_id'])}</td><td class='mono'>{escape(c['artifact']['artifact_type'])} {escape(c['artifact']['sha256'][:12])}…</td><td>{escape(c['disposition'])}</td><td>{'yes' if c['adverse'] else 'no'}</td></tr>" for c in chal) + "</tbody></table>")
        hist = ("<p class='muted'>History: compare two published scoreboard files with <code>python3 -c \"from v3.receipts.scoreboard import history\"</code> — "
                "the diff lists receipts added/superseded, challenges added and dispositions changed, with absolute movement (never a multiplier from a zero baseline).</p>")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>YUCLAW · Evidence Scoreboard</title>
  <meta name="description" content="Derived evidence scoreboard: witnesses, pilots, replications, audits, refusals, packet uses and challenges — with counting definitions and real zero/pending states. Research only — not investment advice.">
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0B0E14;font-family:Inter,sans-serif;color:#E2E8F0;line-height:1.6}}
    .container{{max-width:960px;margin:0 auto;padding:24px}}
    .panel{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px}}
    .panel-title{{font-size:13px;font-weight:700;color:#FFF;margin-bottom:10px}}
    .disclaimer{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:12px 16px;margin-bottom:20px;font-size:12px;color:#A0AEC0}}
    .disclaimer strong{{color:#FBA94B}}
    table{{width:100%;border-collapse:collapse;font-size:13px}} th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #1E232D;vertical-align:top}} th{{color:#A0AEC0;font-weight:600}}
    .mono{{font-family:JetBrains Mono,monospace;font-size:12px;color:#A0AEC0}} .muted{{color:#718096;font-size:13px}}
    .state{{display:inline-block;padding:2px 8px;border-radius:5px;font-size:11px;font-weight:700;font-family:JetBrains Mono,monospace}}
    .zero{{background:#1E232D;color:#A0AEC0}} .pend{{background:#FBA94B20;color:#FBA94B}} .obs{{background:#00E67620;color:#00E676}}
    .wrap{{overflow-x:auto}} a{{color:#00E676}} code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:JetBrains Mono,monospace;font-size:12px}}
    @media (max-width:640px){{.container{{padding:12px}} td,th{{padding:6px}}}}
  </style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="Evidence Scoreboard", active="evidence_scoreboard.html")}
    <h1 style="font-size:22px;font-weight:800;color:#FFF;margin-bottom:6px">Evidence Scoreboard</h1>
    <p class="muted" style="margin-bottom:14px;font-family:JetBrains Mono,monospace">{escape(stamp)}</p>
    <div class="disclaimer"><strong>Disclaimer —</strong> {escape(DISCLAIMER)}</div>
    <div class="panel"><div class="panel-title">What is counted (each column shows its own definition; zero and pending are real states)</div>
      <div class="wrap"><table><thead><tr><th>column</th><th>state</th><th>counts</th><th>counting definition</th></tr></thead><tbody>{rows}</tbody></table></div>
      <p class="muted" style="margin-top:8px">Primary replication population = qualified attempts, including qualified failed and inconclusive outcomes; the successful cohort is reported separately. Program evidence (any release, legacy prefix-bound) is separate from exact-release evidence (verified wheel/sdist bytes). A site or endpoint check is never a package reproduction.</p>
    </div>
    <div class="panel"><div class="panel-title">Public receipts</div><div class="wrap">{receipts_html}</div></div>
    <div class="panel"><div class="panel-title">Challenges (adverse and unresolved findings are never hidden)</div><div class="wrap">{chal_html}</div>{hist}</div>
    <div class="panel"><div class="panel-title">How to add evidence</div>
      <p class="muted">Check → reproduce → challenge → document use: <code>yuclaw packet build</code> · <code>yuclaw packet verify</code> · <code>yuclaw challenge</code> · <code>yuclaw decision</code>. Receipts are reviewed under a designated reviewer before they count; owner-operated checks and synthetic fixtures contribute zero outsiders.</p>
    </div>
    <p style="font-size:12px;color:#718096">Research and education only. Not investment advice.</p>
{footer_stamp_html(freshness_strip())}
{build_footer()}
  </div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    board = load_public(SRC)
    OUT.write_text(render(board))
    print(f"[render_scoreboard] wrote {OUT} ({'PENDING (no public board)' if board is None else board['source_timestamp']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
