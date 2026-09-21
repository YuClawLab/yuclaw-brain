"""
EvidenceBench page (docs/evidencebench.html) — groundedness, not
prediction. How to run, the scoring rule (abstention outscores
fabrication by construction), the honest leaderboard with our
self-evaluation row loudly labeled, and the dataset pointer (derived
events + excerpts + keys; no OHLCV — the export rule).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from v3.web.useful_blocks import (footer_stamp_html, build_footer, freshness_strip, site_header_html)

OUT = _REPO / "docs" / "evidencebench.html"
BENCH_DIR = _REPO / "docs" / "evidencebench"
LINEAGE = BENCH_DIR / "lineage.json"
ABSTAIN = "cannot verify from the evidence provided"


def lineage(meta: dict, ident: dict) -> dict:
    """The published item sets, oldest first (8.0.1 C08). The benchmark is REGENERATED every week over a trailing window, so
    consecutive releases are different item sets with different counts — not revisions of one set. Entries before this file
    existed were taken from the repository history of meta.json (each names its publishing commit); a release is appended the
    first time its canonical hash is seen. Nothing older than the repository's own history is asserted."""
    try:
        lin = json.loads(LINEAGE.read_text())
    except Exception:                                                     # noqa: BLE001
        lin = {"record": "yuclaw-evidencebench-lineage/1", "releases": []}
    lin.update({"rule": "one item set per weekly generation; window = trailing 7 days of accepted post-cutoff evidence; templates T1/T2 from events with an accession, T3 from up to 150 signal labels; "
                        "items sorted by item_id; item_set_hash = sha256 of the canonical JSON of that sorted list (sort_keys) — NOT the sha256 of the items.jsonl file",
                "limits": "counts differ from week to week because the evidence volume of the window differs; no item is carried over or migrated between releases; "
                          "releases older than the first entry are not recorded here"})
    for r in lin["releases"]:                                             # a release taken from the repository history gains the file digest once it is the one on disk
        if r.get("item_set_hash") == meta.get("item_set_hash") and not r.get("items_sha256"):
            r["items_sha256"] = ident.get("items_sha256")
    if meta.get("item_set_hash") and all(r.get("item_set_hash") != meta["item_set_hash"] for r in lin["releases"]):
        lin["releases"].append({"generated": meta.get("generated"), "version": meta.get("version"), "protocol_id": meta.get("protocol_id"), "window": meta.get("window"), "n_items": meta.get("n_items"),
                                "item_set_hash": meta["item_set_hash"], "items_sha256": ident.get("items_sha256"), "source": "generator (recorded at page build)"})
    lin["releases"].sort(key=lambda r: r.get("generated") or "")
    LINEAGE.write_text(json.dumps(lin, indent=1) + "\n")
    return lin


def echo_control(items_path: Path) -> dict:
    """A NEGATIVE control computed on THIS release's items with the packaged scorer: every answer is the question itself.
    It shows what each rubric does with an answer that contains no fact; it validates nothing."""
    from v3.bench import evidencebench as B
    ident = B.items_identity(items_path); items = B.load_items(items_path); preds = {i["item_id"]: i["question"] for i in items}; out = {"n_items": len(items), **ident}
    for rubric in ("v1", "v2"):
        r = B.score(items, preds, rubric=rubric, label="QUESTION_ECHO_CONTROL", items_sha256=ident["items_sha256"], item_set_hash_value=ident["item_set_hash"])
        out[rubric] = {"T1": r["per_type"].get("T1"), "aggregate": r["aggregate"]}
    return out


def _bench_data_through() -> str:
    """The benchmark page's own artifact date: the item set's generation date (QA-G3), never the signal date."""
    try:
        return json.loads((_REPO / "docs" / "evidencebench" / "meta.json").read_text())["generated"][:10]
    except Exception:                                                     # noqa: BLE001
        return "unavailable"


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta = json.loads((_REPO / "docs" / "evidencebench" /
                       "meta.json").read_text())
    lb = json.loads((_REPO / "docs" / "evidencebench" /
                     "leaderboard.json").read_text())
    header = site_header_html(subtitle="EvidenceBench")
    ctl = echo_control(BENCH_DIR / "items.jsonl"); lin = lineage(meta, ctl)
    lin_rows = "".join(f"<tr><td class='mono'>{escape(str(r.get('generated'))[:10])}</td><td class='mono'>{r.get('n_items')}</td><td class='mono'>{escape(str(r.get('item_set_hash'))[:16])}…</td>"
                       f"<td class='muted'>{escape(str(r.get('source')))}</td></tr>" for r in reversed(lin["releases"][-12:]))
    rows = "".join(
        f"<tr><td>{escape(r['label'])}</td>"
        f"<td class='mono'>{r['aggregate']}</td>"
        f"<td class='mono'>{escape(json.dumps(r['per_type']))}</td>"
        f"<td class='mono'>{r['abstentions']}</td></tr>"
        for r in lb["rows"])
    OUT.write_text(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EvidenceBench — financial groundedness, contamination-resistant</title>
<meta name="description" content="A weekly-regenerated groundedness benchmark from post-cutoff SEC evidence. Abstention outscores fabrication by construction. Groundedness, not prediction. Research only.">
<style>
 *{{margin:0;padding:0;box-sizing:border-box}}
 body{{background:#0B0E14;font-family:Inter,system-ui,sans-serif;color:#E2E8F0;line-height:1.6}}
 .container{{max-width:960px;margin:0 auto;padding:24px}}
 h1{{font-size:24px;color:#FFF}} h2{{font-size:17px;color:#FFF;margin:22px 0 10px}}
 .card{{background:#151A23;border:1px solid #1E232D;border-radius:12px;padding:22px;margin-bottom:16px}}
 .amber{{background:#1E232D;border-left:3px solid #FBA94B;border-radius:6px;padding:11px 16px;font-size:12px;color:#A0AEC0;margin:14px 0}}
 .amber strong{{color:#FBA94B}}
 .mono{{font-family:'JetBrains Mono',monospace;font-size:12px}}
 table{{width:100%;border-collapse:collapse;margin:10px 0}}
 td,th{{padding:9px 12px;border-bottom:1px solid #1E232D;font-size:13px;text-align:left}}
 th{{color:#718096;font-size:11px;text-transform:uppercase}}
 code{{background:#1E232D;padding:2px 6px;border-radius:4px;font-family:'JetBrains Mono',monospace;font-size:12px;color:#00E676}}
 .muted{{color:#718096;font-size:12px}}
 .wait{{border:1px dashed #00E67650;border-radius:10px;padding:16px;text-align:center;color:#00E676;font-size:14px;margin-top:8px}}
</style>
</head>
<body><div class="container">
{header}
<div class="card">
  <h1>EvidenceBench v{meta['version']} — groundedness, not prediction</h1>
  <p style="margin-top:8px;color:#A0AEC0">Can your model answer questions about real SEC disclosures with
  verifiable grounding — and abstain when it cannot? Items regenerate <strong style="color:#E2E8F0">weekly
  from the newest post-cutoff evidence</strong>, so no static answer key can have been memorized from a
  training corpus: the answers did not exist at training time. That property is mechanical, not aspirational
  — keys ship openly.</p>
  <p class="muted" style="margin-top:8px">Current release: {meta['n_items']} items · generated {escape(str(meta['generated'])[:10])} ·
  canonical item-set hash <span class="mono">{meta['item_set_hash'][:16]}…</span> ·
  generation spec registered as protocol <span class="mono">{meta['protocol_id']}</span> ·
  window: {escape(meta['window'])}</p>
</div>
<div class="amber"><strong>Research and education only — not investment advice.</strong>
EvidenceBench measures groundedness against disclosed evidence; nothing here measures or implies future
returns. Signal labels are research classifications, not buy/sell recommendations.</div>

<div class="card"><h2>How to run (current: the scorer in the installed package)</h2>
<p style="font-size:13.5px">The scorer ships inside the package (since 7.0.1); nothing has to be cloned. It is standard-library only and reads exactly the item file you give it:</p>
<pre>pip install yuclaw
curl -sO https://yuclaw.ca/evidencebench/items.jsonl
curl -sO https://yuclaw.ca/evidencebench/meta.json
yuclaw evidencebench score predictions.json "your-model-name" --items items.jsonl --rubric v1 \\
       --expect-item-set-hash {meta['item_set_hash']}</pre>
<p style="font-size:13.5px"><code>predictions.json</code> maps <code>item_id</code> → answer string; the literal abstention string is
"{ABSTAIN}". With <code>meta.json</code> beside the items the identity is checked automatically; a mismatch is a refusal (exit 3), never a score.</p>
<p style="font-size:13px;color:#A0AEC0"><strong>Historical reproduction only:</strong> release 7.0.0 did not ship the scorer; its numbers reproduce from a pinned checkout
(<code>git clone --branch v7.0.0 --depth 1 https://github.com/YuClawLab/yuclaw-brain.git</code>, then
<code>python3 -m tools.yuclaw_evidencebench score /absolute/path/predictions.json "name"</code> from its root, against the item file of that checkout).
That recipe is kept for the record and is not the current instruction.</p>
</div>

<div class="card"><h2>What exists, stated separately</h2>
<table><tbody>
<tr><th scope="row">Code</th><td>The scorer is in the installed package: <code>yuclaw evidencebench score … --rubric v1|v2</code>.</td></tr>
<tr><th scope="row">Rubric v1</th><td>The released rule, kept byte-identical for reproduction. <strong>Known flaw (disclosed, preserved):</strong> T1 credit is lexical — token overlap ≥ 0.5 with the keyed
excerpt <em>or</em> the keyed accession appearing in the answer — and T1 questions quote the accession, so an answer that only repeats the question earns T1 credit. v1 numbers reproduce a flawed rubric; they do not measure groundedness.</td></tr>
<tr><th scope="row">Rubric v2</th><td><strong>Candidate</strong> — implemented and contract-tested in the package; <strong>not registered</strong>. A structured-fact rule (accession + event type + keyed numeric
facts, question tokens excluded, contradictions score 0): bounded lexical/numeric matching, not semantic verification.</td></tr>
<tr><th scope="row">Item set</th><td>One published set: this week's v{meta['version']} items, generated for v1. <strong>No v2 item set exists</strong>; generating one needs a prospective protocol registration that has not been adopted.</td></tr>
<tr><th scope="row">Registration</th><td>The v{meta['version']} generation spec is registered as protocol <span class="mono">{meta['protocol_id']}</span>. Rubric v2 is not registered.</td></tr>
<tr><th scope="row">Validation</th><td><strong>None is claimed.</strong> The package's contract tests check the rules on constructed cases (grounded answers, wrong numbers, contradictions, missing facts, abstention). There is no pooled leaderboard across versions and no external validation.</td></tr>
</tbody></table>
<p style="font-size:13px;color:#A0AEC0;margin-top:10px"><strong>Negative control on this release</strong> (computed at page build with the packaged scorer, on the {ctl['n_items']} items identified below;
every answer is the question itself): rubric v1 gives T1 = {ctl['v1']['T1']} and aggregate {ctl['v1']['aggregate']}; rubric v2 gives T1 = {ctl['v2']['T1']} and aggregate {ctl['v2']['aggregate']}.
It shows v1's disclosed flaw and that v2 rejects a question echo; it is one control, not a validation of v2.</p>
</div>

<div class="card"><h2>Item-set identity and lineage</h2>
<p style="font-size:13px">This release: <strong>{meta['n_items']} items</strong>, generated {escape(str(meta['generated'])[:10])}, window: {escape(meta['window'])}.
Two different digests identify it — do not compare one with the other:</p>
<table><tbody>
<tr><th scope="row">Canonical item-set hash</th><td class="mono">{meta['item_set_hash']}</td><td class="muted">sha256 of the canonical JSON of the items sorted by id (<code>item_set_hash</code> in meta.json; <code>--expect-item-set-hash</code>)</td></tr>
<tr><th scope="row">Raw file SHA-256</th><td class="mono">{ctl['items_sha256']}</td><td class="muted">sha256 of the bytes of items.jsonl as downloaded (<code>--expect-items-sha256</code>)</td></tr>
</tbody></table>
<p style="font-size:13px;margin-top:10px">The item set is <strong>regenerated every week</strong> from the evidence of the trailing window, so each release is a different set and the
count moves with that week's evidence volume; nothing is migrated from one release to the next. Published releases
(<a href="evidencebench/lineage.json" style="color:#00E676">lineage.json</a>; earlier entries come from the repository history of meta.json and name their commit):</p>
<table><thead><tr><th>Generated</th><th>Items</th><th>Canonical hash</th><th>Recorded from</th></tr></thead><tbody>{lin_rows}</tbody></table>
</div>

<div class="card"><h2>Leaderboard</h2>
<table><thead><tr><th>System</th><th>Aggregate</th><th>Per-type</th><th>Abstentions</th></tr></thead>
<tbody>{rows}</tbody></table>
<div class="wait">this row is waiting for your model</div>
<p class="muted" style="margin-top:8px">The only current row is our own extraction stack scored against its
own corpus — a format demonstration, loudly labeled self-evaluation; nothing is claimed by it.</p></div>

<div class="card"><h2>Dataset</h2>
<p style="font-size:13px">Items + keys: <a href="evidencebench/items.jsonl" style="color:#00E676">items.jsonl</a> (JSONL — one item per line: <code>{{item_id, template, question, key}}</code>)
· <a href="evidencebench/meta.json" style="color:#00E676">meta.json</a>. Under the export rule: derived
events, verified excerpts, and keys only — no raw vendor OHLCV is published. Weekly snapshots are tagged in
the repository (dataset citability: see CITATION.cff at the repo root and the
<a href="replication.html" style="color:#00E676">replication page</a>).</p></div>

<div class="amber"><strong>Research and education only — not investment advice.</strong>
Past results — in-sample or forward-tracked — do not predict future performance.</div>
<p class="muted">YUCLAW · <a href="index.html" style="color:#A0AEC0">Home</a> ·
<a href="for_ai_builders.html" style="color:#A0AEC0">For AI builders</a></p>
{footer_stamp_html(freshness_strip(_bench_data_through()))}
{build_footer()}
</div></body></html>""")
    print(f"[render_evidencebench] {meta['n_items']} items · "
          f"{len(lb['rows'])} leaderboard row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
