"""⭐ 自造剪刀的**唯一量法** ＋ 合法白名单（`TAIL-219` 批 3 · 2026-10-04）。

## 为什么有它（大白话）

壳原先是**一坨纯文本** ⇒ 谁想问它一句人话（"这页有哪些按钮 / 动作 / 常量表"），都只能
**自己拿剪刀**从这坨文本里按字面剪一段（实测 **48 把 / 33 件** ＋ 就地取片 103 处）。
语义窗口 `tools/audit/shell_api.py` 立起来之后，要保证的是 ——
**老账分批还，新账当场拦** ⇒ 判词 = **剪刀清单只许变短**。

## 谁守它

`backend/tests/test_shell_api.py::test_壳的语义剪刀清单只许变短`（`@acc()` ⇒ 不涨判据点）：
新长出一把 ⇒ 红；白名单里有条目已经不是剪刀了（换掉了没销号）⇒ 红。

## 量法（⛔ 与只读量测件的分工）

- **本件（判据用）**：AST 认**代码** —— 注释 / docstring 里写着 `SHELL.find(` 这类字样**不算**。
- `.scratch/local/_tail219_scissors.py`（人看一眼的只读量测件）：正则认**文本** ⇒ 会被
  注释字样骗（实测把 `test_wired_m03_list._nt_region` 的 docstring 误报成一把）。本件是**唯一真源**。
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
#: 与只读量测件同口径：不算活区的目录
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache", "artifacts", "var", "data", "exports", "dist"}
#: ⭐ 两个**所有者**：字节层（`shell_source`）与语义层（`shell_api`）本来就在读壳，⛔ 不算剪刀
OWNERS = {"tools/audit/shell_api.py", "tools/audit/shell_source.py"}
_EXTRACT_ATTRS = {"find", "split", "index", "count"}

#: ⭐ **合法剪刀白名单** —— 每条都要写清"为什么正当"；⛔ 别往里加条目来消红。
#: · `非测试面`：尺子 / 一次性件 / 探针**本来就有权**直接读壳（施工图 §13.3 已登记）
#: · `测试侧`：登记为正当 —— 两端**不是**具名之物（页内标记 / HTML 标签 / 泛型标记对），
#:   或**两端具名但"区间"本身不是具名之物**（窗里 ⛔ 不设万能 `between(a,b)`）。
ALLOW: dict[str, str] = {
    # ── 非测试面 · 正当（9）─────────────────────────────────────────
    "backend/tests/shell_src.py::dl_kernel": "根因守卫：抽通用件后要'两段拼起来看'（`TAIL-67`）",
    "backend/tests/shell_src.py::tbl_kernel": "同上（`TAIL-64` P0 表外壳）",
    "backend/tests/shell_src.py::fbar_kernel": "同上（`TAIL-64` P4-a 筛选栏）",
    "backend/tests/shell_src.py::pjb_kernel": "同上（`TAIL-64` P4-d-a 项目按钮）",
    "tools/audit/ui_parity.py::main": "尺子入口：人看一眼逐页对照",
    "tools/oneoff/_apply_no_chg.py::main": "一次性件（改壳字节）",
    "tools/oneoff/_p4b_ghosts.py::ghosts": "一次性件（清幽灵条目）",
    "tools/oneoff/_prune_ghosts.py::ghost_keys": "一次性件（清幽灵条目）",
    "tools/probe/_probe_material.py::main": "真机探针",
    # ── 测试侧 · 登记正当（8）───────────────────────────────────────
    "backend/tests/test_acc_home_todo.py::_home": "终点是**页内标记**（`  return \\``）⇒ 不是具名之物",
    "backend/tests/test_imp_shell.py::_imp_region": "两端具名（函数 / 动作），但**区间**非具名之物 ⇒ 见施工图 §14",
    "backend/tests/test_shell_render.py::_render_body": "两端具名（`render` / `const V`），但**区间**非具名之物",
    "backend/tests/test_tail04_export.py::_m08_card_head": "取的是卡头 **HTML 片段**（`<h4>…</h4>`）⇒ 非具名之物",
    "backend/tests/test_ux_buttons.py::_btn": "取的是**开标签**（`<button … >`）⇒ 非具名之物",
    "backend/tests/test_ux_states.py::_seg": "**泛型**标记对（`marker`/`stop` 由调用方给，端点各不相同）",
    "backend/tests/test_wired_m03_action.py::_slice": "**泛型**标记对（端点混着动作名 / 片段 / 注释）",
    "backend/tests/test_wired_m03_pay.py::_slice": "**泛型**标记对（同上）",
}


def _shell_obj(node: ast.expr) -> bool:
    """`SHELL`（裸名）或 `X.SHELL`（带限定，如 `U.read_shell()` 那一族）⇒ True。

    ⚠️ 2026-10-04 实测补的**第二版**：第一版只认裸名 `SHELL` ⇒ 漏掉 `U.SHELL` / `U.read_shell()`
       （`tools/oneoff/_prune_ghosts.py` 那种写法）—— 又是"**量法比发生面窄**"（本仓老课）。
    """
    if isinstance(node, ast.Name):
        return node.id == "SHELL"
    return isinstance(node, ast.Attribute) and node.attr == "SHELL"


def _is_scissors(fn: ast.FunctionDef) -> bool:
    """函数体里"从壳文本里按字面取片段" ⇒ True。

    ⚠️ 只认**代码**（`ast.walk` 走的是语法树 ⇒ 注释与 docstring 里的字样**不算**）。
    """
    has_shell = False
    has_re = False
    for node in ast.walk(fn):
        if _shell_obj(node):
            has_shell = True
        elif isinstance(node, ast.Attribute):
            if node.attr in _EXTRACT_ATTRS and _shell_obj(node.value):
                return True
            if node.attr == "read_shell":            # `U.read_shell()`（带限定的读取）
                return True
        elif isinstance(node, ast.Subscript):
            if _shell_obj(node.value):
                return True
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id == "read_shell":
                return True
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "re":
                has_re = True
    return has_shell and has_re          # `re.<x>(… , SHELL)` 那种"正则式"剪刀


def scan() -> list[tuple[str, str]]:
    """活区里所有"自造剪刀"的 `(相对路径, 函数名)`（名字不以 `test_` 开头的才叫剪刀）。"""
    out: list[tuple[str, str]] = []
    for p in sorted(ROOT.rglob("*.py")):
        if any(x in p.parts for x in SKIP_DIRS):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith((".scratch/", ".artifacts/", "docs/archive/")) or "/_归档-" in rel or rel in OWNERS:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.FunctionDef) and not node.name.startswith("test_")
                    and _is_scissors(node)):
                out.append((rel, node.name))
    return out


def main() -> int:
    """`python -m tests.shell_scissors`（在 `backend/` 下）—— 人看一眼当前剪刀清单（⛔ 不是判据）。"""
    found = scan()
    print(f"自造剪刀：{len(found)} 把 / {len({r for r, _ in found})} 件（白名单 {len(ALLOW)} 条）")
    for rel, name in found:
        flag = "OK " if f"{rel}::{name}" in ALLOW else "❗新"
        print(f"  [{flag}] {rel}::{name}")
    for key in sorted(set(ALLOW) - {f"{r}::{n}" for r, n in found}):
        print(f"  [幽灵] {key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
