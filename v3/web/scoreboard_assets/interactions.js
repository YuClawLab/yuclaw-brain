(() => {
  'use strict';
  const payload = JSON.parse(document.getElementById('scoreboard-data').textContent);
  const all = payload.research.rows;
  const byTicker = new Map(all.map(r => [r.ticker, r]));
  const query = document.getElementById('query');
  const sector = document.getElementById('sector');
  const scope = document.getElementById('scope');
  const sort = document.getElementById('sort');
  const tbody = document.getElementById('company-rows');
  const detail = document.getElementById('company-detail');
  let selected = byTicker.has('AMZN') ? 'AMZN' : all[0]?.ticker;
  let visible = [...all];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const count = n => Number(n).toLocaleString('en-US');
  const date = value => value ? new Intl.DateTimeFormat('en-GB',{day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(value)) : '—';
  const type = s => ({INSIDER_SELL:'Insider disposal',INSIDER_BUY:'Insider acquisition',M_AND_A_ANNOUNCE:'M&A announcement',EXEC_CHANGE:'Executive change',OTHER_MATERIAL:'Other material event'}[s] || s.replaceAll('_',' ').toLowerCase());
  function renderDetail(r) {
    if (!r) { detail.innerHTML = '<p>No matching names. Change the filters to explore the corpus.</p>'; return; }
    const head = `<p class="eyebrow">SELECTED EVIDENCE</p><div class="detail-title"><h3>${esc(r.ticker)}</h3><span class="status none">${esc(r.kind)}</span></div><p class="subtitle">${esc(r.name)} · ${esc(r.sector)}</p>`;
    if (r.status !== 'AVAILABLE') {detail.innerHTML = head + '<p>Evidence history is unavailable. Counts are not treated as zero.</p>';return;}
    const filings = r.filings.map(f => `<li><a href="${esc(f.source_url || r.url)}" target="_blank" rel="noopener noreferrer">${date(f.filing_date)} · ${f.source_url ? 'SEC source' : 'Evidence page'} ↗</a><small>${esc(f.types.map(type).join(', '))} · ${count(f.records)} record(s)</small><small>${esc(f.accession)}</small></li>`).join('');
    const types = Object.entries(r.types).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0])).map(([k,v]) => `<span class="type-tag">${esc(type(k))} ${count(v)}</span>`).join('');
    detail.innerHTML = head + `<div class="detail-stats"><div><strong>${count(r.filings_90d)}</strong><span>distinct filings · 90d</span></div><div><strong>${count(r.events_90d)}</strong><span>event records · 90d</span></div></div><div>${types}</div><h4>Recent source documents</h4>${filings ? '<ul class="filing-list">'+filings+'</ul>' : '<p>No direct event records in this window. Check constituent or issuer sources for this instrument.</p>'}<p>${esc(r.question)}</p><a class="detail-link" href="${esc(r.url)}">Open full evidence page ↗</a><a class="detail-link" href="${esc(r.json_url)}">Download complete history ↗</a>`;
  }
  function paintRows() {
    tbody.innerHTML = visible.map(r => {
      const ok = r.status === 'AVAILABLE';
      const has = ok && r.events_90d > 0;
      return `<tr data-ticker="${esc(r.ticker)}" class="${r.ticker === selected ? 'selected' : ''}"><td><a class="company-name" href="${esc(r.url)}" data-company="${esc(r.ticker)}"${r.ticker===selected ? ' aria-current="true"' : ''}>${esc(r.ticker)}</a><span class="company-sub">${esc(r.name !== r.ticker ? r.name : r.sector)}</span></td><td class="num">${ok ? count(r.filings_90d) : '—'}</td><td class="num">${ok ? count(r.events_90d) : '—'}</td><td>${date(r.recent_at)}</td><td><span class="status ${has ? '' : ok ? 'none' : 'warning'}">${has ? 'Direct records' : ok ? 'No direct records' : 'Unavailable'}</span></td></tr>`;
    }).join('') || '<tr><td colspan="5" class="empty">No matches. Try another ticker, sector or evidence view.</td></tr>';
    document.getElementById('result-count').textContent = `${visible.length} of ${all.length} tracked names · ${sort.selectedOptions[0].textContent.toLowerCase()}`;
    renderDetail(byTicker.get(selected));
  }
  function filter() {
    const q = query.value.trim().toLowerCase();
    visible = all.filter(r => {
      if (q && !`${r.ticker} ${r.name}`.toLowerCase().includes(q)) return false;
      if (sector.value && r.sector !== sector.value) return false;
      if (scope.value === 'direct') return r.status === 'AVAILABLE' && r.events_90d > 0;
      if (scope.value === 'none') return r.status === 'AVAILABLE' && r.events_90d === 0;
      if (scope.value === 'recent') return r.status === 'AVAILABLE' && r.age_days !== null && r.age_days <= 7;
      if (scope.value === 'unavailable') return r.status !== 'AVAILABLE';
      return true;
    });
    visible.sort((a,b) => {
      if (sort.value === 'filings') return (b.filings_90d ?? -1)-(a.filings_90d ?? -1) || a.ticker.localeCompare(b.ticker);
      if (sort.value === 'recent') return (a.age_days ?? Infinity)-(b.age_days ?? Infinity) || a.ticker.localeCompare(b.ticker);
      return a.ticker.localeCompare(b.ticker);
    });
    if (!visible.some(r => r.ticker === selected)) selected = visible[0]?.ticker;
    paintRows();
  }
  query.addEventListener('input',filter);
  [sector,scope,sort].forEach(el => el.addEventListener('change',filter));
  document.getElementById('reset').addEventListener('click',() => {query.value='';sector.value='';scope.value='all';sort.value='ticker';selected=byTicker.has('AMZN')?'AMZN':all[0]?.ticker;filter();});
  tbody.addEventListener('click',event => {
    const a=event.target.closest('[data-company]');
    if (!a || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();selected=a.dataset.company;
    // Keep the activating anchor and keyboard focus; replace only the detail content.
    tbody.querySelectorAll('[data-ticker]').forEach(tr => {
      tr.classList.toggle('selected',tr.dataset.ticker===selected);
      const link=tr.querySelector('[data-company]');
      if (tr.dataset.ticker===selected) link.setAttribute('aria-current','true'); else link.removeAttribute('aria-current');
    });
    renderDetail(byTicker.get(selected));
    if (window.matchMedia('(max-width:850px)').matches) detail.scrollIntoView({block:'start'});
  });
  document.getElementById('csv').addEventListener('click',() => {
    const cell = value => {
      let s=String(value ?? '');
      if (/^[=+@\-\t\r]/.test(s)) s="'"+s;
      return '"'+s.replaceAll('"','""')+'"';
    };
    const header=['Ticker','Name','Sector','Instrument type','Data status','Filings 90d','Events 90d','Events 30d','Latest recorded UTC','Cutoff UTC','Window start exclusive UTC','Evidence page'];
    const lines=[header,...visible.map(r => [r.ticker,r.name,r.sector,r.kind,r.status,r.filings_90d,r.events_90d,r.events_30d,r.recent_at,payload.research.cutoff,payload.research.window_start_exclusive,'https://yuclaw.ca/'+r.url])];
    const blob=new Blob(['\ufeff'+lines.map(row => row.map(cell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'});
    const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='yuclaw-evidence-coverage-'+payload.research.cutoff.slice(0,10)+'.csv';a.click();setTimeout(() => URL.revokeObjectURL(url),1000);
  });
  document.getElementById('filters').hidden=false;
  document.getElementById('csv').hidden=false;
  document.getElementById('sort-wrap').hidden=false;
  filter();
})();
