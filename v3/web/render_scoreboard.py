"""
Render the Evidence Scoreboard page (docs/evidence_scoreboard.html) — v7.

Receipt counts read ONLY the derived, non-synthetic scoreboard file docs/receipts/scoreboard.json (produced by
`yuclaw receipts --store <private store> scoreboard --out docs/receipts/scoreboard.json` in the daily
chain). Production never consumes demonstration fixtures: a synthetic board is refused by
load_public and the page then shows the explicit PENDING state. Zero and pending are real states.
The research view separately reads public coverage/history artifacts and dated issuer-source notes.
No composite trust score is computed; issuer financial figures never change receipt counts.

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


def _receipt_register(board: dict | None, status: str = "OK") -> str:
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
    return f"""
    <p class="muted">{stamp}</p>
    <p class="muted">{escape(DISCLAIMER)}</p>
    <div class="panel"><div class="panel-title">What is counted</div>
      <div class="wrap" tabindex="0" role="region" aria-label="Receipt counting definitions"><table class="defs"><thead><tr><th scope="col">Column</th><th scope="col">State</th><th scope="col">Counts</th><th scope="col">Counting definition</th></tr></thead><tbody>{rows}</tbody></table></div>
      <p class="muted">Primary replication population = qualified attempts, including qualified failed and inconclusive outcomes; the successful cohort is reported separately. Program evidence (any release, legacy prefix-bound) is separate from exact-release evidence (verified wheel/sdist bytes). A site or endpoint check is never a package reproduction.</p>
    </div>
    <div class="panel"><div class="panel-title">Public receipts</div><div class="wrap">{receipts_html}</div></div>
    <div class="panel"><div class="panel-title">Challenges (adverse and unresolved findings are never hidden)</div><div class="wrap">{chal_html}</div>{hist}</div>
    <div class="panel"><div class="panel-title">How to add evidence</div><p class="muted">Check → reproduce → challenge → document use: <code>yuclaw packet build</code> · <code>yuclaw packet verify</code> · <code>yuclaw challenge</code> · <code>yuclaw decision</code>. Explain a count with <code>yuclaw receipts --store &lt;private&gt; explain &lt;receipt id&gt;</code>. Receipts require review before they count. Owner-operated checks and synthetic fixtures contribute zero outsiders.</p></div>
    """


def render(board: dict | None, status: str = "OK", *, research=None, notes=None) -> str:
    from v3.web.scoreboard_page import present
    return present(board, status, _receipt_register(board, status), research, notes)


def main(argv: list[str] | None = None) -> int:
    info = inspect_public(SRC)
    board = info["board"]
    from v3.web.scoreboard_research import load_research
    from v3.web.scoreboard_page import load_notes
    research = load_research(_REPO / "docs")
    notes = load_notes(_REPO / "docs")
    (_REPO / "docs/evidence/scoreboard_research.json").write_text(json.dumps({"research": research, "notes": notes}, indent=2) + "\n")
    OUT.write_text(render(board, info["status"], research=research, notes=notes))
    print(f"[render_scoreboard] wrote {OUT} ({info['status'] + ': ' + info['reason'] if board is None else board['source_timestamp']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
