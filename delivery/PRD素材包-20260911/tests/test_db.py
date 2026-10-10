# -*- coding: utf-8 -*-
"""数据库层测试（R3 补强）：迁移幂等 / 默认 admin 账号 seed。"""
import db


def test_default_admin_seeded(monkeypatch, tmp_path):
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'test.db'))
    db.init_db()
    # 默认 admin 账号 seed：密码 123456 可校验通过，错误密码拒绝
    assert db.verify_user('admin', '123456') is not None
    assert db.verify_user('admin', 'wrong') is None


def test_init_db_idempotent(monkeypatch, tmp_path):
    # 用临时库隔离，避免污染生产 workbench.db
    monkeypatch.setattr(db, 'DB_PATH', str(tmp_path / 'test.db'))
    db.init_db()
    db.init_db()  # 连续两次不抛错即幂等

    conn = db.get_conn()
    try:
        migs = [r[0] for r in conn.execute(
            'SELECT version FROM schema_migrations ORDER BY version')]
        assert '001_baseline' in migs
        assert '002_pay_notice_lock' in migs
        assert '003_add_project_phid_aliases' in migs

        cols = [r[1] for r in conn.execute('PRAGMA table_info(projects)')]
        assert 'phid' in cols
        assert 'aliases' in cols
    finally:
        conn.close()
