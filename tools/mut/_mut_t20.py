#!/usr/bin/env python
"""`T20` 反向灵敏度 —— 证明「保留期与容量」这条判据**真的有牙**。

守什么（`audit_work.check_retention`）：
- `README.md` 写着 `.codebuddy/backups/`「留 5 份 · 月度清」，而 2026-09-22 整改设计给的验收判据
  就是「目录计数 ≤5（可数）」—— 却**从没被机器守过** ⇒ 43 个条目静默堆着（含 09-18 的旧快照）。
- 2026-09-29（`TAIL-194`）再加两处：`.workbuddy/scratch/` 活区规模、**`tools/oneoff/` 件数 / 容量**。

变异（都在**新增临时件**上做，跑完清干净；⛔ 不删任何既有备份）：
  ① 往 `.codebuddy/backups/` 放**两个**假快照目录 ⇒ 该处的**条目数**必须**变大**（或从"无命中"变"有命中"）；
  ② 往 `.workbuddy/scratch/` 放一个 51 MB 稀疏文件（`truncate` 秒建，占 0 盘）⇒ 同上；
  ③ 往 `tools/oneoff/` 放一个 6 MB 稀疏文件（> 容量线 5 MB）⇒ 同上。

⭐⭐ **判法（2026-09-29 订正 —— 这里踩过一次）**：原来只比「**命中条数**是否上升」，而这在该项
**基线本就超线**时**必然失效** —— 那三处超线都只报**一行**，`7 → 8` 个条目仍是 **1 行** ⇒
变异"没抓到"是**假红**（实测：当时 `backups/` 顶层 7 > 5，①靶当场报红）。
⇒ 现改成：**按 `rel` 取出该处报告里的第一个数字**（条目数 / 件数），比**这个数字**是否变大
（`无命中 → 有命中` 也算变大）。⚠️ 用的仍是 `check_retention()` 的**真逻辑**（⛔ 不另写一套判定），
只是**读它报出来的数**。
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
R = pathlib.Path(r"D:\dev\mtrl-workbench")
FAKE_SNAP = R / ".codebuddy" / "backups" / "_t20_probe_tmp" / "x.md"
FAKE_SNAP2 = R / ".codebuddy" / "backups" / "_t20_probe_tmp2" / "x.md"
BIG = R / ".workbuddy" / "scratch" / "_t20_probe_tmp.bin"
BIG3 = R / "tools" / "oneoff" / "_t20_probe_tmp.bin"


def report() -> str:
    """跑 `check_retention()`（子进程 · 走真逻辑）⇒ 它的完整输出文本。

    ⚠️ 必须带 `-X utf8`：否则 Windows 控制台编码会把中文输出搞崩 ⇒ 子进程 rc≠0、判据读不到
       （本仓「跑审计件的正确起手」那一条）。
    """
    r = subprocess.run(
        [str(R / "backend" / ".venv" / "Scripts" / "python.exe"), "-X", "utf8", "-c",
         "import sys; sys.path.insert(0, r'tools/audit');"
         "from audit_work import check_retention as c;"
         "h = c();"
         "print('命中', len(h));"
         "[print('  -', x['code'], x['rel'], x['what'][:60]) for x in h]"],
        cwd=R, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    if "命中" not in out:
        print(out[-400:])
    return out


def n_for(text: str, rel: str) -> int | None:
    """从报告里取 `rel` 那一行命中的**第一个数字**（条目数 / 件数）；无命中 ⇒ `None`。"""
    for line in text.splitlines():
        if line.strip().startswith("-") and rel in line:
            m = re.search(r"(\d+)", line.split(rel, 1)[1])
            if m:
                return int(m.group(1))
    return None


def grew(before: str, after: str, rel: str) -> bool:
    a, b = n_for(before, rel), n_for(after, rel)
    if b is None:
        return False
    return a is None or b > a


fail: list[str] = []
print("基线…")
base = report()
print(base)

print("变异①：`backups/` 里放**两个**假快照目录 ⇒ 该处条目数应变大…")
FAKE_SNAP.parent.mkdir(parents=True, exist_ok=True)
FAKE_SNAP.write_text("tmp", encoding="utf-8")
FAKE_SNAP2.parent.mkdir(parents=True, exist_ok=True)
FAKE_SNAP2.write_text("tmp", encoding="utf-8")
r1 = report()
if not grew(base, r1, ".codebuddy/backups/"):
    fail.append(f"① backups 条目数没变大（{n_for(base, '.codebuddy/backups/')} → {n_for(r1, '.codebuddy/backups/')}）")
FAKE_SNAP.unlink(missing_ok=True)
FAKE_SNAP.parent.rmdir()
FAKE_SNAP2.unlink(missing_ok=True)
FAKE_SNAP2.parent.rmdir()

print("变异②：`scratch/` 里放一个 51 MB 稀疏文件 ⇒ 该处规模应变大…")
with BIG.open("wb") as f:
    f.truncate(51 * 1024 * 1024)
r2 = report()
if not grew(base, r2, ".workbuddy/scratch/"):
    fail.append(f"② scratch 规模没变大（{n_for(base, '.workbuddy/scratch/')} → {n_for(r2, '.workbuddy/scratch/')}）")
BIG.unlink(missing_ok=True)

print("变异③：`tools/oneoff/` 里放一个 6 MB 稀疏文件 ⇒ 该处规模应变大…")
with BIG3.open("wb") as f:
    f.truncate(6 * 1024 * 1024)
r3 = report()
if not grew(base, r3, "tools/oneoff/"):
    fail.append(f"③ oneoff 规模没变大（{n_for(base, 'tools/oneoff/')} → {n_for(r3, 'tools/oneoff/')}）")
BIG3.unlink(missing_ok=True)

print("复检…")
if n_for(report(), ".codebuddy/backups/") != n_for(base, ".codebuddy/backups/") or \
        n_for(report(), "tools/oneoff/") != n_for(base, "tools/oneoff/"):
    fail.append("清场不完（复检数与基线不一致）")

print("❌ " + "；".join(fail) if fail else
      "✅ 有区分力：三处变异都让报告里的数变大（backups "
      f"{n_for(base, '.codebuddy/backups/')}→{n_for(r1, '.codebuddy/backups/')} · scratch "
      f"{n_for(base, '.workbuddy/scratch/')}→{n_for(r2, '.workbuddy/scratch/')} · oneoff "
      f"{n_for(base, 'tools/oneoff/')}→{n_for(r3, 'tools/oneoff/')}）、临时件已清")
sys.exit(1 if fail else 0)
