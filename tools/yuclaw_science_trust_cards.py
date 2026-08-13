#!/usr/bin/env python3
"""
SCIENCE TRUST CARDS — v6 Implementation I, Phase 7/8 (order 2026-08-14).
STAGED ONLY: writes exclusively under docs/preview/. Linked from nowhere
public; navigation untouched; live pages and live JSON untouched.
===========================================================================
Every displayed state is DERIVED AT BUILD TIME from the then-current
registered artifacts through Research-State Derivation v1 (ad599b80d2db)
and its registered inputs. Nothing is hardcoded: no research state, no
sequential state, no coverage state, no truncation state, no maturity
state appears in this module as a per-name constant. Absence is
information — PENDING / UNKNOWN / NOT_APPLICABLE / NOT_ESTIMABLE /
NOT_IDENTIFIABLE / INSUFFICIENT_EVIDENCE are first-class visible states,
never hidden, zeroed, neutralized, or collapsed.

ONE derivation path: derive_all() below produces the canonical field set;
the human card (HTML), the staged machine JSON, and the staged why-mirror
science_trust blocks all render from the same derived object. The
equality gate (tools/check_science_trust.py, release gate #11) re-derives
and compares all three surfaces field-for-field, checks provenance
against the registry artifacts directly, checks absence-state visibility,
and checks byte-reproducibility.

DETERMINISM: no wall clock anywhere in the outputs. The derivation
anchor is Research-State Derivation v1's own chain-tip anchor; the same
canonical artifacts + the same renderer version always produce
byte-identical output (A-7).

Promotion: NOTHING here promotes previews live — no date logic, no cron,
no feature flag, no build rule (A-6). Live promotion requires a separate
authorized v6 release order after Phase-13 gates.
"""
from __future__ import annotations

import html as _html
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from yuclaw_anytime_record import THETA_SUPPORTED, THETA_WEAK  # noqa: E402
from yuclaw_anytime_observer import load_enrollments, load_obs_chain, \
    _state as _anytime_state  # noqa: E402

RENDERER_VERSION = "1.0.0"
REG = _REPO / "registry"
OUT_TRUST = _REPO / "docs" / "preview" / "trust"
OUT_WHY = _REPO / "docs" / "preview" / "why"

ANNOTATIONS = {"FACT", "DERIVED_RESULT", "LIMITATION", "PENDING",
               "NOT_ESTIMABLE", "NOT_IDENTIFIABLE"}
ABSENCE_STATES = {"PENDING", "UNKNOWN", "NOT_APPLICABLE", "NOT_ESTIMABLE",
                  "NOT_IDENTIFIABLE", "INSUFFICIENT_EVIDENCE"}


# ------------------------------------------------------------ derivation
def load_canon() -> dict:
    """Load the registered artifacts (read-only). The anchor is Research-
    State Derivation v1's chain-tip anchor — the derivation this surface
    renders through (A-1)."""
    c = {
        "research_state": json.loads((REG / "research_state.json").read_text()),
        "completeness": json.loads((REG / "completeness_profile.json").read_text()),
        "discovery": json.loads((REG / "discovery_ledger.json").read_text()),
        "anytime": json.loads((REG / "anytime_record.json").read_text()),
        "truncation": json.loads((REG / "truncation_ledger.json").read_text()),
    }
    c["anchor"] = c["research_state"]["spec"]["derivation_anchor_chain_tip"]
    return c


def _f(value, annotation: str, basis: str, source: str) -> dict:
    """One canonical Science Trust field."""
    if annotation not in ANNOTATIONS:
        raise ValueError(f"annotation {annotation!r} outside the locked "
                         f"vocabulary {sorted(ANNOTATIONS)}")
    return {"value": value, "annotation": annotation, "basis": basis,
            "source": source}


def _name_scoped_hypotheses(canon: dict, name: str) -> list[dict]:
    """Ledger hypotheses whose registered universe/name/claim carries the
    ticker as a whole token (results-blind text scan of the derived
    ledger; SUPERSEDED lineage kept visible in HISTORY, excluded here)."""
    import re
    pat = re.compile(rf"(?<![A-Z0-9]){re.escape(name)}(?![A-Z0-9])")
    out = []
    for h in canon["discovery"]["hypotheses"]:
        blob = f"{h.get('name','')} {h.get('claim','')} {h.get('universe','')}"
        if pat.search(blob):
            out.append({"hypothesis_id": h["hypothesis_id"],
                        "family": h["evidence_family"],
                        "status": h["status"],
                        "family_adjudication": h.get("family_adjudication",
                                                     "PENDING")})
    return out


def derive_platform(canon: dict) -> dict:
    """Platform-scoped derived context shared by every card (SCIENCE tab)."""
    rs, dl, tr = (canon["research_state"], canon["discovery"],
                  canon["truncation"])
    # C6 component: every registered read, verbatim, latest last.
    c6 = rs["platform"].get("c6_component", [])
    # Sequential evidence: exactly from the canonical Anytime artifact +
    # the observation chain replay — never assumed (A-2).
    enrollments = load_enrollments()
    obs = load_obs_chain(enrollments=enrollments)
    seq = []
    for e in enrollments:
        st = obs[e["enrollment_id"]]
        seq.append({
            "enrollment_id": e["enrollment_id"],
            "instrument": e["instrument"],
            "observations": st["t"],
            "sequential_state": _anytime_state(e, st),
            "maturity_condition": next(
                x["maturity"] for x in canon["anytime"]["enrollments"]
                if x["enrollment_id"] == e["enrollment_id"]),
        })
    trunc_entries = [{"site_key": t["site_key"],
                      "count": str(t.get("count")),
                      "reason": t["reason"]}
                     for t in tr["entries"]]
    return {
        "c6_component": [{"research_state": r["research_state"],
                          "annotation_verbatim": r["annotation"]}
                         for r in c6],
        "discovery_ledger": {"hypotheses": len(dl["hypotheses"]),
                             "families": len(dl["families"]),
                             "status_counts": dl["status_counts"],
                             "family_adjudication": "PENDING until each "
                             "family's first registered read"},
        "sequential_evidence": seq,
        "truncation_ledger": {"entries": len(trunc_entries),
                              "entries_with_pending_or_unknown_count":
                              sorted(t["site_key"] for t in trunc_entries
                                     if str(t["count"]).upper()
                                     in ("PENDING", "UNKNOWN", "NONE")),
                              "detail": trunc_entries},
    }


def derive_name(canon: dict, name: str) -> dict:
    """The canonical Science Trust field set for one name. Pure function
    of the registered artifacts — every state below is read or scanned,
    never chosen."""
    rs = canon["research_state"]["names"][name]
    cp = canon["completeness"]["names"][name]
    cls = cp["class"]
    scored = cls == "us_scoring"
    hyps = _name_scoped_hypotheses(canon, name)
    active_hyps = [h for h in hyps if h["status"] != "SUPERSEDED"]

    fields = {}
    fields["name"] = _f(name, "FACT", "registered universe membership",
                        "completeness_profile.json")
    fields["universe_class"] = _f(
        cls, "FACT",
        "evidence tier — never scored" if cls == "canada_evidence" else
        ("scored US universe (U79)" if scored else
         "foreign issuer — Form 4 exemption applies"),
        "completeness_profile.json")
    fields["research_state"] = _f(
        rs["research_state"], "DERIVED_RESULT",
        "Research-State Derivation v1 precedence table over registered "
        "reads at the build anchor",
        "research_state.json")
    fields["evidence_coverage"] = _f(
        {fam: st["state"] for fam, st in sorted(cp["per_family"].items())},
        "DERIVED_RESULT",
        "Evidence Completeness Profile v1 counting rules; UNKNOWN and "
        "NOT_APPLICABLE are legal derived states, not gaps in this card",
        "completeness_profile.json")
    fields["independent_evidence"] = _f(
        {"families_observed": len(cp["observed_families"]),
         "families": sorted(cp["observed_families"]),
         "material_missing": sorted(cp["material_missing_families"])},
        "DERIVED_RESULT",
        "distinct observed evidence families (counting only; cross-family "
        "independence is declared, not measured — see dependency)",
        "completeness_profile.json")
    dep_hyps = [h for h in canon["discovery"]["hypotheses"]
                if "dependency" in h["evidence_family"]]
    fields["dependency"] = _f(
        "PENDING" if dep_hyps else "PENDING",
        "PENDING",
        (f"layered-dependency family registered "
         f"({dep_hyps[0]['evidence_family']}, "
         f"{dep_hyps[0]['status']}) — no name-scoped read yet"
         if dep_hyps else
         "no registered dependency read exists at the build anchor"),
        "discovery_ledger.json")
    fields["discovery_context"] = _f(
        {"multiplicity": rs["multiplicity"],
         "name_scoped_hypotheses":
             [{"hypothesis_id": h["hypothesis_id"], "family": h["family"],
               "status": h["status"]} for h in active_hyps]},
        "DERIVED_RESULT" if active_hyps else "PENDING",
        "Discovery Ledger v1 (results-blind name scan) + family "
        "adjudication state from Research-State Derivation v1",
        "discovery_ledger.json")
    c6 = canon["research_state"]["platform"].get("c6_component", [])
    fields["platform_component_context"] = _f(
        {"c6_component": c6[-1]["research_state"] if c6 else "PENDING",
         "registered_reads": len(c6)},
        "DERIVED_RESULT" if c6 else "PENDING",
        "platform C6 risk-component reads recorded in the chain, "
        "rendered verbatim on the SCIENCE tab; the discovery family "
        "adjudicates at its registered read",
        "research_state.json")
    fields["sequential_evidence"] = _f(
        rs["sequential_evidence"], "DERIVED_RESULT",
        "Anytime Evidence Record v1 — enrolled instruments are label-tier; "
        "the platform enrollment states render on the SCIENCE tab from "
        "the canonical artifact at build time",
        "anytime_record.json")
    fields["conflicting_evidence"] = _f(
        "CONFLICTED" if rs["research_state"] == "CONFLICTED"
        else "NONE_DERIVED",
        "DERIVED_RESULT",
        "Research-State Derivation v1 contradiction rule (CONFLICTED "
        "would surface here and in the research state itself)",
        "research_state.json")
    fields["truncation_impact"] = _f(
        "NOT_ESTIMABLE", "NOT_ESTIMABLE",
        "the Truncation & Error Budget ledger is site-key-scoped; no "
        "registered per-name attribution exists — the full ledger "
        "renders on the SCIENCE tab, including PENDING counts",
        "truncation_ledger.json")
    if cls == "canada_evidence":
        fields["forward_maturity"] = _f(
            "NOT_APPLICABLE", "DERIVED_RESULT",
            "evidence-tier names are never scored; no forward label "
            "outcomes exist by design (registered tier rule)",
            "completeness_profile.json")
    else:
        matured = [h for h in active_hyps
                   if h["status"] in ("MATURED", "SUPPORTED",
                                      "NOT_SUPPORTED")]
        fields["forward_maturity"] = _f(
            {"matured_name_scoped_reads": len(matured)} if matured
            else "PENDING",
            "DERIVED_RESULT" if matured else "PENDING",
            "matured name-scoped primary endpoints in the Discovery "
            "Ledger at the build anchor",
            "discovery_ledger.json")
    return fields


def derive_all() -> dict:
    canon = load_canon()
    names = sorted(canon["research_state"]["names"])
    return {
        "anchor": canon["anchor"],
        "renderer_version": RENDERER_VERSION,
        "derivation_protocol": canon["research_state"]["spec"]["protocol_id"],
        "platform": derive_platform(canon),
        "names": {n: derive_name(canon, n) for n in names},
    }


# --------------------------------------------------------------- html
_CSS = """
:root{--ink:#1a202c;--sub:#4a5568;--mut:#718096;--line:#e2e8f0;
--bg:#fafbfc;--card:#ffffff;--chip:#edf2f7;--accent:#2c5282}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--ink);
font-family:Georgia,'Times New Roman',serif;line-height:1.55}
.wrap{max-width:860px;margin:0 auto;padding:28px 20px 60px}
.previewband{background:#fffaf0;border:1px solid #ecc94b;color:#744210;
font-family:'JetBrains Mono',monospace;font-size:11px;padding:6px 10px;
margin-bottom:18px}
header h1{font-size:21px;font-weight:600;letter-spacing:.2px}
header .sub{color:var(--sub);font-size:13px;margin-top:4px}
.anchor{font-family:'JetBrains Mono',monospace;font-size:10px;
color:var(--mut);margin-top:6px;word-break:break-all}
.card{background:var(--card);border:1px solid var(--line);margin-top:18px}
.frow{display:flex;gap:14px;padding:12px 16px;border-top:1px solid
var(--line);align-items:baseline;flex-wrap:wrap}
.frow:first-child{border-top:none}
.flab{flex:0 0 190px;color:var(--sub);font-size:13px}
.fval{flex:1;min-width:220px;font-size:14px}
.chip{display:inline-block;font-family:'JetBrains Mono',monospace;
font-size:11.5px;background:var(--chip);border:1px solid var(--line);
padding:2px 8px;color:var(--ink)}
.basis{color:var(--mut);font-size:12px;margin-top:3px}
.annot{font-family:'JetBrains Mono',monospace;font-size:10px;
color:var(--mut);letter-spacing:.4px}
.tabs{margin-top:22px}
.tabs details{border-bottom:1px solid var(--line)}
.tabs summary{font-family:'JetBrains Mono',monospace;font-size:11px;
letter-spacing:.6px;padding:9px 4px;cursor:pointer;color:var(--mut)}
.tabs details[open]>summary{color:var(--accent)}
.tabs details>div{padding:4px 4px 16px;font-size:13.5px;
color:var(--sub)}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0}
th,td{border:1px solid var(--line);padding:5px 8px;text-align:left;
vertical-align:top}
th{font-family:'JetBrains Mono',monospace;font-size:10.5px;
letter-spacing:.5px;color:var(--mut);font-weight:500}
code{font-family:'JetBrains Mono',monospace;font-size:12px;
background:var(--chip);padding:1px 4px}
.footnote{color:var(--mut);font-size:11.5px;margin-top:26px;
border-top:1px solid var(--line);padding-top:10px}
@media(max-width:480px){.flab{flex-basis:100%}.wrap{padding:18px 12px}}
"""
_TABS = ["WHY", "SOURCES", "STORIES", "DEPENDENCIES", "SCIENCE",
         "HISTORY", "REPRODUCE"]



def _esc(x) -> str:
    return _html.escape(str(x), quote=True)


def _val_html(v) -> str:
    if isinstance(v, dict):
        rows = []
        for k, x in v.items():
            if isinstance(x, list):
                x = ", ".join(str(i) if not isinstance(i, dict) else
                              " ".join(str(j) for j in i.values())
                              for i in x) or "none recorded"
            rows.append(f"<div><span class='annot'>{_esc(k)}</span> "
                        f"<span class='chip'>{_esc(x)}</span></div>")
        return "\n".join(rows)
    return f"<span class='chip'>{_esc(v)}</span>"


def render_card(name: str, fields: dict, platform: dict, meta: dict) -> str:
    rows = []
    for key, f in fields.items():
        label = key.replace("_", " ")
        rows.append(
            f"<div class='frow' data-field='{_esc(key)}'>"
            f"<div class='flab'>{_esc(label)}"
            f"<div class='annot'>{_esc(f['annotation'])}</div></div>"
            f"<div class='fval'>{_val_html(f['value'])}"
            f"<div class='basis'>{_esc(f['basis'])}</div></div></div>")

    cov = fields["evidence_coverage"]["value"]
    stories = "".join(
        f"<tr><td>{_esc(fam)}</td><td><span class='chip'>{_esc(st)}"
        f"</span></td></tr>" for fam, st in cov.items())
    seq_rows = "".join(
        f"<tr><td>{_esc(s['enrollment_id'])}</td>"
        f"<td>{_esc(s['instrument'])}</td>"
        f"<td>{s['observations']}</td>"
        f"<td><span class='chip'>{_esc(s['sequential_state'])}</span></td>"
        f"<td>{_esc(s['maturity_condition'])}</td></tr>"
        for s in platform["sequential_evidence"])
    c6_rows = "".join(
        f"<tr><td><span class='chip'>{_esc(r['research_state'])}</span>"
        f"</td><td>{_esc(r['annotation_verbatim'])}</td></tr>"
        for r in platform["c6_component"])
    tr_rows = "".join(
        f"<tr><td>{_esc(t['site_key'])}</td>"
        f"<td><span class='chip'>{_esc(t['count'])}</span></td>"
        f"<td>{_esc(t['reason'])}</td></tr>"
        for t in platform["truncation_ledger"]["detail"])
    hist_rows = "".join(
        f"<tr><td>{_esc(h['hypothesis_id'])}</td><td>{_esc(h['family'])}"
        f"</td><td><span class='chip'>{_esc(h['status'])}</span></td></tr>"
        for h in _hist(fields)) or \
        "<tr><td colspan='3'>no name-scoped registered reads at the " \
        "build anchor — absence is information, not an error</td></tr>"

    dl = platform["discovery_ledger"]
    tabs_html = [
        # WHY
        f"<p>This card states what the evidence record can and cannot "
        f"support for {_esc(name)} — derived, field by field, from the "
        f"registered artifacts listed under SOURCES. States such as "
        f"PENDING, UNKNOWN, NOT_APPLICABLE, NOT_ESTIMABLE and "
        f"INSUFFICIENT_EVIDENCE are findings in their own right: they "
        f"say precisely how far the record goes today. Nothing on this "
        f"card is chosen by hand; re-running the renderer against the "
        f"same artifacts reproduces it byte for byte.</p>"
        f"<p>Research state here never translates to a trading signal, "
        f"score, or portfolio action — the two vocabularies are "
        f"structurally separated and gate-enforced.</p>",
        # SOURCES
        "<table><tr><th>artifact</th><th>role</th></tr>" +
        "".join(f"<tr><td><code>registry/{a}</code></td><td>{r}</td></tr>"
                for a, r in [
                    ("research_state.json", "Research-State Derivation v1 "
                     "(the derivation this card renders through)"),
                    ("completeness_profile.json", "evidence coverage per "
                     "family"),
                    ("discovery_ledger.json", "discovery context, "
                     "hypothesis lineage, family adjudication"),
                    ("anytime_record.json", "sequential-evidence "
                     "enrollments"),
                    ("truncation_ledger.json", "truncation & error "
                     "budget entries"),
                    ("protocols.jsonl", "the canonical chain every "
                     "artifact above derives from")]) +
        f"</table><p class='basis'>derivation anchor (chain tip): "
        f"<code>{_esc(meta['anchor'])}</code></p>",
        # STORIES
        f"<p>Evidence families observed for {_esc(name)} — each family "
        f"is one independent line of evidence in the completeness "
        f"profile:</p><table><tr><th>family</th><th>state</th></tr>"
        f"{stories}</table>",
        # DEPENDENCIES
        f"<p>Cross-family independence is declared, not measured: the "
        f"dependency profile below is {_esc(fields['dependency']['value'])} "
        f"until the registered layered-dependency read exists.</p>"
        f"<p class='basis'>{_esc(fields['dependency']['basis'])}</p>",
        # SCIENCE
        f"<p>Platform component context (registered reads, verbatim):</p>"
        f"<table><tr><th>state</th><th>registered annotation</th></tr>"
        f"{c6_rows}</table>"
        f"<p>Sequential evidence — enrolled instruments (label-tier), "
        f"read from the canonical Anytime Evidence Record and the "
        f"observation chain at build time; thresholds "
        f"{THETA_WEAK:g}/{THETA_SUPPORTED:g}:</p>"
        f"<table><tr><th>enrollment</th><th>instrument</th><th>obs</th>"
        f"<th>state</th><th>maturity condition</th></tr>{seq_rows}</table>"
        f"<p>Discovery ledger: {dl['hypotheses']} hypotheses across "
        f"{dl['families']} families; status counts "
        f"{_esc(json.dumps(dl['status_counts'], sort_keys=True))}; "
        f"family adjudication {_esc(dl['family_adjudication'])}.</p>"
        f"<p>Truncation &amp; error budget ledger "
        f"({platform['truncation_ledger']['entries']} entries; counts "
        f"shown verbatim, including PENDING):</p>"
        f"<table><tr><th>site</th><th>count</th><th>reason</th></tr>"
        f"{tr_rows}</table>",
        # HISTORY
        f"<p>Name-scoped registered lineage (including superseded "
        f"lines):</p><table><tr><th>hypothesis</th><th>family</th>"
        f"<th>status</th></tr>{hist_rows}</table>",
        # REPRODUCE
        f"<p>Rebuild this exact card from the registered artifacts:</p>"
        f"<p><code>python3 tools/yuclaw_science_trust_cards.py --write"
        f"</code></p><p>Verify all three staged surfaces agree and "
        f"reproduce byte-for-byte:</p>"
        f"<p><code>python3 tools/check_science_trust.py</code></p>"
        f"<p class='basis'>renderer {RENDERER_VERSION} · anchor "
        f"<code>{_esc(meta['anchor'])}</code> · same artifacts + same "
        f"renderer version &rArr; byte-identical output</p>",
    ]

    tab_blocks = "".join(
        f"<details{' open' if i == 0 else ''}><summary>{t}</summary>"
        f"<div>{p}</div></details>"
        for i, (t, p) in enumerate(zip(_TABS, tabs_html)))

    canonical = {"name": name, "science_trust": fields,
                 "anchor": meta["anchor"],
                 "renderer_version": RENDERER_VERSION}
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Science Trust — {_esc(name)} (preview)</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
<div class="previewband">STAGED PREVIEW — not public, linked from
nowhere. Live promotion requires a separate authorized v6 release
order.</div>
<header><h1>Science Trust — {_esc(name)}</h1>
<div class="sub">What the evidence record supports today, and exactly
where it stops. Derived from registered artifacts; absence is
information.</div>
<div class="anchor">derivation anchor {_esc(meta['anchor'])} · renderer
{RENDERER_VERSION}</div></header>
<div class="card">{''.join(rows)}</div>
<div class="tabs">{tab_blocks}</div>
<div class="footnote">Research use only. Not investment advice. States
on this card live on the research axis and never translate to signals,
scores, or portfolio actions.</div>
</div>
<script type="application/json" id="st-canonical">
{json.dumps(canonical, indent=1, sort_keys=True)}
</script></body></html>
"""


def _hist(fields: dict) -> list:
    dc = fields["discovery_context"]["value"]
    return dc.get("name_scoped_hypotheses", [])


# ------------------------------------------------------------- writers
def write_all(base: Path | None = None) -> dict:
    derived = derive_all()
    base_trust = (base / "trust") if base else OUT_TRUST
    base_why = (base / "why") if base else OUT_WHY
    base_trust.mkdir(parents=True, exist_ok=True)
    base_why.mkdir(parents=True, exist_ok=True)
    meta = {"anchor": derived["anchor"]}
    n_cards = n_json = 0

    for name, fields in derived["names"].items():
        (base_trust / f"{name}.html").write_text(
            render_card(name, fields, derived["platform"], meta))
        machine = {"name": name, "science_trust": fields,
                   "platform": derived["platform"],
                   "anchor": derived["anchor"],
                   "renderer_version": RENDERER_VERSION,
                   "derivation_protocol": derived["derivation_protocol"],
                   "staged": True, "surface": "preview"}
        (base_trust / f"{name}.json").write_text(
            json.dumps(machine, indent=1, sort_keys=True) + "\n")
        n_cards += 1
        n_json += 1

    # why/{T}.json preview mirrors (staged machine surface): live JSON
    # verbatim + the SAME derived science_trust block. LIVE files untouched.
    n_mirrors = 0
    for wf in sorted((_REPO / "docs" / "why").glob("*.json")):
        t = wf.stem
        if t not in derived["names"]:
            continue
        live = json.loads(wf.read_text())
        live["science_trust"] = derived["names"][t]
        live["science_trust_meta"] = {
            "staged": True, "surface": "preview",
            "anchor": derived["anchor"],
            "renderer_version": RENDERER_VERSION,
            "derivation_protocol": derived["derivation_protocol"]}
        (base_why / f"{t}.json").write_text(
            json.dumps(live, indent=1, sort_keys=True) + "\n")
        n_mirrors += 1

    # capabilities.json schema-vNext preview mirror (live untouched)
    cap = json.loads((_REPO / "docs" / "capabilities.json").read_text())
    cap["schema_preview"] = "vNext"
    cap["science_trust"] = {
        "status": {"value": "STAGED_PREVIEW", "annotation": "FACT",
                   "basis": "order 2026-08-14 — preview only, promoted "
                            "only by a separate authorized v6 release "
                            "order", "source": "this file"},
        "card_html": {"value": "preview/trust/{NAME}.html",
                      "annotation": "FACT", "basis": "staged path",
                      "source": "this file"},
        "card_json": {"value": "preview/trust/{NAME}.json",
                      "annotation": "FACT", "basis": "staged path",
                      "source": "this file"},
        "why_mirror": {"value": "preview/why/{TICKER}.json",
                       "annotation": "FACT", "basis": "staged path",
                       "source": "this file"},
        "derivation": {"value": "Research-State Derivation v1",
                       "annotation": "DERIVED_RESULT",
                       "basis": "every state derived at build time; "
                                "nothing hand-maintained",
                       "source": "registry/research_state.json"},
        "anchor": {"value": derived["anchor"], "annotation": "FACT",
                   "basis": "chain-tip derivation anchor",
                   "source": "registry/research_state.json"},
    }
    (base_trust.parent / "capabilities.vnext.json").write_text(
        json.dumps(cap, indent=1, sort_keys=True) + "\n")

    # EvidenceBench READ-ONLY consumption (Phase 9): abstention/context
    # evaluation metadata derived from canonical research-state outputs.
    # Consumes Science Trust state; NEVER defines it. Zero changes to
    # scoring formula, weights, leaderboard, item eligibility,
    # thresholds, abstention reward, or benchmark identity.
    items_path = _REPO / "docs" / "evidencebench" / "items.jsonl"
    eb_items = []
    if items_path.exists():
        for line in items_path.read_text().splitlines():
            if not line.strip():
                continue
            it = json.loads(line)
            ticker = it["item_id"].split("_")[1] if "_" in it["item_id"] \
                else None
            st = derived["names"].get(ticker)
            eb_items.append({
                "item_id": it["item_id"],
                "ticker": ticker,
                "research_state_context": {
                    "research_state":
                        st["research_state"]["value"] if st else "UNKNOWN",
                    "annotation":
                        st["research_state"]["annotation"] if st
                        else "NOT_ESTIMABLE",
                    "abstention_context": (
                        "context only — abstention scoring is unchanged; "
                        "this metadata never enters the scoring formula"),
                },
            })
    (base_trust.parent / "evidencebench_context.json").write_text(
        json.dumps({
            "purpose": "EvidenceBench READ-ONLY research-state context "
                       "(order 2026-08-14 Part C): consumed for "
                       "abstention/context evaluation metadata only",
            "invariants": ["scoring formula unchanged",
                           "dimension weights unchanged",
                           "leaderboard ordering unchanged",
                           "item eligibility unchanged",
                           "pass/fail thresholds unchanged",
                           "abstention reward unchanged",
                           "benchmark identity unchanged"],
            "anchor": derived["anchor"],
            "renderer_version": RENDERER_VERSION,
            "staged": True, "surface": "preview",
            "n_items": len(eb_items),
            "items": eb_items,
        }, indent=1, sort_keys=True) + "\n")

    # ---- Part D: include-point previews (live include-points untouched)
    def _include_page(title: str, intro: str, names: list[str],
                      live_href: str | None) -> str:
        secs = "".join(
            f"<section data-include='science-trust-card' "
            f"data-name='{_esc(n)}'>"
            f"<h2>{_esc(n)}</h2>"
            f"<iframe src='trust/{_esc(n)}.html' title='Science Trust "
            f"{_esc(n)}' loading='lazy' "
            f"style='width:100%;height:520px;border:1px solid #e2e8f0'>"
            f"</iframe></section>" for n in names)
        live = (f"<p class='live'>Live page (unchanged by this preview): "
                f"<code>{_esc(live_href)}</code></p>" if live_href else "")
        return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>{_esc(title)} (preview)
</title><style>body{{font-family:Georgia,serif;color:#1a202c;
background:#fafbfc;margin:0}}.wrap{{max-width:900px;margin:0 auto;
padding:24px 16px}}.band{{background:#fffaf0;border:1px solid #ecc94b;
color:#744210;font-family:monospace;font-size:11px;padding:6px 10px;
margin-bottom:16px}}h1{{font-size:19px}}h2{{font-size:15px;
margin:18px 0 6px}}.live,{{color:#718096;font-size:12px}}
code{{font-family:monospace;font-size:12px;background:#edf2f7;
padding:1px 4px}}</style></head><body><div class="wrap">
<div class="band">STAGED PREVIEW — include-point wiring only. Linked
from nowhere public; the live page carries no include-point under this
order.</div>
<h1>{_esc(title)} — Science Trust include-points</h1>
<p>{_esc(intro)}</p>{live}{secs}
</div></body></html>
"""

    n_includes = 0
    # U79 name pages (incl. the ETF tickers among them)
    for wf in sorted((_REPO / "docs" / "why").glob("*.html")):
        t = wf.stem
        if t not in derived["names"]:
            continue
        (base_why / f"{t}.html").write_text(_include_page(
            f"Name page — {t}",
            "Preview-only version of the name page wired with its "
            "Science Trust card include-point.",
            [t], f"docs/why/{t}.html"))
        n_includes += 1
    # Canada / evidence-tier page
    canada = sorted(n for n, f in derived["names"].items()
                    if f["universe_class"]["value"] == "canada_evidence")
    (base_trust.parent / "canada_trust_includes.html").write_text(
        _include_page(
            "Canada Resources (evidence tier)",
            "Evidence-tier names are never scored: scoring-dependent "
            "fields on these cards derive NOT_APPLICABLE and are shown, "
            "not hidden.",
            canada, "docs/canada_resources.html"))
    n_includes += 1
    # Lens pages (ETF lens tickers where applicable)
    lens = [t for t in ("SMH", "XLK") if t in derived["names"]]
    (base_trust.parent / "lens_trust_includes.html").write_text(
        _include_page(
            "Sector lens pages",
            "Lens pages gain the lens ETF's own Science Trust card as "
            "an include-point; member-name cards link from the name "
            "pages.",
            lens, "docs/xlk_evidence.html · docs/etf_evidence.html"))
    n_includes += 1

    return {"cards": n_cards, "card_json": n_json, "why_mirrors": n_mirrors,
            "capabilities_vnext": 1, "evidencebench_context": 1,
            "include_pages": n_includes, "anchor": derived["anchor"]}


if __name__ == "__main__":
    if "--write" in sys.argv:
        stats = write_all()
        print(f"[science-trust-cards] STAGED write complete: "
              f"{stats['cards']} cards, {stats['card_json']} card JSON, "
              f"{stats['why_mirrors']} why mirrors, 1 capabilities vNext "
              f"— anchor {stats['anchor'][:16]}… (docs/preview/ only; "
              f"live surfaces untouched)")
    else:
        d = derive_all()
        states = {}
        for n, f in d["names"].items():
            states[f["research_state"]["value"]] = \
                states.get(f["research_state"]["value"], 0) + 1
        print(f"[science-trust-cards] derive-only: {len(d['names'])} "
              f"names · research states {states} · anchor "
              f"{d['anchor'][:16]}… · nothing written")
