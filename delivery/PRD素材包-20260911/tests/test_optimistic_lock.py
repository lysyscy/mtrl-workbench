# -*- coding: utf-8 -*-
"""pay_notice 行级乐观锁测试（R3 补强）：expect_ts 匹配 / 不匹配两路径。"""
from flask import Flask

import db
import auth
from api import api
from pay_api import pay_api   # 付款域路由已拆到独立蓝图，测试 app 需与 server.create_app() 一致


def _make_app():
    app = Flask(__name__)
    app.secret_key = auth.SECRET_KEY
    app.register_blueprint(api)
    app.register_blueprint(pay_api)
    return app


def test_optimistic_lock_match_then_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'test.db'))
    db.init_db()

    conn = db.get_conn()
    try:
        conn.execute(
            "INSERT INTO pay_notice(单据编码, biz_class, updated_at) "
            "VALUES('T-001', '待确认', '2026-08-01 10:00:00')")
        conn.commit()
        nid = conn.execute("SELECT id FROM pay_notice WHERE 单据编码='T-001'").fetchone()['id']
    finally:
        conn.close()

    c = _make_app().test_client()
    assert c.post('/api/login', json={'username': 'admin', 'password': '123456'}).get_json()['ok'] is True

    # 路径1：expect_ts 匹配（所见版本=库内版本）→ 写入成功，分类改为机械
    r = c.post('/api/pay/notice/confirm',
               json={'id': nid, 'biz_class': '机械', 'expect_ts': '2026-08-01 10:00:00'})
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

    # 路径2：expect_ts 不匹配（上一步已刷新 updated_at）→ 拒绝，分类保持不变
    r2 = c.post('/api/pay/notice/confirm',
                json={'id': nid, 'biz_class': '辅材', 'expect_ts': '2026-08-01 10:00:00'})
    assert r2.status_code == 400
    assert r2.get_json()['ok'] is False

    conn = db.get_conn()
    try:
        cur = conn.execute('SELECT biz_class FROM pay_notice WHERE id=?', (nid,)).fetchone()
    finally:
        conn.close()
    assert cur['biz_class'] == '机械'
