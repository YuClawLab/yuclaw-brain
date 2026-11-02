"""Read-only research view over published artifacts. No private ledger or model inputs.

All 90-day counts use one UTC cutoff. A COMPLETE history must match its manifest
(hash, length, count and build), cover the whole window, and reconcile to coverage.
Invalid/missing histories are unavailable, never a measured zero.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import urlparse

NAMES = {'AAPL':'Apple','MSFT':'Microsoft','AMZN':'Amazon','GOOGL':'Alphabet','META':'Meta Platforms',
         'NVDA':'NVIDIA','TSLA':'Tesla','AMD':'Advanced Micro Devices','XOM':'ExxonMobil','CVX':'Chevron',
         'COP':'ConocoPhillips','SLB':'SLB','PSX':'Phillips 66','DELL':'Dell Technologies','INTC':'Intel',
         'MU':'Micron Technology','ARM':'Arm','MRVL':'Marvell Technology','HPE':'Hewlett Packard Enterprise',
         'AMAT':'Applied Materials','LRCX':'Lam Research','JPM':'JPMorgan Chase','BAC':'Bank of America',
         'GS':'Goldman Sachs','MS':'Morgan Stanley','WFC':'Wells Fargo','C':'Citigroup','AXP':'American Express',
         'V':'Visa','MA':'Mastercard','UNH':'UnitedHealth Group','JNJ':'Johnson & Johnson',
         'PFE':'Pfizer','MRK':'Merck','ABBV':'AbbVie','LLY':'Eli Lilly','TMO':'Thermo Fisher Scientific',
         'DHR':'Danaher','ABT':'Abbott','BMY':'Bristol Myers Squibb','PG':'Procter & Gamble','KO':'Coca-Cola',
         'PEP':'PepsiCo','WMT':'Walmart','COST':'Costco','CRCL':'Circle','RKLB':'Rocket Lab','LUNR':'Intuitive Machines'}
FUND_SECTORS = {'Sector ETF','Broad ETF'}


def require(condition):
    if not condition:
        raise ValueError("Inconsistent public artifact")


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace('Z','+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone required')
    return result.astimezone(timezone.utc)


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def source_links(page: Path) -> dict:
    """Reuse published source links; accession prefixes are NOT issuer CIKs."""
    if not page.is_file():
        return {}
    result = {}
    for href in re.findall(r'href=[\'\"]([^\'\"]+)', page.read_text(encoding='utf-8')):
        href = unescape(href)
        u = urlparse(href)
        m = re.search(r'/Archives/edgar/data/\d+/(\d{18})/', u.path)
        if u.scheme == 'https' and u.hostname == 'www.sec.gov' and m:
            result[m[1]] = href
    return result


def load_research(docs: Path) -> dict:
    try:
        coverage = read(docs/'coverage.json')
        explorer = read(docs/'explorer_data.json')
        manifest = read(docs/'why/history_manifest.json')
        cutoff = utc(coverage['as_of'])
        start = cutoff - timedelta(days=90)
        require(coverage['schema'] == 'coverage/1' and coverage['basis']['window_days'] == 90)
        require(explorer['coverage_source']['as_of'] == coverage['as_of'])
        require(explorer['coverage_source']['source_sha256'] == coverage['source_identity']['sha256'])
        require(len(explorer['rows']) == len({r['ticker'] for r in explorer['rows']}))
        require(set(r['ticker'] for r in explorer['rows']) == set(coverage['tickers']))
        require(coverage['ticker_set']['count'] == len(coverage['tickers']))
        require(manifest['schema'] == 'why-history-manifest/1')
    except (OSError, ValueError, KeyError, TypeError, AssertionError):
        return {'status':'UNAVAILABLE','reason':'The published coverage, explorer and history manifest do not form a consistent snapshot.', 'rows':[]}
    rows, events, verified = [], [], 0
    for item in sorted(explorer['rows'],key=lambda r:r['ticker']):
        tk = item['ticker']
        if not re.fullmatch(r'[A-Z0-9.^-]{1,12}',tk):
            return {'status':'UNAVAILABLE','reason':'Invalid ticker in published snapshot.','rows':[]}
        row = {'ticker':tk,'name':NAMES.get(tk,tk),'sector':item['sector'],
               'kind':'Fund / macro' if item['sector'] in FUND_SECTORS or item['sector']=='Macro' else 'Company',
               'url':f'why/{tk}.html','json_url':f'why/{tk}.history.json','status':'UNAVAILABLE'}
        try:
            entry = manifest['files'][tk]
            require(entry['path'] == f'why/{tk}.history.json')
            raw = (docs/entry['path']).read_bytes()
            require(sha256(raw).hexdigest() == entry['sha256'] and len(raw) == entry['bytes'])
            history = json.loads(raw)
            require(history.get('synthetic') is not True)
            collection = history['collection']; objects = history['evidence_objects']
            require(history['ticker'] == tk and history['build_id'] == manifest['build_id'] == collection['build_id'])
            require(collection['completeness'] == 'COMPLETE')
            require(len(objects) == entry['count'] == collection['returned'] == collection['total_available'])
            require(utc(collection['corpus_start']) <= start and utc(collection['corpus_end']) >= cutoff)
            require(all(o['ticker']==tk and re.fullmatch(r'\d{10}-\d{2}-\d{6}',o['accession_number'] or '') for o in objects))
            window = [o for o in objects if start < utc(o['available_as_of']) <= cutoff]
            require(len(window) == coverage['tickers'][tk]['events_90d'])
            links = source_links(docs/f'why/{tk}.html')
            filings = {}
            for o in sorted(window,key=lambda o:(utc(o['available_as_of']),o['accession_number']),reverse=True):
                acc=o['accession_number']
                if acc not in filings:
                    filings[acc]={'accession':acc,'filing_date':o['filing_date'],'available_as_of':o['available_as_of'],
                                  'types':[], 'records':0,'source_url':links.get(acc.replace('-',''))}
                filings[acc]['records'] += 1
                if o['evidence_type'] not in filings[acc]['types']:filings[acc]['types'].append(o['evidence_type'])
            recent=max((utc(o['available_as_of']) for o in window),default=None)
            types=Counter(o['evidence_type'] for o in window)
            insider=sum(n for k,n in types.items() if k.startswith('INSIDER_'))
            row.update(status='AVAILABLE',events_90d=len(window),filings_90d=len(filings),
                       events_30d=sum(utc(o['available_as_of'])>cutoff-timedelta(days=30) for o in window),
                       recent_at=recent.isoformat() if recent else None,
                       age_days=round((cutoff-recent).total_seconds()/86400,1) if recent else None,
                       insider_events=insider,other_events=len(window)-insider,
                       types=dict(types),filings=list(filings.values())[:5],history_sha256=entry['sha256'],
                       coverage_state='Direct evidence' if window else 'No direct records',
                       question=('Check fund holdings and issuer evidence before applying a company-level conclusion.' if row['kind']=='Fund / macro' else
                                 'Read the underlying filings to distinguish reported transactions from model classifications.'))
            events.extend(window);verified+=1
        except (OSError, ValueError, KeyError, TypeError, AssertionError):
            row['reason']='History unavailable, incomplete, mismatched, or outside the common window.'
        rows.append(row)
    valid=[r for r in rows if r['status']=='AVAILABLE']
    sector_rows=[]
    for sector in sorted({r['sector'] for r in rows}):
        group=[r for r in rows if r['sector']==sector]
        sector_rows.append({'sector':sector,'total':len(group),'with_evidence':sum(r.get('events_90d',0)>0 for r in group),
                            'unavailable':sum(r['status']!='AVAILABLE' for r in group)})
    return {'schema':'scoreboard-research/1','status':'OK' if verified==len(rows) else 'PARTIAL',
            'cutoff':coverage['as_of'],'window_start_exclusive':start.isoformat(),'window_days':90,
            'history_build_id':manifest['build_id'],'coverage_source_sha256':coverage['source_identity']['sha256'],
            'summary':{'tracked':len(rows),'histories_verified':verified,'with_evidence':sum(r['events_90d']>0 for r in valid),
                       'without_evidence':sum(r['events_90d']==0 for r in valid),'events':len(events),
                       'distinct_filings':len({o['accession_number'] for o in events}),
                       'insider_events':sum(o['evidence_type'].startswith('INSIDER_') for o in events)},
            'sectors':sector_rows,'rows':rows,
            'definitions':{'event':'An accepted event record in the public corpus. Several records may share one filing.',
                           'filing':'Unique SEC accession number in the common 90-day window.',
                           'recent':'Latest recorded available_as_of in that window, not the date of the latest SEC filing in existence.',
                           'scope':'Complete for the published corpus only. This is not comprehensive SEC coverage or independent verification.'}}
