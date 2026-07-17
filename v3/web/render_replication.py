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

from v3.web.useful_blocks import VERSION, site_header_html, status_block_html

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


def _commit() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO, capture_output=True, text=True)
    return r.stdout.strip()[:12] if r.returncode == 0 else "unknown"


def render() -> str:
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entries = _log_entries()

    if entries:
        rows = "".join(
            f"<tr><td style='padding:8px 12px'>{escape(str(e.get('date','')))}</td>"
            f"<td style='padding:8px 12px'>{escape(str(e.get('os','')))}</td>"
            f"<td style='padding:8px 12px'>{escape(str(e.get('python','')))}</td>"
            f"<td style='padding:8px 12px'><code>{escape(str(e.get('command','')))}</code></td>"
            f"<td style='padding:8px 12px'><code>{escape(str(e.get('output_hash',''))[:16])}…</code></td>"
            f"<td style='padding:8px 12px;font-weight:700;color:"
            f"{'#00E676' if str(e.get('result','')).upper().startswith('PASS') else '#FF3366'}'>"
            f"{escape(str(e.get('result','')))}</td>"
            f"<td style='padding:8px 12px'><a href='{escape(str(e.get('issue_url','#')))}'>issue</a></td></tr>"
            for e in entries)
        log_html = f"""
      <div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse">
        <thead><tr>
          <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#718096;border-bottom:1px solid #2D3748">Date</th>
          <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#718096;border-bottom:1px solid #2D3748">OS</th>
          <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#718096;border-bottom:1px solid #2D3748">Python</th>
          <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#718096;border-bottom:1px solid #2D3748">Command</th>
          <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#718096;border-bottom:1px solid #2D3748">Output hash</th>
          <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#718096;border-bottom:1px solid #2D3748">Result</th>
          <th style="padding:8px 12px;text-align:left;font-size:10px;text-transform:uppercase;color:#718096;border-bottom:1px solid #2D3748">Source</th>
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
    {site_header_html(subtitle="Independent Replication")}

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
      {log_html}
    </div>

    {status_block_html()}

    <div class="footer">
      YUCLAW Independent Replication · built {escape(built)} · source commit <code>{escape(_commit())}</code> ·
      <a href="https://github.com/YuClawLab/yuclaw-brain">YuClawLab</a> · research &amp; education only
    </div>
  </div>
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
