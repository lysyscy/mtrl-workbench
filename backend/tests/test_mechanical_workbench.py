"""Public workbench behavior on the guarded PostgreSQL rollback fixture."""

from decimal import Decimal
from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core import db
from app.core.errors import MustReportError
from app.mod01_projects.models import Project
from app.mod06_proc.models import ProcMechManual
from app.mod06_proc.workbench_models import MechanicalWorkbenchRecord, MechanicalWorkbenchPreview
from app.mod06_proc import workbench as W


@pytest.fixture
def session(rollback_db, monkeypatch):
    assert rollback_db.dialect.name == 'postgresql'
    for model in (MechanicalWorkbenchPreview, MechanicalWorkbenchRecord, ProcMechManual):
        rollback_db.execute(model.__table__.delete())
    from app.mod01_projects import service as projects
    original_all, original_index = projects.all_projects, projects.warehouse_index
    owned = lambda wh: wh in ('甲', '乙') or str(wh).startswith('隔离项目')
    # Keep unrelated committed project fixtures in place; query the real owner
    # service and restrict only this test's visible archive scope.
    monkeypatch.setattr(projects, 'all_projects', lambda s: [p for p in original_all(s) if owned(p.warehouse_name)])
    monkeypatch.setattr(projects, 'warehouse_index', lambda s: {wh: p for wh, p in original_index(s).items() if owned(wh)})
    factory = db.get_session_factory()
    with factory() as s:
        for order, wh in enumerate(('甲', '乙')):
            project = s.scalar(select(Project).where(Project.warehouse_name == wh))
            if project is None:
                project = Project(warehouse_name=wh)
                s.add(project)
            project.name_full, project.disp, project.phid, project.ord = wh + '项目', '', '', order
        s.commit()
        yield s
        s.rollback()


def row(**values):
    return {'id': 'a', 'device': '升降车', 'amount': '103.00', 'rate': '103.00',
            'tax': '3%专', 'qty': '1', 'plate': '', 'date': '1日至3日', **values}


def save(s, rows=None, revision=0, cat='zero', ym='2026-09'):
    return W.action(s, 'details-save', {'warehouse': '甲', 'ym': ym, 'category': cat,
                                      'revision': revision, 'rows': [row()] if rows is None else rows})


def test_page_state_preserves_amounts_signatures_and_all_month_reconciliation_without_source_copies(monkeypatch):
    """A captured read model exercises historical/future facts without a database."""
    from app.mod07_setl import service as meetings

    projects = [SimpleNamespace(warehouse_name=wh, disp=wh + '项目', phid='', ord=i, id=i)
                for i, wh in enumerate(('甲', '乙'))]
    monkeypatch.setattr(W.project_service, 'all_projects', lambda s: projects)
    monkeypatch.setattr(meetings, 'opening_months', lambda s, warehouses, months: {
        wh: {month: '2024-03' if wh == '甲' else None for month in months} for wh in warehouses})
    sources = {'__detail_sources': {'mech_2': {'mode': 'detail', 'basis': {'rows': [row()], 'source': {'file': '原报.xlsx'}}}},
               'archive': {'original': ['raw']}}
    manual = [ProcMechManual(warehouse_name='甲', ym=month, mech_1=Decimal('0'), mech_2=Decimal(value),
                             mech_3=Decimal('0'), source_batches=sources, updated_at=datetime(2026, 11, 2))
              for month, value in [('2026-08', '10'), ('2026-09', '103'), ('2026-10', '20')]]
    current_row = row(source={'file': '原报.xlsx', 'sheet': '零租'}, lineage={'stable_id': 'original-a'})
    detail = {'warehouse': '甲', 'ym': '2026-09', 'category': 'zero', 'rows': [current_row],
              'baseline_rows': [row()], 'versions': [{'rows': [row()]}], 'source': {'file': '原报.xlsx'}}
    history = {'warehouse': '甲', 'base_month': '2026-08', 'category_totals': {
        'zero': '10.00', 'monthly': '0.00', 'internal': '0.00', 'company': None, 'weekly': None},
        'report_total': '10.00', 'i6': '1.00', 'source': {'kind': 'cumulative-opening', 'note': '已核'},
        'effective_base': {'2026-08': {'mech_2': '10.00', 'mech_1': '0.00', 'mech_3': '0.00'}},
        'reference_months': {'2026-08': {'mech_2': '10.00', 'mech_1': '0.00', 'mech_3': '0.00'}},
        'original_months': {'2026-08': {'weekly': '9.00'}, '2026-09': {'weekly': '7.00'}},
        'annual_rows': [{'cells': {'A': 'raw'}}]}
    document = {'id': 't', 'bill': '单据1', 'periodKey': 'unknown', 'amount': '3.00', 'approval': '4.00',
                'source': {'raw': ['original response']}}
    i8 = {'warehouse': '甲', 'sources': {'usage': [], 'project': [], 'team': [document]},
          'totals': {'usage': '1.00', 'project': '0.00', 'team': '4.00'}, 'unknown_documents': [document]}
    payloads = [(W.key('details', '甲', '2026-09', 'zero'), detail),
                (W.key('details', '甲', '2026-08', 'zero'), {**detail, 'ym': '2026-08'}),
                (W.key('history', '甲'), history), (W.key('i8', '甲'), i8),
                (W.key('adoption', '甲', '2026-10'), {'columns': ['mech_2'], 'versions': {'mech_2': 3}})]
    records = [SimpleNamespace(key=key, payload=payload, revision=1) for key, payload in payloads]

    class CapturedSession:
        def scalars(self, statement):
            return records if statement.column_descriptions[0]['entity'] is W.Record else manual

    captured = CapturedSession()
    full = W.state(captured, '2026-09')

    class SourceWithoutCopies(dict):
        def __deepcopy__(self, memo):
            raise AssertionError('page tried to clone discarded source/history facts')

    for field in ('baseline_rows', 'versions', 'source'):
        # Only the row-level provenance is editable and must still be copied.
        detail[field] = SourceWithoutCopies({'unused': detail[field]})
    history['annual_rows'] = SourceWithoutCopies({'unused': history['annual_rows']})
    document['source'] = SourceWithoutCopies(document['source'])
    manual[0].source_batches = SourceWithoutCopies(sources)
    manual[1].source_batches = SourceWithoutCopies(sources)
    page = W.page_state(captured, '2026-09')
    assert page['months'] == full['months'] == ['2026-08', '2026-09', '2026-10']
    assert page['projects'] == full['projects'] and page['settings'] == full['settings']
    assert len(page['details']) == 1
    assert page['details'][0] == {field: full['details'][0][field] for field in (
        'warehouse', 'ym', 'category', 'rows', 'revision', 'totals', 'issues')}
    assert page['details'][0]['rows'][0]['source'] == current_row['source']
    assert page['details'][0]['rows'][0]['lineage'] == current_row['lineage']
    full_current = [item for item in full['effective'] if item['ym'] == '2026-09']
    assert [{key: item[key] for key in ('warehouse', 'ym', 'values', 'signature')} for item in page['effective']] == [
        {key: item[key] for key in ('warehouse', 'ym', 'values', 'signature')} for item in full_current]
    assert all(set(item) == {'warehouse', 'ym', 'values', 'signature', 'sources'} for item in page['effective'])
    assert page['effective'][0]['sources']['mech_2'] == {'mode': 'detail'}
    assert page['summary'] == [item for item in full['summary'] if item['ym'] == '2026-09']
    assert page['history_bases'] == full['history_bases']
    report = next(item for item in page['reconciliations'] if item['warehouse'] == '甲' and item['relation'] == 'report')
    assert report['left'] == '133.00'  # October still participates when September is displayed.
    assert report['left'] == full['reconciliations'][0]['left']
    assert page['billDifferences'][0]['difference'] == full['billDifferences'][0]['difference'] == '1.00'
    assert 'source' not in page['billDifferences'][0] and 'source' not in page['i8'][0]['sources']['team'][0]
    assert page['histories'] == [{'warehouse': '甲', 'revision': 1, 'original_months': {'2026-09': {'weekly': '7.00'}}}]
    assert page['company_rows'][0]['values'] == ['1', '甲项目', '2024', '3', '113.00', '0.00', None,
                                               '0.00', None, '103.00', '0.00', None, '0.00', None, None]
    assert page['company_rows'][1]['values'][4:] == [None] * 11
    # Initialization protection must notice a non-displayed month's per-column adoption.
    records[-1].payload['versions']['mech_2'] = 4
    assert W.page_state(captured, '2026-09')['history_bases'][0]['signature'] != page['history_bases'][0]['signature']


def test_saved_details_and_unique_effective_source_roundtrip(session):
    saved = save(session)
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] == '103.00'
    assert saved['totals'] == {'gross': '103.00', 'net': '100.00'}
    result = W.effective(session, '甲', '2026-09')
    assert result['values']['mech_2'] == '103.00'
    assert result['values']['mech_4'] == '100.00'
    assert session.scalar(select(ProcMechManual)).mech_2 == Decimal('103.00')
    s = save(session, [row(amount='206.00')], revision=1)
    assert s['totals']['gross'] == '206.00'
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] == '206.00'
    session.commit()
    with Session(session.bind, join_transaction_mode='create_savepoint') as reopened:
        assert W.state(reopened)['details'][0]['rows'][0]['date'] == '1日至3日'
        assert W.state(reopened)['effective'][0]['values']['mech_2'] == '206.00'


def test_stale_detail_revision_never_overwrites_effective_amount(session):
    saved = save(session)
    with pytest.raises(MustReportError, match='其他操作'):
        save(session, revision=0)
    assert W.effective(session, '甲', '2026-09')['values']['mech_2'] == '103.00'


def test_plate_shared_keywords_clear_and_legacy_monthly(session):
    value = save(session, [row(device='汽车吊')])
    assert value['issues'] == [{'id': 'a', 'fields': ['车牌']}]
    W.action(session, 'settings', {'revision': 0, 'plate_keywords': [' 吊 ', '吊', '', '升降']})
    assert W.settings(session)['plate_keywords'] == ['吊', '升降']
    assert not W.detail_view(session, value, 1)['issues']
    W.action(session, 'settings', {'revision': 1, 'plate_keywords': []})
    assert save(session, revision=1)['issues'][0]['fields'] == ['车牌']
    assert not save(session, cat='monthly', ym='2026-05')['issues']
    assert save(session, [row(tax='', qty=None, rate='200.00')], cat='monthly', ym='2026-04')['totals'] == {'gross': '103.00', 'net': None}


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-1', True])
def test_invalid_amount_never_saved(session, value):
    with pytest.raises(MustReportError):
        save(session, [row(amount=value)])
    assert not W.state(session)['details']


def test_three_way_source_conflicts_and_idempotent_recording(session):
    source = {'file': 'source.xlsx', 'sha256': 'x', 'sheet': '表2', 'row': 5}
    def record(rows, rid, **extra):
        revision = W.read(session, W.key('details', '甲', '2026-08', 'zero'))[1]
        return W.record_details(session, {'request_id': rid, 'batches': [{'warehouse': '甲', 'ym': '2026-08',
                    'category': 'zero', 'revision': revision, 'rows': rows, 'source': source}], **extra})
    record([row(tax='3%专', plate='错')], 'one')
    W.save_details(session, {'warehouse': '甲', 'ym': '2026-08', 'category': 'zero', 'revision': 1,
                             'rows': [row(tax='普票', plate='错')]})
    result = record([row(tax='3%专', plate='苏A12345')], 'two')
    saved = W.read(session, W.key('details', '甲', '2026-08', 'zero'))[0]
    assert saved['rows'][0]['tax'] == '普票'
    assert saved['rows'][0]['plate'] == '苏A12345'
    assert record([row(tax='3%专', plate='苏A12345')], 'two') == result
    with pytest.raises(MustReportError, match='修订冲突'):
        record([row(tax='6%专', plate='苏A12345')], 'three')
    record([row(tax='6%专', plate='苏A12345')], 'three', resolutions={'a:tax': 'current'})
    assert W.state(session)['details'][0]['rows'][0]['tax'] == '普票'


def test_source_precision_cached_net_and_invoice_text(session):
    rows = [row(id='a', amount='0.335', original='0.335', sourceNet='0.32524', originalTax='3%专'),
            row(id='b', amount='0.335', original='0.335', sourceNet='0.32524', originalTax='3%专')]
    saved = save(session, rows)
    assert saved['totals'] == {'gross': '0.67', 'net': '0.65'}
    assert saved['rows'][0]['sourceNet'] == '0.32524'
    assert W.row_net(row(tax='1%普票，不含油')) == '103.00'


def test_unapproved_unknown_document_is_retained_outside_approved_total(session):
    item = i8_project()
    item['sources']['team'].append({'id': 'unapproved', 'amount': None, 'approval': None, 'status': 0, 'workflow': 0})
    adopt_i8(session, [item])
    saved = W.state(session)['i8'][0]
    assert saved['totals']['team'] == '100.00'
    assert saved['unknown_documents'][0]['id'] == 'unapproved'
    assert saved['unknown_documents'][0]['approval'] is None


def i8_project(wh='甲', usage='100.12', settlement='100.08', approval='100.00', extra=None):
    sources = {'usage': [{'id': 'u', 'amount': usage}], 'project': [],
               'team': [{'id': 't', 'amount': settlement, 'approval': approval, 'periodKey': 'unknown-old-key', 'bill': 'JXXHD01'}]}
    if extra:
        sources['usage'].append(extra)
    return {'warehouse': wh, 'sources': sources, 'complete': dict.fromkeys(sources, True), 'fetched_at': '2026-10-17'}


def adopt_i8(s, projects, rid='i8', **options):
    p = W.i8_preview(s, {'projects': projects, 'request_id': rid, 'full_scope': True})
    W.i8_confirm(s, {'preview_id': p['preview_id'], 'warehouses': [p['warehouse'] for p in projects], **options})
    return p


def test_i8_single_project_independent_ignores_and_change_discovery(session):
    adopt_i8(session, [i8_project(), i8_project('乙')])
    checks, bills = W.reconciliations(session, ['甲'])
    internal = next(r for r in checks if r['relation'] == 'internal')
    assert internal['raw'] == '0.12'
    assert bills[0]['difference'] == '-0.08'
    W.ignore(session, {'warehouse': '甲', 'relation': 'internal', 'revision': 0})
    assert W.reconciliations(session, ['甲'])[0][1]['pending'] == '0.00'
    assert not W.reconciliations(session, ['甲'])[1][0]['ignored']
    W.document_ignore(session, {'warehouse': '甲', 'document_id': 't', 'revision': 0})
    old_other = W.read(session, W.key('i8', '乙'))
    adopt_i8(session, [i8_project(usage='200.12', settlement='101.00')], 'changed')
    checks, bills = W.reconciliations(session, ['甲'])
    assert checks[1]['pending'] == '100.00'
    assert not bills[0]['ignored']
    assert bills[0]['periodKey'] == 'unknown-old-key'
    assert W.read(session, W.key('i8', '乙')) == old_other
    assert any(d['warehouse'] == '乙' and d['kind'] == 'missing-project' for d in W.state(session)['discoveries'])


def test_missing_incomplete_unknown_and_reduction_are_protected(session):
    adopt_i8(session, [i8_project(extra={'id': 'u2', 'amount': '1.00'})])
    p = W.i8_preview(session, {'request_id': 'drop', 'projects': [i8_project()]})
    assert p['projects'][0]['missing'] == ['usage:u2']
    with pytest.raises(MustReportError, match='采用依据'):
        W.i8_confirm(session, {'preview_id': p['preview_id'], 'warehouses': ['甲']})
    W.i8_confirm(session, {'preview_id': p['preview_id'], 'warehouses': ['甲'], 'allow_reduction': True, 'reduction_reason': '已核实作废'})
    incomplete = i8_project()
    incomplete['complete']['team'] = False
    p = W.i8_preview(session, {'request_id': 'incomplete', 'projects': [incomplete]})
    with pytest.raises(MustReportError, match='三类来源'):
        W.i8_confirm(session, {'preview_id': p['preview_id'], 'warehouses': ['甲']})
    unknown = i8_project(approval=None)
    adopt_i8(session, [unknown], 'unknown')
    assert W.reconciliations(session, ['甲'])[0][1]['raw'] is None


def test_existing_history_delta_is_replacement_and_matter_does_not_change_amount(session):
    W.repo.save_mech(session, ym='2026-08', warehouse='甲', values={'mech_1': Decimal('14000'), 'mech_2': Decimal('5000')})
    history = {
        'base_month': '2026-09', 'report_total': '20000.00', 'i6': '1000.00', 'source': {'file': '表4'},
        'reference_months': {'2026-08': {'mech_1': '14000.00', 'mech_2': '5000.00', 'mech_3': '0.00'}},
        'effective_base': {'2026-08':W.effective(session,'甲','2026-08')['values']}}
    W.write(session,W.key('history','甲'),{'warehouse':'甲',**history},0)
    W.matter_save(session,{'id':'guofeng','warehouse':'甲','revision':0,'text':'下月少做500，未执行',
                          'metadata':{'original':'4500','adopted':'5000'}})
    assert W.report_total(session, '甲') == '20000.00'
    current = W.effective(session, '甲', '2026-08')
    W.internal_save(session, {'warehouse': '甲', 'ym': '2026-08', 'values': {'mech_1': '14500'}, 'effective_signature': current['signature']})
    assert W.report_total(session, '甲') == '20500.00'
    W.repo.save_mech(session, ym='2026-08', warehouse='甲', values={'mech_2': Decimal('4500')})
    assert W.report_total(session, '甲') == '20000.00'
    matter = W.state(session)['matters'][0]
    W.matter_save(session, {**matter, 'completed': True})
    assert W.report_total(session, '甲') == '20000.00'
    assert W.state(session)['matters'][0]['metadata']['adopted'] == '5000'


def test_initial_monthly_annual_conflict_does_not_rewrite_cumulative(session):
    W.repo.save_mech(session,ym='2026-02',warehouse='甲',values={'mech_2':Decimal('0.00')})
    W.write(session,W.key('history','甲'),{'warehouse':'甲',
        'source': {'file': 'history'}, 'base_month': '2026-09', 'report_total': '4850.00', 'i6': '0.00',
        'reference_months': {'2026-02': {'mech_2': '4850.00'}},
        'cumulative_at': {'2026-09': {'zero': '4850.00'}},
        'effective_base':{'2026-02':W.effective(session,'甲','2026-02')['values']}},0)
    assert W.report_total(session, '甲') == '4850.00'
    assert W.cumulative(session, '甲', '2026-09')['zero'] == '4850.00'
    W.repo.save_mech(session, ym='2026-02', warehouse='甲', values={'mech_2': Decimal('5000')})
    assert W.report_total(session, '甲') == '5000.00'
    assert W.cumulative(session, '甲', '2026-09')['zero'] == '5000.00'


def test_old_quantity_text_and_precision_survive_roundtrip(session):
    saved = save(session, [row(qty='0.5+', plan='2小时', used='0.111428571428571')])
    assert saved['rows'][0]['qty'] == '0.5+'
    assert saved['rows'][0]['plan'] == '2小时'
    assert saved['rows'][0]['used'] == '0.111428571428571'
    assert saved['totals']['gross'] == '103.00'


def test_ignore_negative_change_zero_and_undo_no_automatic_tolerance(session):
    adopt_i8(session, [i8_project(usage='99.88')])
    W.ignore(session, {'warehouse': '甲', 'relation': 'internal', 'revision': 0})
    adopt_i8(session, [i8_project(usage='0.88')], 'lower', allow_reduction=True, reduction_reason='核实减少')
    assert W.reconciliations(session, ['甲'])[0][1]['pending'] == '-99.00'
    with pytest.raises(MustReportError, match='已变化'):
        W.ignore(session, {'warehouse': '甲', 'relation': 'internal', 'revision': 1, 'raw': '-0.12'})
    W.ignore(session, {'warehouse': '甲', 'relation': 'internal', 'revision': 1, 'undo': True})
    assert W.reconciliations(session, ['甲'])[0][1]['pending'] == '-99.12'
    W.ignore(session, {'warehouse': '甲', 'relation': 'internal', 'revision': 2})
    adopt_i8(session, [i8_project(usage='100.00')], 'matched')
    assert W.reconciliations(session, ['甲'])[0][1]['pending'] == '0.00'


def test_same_amount_changed_document_is_discovered_but_order_is_not(session):
    original = i8_project(extra={'id': 'u2', 'amount': '1.00'})
    adopt_i8(session, [original])
    reordered = i8_project(extra={'id': 'u2', 'amount': '1.00'})
    reordered['sources']['usage'].reverse()
    same = W.i8_preview(session, {'request_id': 'reordered', 'projects': [reordered]})
    assert not same['projects'][0]['changed']
    changed = i8_project(extra={'id': 'replacement', 'amount': '1.00'})
    preview = W.i8_preview(session, {'request_id': 'different-document', 'projects': [changed]})
    assert preview['projects'][0]['totals'] == same['projects'][0]['totals']
    assert preview['projects'][0]['changed']
    assert preview['projects'][0]['missing'] == ['usage:u2']


def test_direct_recording_two_categories_updates_one_month(session):
    batches = [{'warehouse': '甲', 'ym': '2026-09', 'category': cat, 'source': {'file': '原件'},
                'rows': [row(id=cat)], 'revision':0} for cat in ('zero', 'monthly')]
    W.record_details(session, {'request_id': 'both', 'batches': batches})
    values = W.effective(session, '甲', '2026-09')['values']
    assert values['mech_2'] == values['mech_3'] == '103.00'
    assert values['mech_4'] == values['mech_5'] == '100.00'


def test_empty_month_has_signature_and_unknown_cumulative(session):
    result = W.state(session, '2026-11')
    assert len(result['effective']) == 2
    assert result['effective'][0]['signature']
    assert set(result['effective'][0]['values'].values()) == {None}
    assert result['summary'][0]['cumulative']['zero'] is None


def opening(s, **changes):
    basis = next(b for b in W.state(s)['history_bases'] if b['warehouse'] == '甲')
    return {'warehouse': '甲', 'revision': basis['revision'], 'effective_signature': basis['signature'],
            'base_month': '2026-09', 'category_totals': {'zero': '0', 'monthly': '0', 'internal': '0'},
            'i6': '0', 'note': '用户确认开工前无机械费及i6', **changes}


def test_new_project_details_opening_i8_and_reconciliation_form_one_chain(session):
    save(session, [row(amount='9600')], ym='2026-10')
    adopt_i8(session, [i8_project(usage='9599', approval='9599', settlement='9599')])
    report = W.reconciliations(session, ['甲'])[0][0]
    assert report['left'] is report['right'] is None
    assert report['recorded_total'] == '9600.00'
    assert report['recorded_months'] == ['2026-10']
    assert report['i8_usage'] == '9599.00'
    assert report['missing_reasons'] == ['累计起点待补', '固定i6待补']
    details_before = W.read(session, W.key('details', '甲', '2026-10', 'zero'))
    effective_before = W.effective(session, '甲', '2026-10')
    W.action(session, 'history-initialize', opening(session), 'test-operator')
    report = W.reconciliations(session, ['甲'])[0][0]
    assert (report['left'], report['right'], report['raw']) == ('9600.00', '9599.00', '1.00')
    assert report['missing_reasons'] == []
    assert W.cumulative(session, '甲', '2026-10')['zero'] == '9600.00'
    assert W.cumulative(session, '甲', '2026-08')['zero'] is None
    assert W.read(session, W.key('details', '甲', '2026-10', 'zero')) == details_before
    assert W.effective(session, '甲', '2026-10') == effective_before
    assert W.read(session, W.key('history', '甲'))[0]['source']['operator'] == 'test-operator'
    save(session, [row(amount='9700')], revision=1, ym='2026-10')
    assert W.report_total(session, '甲') == '9700.00'


def test_opening_requires_confirmed_values_and_current_month_signature(session):
    save(session, ym='2026-10')
    payload = opening(session)
    save(session, [row(amount='206')], revision=1, ym='2026-10')
    with pytest.raises(MustReportError, match='月值已变化'):
        W.action(session, 'history-initialize', payload)
    with pytest.raises(MustReportError, match='金额不能为空'):
        W.action(session, 'history-initialize', opening(session, i6=None))
    with pytest.raises(MustReportError, match='金额不能为空'):
        W.action(session, 'history-initialize', opening(session, category_totals={'zero': '0', 'monthly': '0'}))
    assert W.read(session, W.key('history', '甲'))[1] == 0
    payload = opening(session)
    W.action(session, 'history-initialize', payload)
    with pytest.raises(MustReportError, match='已有累计起点'):
        W.action(session, 'history-initialize', payload)


def test_opening_preserves_annual_reference_and_new_old_month_revisions(session):
    save(session, [row(amount='0')], ym='2026-02')
    W.initialize_history(session, opening(session, category_totals={'zero': '4850', 'monthly': '0', 'internal': '0'}),
                         reference_months={'2026-02': {'mech_2': '4850'}})
    assert W.report_total(session, '甲') == '4850.00'
    save(session, [row(amount='5000')], revision=1, ym='2026-02')
    assert W.report_total(session, '甲') == '5000.00'
    assert W.cumulative(session, '甲', '2026-09')['zero'] == '5000.00'
    W.repo.save_mech(session, ym='2026-03', warehouse='甲', values={'mech_2': Decimal('100')})
    assert W.report_total(session, '甲') == '5100.00'
    assert W.cumulative(session, '甲', '2026-09')['zero'] == '5100.00'


def test_opening_captures_only_the_validated_months_when_another_writer_inserts(session, monkeypatch):
    save(session, [row(amount='100')], ym='2026-09')
    session.commit()
    payload = opening(session, category_totals={'zero': '100', 'monthly': '0', 'internal': '0'})
    original = W.history_basis

    def insert_after_signature(*args, **kwargs):
        basis = original(*args, **kwargs)
        with Session(session.bind) as other:
            W.repo.save_mech(other, ym='2026-08', warehouse='甲', values={'mech_2': Decimal('50')})
            other.commit()
        return basis

    monkeypatch.setattr(W, 'history_basis', insert_after_signature)
    W.action(session, 'history-initialize', payload)
    assert W.report_total(session, '甲') == '150.00'
    assert W.cumulative(session, '甲', '2026-09')['zero'] == '150.00'


def test_preopening_adoptions_do_not_apply_until_that_column_is_adopted_again(session):
    save(session, [row(amount='0')], ym='2026-02')
    W.initialize_history(session, opening(session, category_totals={'zero': '4850', 'monthly': '0', 'internal': '0'}),
                         reference_months={'2026-02': {'mech_2': '4850'}})
    save(session, [row(amount='50')], cat='monthly', ym='2026-02')
    assert W.report_total(session, '甲') == '4900.00'
    assert W.cumulative(session, '甲', '2026-09')['zero'] == '4850.00'
    W.mark_adoption(session, '甲', '2026-02', ['mech_2'])
    assert W.report_total(session, '甲') == '50.00'
    assert W.cumulative(session, '甲', '2026-09')['zero'] == '0.00'


def test_opening_includes_a_later_filled_category_in_an_existing_old_month(session):
    save(session, [row(amount='100')], ym='2026-09')
    W.action(session, 'history-initialize', opening(session, category_totals={'zero': '100', 'monthly': '0', 'internal': '0'}))
    save(session, [row(amount='50')], cat='monthly', ym='2026-09')
    assert W.report_total(session, '甲') == '150.00'
    assert W.cumulative(session, '甲', '2026-09')['monthly'] == '50.00'


def test_first_empty_i8_is_checked_but_never_adopted_as_zero(session):
    empty = {'warehouse': '甲', 'projectId': '1', 'sources': {k: [] for k in ('usage', 'project', 'team')},
             'complete': {k: True for k in ('usage', 'project', 'team')},
             'fetched_at': '2026-11-02T00:00:00+00:00', 'scope': 'full', 'source_status': 'no-records'}
    preview = W.i8_preview(session, {'request_id': 'first-empty', 'projects': [empty]})
    assert not preview['projects'][0]['complete']
    assert set(preview['projects'][0]['totals'].values()) == {None}
    with pytest.raises(MustReportError, match='来源无记录'):
        W.i8_confirm(session, {'preview_id': preview['preview_id'], 'warehouses': ['甲']})
    assert W.read(session, W.key('i8', '甲'))[1] == 0
    checks = W.state(session)['reconciliations']
    report = next(r for r in checks if r['warehouse'] == '甲' and r['relation'] == 'report')
    assert report['i8_source_status'] == 'no-records'
    assert report['i8_checked_at'] == empty['fetched_at']
    assert '本次i8来源无记录' in report['missing_reasons']
    assert not W.state(session)['discoveries']
    adopt_i8(session, [i8_project()], 'later-available')
    assert W.reconciliations(session, ['甲'])[0][0]['i8_source_status'] == 'available'
    # Empty returns for an existing adopted identity remain an explicit reduction.
    preview = W.i8_preview(session, {'request_id': 'old-empty', 'projects': [empty]})
    assert preview['projects'][0]['complete'] and preview['projects'][0]['reduction']
    assert preview['projects'][0]['totals']['usage'] == '0.00'
    W.i8_confirm(session, {'preview_id': preview['preview_id'], 'warehouses': ['甲'],
                          'allow_reduction': True, 'reduction_reason': '已核实全部单据作废'})
    assert W.reconciliations(session, ['甲'])[0][0]['i8_usage'] == '0.00'


def test_i8_one_preview_can_confirm_projects_separately(session):
    preview = W.i8_preview(session, {'projects': [i8_project(), i8_project('乙')]})
    W.i8_confirm(session, {'preview_id': preview['preview_id'], 'warehouses': ['甲']})
    assert W.read(session, W.key('i8', '乙'))[1] == 0
    result = W.i8_confirm(session, {'preview_id': preview['preview_id'], 'warehouses': ['乙']})
    assert result['warehouses'] == ['乙', '甲']
    assert W.read(session, W.key('i8', '甲'))[1] == W.read(session, W.key('i8', '乙'))[1] == 1
    assert W.i8_confirm(session, {'preview_id': preview['preview_id'], 'warehouses': ['甲']}) == result


def test_unmapped_i8_project_persists_fact_without_creating_archive_or_amount(session):
    unknown = {'projectId': 'unknown-i8-id', 'projectName': '新发现原名', 'sources': i8_project()['sources'],
               'complete': {'usage': True, 'team': True, 'project': True}}
    W.i8_preview(session, {'request_id': 'unmapped', 'projects': [i8_project()], 'unmapped_projects': [unknown]})
    W.i8_preview(session, {'request_id': 'unmapped-again', 'unmapped_projects': [unknown]})
    discovered = [r for r in W.state(session)['discoveries'] if r['kind'] == 'unmapped']
    assert len(discovered) == 1
    assert discovered[0]['projectId'] == 'unknown-i8-id'
    assert discovered[0]['warehouse'] == ''
    assert len(W.state(session)['projects']) == 2
    assert not W.state(session)['effective']


@pytest.mark.parametrize('case', ['exact', 'changed', 'missing', 'duplicate-owner'])
def test_adoption_retires_only_fully_covered_unique_original_ownership_warning(session, case):
    from copy import deepcopy
    incoming = i8_project()
    for rows in incoming['sources'].values():
        for row in rows:
            row.update(projectId='shell-id', title='大唐雷州')
    unknown = {'projectId': 'shell-id', 'sources': deepcopy(incoming['sources'])}
    W.i8_preview(session, {'request_id': 'unmapped', 'unmapped_projects': [unknown]})
    if case == 'changed':
        incoming['sources']['usage'][0]['amount'] = '200.00'
    elif case == 'missing':
        incoming['sources']['team'] = []
    projects = [incoming]
    if case == 'duplicate-owner':
        projects.append({**deepcopy(incoming), 'warehouse': '乙'})
    preview = W.i8_preview(session, {'request_id': 'mapped', 'projects': projects})
    warning = lambda: next(d for d in W.state(session)['discoveries'] if d['kind'] == 'unmapped')
    assert warning()['status'] == 'pending'
    W.i8_confirm(session, {'preview_id': preview['preview_id'], 'warehouses': [p['warehouse'] for p in projects]})
    assert warning()['status'] == ('resolved' if case == 'exact' else 'pending')
    assert warning()['sources'] == W.normalize_sources(unknown['sources'])
    if case == 'exact':
        assert warning()['mapped_warehouses'] == ['甲']
    assert not W.state(session)['effective']


def test_state_batches_reads_and_returns_independent_history_values(session):
    from copy import deepcopy
    from time import perf_counter
    from sqlalchemy import event

    warehouses = ['甲', '乙', *[f'隔离项目{i}' for i in range(22)]]
    session.add_all(Project(warehouse_name=wh, name_full=wh) for wh in warehouses[2:])
    months = [f'2026-{month:02d}' for month in range(1, 10)]
    references = {ym: {f'mech_{i}': '0.00' for i in range(6)} for ym in months}
    source_cells = {f'A{i}': {'raw': '原报坐标及原文', 'cache': str(i), 'cell': f'A{i}',
                              'formula': '=SUM(B1:B20)'} for i in range(1000)}
    for wh in warehouses:
        history = {'warehouse': wh, 'base_month': '2026-09', 'report_total': '273.45', 'i6': '10.00',
                   'reference_months': deepcopy(references), 'effective_base': deepcopy(references),
                   'cumulative_at': {ym: {'zero': '123.45', 'monthly': '100.00', 'internal': '50.00',
                                          'company': '75.00', 'weekly': '0.00'} for ym in months},
                   'annual_rows': [{'source_cells': deepcopy(source_cells)}]}
        session.add(MechanicalWorkbenchRecord(key=W.key('history', wh), revision=1, payload=history))
        session.add_all(ProcMechManual(warehouse_name=wh, ym=ym, source_batches={}) for ym in months)
    session.add(MechanicalWorkbenchRecord(key=W.key('details', '甲', '2026-09', 'zero'), revision=1,
        payload={'warehouse': '甲', 'ym': '2026-09', 'category': 'zero',
                 'rows': [row(id=str(i)) for i in range(1966)], 'versions': [{'source': {'file': '历史原件'}}]}))
    session.commit()
    session.expunge_all()
    queries = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith('SELECT'):
            queries.append(statement)

    event.listen(session.bind, 'before_cursor_execute', capture)
    started = perf_counter()
    try:
        result = W.state(session, '2026-09')
    finally:
        elapsed = perf_counter() - started
        event.remove(session.bind, 'before_cursor_execute', capture)
    print(f'mechanical state: {len(queries)} SQL, {elapsed:.3f}s')
    # 64b5948 added the AnalysisBigManual batch; the scale/carry test proves four fixed reads.
    assert len(queries) == 4
    assert len(result['summary']) == 216
    assert result['summary'][0]['cumulative']['zero'] == '123.45'
    assert result['reconciliations'][0]['left'] == '273.45'
    assert len(result['details'][0]['rows']) == 1966
    assert result['details'][0]['totals']['gross'] == '202498.00'
    result['histories'][0]['annual_rows'][0]['source_cells']['A1']['raw'] = '仅改回包'
    result['details'][0]['versions'][0]['source']['file'] = '仅改回包'
    unchanged = W.state(session, '2026-09')
    assert unchanged['histories'][0]['annual_rows'][0]['source_cells']['A1']['raw'] == '原报坐标及原文'
    assert unchanged['details'][0]['versions'][0]['source']['file'] == '历史原件'
    W.repo.save_mech(session, ym='2026-09', warehouse='甲', values={'mech_2': Decimal('25.00')})
    assert W.report_total(session, '甲') == '298.45'
    assert W.state(session, '2026-09')['summary'][8]['cumulative']['zero'] == '148.45'


def test_project_reads_use_owner_service_and_preserve_archive_fields(session, monkeypatch):
    from app.mod01_projects import service as projects

    project = session.scalar(select(Project).where(Project.warehouse_name == '甲'))
    project.disp, project.phid, project.ord = '真实展示名', 'i8-original-id', 10
    session.flush()
    original_all, original_index = projects.all_projects, projects.warehouse_index
    calls = []

    def all_projects(s):
        calls.append('all')
        return original_all(s)

    def warehouse_index(s):
        calls.append('index')
        return original_index(s)

    monkeypatch.setattr(projects, 'all_projects', all_projects)
    monkeypatch.setattr(projects, 'warehouse_index', warehouse_index)
    assert W.warehouse(session, '甲') == '甲'
    result = W.state(session, '2026-09')
    assert calls == ['index', 'all']
    assert result['projects'] == [
        {'warehouse': '乙', 'name': '乙', 'phid': ''},
        {'warehouse': '甲', 'name': '真实展示名', 'phid': 'i8-original-id'},
    ]


def test_resolved_discovery_reopens_only_after_another_observed_fact(session):
    first = adopt_i8(session, [i8_project()], 'fact-a')
    a = next(d for d in W.state(session)['discoveries'] if d['id'] == first['projects'][0]['discovery_id'])
    W.discovery_resolve(session, {**a, 'note': '本轮无需补报A'})
    W.i8_preview(session, {'request_id': 'fact-a-repeat', 'projects': [i8_project()]})
    assert not [d for d in W.state(session)['discoveries'] if d['status'] == 'pending']
    second = adopt_i8(session, [i8_project(usage='200.12')], 'fact-b')
    b = next(d for d in W.state(session)['discoveries'] if d['id'] == second['projects'][0]['discovery_id'])
    W.discovery_resolve(session, {**b, 'note': '本轮无需补报B'})
    W.i8_preview(session, {'request_id': 'fact-a-returned', 'projects': [i8_project()]})
    pending = [d for d in W.state(session)['discoveries'] if d['status'] == 'pending']
    assert len(pending) == 1 and pending[0]['id'] == a['id']


def test_confirm_old_company_month_replaces_historical_component(session):
    W.repo.save_mech(session,ym='2026-02',warehouse='甲',values={'mech_0':Decimal('100')})
    W.write(session,W.key('history','甲'),{'warehouse':'甲','base_month':'2026-09',
        'cumulative_at':{'2026-02':{'company':'100'}},
        'original_months':{'2026-02':{'mech_0':'100'}},
        'effective_base':{'2026-02':W.effective(session,'甲','2026-02')['values']}},0)
    current = W.effective(session, '甲', '2026-02')
    assert W.cumulative(session, '甲', '2026-02')['company'] == '100.00'
    W.internal_save(session, {'warehouse': '甲', 'ym': '2026-02', 'values': {'mech_0': '150.00'},
                              'effective_signature': current['signature']})
    assert W.cumulative(session, '甲', '2026-02')['company'] == '150.00'


def test_postgresql_effective_and_preview_queries_acquire_row_share_locks(session):
    assert session.bind.dialect.name == 'postgresql'
    W.repo.save_mech(session, ym='2026-09', warehouse='甲', values={'mech_2': Decimal('103.00')})
    preview = W.i8_preview(session, {'projects':[i8_project()]})
    W.effective(session, '甲', '2026-09', lock=True)
    W.get_preview(session, {'preview_id': preview['preview_id']}, 'i8')
    locks = set(session.execute(text("SELECT relation::regclass::text FROM pg_locks "
                                    "WHERE pid=pg_backend_pid() AND mode='RowShareLock' AND granted")).scalars())
    assert {'proc_mech_manual', 'mechanical_workbench_preview'} <= locks


def test_start_date_uses_big_table_as_of_month_read_only(session):
    from app.mod07_setl import big_repository as big
    from app.mod07_setl.models import AnalysisBigManual
    session.query(AnalysisBigManual).filter(AnalysisBigManual.warehouse_name.in_(['甲','乙'])).delete(synchronize_session=False)
    big.save_cell(session, ym='2026-08', warehouse='甲', key='open_ym', value='2024-03')
    big.save_cell(session, ym='2026-10', warehouse='甲', key='open_ym', value='2025-06')
    W.write(session, W.key('history','甲'), {'warehouse':'甲','meta_at':{'2026-09':{'year':1999,'month':1}}}, 0)
    september = W.state(session, '2026-09')
    row = next(r for r in september['summary'] if r['warehouse']=='甲' and r['ym']=='2026-09')
    assert (row['start_year'], row['start_month']) == (2024,3)
    missing = next(r for r in september['summary'] if r['warehouse']=='乙' and r['ym']=='2026-09')
    assert missing['start_year'] is None and missing['start_month'] is None
    october = W.snapshot(session, '2026-10', ['甲'])
    row = next(r for r in october['summary'] if r['warehouse']=='甲' and r['ym']=='2026-10')
    assert (row['start_year'], row['start_month']) == (2025,6)
    assert big.load_manual(session)['2026-08']['甲']['open_ym']=='2024-03'
    assert W.read(session,W.key('history','甲'))[0]['meta_at']['2026-09']['year']==1999
