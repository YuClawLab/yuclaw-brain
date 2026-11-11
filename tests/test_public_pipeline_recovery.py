"""Regressions for the November daylight-saving outage and false health report."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import pytest
from v3.lab import replay_check as replay
from tools import check_public_freshness as health
from v3.web.useful_blocks import update_due_warning

def bundle(stamp, analysis_day):
    utc_day = stamp[:10]
    leaves = []
    for ticker in ('ONE', 'TWO'):
        sid = 'snap_' + ticker + '_' + hashlib.sha256(f'{ticker}|{stamp}|v3.0'.encode()).hexdigest()[:16]
        leaves.append({'ticker': ticker, 'snapshot_id': sid, 'total_score': .3,
                       'components': {'c1': .2}, 'signal_time_utc': stamp})
    hashes = [replay.content_hash(r['snapshot_id'], r['total_score'], r['components']) for r in leaves]
    return {'schema': 'lab-replay/3',
            'methodology': {'min_universe_for_deciles': 2, 'date_basis': dict(replay.DATE_BASIS)},
            'ledger_leaves': {utc_day: leaves},
            'ledger_daily_roots': [{'date': utc_day, 'snapshot_count': 2, 'entry_hashes': hashes,
                                   'daily_root': hashlib.sha256('|'.join(sorted(hashes)).encode()).hexdigest()}],
            'panels': {'forward': {'rebalances': [{'signal_date': analysis_day,
                'scores': {r['ticker']: .3 for r in leaves}, 'snapshot_ids': {r['ticker']: r['snapshot_id'] for r in leaves}}],
                'ic_rows': [{'date': analysis_day, 'ticker': r['ticker'], 'score': .3, 'snapshot_id': r['snapshot_id'],
                             'r1': .1, 'r5': None, 'r20': None} for r in leaves]}}}

@pytest.mark.parametrize('stamp,day', [
    ('2026-10-30T23:00:01.123456+00:00', '2026-10-30'),
    ('2026-11-03T00:00:01.123456+00:00', '2026-11-02'),
    ('2026-03-09T00:00:01.123456+00:00', '2026-03-08'),
    ('2026-11-03T07:00:00+00:00', '2026-11-03'),
])
def test_dates_are_distinct_but_identity_still_binds(stamp, day):
    b = bundle(stamp, day)
    replay.FAILURES.clear()
    assert replay._ledger_checks(b) is False  # no external provenance claimed
    assert replay.FAILURES == []

@pytest.mark.parametrize('mutation', ['timestamp', 'analysis_day', 'score', 'ticker', 'sid', 'zone', 'utc_day', 'missing_timestamp', 'missing_root'])
def test_date_repair_does_not_bypass_any_identity_check(mutation):
    b = bundle('2026-11-03T00:00:01.123456+00:00', '2026-11-02')
    leaf = b['ledger_leaves']['2026-11-03'][0]
    rb = b['panels']['forward']['rebalances'][0]
    if mutation == 'timestamp': leaf['signal_time_utc'] = '2026-11-03T08:00:00+00:00'
    if mutation == 'analysis_day': rb['signal_date'] = '2026-11-03'
    if mutation == 'score': rb['scores']['ONE'] = .4
    if mutation == 'ticker': leaf['ticker'] = 'OTHER'
    if mutation == 'sid': rb['snapshot_ids']['ONE'] = 'invented'
    if mutation == 'zone': b['methodology']['date_basis']['analysis_timezone'] = 'UTC'
    if mutation == 'utc_day':
        b['ledger_leaves']['2026-11-02'] = b['ledger_leaves'].pop('2026-11-03')
        b['ledger_daily_roots'][0]['date'] = '2026-11-02'
    if mutation == 'missing_timestamp': leaf.pop('signal_time_utc')
    if mutation == 'missing_root': b['ledger_daily_roots'] = []
    replay.FAILURES.clear()
    try:
        replay._ledger_checks(b)
    except (ValueError, KeyError):
        return
    assert replay.FAILURES

@pytest.mark.parametrize('now,want', [
    ('2026-11-04T02:01:00+00:00','2026-11-04T00:00:00+00:00'),
    ('2026-11-09T20:00:00+00:00','2026-11-07T00:00:00+00:00'),
    ('2026-10-31T02:00:00+00:00','2026-10-30T23:00:00+00:00'),
    ('2026-11-03T01:59:00+00:00','2026-10-30T23:00:00+00:00'),
])
def test_monitor_schedule_covers_weekends_and_dst(now, want):
    assert health.expected_after(datetime.fromisoformat(now)).isoformat() == want

def test_stale_served_page_fails_even_when_http_is_successful():
    now = datetime(2026,11,11,5,tzinfo=timezone.utc)
    body = b'<footer class="buildinfo">build 2026-11-03 00:01 UTC</footer>'
    with pytest.raises(ValueError, match='stale'):
        health.inspect('index.html', body, now, health.expected_after(now))
    assert health.inspect('index.html', body.replace(b'11-03', b'11-11'), now, health.expected_after(now))

def test_fresh_render_cannot_hide_stale_scoreboard_data():
    now = datetime(2026,11,11,5,tzinfo=timezone.utc)
    with pytest.raises(ValueError, match='stale'):
        health.inspect('evidence/scoreboard_research.json', b'{"research":{"cutoff":"2026-11-03T00:01:00Z"}}', now, health.expected_after(now))

def test_future_or_missing_clock_is_not_healthy():
    now = datetime(2026,11,11,5,tzinfo=timezone.utc)
    for body in (b'{}', b'{"research":{"cutoff":"2026-11-12T00:01:00Z"}}'):
        with pytest.raises((ValueError, AttributeError)):
            health.inspect('evidence/scoreboard_research.json', body, now, health.expected_after(now))

def test_warning_deadline_is_after_next_scheduled_completion():
    import re
    text = update_due_warning(datetime(2026,11,7,3,tzinfo=timezone.utc))
    deadline = int(re.search(r'deadline="(\d+)"',text).group(1))
    assert datetime.fromtimestamp(deadline/1000,timezone.utc).isoformat() == '2026-11-10T02:00:00+00:00'
    assert 'public-update-overdue' in text

def test_wrong_branch_refused_before_pull_or_push(tmp_path):
    subprocess.run(['git','init','-b','private-test',str(tmp_path)],check=True,capture_output=True)
    script = Path(__file__).resolve().parents[1]/'cron/lib_push_retry.sh'
    marker = tmp_path/'failed'
    p = subprocess.run(['bash','-c','source "$1"; push_with_retry origin main "$2"', '_', str(script), str(marker)],
                       cwd=tmp_path,capture_output=True,text=True)
    assert p.returncode == 23
    assert 'branch mismatch' in marker.read_text()


def test_live_scoreboard_wrapper_and_data_clock():
    now = datetime(2026,11,11,5,tzinfo=timezone.utc)
    doc = {'research': {'cutoff': '2026-11-11T00:01:00Z'}, 'notes': {}}
    assert health.inspect('evidence/scoreboard_research.json', json.dumps(doc).encode(), now, health.expected_after(now))


def test_pinned_calendar_matches_production_winter_and_summer():
    for stamp, offset in [('2026-11-11T00:00:00+00:00', -7), ('2026-07-11T00:00:00+00:00', -6)]:
        assert datetime.fromisoformat(stamp).astimezone(replay.ANALYSIS_ZONE).utcoffset().total_seconds() == offset*3600


def test_old_date_join_reproduces_the_november_failure():
    b = bundle('2026-11-03T00:00:01.123456+00:00', '2026-11-02')
    b['schema'] = 'lab-replay/2'
    replay.FAILURES.clear()
    replay._ledger_checks(b)
    assert any('input binding mismatch' in s for s in replay.FAILURES)
