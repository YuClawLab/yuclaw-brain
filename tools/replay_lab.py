#!/usr/bin/env python3
"""Packaged `yuclaw replay-lab` — reproduce the Validation Lab from the public bundle.

PACKAGED MIRROR of tools/replay_lab.py (the stdlib-only standalone script, which
stays working as-is for users who do not want to install anything). DUAL-COPY
RULE: any logic change must be applied to BOTH files identically.

Usage:
    yuclaw replay-lab                      # fetch the public bundle, verify
    yuclaw replay-lab bundle.json          # verify a local bundle
    yuclaw replay-lab --check              # alias for the default fetch+verify

Exit 0 = numerical reproduction and bundled ledger consistency; external provenance
is separate. Exit 4 = required external coverage incomplete. Non-zero on mismatch. Stdlib only. Research/education only — not investment advice.
"""


from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

STDLIB_ONLY = True
SUPPORTED_PYTHON = ("3.10", "3.11", "3.12", "3.13")
TOL = 1e-9


# ---------- stats (verbatim re-implementations of v3/lab/stats.py) ----------
def mean(xs): return sum(xs) / len(xs)


def stdev(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 200, 3e-12, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN: d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN: d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN: c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def _betai(a, b, x):
    if x <= 0.0: return 0.0
    if x >= 1.0: return 1.0
    ln_bt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_pvalue_two_sided(t, df):
    """Two-sided p for Student-t (exact via regularized incomplete beta)."""
    t = abs(t)
    return min(1.0, _betai(df / 2.0, 0.5, df / (df + t * t)))


def one_sample_t(xs):
    n = len(xs)
    if n < 2: return {"mean": mean(xs) if n else None, "t": None, "p": None, "n": n}
    m, s = mean(xs), stdev(xs)
    if s == 0: return {"mean": m, "t": None, "p": None, "n": n}
    t = m / (s / math.sqrt(n))
    return {"mean": m, "t": t, "p": t_pvalue_two_sided(t, n - 1), "n": n}


def bootstrap_ci_mean(xs, iters=10_000, alpha=0.05, seed=20260518):
    n = len(xs)
    if n < 3: return None
    rng = random.Random(seed)
    means = []
    for _ in range(iters):
        means.append(sum(rng.choice(xs) for _ in range(n)) / n)
    means.sort()
    return (means[int((alpha / 2) * iters)],
            means[min(iters - 1, int((1 - alpha / 2) * iters))])


def newey_west_t(xs, lag):
    n = len(xs)
    if n < 3: return {"mean": mean(xs) if n else None, "t": None, "p": None, "n": n, "lag": lag}
    lag = max(0, min(lag, n - 2))
    m = mean(xs)
    e = [x - m for x in xs]
    s = sum(v * v for v in e) / n
    for l in range(1, lag + 1):
        gl = sum(e[i] * e[i - l] for i in range(l, n)) / n
        s += 2.0 * (1.0 - l / (lag + 1.0)) * gl
    if s <= 0: return {"mean": m, "t": None, "p": None, "n": n, "lag": lag}
    t = m / math.sqrt(s / n)
    return {"mean": m, "t": t, "p": t_pvalue_two_sided(abs(t), n - 1), "n": n, "lag": lag}


def _ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def pearson(xs, ys):
    n = len(xs)
    if n < 2: return None
    mx, my = mean(xs), mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0: return None
    return sum((xs[i] - mx) * (ys[i] - my) for i in range(n)) / math.sqrt(sxx * syy)


def spearman(xs, ys):
    if len(xs) != len(ys) or len(xs) < 2: return None
    return pearson(_ranks(xs), _ranks(ys))


def ols(y, x):
    n = len(y)
    if n < 3 or len(x) != n: return None
    mx, my = mean(x), mean(y)
    sxx = sum((xi - mx) ** 2 for xi in x)
    if sxx == 0: return None
    beta = sum((x[i] - mx) * (y[i] - my) for i in range(n)) / sxx
    alpha = my - beta * mx
    resid = [y[i] - alpha - beta * x[i] for i in range(n)]
    sse = sum(r * r for r in resid)
    sst = sum((yi - my) ** 2 for yi in y)
    df = n - 2
    s2 = sse / df
    se_alpha = math.sqrt(s2 * (1.0 / n + mx * mx / sxx))
    t_alpha = alpha / se_alpha if se_alpha > 0 else None
    return {"alpha": alpha, "beta": beta, "t_alpha": t_alpha,
            "p_alpha": t_pvalue_two_sided(abs(t_alpha), df) if t_alpha is not None else None,
            "r2": 1.0 - sse / sst if sst > 0 else None, "n": n, "se_alpha": se_alpha}


# ---------- reproduction ----------
FAILURES: list[str] = []


def check(label, got, want, tol=1e-6):
    if want is None and got is None:
        return
    if want is None or got is None:
        FAILURES.append(f"{label}: got {got}, expected {want}")
        return
    if (isinstance(got, bool) or isinstance(want, bool)
            or not math.isfinite(float(got)) or not math.isfinite(float(want))):
        FAILURES.append(f"{label}: finite numerical values required")
        return
    if abs(float(got) - float(want)) > tol:
        FAILURES.append(f"{label}: got {got:.10f}, expected {float(want):.10f}")


def content_hash(snapshot_id, total_score, components):
    """Ledger leaf hash (must match v3/proof/_hash.py)."""
    parts = [snapshot_id, f"{float(total_score):.6f}"]
    for cid in sorted(components):
        parts.append(f"{cid}={float(components[cid]):.6f}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _same(label, got, want):
    if got != want:
        FAILURES.append(f"{label}: got {got!r}, expected {want!r}")


def _finite_tree(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite JSON number")
    if isinstance(value, dict):
        for x in value.values():
            _finite_tree(x)
    elif isinstance(value, list):
        for x in value:
            _finite_tree(x)


def _unique_object(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise ValueError(f"duplicate JSON key: {k}")
        obj[k] = v
    return obj


def _load_json(path):
    data = json.loads(Path(path).read_text(), object_pairs_hook=_unique_object)
    _finite_tree(data)
    return data


def _mde(se, df):
    if se is None or se <= 0 or df < 3:
        return None
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if t_pvalue_two_sided(mid, df) > 0.05:
            lo = mid
        else:
            hi = mid
    return ((lo + hi) / 2 + 0.8416) * se


def _ledger_checks(bundle, ledger_path=None, ledger_sha256=None):
    """Check bundled integrity separately from externally pinned provenance."""
    roots = bundle['ledger_daily_roots']
    leaves = bundle['ledger_leaves']
    if not isinstance(roots, list) or not roots or not isinstance(leaves, dict) or not leaves:
        raise ValueError("INCOMPLETE: required daily roots and ledger leaves must be nonempty")
    blocks = {}
    for block in roots:
        day = block['date']; _d(day)
        if day in blocks:
            raise ValueError(f"duplicate ledger date {day}")
        blocks[day] = block
    _same('ledger day coverage', set(blocks), set(leaves))
    pinned = None
    if ledger_path:
        if not ledger_sha256 or len(ledger_sha256) != 64:
            raise ValueError("--ledger requires an independently obtained --ledger-sha256")
        raw = Path(ledger_path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != ledger_sha256.lower():
            raise ValueError("external ledger SHA-256 does not match the independently supplied pin")
        pinned = {}
        for line in raw.splitlines():
            if not line.strip():
                continue
            block = json.loads(line, object_pairs_hook=_unique_object)
            if block['date'] in pinned:
                raise ValueError("duplicate date in external ledger")
            hashes = [r['content_hash'] for r in block['entries']]
            actual = hashlib.sha256('|'.join(sorted(hashes)).encode()).hexdigest()
            _same(f"external ledger {block['date']} root", actual, block['daily_root'])
            _same(f"external ledger {block['date']} count", len(hashes), block['snapshot_count'])
            pinned[block['date']] = block
    n_ok = n_subset = n_leaves = 0
    unanchored_inputs = set()
    index = defaultdict(list)
    seen_ids = set()
    anchored = set()
    for day, rows in sorted(leaves.items()):
        _d(day)
        if not rows:
            raise ValueError(f"empty ledger day {day}")
        hashes = []
        for row in rows:
            sid = row['snapshot_id']
            if sid in seen_ids:
                raise ValueError(f"duplicate snapshot_id {sid}")
            seen_ids.add(sid)
            h = content_hash(sid, row['total_score'], row['components'])
            hashes.append(h)
            index[(day, row['ticker'])].append((row, h))
        n_leaves += len(rows)
        block = blocks.get(day)
        if block is None:
            FAILURES.append(f"INCOMPLETE: missing daily root for {day}")
            continue
        entry_hashes = block.get('entry_hashes')
        if not entry_hashes:
            FAILURES.append(f"INCOMPLETE: missing anchor membership for {day}")
            continue
        _same(f"{day} anchor count", len(entry_hashes), block['snapshot_count'])
        root = hashlib.sha256('|'.join(sorted(entry_hashes)).encode()).hexdigest()
        _same(f"{day} anchor root", root, block['daily_root'])
        missing = Counter(entry_hashes) - Counter(hashes)
        if missing:
            FAILURES.append(f"ledger leaf mismatch on {day}: {sum(missing.values())} anchored leaves missing")
        elif Counter(entry_hashes) == Counter(hashes):
            n_ok += 1
        else:
            n_subset += 1
            print(f"  note: {day} — {len(entry_hashes)} of {len(hashes)} bundled leaves anchored; extra leaves are NOT authenticated by this daily root")
        anchored.update(entry_hashes)
        if pinned is not None:
            external = pinned.get(day)
            if external is None:
                FAILURES.append(f"INCOMPLETE: external ledger lacks {day}")
            else:
                _same(f"{day} external root", block['daily_root'], external['daily_root'])
                _same(f"{day} external members", Counter(entry_hashes), Counter(x['content_hash'] for x in external['entries']))
    # The historical in-sample reconstruction has no forward-ledger claim.
    # Legacy bundles identify scores by date/ticker/value. New exports also
    # supply snapshot identifiers; both routes must agree with actual leaves.
    def bind(day, ticker, score, sid=None):
        candidates = [(r,h) for r,h in index.get((day,ticker), [])
                      if abs(float(r['total_score']) - float(score)) <= 0.0000005
                      and (sid is None or r['snapshot_id'] == sid)]
        if not candidates:
            FAILURES.append(f"input binding mismatch: {day}/{ticker}, score {score}, snapshot {sid}")
        elif not all(h in anchored for _,h in candidates):
            unanchored_inputs.add((day,ticker))
    forward = bundle['panels']['forward']
    min_uni = bundle['methodology']['min_universe_for_deciles']
    for rb in forward['rebalances']:
        if len(rb['scores']) < min_uni:
            continue  # excluded partial-universe rows are not analytical inputs
        for ticker, score in rb['scores'].items():
            bind(rb['signal_date'], ticker, score, rb.get('snapshot_ids', {}).get(ticker))
    counts = Counter((r['date'], h) for r in forward['ic_rows'] for h in ('r1','r5','r20') if r[h] is not None)
    for row in forward['ic_rows']:
        if not any(row[h] is not None and counts[(row['date'], h)] >= min_uni for h in ('r1','r5','r20')):
            continue
        bind(row['date'], row['ticker'], row['score'], row.get('snapshot_id'))
    print(f"Ledger verification: {n_ok} daily roots exact + {n_subset} anchored-subset days ({n_leaves} leaf hashes recomputed)")
    print(f"Analysis-input binding: date/ticker/score checked; {len(unanchored_inputs)} date/ticker inputs not fully covered by daily anchors")
    print("External provenance: " + ("PINNED LEDGER MATCH CHECKED" if pinned is not None else "UNVERIFIED (bundle-local checks only; supply --ledger and --ledger-sha256)"))
    return pinned is not None and not unanchored_inputs


def _run(path, ledger_path=None, ledger_sha256=None, require_external=False):
    FAILURES.clear()
    bundle = _load_json(path)
    if bundle.get('schema') not in (None, 'lab-replay/2'):
        raise ValueError('unsupported replay schema')
    meta = bundle['methodology']
    print(f"Replay bundle built {bundle['built_utc']} from source commit {(bundle.get('source_commit') or '?')[:12]}")
    print(f"Ledger repo: {bundle['ledger_repo']} @ {(bundle.get('ledger_commit') or '?')[:12]}\n")
    min_uni = meta['min_universe_for_deciles']
    if not isinstance(min_uni, int) or isinstance(min_uni, bool) or min_uni < 2:
        raise ValueError("invalid minimum universe")
    if not 0 < meta['decile_fraction'] <= 0.5:
        raise ValueError("invalid decile fraction")
    _same('bootstrap iterations', meta['bootstrap']['iters'], 10000)
    _same('bootstrap seed', meta['bootstrap']['seed'], 20260518)
    for panel in ('forward', 'in_sample'):
        p = bundle['panels'][panel]; exp = bundle['expected'][panel]
        if bundle.get('schema') == 'lab-replay/2':
            if not isinstance(p.get('trading_dates'), list) or not p['trading_dates'] or not p.get('observation_units'):
                raise ValueError('lab-replay/2 requires calendar and observation units')
            for rb in p['rebalances']:
                ids = rb.get('snapshot_ids', {})
                if set(ids) != set(rb['scores']) or any(not isinstance(sid, str) or not sid for sid in ids.values()):
                    raise ValueError('lab-replay/2 requires a snapshot identifier for every score')
            if any(not isinstance(row.get('snapshot_id'), str) or not row['snapshot_id'] for row in p['ic_rows']):
                raise ValueError('lab-replay/2 requires snapshot identifiers for IC rows')
        top, bot, uew, spy, eligible = [], [], [], [], []
        dates = [rb['signal_date'] for rb in p['rebalances']]
        if dates != sorted(set(dates)):
            raise ValueError(f"{panel}: duplicate or unordered rebalance dates")
        for rb in p['rebalances']:
            scores, rets = rb['scores'], rb['period_returns']
            if _d(rb['exit']) <= _d(rb['entry']):
                raise ValueError('rebalance exit must be after entry')
            if any(isinstance(v, bool) or not isinstance(v, (int,float)) for v in scores.values()):
                raise ValueError('scores must be finite numbers')
            if not set(rets).issubset(scores):
                raise ValueError('returns contain a name outside the scored population')
            if len(scores) < min_uni:
                continue
            ranked = sorted(scores, key=lambda tk: (-scores[tk], tk))
            k = max(1, round(len(ranked)*meta['decile_fraction']))
            def cret(tks):
                vals = [rets[t] for t in tks if t in rets]
                return mean(vals) if vals else 0.0
            top.append(cret(ranked[:k])); bot.append(cret(ranked[-k:]))
            uew.append(cret(list(scores))); spy.append(rb['spy_ret']); eligible.append(rb)
        _same(f'{panel}.evaluable', bool(eligible), exp['evaluable'])
        if not eligible:
            print(f'[{panel}] no evaluable periods in inputs')
            continue
        if not exp['evaluable']:
            continue  # already a recorded mismatch, never a successful skip
        window = [eligible[0]['entry'], eligible[-1]['exit']]
        for name, value in [('panel window',p['window']),('expected window',exp['window']),('spread window',exp['spreads']['window']),('market-model window',exp['market_model']['window'])]:
            _same(f'{panel}.{name}', window, value)
        _same(f'{panel}.n_periods', len(top), exp['n_periods'])
        print(f"[{panel}] {len(top)} rebalance periods, window {window}")
        for key,a,b in (('top_minus_bottom',top,bot),('top_minus_universe',top,uew)):
            diffs = [x-y for x,y in zip(a,b)]; t = one_sample_t(diffs)
            ci = bootstrap_ci_mean(diffs, seed=meta['bootstrap']['seed']); e = exp['spreads'][key]
            for got,want in [('mean','mean_per_period'),('t','t_stat'),('p','p_value'),('n','n_periods')]:
                check(f'{panel}.{key}.{want}',t[got],e[want],1e-9)
            if ci is None or e['ci95'] is None:
                _same(f'{panel}.{key}.ci95',ci,e['ci95'])
            else:
                for i in range(2):check(f'{panel}.{key}.ci95[{i}]',ci[i],e['ci95'][i],1e-9)
            print(f"  spread {key:18s} mean/period {t['mean']:+.5f}  p={t['p']}  n={t['n']}  CI95={ci}")
        units = p.get('observation_units')
        if units:
            _same(f'{panel}.ic_rows', len(p['ic_rows']), units['ic_rows'])
            _same(f'{panel}.distinct_issuer_dates', len({(r['date'],r['ticker']) for r in p['ic_rows']}), units['distinct_issuer_dates'])
        by_date = defaultdict(list); seen = set()
        for row in p['ic_rows']:
            _d(row['date'])
            for key in ('score', 'r1', 'r5', 'r20'):
                value = row[key]
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                    raise ValueError(f'IC {key} must be a finite number or a missing return')
            if row['score'] is None:
                raise ValueError('IC score cannot be missing')
            ident = row.get('snapshot_id')
            if ident is not None and ident in seen:raise ValueError(f'duplicate IC snapshot {ident}')
            if ident is not None:seen.add(ident)
            by_date[row['date']].append(row)
        for h,rk in ((1,'r1'),(5,'r5'),(20,'r20')):
            ics,dts,ns,raw_dates = [],[],[],[]
            for day in sorted(by_date):
                rows = [r for r in by_date[day] if r[rk] is not None]
                if rows:raw_dates.append(day)
                if len(rows)<min_uni:continue
                rho = spearman([r['score'] for r in rows],[r[rk] for r in rows])
                if rho is not None:ics.append(rho);dts.append(day);ns.append(len(rows))
            e = exp['ic'][str(h)]
            t = one_sample_t(ics)
            got = {'mean_ic':t['mean'],'t_stat':t['t'],'p_value':t['p'],'n_dates':len(ics),
                   'median_cross_section':sorted(ns)[len(ns)//2] if ns else None,
                   'ic_positive_share':sum(x>0 for x in ics)/len(ics) if len(ics)>=2 else None,
                   'date_range':[min(raw_dates),max(raw_dates)] if ics else None}
            if len(ics)>=2:
                span = (_d(dts[-1])-_d(dts[0])).days or 1
                spacing=max(1.0,span*5/7/max(1,len(ics)-1))
                nw=newey_west_t(ics,max(0,math.ceil(h/spacing)-1))
                got.update(nw_lag=nw['lag'],nw_t_stat=nw['t'],nw_p_value=nw['p'],t_reliable=len(ics)/(nw['lag']+1)>=3)
            _same(f'{panel}.ic{h}.fields',set(got),set(e))
            for key,value in got.items():
                if key not in e:continue
                if key in ('date_range','t_reliable'):_same(f'{panel}.ic{h}.{key}',value,e[key])
                else:check(f'{panel}.ic{h}.{key}',value,e[key],1e-9)
            print(f"  IC {h:2d}d mean {got['mean_ic']} NW-p={got.get('nw_p_value')} T={len(ics)} dates")
        mm=exp['market_model'];ppy=mm['periods_per_year']
        check(f'{panel}.annualization',ppy,252/mm['avg_holding_td'],1e-9)
        # Legacy bundles lack a calendar; keep that dependency explicit.
        if p.get('trading_dates'):
            if p['trading_dates'] != sorted(set(p['trading_dates'])):
                raise ValueError('duplicate or unordered trading dates')
            for day in p['trading_dates']:_d(day)
            span=sum(1 for d in p['trading_dates'] if p['rebalances'][0]['entry']<=d<=window[1])
            check(f'{panel}.avg_holding_td',span/len(top),mm['avg_holding_td'],1e-9)
        for key,mkt in (('vs_universe',uew),('vs_spy',spy)):
            r=ols(top,mkt);e=mm[key]
            if r is None or e is None:
                _same(f'{panel}.mm.{key}',r,e);continue
            mde=_mde(r['se_alpha'],r['n']-2)
            got={'alpha_per_period':r['alpha'],'alpha_annualized':(1+r['alpha'])**ppy-1,
                 'beta':r['beta'],'t_alpha':r['t_alpha'],'p_alpha':r['p_alpha'],'r2':r['r2'],
                 'n_periods':r['n'],'mde_alpha_annualized':(1+mde)**ppy-1 if mde is not None else None}
            _same(f'{panel}.mm.{key}.fields',set(got),set(e))
            for k,v in got.items():check(f'{panel}.mm.{key}.{k}',v,e[k],1e-8)
            print(f"  market-model {key} alpha/period {r['alpha']:+.5f} beta {r['beta']:.2f} p={r['p_alpha']} n={r['n']}")
    external_complete=_ledger_checks(bundle,ledger_path,ledger_sha256)
    if FAILURES:
        print('\nREPRODUCTION FAILED:')
        for failure in FAILURES:print('  - '+failure)
        return 1
    if require_external and not external_complete:
        print('\nINCOMPLETE: externally pinned coverage of every forward analysis input is required')
        return 4
    print('\nREPRODUCED OK — checked numerical fields and bundled ledger consistency.')
    print('Scope: core expected tables only; historical in-sample inputs and vendor-derived returns are not independently authenticated. Legacy annualization uses declared calendar metadata.')
    return 0


def _d(s):
    from datetime import date
    return date.fromisoformat(s)


BUNDLE_URL = "https://yuclawlab.github.io/yuclaw-brain/replay/lab_replay_bundle.json"


# Exit codes: 0 = reproduced, 1 = statistic/root mismatch, 2 = argparse,
# 3 = could not fetch the published bundle (network/proxy — not a data problem).
EXIT_FETCH_FAILED = 3


class _FetchError(Exception):
    pass


def _fetch(url: str) -> str:
    import tempfile
    import urllib.error
    import urllib.request
    print(f"fetching {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "yuclaw-replay-lab"})
    try:
        data = urllib.request.urlopen(req, timeout=120).read()
    except urllib.error.HTTPError as e:
        raise _FetchError(f"HTTP {e.code} fetching the replay bundle\n  URL: {url}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise _FetchError(f"could not reach the replay-bundle host ({reason})\n  URL: {url}") from e
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    tmp.write(data)
    tmp.close()
    print(f"  {len(data):,} bytes -> {tmp.name}")
    return tmp.name


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="yuclaw replay-lab",
                                description="Reproduce the Validation Lab's statistics and "
                                            "ledger roots from the public replay bundle.",
                                epilog="Three commands, three contracts: `yuclaw why TICKER --as-of DATE` shows the STORED signal at that date (offline only for the bundled demo signal, AMD @ 2026-05-20; otherwise it reads the research backend); `yuclaw replay TICKER --date DATE` RECOMPUTES the signal from the database as of that date; `yuclaw replay-lab` reproduces the published Validation Lab statistics from the PUBLIC bundle and needs no database.")
    p.add_argument("bundle", nargs="?", help="path to lab_replay_bundle.json "
                                             "(default: fetch the published bundle)")
    p.add_argument("--check", action="store_true",
                   help="explicit check mode (same as the default behavior)")
    p.add_argument("--ledger", help="independently acquired yuclaw-trust ledger JSONL")
    p.add_argument("--ledger-sha256", help="independently obtained SHA-256 of that ledger file")
    p.add_argument("--require-external-ledger", action="store_true", help="exit 4 unless every forward input has externally pinned anchor coverage")
    a = p.parse_args(argv)
    if a.ledger_sha256 and not a.ledger:
        p.error("--ledger-sha256 requires --ledger")
    try:
        path = a.bundle or _fetch(BUNDLE_URL)
    except _FetchError as e:
        print(f"\n[replay-lab] bundle fetch failed: {e}\n"
              f"  Check connectivity/proxy and retry. The bundle is also downloadable\n"
              f"  manually at {BUNDLE_URL} — then run:\n"
              f"  yuclaw replay-lab /path/to/lab_replay_bundle.json", file=sys.stderr)
        return EXIT_FETCH_FAILED
    try:
        return _run(path, a.ledger, a.ledger_sha256, a.require_external_ledger)
    except (ValueError, KeyError, TypeError, OSError, OverflowError, ZeroDivisionError) as e:
        print(f"REPRODUCTION FAILED: invalid or incomplete bundle: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
