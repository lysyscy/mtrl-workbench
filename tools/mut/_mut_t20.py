#!/usr/bin/env python
"""`T20` 反向灵敏度 —— 证明「保留期与容量」这条新判据**真的有牙**。

守什么（`audit_work.check_retention`）：`README.md` 写着 `.workbuddy/backups/`「留 5 份 · 月度清」，
而 2026-09-22 整改设计给的验收判据就是「目录计数 ≤5（可数）」—— 却**从没被机器守过**
⇒ 43 个条目静默堆着（含 09-18 的旧快照）。本条给那口径装上机器眼。

变异（都在**新增临时件**上做，跑完清干净；⛔ 不删任何既有备份）：
  ① 往 `.workbuddy/backups/` 放一个假快照目录 ⇒ `T20` 命中数**必须上升**（超上限）；
  ② 往 `.workbuddy/scratch/` 放一个 51 MB 稀疏文件（`truncate` 秒建，占 0 盘）⇒ 命中数**必须上升**。

⚠️ 判法用**增量**（`Δ命中 ≥ 1`），⛔ 不要求"基线 = 0" —— 因为本仓库**当前**可能本来就有欠账
（那正是立这条判据的原因），基线为零不是判据的前提。
⚠️ 用的是 `check_retention()` 的**真逻辑**（⛔ 不另写一套判定）。
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

# ⛔ **结果隔离**（本仓纪律）：非全套 pytest 必须把四态结果写到**临时文件**
os.environ.setdefault("ACC_RESULTS_PATH", "../artifacts/_mut_acc_results.json")

sys.stdout.reconfigure(encoding="utf-8")
R = pathlib.Path(r"D:\dev\mtrl-workbench")
FAKE_SNAP = R / ".workbuddy" / "backups" / "_t20_probe_tmp" / "x.md"
BIG = R / ".workbuddy" / "scratch" / "_t20_probe_tmp.bin"


def hits() -> int:
    r = subprocess.run(
        # ⚠️ **必须 `-X utf8`**：检查输出里带 `⛔` 这类字符，PS 5.1 的 GBK 控制台编码会当场 `UnicodeEncodeError`
        #   ⇒ 子进程 rc≠0、判据读不到（实测踩过：本仓「跑审计件的正确起手」那一条）
        [str(R / "backend" / ".venv" / "Scripts" / "python.exe"), "-X", "utf8", "-c",
         "import sys; sys.path.insert(0, r'tools/audit');"
         "from audit_work import check_retention as c;"
         "h = c();"
         "print('命中', len(h));"
         "[print('  -', x['code'], x['rel'], x['what'][:52]) for x in h]"],
        cwd=R, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "").strip() or (r.stderr or "")[-200:])
    for line in (r.stdout or "").splitlines():
        if line.startswith("命中"):
            return int(line.split()[1])
    return -1


fail = []
print("基线…")
base = hits()
if base < 0:
    fail.append("基线读不出（检查脚本本身跑不起来）")

print("变异①：`backups/` 里放一个假快照目录 ⇒ 应超上限…")
FAKE_SNAP.parent.mkdir(parents=True, exist_ok=True)
FAKE_SNAP.write_text("tmp", encoding="utf-8")
n1 = hits()
if not (n1 > base):
    fail.append(f"① backups 超限未被抓到（基线 {base} → 变异 {n1}）")
FAKE_SNAP.unlink(missing_ok=True)
FAKE_SNAP.parent.rmdir()

print("变异②：`scratch/` 里放一个 51 MB 稀疏文件 ⇒ 应超规模线…")
with BIG.open("wb") as f:
    f.truncate(51 * 1024 * 1024)
n2 = hits()
if not (n2 > base):
    fail.append(f"② scratch 规模超线未被抓到（基线 {base} → 变异 {n2}）")
BIG.unlink(missing_ok=True)

print("复检…")
if hits() != base:
    fail.append("清场不完（复检命中数与基线不一致）")

print("❌ " + "；".join(fail) if fail else f"✅ 有区分力：两处变异都命中（基线 {base} → ① {n1} / ② {n2}）、临时件已清")
sys.exit(1 if fail else 0)
