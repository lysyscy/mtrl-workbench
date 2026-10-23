# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— 「**剔除行可勾选**」＋「**超付挂提醒**」这两处的断言**是否真有区分力**。

做法：把实现**故意改坏**若干处，确认**对应断言确实变红**；每次立刻按 bytes 复原，最后核对 MD5。
用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_excl_overpay.py`

⚠️ 为什么另起一件、⛔ 不并进 `_mut_m03pay.py`：那件的 runner 跑的是 `{TEST}::{case}`（**固定文件**）
   ⇒ 把目标指向别文件的用例时，pytest 会因"找不到该测试"而非零退出，被误判成「✅ 变红」。
   本件照 `_mut_tail04_pages.py` 走 `-k`（**全 `tests/` 里按名字找**），跨文件才靠得住。
⚠️ 本仓纪律（memory §十七）：bytes 写入 / 中文片段用 `str+.encode()` / 行尾按目标文件归一 /
   变异点必须唯一命中 / 跑完必须再跑一次全套 `pytest`。
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
APP = BE / "app"
PY = BE / ".venv" / "Scripts" / "python.exe"

FILES = {
    "index": APP / "web" / "index.html",
    "core": APP / "web" / "shell" / "core.js",
    "actions": APP / "web" / "shell" / "actions.js",
    "live": APP / "mod03_notice" / "list_view.py",
    "api": APP / "mod03_notice" / "notice_api_router.py",
}

T_RESTORE = "test_恢复剔除必须先勾选"
T_BATCH = "test_壳里撤单行与剔除行不得进入付款"
T_OVER = "test_实付超过审批金额照实写入不封顶"

# (说明, 件, 原文（LF）, 改成（LF）, 应变红的用例名)
MUTS: list[tuple[str, str, str, str, str]] = [
    # ---- 剔除行可勾选（用户 2026-09-21 报障的那条死锁）
    ("可勾选出口漏掉剔除行（回到死锁：勾不上 ⇒ 恢复无路可走）",
     "index", "const ntSelectable=n=>ntPayCand(n)||!!n.excl;",
     "const ntSelectable=n=>ntPayCand(n);", T_RESTORE),
    ("勾选框又钉回 `ntPayCand`（剔除行不可勾）",
     "index", "${ntSelectable(n)?'':'disabled'}",
     "${ntPayCand(n)?'':'disabled'}", T_RESTORE),
    ("全选与勾选框走了两个出口（全选框永久卡半选态）",
     "index", "  const vis=ntHit(fNt).filter(ntSelectable).map(n=>n.id), hit=vis.filter(i=>pickSet.has(i)).length;",
     "  const vis=ntHit(fNt).filter(ntPayCand).map(n=>n.id), hit=vis.filter(i=>pickSet.has(i)).length;",
     T_RESTORE),
    ("`pickAll` 与勾选框走了两个出口（全选漏掉剔除行）",
     "actions", "pickAll:t=>{ const ids=ntHit(fNt).filter(ntSelectable).map(n=>n.id);",
     "pickAll:t=>{ const ids=ntHit(fNt).filter(ntPayCand).map(n=>n.id);", T_RESTORE),

    # ---- 付款批次仍然不收（判据 001-04 的**本体**：放宽了必须变红）
    ("付款准入出口被放宽（撤单行不再排除）",
     "index", "const ntPayCand=n=>ntLive(n)&&!ntVoid(n);",
     "const ntPayCand=n=>ntLive(n);", T_BATCH),
    ("窗口组装不再过滤付款候选（剔除/撤单行会被付掉）",
     "actions", "   const rows=all.filter(ntPayCand), drop=all.filter(n=>!ntPayCand(n));",
     "   const rows=all, drop=[];", T_BATCH),
    ("排除提示改回一律写「i8 已撤单」（对剔除行**撒谎**）",
     "actions", "const whyOf=n=>ntVoid(n)?'i8 已撤单':'已剔除';",
     "const whyOf=n=>'i8 已撤单';", T_BATCH),
    ("提交时的兜底复检被拿掉（状态错位可把作废单送进付款）",
     "actions", ".filter(Boolean).filter(ntPayCand);",
     ".filter(Boolean);", T_BATCH),

    # ---- 超付挂提醒（002-06 的后半句）
    ("超付判定用 `>=`（把「付清」误报成超付）",
     "live", "return to_money(self.amount_paid) > to_money(self.amount_approved)",
     "return to_money(self.amount_paid) >= to_money(self.amount_approved)", T_OVER),
    ("超付标志恒假（界面上永远没有提醒）",
     "live", "return to_money(self.amount_paid) > to_money(self.amount_approved)",
     "return False", T_OVER),
    ("API 不把超付标志交给壳",
     "api", '        "is_overpaid": bool(row.is_overpaid),\n', "", T_OVER),
    ("壳不接后端标志（或自己另算一份）",
     "core", "    over: !!x.is_overpaid,\n", "    over: false,\n", T_OVER),
    ("「超付」标记从通知书行上拿掉",
     "index", '${n.over?` <span class="tag t-dg" title="超付（§4.4.6）',
     '${false?` <span class="tag t-dg" title="超付（§4.4.6）', T_OVER),
]


def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


def run_one(case: str) -> bool:
    """跑**全 `tests/`** 里名字含 `case` 的用例（跨文件才靠得住，理由见模块头）。"""
    env = {**os.environ,

           "PYTHONIOENCODING": "utf-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), "-m", "pytest", "-q", "-k", case, "tests/"],
                       cwd=str(BE), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    # ⚠️ 退出码 5 = **一个用例都没选中**（名字写错 / 被改名）⇒ 那是"没验"，⛔ 不是"变红"
    if r.returncode == 5:
        print(f"     ⚠️ 选中 0 个用例 —— 用例名可能变了：{case}")
        return True
    return r.returncode == 0


def main() -> int:
    orig = {k: p.read_bytes() for k, p in FILES.items()}
    before = {k: hashlib.md5(v).hexdigest() for k, v in orig.items()}
    for k, v in orig.items():
        print(f"{k}: {len(v)} 字节 · MD5 {before[k][:12]}")

    hit = miss = 0
    for i, (desc, fkey, old, new, case) in enumerate(MUTS, 1):
        target = orig[fkey]
        o, nw = _fit(old.encode("utf-8"), target), _fit(new.encode("utf-8"), target)
        cnt = target.count(o)
        if cnt != 1:
            print(f"  {i:2d}. ⚠️ SKIP（变异点命中 {cnt} 次）—— [{fkey}] {desc}")
            miss += 1
            continue
        FILES[fkey].write_bytes(target.replace(o, nw))
        red = not run_one(case)
        FILES[fkey].write_bytes(target)
        print(f"  {i:2d}. {'✅ 变红' if red else '⛔ 仍绿（假绿！）'} —— [{fkey}] {desc}  [{case}]")
        if red:
            hit += 1

    after = {k: hashlib.md5(p.read_bytes()).hexdigest() for k, p in FILES.items()}
    ok_md5 = all(after[k] == before[k] for k in FILES)
    print(f"\n命中 {hit}/{len(MUTS) - miss} · SKIP {miss} · "
          f"MD5 {'逐字节复原 ✅' if ok_md5 else '⛔ 不一致'}")

    print("重跑全套 pytest（复原态）…")
    full = subprocess.run([str(PY), "-m", "pytest", "-q", "tests/"],
                          cwd=str(BE), capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8",
                                                 "PYTHONDONTWRITEBYTECODE": "1"})
    print("  全套 pytest 退出码 =", full.returncode)
    return 0 if (ok_md5 and miss == 0 and hit == len(MUTS) and full.returncode == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
