"""Offline point-in-time export from a complete, manifest-bound public history."""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import timezone
from pathlib import Path

from v3.evidence.history import as_of_query, _as_of_bound
from v3.evidence.research_contract import EVENT_HASH_SCOPE
from v3.evidence.research_summary import denominators


def prepare(history_bytes, manifest_bytes, ticker, as_of):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError('duplicate JSON key: ' + key)
            obj[key] = value
        return obj
    def invalid_constant(value):
        raise ValueError('non-finite JSON number: ' + value)
    history = json.loads(history_bytes, object_pairs_hook=unique, parse_constant=invalid_constant)
    manifest = json.loads(manifest_bytes, object_pairs_hook=unique, parse_constant=invalid_constant)
    if not isinstance(history, dict) or not isinstance(manifest, dict):
        raise ValueError('history and manifest must be JSON objects')
    ticker = ticker.upper()
    entry = manifest['files'][ticker]
    if history.get('schema') != 'WhyHistory.v1' or manifest.get('schema') != 'why-history-manifest/1':
        raise ValueError('unsupported history/manifest schema')
    if history['ticker'] != ticker or history['build_id'] != manifest['build_id'] or history['collection']['build_id'] != manifest['build_id']:
        raise ValueError('mixed ticker/build identities')
    rows = history['evidence_objects']
    if entry['sha256'] != hashlib.sha256(history_bytes).hexdigest() or entry['bytes'] != len(history_bytes) or entry['count'] != len(rows):
        raise ValueError('history digest, length or count does not match manifest')
    if any(row['ticker'] != ticker for row in rows):
        raise ValueError('history contains another ticker')
    if history['collection'].get('completeness') != 'COMPLETE':
        raise ValueError('PREVIEW is not a complete research source')
    result = as_of_query(history['collection'], rows, as_of)
    if result['status'] not in ('COMPLETE', 'COMPLETE_EMPTY'):
        raise ValueError(result['status'] + ': ' + result['reason'])
    selected = result['objects']
    fields = ['ticker', 'evidence_type', 'filing_date', 'accession_number', 'excerpt', 'source_hash', 'available_as_of', 'protocol_id']
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fields, lineterminator='\n')
    writer.writeheader()
    # Neutralize spreadsheet formula execution in CSV; JSON preserves exact text.
    for row in selected:
        writer.writerow({k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v)
                         for k in fields for v in [row.get(k)]})
    dump = lambda x: (json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    metadata = {'schema': 'research-export/1', 'ticker': ticker, 'as_of_utc': _as_of_bound(as_of).astimezone(timezone.utc).isoformat(),
                'status': result['status'], 'build_id': history['build_id'], 'row_count': len(selected),
                'history_sha256': entry['sha256'], 'source_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
                'external_authenticity': 'UNVERIFIED: file consistency does not independently authenticate the manifest',
                'hash_scope': EVENT_HASH_SCOPE, 'denominators_90d': denominators(selected, _as_of_bound(as_of).astimezone(timezone.utc).isoformat()),
                'unit': 'accepted event object, not independent filing or firm',
                'selection': 'available_as_of <= UTC bound, complete only for the declared corpus/build',
                'source_corpus_start': history['collection'].get('corpus_start'),
                'source_corpus_end': history['collection'].get('corpus_end')}
    dictionary = {'fields': {k: {'nullable': k in ('filing_date', 'accession_number', 'protocol_id')} for k in fields},
                  'available_as_of': 'Recorded availability, not filing date; ingestion may be later.',
                  'filing_date': 'Source publication date; not a point-in-time availability substitute.',
                  'excerpt': 'Published excerpt may be truncated; not the entire source document.',
                  'csv': 'UTF-8; null becomes an empty cell. Leading formula-like text is prefixed with an apostrophe. Use JSON for exact values.',
                  'source_hash': EVENT_HASH_SCOPE}
    files = {'events.json': dump(selected), 'events.csv': output.getvalue().encode(),
             'data_dictionary.json': dump(dictionary), 'source_history.json': history_bytes,
             'source_manifest.json': manifest_bytes}
    metadata['files'] = {name: {'sha256': hashlib.sha256(b).hexdigest(), 'bytes': len(b)} for name, b in files.items()}
    files['manifest.json'] = dump(metadata)
    return files, metadata


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--history', required=True, type=Path)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--ticker', required=True)
    p.add_argument('--as-of', required=True)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args(argv)
    try:
        files, metadata = prepare(a.history.read_bytes(), a.manifest.read_bytes(), a.ticker, a.as_of)
        a.out.mkdir(parents=True, exist_ok=False)
        for name, content in files.items():
            (a.out / name).write_bytes(content)
    except (ValueError, KeyError, TypeError, OSError, AttributeError) as exc:
        print('EXPORT REFUSED: ' + str(exc), file=sys.stderr)
        return 1
    print(f"{metadata['status']}: {metadata['row_count']} event objects; manifest: {a.out / 'manifest.json'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
