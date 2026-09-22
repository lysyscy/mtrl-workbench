# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `TAIL-35`（`m04` 导入 ＋ 手动行）接线断言**是否真有区分力**。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_tail35.py`

纪律同 `_mut_m7w.py`：bytes 级 · 行尾归一 · 变异点唯一命中 · 跑完重跑全套 `pytest` · MD5 复核。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH, pick  # noqa: E402  ← `P4`① 读取点收敛

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
FILES = {
    "shell": SHELL_PATH,
    "m04api": ROOT / "backend" / "app" / "mod04_plan" / "plan_api_router.py",
}

#: (说明, 目标文件, 原文片段, 改坏成, 应当变红的测试名)
MUTATIONS: list[tuple[str, str, str, str, str]] = [
    ("手动行不再走后端",
     "shell", "m04PlanSave: body => API.post('/api/m04/plans', body)",
     "m04PlanSave: body => null",
     "test_导入与手动行走后端"),
    ("导入客户端不再是 multipart",
     "shell", "new FormData()", "{}",
     "test_导入与手动行走后端"),
    ("plImportOk 退回同步（假导入）",
     "shell", "plImportOk:async ()=>{", "plImportOk:()=>{",
     "test_导入与手动行走后端"),
    ("失败时把草稿清空（§4.3.3.1 要求保留已填内容）",
     "shell", "}catch(e){\n     await reloadPlans();          /* 回后端真实状态",
     "}catch(e){\n     plD={};\n     await reloadPlans();          /* 回后端真实状态",
     "test_手动行失败时保留已填内容"),
    ("手动行保存回到前端复写金额校验（第二份口径）",
     "shell", "const r=await API.m04PlanSave({", "const r=await badMoney({",
     "test_手动行判据不得在前端复写"),
    ("手动行本地动作没恢复原型（plRowAdd 仍是提示）",
     "shell", "plRowEditId=PL_NEW_ID; plD=plBlank(); render();",
     "plRowEditId=''; render();",
     "test_手动行三个本地动作已恢复原型"),
    ("后端手动行端点不走 manual_row_payload（另写一套）",
     "m04api",
     "payload = manual_row_payload(",
     "payload = _manual_row_payload(",
     "test_后端两个新端点存在"),
    ("后端导入端点不走 merge_month（丢幂等）",
     "m04api",
     "result = repo.merge_month(session, year_month=year_month, rows=rows)",
     "result = {'created': len(rows)}",
     "test_后端两个新端点存在"),
]


def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


def main() -> int:
    orig = {k: p.read_bytes() for k, p in FILES.items()}
    md5_before = {k: hashlib.md5(v).hexdigest() for k, v in orig.items()}
    for k, v in orig.items():
        print(f"{k}: {len(v)} 字节 · MD5 {md5_before[k][:12]}")

    hit = miss = 0
    for i, (label, fkey, old, new, test_name) in enumerate(MUTATIONS, 1):
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳是多件 ⇒ 锚点在哪件就改哪件（⛔ 仍逐字节复原）。
        #    ⚠️ 判断基准一律用**原始** `SHELL_PATH`：`FILES["shell"]` 已被上一条改成别的件，
        #    拿它当基准会**累积失效**（实测：第 6 条起全 SKIP）。
        if fkey == "shell":
            FILES["shell"] = pick(SHELL_PATH, old, new)
            orig["shell"] = FILES["shell"].read_bytes()
            md5_before["shell"] = hashlib.md5(FILES["shell"].read_bytes()).hexdigest()
        target = orig[fkey]
        o, n = _fit(old.encode("utf-8"), target), _fit(new.encode("utf-8"), target)
        cnt = target.count(o)
        if cnt != 1:
            print(f"  {i:2d}. ⚠️ SKIP（命中 {cnt} 次）—— [{fkey}] {label}")
            miss += 1
            continue
        FILES[fkey].write_bytes(target.replace(o, n))
        r = subprocess.run([str(PY), "-m", "pytest", "-q", "-k", test_name, "tests/"],
                           cwd=ROOT / "backend", capture_output=True, text=True)
        bad = r.returncode != 0
        print(f"  {i:2d}. {'✅ 变红' if bad else '⛔ 仍绿（假绿！）'} —— [{fkey}] {label}  [{test_name}]")
        if bad:
            hit += 1
        FILES[fkey].write_bytes(target)

    md5_after = {k: hashlib.md5(p.read_bytes()).hexdigest() for k, p in FILES.items()}
    ok = all(md5_after[k] == md5_before[k] for k in FILES)
    print(f"\n命中 {hit}/{len(MUTATIONS) - miss} · SKIP {miss} · MD5 {'逐字节复原 ✅' if ok else '⛔ 不一致'}")

    print("重跑全套 pytest（复原态）…")
    full = subprocess.run([str(PY), "-m", "pytest", "-q", "tests/"],
                          cwd=ROOT / "backend", capture_output=True, text=True)
    print("  全套 pytest 退出码 =", full.returncode)
    return 0 if (ok and miss == 0 and hit == len(MUTATIONS) and full.returncode == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
