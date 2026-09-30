"""`TAIL-195` 批 2（拆两个环）· **只读量测** —— 把两环的**真实引用面 ＋ 被 import 的符号**数清楚。

输出五节：
  ① `app/report_export/**` → 业务包（**正向边**，方案 §3.1 估 ~10 处）
  ② 业务包 → `app.report_export`（**反向边**，方案 §3.1 估 ~14 处）
  ③ `backend/tests/**` → `app.report_export`（引用面；方案说测试 ≈60 处）
  ④ `mod03` ⇄ `mod05`（第二条环）
  ⑤ `app.report_export` 被 import 的**符号**清单（设计接缝用 —— 决定"搬中立件"还是"注册表按名取"）

⚠️ 纯只读（不写任何文件）；
⭐ 认 `Import` 与 `ImportFrom`（含函数内延迟 import —— `ast.walk` 全树扫）＋ 相对 import 跳过（本仓没有）。

用法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_t195b2_survey.py`
"""

from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend" / "app"
TESTS = ROOT / "backend" / "tests"
RE = "app.report_export"
BIZ_PREFIXES = ("app.mod", "app.home", "app.import_kit")


def _imports(path: Path) -> list[tuple[int, str, tuple[str, ...]]]:
    """→ `[(行号, 模块名, 名字元组)]`（`import x` 的名字取 `x`）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[int, str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.append((node.lineno, a.name, (a.name,)))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            out.append((node.lineno, node.module, tuple(a.name for a in node.names)))
    return out


def _files(base: Path) -> list[Path]:
    return sorted(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)


def _is_re(m: str) -> bool:
    return m == RE or m.startswith(RE + ".")


def _is_biz(m: str) -> bool:
    return any(m.startswith(p) for p in BIZ_PREFIXES)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    app_files = _files(APP)
    test_files = _files(TESTS)

    fwd: list[str] = []          # ① report_export → 业务
    back: list[str] = []         # ② 业务 → report_export
    tst: list[str] = []          # ③ tests → report_export
    syms: Counter[str] = Counter()
    mod03_05: list[str] = []     # ④
    n_back_files: set[str] = set()
    n_tst_files: set[str] = set()

    for p in app_files:
        rel = p.relative_to(ROOT).as_posix()
        in_re = rel.startswith("backend/app/report_export/")
        for lineno, mod, names in _imports(p):
            if in_re and _is_biz(mod):
                fwd.append(f"{rel}:{lineno}  {mod}  -> {', '.join(names)}")
            if (not in_re) and _is_re(mod):
                back.append(f"{rel}:{lineno}  {mod}  -> {', '.join(names)}")
                n_back_files.add(rel)
                syms[mod] += 1
            if rel.startswith("backend/app/mod03") and mod.startswith("app.mod05"):
                mod03_05.append(f"mod03->mod05  {rel}:{lineno}  {mod}  -> {', '.join(names)}")
            if rel.startswith("backend/app/mod05") and mod.startswith("app.mod03"):
                mod03_05.append(f"mod05->mod03  {rel}:{lineno}  {mod}  -> {', '.join(names)}")

    for p in test_files:
        rel = p.relative_to(ROOT).as_posix()
        for lineno, mod, names in _imports(p):
            if _is_re(mod):
                tst.append(f"{rel}:{lineno}  {mod}  -> {', '.join(names)}")
                n_tst_files.add(rel)

    def show(title: str, rows: list[str]) -> None:
        print(f"\n=== {title}（{len(rows)} 处）===")
        for r in rows:
            print("  " + r)

    show("① app/report_export/** → 业务包（正向边）", fwd)
    show("② 业务包 → app.report_export（反向边）", back)
    print(f"\n  （② 涉及 {len(n_back_files)} 个文件）")
    show("③ backend/tests/** → app.report_export", tst)
    print(f"\n  （③ 涉及 {len(n_tst_files)} 个文件）")
    show("④ mod03 ⇄ mod05", mod03_05)
    print("\n=== ⑤ app.report_export 被 import 的**模块**（反向边 + 测试合并计数）===")
    for m, c in syms.most_common():
        print(f"  {c:>3}  {m}")
    print(f"\n合计：正向 {len(fwd)} · 反向 {len(back)} · 测试 {len(tst)} · "
          f"环② {len(mod03_05)} ⇒ 两环相关引用 {len(fwd) + len(back) + len(tst) + len(mod03_05)} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
