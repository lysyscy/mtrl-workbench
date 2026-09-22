"""反向灵敏度 · `ACC-PRJ-OWN-001` 的 `001-09`（`TAIL-29`-①）。

做法：把实现故意改坏，确认对应断言**确实变红**，然后逐字节复原（MD5 校验）。

用法：`python tools/_mut_own_109.py`
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PY = BACKEND / ".venv" / "Scripts" / "python.exe"
CLS = BACKEND / "app" / "mod03_notice" / "classify.py"

# (说明, 原名, 改成, 期望变红的测试)
MUTS = [
    (
        "M1 不过滤（剔除行照样参与整批校验 —— 就是修之前的行为）",
        "    return [(i, row) for i, row in enumerate(rows or ()) if not is_excluded(row, rules)]",
        "    return list(enumerate(rows or ()))",
        "test_规则剔除行不参与归属校验",
    ),
    (
        "M2 序号被重排（不保留原序号 ⇒ 落库会串行）",
        "    return [(i, row) for i, row in enumerate(rows or ()) if not is_excluded(row, rules)]",
        "    return [(n, row) for n, (_, row) in enumerate(\n"
        "        [(i, r) for i, r in enumerate(rows or ()) if not is_excluded(r, rules)])]",
        "test_剔除行只是不参与校验_其余行原序号不被挪动",
    ),
    (
        "M3 另写一份判定（只看空项目名，漏掉规则剔除）",
        "    return [(i, row) for i, row in enumerate(rows or ()) if not is_excluded(row, rules)]",
        "    return [(i, row) for i, row in enumerate(rows or ())\n"
        "            if str(row.get('project_name') or '').strip()]",
        "test_规则剔除行不参与归属校验",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(name: str) -> bool:
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", f"tests/test_acc_prj_own.py::{name}"],
        cwd=str(BACKEND), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return r.returncode == 0


def main() -> int:
    before = (CLS.read_bytes(), md5(CLS))
    hits = 0
    try:
        for desc, old, new, expect in MUTS:
            raw = CLS.read_bytes()
            text = raw.decode("utf-8")
            assert text.count(old) == 1, f"{desc}：锚串命中 {text.count(old)} 次，脚本停手"
            CLS.write_bytes(text.replace(old, new, 1).encode("utf-8"))
            passed = run_one(expect)
            tag = "✅ 命中（断言变红）" if not passed else "❌ 未命中（仍绿 ⇒ 假绿！）"
            if not passed:
                hits += 1
            print(f"  {tag}  {desc}\n        → 期望变红：{expect}")
            CLS.write_bytes(raw)
    finally:
        ok = CLS.read_bytes() == before[0]
        print(f"\n  反向灵敏度：{hits}/{len(MUTS)} 命中")
        print(f"  复原校验（MD5 逐字节）：{'✅ 复原' if ok else '❌ 没复原！'}  md5={md5(CLS)}")
    return 0 if hits == len(MUTS) else 1


if __name__ == "__main__":
    sys.exit(main())
