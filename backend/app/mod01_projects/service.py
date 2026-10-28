"""`MOD-01` 项目档案 · **包间出口**（别的包要项目数据，只许经这一层）。

⭐ **为什么有这件**（`TAIL-218` 批 2）：本包原先**没有 `service.py`** ⇒ 别的包（`mod03_notice` /
   `mod07_setl` / `mod08_inv` / `mod11_jc`）想拿项目数据时**没有窗口可走**，只能
   `import app.mod01_projects.repository` **伸手翻账本** —— 实测 **11 处**（施工图 =
   `docs/archive/designs/设计-分层门禁一般式-20261002.md` §三 A 组）。
   计划 `§2.3`：「包间只经 `service` 调用，**不得跨包直查对方表**」⇒ 本件把那几件事收成口。
   守卫 = `backend/tests/test_layering.py` **规则 C**（一般式）。

⚠️⚠️ **每条必须写成函数、且每次经 `repository` 模块取** —— ⛔ 别写成模块级别名
   （`all_projects = R.all_projects`）：那会在导入时把函数对象**绑死**，测试里
   `monkeypatch.setattr(mod01_projects.repository, "all_projects", …)` 就**再也打不着**
   （2026-09-30 实测：**12 条判据当场红**，症状是 `session=None` 一路传到真的查询里）。
   ⭐ 机器眼 = `test_layering.py::test_包间出口必须真转发_打得着桩`（取样表 `_EXPORT_SMOKE`）。

⚠️ 出参**照实**回（⛔ 不做形状转换 —— 转形是壳适配层的活，本层只出语义，同 `mod11_jc/service.py` 文件头）。
⚠️ ⛔ **不写"只为转手而转手"的出口** —— 本件出口都有真调用者（`list_projects` 那一处原本自己
   就是一层薄名，换转发对象即可 ⇒ 见施工图 §3.3 的取舍判据）。
"""

from __future__ import annotations


def all_projects(session, **kw):
    """⭐ 包间出口：**全部**已建档项目（含归档 · **原序**，⛔ 不排序 —— 要排序走 `domain.ordered`）。"""
    from app.mod01_projects import repository as R

    return R.all_projects(session, **kw)


def get_project(session, project_id, **kw):
    """历史数据核对在同一事务内读取并按需锁定所属项目。"""
    from app.mod01_projects import repository as R
    return R.get_project(session, project_id, **kw)


def list_projects(session, **kw):
    """⭐ 包间出口：按筛选取档案（缺省**只筛「在建」** ＋ 自定义排序 —— 口径见 `repository.list_projects`）。"""
    from app.mod01_projects import repository as R

    return R.list_projects(session, **kw)


def export_phids(session, **kw):
    """⭐ 包间出口：导出用的项目 id 串（**保序去重** · 空档案 ⇒ 报错不臆造）。"""
    from app.mod01_projects import repository as R

    return R.export_phids(session, **kw)


def create_project(session, **kw):
    """⭐ 包间出口：建档（跨包**写**动作 —— 走本口，⛔ 别在别包直接造 `Project` 行）。"""
    from app.mod01_projects import repository as R

    return R.create_project(session, **kw)


def set_keywords(session, *args, **kw):
    """⭐ 包间出口：设置小微识别关键词（`project` ＋ `keywords` 按位置传）。"""
    from app.mod01_projects import repository as R

    return R.set_keywords(session, *args, **kw)


def warehouse_index(session):
    """仓库名→档案行；多包共用同一索引，按id取仓库名可遍历values。"""
    from app.mod01_projects import repository as R

    return R.warehouse_index(session)


def promote_synced_placeholders(session, warehouse_rows):
    """仓库同步后，在原档案上扶正；不创建新项目。"""
    from app.mod01_projects import recovery
    return recovery.promote_synced_placeholders(session, warehouse_rows)


__all__ = ["all_projects", "get_project", "list_projects", "export_phids", "create_project", "set_keywords", "warehouse_index", "promote_synced_placeholders"]
