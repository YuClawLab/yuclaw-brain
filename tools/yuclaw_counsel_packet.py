#!/usr/bin/env python3
"""
Counsel briefing packet assembler (order of 2026-07-27) — box-local,
gitignored. One zip so the consult starts with everything in hand.

Contents (internal/counsel_packet/):
  COVER_NOTE.pdf              auto-generated from live state (2 pages):
                              what YUCLAW is, locked public vocabulary,
                              frozen implication line, EXPLORATORY (CLIENT)
                              ceiling, enumerated [COUNSEL] questions
  founding_pilot_onepager.pdf generated DRAFT (no prior artifact existed in
                              the repo — flagged in the build output)
  evidence_memo_su.md         the real SU demo memo (copied verbatim)
  lane.pdf                    printed lane page (includes the shared status
                              block) via WeasyPrint
  gdx_synthesis_preview.pdf   one synthesis preview, printed
  pilot_engagement_terms_DRAFT.md / client_data_handling_DRAFT.md
  client_deliverable_sample.zip (the synthetic dry-run deliverable)
  counsel_packet.zip          all of the above
"""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from weasyprint import HTML

from v3.web.useful_blocks import PUBLIC_LABELS, VERSION
from yuclaw_research_brief import IMPLICATION_FROZEN

PKT = _REPO / "internal" / "counsel_packet"
DRAFTS = _REPO / "internal" / "legal_drafts"

CSS = """
@page { size: A4; margin: 22mm 18mm; @bottom-center {
  content: "DRAFT — pending counsel review; never send unreviewed · page " counter(page);
  font-size: 8pt; color: #a33; } }
body { font-family: 'DejaVu Sans', sans-serif; font-size: 10pt; color: #111; line-height: 1.55; }
.band { background: #0B0E14; color: #fff; padding: 14px 18px; border-left: 6px solid #00C853; margin-bottom: 12px; }
.band .t { font-size: 15pt; font-weight: 800; }
.band .s { font-size: 9pt; color: #9adbb4; font-family: monospace; }
.warn { background: #FFF3E0; border: 2px solid #E65100; color: #7f2d00; padding: 8px 12px; font-weight: 700; margin: 10px 0; }
h2 { font-size: 12pt; border-bottom: 1px solid #ccc; padding-bottom: 3px; margin: 16px 0 6px; }
li { margin-bottom: 4px; }
.mono { font-family: monospace; font-size: 9pt; }
"""


def _pdf(html_body: str, out: Path):
    HTML(string=f"<style>{CSS}</style>{html_body}").write_pdf(str(out))


def counsel_questions() -> list[str]:
    qs = []
    for f in sorted(DRAFTS.glob("*_DRAFT.md")):
        for m in re.finditer(r"\[COUNSEL:([^\]]+)\]", f.read_text()):
            qs.append(f"{f.stem.replace('_DRAFT', '')}: {m.group(1).strip()}")
    return qs


def cover_note(out: Path):
    qs = counsel_questions()
    q_html = "".join(f"<li>{q}</li>" for q in qs)
    labels = " · ".join(sorted(PUBLIC_LABELS))
    body = f"""
<div class="band"><div class="t">YUCLAW {VERSION} — Counsel Briefing Packet</div>
<div class="s">prepared {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} · box-local · not for distribution</div></div>
<div class="warn">DRAFT — pending counsel review; never send unreviewed. This packet
prepares the consult; nothing in it has been reviewed or approved.</div>

<h2>1 · What YUCLAW is</h2>
<p>An open-source, evidence-first equity research platform run as a research and
education project. Every published signal is a research classification tied to
verifiable SEC filings, replayable point-in-time, and hash-anchored in a public
ledger. It publishes no recommendations, manages no assets, and charges nothing
for the public record. Public output lives at yuclawlab.github.io/yuclaw-brain;
every page carries research-only disclaimers.</p>

<h2>2 · The locked public vocabulary</h2>
<p class="mono">{labels}</p>
<p>These eight labels are the only signal classifications any public page may
render; the machine enforces the set. There is no SELL or SHORT label.</p>

<h2>3 · The frozen implication line (verbatim, rendered on research canvases)</h2>
<p class="mono">{IMPLICATION_FROZEN}</p>

<h2>4 · The proposed commercial pilot (what counsel is being asked about)</h2>
<p>A single fixed-fee (CAD 5,000, prepaid) research pilot: a client submits a
ticker basket and/or a dated signal file; YUCLAW returns a research memo with
registered statistics, a plain-language methodology note, and a reproduction
bundle. Client work runs in a code-isolated namespace, never enters the public
record or the public repository, and is classified at most
<b>EXPLORATORY (CLIENT)</b> under a registered standard — higher standings are
reserved for the canonical public record and are not purchasable. The delivery
channel is deliberately undecided pending this consult.</p>

<h2>5 · Specific questions for counsel ({len(qs)} extracted from the drafts)</h2>
<ol>{q_html}</ol>

<h2>6 · What is in this packet</h2>
<ol>
<li>This cover note.</li>
<li>Founding-pilot one-pager (generated draft — describes the offer).</li>
<li>A real public evidence memo (Suncor demo) — what research output looks like.</li>
<li>Printed public pages: the lane page (with the standing status block) and one
research synthesis preview — the voice and disclaimers in situ.</li>
<li>Both draft documents: engagement terms template; client-data handling.</li>
<li>A complete sample deliverable (synthetic client): memo PDF, methodology
note, reproduction bundle, checksums.</li>
</ol>"""
    _pdf(body, out)


def onepager(out: Path):
    body = f"""
<div class="band"><div class="t">YUCLAW Founding Pilot — one page</div>
<div class="s">generated draft {datetime.now(timezone.utc).strftime('%Y-%m-%d')} · no prior artifact existed; drafted for counsel review</div></div>
<div class="warn">DRAFT — pending counsel review; never send unreviewed.</div>
<h2>The offer</h2>
<p>Bring a signal (or a basket). Receive an honest, registered, reproducible
answer about what the evidence shows — and what it cannot show at your sample
size. Fixed fee CAD 5,000, paid before any work on your data begins. One memo,
one methodology note, one reproduction bundle, 30 days of questions. No
renewal unless separately agreed.</p>
<h2>What you get</h2>
<ul>
<li>Signal validation suite: rank association with later returns (with
confidence intervals), quantile ordering, churn, horizon decay, placebo.</li>
<li>Basket event-study panel with cluster-robust intervals and a
falsification battery.</li>
<li>Everything registered before computation in your own tamper-evident
protocol chain; a bundle that lets you rerun our numbers without us.</li>
</ul>
<h2>What you do not get</h2>
<ul>
<li>No advice, no recommendations, no forecasts, no targets.</li>
<li>No standing above EXPLORATORY (CLIENT) — the public record's higher
standings cannot be bought.</li>
<li>No use of your data anywhere outside your engagement — enforced in code
and auditable.</li>
</ul>
<h2>Honesty rules baked in</h2>
<p>Fewer than 15 names per date is disclosed as underpowered up front.
Adverse results are delivered as measured. Your file is rejected if it
contains columns we did not ask for.</p>"""
    _pdf(body, out)


def main() -> int:
    PKT.mkdir(parents=True, exist_ok=True)
    manifest = []

    cover_note(PKT / "COVER_NOTE.pdf")
    manifest.append("COVER_NOTE.pdf (generated from live state)")
    onepager(PKT / "founding_pilot_onepager.pdf")
    manifest.append("founding_pilot_onepager.pdf (generated draft — none pre-existed)")

    shutil.copy(_REPO / "docs" / "examples" / "evidence_memo_su.md",
                PKT / "evidence_memo_su.md")
    manifest.append("evidence_memo_su.md (verbatim public demo memo)")

    for src, name in ((_REPO / "docs" / "lane.html", "lane.pdf"),
                      (_REPO / "docs" / "signal_review.html",
                       "signal_review.pdf"),
                      (_REPO / "docs" / "preview" / "gdx_synthesis.html",
                       "gdx_synthesis_preview.pdf")):
        HTML(string=src.read_text(), base_url=str(src.parent)).write_pdf(
            str(PKT / name))
        manifest.append(f"{name} (printed from {src.relative_to(_REPO)})")

    for f in DRAFTS.glob("*_DRAFT.md"):
        shutil.copy(f, PKT / f.name)
        manifest.append(f"{f.name} (COUNSEL-marked draft)")

    (PKT / "ARCHITECTURE_NOTE.md").write_text("""# No-upload / no-payment architecture (for counsel review)

The product surface the lawyer reviews IS the shipped surface:

- The site collects nothing. Zero <form>, upload, or payment elements
  exist anywhere under docs/ — asserted daily by an automated gate
  (tools/check_no_forms.py) in the publish chain; a violation blocks
  deployment.
- The client's first step runs on the client's machine: `yuclaw
  intake-check their.csv` validates the file locally against the exact
  server intake rules (shared code, cannot drift) and prints that nothing
  was transmitted.
- Data changes hands only after engagement, through the counsel-approved
  channel; intake auto-rejects files containing columns we did not
  request.
- Fees are fixed (Founding Pilot A CAD 2,500 / B CAD 5,000), invoiced —
  no online payment collection exists.
- All client work is capped at EXPLORATORY (CLIENT); the public record's
  standings cannot be bought; deliverable scope per tier is enforced by a
  self-test diffing the page's promises against produced sections.
""")
    manifest.append("ARCHITECTURE_NOTE.md (no-upload/no-payment surface, generated)")
    shutil.copy(_REPO / "output" / "byos_dryrun" / "client_deliverable.zip",
                PKT / "client_deliverable_sample.zip")
    manifest.append("client_deliverable_sample.zip (synthetic dry-run deliverable)")

    zpath = PKT / "counsel_packet.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(PKT.iterdir()):
            if f.name != zpath.name and f.is_file():
                z.write(f, f.name)
    print(f"[counsel-packet] {zpath} ({zpath.stat().st_size/1024:.0f} KB)")
    for m in manifest:
        print(f"  · {m}")
    print(f"  · counsel questions enumerated: {len(counsel_questions())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
