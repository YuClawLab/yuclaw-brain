#!/usr/bin/env python3
"""Stage research-contract corrections from public snapshots, without rewriting history.

Does not query the database, change prices/statistical results, rebuild release
packets, or claim that missing historical confidence/anchor data exist.
Run after public generators; safe to repeat on the same inputs.
"""
from pathlib import Path
import hashlib
import json
import re
import sys
from html import escape

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from v3.evidence.research_contract import AS_OF_RECIPE, EVENT_HASH_SCOPE, LAB_LIMITATIONS, REPLAY_SCOPE
from v3.evidence.research_summary import denominators
from v3.evidence.claim_support import assess
from v3.web import lab_prose as L
from v3.web.useful_blocks import responsive_research_page
from tools.check_viewport import routes

DOCS = ROOT / 'docs'
MARK = 'RESEARCH-CONTRACT'


def put(html, content, before=None):
    block = f'<!-- {MARK} BEGIN -->{content}<!-- {MARK} END -->'
    pat = re.compile(f'<!-- {MARK} BEGIN -->.*?<!-- {MARK} END -->\n?', re.S)
    html = pat.sub('', html)
    if before and before in html:
        return html.replace(before, block + '\n' + before, 1)
    return html.replace('</body>', block + '\n</body>')


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + '\n')


def card(title, paragraphs):
    return '<section style="margin:24px auto;padding:20px;max-width:1000px;border:1px solid #64748b;border-radius:8px"><h2>' + escape(title) + '</h2>' + ''.join('<p>' + escape(p) + '</p>' for p in paragraphs) + '</section>'


def main():
    manifest = json.loads((DOCS / 'why/history_manifest.json').read_text())
    for tk, entry in manifest['files'].items():
        raw = (DOCS / entry['path']).read_bytes()
        hist = json.loads(raw)
        if hashlib.sha256(raw).hexdigest() != entry['sha256'] or len(raw) != entry['bytes'] or len(hist['evidence_objects']) != entry['count'] or hist['build_id'] != manifest['build_id']:
            raise ValueError(f'{tk}: mixed or corrupted history')
        path = DOCS / 'why' / f'{tk.replace(".", "-")}.json'
        doc = json.loads(path.read_text())
        if doc['build_id'] != manifest['build_id']:
            raise ValueError(f'{tk}: mixed preview build')
        doc['as_of_recipe'], doc['verify'] = AS_OF_RECIPE, EVENT_HASH_SCOPE
        d = denominators(hist['evidence_objects'], hist['collection']['corpus_end'])
        doc['descriptive_denominators_90d'] = d
        doc.setdefault('component_anatomy', {'status': 'INCOMPLETE', 'reason': 'This historical public snapshot does not expose stored per-component confidences or historical weights; they have not been reconstructed or assumed.'})
        doc['excerpt_comparison_checks'] = [{'source_hash': o['source_hash'], 'scope': 'published excerpt only; not a whole-filing or independent truth check', **assess(o['evidence_type'], o['excerpt'])} for o in doc['evidence_objects'] if o['evidence_type'] in ('EARNINGS_BEAT', 'EARNINGS_MISS')]
        write_json(path, doc)
        hp = path.with_suffix('.html')
        if hp.exists():
            paras = [f"In the 90 days ending {d['window_end_inclusive']}: {d['event_objects']} event objects from {d['distinct_accessions']} distinct accessions; {d['objects_without_accession']} objects lack an accession. These are descriptive counts, not independent observations.",
                     f"Composite reconstruction: {doc['component_anatomy']['status']}. Confidence inputs are not calibrated probabilities. Current weights alone cannot establish historical contributions. C4 remains disclosed as frozen from 2026-05-18.", EVENT_HASH_SCOPE]
            for check in doc['excerpt_comparison_checks']:
                paras.append(f"Excerpt comparison {check['source_hash'][:12]}: {check['status']} — {check['reason']} Scope: published excerpt only.")
            # Why pages declare <base href="../">, so links use docs-root paths.
            hp.write_text(put(hp.read_text(), card('Research interpretation and limits', paras), before='<div class="card"><h2>Evidence coverage'))

    path = DOCS / 'capabilities.json'
    doc = json.loads(path.read_text()); doc['as_of_recipe'] = AS_OF_RECIPE
    write_json(path, doc)
    path = DOCS / 'evidence/verify.json'
    doc = json.loads(path.read_text())
    doc.update(object_type='signal_snapshot', event_hash_proof='NOT_AVAILABLE: this endpoint does not authenticate event source_hash values',
               canonicalization='sha256(json.dumps(entries, sort_keys=True).encode(utf-8)); list order is preserved; default JSON separators',
               external_provenance='UNVERIFIED without an independently obtained ledger reference')
    doc['how'][1] = 'recompute sha256(json.dumps(entries, sort_keys=True).encode()) with list order preserved; compare root_sha256'
    write_json(path, doc)

    # General copy corrections; leave timestamps and measured values intact.
    replacements = {
        'Every signal traces to a real SEC filing.': 'Accepted filing events link to SEC sources. Composite classifications also use market inputs; some names have no direct filing evidence in our corpus.',
        'every signal traced to its SEC filings': 'filing events linked to SEC sources, with separate signal verification',
        'Exit 0 = every statistic and evidence-ledger root reproduced.': 'Exit 0 = core tables reproduced and bundled ledger consistency checked; external provenance is separate.',
        'Replay works — one command reproduces every Lab statistic and evidence-ledger root from published data': 'Replay checks core expected tables and bundled ledger consistency; external provenance is separate',
        'stdlib script reproduces every statistic + evidence-ledger roots': 'stdlib script checks core expected tables and bundled ledger consistency',
        'recompute every statistic': 'recompute the core expected statistical tables',
        'a SHA-256 anchored in a public daily ledger': 'a stored event-record SHA-256 (public event inclusion verification is unavailable; the daily ledger covers signal snapshots)',
        'SourceLock-verified — it must locate verbatim in the filing text or the event is rejected.': 'SourceLock checks source occurrence, including normalization and a lexical-similarity fallback; this does not establish the earnings comparison.',
        'Verified quote (SourceLock):': 'Source-checked excerpt (SourceLock):',
        'same parametric look-ahead disclosure': 'same historical-reconstruction limitations',
    }
    for path in DOCS.glob('*.html'):
        if path.name.startswith('YUCLAW_') and '_v5.' in path.name:
            continue  # immutable earlier guide editions
        html = path.read_text()
        for old, new in replacements.items():
            html = html.replace(old, new)
        if path.name == 'validation_lab.html':
            bundle = json.loads((DOCS / 'replay/lab_replay_bundle.json').read_text())
            html = L.restage(html, bundle['expected'], L.bundle_identity(bundle))
            # Compare the displayed qualified-pool and universe numbers, not a
            # hard-coded direction. Do not derive a new return statistic.
            pat = re.compile(r'(<strong style="color:#E2E8F0">)(?:trails|exceeds|matches) the universe(?: at displayed precision)?(</strong>\s*\(([+-]?[\d.]+)% vs ([+-]?[\d.]+)%\)\.)')
            html = pat.sub(lambda m: m[1] + L.comparative_return(float(m[3])/100, float(m[4])/100) + m[2], html)
            html = put(html, card('Verification scope and statistical limits', [REPLAY_SCOPE] + LAB_LIMITATIONS), before='<div class="panel">')
        if path.name == 'trace_su.html':
            html = put(html, card('Earnings comparison correction', ['The displayed profitability passage does not establish an expectations benchmark for the historical EARNINGS_BEAT classification. That comparison is UNSUPPORTED by the displayed passage. The original event is retained; quotation matching, arithmetic and earnings surprise are separate checks.', EVENT_HASH_SCOPE]), before='<h1 ')
        path.write_text(html)

    for rel in routes()[0]:
        path = DOCS / rel
        html = path.read_text()
        path.write_text(responsive_research_page(html))

    # Existing published packets are immutable evidence: attach corrections by
    # exact archive hash instead of changing their historical metadata in place.
    correction_path = DOCS / 'packets/corrections.json'
    if not correction_path.exists():
        packet = DOCS / 'packets/yuclaw_validation_lab_packet.zip'
        archives = {packet.name: hashlib.sha256(packet.read_bytes()).hexdigest()}
        write_json(correction_path, {'schema': 'packet-limitations-correction/1', 'issued': '2026-10-13', 'applies_to_sha256': archives, 'lab_limitations': LAB_LIMITATIONS, 'replay_scope': REPLAY_SCOPE, 'canonical_lookahead': '/methodology/lookahead_statement.txt', 'note': 'Correction of interpretation for this exact historical Lab packet; original archives and measured values are retained.'})
    # Later nightly packets must not replace the historical correction's target.
    print(f'Staged contracts for {len(manifest["files"])} names; historical bundles, ledgers and archives unchanged.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
