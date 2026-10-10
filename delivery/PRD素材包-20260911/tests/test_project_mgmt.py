# -*- coding: utf-8 -*-
"""项目管理功能测试：ensure_project 三维匹配 / is_small 判定 / 增删改查 / 合并迁移 / 删除级联 / 完整性。"""
import sqlite3

import pytest
from flask import Flask

import db
import importer
import auth
from api import api as api_bp


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'test.db'))
    db.init_db()
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False
    app.secret_key = auth.SECRET_KEY
    app.register_blueprint(api_bp)
    c = app.test_client()
    c.post('/api/login', json={'username': 'admin', 'password': '123456'})
    return c


@pytest.fixture
def conn(monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'test.db'))
    db.init_db()
    c = db.get_conn()
    yield c
    c.close()


# ============ 纯函数 ============
def test_is_small_project():
    sm = {'第四工程公司 2024小微项目': {'大唐雷州': ['大唐雷州'], '焦作佰利': ['佰利']}}
    assert importer.is_small_project('大唐雷州', sm) is True              # 具体小微
    assert importer.is_small_project('第四工程公司 2024小微项目', sm) is True   # 壳
    assert importer.is_small_project('灵宝二期', sm) is False              # 普通
    assert importer.is_small_project('', sm) is False


def test_ensure_project_three_dim(conn):
    pid = db.ensure_project('仓库A', conn=conn, full_name='全名A有限公司项目')
    assert db.ensure_project('仓库A', conn=conn) == pid                    # name 精确
    assert db.ensure_project('另一个名', conn=conn, full_name='全名A有限公司项目') == pid  # full_name 反向
    conn.execute("UPDATE projects SET aliases='|别名X|' WHERE id=?", (pid,))
    assert db.ensure_project('别名X', conn=conn) == pid                    # aliases 兜底
    # 命中补 full_name
    conn.execute("UPDATE projects SET full_name='' WHERE id=?", (pid,))
    db.ensure_project('仓库A', conn=conn, full_name='全名A有限公司项目')
    row = conn.execute('SELECT full_name FROM projects WHERE id=?', (pid,)).fetchone()
    assert row['full_name'] == '全名A有限公司项目'


# ============ API 端点 ============
def test_add_and_duplicate(client):
    r = client.post('/api/projects/add', json={'name': '仓库A', 'full_name': '全名A'})
    assert r.get_json()['ok'] is True
    r = client.post('/api/projects/add', json={'name': '仓库A'})
    assert r.get_json()['ok'] is False                              # 重复名拒绝


def test_rename_sync_text(client):
    client.post('/api/projects/add', json={'name': '仓库A'})
    pid = client.get('/api/projects').get_json()['data'][0]['id']
    # 挂业务数据
    c = sqlite3.connect(db.DB_PATH)
    c.execute("INSERT INTO stock_monthly(month, project_id, 仓库, 资源编码) VALUES('2026-08',?,?, 'ZC1')", (pid, '仓库A'))
    c.execute("INSERT INTO mtrl_extract(month, cat, wh, amount) VALUES('2026-08','气体',?,100)", ('仓库A',))
    c.commit(); c.close()
    r = client.post('/api/projects/rename', json={'id': pid, 'field': 'name', 'value': '仓库A2'})
    assert r.get_json()['ok'] is True
    c = sqlite3.connect(db.DB_PATH)
    assert c.execute('SELECT 仓库 FROM stock_monthly').fetchone()[0] == '仓库A2'
    assert c.execute('SELECT wh FROM mtrl_extract').fetchone()[0] == '仓库A2'
    c.close()


def test_merge_migrates(client):
    a = client.post('/api/projects/add', json={'name': '仓库A', 'full_name': '全名A'}).get_json()['data']['id']
    b = client.post('/api/projects/add', json={'name': '仓库B', 'full_name': '全名B'}).get_json()['data']['id']
    c = sqlite3.connect(db.DB_PATH)
    c.execute("INSERT INTO stock_monthly(month, project_id, 仓库, 资源编码) VALUES('2026-08',?,?, 'ZC1')", (b, '仓库B'))
    c.commit(); c.close()
    r = client.post('/api/projects/merge', json={'keep_id': a, 'dup_ids': [b], 'confirm': True})
    assert r.get_json()['ok'] is True
    c = sqlite3.connect(db.DB_PATH)
    assert c.execute('SELECT project_id FROM stock_monthly').fetchone()[0] == a   # 迁移
    assert c.execute('SELECT COUNT(*) FROM projects').fetchone()[0] == 1         # dup 已删
    c.close()


def test_delete_cascade(client):
    pid = client.post('/api/projects/add', json={'name': '仓库D'}).get_json()['data']['id']
    c = sqlite3.connect(db.DB_PATH)
    c.execute("INSERT INTO stock_monthly(month, project_id, 仓库, 资源编码) VALUES('2026-08',?,?, 'ZC1')", (pid, '仓库D'))
    c.execute("INSERT INTO inv_detail(month, project_id, 仓库, 单据编号, 序号) VALUES('2026-08',?,?, 'DJ1', '1')", (pid, '仓库D'))
    c.execute("INSERT INTO mtrl_extract(month, cat, wh, amount) VALUES('2026-08','气体',?,100)", ('仓库D',))
    c.commit(); c.close()
    # 无 confirm 拒绝
    r = client.post('/api/projects/delete', json={'id': pid})
    assert r.get_json()['ok'] is False
    # 有 confirm 执行级联
    r = client.post('/api/projects/delete', json={'id': pid, 'confirm': True})
    assert r.get_json()['ok'] is True
    c = sqlite3.connect(db.DB_PATH)
    assert c.execute('SELECT COUNT(*) FROM projects').fetchone()[0] == 0
    assert c.execute('SELECT COUNT(*) FROM stock_monthly').fetchone()[0] == 0
    assert c.execute('SELECT COUNT(*) FROM inv_detail').fetchone()[0] == 0
    assert c.execute('SELECT COUNT(*) FROM mtrl_extract').fetchone()[0] == 0
    c.close()


def test_integrity(client):
    r = client.get('/api/projects/integrity')
    d = r.get_json()['data']
    assert d['orphan_stock_monthly'] == 0
    assert 'empty_projects' in d
