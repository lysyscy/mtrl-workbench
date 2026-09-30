"""`TAIL-195` 批 1（结构债）· `models_registry.py` 挪出 `core` —— **机械迁移**（一次性留痕）。

做两件事：
  1. `git mv backend/app/core/models_registry.py backend/app/models_registry.py`
  2. 全仓（`backend/` ＋ `tools/`）把 **`app.core.models_registry`** 替换成 **`app.models_registry`**
     —— 逐文件断言命中数；**命中 0 的件报错并停手**（防"路径写法变了没跟上"那族静默）。

⚠️ 本件**只做 import 路径的机械替换**（字节级替换、⛔ 不动行尾）：
   判据侧（`test_schema_drift.py` 的靶常量与文案）＋ 新守卫（`tests/test_layering.py`）由本批其它步骤负责。

用法：
    python tools/oneoff/_t195b1_move.py --dry-run     # 只数、不写
    python tools/oneoff/_t195b1_move.py --write
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD = ROOT / "backend" / "app" / "core" / "models_registry.py"
NEW = ROOT / "backend" / "app" / "models_registry.py"

IMPORT_OLD = "app.core.models_registry"
IMPORT_NEW = "app.models_registry"

#: 扫描面 —— `backend/` 与 `tools/`（下同；⛔ 别扫 `.venv` / `__pycache__`）
SCAN_DIRS = (ROOT / "backend", ROOT / "tools")
SKIP_PARTS = {".venv", "__pycache__", "node_modules", ".mypy_cache"}
#: ⛔ 跳过本件自己 —— 它**必然**写着那两串字面量（否则没法做替换），
#:   把自己算进去会让"引用点计数"里凭空多 2 处、还会把本件改写坏。
SKIP_NAMES = {Path(__file__).name}


def _targets() -> list[Path]:
    out: list[Path] = []
    for d in SCAN_DIRS:
        for p in sorted(d.rglob("*.py")):
            if any(part in SKIP_PARTS for part in p.parts) or p.name in SKIP_NAMES:
                continue
            out.append(p)
    return out


def main() -> int:
    write = "--write" in sys.argv
    if not OLD.exists():
        print(f"⛔ 源文件不在：{OLD}（多半已经搬过了）")
        return 1
    if NEW.exists():
        print(f"⛔ 目标已存在：{NEW}（⛔ 别覆盖）")
        return 1

    # ---- 1) 先把要改的引用点全部数清楚（动文件之前取完数据）----
    hits: list[tuple[Path, int]] = []
    for p in _targets():
        n = p.read_bytes().decode("utf-8").count(IMPORT_OLD)
        if n:
            hits.append((p, n))
    total = sum(n for _, n in hits)
    print(f"引用点：{len(hits)} 个文件 · 共 {total} 处 `{IMPORT_OLD}`")
    for p, n in hits:
        print(f"    {p.relative_to(ROOT).as_posix()}  ×{n}")
    if total == 0:
        print("⛔ 一处都没数到 —— 路径写法变了？停手。")
        return 1

    if not write:
        print("\n（dry-run：未动任何文件。加 --write 执行）")
        return 0

    # ---- 2) git mv（保历史）----
    r = subprocess.run(["git", "mv", str(OLD), str(NEW)], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"⛔ git mv 失败：{r.returncode}\n{r.stdout}\n{r.stderr}")
        return 1
    print(f"\n✅ git mv：{OLD.relative_to(ROOT)} → {NEW.relative_to(ROOT)}")

    # ---- 3) 逐文件字节级替换（⛔ 不动行尾 / 编码）----
    for p, n in hits:
        raw = p.read_bytes()
        text = raw.decode("utf-8")
        assert text.count(IMPORT_OLD) == n, f"{p}：替换前计数变了，停手"
        p.write_bytes(text.replace(IMPORT_OLD, IMPORT_NEW).encode("utf-8"))
        assert p.read_bytes().decode("utf-8").count(IMPORT_OLD) == 0, f"{p}：替换后仍有残留"
    print(f"✅ 已替换 {len(hits)} 个文件（{total} 处）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
