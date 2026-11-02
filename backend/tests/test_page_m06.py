"""过程资料组装、历史读取与机械手录的工程回归。"""
from __future__ import annotations

import copy
from decimal import Decimal

import pytest

from app.core import preview_store
from app.core.errors import MustReportError
from app.mod06_proc import domain as D, mech_ui, repository as repo
from app.mod06_proc.models import ProcCutoff, ProcHistoryBatch, ProcHistorySnapshot
from app.mod06_proc.service import build_page_data, parse_state
from app.mod08_inv.models import InvDetail
from tests.m06_helpers import CUTOFF_YM, WAREHOUSE, FakeSession, dataset_sections
from tests.test_proc_split_cutoffs import session  # noqa: F401


def _sess() -> FakeSession:
    return FakeSession(copy.deepcopy(dataset_sections()))


def _by_month(s: FakeSession) -> dict[str, dict]:
    return {r["ym"]: r for r in build_page_data(s, parse_state({"pj": WAREHOUSE}))["rows"]}


def test_机械手录入参解析_空按零_负数与非数字报错():
    """⚠️ 原先这条还借旧页 html 看「核算月带回 / 现值预填」；那是页面形态，旧页删后随之删掉，
    留下的**入参解析（空按 0 / 负数与非数字报错）与月份归一**是与页面无关的实质。"""

    zeros = {f"mech_{i}": Decimal("0.00") for i in range(len(D.MECH_COLUMNS))}
    assert mech_ui.parse_mech_values({}) == zeros, "空框按 0（0 是合法录入值）"
    assert mech_ui.parse_mech_values({"mech_0": "12.5"})["mech_0"] == Decimal("12.50")
    with pytest.raises(ValueError):
        mech_ui.parse_mech_values({"mech_0": "-1"})
    with pytest.raises(ValueError):
        mech_ui.parse_mech_values({"mech_0": "abc"})
    # 月份归一（唯一出口 = domain）
    assert D.normalize_ym("2026/8") == D.normalize_ym("202608") == "2026-08"
    assert D.normalize_ym("2026-13") == "" and D.normalize_ym("八月") == ""


def test_机械手录落库后表内取到_且重抓不覆盖():
    s = _sess()
    repo.save_mech(s, ym='2026-09', warehouse=WAREHOUSE, values={'mech_0': Decimal('55.00')})
    assert _by_month(s)['2026-09']['mech_0'] == Decimal('55.00')
    for row in s.by_model[InvDetail]:
        row.amount = Decimal('77777.00')
    assert _by_month(s)['2026-09']['mech_0'] == Decimal('55.00')
    repo.save_mech(s, ym='2026-06', warehouse=WAREHOUSE, values={'mech_0': Decimal('33.00')})
    assert _by_month(s)['2026-06']['mech_0'] == Decimal('33.00')
    assert all(D.column_editable(key, ym='2026-06', cutoff_ym=CUTOFF_YM) for key in D.MECH_KEYS)


def test_预览暂存不落库且过程资料使用通用载具(tmp_path, monkeypatch):
    monkeypatch.setattr(preview_store, 'PREVIEW_DIR', tmp_path)
    token = preview_store.save({'rows': [{'ym': '2026-03'}]})
    assert preview_store.load(token)['rows'] == [{'ym': '2026-03'}]
    with pytest.raises(MustReportError):
        preview_store.load('deadbeefdeadbeef')
    with pytest.raises(MustReportError):
        preview_store.load('../etc/passwd')


def test_接口按分界月给机械值_历史段读快照(session, monkeypatch):
    from contextlib import contextmanager
    from app.mod06_proc import router
    @contextmanager
    def scope():
        yield session
    monkeypatch.setattr(router, 'session_scope', scope)
    session.add(ProcCutoff(warehouse_name='历史仓', cutoff_ym='2026-06'))
    session.add(ProcHistoryBatch(batch_no='old', warehouse_name='历史仓', status='active'))
    snapshot = ProcHistorySnapshot(batch_no='old', warehouse_name='历史仓', ym='2026-05', mech_0=11)
    session.add(snapshot)
    repo.save_mech(session, ym='2026-05', warehouse='历史仓', values={'mech_0': '99'})
    repo.save_mech(session, ym='2026-09', warehouse='正式仓', values={'mech_0': '22'})
    got = router.api_mech()
    assert got['mech']['历史仓']['2026-05'][0] == 99.0
    assert got['mech']['正式仓']['2026-09'][0] == 22.0
    assert got['sections']['历史仓']['2026-05'] == D.SECTION_HISTORY
    assert got['sections']['正式仓']['2026-09'] == D.SECTION_FORMAL
    assert snapshot.mech_0 == Decimal('11')


def test_屏幕读模型与完整机械接口逐值同签名_只少来源明细(session, monkeypatch):
    """`/api/m06/mech-screen` 是屏幕读模型：值、月份、分段、两张签名、模式必须与完整接口相同，
    只有 `sources` 少了 `basis`/`history`（导出与明细回执才读那些）。"""
    from contextlib import contextmanager
    from app.mod06_proc import router

    @contextmanager
    def scope():
        yield session

    monkeypatch.setattr(router, 'session_scope', scope)
    session.add(ProcCutoff(warehouse_name='历史仓', cutoff_ym='2026-06'))
    session.add(ProcHistoryBatch(batch_no='old', warehouse_name='历史仓', status='active'))
    session.add(ProcHistorySnapshot(batch_no='old', warehouse_name='历史仓', ym='2026-05', mech_0=11))
    repo.save_mech(session, ym='2026-05', warehouse='历史仓', values={'mech_0': '99'})
    repo.save_mech(session, ym='2026-09', warehouse='正式仓', values={'mech_0': '22'},
                   detail_sources={'mech_0': {'batch': '已确认明细'}})
    full = router.api_mech()
    screen = router.api_mech_screen()
    assert screen['mech'] == full['mech']
    assert screen['count'] == full['count'] and screen['columns'] == full['columns']
    assert screen['sections'] == full['sections']
    assert screen['effective_signatures'] == full['effective_signatures']
    assert screen['detail_signatures'] == full['detail_signatures']
    assert screen['effective_values'] == full['effective_values']
    for warehouse, months in full['sources'].items():
        for ym, columns in months.items():
            full_modes = {k: v['mode'] for k, v in columns.items()}
            screen_modes = {k: v['mode'] for k, v in screen['sources'][warehouse][ym].items()}
            assert full_modes == screen_modes
    assert list(screen['sources']) == list(full['sources'])
    assert full['sources']['正式仓']['2026-09']['mech_0']['basis'] == {'batch': '已确认明细'}
    assert screen['sources']['正式仓']['2026-09']['mech_0']['mode'] == 'detail'
    assert 'basis' not in screen['sources']['正式仓']['2026-09']['mech_0']
