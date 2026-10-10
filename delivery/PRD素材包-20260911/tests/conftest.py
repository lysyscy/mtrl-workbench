# -*- coding: utf-8 -*-
"""pytest 公共夹具：把 app/ 与 input/ 加入 sys.path，使测试能直接 import 项目模块。

备份目录隔离（2026-09-09 加）：
    单测会触发 db.backup_db()，若 BACKUP_DIR 仍是真实的 app/data/backup/，
    会灌入一批小备份文件，把用户的正式备份挤出保留窗口（只保留最近 8 份）。
    这里用 autouse fixture 把所有测试的备份目录指到临时目录，不污染真实备份。
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, 'app'), os.path.join(ROOT, 'input')):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture(autouse=True)
def _isolate_backup_dir(monkeypatch, tmp_path):
    """所有测试自动隔离备份目录到 tmp_path，避免污染真实 app/data/backup/。"""
    try:
        import db
        if hasattr(db, 'BACKUP_DIR'):
            d = tmp_path / 'backup'
            d.mkdir(parents=True, exist_ok=True)
            monkeypatch.setattr(db, 'BACKUP_DIR', str(d))
    except Exception:
        # 夹具失败不应阻断测试本身
        pass
