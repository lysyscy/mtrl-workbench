#!/usr/bin/env python
"""`T14`/`T15` 反向灵敏度 —— 证明两条新尺子**真的有牙**。

变异（都在**新增临时件**上做，跑完清干净；⛔ 不改任何源文件）：
  ① 往 `work/00-scratch/` 放一个**改 mtime 为 20 天前**的文件 ⇒ `T14` 必须命中；
  ② 往 `artifacts/` 放一个过程类 md ⇒ `T15` 必须命中；
  ③ 往 `tools/` 根放一个 .py ⇒ `T14` 必须命中。
基线：⚠️ **只作对照**，⛔ 不要求为 0（2026-10-01 订正）—— 现实里基线**有**既存的 T15 黄（work 区几件文档
文头不全），钉"绝对 0"会让本件**永远红**。判法 = **比相对增量**：每处变异之后命中数必须 > 基线，且清场后回到基线。
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
    # ⚠️⚠️ 2026-10-01（`TAIL-204` 第 7 步）**第三个同款坑**：漏了 `-X utf8` —— 子进程按本机默认编码
    #    （GBK）写 stdout，而本件按 utf-8 解 ⇒ 那行 `命中 N` 成了乱码 ⇒ `startswith("命中")` 永远不成立
    #    ⇒ 本函数返回 **-1** ⇒ 三处变异**一处都没验到**（症状 = "基线有命中（误报）＋ 三条都未被抓到"）。
    #    ⭐ 同族：`_mut_t12.py` 一模一样的病（同日一起修）；根因都是**同一句规矩没抄到**：
    #    「跑审计件的子进程必须带 `-X utf8`」。
    r = subprocess.run(
        [str(R / "backend" / ".venv" / "Scripts" / "python.exe"), "-X", "utf8", "-c",
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
#: ⚠️⭐ 2026-10-01（第 7 步）**改成相对比较**：原来要求"基线必须 0 命中" —— 而基线**本来就有 5 条 `T15` 黄**
#:   （`work/10-designs` 4 件 ＋ `work/40-decisions` 1 件的**文头缺元信息**，属既有欠账、黄档不挡合入）。
#:   ⇒ 钉"绝对 0"会让本件**永远红**（那不是判据有问题，是**靶的假设过期**了 —— 同 `_mut_t20` 那次的订正）。
base_n = hits()
if base_n < 0:
    fail.append("基线读数失败（子进程没吐出「命中 N」）")
print(f"   （基线命中 {base_n} —— ⚠️ 非 0 是**既有的那 5 条 T15 黄**，见本件上方注释；故比**相对增量**）")

print("变异①：scratch 里放 20 天前的文件…")
SCRATCH.write_text("tmp", encoding="utf-8")
old = time.time() - 20 * 86400
os.utime(SCRATCH, (old, old))
if hits() <= base_n:
    fail.append("① 超期 scratch 未被抓到")
SCRATCH.unlink(missing_ok=True)

print("变异②：artifacts 里放过程类 md…")
ART.write_text("# 假的过程类 md\n", encoding="utf-8")
if hits() <= base_n:
    fail.append("② artifacts 过程 md 未被抓到")
ART.unlink(missing_ok=True)

print("变异③：tools 根放散件 .py…")
TOOLS.write_text("# 假的散件\n", encoding="utf-8")
if hits() <= base_n:
    fail.append("③ tools 根散件未被抓到")
TOOLS.unlink(missing_ok=True)

print("复检基线…")
if hits() != base_n:
    fail.append("清场不完（基线命中数没回到原值）")

print("❌ " + "；".join(fail) if fail else
      f"✅ 有区分力：三处变异都让命中数超过基线（{base_n} → 更多）、清场后回到 {base_n}、临时件已清"
      "（⚠️ 基线 {base_n} 非 0 = 既有的 T15 黄，不是本件造的）".replace("{base_n}", str(base_n)))
sys.exit(1 if fail else 0)
