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
from v3.receipts.scoreboard import DEFINITIONS, inspect_public

_REPO = Path(__file__).resolve().parents[2]
OUT = _REPO / "docs" / "evidence_scoreboard.html"
SRC = _REPO / "docs" / "receipts" / "scoreboard.json"
DISCLAIMER = ("Research & education only. Not investment advice. The scoreboard counts receipts and dispositions; "
              "it computes no trust score and no financial statistic. Zero and pending are shown as such.")


def _cell(v) -> str:
    return escape(str(v))


def _lineage_cell(r: dict) -> str:
    """Lineage cell for one public receipt row (kept out of any f-string expression: Python 3.10 grammar)."""
    version = _cell(r["version"])
    if r.get("corrected"):
        head = "<span class='state pend'>CORRECTED</span> v" + version + " superseded " + escape(str(r.get("superseded_at")))
    else:
        head = "v" + version
    return head + "; first observed " + escape(r["first_observed_at"])


def render(board: dict | None, status: str = "OK") -> str:
    """board=None renders the explicit unavailable state: PENDING when no board exists yet, UNAVAILABLE when the
    file is invalid or synthetic (never a measured zero)."""
    if board is None:
        label = "PENDING" if status in ("OK", "ABSENT") else "UNAVAILABLE"
        rows = "".join(f"<tr><td data-label='column'>{escape(k)}</td><td data-label='state'><span class='state pend'>{escape(label)}</span></td><td data-label='counts'>—</td><td data-label='definition'>{escape(v)}</td></tr>" for k, v in DEFINITIONS.items())
        stamp = "no public scoreboard published yet" if label == "PENDING" else f"public scoreboard unavailable ({escape(status.lower().replace('_', ' '))}); counts are not shown as zero"
        receipts_html, chal_html, hist = "", "", ""
    else:
        cols = board["columns"]
        def row(name, col):
            detail = {k: v for k, v in col.items() if k not in ("state",) and not isinstance(v, (dict, list))}
            return (f"<tr><td data-label='column'>{escape(name)}</td><td data-label='state'><span class='state {'zero' if col.get('state') in ('ZERO',) else 'pend' if 'PENDING' in str(col.get('state')) else 'obs'}'>{_cell(col.get('state'))}</span></td>"
                    f"<td data-label='counts' class='mono'>{escape(', '.join(f'{k}={v}' for k, v in detail.items()) or '—')}</td><td data-label='definition'>{escape(DEFINITIONS[name])}</td></tr>")
        rows = "".join(row(n, cols[n]) for n in DEFINITIONS)
        rep = cols["replications"]; ere = rep["exact_release_evidence"]; cov = ere["exact_target_evidence"]; tgt = board.get("target", {})
        rows += (f"<tr><td data-label='column'>replications · program-wide exact-artifact evidence</td><td data-label='state'><span class='state obs'>OBSERVED</span></td>"
                 f"<td data-label='counts' class='mono'>successful package reproductions (any release)={_cell(ere['program_exact_artifact_evidence']['successful_package_reproductions'])}, "
                 f"successful-cohort artifacts={_cell(rep['artifacts']['successful_cohort_artifacts'])}, attempted={_cell(rep['artifacts']['attempted_artifacts'])}, verified={_cell(rep['artifacts']['verified_artifacts'])}, "
                 f"legacy program log {_cell(rep['program_evidence_legacy'].get('source', 'UNSTATED'))}: entries={_cell(rep['program_evidence_legacy']['entries'])} (PREFIX_ONLY; affiliated operators: {_cell(rep['program_evidence_legacy']['affiliated'])}; unaffiliated: {_cell(rep['program_evidence_legacy']['entries'] - rep['program_evidence_legacy']['affiliated'])}), corrected attempts={_cell(rep.get('corrected_attempts', 0))}</td>"
                 f"<td data-label='definition'>{escape(ere['program_exact_artifact_evidence']['note'])}</td></tr>")
        if cov["state"] == "BOUND":
            arts = ", ".join(f"{escape(a['artifact_type'])} {escape(a['sha256'][:12])}… ({_cell(a['size_bytes'])} B) {'covered' if a['covered'] else 'not covered'}: {_cell(a['qualified_successful_attempts'])} qualified successful" for a in cov["per_artifact"])
            rows += (f"<tr><td data-label='column'>replications · exact-target evidence</td><td data-label='state'><span class='state obs'>BOUND · {_cell(tgt.get('label'))}</span></td>"
                     f"<td data-label='counts' class='mono'>target {escape(str(tgt.get('tag')))} ({escape(str(tgt.get('version')))}) source {escape(str(tgt.get('source_sha', ''))[:12])}…; artifacts covered={_cell(cov['artifacts_covered'])}/{_cell(cov['artifacts_total'])}; "
                     f"successful package reproductions of the target={_cell(cov['successful_package_reproductions'])}; {arts}. Display prefixes never establish a binding — full hashes and lengths are in receipts/scoreboard.json</td>"
                     f"<td data-label='definition'>{escape(cov['note'])}</td></tr>")
        else:
            rows += (f"<tr><td data-label='column'>replications · exact-target evidence</td><td data-label='state'><span class='state pend'>UNBOUND</span></td>"
                     f"<td data-label='counts' class='mono'>no release target manifest bound — exact-target coverage is not measured (this is not a zero)</td><td data-label='definition'>{escape(cov['note'])}</td></tr>")
        pol = board.get("publication_policy", {})
        stamp = (f"source {escape(board['source_timestamp'])} · policy {escape(board['policy_version'])} · scoreboard {escape(board['scoreboard_version'])} · schema {escape(board.get('public_schema_version', ''))} · "
                 f"target {escape(tgt.get('state', 'UNBOUND'))}{(' ' + escape(str(tgt.get('tag')))) if tgt.get('state') == 'BOUND' else ''} · free text {'publishable' if pol.get('free_text_publishable') else 'not publishable (policy unavailable)'}")
        recs = board.get("receipts_public", [])
        receipts_html = ("<p class='muted'>No public receipts yet — this is a real zero, not a hidden count (receipted: 0 · unreceipted relationships not counted).</p>" if not recs else
                         "<table><thead><tr><th>receipt</th><th>type</th><th>artifact</th><th>outcome</th><th>review</th><th>qualified</th><th>successful</th><th>lineage</th></tr></thead><tbody>" +
                         "".join(f"<tr><td class='mono'>{escape(r['receipt_id'][:14])}… · {escape(r['attempt_id'])}</td><td>{escape(r['activity_type'])}</td><td class='mono'>{escape(r['artifact_binding']['artifact_type'])} {escape(r['artifact_binding']['sha256'][:12])}… ({_cell(r['artifact_binding']['size_bytes'])} B)</td><td>{escape(r['outcome'])}</td><td>{escape(r['review_state'])} ({escape(r['review_authority'])})</td><td>{_cell(r['qualified'])}</td><td>{_cell(r['successful'])}</td>"
                                 "<td>" + _lineage_cell(r) + "</td></tr>" for r in recs) + "</tbody></table>")
        chal = board.get("challenges_public", [])
        chal_html = ("<p class='muted'>No challenges recorded.</p>" if not chal else
                     "<table><thead><tr><th>challenge</th><th>artifact</th><th>criterion</th><th>disposition</th><th>adverse</th></tr></thead><tbody>" +
                     "".join(f"<tr><td class='mono'>{escape(c['challenge_id'])}</td><td class='mono'>{escape(c['artifact']['artifact_type'])} {escape(c['artifact']['sha256'][:12])}…</td><td>{escape(c.get('criterion', 'general'))}</td><td>{escape(c['disposition'])}</td><td>{'yes' if c['adverse'] is True else 'no'}</td></tr>" for c in chal) + "</tbody></table>")
        hist = ("<p class='muted'>History: compare two published scoreboard files with <code>yuclaw receipts --store &lt;any private dir&gt; history a.json b.json</code> — "
                "the comparison lists receipts added, supersessions (rendered CORRECTED inside their original window), disposition changes, per-window movement and absolute movement (never a multiplier from a zero baseline).</p>")
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
    .mono{{word-break:break-word}}
    @media (max-width:640px){{
      .container{{padding:12px}}
      table.defs thead{{display:none}} table.defs tr{{display:block;border-bottom:1px solid #1E232D;padding:8px 0}}
      table.defs td{{display:block;border:none;padding:2px 0}} table.defs td::before{{content:attr(data-label) ": ";color:#718096;font-size:11px;font-family:JetBrains Mono,monospace}}
    }}
  </style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="Evidence Scoreboard", active="evidence_scoreboard.html")}
    <h1 style="font-size:22px;font-weight:800;color:#FFF;margin-bottom:6px">Evidence Scoreboard</h1>
    <p class="muted" style="margin-bottom:14px;font-family:JetBrains Mono,monospace">{escape(stamp)}</p>
    <div class="disclaimer"><strong>Disclaimer —</strong> {escape(DISCLAIMER)}</div>
    <div class="panel"><div class="panel-title">What is counted (each column shows its own definition; zero and pending are real states)</div>
      <div class="wrap"><table class="defs"><thead><tr><th>column</th><th>state</th><th>counts</th><th>counting definition</th></tr></thead><tbody>{rows}</tbody></table></div>
      <p class="muted" style="margin-top:8px">Primary replication population = qualified attempts, including qualified failed and inconclusive outcomes; the successful cohort is reported separately. Program evidence (any release, legacy prefix-bound) is separate from exact-release evidence (verified wheel/sdist bytes). A site or endpoint check is never a package reproduction.</p>
    </div>
    <div class="panel"><div class="panel-title">Public receipts</div><div class="wrap">{receipts_html}</div></div>
    <div class="panel"><div class="panel-title">Challenges (adverse and unresolved findings are never hidden)</div><div class="wrap">{chal_html}</div>{hist}</div>
    <div class="panel"><div class="panel-title">How to add evidence</div>
      <p class="muted">Check → reproduce → challenge → document use: <code>yuclaw packet build</code> · <code>yuclaw packet verify</code> · <code>yuclaw challenge</code> · <code>yuclaw decision</code>. Why a receipt counted or not: <code>yuclaw receipts --store &lt;private&gt; explain &lt;receipt id&gt;</code>. Receipts are reviewed under a designated reviewer before they count; owner-operated checks and synthetic fixtures contribute zero outsiders; a site or endpoint check is never a package reproduction; program totals are distinct from a release's exact-target totals.</p>
    </div>
    <p style="font-size:12px;color:#718096">Research and education only. Not investment advice.</p>
{footer_stamp_html(freshness_strip(board['source_timestamp'][:10] if board else None))}
{build_footer()}
  </div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    info = inspect_public(SRC)
    board = info["board"]
    OUT.write_text(render(board, info["status"]))
    print(f"[render_scoreboard] wrote {OUT} ({info['status'] + ': ' + info['reason'] if board is None else board['source_timestamp']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
