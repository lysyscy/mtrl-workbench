"""离线测量判据与预览身份保护；现场采集由 frontend_measure.py run 显式执行。"""
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.dev.frontend_measure import quality, regressions, write_json
import pytest


def row(n=1, *, ready=444, main=446):
    return dict(kind='warm', route='contracts', sample=n, ready_ms=ready,
                main_thread_ms=main, transfer_bytes=100, fcp_ms=None, lcp_ms=None,
                cls=0, layout_shift_all=0, observed_blocking_ms=0,
                font_loaded=True, font_status='loaded', content_chars=100,
                errors=[], bad_responses=[], failed_requests=[])


def test_character_check_does_not_imply_font_set_stable():
    sample = row()
    sample['font_status'] = 'loading'
    result = quality([sample], expected=Counter({('warm', 'contracts'):1}))
    assert result['ok']
    assert not result['font_set_stable_for_all_samples']
    assert result['warnings'] == [{'sample':['warm','contracts',1], 'reason':'font-set-still-loading'}]


def test_navigation_host_transport_is_not_user_latency():
    actions = [dict(action='inventory-return', next_two_frames_ms=2100, api=[{'path':'/api/m08/inventory'}])]
    result = quality([row()], interactions=actions)
    assert result['ok']
    assert not result['navigation_automation_time_is_user_latency']
    assert result['warnings'][0]['reason'] == 'navigation-automation-time-not-user-latency'
    actions[0] = dict(action='inventory-input', api=[{'path':'/api/m08/inventory'}])
    assert not quality([row()], interactions=actions)['ok']


@pytest.mark.parametrize('damage', ['request', 'duplicate', 'missing', 'nonfinite'])
def test_invalid_samples_cannot_pass_screen(damage):
    rows = [row(1), row(2), row(3)]
    if damage == 'request': rows[0]['failed_requests'] = [{'failure':'aborted'}]
    if damage == 'duplicate': rows[1]['sample'] = 1
    if damage == 'missing': rows.pop()
    if damage == 'nonfinite': rows[0]['ready_ms'] = float('nan')
    assert not quality(rows, expected=Counter({('warm', 'contracts'):3}))['ok']


def test_large_regression_is_reported_but_small_noise_is_not():
    baseline = [dict(kind='warm', route='contracts', ready_ms={'median':501}, main_thread_ms={'median':513})]
    assert not regressions([row(i) for i in range(1, 4)], baseline)
    hits = regressions([row(i, ready=782, main=831) for i in range(1, 4)], baseline)
    assert {x['metric'] for x in hits} == {'ready_ms', 'main_thread_ms'}
    # Both bounds must hold: this is an alarm, not a statistical significance claim.
    assert not regressions([row(i, ready=550, main=540) for i in range(1, 4)], baseline)


def test_outputs_never_overwrite_existing_evidence(tmp_path):
    path = tmp_path/'quality.json'
    write_json(path, {'original':True})
    with pytest.raises(FileExistsError): write_json(path, {'replacement':True})
    assert path.read_text(encoding='utf-8').find('original') >= 0


@pytest.mark.parametrize('damage', ['port', 'schema', 'instrumented', 'asset'])
def test_preview_guard_rejects_unsafe_or_changed_input(tmp_path, monkeypatch, damage):
    import hashlib
    import json
    from tools.dev import frontend_measure as m
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    run = tmp_path/'.artifacts/active/fixture/run'
    build = run/'work/dist'
    build.mkdir(parents=True)
    (run/'reports').mkdir()
    (build/'index.html').write_text('fixture', encoding='utf-8')
    digest = hashlib.sha256(b'fixture').hexdigest()
    owner = dict(status='ready', host='127.0.0.1', port=8065, read_only=True,
                 database='mtrl_workbench_test', schema='fixture', preview_account='preview-user',
                 cookie_name='mw_real_preview_fixture', index_sha256=digest)
    version = dict(build_path=str(build), index_sha256=digest, diagnostic_instrumentation=False,
                   files={'index.html':digest})
    if damage == 'port': owner['port'] = 8000
    if damage == 'schema': owner['schema'] = 'public'
    if damage == 'instrumented': version['diagnostic_instrumentation'] = True
    if damage == 'asset': (build/'index.html').write_text('changed', encoding='utf-8')
    for name, value in [('real_owner', owner), ('version', version)]:
        (run/f'reports/{name}.json').write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises(ValueError): m.preview_identity(run)
