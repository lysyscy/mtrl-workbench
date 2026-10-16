#!/usr/bin/env python
"""结构审计的**量测器**（2026-09-29 · 只读 · 一次性）：给"项目结构是否合理"提供**数字**，
⛔ 不替代判据、也不下结论 —— 判读由人做（与 `.codebuddy/skills/docs-audit/scripts/doc_inventory.py` 同款定位）。

**为什么要有它**：用户问「目录组织 / 模块划分 / 依赖关系 / 配置文件是否合理」——「感觉乱」不能当判据，
而仓里已有的尺子（`wiring_audit` / `chain_audit` / `asset_audit`）测的是**接线与死代码**，
⭐ **没人测"包与包之间的依赖方向"和"每包规模/层数与命名的一致性"** —— 本件就是补这两项。

量三组（都只读）：
  ① **顶层包规模**：件数 / 行数 / **包内文件命名模式**（各层有没有、名字一不一样）；
  ② **包间依赖**：`from app.X import …` 的**方向与次数**（⭐ 找出**环**与**反常方向** —— 底层包依赖业务包之类）；
  ③ **配置件清单**：仓根与 `backend/` 下的配置/入口件（存在与否 ＋ 大小）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_struct_scan.py`
"""

from __future__ import annotations

import collections
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
APP = REPO / "backend" / "app"

#: 已知的"层"文件（用来量"每个包有没有这几层、名字是否一致"）—— ⚠️ 这是**观察口径**，不是规范
LAYERS = ("domain.py", "service.py", "repository.py", "router.py", "models.py", "schemas.py",
          "api.py", "repository.py", "hooks.py", "imp_spec.py")


def packages() -> list[pathlib.Path]:
    return sorted(p for p in APP.iterdir() if p.is_dir() and not p.name.startswith("__"))


def scan_sizes() -> None:
    print("① 顶层包规模与包内件名（⚠️ 只列 ≤12 件的小包名，大包只给数）")
    print(f"{'包':<18}{'件数':>5}{'行数':>7}  层文件（有哪几个）")
    for p in packages():
        fs = sorted(p.rglob("*.py"))
        n = len(fs)
        lines = sum(len(f.read_text(encoding="utf-8", errors="replace").splitlines()) for f in fs)
        names = sorted({f.name for f in fs})
        layers = [x for x in LAYERS if x in names]
        others = [x for x in names if x not in LAYERS and not x.startswith("__")][:6]
        print(f"{p.name:<18}{n:>5}{lines:>7}  {' '.join(layers) or '（无标准层名）'}"
              + (f"  ／ 其它: {' '.join(others)}" if others else ""))


def scan_deps() -> None:
    print("\n② 包间依赖（`from app.X import` 的次数）—— ⭐ 看**环**与**反常方向**")
    edges: collections.Counter[tuple[str, str]] = collections.Counter()
    for p in packages():
        for f in p.rglob("*.py"):
            t = f.read_text(encoding="utf-8", errors="replace")
            for dep in re.findall(r"from app\.([A-Za-z_][A-Za-z0-9_]*)", t):
                if dep != p.name and (APP / dep).is_dir():
                    edges[(p.name, dep)] += 1
    for (a, b), n in sorted(edges.items()):
        print(f"   {a:<18} -> {b:<18} {n:>4}")
    print("   ⭐ 互为依赖（环）:")
    found = False
    for (a, b) in sorted(edges):
        if (b, a) in edges:
            print(f"      ⚠️ {a} <-> {b}（{edges[(a, b)]} / {edges[(b, a)]} 次）")
            found = True
    if not found:
        print("      （无 · ⚠️ 但注意：本扫描只看 `from app.X import`，`import app.X` 形式会漏）")


def scan_configs() -> None:
    print("\n③ 配置 / 入口件（存在 ＋ 大小）")
    cands = [REPO / ".env.example", REPO / ".env", REPO / ".gitignore", REPO / "README.md",
             REPO / "backend" / "alembic.ini", REPO / "backend" / "uv.lock",
             REPO / "backend" / "pyproject.toml",
             REPO / "backend" / "pytest.ini", REPO / "backend" / "tests" / "conftest.py",
             REPO / "backend" / "app" / "main.py", REPO / "backend" / "app" / "core" / "config.py"]
    for c in cands:
        ok = c.exists()
        size = f"{c.stat().st_size:>7} B" if ok else "  —— 缺"
        print(f"   {'✓' if ok else '·'} {size}  {c.relative_to(REPO)}")
    env = REPO / ".env.example"
    if env.exists():
        keys = [l.split("=")[0].strip() for l in env.read_text(encoding="utf-8", errors="replace").splitlines()
                if l.strip() and not l.strip().startswith("#") and "=" in l]
        print(f"   ⭐ `.env.example` 共 {len(keys)} 个键：" + "、".join(keys))


if __name__ == "__main__":
    print(f"=== 结构量测（只读）· {APP} ===\n")
    scan_sizes()
    scan_deps()
    scan_configs()
    sys.exit(0)
