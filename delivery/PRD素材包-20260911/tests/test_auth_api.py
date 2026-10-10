# -*- coding: utf-8 -*-
"""认证与用户管理端点测试：登录/登出/状态 + 用户增删改查/重置/启停（支持人员更迭）。

背景（2026-09-09）：鉴权从"单密码"升级为"用户名+密码"，补端点层防线，
验证 users 表、PBKDF2 密码校验、登录态写 session、人员更迭（增/删/停用/重置）全链路。
"""
from flask import Flask

import db
import auth
from api import api as api_bp


def _client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'test.db'))
    db.init_db()
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False
    app.secret_key = auth.SECRET_KEY
    app.register_blueprint(api_bp)
    return app.test_client()


def test_login_ok_and_status(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    r = c.post('/api/login', json={'username': 'admin', 'password': '123456'})
    assert r.get_json()['ok'] is True
    assert r.get_json()['data']['user'] == 'admin'
    st = c.get('/api/auth/status').get_json()
    assert st['data']['authed'] is True
    assert st['data']['user'] == 'admin'


def test_login_wrong_password(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    r = c.post('/api/login', json={'username': 'admin', 'password': 'wrong'})
    assert r.status_code == 401
    assert r.get_json()['ok'] is False


def test_login_empty_fields(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    assert c.post('/api/login', json={}).status_code == 401


def test_logout_clears_session(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    c.post('/api/login', json={'username': 'admin', 'password': '123456'})
    assert c.get('/api/auth/status').get_json()['data']['authed'] is True
    c.post('/api/logout', json={})
    assert c.get('/api/auth/status').get_json()['data']['authed'] is False


def test_user_full_lifecycle(monkeypatch, tmp_path):
    """人员更迭全链路：新增→登录→重置密码→停用→删除。"""
    c = _client(monkeypatch, tmp_path)
    c.post('/api/login', json={'username': 'admin', 'password': '123456'})

    # 新增用户
    r = c.post('/api/users', json={'username': 'zhang', 'password': 'abcd', 'display_name': '张三'})
    assert r.get_json()['ok'] is True
    # 重复用户名 → 400
    assert c.post('/api/users', json={'username': 'zhang', 'password': 'abcd'}).status_code == 400

    # 列表含 admin 与 zhang
    users = c.get('/api/users').get_json()['data']
    names = [u['username'] for u in users]
    assert 'admin' in names and 'zhang' in names
    zid = [u['id'] for u in users if u['username'] == 'zhang'][0]

    # 新用户可登录
    assert c.post('/api/login', json={'username': 'zhang', 'password': 'abcd'}).get_json()['ok'] is True
    # 重置密码后可登录，旧密码失效
    assert c.post('/api/users/reset', json={'id': zid, 'password': 'newpwd'}).get_json()['ok'] is True
    assert c.post('/api/login', json={'username': 'zhang', 'password': 'newpwd'}).get_json()['ok'] is True
    assert c.post('/api/login', json={'username': 'zhang', 'password': 'abcd'}).status_code == 401

    # 切回 admin 身份，再停用/删除 zhang
    c.post('/api/login', json={'username': 'admin', 'password': '123456'})
    # 停用后无法登录
    assert c.post('/api/users/toggle', json={'id': zid, 'is_active': False}).get_json()['ok'] is True
    assert c.post('/api/login', json={'username': 'zhang', 'password': 'newpwd'}).status_code == 401

    # 删除
    assert c.post('/api/users/delete', json={'id': zid}).get_json()['ok'] is True
    users = c.get('/api/users').get_json()['data']
    assert 'zhang' not in [u['username'] for u in users]


def test_cannot_self_deactivate_or_delete(monkeypatch, tmp_path):
    c = _client(monkeypatch, tmp_path)
    c.post('/api/login', json={'username': 'admin', 'password': '123456'})
    admin_id = [u['id'] for u in c.get('/api/users').get_json()['data'] if u['username'] == 'admin'][0]
    assert c.post('/api/users/toggle', json={'id': admin_id, 'is_active': False}).status_code == 400
    assert c.post('/api/users/delete', json={'id': admin_id}).status_code == 400


def test_i8_binding_roundtrip(monkeypatch, tmp_path):
    """i8 账号绑定：设账号+密码 → 列表脱敏返回 → 解密一致 → 清空绑定。"""
    c = _client(monkeypatch, tmp_path)
    c.post('/api/login', json={'username': 'admin', 'password': '123456'})

    admin_id = [u['id'] for u in c.get('/api/users').get_json()['data'] if u['username'] == 'admin'][0]
    r = c.post('/api/users/i8', json={'id': admin_id, 'i8_account': 'CSM880909', 'i8_password': '090988'})
    assert r.get_json()['ok'] is True

    users = c.get('/api/users').get_json()['data']
    admin = [u for u in users if u['username'] == 'admin'][0]
    assert admin['i8_account'] == 'CSM880909'
    assert admin['i8_has_password'] is True
    assert 'i8_password' not in admin      # 不返回明文

    conn = db.get_conn()
    try:
        stored = conn.execute("SELECT i8_password FROM users WHERE username='admin'").fetchone()[0]
    finally:
        conn.close()
    assert stored != '090988'                                   # 非明文
    assert auth.deobfuscate_i8_password(stored) == '090988'      # 可逆还原

    # 清空绑定
    r = c.post('/api/users/i8', json={'id': admin_id, 'i8_account': '', 'i8_password': ''})
    assert r.get_json()['ok'] is True
    admin = [u for u in c.get('/api/users').get_json()['data'] if u['username'] == 'admin'][0]
    assert admin['i8_account'] == ''
    assert admin['i8_has_password'] is False


def test_i8_binding_unknown_user(monkeypatch, tmp_path):
    """i8 绑定不存在的用户 → 404。"""
    c = _client(monkeypatch, tmp_path)
    c.post('/api/login', json={'username': 'admin', 'password': '123456'})
    r = c.post('/api/users/i8', json={'id': 9999, 'i8_account': 'X', 'i8_password': ''})
    assert r.status_code == 404
