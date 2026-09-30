"""导出件**注册表**（装配层 · **叶子件**）—— 业务包从这里**按名取**导出器。

## 它治什么（`TAIL-195` 批 2b · 方案件 §七 ③）

「导出层（`app/report_export/`）⇄ 业务包」原本是个**环**：导出层要读业务数据（正向），
而 9 个业务包又反过来 `import app.report_export`（反向）⇒ **改一侧牵动另一侧**。
⇒ 从本批起，业务侧只认**名字**；「名字 → 导出件」那张表只存在于**装配层**
（`app/export_bindings.py`），⛔ 业务包不再 import 导出层。

## ⚠️⚠️ 本件是**叶子**：⛔ 绝不许 `import` 任何 `app.*`

它一旦 import 了导出层，就成了「业务 → 本件 → 导出层 → 业务」的**换名环** ——
`tests/test_layering.py` 的**规则 B** 也就成了"绕开结构问题"的假绿（⛔ 那比不立规则更坏）。
⇒ 机器守 = `tests/test_layering.py::test_B2_注册表必须是叶子件`。

⚠️ 本件**不 import 任何 `app.*`** ⇒ 业务包 import 它**不构成环**（叶子在图上没有出边）。
"""

from __future__ import annotations

from types import ModuleType

_REG: dict[str, ModuleType] = {}


def register(name: str, module: ModuleType) -> None:
    """填表（**只有装配层**该调 —— `app/export_bindings.py::register_all`）。⛔ 业务包不许调。"""
    _REG[name] = module


def get(name: str) -> ModuleType:
    """按名取导出件。⚠️ 没注册 ⇒ **显式报错**（⛔ 不静默回落成 `None` —— 那会把"没接上"藏起来）。"""
    mod = _REG.get(name)
    if mod is None:
        raise RuntimeError(
            f"导出件「{name}」没有注册 —— 装配层必须先注册（`app.export_bindings.register_all()`）；"
            f"当前已注册：{sorted(_REG) or '（空）'}"
        )
    return mod


__all__ = ["get", "register"]
