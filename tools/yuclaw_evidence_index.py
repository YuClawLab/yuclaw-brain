#!/usr/bin/env python3
"""
evidence_index.json generator (AI evidence layer, 2026-08-01).

Machine-readable index of every public page, packet, protocol, and citation
convention with stable URLs and data-through dates — regenerated in the
daily chain so agents can discover the surface without scraping HTML.
Derived data only; the not-advice frame travels in the payload.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

BASE = "https://yuclawlab.github.io/yuclaw-brain"
OUT = _REPO / "docs" / "evidence_index.json"

PAGES = {
    "explorer.html": "Universe Explorer — the full 79-name table, client-side filter/sort",
    "sectors.html": "Sector overview — descriptive medians of current classifications (display, not inference)",
    "tour.html": "The 5-minute tour — five commands with build-captured output",
    "signal_review.html": "Signal Review — bring-your-signal research review "
                          "service (five-step no-upload flow, fixed tiers, "
                          "EXPLORATORY (CLIENT) ceiling)",
    # Why-page family: one pattern entry + the worked example. Builder's
    # choice, stated: the index stays compact — all 79 tickers enumerate
    # in /explorer_data.json; every page follows the same pinned template.
    "why/AAPL.html": "Why AAPL — per-name classification anatomy (worked "
                     "example of the why/{TICKER}.html family, 79 pages, "
                     "one pinned template)",

    "index.html": "landing — current signals (locked vocabulary)",
    "validation_lab.html": "Validation Lab — cohorts, rigor, clustered inference, baselines",
    "validation.html": "Forward Tracking — ledger, label calibration",
    "etf_evidence.html": "SMH Covered-Constituent Evidence Lens",
    "xlk_evidence.html": "XLK Covered-Constituent Evidence Lens",
    "canada_resources.html": "Canada Resources Evidence",
    "todays_evidence.html": "Today's Evidence Changes",
    "replication.html": "Replication — how to reproduce, honestly-empty log",
    "lane.html": "YUCLAW's Lane — scope statement",
    "trace_su.html": "Suncor evidence trace (worked example)",
}


def _data_through(html_path: Path) -> str | None:
    try:
        m = re.search(r"[Dd]ata through (\d{4}-\d{2}-\d{2})",
                      html_path.read_text(errors="replace"))
        return m.group(1) if m else None
    except OSError:
        return None


def main() -> int:
    from yuclaw_protocol_registry import Registry
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    protocols = []
    runs_by: dict = {}
    for ln in reg._lines:
        if ln["kind"] == "run":
            runs_by[ln["payload"]["protocol_id"]] = \
                runs_by.get(ln["payload"]["protocol_id"], 0) + 1
    sup = {l["payload"]["protocol_id"] for l in reg._lines
           if l["kind"] == "supersede_notice"}
    for ln in reg._lines:
        if ln["kind"] != "protocol":
            continue
        pl = ln["payload"]
        protocols.append({"protocol_id": pl["protocol_id"],
                          "name": pl["name"],
                          "lock_date": pl["lock_date"],
                          "runs": runs_by.get(pl["protocol_id"], 0),
                          "status": ("SUPERSEDED" if pl["protocol_id"] in sup
                                     else "LOCKED")})
    manifest_p = _REPO / "docs" / "packets" / "manifest.json"
    packets = json.loads(manifest_p.read_text()) if manifest_p.exists() else {}

    index = {
        "what": ("YUCLAW evidence index — machine-readable map of the open "
                 "evidence layer. Research and education only; nothing here "
                 "is investment advice; classifications are not "
                 "recommendations."),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "base_url": BASE,
        "llms_txt": f"{BASE}/llms.txt",
        "locked_vocabulary": ["STRONG_BULLISH", "BULLISH", "NEUTRAL", "WATCH",
                              "WEAKENING", "NEGATIVE_EVENT", "BEARISH_WATCH",
                              "RISK_ALERT"],
        "frozen_implication_line": (
            "Investment implication: none established — no buy, sell, or "
            "alpha conclusion is supported by this page."),
        "pages": [{"url": f"{BASE}/{p}", "what": what,
                   "data_through": _data_through(_REPO / "docs" / p)}
                  for p, what in PAGES.items()],
        "packets": {k: {"url": f"{BASE}/packets/{v['zip']}",
                        "data_through": v.get("data_through"),
                        "files": v.get("files")}
                    for k, v in packets.items() if isinstance(v, dict)},
        "replay_bundle": f"{BASE}/replay/lab_replay_bundle.json",
        "schemas": {n: f"{BASE}/schemas/{n}.v1.json" for n in
                    ("SignalSnapshot", "EvidenceEvent", "ResearchProtocol",
                     "RobustnessCell", "ResearchMemo")},
        "registry": {"where": "registry/protocols.jsonl in "
                              "github.com/YuClawLab/yuclaw-brain "
                              "(hash-chained, append-only)",
                     "protocols": protocols},
        "citation_format": ("YUCLAW <page>, data through <date>, "
                            "build <commit>, "
                            "https://github.com/YuClawLab/yuclaw-brain — or "
                            "the CITATION.txt inside any packet; event-level "
                            "citations use event IDs from the packet CSVs."),
        "verify": ("pip install yuclaw && yuclaw replay-lab  # recomputes "
                   "the published Lab statistics from the public bundle"),
    }
    OUT.write_text(json.dumps(index, indent=1))
    # llms.txt auto-managed pages block (audit F2): regenerated from the
    # same PAGES dict every build so the machine surface can never lag.
    lp = _REPO / "docs" / "llms.txt"
    txt = lp.read_text()
    START = "## Pages (auto-generated from the evidence index — do not hand-edit)"
    END = "## How to cite"
    lines = [START, ""]
    lines.append("- /why/{TICKER}.html — per-name classification anatomy "
                 "(79 pages; worked example /why/AAPL.html)")
    for pg, what in sorted(PAGES.items()):
        lines.append(f"- /{pg} — {what}")
    lines += ["", END]
    import re as _re
    if START in txt:
        txt = _re.sub(_re.escape(START) + r".*?" + _re.escape(END),
                      "\n".join(lines), txt, flags=_re.S)
    else:
        txt = txt.replace(END, "\n".join(lines), 1)
    lp.write_text(txt)
    print(f"[evidence-index] wrote {OUT} ({len(protocols)} protocols, "
          f"{len(PAGES)} pages, {len(index['packets'])} packets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
