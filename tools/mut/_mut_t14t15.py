#!/usr/bin/env python
"""`T14`/`T15` 反向灵敏度 —— 证明两条新尺子**真的有牙**。

变异（都在**新增临时件**上做，跑完清干净；⛔ 不改任何源文件）：
  ① 往 `work/00-scratch/` 放一个**改 mtime 为 20 天前**的文件 ⇒ `T14` 必须命中；
  ② 往 `artifacts/` 放一个过程类 md ⇒ `T15` 必须命中；
  ③ 往 `tools/` 根放一个 .py ⇒ `T14` 必须命中。
基线（无临时件）必须 0 命中。
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import time

# ⛔ **结果隔离**（本仓纪律）：非全套 pytest 必须把四态结果写到**临时文件** ——
#    否则每处变异都会把权威 `artifacts/acc_results.json` 冲成单条 ⇒ `doc_audit` 的 T4 立刻报红。
os.environ.setdefault("ACC_RESULTS_PATH", "../artifacts/_mut_acc_results.json")

sys.stdout.reconfigure(encoding="utf-8")
R = pathlib.Path(r"D:\dev\mtrl-workbench")
SCRATCH = R / ".codebuddy" / "work" / "00-scratch" / "_t14_probe_tmp.txt"
ART = R / "artifacts" / "_t15_probe_tmp.md"
TOOLS = R / "tools" / "_t14_probe_tmp.py"


def hits() -> int:
    r = subprocess.run(
        [str(R / "backend" / ".venv" / "Scripts" / "python.exe"), "-c",
         "import sys; sys.path.insert(0, r'tools/audit');"
         "from audit_work import check_scratch_ttl as a, check_artifacts_and_headers as b;"
         "h = a() + b();"
         "print('命中', len(h));"
         "[print('  -', x['code'], x['rel'], x['what'][:40]) for x in h]"],
        cwd=R, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "").strip() or (r.stderr or "")[-200:])
    for l in (r.stdout or "").splitlines():
        if l.startswith("命中"):
            return int(l.split()[1])
    return -1


fail = []
print("基线…")
if hits() != 0:
    fail.append("基线有命中（误报）")

print("变异①：scratch 里放 20 天前的文件…")
SCRATCH.write_text("tmp", encoding="utf-8")
old = time.time() - 20 * 86400
os.utime(SCRATCH, (old, old))
if hits() < 1:
    fail.append("① 超期 scratch 未被抓到")
SCRATCH.unlink(missing_ok=True)

print("变异②：artifacts 里放过程类 md…")
ART.write_text("# 假的过程类 md\n", encoding="utf-8")
if hits() < 1:
    fail.append("② artifacts 过程 md 未被抓到")
ART.unlink(missing_ok=True)

print("变异③：tools 根放散件 .py…")
TOOLS.write_text("# 假的散件\n", encoding="utf-8")
if hits() < 1:
    fail.append("③ tools 根散件未被抓到")
TOOLS.unlink(missing_ok=True)

print("复检基线…")
if hits() != 0:
    fail.append("清场不完（基线仍有命中）")

print("❌ " + "；".join(fail) if fail else "✅ 有区分力：三处变异都命中、基线干净、临时件已清")
sys.exit(1 if fail else 0)
