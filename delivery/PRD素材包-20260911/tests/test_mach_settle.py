# -*- coding: utf-8 -*-
"""机械费月结算端点测试：手动录入优先，未录入按付款通知书机械审批金额。

背景（2026-09-09）：C5 机械费台账暂不实现，改为"机械费每月结算金额手动录入"入口；
规则=有手动录入用手动，未录入按通知书机械类审批金额；覆盖同步影响欠款统计（v_debt）。
"""
from flask import Flask

import db
import auth
from api import api as api_bp
from pay_api import pay_api as pay_bp


def _client(monkeypatch, tmp_path):
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


def _mk_mach_notice(code, stat_name, month, approve):
    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT INTO pay_notice(单据编码, 单据名称, 单据日期, stat_name, 审批金额, "
            "审批状态, biz_class, source, manual, deleted) VALUES(?,?,?,?,?,?,?,?,0,0)",
            (code, '机械单', month + '-01', stat_name, approve, '已审批', '机械', 'auto'))
        conn.commit()
    finally:
        conn.close()


def _rows(c, month, project):
    r = c.get('/api/mach/settle?month=%s' % month).get_json()
    assert r['ok'] is True
    return [x for x in r['data'] if x['project'] == project]


def test_mach_settle_auto_only(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    _mk_mach_notice('JX001', '内蒙宜化项目', '2026-08', 1000.0)
    rows = _rows(c, '2026-08', '内蒙宜化项目')
    assert len(rows) == 1
    assert rows[0]['自动结算'] == 1000.0
    assert rows[0]['手动结算'] is None
    assert rows[0]['结算金额'] == 1000.0
    assert rows[0]['is_manual'] is False


def test_mach_settle_manual_override(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    _mk_mach_notice('JX002', '内蒙宜化项目', '2026-08', 1000.0)
    assert c.post('/api/mach/settle',
                  json={'project': '内蒙宜化项目', 'month': '2026-08', 'amount': 1200}).get_json()['ok'] is True
    row = _rows(c, '2026-08', '内蒙宜化项目')[0]
    assert row['手动结算'] == 1200.0
    assert row['结算金额'] == 1200.0
    assert row['is_manual'] is True
    # 欠款统计（v_debt）机械结算反映手动覆盖
    d = c.get('/api/debt?month=2026-08&cls=机械').get_json()['data']
    debt_row = [x for x in d['rows'] if x['project'] == '内蒙宜化项目'][0]
    assert debt_row['stat_settle'] == 1200.0


def test_mach_settle_clear(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    _mk_mach_notice('JX003', '内蒙宜化项目', '2026-08', 1000.0)
    c.post('/api/mach/settle', json={'project': '内蒙宜化项目', 'month': '2026-08', 'amount': 1200})
    assert c.post('/api/mach/settle/clear',
                  json={'project': '内蒙宜化项目', 'month': '2026-08'}).get_json()['ok'] is True
    row = _rows(c, '2026-08', '内蒙宜化项目')[0]
    assert row['结算金额'] == 1000.0
    assert row['is_manual'] is False


def test_mach_settle_invalid_amount(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    assert c.post('/api/mach/settle',
                  json={'project': 'X', 'month': '2026-08', 'amount': 'abc'}).status_code == 400
    assert c.post('/api/mach/settle',
                  json={'project': 'X', 'month': '2026-08', 'amount': -5}).status_code == 400
