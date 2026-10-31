"""导出件**绑定表**（装配层）—— 「名字 → 导出件」的**唯一一处**（`TAIL-195` 批 2b）。

⚠️ 为什么单独立一件（而不是并进 `export_registry.py`）：这张表**必须 import 导出层**，
   而注册表是**叶子**（见 `export_registry.py` 的模块头）⇒ 两者**不能同件**，否则叶子变成环的一环。

⚠️ **谁调 `register_all()`**：① 生产 = `app/main.py`（与 `models_registry` 同款：装配层的活）
   ② 测试 = `backend/tests/conftest.py`（许多测试**直调**导出件、不经过 `app.main`）。
   ⛔ **表只有这一份** —— 别在别处再写一张（那就是"同一件事两个口"，本仓最贵的病）。
"""

from __future__ import annotations

from app import export_registry as REG
from app.report_export import (
    fl_export,
    jc_export,
    jc_print_export,
    mechanical_export,
    nt_export,
    oilcard_export,
    pj_export,
    save,
    service,
)

#: 名字 → 件（⭐ **唯一一处**；业务包只认这些名字：
#:   `EXP.get("pj")` / `EXP.get("nt")` / `EXP.get("fl")` /
#:   `EXP.get("jc")` / `EXP.get("service")` / `EXP.get("save")`）
BINDINGS = {
    "pj": pj_export,        # 项目档案导出（`mod01`）
    "nt": nt_export,        # 付款通知书导出（`mod03`）
    "fl": fl_export,        # 付款流水导出（`mod05`）
    "jc_print": jc_print_export,
    "mechanical": mechanical_export,
    "oilcard": oilcard_export,
    "jc": jc_export,        # 集采台账导出（`mod11`）
    "service": service,     # 中立编排：`export_big` / `export_ledger` / `export_proc` / …（`mod05/06/07/08`）
    "save": save,           # `save_workbook`（`mod05` 的「总欠款表」用它落盘）
}


def register_all() -> None:
    """把 `BINDINGS` 填进注册表（**幂等** —— 重复调用无害）。"""
    for name, mod in BINDINGS.items():
        REG.register(name, mod)


__all__ = ["BINDINGS", "register_all"]
