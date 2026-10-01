#!/usr/bin/env python
"""`T12`（文档分层与命名约定）的**反向灵敏度** —— 造三处"布局违规"，看它会不会红。

⭐ 依据本仓纪律：**新加的尺子必须证明"改坏了它会红"**（否则就是假绿）。
   ⚠️ 每次造完**立即删掉**（`finally`）⇒ ⛔ 不留残件。
用法：`backend\\.venv\\Scripts\\python.exe tools\\_mut_t12.py`（期望输出 `3/3 变红 ＋ 复原干净`）
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")

CASES = [
    ("plans/ 里冒出第三份活文档", ROOT / ".codebuddy" / "plans" / "_tmp_t12_第三份.md"),
    ("仓库根冒出白名单外的 md", ROOT / "_tmp_t12_根.md"),
    ("日志没进 journal/", ROOT / ".codebuddy" / "memory" / "2026-01-01.md"),
]


def run_doc_audit() -> str:
    # ⚠️ 2026-09-23：审计件早已从 `tools/` 搬进 `tools/audit/` —— 旧路径下 subprocess 直接失败、
    #    `stdout` 为空 ⇒ 三处"造出来的违规"一条都看不见 ⇒ **假绿**（实测：`0/3 变红 ＋ 复原干净 ✅`）。
    # ⚠️⚠️ 2026-10-01（`TAIL-204` 第 7 步）**第二个同款坑**：**漏了 `-X utf8`** —— 子进程按本机默认
    #    编码（GBK）写 stdout，而本件按 `encoding="utf-8"` 解 ⇒ **中文全成乱码** ⇒ 拿文件名去比
    #    **永远比不上** ⇒ 三处违规一条都认不出 ⇒ **又一次 `0/3 变红 ＋ 复原干净 ✅` 假绿**
    #    （判据本身是好的：手工造同样三处，`doc_audit -v` 当场报 3 条 `[T12]`）。
    #    ⭐ 同族：`_mut_t20.py` 的 `report()` 里**写着**这条规矩 —— 本件当初没抄到。
    r = subprocess.run([PY, "-X", "utf8", "tools/audit/doc_audit.py", "-v"], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout or ""


def t12_lines(out: str) -> list[str]:
    return [l.strip() for l in out.splitlines() if "[T12]" in l]


ok = 0
for name, path in CASES:
    path.write_text("# 临时件（T12 反向灵敏度用）\n", encoding="utf-8")
    try:
        hits = t12_lines(run_doc_audit())
        hit = [h for h in hits if path.name in h]
        print(f"{'✅' if hit else '❌'} {name} → {hit[0] if hit else '（T12 没报！）'}")
        ok += 1 if hit else 0
    finally:
        path.unlink(missing_ok=True)

# 复原后必须回到 0 —— 证明"刚才那些报告是它造的、不是本来就有的"
after = run_doc_audit()
left = t12_lines(after)
print(f"\n复原后 T12 命中：{len(left)} 条 {'✅（干净）' if not left else '❌ ' + str(left)}")
print("复原后：", next((l for l in after.splitlines() if "必须修" in l), "").strip())
print(f"\n反向灵敏度：{ok}/{len(CASES)} 变红" + (" ＋ 复原干净 ✅" if not left else " ⚠️ 复原不干净"))
raise SystemExit(0 if ok == len(CASES) and not left else 1)
