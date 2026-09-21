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

#: 已接后端的十页（`WIRED`）＋ 初始视图 `home`
PAGES = ("home", "m01", "m02", "m03", "m04", "m05", "m06", "m07", "m08", "m09", "m14")
#: **依赖屏障**：这几路必须等它的**前置路**（真源 = `P2`/`P3` 的依赖逐条核查结论）。
#: ⚠️ **逐路不同** —— 别拍成"都要 `机械 6 列` ＋ `库存单据`"（实测：`付款域` 只吃 `MACH6`，
#:    不吃库存；需要两者的只有 `收发结存与大表`）。本仓纪律：这条**不许臆造**，改动要先核代码。
DEP_BEFORE: dict[str, tuple[str, ...]] = {
    "收发结存与大表": ("机械 6 列", "库存单据"),
    "付款域": ("机械 6 列",),
}
#: 依赖屏障涉及的**全部**路（＝ `DEP_BEFORE` 的键）
DEP = tuple(DEP_BEFORE)


def _obj(name: str) -> str:
    """取 `const <name> = { … };` 的字面量正文（到**行首的 `};`** 为止）。"""
    m = re.search(rf"const {name} = \{{(.*?)\n\}};", SHELL, re.S)
    assert m, f"壳里找不到 `const {name} = {{`（形态变了就同批改本件）"
    return m.group(1)


def exp_routes() -> dict[str, str]:
    """⭐ `EXP_ROUTES`：**导出真分发表**（`TAIL-04`）—— `data-t` → 端点。

    ⚠️ 为什么走解析而不是 `in` 断言：这张表是 `exp` 动作的**唯一**落点来源，
       "某一页有没有被接上/有没有被接到**别的**端点"必须看得见
       （`test_tail04_export.py` 的 `ACC-INV-001/001-12`「朴素那两份并存互不影响」就靠它 ——
        光看 `exp` 动作体已经看不出来了，端点串住在这张表里）。
    """
    out: dict[str, str] = {}
    for line in _obj("EXP_ROUTES").splitlines():
        m = re.match(r"\s*'([^']+)':\s*\{.*?url:\s*'([^']+)'", line)
        if m:
            out[m.group(1)] = m.group(2)
    assert out, "`EXP_ROUTES` 解析出 0 条 —— 形态变了（⛔ 别静默放过）"
    return out


def page_load() -> dict[str, list[str]]:
    """`PAGE_LOAD`：页 → 它要的取数路（标签）。"""
    out: dict[str, list[str]] = {}
    for line in _obj("PAGE_LOAD").splitlines():
        m = re.match(r"\s*([A-Za-z0-9_]+):\s*\[(.*?)\],", line)
        if m:
            out[m.group(1)] = re.findall(r"'([^']+)'", m.group(2))
    assert out, "`PAGE_LOAD` 解析出 0 条 —— 形态变了（⛔ 别静默放过）"
    return out


def loaders() -> set[str]:
    """`LOADERS` 的**标签**集合（标签即"失败点名"用的中文名，用户能看懂）。"""
    keys = set(re.findall(r"^\s*'([^']+)':", _obj("LOADERS"), re.M))
    assert keys, "`LOADERS` 解析出 0 条 —— 形态变了（⛔ 别静默放过）"
    return keys


def load_dep() -> set[str]:
    """`LOAD_DEP`：必须等前置两路的那些路。"""
    m = re.search(r"const LOAD_DEP = new Set\(\[(.*?)\]\);", SHELL, re.S)
    assert m, "壳里找不到 `const LOAD_DEP = new Set([…])`"
    return set(re.findall(r"'([^']+)'", m.group(1)))


def boot_body() -> str:
    """`boot()` 的函数体（终点 = 下一个顶层函数）。"""
    i = SHELL.find("async function boot() {")
    assert i >= 0, "壳里找不到 `boot()`"
    j = SHELL.find("function bootErrorBanner()", i)
    assert j > i, "找不到 `boot()` 的终点（`bootErrorBanner`）"
    return SHELL[i:j]


def load_paths_body() -> str:
    """`loadPaths()` 的函数体（终点 = 下一个顶层声明）。"""
    i = SHELL.find("async function loadPaths(labels) {")
    assert i >= 0, "壳里找不到 `loadPaths()`"
    j = SHELL.find("async function boot() {", i)
    assert j > i
    return SHELL[i:j]
