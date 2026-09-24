#!/usr/bin/env python
"""反向灵敏度（`TAIL-78`）：证明「**导入/回滚 ⇒ 取数缓存全标脏**」这条判据真有牙。

变异：把 `ACT.impCommit` 的 `LOADED.clear()` 换回**部分标脏**（旧写法：只删「机械 6 列」）
⇒ `test_导入回滚后把取数缓存全标脏` 必须红；跑完**逐字节复原**。

⚠️ 与 `_mut_impkit.py` 同款：① 结果隔离（子集 pytest 不许冲权威 `acc_results.json`）；
② 锚点**在哪一件就改哪件**（壳是多件）。
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

# ⛔ **结果隔离**（本仓纪律）：非全套 pytest 必须把四态结果写到**临时文件**。
os.environ.setdefault("ACC_RESULTS_PATH", "../artifacts/_mut_acc_results.json")

sys.stdout.reconfigure(encoding="utf-8")            # noqa: E402
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "audit"))
from shell_source import SHELL_PATH, resolve  # noqa: E402

PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
CASE = "tests/test_imp_shell.py::test_导入回滚后把取数缓存全标脏"

ANCHOR = b"  LOADED.clear();\n  render();"
MUTANT = b"  LOADED.delete('\xe6\x9c\xba\xe6\xa2\xb0 6 \xe5\x88\x97');\n  render();"   # 机械 6 列
TARGET = resolve("ACT.impCommit =")
orig = TARGET.read_bytes()

fails: list[str] = []


def run_case() -> int:
    r = subprocess.run([str(PY), "-m", "pytest", "-q", CASE, "-p", "no:cacheprovider", "--tb=no"],
                       cwd=ROOT / "backend", capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = [x for x in ((r.stdout or "") + (r.stderr or "")).splitlines() if x.strip()]
    print("   ", (tail[-1][:110] if tail else "?"))
    return r.returncode


if ANCHOR not in orig:
    fails.append("锚文没找到（`ACT.impCommit` 的收尾形态变了？先看再改）")
else:
    print("基线（未变异）…")
    if run_case() != 0:
        fails.append("基线就红（判据本身坏了）")

    print("变异：`ACT.impCommit` 退回部分标脏…")
    TARGET.write_bytes(orig.replace(ANCHOR, MUTANT, 1))
    if run_case() == 0:
        fails.append("变异未被抓住 —— 「导入后全标脏」判据是假的")
    TARGET.write_bytes(orig)

if hashlib.md5(TARGET.read_bytes()).hexdigest() != hashlib.md5(orig).hexdigest():
    fails.append("复原不一致")

print(f"❌ {'；'.join(fails)}" if fails else f"✅ 有区分力：变异红、基线绿、逐字节复原（{TARGET.name}）")
sys.exit(1 if fails else 0)
