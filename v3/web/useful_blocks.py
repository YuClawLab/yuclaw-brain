"""
Shared page blocks for the usefulness build (order of 2026-07-16).

ONE source file for content that renders on multiple pages, so the copies can
never drift:

  - site_header_html()       — site-standard header: logo + version badge +
                               full nav chips (every public page)
  - status_block_html()      — "What is proven / not proven / accruing"
                               (Dashboard + Lab + Canada + Open Index)
  - use_in_research_html()   — "Use YUCLAW in your research" 3-path entry block
  - packet_block_html()      — "Download evidence packet" + citation snippet
                               (Lab / Open Index / Canada)
  - C6_APPROVED_SENTENCE     — the approved C6 status sentence, VERBATIM,
                               required wherever C6 status appears

Compliance: locked vocabulary only — counts, statuses, measured numbers.
No banned adjectives (see tools/check_language.py). All strings here are
research classifications, not recommendations.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

VERSION = "v5.1.0"

# Locked public signal vocabulary — the ONLY signal labels any public page may
# render (mirrors the homepage "Public signal vocabulary" legend). Pages render
# these verbatim; display-layer remaps that invent labels outside this set
# (e.g. "RISK_FLAG (weakening)") are a bug — label-audit order of 2026-07-26.
PUBLIC_LABELS = {
    "STRONG_BULLISH", "BULLISH", "NEUTRAL", "WATCH",
    "WEAKENING", "NEGATIVE_EVENT", "BEARISH_WATCH", "RISK_ALERT",
}


def public_label(raw: str) -> str:
    """Render a signal label from the locked vocabulary, verbatim.
    Anything outside the set renders as "(?)" — never an invented label."""
    lbl = (raw or "").upper()
    return lbl if lbl in PUBLIC_LABELS else "(?)"

_PACKETS_DIR = Path(__file__).resolve().parents[2] / "docs" / "packets"


def load_packet_manifest(kind: str) -> dict | None:
    """Read docs/packets/manifest.json entry for `kind` (lab | open_index | canada).
    Returns None when packets have not been built yet — callers skip the block."""
    m = _PACKETS_DIR / "manifest.json"
    if not m.exists():
        return None
    try:
        return json.loads(m.read_text()).get(kind)
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Site-standard header (one source, every page) — YUCLAW + version badge +
# full nav chips + optional page subtitle + optional right-side stamp.
# Fully inline-styled so it renders identically regardless of page CSS.
# ---------------------------------------------------------------------------
_NAV_CHIPS = (
    ("Validation Lab", "validation_lab.html"),
    ("SMH Evidence Lens", "etf_evidence.html"),
    ("XLK Evidence Lens", "xlk_evidence.html"),
    ("Canada Resources Evidence", "canada_resources.html"),
    ("Forward Tracking", "validation.html"),
    ("Signal Review", "signal_review.html"),
    ("GitHub", "https://github.com/YuClawLab/yuclaw-brain"),
    ("PyPI", "https://pypi.org/project/yuclaw/"),
    ("Ledger", "https://github.com/YuClawLab/yuclaw-trust"),
    ("Methodology", "methodology/backfill.md"),
    ("Home", "index.html"),
)


def site_header_html(subtitle: str = "", stamp: str = "", active: str = "") -> str:
    """The shared site header. Rendered identically on every page that calls it.
    active: this page's output filename (e.g. "validation_lab.html") — the
    matching nav chip gets the accent treatment + aria-current="page"."""
    def chip(label: str, href: str) -> str:
        if href == active:
            return (f'<a href="{href}" aria-current="page" '
                    f'style="color:#00E676;text-decoration:none;font-size:12px;'
                    f'padding:4px 10px;border-radius:6px;background:#00E67614;'
                    f'border:1px solid #00E67640;white-space:nowrap">'
                    f"{escape(label)}</a>")
        return (f'<a href="{href}" style="color:#A0AEC0;text-decoration:none;font-size:12px;'
                f'padding:4px 10px;border-radius:6px;background:#1E232D;white-space:nowrap">'
                f"{escape(label)}</a>")
    chips = "".join(chip(label, href) for label, href in _NAV_CHIPS)
    sub = (f'<span style="font-size:11px;color:#718096;font-family:JetBrains Mono,monospace">'
           f"{escape(subtitle)}</span>") if subtitle else ""
    right = (f'<span style="font-size:11px;color:#718096;font-family:JetBrains Mono,monospace;'
             f'white-space:nowrap">{escape(stamp)}</span>') if stamp else ""
    return f"""
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;
                gap:10px;margin-bottom:20px;padding:14px 20px;background:#151A23;
                border:1px solid #1E232D;border-radius:12px">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <a href="index.html" style="text-decoration:none;display:inline-flex;
                                    align-items:center;gap:12px">
          <span style="font-size:20px;font-weight:800;color:#FFF">YU<span
            style="color:#00E676">CLAW</span></span>
          <span style="display:inline-block;background:#00E67620;color:#00E676;
                       border:1px solid #00E67680;padding:3px 9px;border-radius:5px;
                       font-size:10px;font-weight:700;letter-spacing:0.5px;
                       font-family:JetBrains Mono,monospace">{escape(VERSION)}</span>
        </a>
        {sub}
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:6px;align-items:center">
        {chips}
        {right}
      </div>
    </div>"""


# The approved C6 status sentence. VERBATIM wherever C6 status appears —
# do not paraphrase, shorten, or update outside a dedicated methodology order.
C6_APPROVED_SENTENCE = (
    "rareness confirmed OOS 2026-07-06 (22% fire rate, n=9 held-out); "
    "sign confirmation pending (elevated arm n=2; accrual live from 2026-07-16)"
)

# ---------------------------------------------------------------------------
# Part H — proven / not proven / accruing (single source, four pages)
# ---------------------------------------------------------------------------
STATUS_PROVEN = [
    "Replay works — one command reproduces every Lab statistic and ledger root from published data",
    "Ledger anchored daily — sha-256 daily roots committed to a public git repository before pages update",
    "Evidence traces to filings — every accepted event carries a source URL, accession number, and verified excerpt",
    "Coverage measured — SEC-filer weight per lens is stated as measured, never rounded up",
    "Snapshots are point-in-time — daily as-of writes, zero retroactive edits (outage window disclosed, not repaired)",
    "Evidence-tier names are never scored — enforced by positive gating and a standing negative check",
]
STATUS_NOT_PROVEN = [
    "Forward alpha — no spread, IC, or alpha significant at 5% with adequate power",
    f"C6 risk-gate sign — {C6_APPROVED_SENTENCE}",
    "Peer-model CAR lead — event-study lead over peer models is not established; live-era sample remains small",
]
STATUS_ACCRUING = [
    "Forward out-of-sample record — one period per trading day, accruing daily",
    "Matured CAR events — each accepted event matures into the event study after its forward window completes",
    "C6 elevated arm — live Form-4 ingestion since 2026-07-16 restores the insider stream to production inputs",
    "External replications — the replication log accrues as independent runs are reported",
]


def status_block_html() -> str:
    """The shared status block. Rendered identically on every page that calls it."""
    def li(items: list[str], mark: str, color: str) -> str:
        return "".join(
            f'<li style="margin:5px 0;color:#A0AEC0;font-size:12.5px;line-height:1.55">'
            f'<span style="color:{color};font-weight:700">{mark}</span> {escape(x)}</li>'
            for x in items)
    col = (
        '<div style="flex:1;min-width:250px">'
        '<div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:{c};margin-bottom:6px">{h}</div>'
        '<ul style="list-style:none;padding:0">{body}</ul></div>'
    )
    return f"""
    <div style="background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px" id="status-block">
      <div style="font-size:13px;font-weight:700;color:#FFF;margin-bottom:8px">Status — proven · not proven · accruing</div>
      <p style="font-size:11.5px;color:#718096;margin:0 0 10px">
        Rendered from one shared source (<code>v3/web/useful_blocks.py</code>) on every page that shows it,
        so the copies cannot drift. Statuses are measured, not aspirational.
      </p>
      <div style="display:flex;gap:22px;flex-wrap:wrap">
        {col.format(c="#00E676", h="Proven (verifiable today)", body=li(STATUS_PROVEN, "✓", "#00E676"))}
        {col.format(c="#FF3366", h="Not proven", body=li(STATUS_NOT_PROVEN, "✗", "#FF3366"))}
        {col.format(c="#FBA94B", h="Accruing", body=li(STATUS_ACCRUING, "·", "#FBA94B"))}
      </div>
    </div>"""


# ---------------------------------------------------------------------------
# Part B — "Use YUCLAW in your research" (Dashboard + Lab + Canada + Open Index)
# ---------------------------------------------------------------------------
SUNCOR_TRACE_HREF = "trace_su.html"


def use_in_research_html(packet_href: str | None = None,
                         guide_link: bool = False) -> str:
    """Three paths, three lines each. packet_href: this page's evidence packet
    (None on pages without one — the citation path then links the Lab packet).
    guide_link: landing only — adds the User Guide (PDF) line to the block."""
    cite_href = packet_href or "validation_lab.html#evidence-packet"
    guide = ('<p style="font-size:12px;color:#A0AEC0;margin:10px 0 0">'
             '<a href="YUCLAW_User_Guide_v5.1.pdf">\U0001F4D6 User Guide (PDF)</a>'
             ' — from pip install to full verification, six pages. · '
             '<a href="YUCLAW_Guide_Utilisateur_v5.1_FR.pdf">\U0001F4D6 '
             "Guide de l'utilisateur (FR)</a></p>"
             ) if guide_link else ""
    return f"""
    <div style="background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px" id="use-in-research">
      <div style="font-size:13px;font-weight:700;color:#FFF;margin-bottom:8px">Use YUCLAW in your research</div>
      <div style="display:flex;gap:18px;flex-wrap:wrap">
        <div style="flex:1;min-width:240px">
          <div style="font-size:12px;color:#E2E8F0;font-weight:700;margin-bottom:4px">1 · Verify the record</div>
          <p style="font-size:12px;color:#A0AEC0;line-height:1.6;margin:0">
            <code>pip install yuclaw</code> then <code>yuclaw replay-lab</code>.<br>
            No install: <a href="https://github.com/YuClawLab/yuclaw-brain/blob/main/tools/replay_lab.py">tools/replay_lab.py</a>
            (stdlib only) against the published bundle.<br>
            Exit 0 = every statistic and ledger root reproduced. <a href="replication.html">How to report a replication →</a>
          </p>
        </div>
        <div style="flex:1;min-width:240px">
          <div style="font-size:12px;color:#E2E8F0;font-weight:700;margin-bottom:4px">2 · Inspect one evidence trace</div>
          <p style="font-size:12px;color:#A0AEC0;line-height:1.6;margin:0">
            One real Suncor 6-K, end to end:<br>
            filing → exhibit → extracted prose → event type → grade → C6 posture.<br>
            <a href="{SUNCOR_TRACE_HREF}">Open the trace →</a> ·
            <a href="examples/evidence_memo_su.md">example evidence memo (Suncor) →</a>
          </p>
        </div>
        <div style="flex:1;min-width:240px">
          <div style="font-size:12px;color:#E2E8F0;font-weight:700;margin-bottom:4px">3 · Cite a research lens</div>
          <p style="font-size:12px;color:#A0AEC0;line-height:1.6;margin:0">
            Every evidence packet ships a ready citation snippet<br>
            (version, data-through, build date, source commit).<br>
            <a href="{cite_href}">Get the citation →</a>
          </p>
        </div>
      </div>
      {guide}
    </div>"""


# ---------------------------------------------------------------------------
# Part A — evidence packet block + citation snippet (Lab / Open Index / Canada)
# ---------------------------------------------------------------------------
def citation_snippet(page_label: str, data_through: str, built: str, commit: str) -> str:
    """The locked citation template (plain text, shown verbatim + shipped in packets)."""
    return (f"YUCLAW {page_label}, {VERSION}, data through {data_through}, "
            f"built {built}, commit {commit[:12]}; evidence-tier names excluded "
            f"from scoring universe.")


def packet_block_from_manifest(kind: str) -> str:
    """Render the packet block from docs/packets/manifest.json; empty string
    when the packet has not been built yet (never a broken link)."""
    m = load_packet_manifest(kind)
    if not m:
        return ""
    return packet_block_html(m["page_label"], f"packets/{m['zip']}", m["files"],
                             m["data_through"], m["built"], m["commit"])


def packet_block_html(page_label: str, packet_href: str, contents: list[str],
                      data_through: str, built: str, commit: str) -> str:
    """"Download evidence packet" card. contents: human list of files inside."""
    cite = citation_snippet(page_label, data_through, built, commit)
    items = "".join(f"<li style='margin:3px 0'>{escape(x)}</li>" for x in contents)
    return f"""
    <div style="background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:20px" id="evidence-packet">
      <div style="font-size:13px;font-weight:700;color:#FFF;margin-bottom:8px">Download evidence packet</div>
      <p style="font-size:12px;color:#A0AEC0;margin:0 0 8px;line-height:1.6">
        Everything this page derives, as files — YUCLAW-derived data only (derived statistics,
        counts, classifications; never raw vendor price/options data). Regenerated in the daily chain.
      </p>
      <p style="margin:0 0 10px">
        <a href="{packet_href}" download
           style="display:inline-block;background:#00E676;color:#0B0E14;font-weight:800;font-size:13px;
                  padding:8px 16px;border-radius:8px;text-decoration:none">Download packet (.zip)</a>
      </p>
      <ul style="list-style:none;padding:0;font-size:11.5px;color:#718096;font-family:JetBrains Mono,monospace">
        {items}
        <li style='margin:3px 0'>METADATA.json — data-through, build date, source commit, ledger root, methodology version, scope, known limitations</li>
        <li style='margin:3px 0'>CITATION.txt — the snippet below</li>
      </ul>
      <div style="margin-top:10px;background:#151A23;border:1px solid #1E232D;border-radius:8px;padding:10px 14px">
        <div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#718096;margin-bottom:4px">Cite this page</div>
        <code style="font-size:11.5px;line-height:1.5;display:block;white-space:normal">{escape(cite)}</code>
      </div>
    </div>"""
