"""反向灵敏度 · `TAIL-36`（项目三小件唯一实现）。

做法：把实现**故意改坏**（口径 / 身份 / 形状），确认对应断言**确实变红**；
      然后**逐字节复原**（MD5 校验）。不红 ⇒ 断言是假绿。

用法：`python tools/_mut_core_projects.py`
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PY = BACKEND / ".venv" / "Scripts" / "python.exe"

CORE = BACKEND / "app" / "core" / "projects.py"
S5 = BACKEND / "app" / "mod05_flow" / "service.py"

# (说明, 文件, 原名, 改成, 期望变红的测试名)
MUTS = [
    (
        "M1 归并键改用「项目全名」（口径错：§2.7.4 是仓库名）",
        CORE,
        'return p.warehouse_name or f"#{p.id}"',
        'return p.name_full or f"#{p.id}"',
        "test_归并键就是仓库名",
    ),
    (
        "M2 归并键改用「展示名」（展示名会改 ⇒ 键会漂）",
        CORE,
        'return p.warehouse_name or f"#{p.id}"',
        'return p.disp or f"#{p.id}"',
        "test_展示名不参与归并_改展示名不得改变归并键",
    ),
    (
        "M3 仓库名缺失时拿全名顶上（违反「不猜」）",
        CORE,
        'return p.warehouse_name or f"#{p.id}"',
        'return p.warehouse_name or p.name_full or f"#{p.id}"',
        "test_仓库名缺失时退化为id而不猜",
    ),
    (
        "M4 显示名优先级改序（不给展示名优先）",
        CORE,
        "return p.disp or p.warehouse_name or p.name_full or f\"#{p.id}\"",
        "return p.name_full or p.warehouse_name or p.disp or f\"#{p.id}\"",
        "test_显示名优先级为展示名到仓库名到全名到id",
    ),
    (
        "M5 项目索引改用仓库名做键（下游按 id 找行会全空）",
        CORE,
        "{p.id: p for p in s.execute(select(Project)).scalars().all()}",
        "{p.warehouse_name: p for p in s.execute(select(Project)).scalars().all()}",
        "test_项目索引以id为键",
    ),
    (
        "M6 mod05 又抄一份本地 project_key（唯一实现被破坏）",
        S5,
        "from app.core.projects import project_index, project_key, project_label",
        "from app.core.projects import project_index, project_key, project_label\n"
        "def project_key(p):  # 故意：又抄一份\n"
        "    return \"抄的\"",
        "test_三件是同一个函数对象而不是各自包一层",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(test_name: str) -> bool:
    """跑单个测试 → True 表示**通过**。"""
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", f"tests/test_core_projects.py::{test_name}"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return r.returncode == 0


def main() -> int:
    files = sorted({m[1] for m in MUTS})
    before = {p: (p.read_bytes(), md5(p)) for p in files}
    hits = 0
    try:
        for i, (desc, path, old, new, expect_test) in enumerate(MUTS, 1):
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            assert text.count(old) == 1, f"{desc}：锚串命中 {text.count(old)} 次，脚本停手"
            path.write_bytes(text.replace(old, new, 1).encode("utf-8"))

            passed = run_one(expect_test)
            flag = "✅ 命中（断言变红）" if not passed else "❌ 未命中（断言仍绿 ⇒ 假绿！）"
            if not passed:
                hits += 1
            print(f"  {flag}  {desc}\n        → 期望变红的断言：{expect_test}")

            path.write_bytes(raw)  # 立刻逐字节复原
    finally:
        ok = all(path.read_bytes() == before[path][0] for path in files)
        print()
        print(f"  反向灵敏度：{hits}/{len(MUTS)} 命中")
        print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原！'}")
        for path in files:
            print(f"      {path.relative_to(ROOT)}  md5={md5(path)}")
    return 0 if hits == len(MUTS) else 1


if __name__ == "__main__":
    sys.exit(main())
