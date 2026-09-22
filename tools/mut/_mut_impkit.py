#!/usr/bin/env python
"""`TAIL-69` 反向灵敏度 —— 证明「**预览不写库**」判据真的有牙。

变异：往 `parse` 端点里塞一行 `repo.merge_month(...)`（= 预览阶段就写库）
⇒ `test_两步导入_预览不写库_确认才落库` 必须红；跑完逐字节复原。
⛔ 不变异 `confirm`（它本来就该写库 —— 变异错了对象只会得到假绿）。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
REPO = pathlib.Path(r"D:\dev\mtrl-workbench")
TARGET = REPO / "backend" / "app" / "mod04_plan" / "plan_api_router.py"
orig = TARGET.read_bytes()

# ⭐ 变异锚 = parse 端点里 staging.save_preview 那一行之前（预览阶段真的写了一笔）
ANCHOR = b"    token = staging.save_preview(stage_payload(parsed, rows, year_month))"
MUTANT = (b"    with session_scope() as session:\n"
          b"        repo.merge_month(session, year_month=year_month, rows=rows)\n"
          + ANCHOR)
assert ANCHOR in orig, "锚文没找到 —— parse 端点形态变了？先看再改"

fail = []


def run_two_step_test() -> int:
    r = subprocess.run(
        [str(REPO / "backend" / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q",
         "tests/test_plan_import.py::test_两步导入_预览不写库_确认才落库",
         "-p", "no:cacheprovider", "--tb=no"],
        cwd=REPO / "backend", capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    tail = [l for l in out.splitlines() if l.strip()][-1] if out.strip() else "?"
    print("   ", tail[:110])
    return r.returncode


print("基线（未变异）…")
if run_two_step_test() != 0:
    fail.append("基线就红（判据本身坏了）")

print("变异：parse 端点塞入 merge_month（预览阶段写库）…")
TARGET.write_bytes(orig.replace(ANCHOR, MUTANT, 1))
if run_two_step_test() == 0:
    fail.append("变异未被抓住 —— 「预览不写库」判据是假的")

TARGET.write_bytes(orig)
if TARGET.read_bytes() != orig:
    fail.append("复原不一致")

print("❌ " + "；".join(fail) if fail else "✅ 有区分力：变异红、基线绿、逐字节复原")
sys.exit(1 if fail else 0)
