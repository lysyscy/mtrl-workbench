# -*- coding: utf-8 -*-
"""pay_service 单元测试（资金核心：付款/撤销/派生/金额/模糊匹配）。

背景：pay_service.py 是付款域的资金核心（付款、撤销、金额转分、防超付、防连点、
付款方式模糊匹配），此前**零单测**，仅靠集成脚本 verify_pay.py 覆盖。
本文件补齐其关键路径，防御资金类缺陷。
"""
import pytest

import db
import pay_service as ps


def _prep(monkeypatch, tmp_path):
    """建库并返回连接（调用方负责关闭）"""
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'test.db'))
    db.init_db()
    return db.get_conn()


def _add_notice(conn, code, amt, approved='已审批', source='auto'):
    cur = conn.execute(
        "INSERT INTO pay_notice(单据编码, 单据名称, 单据日期, 审批金额, 审批状态, "
        "biz_class, source, deleted) VALUES(?,?,?,?,?,?,?,0)",
        (code, '测试单据', '2026-09-01', amt, approved, '辅材', source))
    conn.commit()
    return cur.lastrowid


# ---------- 金额工具 ----------
def test_to_cents_消除浮点误差():
    # 0.1 + 0.2 直接浮点相加是 0.30000000000000004；转分后应为 30
    assert ps.to_cents(0.1) + ps.to_cents(0.2) == 30
    assert ps.to_cents(12.34) == 1234
    assert ps.to_cents('56.78') == 5678


def test_to_cents_非法值按零处理():
    assert ps.to_cents(None) == 0
    assert ps.to_cents('') == 0
    assert ps.to_cents('abc') == 0
    assert ps.to_cents(float('nan')) == 0   # NaN 不得污染比较


# ---------- 付款方式模糊匹配 ----------
@pytest.mark.parametrize('text,expect_std,expect_matched', [
    ('现汇', '现汇', True),
    ('银行承兑', '承兑', True),
    ('电子承兑汇票', '承兑', True),
    ('供应链保理', '供应链', True),
    ('微信支付', '其他', False),      # 匹配不上 → 归其他且 matched=False（提示手填）
    ('', '', True),                   # 空值不报错
])
def test_match_pay_way(text, expect_std, expect_matched):
    assert ps.match_pay_way(text) == (expect_std, expect_matched)


# ---------- 状态派生 ----------
@pytest.mark.parametrize('approve,paid,expect', [
    (1000.0, 0, '未付款'),
    (1000.0, 500.0, '部分付款'),
    (1000.0, 1000.0, '已付款'),
    (1000.0, 1200.0, '已付款'),   # 超付也归为已付款
])
def test_calc_pay_status(approve, paid, expect):
    assert ps.calc_pay_status(approve, paid) == expect


# ---------- 付款主流程 ----------
def test_pay_正常部分付款(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-001', 1000.0)
        r = ps.pay(conn, nid, 400.0, pay_way='现汇', pay_date='2026-09-10',
                   operator='tester', request_id='R1')
        assert r['ok'] is True
        assert r['已付款金额'] == 400.0
        assert r['付款状态'] == '部分付款'
        assert ps.paid_amount(conn, nid) == 400.0
    finally:
        conn.close()


def test_pay_付清变已付款(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-002', 800.0)
        ps.pay(conn, nid, 300.0, request_id='R1')
        r = ps.pay(conn, nid, 500.0, request_id='R2')   # 累计 800 = 全额
        assert r['付款状态'] == '已付款'
        assert r['已付款金额'] == 800.0
    finally:
        conn.close()


def test_pay_防超付默认拦截(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-003', 100.0)
        with pytest.raises(ps.PayError) as e:
            ps.pay(conn, nid, 150.0, request_id='R1')
        assert '超付' in e.value.msg
        # 被拦截后不应留下流水
        assert ps.paid_amount(conn, nid) == 0
    finally:
        conn.close()


def test_pay_允许超付则放行并告警(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-004', 100.0)
        r = ps.pay(conn, nid, 150.0, request_id='R1', allow_over=True)
        assert r['ok'] is True
        assert r['warning'] and '超付' in r['warning']
        assert ps.paid_amount(conn, nid) == 150.0
    finally:
        conn.close()


def test_pay_未审批禁止付款(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-005', 100.0, approved='未审批')
        with pytest.raises(ps.PayError) as e:
            ps.pay(conn, nid, 50.0, request_id='R1')
        assert '未审批' in e.value.msg
    finally:
        conn.close()


def test_pay_手动行禁止付款(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        # 无流程不付款：source='manual' 的手动增加行不可付款
        nid = _add_notice(conn, 'T-006', 100.0, source='manual')
        with pytest.raises(ps.PayError) as e:
            ps.pay(conn, nid, 50.0, request_id='R1')
        assert '手动' in e.value.msg
    finally:
        conn.close()


def test_pay_金额非正数拦截(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-007', 100.0)
        with pytest.raises(ps.PayError) as e:
            ps.pay(conn, nid, 0, request_id='R1')
        assert '大于 0' in e.value.msg
    finally:
        conn.close()


def test_pay_防连点幂等(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-008', 1000.0)
        r1 = ps.pay(conn, nid, 300.0, request_id='SAME-REQ')
        assert r1['ok'] is True
        # 同一 request_id 重复提交 → 幂等，不重复记账
        r2 = ps.pay(conn, nid, 300.0, request_id='SAME-REQ')
        assert r2['ok'] is True and r2.get('duplicated') is True
        assert ps.paid_amount(conn, nid) == 300.0   # 仍为 300，未变成 600
    finally:
        conn.close()


# ---------- 撤销 ----------
def test_void_必须填原因(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-009', 1000.0)
        ps.pay(conn, nid, 500.0, request_id='R1')
        fid = conn.execute('SELECT id FROM pay_flow WHERE notice_id=? AND voided=0',
                           (nid,)).fetchone()['id']
        with pytest.raises(ps.PayError) as e:
            ps.void_flow(conn, fid, operator='tester', reason='')
        assert '原因' in e.value.msg
    finally:
        conn.close()


def test_void_撤销后状态回退并留痕(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-010', 1000.0)
        ps.pay(conn, nid, 500.0, request_id='R1')
        assert ps.calc_pay_status(1000.0, ps.paid_amount(conn, nid)) == '部分付款'

        fid = conn.execute('SELECT id FROM pay_flow WHERE notice_id=? AND voided=0',
                           (nid,)).fetchone()['id']
        r = ps.void_flow(conn, fid, operator='tester', reason='测试撤销')
        assert r['ok'] is True
        assert ps.paid_amount(conn, nid) == 0          # 金额回退
        assert r['付款状态'] == '未付款'                 # 状态回退
        # 撤销留痕
        log = conn.execute('SELECT action FROM pay_flow_log WHERE flow_id=? AND action=?',
                           (fid, '撤销')).fetchone()
        assert log is not None
    finally:
        conn.close()


def test_void_重复撤销被拒(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-011', 1000.0)
        ps.pay(conn, nid, 500.0, request_id='R1')
        fid = conn.execute('SELECT id FROM pay_flow WHERE notice_id=? AND voided=0',
                           (nid,)).fetchone()['id']
        ps.void_flow(conn, fid, operator='tester', reason='第一次撤销')
        with pytest.raises(ps.PayError) as e:
            ps.void_flow(conn, fid, operator='tester', reason='再次撤销')
        assert '已撤销' in e.value.msg
    finally:
        conn.close()


# ---------- 派生与口径 ----------
def test_notice_view_派生字段(monkeypatch, tmp_path):
    conn = _prep(monkeypatch, tmp_path)
    try:
        nid = _add_notice(conn, 'T-012', 2000.0)
        ps.pay(conn, nid, 600.0, request_id='R1')
        row = conn.execute('SELECT * FROM pay_notice WHERE id=?', (nid,)).fetchone()
        v = ps.notice_view(conn, row)
        assert v['已付款金额'] == 600.0
        assert v['剩余未付'] == 1400.0
        assert v['付款状态'] == '部分付款'
    finally:
        conn.close()
