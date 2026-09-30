"""项目三小件 —— **归并键 / 展示名 / 项目索引**（⭐ **唯一实现**，别再抄一份）。

口径：《材料科业务全流程说明书》**§2.7.4** —— 项目**归并键 = 仓库名**
      （不是项目全名、不是 id；仓库名缺失时退化为 `#id`，**不猜**）。

⚠️ **为什么放在 `core/`**：这三件原本在 `mod04_plan/service.py` 与 `mod05_flow/service.py`
   **各有一份**（第 2 份是接 `m05` 时「本模块没有 ⇒ 又抄一份」）⇒ 重复件最易分叉：
   改一处忘另一处 ⇒ **前端「按仓库名归并 / 点条目筛流水」这类联动会静默失配**。
   ⛔ **后续模块（含材料域 `m06/m07/m08`）要这三件，一律从这里 import。**
   ⚠️ 本文件（连同 `app_settings.py` / `identity.py`）**确实**让 `core` 依赖了业务模块 ——
   ⭐ 2026-09-30（`TAIL-195` 批 1）起那是**已知例外**，由 `backend/tests/test_layering.py` 的
   **放行名单**钉住「⛔ 不再新增」（批 1b 会把它们改成"接口 ＋ 装配层注入"，那时名单清空）。

用法（两个口径分清楚，别混）：

| 件 | 用途 | 别拿它干 |
|---|---|---|
| `project_key` | **归并 / 筛选的键** —— 把不同来源的行归到同一个项目上 | ⛔ 别当显示名（缺失时会成 `#id`，用户看不懂） |
| `project_label` | **显示名** —— 只影响屏幕上写什么 | ⛔ 别当键（展示名可改、会变 ⇒ 键就漂了） |
| `project_index` | 一次取齐全部项目，供上面两件找行 | —— |
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod01_projects.models import Project


def project_index(s: Session) -> dict[int, Project]:
    """全部项目 → `{id: Project}`（**一次取齐**，供归并 / 反查）。"""
    return {p.id: p for p in s.execute(select(Project)).scalars().all()}


def project_key(p: Project | None) -> str:
    """项目**归并键 = 仓库名**（§2.7.4）；缺失时退化为 `#id`（**不猜**）。"""
    if p is None:
        return ""
    return p.warehouse_name or f"#{p.id}"


def project_label(p: Project | None) -> str:
    """项目**显示名**：展示名 → 仓库名 → 全名 → `#id`（**只影响显示，不当键**）。"""
    if p is None:
        return ""
    return p.disp or p.warehouse_name or p.name_full or f"#{p.id}"


__all__ = ["project_index", "project_key", "project_label"]
