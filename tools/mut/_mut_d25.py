#!/usr/bin/env python
"""`D25` 四条裁定的**反向灵敏度**：把每条的实现改坏一处 ⇒ 对应断言必须变红 ⇒ 逐字节复原（MD5 校验）。

⭐ 为什么留成脚本：这四条是**用户口径**（负数照收 / 非数据行跳过 / 标段行认月）—— 日后若有人
"顺手"把它们改回去（例如把负数检查塞回来），本脚本能立刻证明**判据确实护住了**。

⛔ 纪律：只临时替换源文件，跑完立刻回写原文并核对 MD5（源文件逐字节复原）。
"""
from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import hashlib
import os
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/app/mod06_proc/importer.py"
PY = ROOT / "backend/.venv/Scripts/python.exe"
T = "tests/test_proc_import_realfile.py"

orig = SRC.read_text(encoding="utf-8")
md5_0 = hashlib.md5(orig.encode("utf-8")).hexdigest()

MUTS = [
    ("M1 负数检查复原（① 收到改回「报错」）",
     '        return to_money(text.replace(",", "").replace("，", ""))\n    except',
     '        value = to_money(text.replace(",", "").replace("，", ""))\n'
     '        if value < 0:\n            raise MustReportError("负数不收")\n'
     '        return value\n    except',
     f"{T}::test_负数照收_导入层不改用户的定稿数字"),
    ("M2 空行/说明行判定拆掉（③④ 跳过失效）",
     '    if _is_total_row(row):\n        return "合计/小计行"\n    if _has_amounts(row, index):\n        return ""',
     '    if _is_total_row(row):\n        return "合计/小计行"\n    return ""\n'
     '    if _has_amounts(row, index):\n        return ""',
     f"{T}::test_非数据行一律跳过并提示_不当异常报"),
    ("M3 放宽年月匹配关掉（② 标段行认不出）",
     'r"^(\\d{4})\\s*年\\s*(\\d{1,2})\\s*月"',
     'r"^ZZZ_NOMATCH_\\d{4}年\\d{1,2}月"',
     f"{T}::test_标段行_中文年月带后缀照认_值不换算"),
]

ok = True
for name, old, new, target in MUTS:
    if old not in orig:
        print(f"⛔ 锚点找不到，跳过：{name}")
        ok = False
        continue
    SRC.write_text(orig.replace(old, new, 1), encoding="utf-8", newline="")
    env = dict(os.environ)
    # ⛔ 必须指到**变异用**结果文件 —— 否则会把正式 `var/state/verification/acc_results.json` 覆盖成
    #    局部跑的结果 ⇒ `doc_audit` 的 T4（文档数字 vs 实测）立刻对不上（踩过：一次 3 条红）
    got = subprocess.run([str(PY), "-m", "pytest", target, "-q", "-p", "no:cacheprovider",
                          "--tb=no", "-x"], cwd=ROOT / "backend", capture_output=True, env=env)
    red = got.returncode != 0
    print(f"{'✅' if red else '⛔'} {name} ⇒ 断言{'变红（有区分力）' if red else '**仍然绿**（判据没护住！）'}")
    ok = ok and red

SRC.write_text(orig, encoding="utf-8", newline="")
md5_1 = hashlib.md5(SRC.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
print(f"\n复原校验：MD5 {'一致 ✅' if md5_0 == md5_1 else '⛔ 不一致！'}（{md5_0[:12]}…）")
print("结论：" + ("三条都变红 ⇒ 新判据有区分力" if ok else "⚠️ 有判据没护住，得补"))
sys.exit(0 if ok and md5_0 == md5_1 else 1)
