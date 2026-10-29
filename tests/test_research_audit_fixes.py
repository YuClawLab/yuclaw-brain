"""Regression cases for the externally reproduced 2026-10-13 audit failures."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from v3.lab import replay_check as R
from v3.cli.research_export import prepare
from v3.evidence.claim_support import assess
from v3.evidence.research_summary import composite_anatomy, denominators
from v3.web.lab_prose import comparative_return

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def bundle():
    return json.loads((ROOT / 'docs/replay/lab_replay_bundle.json').read_text())


def run_bundle(b, tmp_path, **kwargs):
    path = tmp_path / 'bundle.json'
    path.write_text(json.dumps(b))
    return R.main([str(path)] + (['--require-external-ledger'] if kwargs.get('require_external') else []))


def test_original_reproduces_but_does_not_establish_external_provenance(bundle, tmp_path, capsys):
    assert run_bundle(bundle, tmp_path) == 0
    assert 'UNVERIFIED' in capsys.readouterr().out
    assert run_bundle(bundle, tmp_path, require_external=True) == 4


@pytest.mark.parametrize('mutation', ['all_roots', 'one_root', 'nw_p', 'score_binding', 'false_evaluable'])
def test_audited_controls_refused(bundle, tmp_path, mutation):
    b = copy.deepcopy(bundle)
    if mutation == 'all_roots':
        b['ledger_daily_roots'] = []
    elif mutation == 'one_root':
        b['ledger_daily_roots'].pop(0)
    elif mutation == 'nw_p':
        b['expected']['forward']['ic']['5']['nw_p_value'] = 0.00000001
    elif mutation == 'score_binding':
        # Monotone shifts preserve ranks and portfolio membership, but break
        # provenance. A numerical-only verifier accepted this control.
        for rb in b['panels']['forward']['rebalances']:
            rb['scores'] = {tk: x + .02 for tk, x in rb['scores'].items()}
        for row in b['panels']['forward']['ic_rows']:
            row['score'] += .02
    else:
        b['expected']['forward']['evaluable'] = False
    assert run_bundle(b, tmp_path) != 0


def test_invalid_json_refused(tmp_path):
    p = tmp_path / 'bad.json'
    for bad in ['{"x": NaN}', '{"x":1,"x":2}']:
        p.write_text(bad)
        assert R.main([str(p)]) == 1


def test_verifier_sums_are_correctly_rounded_on_every_runtime():
    # the builtin sum() changed its summation algorithm in Python 3.12; the printed full-precision statistics must not depend on
    # the runtime, so every floating-point sum in the verifier is math.fsum (correctly rounded): 1e16 + 1 - 1e16 is exactly 1
    assert R.mean([1e16, 1.0, -1e16]) == 1.0 / 3
    assert R.pearson([1e16, 1e16 + 2.0, 1e16 + 4.0], [1.0, 2.0, 3.0]) == 1.0


def test_standalone_verifier_is_identical():
    assert (ROOT / 'tools/replay_lab.py').read_text().split('\n', 1)[1] == (ROOT / 'v3/lab/replay_check.py').read_text()


def test_history_export_uses_complete_source_and_cutoff():
    h = (ROOT / 'docs/why/DELL.history.json').read_bytes()
    m = (ROOT / 'docs/why/history_manifest.json').read_bytes()
    files, meta = prepare(h, m, 'dell', '2026-08-01')
    rows = json.loads(files['events.json'])
    expected = [r for r in json.loads(h)['evidence_objects'] if r['available_as_of'][:10] <= '2026-08-01']
    assert len(rows) == len(expected) > 100
    assert meta['status'] == 'COMPLETE'
    assert files['source_history.json'] == h
    assert meta['files']['events.json']['sha256'] == hashlib.sha256(files['events.json']).hexdigest()
    with pytest.raises(ValueError, match='digest'):
        prepare(h + b' ', m, 'DELL', '2026-08-01')
    with pytest.raises(ValueError, match='OUT_OF_RANGE'):
        prepare(h, m, 'DELL', '2099-01-01')


def test_export_rejects_manifest_bound_preview():
    h = json.loads((ROOT / 'docs/why/DELL.history.json').read_text())
    m = json.loads((ROOT / 'docs/why/history_manifest.json').read_text())
    h['collection']['completeness'] = 'PREVIEW'
    raw = json.dumps(h).encode()
    m['files']['DELL'].update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
    with pytest.raises(ValueError, match='PREVIEW'):
        prepare(raw, json.dumps(m).encode(), 'DELL', '2026-08-01')


def test_counts_do_not_equate_events_with_filings():
    rows = [dict(available_as_of='2026-10-01T12:00:00Z', accession_number='A', evidence_type='INSIDER_SELL') for _ in range(3)]
    d = denominators(rows, '2026-10-02T00:00:00Z')
    assert (d['event_objects'], d['distinct_accessions']) == (3, 1)
    assert d['largest_type_share'] == 1 and d['independent_information_count'] is None


def test_confidence_normalization_and_missing_inputs():
    a = composite_anatomy({'c1': {'score': 1., 'confidence': .5}, 'c2': {'score': -1., 'confidence': 0.}}, 1., {'c1': .2, 'c2': .8})
    assert a['reconstructed_score'] == 1 and a['status'] == 'RECONCILED'
    assert a['weight_provenance'] == 'CURRENT_CONFIG_RECONCILIATION_ONLY'
    assert a['components'][0]['effective_weight'] == 1
    assert composite_anatomy({}, 0., {'c1': .2})['status'] == 'INCOMPLETE'


def test_profit_is_not_earnings_beat_and_comparison_is_not_proof():
    assert assess('EARNINGS_BEAT', 'Net earnings were $1.2 billion.')['status'] == 'UNSUPPORTED_COMPARISON'
    assert assess('EARNINGS_BEAT', 'EPS exceeded consensus estimates.')['status'] == 'TEXTUAL_COMPARISON_ONLY'
    assert assess('EARNINGS_BEAT', 'EPS fell below expectations.')['status'] == 'UNSUPPORTED_COMPARISON'
    from v3.extract.sourcelock import validate
    text = 'Net earnings were $1.2 billion.'
    event = dict(event_type='EARNINGS_BEAT', magnitude=.5, direction=1, confidence=.8, raw_excerpt=text, rationale='Reported earnings.')
    assert validate(event, text, 'ZZFX')[0] is False
    event['event_type'] = 'EARNINGS_RESULT'
    assert validate(event, text, 'ZZFX')[0] is True
    event['confidence'] = float('inf')
    assert validate(event, text, 'ZZFX')[0] is False


def test_comparison_word_matches_displayed_values():
    assert comparative_return(.0415, .0406) == 'exceeds the universe'
    assert comparative_return(.04, .05) == 'trails the universe'
    assert comparative_return(.04000001, .04) == 'matches the universe at displayed precision'


def test_external_pin_is_required_and_wrong_pin_is_rejected(bundle, tmp_path):
    path = tmp_path / 'bundle.json'; path.write_text(json.dumps(bundle))
    ledger = tmp_path / 'ledger.jsonl'; ledger.write_text('{}\n')
    assert R.main([str(path), '--ledger', str(ledger)]) == 1
    assert R.main([str(path), '--ledger', str(ledger), '--ledger-sha256', '0' * 64]) == 1


def test_viewport_must_measure_the_requested_file_not_a_404():
    from tools.check_viewport import response_problem
    assert response_problem(404, 'text/html', b'<h1>Not found</h1>', b'<h1>YUCLAW</h1>')
    assert response_problem(200, 'text/html', b'<h1>Another page</h1>', b'<h1>YUCLAW</h1>')
    assert response_problem(200, 'text/html; charset=utf-8', b'<h1>YUCLAW</h1>', b'<h1>YUCLAW</h1>') is None


def test_negated_earnings_comparison_is_not_supported():
    assert assess('EARNINGS_BEAT', 'EPS did not beat expectations.')['status'] == 'UNSUPPORTED_COMPARISON'


def test_equivalent_cutoff_timezones_select_identical_rows():
    h = (ROOT / 'docs/why/DELL.history.json').read_bytes()
    m = (ROOT / 'docs/why/history_manifest.json').read_bytes()
    a, am = prepare(h, m, 'DELL', '2026-08-01T23:00:00Z')
    b, bm = prepare(h, m, 'DELL', '2026-08-02T07:00:00+08:00')
    assert a['events.json'] == b['events.json']
    assert am['as_of_utc'] == bm['as_of_utc']


def test_responsive_tables_preserve_canonical_text_and_are_idempotent():
    from v3.web.useful_blocks import responsive_research_page
    protected = '<!-- mv-html:begin -->\n<p>Owner mission and vision</p>\n<!-- mv-html:end -->'
    html = '<html><head></head><body>' + protected + '<table><tr><td>Long data row</td></tr></table></body></html>'
    result = responsive_research_page(html)
    assert protected in result
    assert 'tabindex="0"' in result and 'overflow-x:auto' in result
    assert result == responsive_research_page(result)


def test_current_routes_keep_historical_guides_separate():
    from tools.check_viewport import routes
    current, archived = routes()
    assert 'why/DELL.html' in current
    assert 'research_start.html' not in current and 'research_start.html' not in archived  # removed 2026-10-28
    assert 'YUCLAW_User_Guide_v5.1_source.html' in archived
    assert 'archive/YUCLAW_User_Guide_v5.0_source.html' in archived


def test_malformed_export_inputs_are_refused():
    for bad in [b'[]', b'{"schema":1,"schema":2}', b'{"x":NaN}']:
        with pytest.raises(ValueError):
            prepare(bad, b'{}', 'DELL', '2026-08-01')


def _legacy_shape(b):
    # The bundle in the tree is schema-less (legacy) on a tree without a database export and lab-replay/2 after a live export
    # (Spark, 2026-10-14); the cases below are stated on an explicit legacy shape so they hold for both.
    b = copy.deepcopy(b); b.pop('schema', None)
    for p in b['panels'].values():
        p.pop('trading_dates', None); p.pop('observation_units', None)
        for rb in p['rebalances']:
            rb.pop('snapshot_ids', None)
        for row in p.get('ic_rows', []):
            row.pop('snapshot_id', None)
    return b


def test_new_replay_schema_cannot_silently_omit_identity_fields(bundle, tmp_path):
    legacy = _legacy_shape(bundle)
    assert run_bundle(legacy, tmp_path) == 0            # legacy compatibility: a schema-less bundle without identity fields still reproduces
    b = copy.deepcopy(legacy); b['schema'] = 'lab-replay/2'
    assert run_bundle(b, tmp_path) == 1                 # the new schema cannot silently omit the identity fields


def test_a_live_v2_bundle_is_refused_when_any_identity_field_is_dropped(bundle, tmp_path):
    if bundle.get('schema') != 'lab-replay/2':
        pytest.skip('the tree carries a legacy bundle (no live export on this host)')
    assert run_bundle(bundle, tmp_path) == 0
    for drop in ('trading_dates', 'observation_units', 'snapshot_ids', 'ic_snapshot_id'):
        b = copy.deepcopy(bundle)
        for p in b['panels'].values():
            if drop == 'snapshot_ids':
                p['rebalances'][0].pop('snapshot_ids')
            elif drop == 'ic_snapshot_id':
                p['ic_rows'][0].pop('snapshot_id')
            else:
                p.pop(drop)
        assert run_bundle(b, tmp_path) == 1, drop
