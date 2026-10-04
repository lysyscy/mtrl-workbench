"""壳「按需取数」结构的**只读解析件**（`P3` 主体 · 2026-09-19）。

为什么要单独一件：`PAGE_LOAD` / `LOADERS` 这两张表被**四个**测试文件引用
（`test_wired_boot` · `test_wired_m06/m07/m08`）—— 各抄一份解析就是"同一件事两遍"（本仓老坑）。
⭐ 2026-09-20 追加 `EXP_ROUTES`（`TAIL-04` 的**导出真分发表**）：它同样被**两个**测试件引用
（`test_tail04_pages` · `test_tail04_export`）⇒ 按同一条纪律放这里，⛔ 别再各写一份正则。

⛔ **只读壳源码、不跑 JS**：解析用保守正则（表是手写的固定形态 ⇒ 够用），
   匹配不到就 `assert` 报出来（⛔ 不许静默返回空 —— 「空输出 ≠ 绿灯」）。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc  # noqa: F401  ← 五个使用方都要它

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛
# ⭐ 2026-10-03（`TAIL-219` 批 2）：取常量表改走壳的语义口径（定义 = `tools/audit/shell_api.py`）
from tools.audit.shell_api import const_obj

#: 已接后端的十页（`WIRED`）＋ 初始视图 `home`
#: ⚠️ 加一页就往这里加一个（本表是 `test_wired_boot.py` 的**覆盖哨**：不在表里的页不会被检查到）。
PAGES = ("home", "m01", "m02", "m03", "m04", "m05", "m06", "m07", "m08", "m09", "m14",
         "imp")
#: **依赖屏障**：这几路必须等它的**前置路**（真源 = `P2`/`P3` 的依赖逐条核查结论）。
#: ⚠️ **逐路不同** —— 别拍成"都要 `机械 6 列` ＋ `库存单据`"（实测：`付款域` 只吃 `MACH6`，
#:    不吃库存；需要两者的只有 `收发结存与大表`）。本仓纪律：这条**不许臆造**，改动要先核代码。
DEP_BEFORE: dict[str, tuple[str, ...]] = {
    "收发结存与大表": ("机械 6 列", "库存单据"),
    "付款域": ("机械 6 列",),
}
#: 依赖屏障涉及的**全部**路（＝ `DEP_BEFORE` 的键）
DEP = tuple(DEP_BEFORE)


# ⭐ 2026-10-03（`TAIL-219` 批 2）：原先这里有个 `_obj(name)` 自造剪刀（正则截 `const X = {…}`）
# —— **已整把删掉**，改用语义口径 `const_obj(name)`（认结构 · 找不到必抛）。⛔ 别写回来。


def exp_routes() -> dict[str, str]:
    """⭐ `EXP_ROUTES`：**导出真分发表**（`TAIL-04`）—— `data-t` → 端点。

    ⚠️ 为什么走解析而不是 `in` 断言：这张表是 `exp` 动作的**唯一**落点来源，
       "某一页有没有被接上/有没有被接到**别的**端点"必须看得见
       （`test_tail04_export.py` 的 `ACC-INV-001/001-12`「朴素那两份并存互不影响」就靠它 ——
        光看 `exp` 动作体已经看不出来了，端点串住在这张表里）。
    """
    out: dict[str, str] = {}
    for line in const_obj("EXP_ROUTES").splitlines():
        m = re.match(r"\s*'([^']+)':\s*\{.*?url:\s*'([^']+)'", line)
        if m:
            out[m.group(1)] = m.group(2)
    assert out, "`EXP_ROUTES` 解析出 0 条 —— 形态变了（⛔ 别静默放过）"
    return out


def page_load() -> dict[str, list[str]]:
    """`PAGE_LOAD`：页 → 它要的取数路（标签）。"""
    out: dict[str, list[str]] = {}
    for line in const_obj("PAGE_LOAD").splitlines():
        m = re.match(r"\s*([A-Za-z0-9_]+):\s*\[(.*?)\],", line)
        if m:
            out[m.group(1)] = re.findall(r"'([^']+)'", m.group(2))
    assert out, "`PAGE_LOAD` 解析出 0 条 —— 形态变了（⛔ 别静默放过）"
    return out


def loaders() -> set[str]:
    """`LOADERS` 的**标签**集合（标签即"失败点名"用的中文名，用户能看懂）。"""
    keys = set(re.findall(r"^\s*'([^']+)':", const_obj("LOADERS"), re.M))
    assert keys, "`LOADERS` 解析出 0 条 —— 形态变了（⛔ 别静默放过）"
    return keys


# ⭐ 2026-10-03（`TAIL-219` 批 2b）：`load_dep()`（取 `new Set([…])` 的项）**已删** ——
#    窗现在有了 `const_items(名)`（批 2b 添）⇒ 调用方直接 `set(const_items("LOAD_DEP"))`。
#    ⇒ ⭐ 本件**一把剪刀都不剩**了（`_obj` / `boot_body` / `load_paths_body` / `load_dep` 全清）。⛔ 别写回来。


# ⭐ 2026-10-03（`TAIL-219` 批 2）：`boot_body()` / `load_paths_body()` 两把剪刀**已整把删掉** ——
#    取函数体改走语义口径 `func_body(name)`（认结构 · 参数表＋花括号配平 · 找不到必抛）。
#    调用方改成 `func_body("boot")` / `func_body("loadPaths")`。⛔ 别写回来。
