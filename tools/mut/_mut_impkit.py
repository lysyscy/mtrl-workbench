#!/usr/bin/env python
"""`TAIL-69` 反向灵敏度 —— 证明「**预览不写库**」判据真的有牙。

变异：往**通用面**的 `POST /api/imp/{域}/preview` 里塞一次 `hooks.commit(...)`
（= 预览阶段就落库）⇒ `test_imp_m06_api.py::test_通用面预览阶段不写库_且坏token显式报错` 必须红；
跑完**逐字节复原**。
⛔ 不变异 `commit` 端点（它本来就该写库 —— 变异错了对象只会得到假绿）。

⚠️ 2026-09-23（`TAIL-75` 余项 · 用户裁定「只留通用面」）：本件原先的靶是 **`m04` 页内端点**
   （`mod04_plan/plan_api_router.py` 的 `parse`），那两条端点已**连件删除** ⇒ 靶改到**通用面**上
   （`import_kit/api.py` 的 `api_preview`）—— 判据搬了落点，本件跟着搬（**claim 一字未改**）。
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import pathlib
import subprocess
import sys
import os

# ⛔ **结果隔离**（本仓纪律）：非全套 pytest 必须把四态结果写到**临时文件** ——
#    否则每处变异都会把权威 `var/state/verification/acc_results.json` 冲成单条 ⇒ `doc_audit` 的 T4 立刻报红。
os.environ.setdefault("ACC_RESULTS_PATH", str(_run_output('_mut_acc_results.json')))

sys.stdout.reconfigure(encoding="utf-8")
REPO = pathlib.Path(r"D:\dev\mtrl-workbench")
TARGET = REPO / "backend" / "app" / "import_kit" / "api.py"
CASE = "tests/test_imp_m06_api.py::test_通用面预览阶段不写库_且坏token显式报错"
orig = TARGET.read_bytes()

# ⭐ 变异锚 = 预览端点收尾那两行之前（在此塞一次真正的落库 ⇒ 预览阶段真的写了一笔）
ANCHOR = (b'                    out["blocks"] = list(extra["blocks"])\n'
          b'            return out')
MUTANT = (b'                    out["blocks"] = list(extra["blocks"])\n'
          b'            with session_scope() as _s:\n'
          b'                hooks.commit(_s, records, mapping_, current_operator(),\n'
          b'                             dict((body or {}).get("options") or {}))\n'
          b'            return out')


def _hit(a: bytes, b: bytes) -> bool:
    """行尾两种写法都能命中（本仓源码行尾不统一）。"""
    return a in b or a.replace(b"\n", b"\r\n") in b


def _apply(a: bytes, b: bytes, src: bytes) -> bytes:
    if a in src:
        return src.replace(a, b, 1)
    return src.replace(a.replace(b"\n", b"\r\n"), b.replace(b"\n", b"\r\n"), 1)


fail = []


def run_case() -> int:
    r = subprocess.run(
        [str(REPO / "backend" / ".venv" / "Scripts" / "python.exe"), "-m", "pytest", "-q",
         CASE, "-p", "no:cacheprovider", "--tb=no"],
        cwd=REPO / "backend", capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    tail = [x for x in out.splitlines() if x.strip()][-1] if out.strip() else "?"
    print("   ", tail[:110])
    return r.returncode


if not _hit(ANCHOR, orig):
    fail.append("锚文没找到 —— 通用面 `api_preview` 的收尾形态变了？先看再改")
else:
    print("基线（未变异）…")
    if run_case() != 0:
        fail.append("基线就红（判据本身坏了）")

    print("变异：预览端点塞入 hooks.commit（预览阶段落库）…")
    TARGET.write_bytes(_apply(ANCHOR, MUTANT, orig))
    if run_case() == 0:
        fail.append("变异未被抓住 —— 「预览不写库」判据是假的")
    TARGET.write_bytes(orig)

import hashlib  # noqa: E402  （收尾核 MD5 用；放这里是为了上面逻辑一眼看完）

if hashlib.md5(TARGET.read_bytes()).hexdigest() != hashlib.md5(orig).hexdigest():
    fail.append("复原不一致")

print(f"❌ {'；'.join(fail)}" if fail else "✅ 有区分力：变异红、基线绿、逐字节复原")
sys.exit(1 if fail else 0)
