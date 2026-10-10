# -*- coding: utf-8 -*-
"""付款域端点冒烟测试：覆盖 /api/pay/pay、/api/pay/void 的 HTTP 层。

背景（2026-09-09 审计）：pay_api.py 曾漏 import session，付款/撤销端点一调用即
NameError 500；而原有 55 例只测了 pay_service 纯函数层，端点层零覆盖，故未拦住。
本文件补上端点层防线，防止同类"模块内 NameError"回归。
"""
import pytest
from flask import Flask

import db
import auth
import pay_service
from api import api as api_bp
from pay_api import pay_api as pay_bp


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'test.db'))
    db.init_db()
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False
    app.secret_key = auth.SECRET_KEY
    app.register_blueprint(api_bp)
    app.register_blueprint(pay_bp)
    c = app.test_client()
    c.post('/api/login', json={'username': 'admin', 'password': '123456'})
    return c


def _mk_notice(conn, code='FKTZS001', approve=1000.0, approve_state='已审批', source='auto'):
    conn.execute(
        "INSERT INTO pay_notice(单据编码, 单据名称, 单据日期, 审批金额, 审批状态, biz_class, source, manual) "
        "VALUES(?,?,?,?,?,?,?,0)",
        (code, '测试单据', '2026-09-01', approve, approve_state, '辅材', source))
    conn.commit()
    return conn.execute("SELECT id FROM pay_notice WHERE 单据编码=?", (code,)).fetchone()['id']


def test_pay_missing_notice_returns_biz_error(client):
    """不存在的单据 → 400 业务错误（而非 NameError 500）"""
    r = client.post('/api/pay/pay', json={'notice_id': 999999, 'amount': 100})
    assert r.status_code == 400
    assert '不存在' in r.get_json()['error']


def test_void_missing_flow_returns_biz_error(client):
    """不存在的流水 → 400 业务错误"""
    r = client.post('/api/pay/void', json={'flow_id': 999999, 'reason': '测试'})
    assert r.status_code == 400
    assert '流水不存在' in r.get_json()['error']


def test_pay_and_void_full_roundtrip(client):
    """完整链路：已审批单据付款成功 → 撤销回退并留痕"""
    conn = db.get_conn()
    try:
        nid = _mk_notice(conn)
    finally:
        conn.close()

    # 付款
    r = client.post('/api/pay/pay', json={'notice_id': nid, 'amount': 500,
                                          'pay_way': '银行承兑', 'request_id': 'req-1'})
    body = r.get_json()
    assert body['ok'] is True, body
    data = body['data']
    assert data['付款状态'] == '部分付款'
    assert data['pay_way'] == '承兑'                       # 模糊匹配银行承兑→承兑

    # 撤销
    flow_id = data['flow_id']
    r = client.post('/api/pay/void', json={'flow_id': flow_id, 'reason': '录错了'})
    assert r.get_json()['ok'] is True
    assert r.get_json()['data']['付款状态'] == '未付款'

    # 留痕
    conn = db.get_conn()
    try:
        n = conn.execute("SELECT COUNT(*) c FROM pay_flow_log WHERE flow_id=?", (flow_id,)).fetchone()['c']
        assert n >= 2                                         # 付款 + 撤销 两笔留痕
    finally:
        conn.close()


def test_pay_blocked_when_not_approved(client):
    """未审批 → 禁止付款（无流程不付款）"""
    conn = db.get_conn()
    try:
        nid = _mk_notice(conn, code='FKTZS002', approve_state='未审批')
    finally:
        conn.close()
    r = client.post('/api/pay/pay', json={'notice_id': nid, 'amount': 100})
    assert r.status_code == 400
    assert '未审批' in r.get_json()['error']


def test_debt_initial_roundtrip(client):
    """期初占位行：录入 → 查询 → 计入欠款总账 → 删除（口径：账=期初+明细）"""
    # 录入期初（期初结算 1000 − 期初付款 300 = 期初欠款 700）
    r = client.post('/api/debt/initial',
                    json={'project': '测试项目', '期初结算': 1000, '期初付款': 300, '备注': '旧信息化'})
    assert r.get_json()['ok'] is True

    # 查询列表 + 合计
    r = client.get('/api/debt/initial')
    body = r.get_json()
    assert body['ok'] is True
    assert body['data']['total_debt'] == pytest.approx(700.0)
    assert len(body['data']['rows']) == 1
    assert body['data']['rows'][0]['项目'] == '测试项目'

    # 欠款台账（无筛选）应把期初计入总账
    r = client.get('/api/debt')
    d = r.get_json()['data']
    assert d['initial']['debt'] == pytest.approx(700.0)
    assert d['total_debt'] == pytest.approx(700.0)   # 无明细时总账 = 期初欠款

    # 删除
    r = client.post('/api/debt/initial/delete', json={'project': '测试项目'})
    assert r.get_json()['ok'] is True
    assert r.get_json()['data']['deleted'] == 1

    # 删除后总账归零
    r = client.get('/api/debt')
    assert r.get_json()['data']['total_debt'] == pytest.approx(0.0)


def test_pay_plan_batch(client):
    """付款计划批量改分类/项目（参数化 IN，无注入）"""
    conn = db.get_conn()
    try:
        conn.execute("INSERT INTO projects(name) VALUES('批量项目')")
        pid = conn.execute("SELECT id FROM projects WHERE name='批量项目'").fetchone()['id']
        for code in ('P001', 'P002'):
            conn.execute(
                "INSERT INTO pay_plan(month, project_id, 单据号, 供应商, 分类, match_status) "
                "VALUES('2026-09', ?, ?, '供应商', '', '待核对')", (pid, code))
        conn.commit()
        plan_ids = [r['id'] for r in conn.execute("SELECT id FROM pay_plan ORDER BY id")]
    finally:
        conn.close()

    # 批量改分类
    r = client.post('/api/pay/plan/batch', json={'ids': plan_ids, '分类': '辅材'})
    assert r.get_json()['ok'] is True
    assert r.get_json()['data']['updated'] == 2

    # 批量改项目（按项目名映射 projects.id）
    r = client.post('/api/pay/plan/batch', json={'ids': plan_ids, 'project': '批量项目'})
    assert r.get_json()['ok'] is True

    # 项目不存在 → 404
    r = client.post('/api/pay/plan/batch', json={'ids': plan_ids, 'project': '不存在的项目'})
    assert r.status_code == 404

    # 空 ids → 业务错误
    r = client.post('/api/pay/plan/batch', json={'ids': [], '分类': '辅材'})
    assert r.status_code == 400
