"""项目三小件 —— **归并键 / 展示名 / 项目索引**（⭐ **唯一实现**，别再抄一份）。

口径：《材料科业务全流程说明书》**§2.7.4** —— 项目**归并键 = 仓库名**
      （不是项目全名、不是 id；仓库名缺失时退化为 `#id`，**不猜**）。

⚠️ **为什么放在 `core/`**：这三件原本在 `mod04_plan/service.py` 与 `mod05_flow/service.py`
   **各有一份**（第 2 份是接 `m05` 时「本模块没有 ⇒ 又抄一份」）⇒ 重复件最易分叉：
   改一处忘另一处 ⇒ **前端「按仓库名归并 / 点条目筛流水」这类联动会静默失配**。
   ⛔ **后续模块（含材料域 `m06/m07/m08`）要这三件，一律从这里 import。**
   ⭐ 2026-09-30（`TAIL-195` 批 1b）起本文件**不再依赖任何业务模块**： 「取全部项目行」由
   **数据主人** `mod01_projects` 提供，本件只留**口**（`bind_rows_loader`），装配层接上
   （`app/core_bindings.py`）；`test_layering.py` 规则 A 的**放行名单已清空**。
   ⛔ `core` 里别 import 业务包（计划 §2.3「依赖方向一律向外」）。

用法（两个口径分清楚，别混）：

| 件 | 用途 | 别拿它干 |
|---|---|---|
| `project_key` | **归并 / 筛选的键** —— 把不同来源的行归到同一个项目上 | ⛔ 别当显示名（缺失时会成 `#id`，用户看不懂） |
| `project_label` | **显示名** —— 只影响屏幕上写什么 | ⛔ 别当键（展示名可改、会变 ⇒ 键就漂了） |
| `project_index` | 一次取齐全部项目，供上面两件找行 | —— |
"""

from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

#: ── 取数口（**装配层注入** · `TAIL-195` 批 1b）─────────────────────────────────
#: 实现 = `mod01_projects.repository.all_projects`（**唯一一份**）；装配 = `app/core_bindings.py`。
_ROWS_LOADER: Callable[[Session], list] | None = None


def bind_rows_loader(fn: Callable[[Session], list]) -> None:
    """装配层接上「取全部项目行」的实现。

    ⚠️ 接**转发**（`lambda s: R.all_projects(s)`）—— ⛔ 别接模块级别名：那会在接的那一刻把函数对象
       绑死，测试里 `monkeypatch.setattr(…, "all_projects", …)` 就再也打不着（`TAIL-195` 批 2c 实测的坑）。
    """
    global _ROWS_LOADER
    _ROWS_LOADER = fn


def project_index(s: Session) -> dict[int, Any]:
    """全部项目 → `{id: 项目行}`（**一次取齐**，供归并 / 反查）。

    ⚠️ **取数归数据主人**（`mod01_projects`）：本件只做「键 = id」这件事，行由装配层注入的取数口给。
       未接上 ⇒ **显式报错**（⛔ 不静默回空表 —— 那会把"没装配"读成"库里一个项目都没有"）。
    """
    if _ROWS_LOADER is None:
        raise RuntimeError(
            "项目行的取数口没接上 ⇒ `project_index` 拒做 —— 见 `app.core_bindings.register_all()`")
    return {p.id: p for p in _ROWS_LOADER(s)}


def project_key(p: Any | None) -> str:
    """项目**归并键 = 仓库名**（§2.7.4）；缺失时退化为 `#id`（**不猜**）。"""
    if p is None:
        return ""
    return p.warehouse_name or f"#{p.id}"


def project_label(p: Any | None) -> str:
    """项目**显示名**：展示名 → 仓库名 → 全名 → `#id`（**只影响显示，不当键**）。"""
    if p is None:
        return ""
    return p.disp or p.warehouse_name or p.name_full or f"#{p.id}"


__all__ = ["project_index", "project_key", "project_label"]
