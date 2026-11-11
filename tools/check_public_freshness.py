#!/usr/bin/env python3
"""Observe served bytes, never local mtimes. No messages or repairs are sent.

The scheduled pipeline runs weekdays at 17:00 America/Edmonton. A two-hour
completion allowance covers the existing build/deploy limits. No-data days
still require a successful publication; historical research dates need not move.
"""
from __future__ import annotations
import argparse
import concurrent.futures
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v3.lab.replay_check import ANALYSIS_ZONE

BASE = 'https://yuclaw.ca/'
PAGES = ('index.html', 'validation.html', 'validation_lab.html', 'etf_evidence.html',
         'xlk_evidence.html', 'canada_resources.html', 'todays_evidence.html',
         'trace_su.html', 'replication.html', 'lane.html', 'signal_review.html',
         'explorer.html', 'sectors.html', 'tour.html', 'methodology.html',
         'for_ai_builders.html', 'evidence_scoreboard.html', 'evidencebench.html',
         'weekly_note.html', 'why/AAPL.html')
JSON_CLOCKS = {'coverage.json': 'as_of', 'explorer_data.json': 'generated',
               'why/history_manifest.json': 'generated',
               'evidence/scoreboard_research.json': 'cutoff',
               'receipts/scoreboard.json': 'source_timestamp'}

def expected_after(now):
    local = now.astimezone(ANALYSIS_ZONE)
    for offset in range(8):
        day = local - timedelta(days=offset)
        due = day.replace(hour=17, minute=0, second=0, microsecond=0)
        if due.weekday() < 5 and due + timedelta(hours=2) <= local:
            return due.astimezone(timezone.utc)
    raise ValueError('no scheduled build found')

def parse_stamp(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('timestamp has no timezone')
    return stamp.astimezone(timezone.utc)

def inspect(rel, body, now, required):
    if rel in JSON_CLOCKS:
        doc = json.loads(body)
        value = (doc.get('research', {}) if rel == 'evidence/scoreboard_research.json' else doc).get(JSON_CLOCKS[rel])
        # coverage's public projection places its clock in identity.
        if value is None and rel == 'coverage.json':
            value = doc.get('identity', {}).get('as_of')
        stamp = parse_stamp(value)
    else:
        text = body.decode('utf-8')
        matches = re.findall(r'<footer\b[^>]*class=["\']buildinfo["\'][^>]*>\s*build (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC', text)
        if len(matches) != 1:
            raise ValueError('expected exactly one generated build footer')
        stamp = datetime.strptime(matches[0], '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc)
    if stamp > now + timedelta(minutes=5):
        raise ValueError('build timestamp is in the future')
    if stamp < required:
        raise ValueError(f'stale: served build {stamp.isoformat()}, required after {required.isoformat()}')
    return stamp.isoformat()

def check_one(rel, now, required, docs=None):
    row = {'path': rel, 'status': 'FAILED'}
    try:
        request = urllib.request.Request(BASE + rel, headers={
            'User-Agent': 'YUCLAW-public-freshness/1', 'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status != 200 or response.geturl() != BASE + rel:
                raise ValueError('unexpected HTTP status or destination')
            body = response.read(2_000_001)
        if len(body) > 2_000_000:
            raise ValueError('response exceeds bound')
        row['built_at'] = inspect(rel, body, now, required)
        row['sha256'] = hashlib.sha256(body).hexdigest()
        if docs is not None:
            local = (docs / rel).read_bytes()
            if local != body:
                raise ValueError('served bytes differ from the generated build')
        row['status'] = 'OK'
    except Exception as exc:
        row['error'] = str(exc)[:500]
    return row

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--against-build', type=Path)
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    required = expected_after(now)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        rows = list(pool.map(lambda p: check_one(p, now, required, a.against_build),
                             (*PAGES, *JSON_CLOCKS)))
    ok = all(r['status'] == 'OK' for r in rows)
    report = {'schema': 'public-site-health/1', 'observed_at': now.isoformat(),
              'required_build_after': required.isoformat(), 'status': 'OK' if ok else 'FAILED',
              'checks': rows}
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        temporary = a.out.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(a.out)
    print('[public-site-health] ' + report['status'] + f': {sum(r["status"] == "OK" for r in rows)}/{len(rows)} served artifacts current')
    for row in rows:
        if row['status'] != 'OK':
            print('  ' + row['path'] + ': ' + row['error'])
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
