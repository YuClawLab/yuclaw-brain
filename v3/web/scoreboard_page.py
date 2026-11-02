"""Presentation for the public research scoreboard; no network access at render time."""
from __future__ import annotations
from datetime import datetime
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from v3.web.useful_blocks import site_header_html, footer_stamp_html, freshness_strip, build_footer

ASSETS = Path(__file__).with_name('scoreboard_assets')
E = lambda value: escape(str(value), quote=True)


def require(condition):
    if not condition:
        raise ValueError("Inconsistent public artifact")


def day(value):
    return datetime.fromisoformat(value[:10]).strftime('%d %b %Y') if value else 'Unavailable'


def load_notes(docs):
    try:
        d=json.loads((docs/'evidence/scoreboard_notes.json').read_text())
        require(d['schema']=='scoreboard-notes/1')
        for n in d['notes']:
            require(all(isinstance(n[k],str) for k in ('ticker','company','category','period','title','metric','metric_label','secondary','summary','implication','question','caution','locator','calculation')))
            u=urlparse(n['source']['url'])
            require(u.scheme=='https' and u.hostname in {'www.sec.gov','ir.aboutamazon.com'})
            require(re.fullmatch(r'[a-f0-9]{64}', n['source']['sha256']))
            require(isinstance(n['source']['bytes'],int) and n['source']['bytes']>0)
            day(n['source']['retrieved_at']);day(n['period_end'])
            require(all(isinstance(f['value'],(int,float)) and all(isinstance(f[k],str) for k in ('label','unit','basis')) for f in n['facts']))
        return d
    except (OSError, ValueError, AssertionError, KeyError, TypeError):
        return {'edition':None,'notes':[]}


def note_card(n):
    facts=''.join(f'<dt>{E(f["label"])} <small>({E(f["basis"])})</small></dt><dd>{E(f["value"]):s}<br><small>{E(f["unit"])}</small></dd>' for f in n['facts'])
    publication=f'Released {day(n["published"])} · ' if n.get('published') else ''
    return f'''<article class="note" id="note-{E(n['ticker'])}">
<div class="note-top"><span class="ticker-tag">{E(n['ticker'])}</span><span>{E(n['category'])}</span><span class="note-period">{E(n['period'])}</span></div>
<h3>{E(n['title'])}</h3><div class="note-number"><strong>{E(n['metric'])}</strong><span>{E(n['metric_label'])}</span></div>
<p class="note-secondary">{E(n['secondary'])}</p><p class="copy">{E(n['summary'])}</p>
<div class="research-question"><b>Next research question</b>{E(n['question'])}</div>
<div class="note-actions"><details class="note-details"><summary>Definitions &amp; calculation</summary><p>{E(n['implication'])}</p><dl>{facts}</dl><p class="calculation">{E(n['calculation'])}</p><p>{E(n['caution'])}</p><p><strong>Find it in the source:</strong> {E(n['locator'])}</p></details><a href="{E(n['source']['url'])}" target="_blank" rel="noopener noreferrer">Read issuer source ↗</a></div>
<div class="source-date">{E(n['company'])} · {E(publication)}Source checked {day(n['source']['retrieved_at'])}</div></article>'''


def event_label(value):
    return {'INSIDER_SELL':'Insider disposal','INSIDER_BUY':'Insider acquisition',
            'M_AND_A_ANNOUNCE':'M&A announcement','EXEC_CHANGE':'Executive change',
            'OTHER_MATERIAL':'Other material event'}.get(value,value.replace('_',' ').lower())


def row_html(r,selected=False):
    valid=r['status']=='AVAILABLE'; n=r.get('events_90d')
    date=day(r.get('recent_at')) if r.get('recent_at') else '—'
    label='Direct records' if valid and n else 'No direct records' if valid else 'Unavailable'
    state='' if valid and n else 'none' if valid else 'warning'
    return f'''<tr data-ticker="{E(r['ticker'])}" class="{'selected' if selected else ''}"><td><a class="company-name" href="{E(r['url'])}" data-company="{E(r['ticker'])}">{E(r['ticker'])}</a><span class="company-sub">{E(r['name'] if r['name']!=r['ticker'] else r['sector'])}</span></td><td class="num">{r['filings_90d'] if valid else '—'}</td><td class="num">{r['events_90d'] if valid else '—'}</td><td>{E(date)}</td><td><span class="status {state}">{label}</span></td></tr>'''


def detail_html(r):
    head=f'<p class="eyebrow">SELECTED EVIDENCE</p><div class="detail-title"><h3>{E(r["ticker"])}</h3><span class="status none">{E(r["kind"])}</span></div><p class="subtitle">{E(r["name"])} · {E(r["sector"])}</p>'
    if r['status']!='AVAILABLE':
        return head+'<p>Evidence history is unavailable. Counts are not treated as zero.</p>'
    filings=''.join(f'<li><a href="{E(f["source_url"] or r["url"])}" target="_blank" rel="noopener noreferrer">{E(day(f["filing_date"]))} · {"SEC source" if f["source_url"] else "Evidence page"} ↗</a><small>{E(", ".join(event_label(t) for t in f["types"]))} · {f["records"]} record(s)</small><small>{E(f["accession"])}</small></li>' for f in r['filings'])
    types=''.join(f'<span class="type-tag">{E(event_label(t))} {count}</span>' for t,count in sorted(r['types'].items(),key=lambda kv:(-kv[1],kv[0])))
    return head+f'''<div class="detail-stats"><div><strong>{r['filings_90d']}</strong><span>distinct filings · 90d</span></div><div><strong>{r['events_90d']}</strong><span>event records · 90d</span></div></div><div>{types}</div><h4>Recent source documents</h4>{'<ul class="filing-list">'+filings+'</ul>' if filings else '<p>No direct event records in this window. Check constituent or issuer sources for this instrument.</p>'}<p>{E(r['question'])}</p><a class="detail-link" href="{E(r['url'])}">Open full evidence page ↗</a><a class="detail-link" href="{E(r['json_url'])}">Download complete history ↗</a>'''


def present(board,status,audit,research=None,notes=None):
    research=research or {'status':'UNAVAILABLE','rows':[]}; notes=notes or {'edition':None,'notes':[]}
    s=research.get('summary',{}); valid=research['status'] in {'OK','PARTIAL'}
    rows=research['rows']; first=next((r for r in rows if r['ticker']=='AMZN'),rows[0] if rows else None)
    def metric(value,label,desc,green=False):
        return f'<div class="metric"><strong class="{"green" if green else ""}">{value:,}</strong><div class="label">{E(label)}</div><p>{E(desc)}</p></div>' if isinstance(value,int) else f'<div class="metric"><strong>—</strong><div class="label">{E(label)}</div><p>Data unavailable</p></div>'
    metrics=''.join([metric(s.get('with_evidence'),'Names with direct evidence',f'Of {s.get("tracked","—")} tracked names',True),metric(s.get('distinct_filings'),'Distinct SEC filings','Deduplicated by accession · 90d'),metric(s.get('events'),'Event records','Several records can share one filing'),metric(s.get('without_evidence'),'Names without direct records','See instrument scope before drawing conclusions')])
    if research['status']=='PARTIAL':metrics+='<p class="error-note">Partial snapshot: unavailable histories are excluded from totals and marked in the table.</p>'
    chart=''.join(f'<div class="sector-row"><span>{E(g["sector"])}</span><div class="bar-track" aria-hidden="true"><div class="bar-fill" style="width:{100*g["with_evidence"]/g["total"]:.2f}%"></div></div><span class="value">{g["with_evidence"]} / {g["total"]}{" *" if g["unavailable"] else ""}</span></div>' for g in research.get('sectors',[]))
    ins=s.get('insider_events',0); ev=s.get('events',0)
    mix=f'<div class="mix-total"><strong>{ins:,} insider-transaction records</strong><span>of {ev:,}</span></div><div class="mix-bar" aria-hidden="true"><div class="mix-insider" style="width:{100*ins/ev if ev else 0:.2f}%"></div></div><div class="mix-labels"><span>Insider transactions</span><span>{ev-ins:,} other events</span></div>' if valid else '<p>Event mix unavailable.</p>'
    validation=[]
    if board:
        c=board['columns'];cov=c['replications']['exact_release_evidence']['exact_target_evidence']
        entries=[(c['witnesses']['qualified'],'Qualified methodology reviews','Reviewed witness receipts'),(c['audits']['qualified'],'Qualified external audit attempts','Internal tests are excluded'),(cov.get('successful_package_reproductions','—'),'Target package reproductions',board['target'].get('tag','No release bound')),(c['packet_uses']['count'],'Document-use receipts','Use does not establish investment benefit')]
        for value,label,desc in entries:validation.append(f'<div class="validation-stat"><strong>{E(value)}</strong><span>{E(label)}</span><small>{E(desc)}</small></div>')
    else:validation.append(f'<p class="empty">{"PENDING" if status in ("ABSENT","OK") else "UNAVAILABLE"}: independent-validation records are unavailable. No zero counts are inferred.</p>')
    data={'research':research,'notes':notes}
    encoded=json.dumps(data,ensure_ascii=True,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    values={'CSS':(ASSETS/'style.css').read_text(),'JS':(ASSETS/'interactions.js').read_text() if rows else '',
            'HEADER':site_header_html(subtitle='Research intelligence',active='evidence_scoreboard.html'),
            'CUTOFF_LABEL':E(day(research.get('cutoff'))),'WINDOW_LABEL':E(day(research.get('window_start_exclusive'))+' – '+day(research.get('cutoff'))) if valid else 'Unavailable',
            'METRICS':metrics,'NOTES_DATE':E(day(notes.get('edition'))),'NOTES':''.join(note_card(n) for n in notes['notes']) or '<p class="empty">Source-linked research notes are unavailable.</p>',
            'SECTOR_OPTIONS':''.join(f'<option>{E(g["sector"])}</option>' for g in research.get('sectors',[])),
            'ROW_COUNT':str(len(rows)) if valid else 'Unavailable',
            'COMPANY_ROWS':''.join(row_html(r,r is first) for r in rows) or '<tr><td colspan="5" class="empty">Coverage data unavailable; no zero counts are inferred.</td></tr>',
            'INITIAL_DETAIL':detail_html(first) if first else '<p>No consistent public snapshot is available.</p>',
            'SECTOR_CHART':chart or '<p>Sector coverage unavailable.</p>','EVENT_MIX':mix,'VALIDATION':''.join(validation),'AUDIT':audit,'DATA':encoded,
            'STAMP':footer_stamp_html(freshness_strip(research.get('cutoff',board['source_timestamp'] if board else '')[:10] or 'unavailable')),'BUILD':build_footer()}
    return re.sub(r'%%([A-Z_]+)%%',lambda m:values[m[1]],(ASSETS/'page.html').read_text())
