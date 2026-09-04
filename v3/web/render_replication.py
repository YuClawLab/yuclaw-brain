"""
Render the Independent Replication page (docs/replication.html) — Part C of
the usefulness build (2026-07-16).

Content: how to reproduce (exact commands), what counts as success, how to
report (GitHub issue template), and the public replication log — read from
docs/replication/replication_log.json and labeled honestly when empty.

CLI: python3 -m v3.web.render_replication
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from v3.web.useful_blocks import footer_stamp_html, build_footer, freshness_strip, VERSION, site_header_html, status_block_html

_REPO = Path(__file__).resolve().parents[2]
OUT = _REPO / "docs" / "replication.html"
LOG = _REPO / "docs" / "replication" / "replication_log.json"

DISCLAIMER_LINE = ("Research & education only. Not investment advice. Replication verifies "
                   "reproducibility of published statistics — it is not an endorsement of any signal.")

ISSUE_URL = ("https://github.com/YuClawLab/yuclaw-brain/issues/new"
             "?template=replication.md&labels=replication")


def _log_entries() -> list[dict]:
    if not LOG.exists():
        return []
    try:
        return json.loads(LOG.read_text()).get("replications", [])
    except Exception:
        return []


_TH = ("padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;"
       "color:#718096;border-bottom:1px solid #2D3748")
_TD = "padding:8px 12px;vertical-align:top"
_PASS = ("PASS", "REPRODUCED")


def _result(e: dict) -> str:
    return str(e.get("replication_result") or e.get("result") or "")


def _passed(e: dict) -> bool:
    return _result(e).upper().startswith(_PASS)


def _disclosure(entries: list[dict]) -> str:
    """Affiliation disclosure, derived from the entries — never typed.
    Counts external-machine reproductions and unaffiliated entries; the
    log never claims more independence than the entries record."""
    ext = [e for e in entries if e.get("replication_machine_external") is True and _passed(e)]
    unaff = sum(1 for e in entries
                if str(e.get("operator_affiliation", "")).upper() == "UNAFFILIATED")
    if not entries:
        return "No replications recorded; unaffiliated replications: 0"
    if ext and unaff == 0:
        who = "an affiliated operator" if len(ext) == 1 else f"{len(ext)} affiliated operators"
        return (f"External-machine reproduction completed by {who}; "
                f"unaffiliated replications: 0")
    return (f"External-machine reproductions: {len(ext)}; "
            f"unaffiliated replications: {unaff}; entries: {len(entries)}")


def _row_html(e: dict) -> str:
    """One table row; accepts both the canonical field set (date,
    replication_machine_external, operator, operator_affiliation, source,
    package, bundle, path, replication_result, detail) and the older
    issue-template fields (os, python, command, output_hash, result,
    issue_url)."""
    def c(v): return escape(str(v)) if v not in (None, "") else "—"
    operator = e.get("operator") or ("issue report" if e.get("issue_url") else "")
    who = c(operator)
    if e.get("operator_affiliation"):
        who += f" · {c(e['operator_affiliation'])}"
    if e.get("replication_machine_external") is True:
        machine = "external"
    else:
        machine = " · ".join(x for x in (e.get("os"), e.get("python")) if x) or "—"
        machine = escape(machine)
    source = " · ".join(x for x in (e.get("source"), e.get("package"), e.get("command")) if x)
    bundle = e.get("bundle") or e.get("bundle_build_metadata") or ""
    path = e.get("path") or ""
    result = _result(e)
    detail = e.get("detail") or e.get("notes") or ""
    if e.get("output_hash"):
        detail = (detail + " · " if detail else "") + f"output sha256 {str(e['output_hash'])[:16]}…"
    if e.get("issue_url"):
        detail = (detail + " · " if detail else "") + f"<a href='{escape(str(e['issue_url']))}'>issue</a>"
        detail_html = detail
    else:
        detail_html = c(detail)
    color = "#00E676" if _passed(e) else "#FF3366"
    return (f"<tr><td style='{_TD}'>{c(e.get('date'))}</td>"
            f"<td style='{_TD}'>{who}</td>"
            f"<td style='{_TD}'>{machine}</td>"
            f"<td style='{_TD}'>{c(source)}</td>"
            f"<td style='{_TD}'><code>{c(bundle)}</code></td>"
            f"<td style='{_TD}'>{c(path)}</td>"
            f"<td style='{_TD};font-weight:700;color:{color}'>{c(result)}</td>"
            f"<td style='{_TD}'>{detail_html}</td></tr>")


def _commit() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO, capture_output=True, text=True)
    return r.stdout.strip()[:12] if r.returncode == 0 else "unknown"


def render() -> str:
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entries = _log_entries()

    disclosure = _disclosure(entries)
    if entries:
        rows = "".join(_row_html(e) for e in entries)
        log_html = f"""
      <div style="background:#10141C;border:1px solid #2D3748;border-radius:8px;padding:12px 16px;margin-bottom:12px;
                  font-size:12.5px;color:#E2E8F0;line-height:1.6"><strong>{escape(disclosure)}</strong></div>
      <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse">
        <thead><tr>
          <th style="{_TH}">Date</th>
          <th style="{_TH}">Operator · affiliation</th>
          <th style="{_TH}">Machine</th>
          <th style="{_TH}">Source · package</th>
          <th style="{_TH}">Bundle</th>
          <th style="{_TH}">Path</th>
          <th style="{_TH}">Result</th>
          <th style="{_TH}">Detail</th>
        </tr></thead><tbody style="font-size:12px;color:#A0AEC0">{rows}</tbody>
      </table></div>"""
    else:
        log_html = """
      <div style="background:#10141C;border:1px dashed #2D3748;border-radius:8px;padding:16px 18px;
                  font-size:12.5px;color:#A0AEC0;line-height:1.6">
        <strong style="color:#E2E8F0">No external replications recorded yet; this log accrues as they
        arrive.</strong> Entries are added verbatim from filed replication issues — pass and fail alike —
        and are never edited retroactively.
      </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YUCLAW — Independent Replication</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{background:#0B0E14;color:#E2E8F0;font-family:Inter,-apple-system,'Segoe UI',Roboto,sans-serif;font-size:14px}}
  .container{{max-width:900px;margin:0 auto;padding:28px 20px}}
  a{{color:#00E676;text-decoration:none}} a:hover{{text-decoration:underline}}
  code{{background:#1E232D;padding:2px 6px;border-radius:4px;color:#00E676;font-family:'JetBrains Mono',monospace;font-size:11.5px}}
  pre{{background:#0B0E14;border:1px solid #1E232D;border-radius:8px;padding:14px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#E2E8F0;overflow-x:auto;line-height:1.6}}
  .header{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:18px}}
  .logo{{font-size:19px;font-weight:800;color:#FFF;letter-spacing:1px}}
  .navlinks a{{margin-left:14px;font-size:12px;color:#A0AEC0}}
  .panel{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px}}
  .panel-title{{font-size:13px;font-weight:700;color:#FFF;margin-bottom:8px}}
  .disclaimer-line{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;margin-bottom:20px;font-size:12px;line-height:1.55;color:#A0AEC0}}
  .footer{{text-align:center;padding:18px;color:#718096;font-size:11px;margin-top:8px}}
</style>
</head>
<body>
  <div class="container">
    {site_header_html(subtitle="Independent Replication", active="replication.html")}

    <h1 style="font-size:22px;font-weight:800;color:#FFF;margin-bottom:6px">Replicate the record yourself</h1>
    <p style="font-size:13px;color:#A0AEC0;margin-bottom:16px;line-height:1.6;max-width:760px">
      Every statistic on the Validation Lab re-derives from published, derived data — on your machine,
      with no account, no API key, and (for the standalone path) no installed dependencies. This page
      is the exact procedure, the exact pass criteria, and the public log of reported replications.
    </p>

    <div class="disclaimer-line"><strong>Disclaimer —</strong> {escape(DISCLAIMER_LINE)}</div>

    <div class="panel">
      <div class="panel-title">1 · How to reproduce — two equivalent paths</div>
      <p style="font-size:12px;color:#A0AEC0;margin-bottom:8px">Path A — packaged (pip):</p>
      <pre>pip install yuclaw
yuclaw replay-lab            # fetches the published bundle and verifies it</pre>
      <p style="font-size:12px;color:#A0AEC0;margin:12px 0 8px">Path B — standalone (Python ≥ 3.10 standard library only, no installs):</p>
      <pre>curl -sO https://yuclawlab.github.io/yuclaw-brain/replay/lab_replay_bundle.json
curl -sO https://raw.githubusercontent.com/YuClawLab/yuclaw-brain/main/tools/replay_lab.py
python3 replay_lab.py lab_replay_bundle.json</pre>
      <p style="font-size:11.5px;color:#718096;margin-top:10px">
        Both paths rebuild the decile cohorts from bundled scores, recompute every statistic
        (bootstrap CI with the published seed, Fama-MacBeth IC with Newey-West correction,
        market-model alpha), and recompute every sha-256 leaf and daily root against the public
        <a href="https://github.com/YuClawLab/yuclaw-trust">yuclaw-trust</a> ledger.
        <span style="display:block;margin-top:6px;font-size:12px;color:#718096">
        Verifier vocabulary: a day counts as <strong style="color:#A0AEC0">exact</strong> when the
        recomputed daily root matches the anchored root byte-for-byte; it counts as an
        <strong style="color:#A0AEC0">anchored-subset</strong> day when the anchored block committed a
        SUBSET of that day's entry hashes (an intraday re-run anchored before the day completed) and
        every anchored hash recomputes unchanged from today's data — fewer hashes anchored, none
        mutated. The replay output names both counts separately; a subset day is a disclosed anchoring
        artifact, not a verification failure.</span>
      </p>
    </div>

    <div class="panel">
      <div class="panel-title">2 · What counts as a successful replication</div>
      <ul style="font-size:12.5px;color:#A0AEC0;line-height:1.8;margin-left:18px">
        <li><strong style="color:#E2E8F0">Exit code 0.</strong> Any statistic or hash mismatch exits non-zero with a diff report.</li>
        <li><strong style="color:#E2E8F0">Statistics match</strong> the bundle's published <code>expected</code> block exactly (same seed, same estimators).</li>
        <li><strong style="color:#E2E8F0">Ledger roots match</strong> — every recomputed daily root equals the root committed to the public yuclaw-trust repository.</li>
        <li><strong style="color:#E2E8F0">Build metadata matches</strong> — the bundle's data-through date, build date, and source commit agree with the page and packet you downloaded them from.</li>
      </ul>
    </div>

    <div class="panel">
      <div class="panel-title">3 · How to report — pass or fail, both are wanted</div>
      <p style="font-size:12.5px;color:#A0AEC0;line-height:1.7">
        File a <a href="{ISSUE_URL}">Replication report issue</a> using the template
        (<code>.github/ISSUE_TEMPLATE/replication.md</code>). Required fields: OS · Python version ·
        exact command · bundle build metadata · sha-256 of the output · result (PASS / FAIL with the
        mismatch report verbatim). Reports are added to the public log below, unedited.
      </p>
    </div>

    <div class="panel">
      <div class="panel-title">4 · Public replication log</div>
      <p style="font-size:12px;color:#A0AEC0;line-height:1.7;margin-bottom:10px">
        Entries are recorded verbatim — from filed replication issues, or from the project's own
        documented external-machine runs — and every entry names its operator and affiliation.
        Pass and fail alike; never edited retroactively. The disclosure line above the table is
        derived from the entries: this log never states more independence than the entries record.
      </p>
      {log_html}
    </div>

    {status_block_html()}

    <div class="footer">
      YUCLAW Independent Replication · source commit <code>{escape(_commit())}</code> ·
      <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> · research &amp; education only
    </div>
  </div>
<div class="card" style="background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:20px;margin:16px 0"><div style="font-size:14px;font-weight:700;color:#FFF;margin-bottom:8px">For researchers</div><p style="font-size:13px;color:#A0AEC0">The evidence layer is citable as a dataset: weekly snapshot tags (dataset-YYYY-MM-DD) freeze the EvidenceBench items, the 79 Ground Truth anatomy documents, and the per-day evidence-ledger roots at a commit; CITATION.cff at the repository root carries the citation record, and every EvidenceBench release prints its item-set hash so a cited item set is byte-reproducible. Derived events and verified excerpts only — no raw vendor market data.</p></div>
{footer_stamp_html(freshness_strip())}
{build_footer()}
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    html = render()
    OUT.write_text(html)
    print(f"[render_replication] wrote {OUT} ({len(html)} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
