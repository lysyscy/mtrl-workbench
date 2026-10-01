#!/usr/bin/env python
"""`TAIL-62` **反向灵敏度**：证明 `tests/test_naive_export_parity.py` 真的有区分力。

⭐ 为什么必须有本件：`fl/jc/pj` 三件已经**只是薄委托**，真正的实现在 `naive_export`
   ⇒ 若那个内核被改坏而测试**还全绿**，就等于没有护栏（本仓 2026-09-21 的教训：
   `_mut_boot.py` / `_mut_m03pay.py` 曾**静默崩掉**、无人知道）。

| 变异 | 怎么改 | 期望（必须变红） |
|---|---|---|
| A · 内核丢掉**序号列** | `if seq_key and key == seq_key: return n` ⇒ `if False: return n` | `test_jc_序号列写行号_列宽上限28` |
| B · 内核**总是写合计行** | `if total_keys and (rows or ()):` ⇒ `if (rows or ()):` | `test_pj_没有合计行`（页面没有 ⇒ 导出**不能**补） |

跑法：`backend/.venv/Scripts/python.exe tools/_mut_naive.py`（rc=0 = 两处都抓到且**逐字节复原**）。
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
KERNEL = ROOT / "backend" / "app" / "report_export" / "naive_export.py"
TEST = "tests/test_naive_export_parity.py"
#: ⚠️ 2026-10-01（`TAIL-204` 第 7 步）换落点：原 `.workbuddy/scratch` 那个根已不存在（`mkdir` ⇒ 复活旧根）。
BAK = ROOT / ".codebuddy" / "work" / "00-scratch" / "naive_export.py.bak-mutnaive"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"

MUTS = [
    ("A · 丢掉序号列",
     "        if seq_key and key == seq_key:\n            return n",
     "        if False:                      # 变异A：序号列被摘掉\n            return n",
     "test_jc_序号列写行号_列宽上限28"),
    ("B · 总是写合计行",
     "    if total_keys and (rows or ()) :",
     "    if (rows or ()) :                  # 变异B：不管有没有 total_keys 都写合计",
     "test_pj_没有合计行"),
]


def run_test(which: str | None = None) -> tuple[int, str]:
    cmd = [str(PY), "-m", "pytest", "-q", TEST if which is None else f"{TEST}::{which}",
           "-p", "no:cacheprovider", "--tb=no"]
    r = subprocess.run(cmd, cwd=str(ROOT / "backend"), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "")[-400:]


def main() -> int:
    orig = KERNEL.read_bytes()
    BAK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(KERNEL, BAK)
    h0 = hashlib.md5(orig).hexdigest()
    rc = 0
    try:
        base_rc, _ = run_test()
        print(f"基线：pytest {TEST} ⇒ rc={base_rc}（应为 0）")
        if base_rc != 0:
            print("❌ 基线就是红的 ⇒ 先修测试再谈变异"); return 1
        for label, old, new, node in MUTS:
            t = orig.decode("utf-8")
            if old not in t:
                print(f"❌ {label}：找不到锚点（代码改过 ⇒ 本脚本要同步改）"); return 1
            KERNEL.write_text(t.replace(old, new, 1), encoding="utf-8", newline="")
            m_rc, tail = run_test(node)
            ok = m_rc != 0
            print(f"{label}：{node} ⇒ rc={m_rc} {'✅ 抓到' if ok else '❌ 没抓到（假绿！）'}")
            rc = rc if ok else 1
            KERNEL.write_bytes(orig)
    finally:
        KERNEL.write_bytes(orig)
    h1 = hashlib.md5(KERNEL.read_bytes()).hexdigest()
    same = h1 == h0
    print(f"复原：MD5 {'一致 ✅' if same else '❌ 不一致'}")
    if same:
        BAK.unlink(missing_ok=True)
    return rc if same else 1


if __name__ == "__main__":
    sys.exit(main())
