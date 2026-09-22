#!/usr/bin/env python
"""装配审查（wiring_audit）—— 查「**口径说了要做的事，代码里到底有没有真的接上**」。

**为什么存在**（2026-09-17 实测事故，本文件就是它的产物）：
    `ensure_batch_settled()`（「归属未走完 ⇒ 整批不入库」·《说明书》§2.7.4）**写好了**、
    判据 `ACC-PRJ-OWN-001` **8/8 绿** —— 但**抓取链路从没调用它** ⇒ 61 条未归属单据照样入库。
    ⭐ **判据绿 ≠ 链路对**：判据测的是**零件（纯函数）**，**不测装配（有没有被调用）**。
    同类事故还有：`resolve_ownership()` 早就写好，抓取链路也没用它。

### 靠什么做到「零人工登记」
本仓有一条**既有惯例**：**口径性函数的 docstring 里会引判据点号**（`ACC-XXX-001/001-08` 或 `001-08`）。
⇒ **"这条函数的 docstring 引了判据点" ＝ "它是某条口径的实现"** ⇒ 它**必须**有生产调用方。
**不需要新建登记表** —— 检查的是**代码自己说过的话**。

### 三把尺子
| 代号 | 检查 | 判据 |
|---|---|---|
| `W1` | **口径性函数零调用方**（docstring 引了判据点 ⇒ 它是某条口径的实现） | 生产代码里零引用 ⇒ **红** |
| `W2` | **死代码**（公共函数 / 类在全站零引用） | 疑似 ⇒ **黄**（走 `wiring_expected.txt` 登记） |
| `W3` | **口径 ↔ 实现**一览（哪些判据点有生产实现兜着） | 信息（配合 `doc_audit` 的 `T7`） |

### 三条防噪音纪律（照 `doc_audit` 的做法）
1. **导入 ≠ 装配** —— 只统计**表达式里真的用了它**（`Name`/`Attribute` 节点），
   `import` 语句**不算**。⭐ 这正是本次事故的形态：**函数被写好、甚至被 import，但没人调用**。
2. **自递归不算装配** —— 引用的行号落在**自己函数体内**的，不计。
3. **白名单只准变短** —— 已知的待清理项登记在 `tools/wiring_expected.txt`，改完一行删一行。

用法：
    python tools/wiring_audit.py             # 人读报告（有红即非零退出）
    python tools/wiring_audit.py --json      # 机器可读
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
TESTS = ROOT / "backend" / "tests"
EXPECTED = ROOT / "tools" / "wiring_expected.txt"

# 判据点号两种写法都要认：完整 `ACC-XXX-001/001-08`（取 `ACC-…-00X`）· 简写 `001-08`
ACC_RE = re.compile(r"ACC-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}")
POINT_RE = re.compile(r"\b(\d{3}-\d{2})\b")

# 由框架调用的装饰器 —— 这些函数「没人显式调用」是对的吗？不是：它们由 FastAPI 注册后调用
FRAMEWORK_DECORATOR_HINTS = (
    "router.", "app.", "page_router.", "actions_router.", "api_router.",
    "staticmethod", "classmethod", "property", "abstractmethod", "pytest.",
)


def rel(p: Path) -> str:
    return str(p).replace("\\", "/").split("mtrl-workbench/")[-1]


@dataclass
class Def:
    name: str
    kind: str                      # func / async / class
    file: str
    line: int
    end_line: int
    doc: str = ""
    decorators: tuple[str, ...] = ()

    @property
    def public(self) -> bool:
        return not self.name.startswith("_")

    @property
    def accs(self) -> list[str]:
        return sorted(set(ACC_RE.findall(self.doc)))

    @property
    def points(self) -> list[str]:
        return sorted(set(POINT_RE.findall(self.doc)))

    @property
    def cites_spec(self) -> bool:
        """docstring 引了判据点 ⇒ 它是**某条口径的实现**（本仓既有惯例）。"""
        return bool(self.accs or self.points)

    @property
    def framework_wired(self) -> bool:
        return any(d.startswith(FRAMEWORK_DECORATOR_HINTS) for d in self.decorators)


def decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return decorator_name(node.func)
    if isinstance(node, ast.Attribute):
        return f"{decorator_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return ""


def scan(paths: list[Path]) -> tuple[list[Def], dict[str, list[tuple[str, int]]]]:
    """扫生产代码 → `(定义列表, 引用位置表)`。

    ⚠️ **只收表达式里的 `Name`/`Attribute`** —— `import` 语句**不算装配**
       （`alias` 节点不是 `Name`）；这正是要抓的形态：**导入了却没调用**。
    """
    defs: list[Def] = []
    refs: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for p in paths:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        f = rel(p)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else (
                    "async" if isinstance(node, ast.AsyncFunctionDef) else "func"
                )
                defs.append(Def(
                    name=node.name, kind=kind, file=f, line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
                    doc=ast.get_docstring(node) or "",
                    decorators=tuple(decorator_name(d) for d in node.decorator_list),
                ))
            elif isinstance(node, ast.Name):
                refs[node.id].append((f, node.lineno))
            elif isinstance(node, ast.Attribute):
                refs[node.attr].append((f, node.lineno))
    return defs, refs


def load_expected() -> set[str]:
    if not EXPECTED.exists():
        return set()
    out: set[str] = set()
    for line in EXPECTED.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.add(s)
    return out


def external_refs(d: Def, refs: dict[str, list[tuple[str, int]]]) -> list[tuple[str, int]]:
    """该定义**在别处**被引用的位置（排除自己函数体内的自引用）。"""
    return [
        (f, ln) for f, ln in refs.get(d.name, ())
        if not (f == d.file and d.line <= ln <= d.end_line)
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="装配审查")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args()

    paths = sorted(p for p in APP.rglob("*.py") if "__pycache__" not in str(p))
    defs, refs = scan(paths)
    # ⚠️ 测试里的引用**单独统计** —— 不能和生产引用混为一谈：
    #    · **防回归**类断言（`assert_*`，如"外部数据源只能是 i8"）**由测试调用就是对的** ⇒ 不该报红；
    #    · 而 `ensure_batch_settled` 那种**只有测试调、生产不调**的，正是"测了零件没装上车"的形态 ⇒ 要人看。
    _, test_refs = scan(sorted(p for p in TESTS.rglob("*.py") if "__pycache__" not in str(p)))
    expected = load_expected()

    def has_test_ref(d: Def) -> bool:
        return bool(test_refs.get(d.name))

    # ---- W1：口径性函数必须有人调用（本次事故的那把尺子）
    w1: list[Def] = []       # 红：生产、测试**都**没人用 ⇒ 铁定死代码
    w1b: list[Def] = []      # 黄：只有测试用 ⇒ 要人判断（防回归？还是没装上车？）
    cited_total = 0
    for d in defs:
        if not d.cites_spec:
            continue
        cited_total += 1
        if d.framework_wired:
            continue                                   # 由框架注册后调用
        if external_refs(d, refs):
            continue
        if has_test_ref(d):
            if f"W1b {d.file}:{d.name}" not in expected:
                w1b.append(d)
        elif f"W1 {d.file}:{d.name}" not in expected:
            w1.append(d)

    # ---- W2：死代码（全站零引用、非框架装配）
    w2: list[Def] = []
    for d in defs:
        if not d.public or d.cites_spec or d.framework_wired:
            continue
        if external_refs(d, refs):
            continue
        if f"W2 {d.file}:{d.name}" in expected:
            continue
        w2.append(d)

    # ---- 可消号（已修好但白名单还留着）
    stale = sorted(
        e for e in expected
        if not any(
            (e == f"W1 {d.file}:{d.name}" or e == f"W2 {d.file}:{d.name}")
            for d in defs
        )
    )

    if args.json:
        print(json.dumps({
            "scanned_files": len(paths), "defs": len(defs), "cited_spec": cited_total,
            "W1": [{"file": d.file, "name": d.name, "line": d.line,
                    "accs": d.accs, "points": d.points} for d in w1],
            "W1b_test_only": [{"file": d.file, "name": d.name, "line": d.line,
                               "accs": d.accs, "points": d.points} for d in w1b],
            "W2": [{"file": d.file, "name": d.name, "line": d.line} for d in w2],
            "stale_expected": stale,
        }, ensure_ascii=False, indent=1))
        return 1 if (w1 or w1b) else 0

    print("=" * 78)
    print(" 装配审查 · wiring_audit —— 「口径说了要做的事，代码里接上了吗」")
    print("=" * 78)
    print(f"扫描 {len(paths)} 个生产文件 · {len(defs)} 个定义 · 其中**引了判据点的口径性函数** {cited_total} 个")
    print()

    print("─ W1 · 口径性函数**零调用方**（红：写好了、连测试都没用过 ⇒ 铁定死代码）")
    if w1:
        for d in w1:
            tag = "、".join(d.accs + d.points) or "(未标判据点)"
            print(f"  ❌ {d.file}:{d.line}  {d.name}()")
            print(f"       口径：{tag}")
            print(f"       说明：docstring 引了判据点 ⇒ 它是这条口径的实现，"
                  f"但**生产与测试都没人调用它** ⇒ 口径没接上")
    else:
        print("  ✅ 无")
    print()

    print("─ W1b · 口径性函数**只有测试调用**（红：**默认阻断** —— 登记白名单才放行）")
    if w1b:
        for d in w1b:
            tag = "、".join(d.accs + d.points) or "(未标判据点)"
            print(f"  ❌ {d.file}:{d.line}  {d.name}()   ← 口径 {tag}")
        print("  ℹ️ **为什么默认阻断**：本项目实测的形态是「**测了零件、没装上车**」——")
        print("     测试全绿、判据全绿，**生产链路却没人调用它**（`ensure_batch_settled` 就是这么漏的）。")
        print("     ⭐ 只有两类可以登记放行：① **防回归 / 配置守卫**（检查常量，测试调就够了）")
        print("     ② **功能尚未做到那一步**（如「用户指定归属时补关键词」的校验）—— 登记时写清是哪一类。")
    else:
        print("  ✅ 无")
    print()

    print("─ W2 · 疑似死代码（黄：公共函数 / 类，全站零引用）")
    if w2:
        for d in w2[:40]:
            print(f"  ⚠️  {d.file}:{d.line}  {d.name}  [{d.kind}]")
        if len(w2) > 40:
            print(f"  … 另有 {len(w2) - 40} 个")
        print(f"  ℹ️ 确认要留 ⇒ 登记 `W2 <文件>:<名字>` 到 tools/wiring_expected.txt；要删 ⇒ 直接删")
    else:
        print("  ✅ 无")
    print()

    if stale:
        print("─ 可消号（白名单里已修好、该删行了）")
        for e in stale:
            print(f"  ✔ {e}")
        print()

    print(f"结论：**W1 必须修 {len(w1)}**（生产+测试都没人调）· "
          f"**W1b 必须修 {len(w1b)}**（只有测试调 · 未登记放行）· "
          f"W2 待清理 {len(w2)}（死代码台账 · 随区清）")
    print("⚠️ 通了不代表口径全对 —— 它只保证「**写了的口径函数有人调用**」；"
          "口径**写得对不对**仍要看 `doc_audit` 与人。")
    return 1 if (w1 or w1b) else 0


if __name__ == "__main__":
    sys.exit(main())
