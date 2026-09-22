#!/usr/bin/env python
"""`TAIL-60` / `TAIL-61` 修法的**反向灵敏度** —— 故意改坏 3 处，对应断言必须变红；结束**逐字节复原**。

| 变异 | 改坏什么 | 应红的断言 |
|---|---|---|
| `M1` | `fields.py` 收款账号改回**标准字段**（= 修之前的错法） | `test_收款账号银行取自定义字段_与i8原生打印同款` |
| `M2` | `fields.py` 收款银行改回**标准字段** | 同上 |
| `M3` | `notice_source.py::fetch_detail` 去掉"空结果再确认" | `tests/test_acc_print_acct.py`（3 条） |

用法：`backend\\.venv\\Scripts\\python.exe tools\\_mut_acct.py`（⚠️ 临时改源码，结束复原并校验 MD5）。
⚠️ 跑**非全套** pytest 必须设 `ACC_RESULTS_PATH`（本仓纪律，防冲掉权威 `acc_results.json`）。
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
FIELDS = ROOT / "backend" / "app" / "mod03_notice" / "print" / "fields.py"
SOURCE = ROOT / "backend" / "app" / "mod02_i8" / "notice_source.py"

MUTS = [
    ("M1 收款账号改回标准字段", FIELDS,
     'f"{h}.user_yhzh": str(first.get("user_yhzh") or first.get("RecAccNo") or ""),',
     'f"{h}.user_yhzh": str(first.get("RecAccNo") or ""),'),
    ("M2 收款银行改回标准字段", FIELDS,
     'f"{h}.收款银行1": str(first.get("user_bank_EXName") or first.get("PhidBank_EXName") or ""),',
     'f"{h}.收款银行1": str(first.get("PhidBank_EXName") or ""),'),
    ("M3 fetch_detail 去掉空结果确认", SOURCE,
     "        for attempt in range(EMPTY_RETRY + 1):\n"
     "            resp = self._client.post_json(DETAIL_PATH, data={\"id\": str(ph_id)})",
     "        for attempt in (0,):\n"
     "            resp = self._client.post_json(DETAIL_PATH, data={\"id\": str(ph_id)})"),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_pytest() -> int:
    """跑**与本变异相关**的两支测试；⚠️ 必须设 `ACC_RESULTS_PATH`（否则冲掉权威四态，`T4` 报红）。"""
    env = dict(os.environ)                       # ⭐ 继承完整环境（⛔ 别只传两项 —— 进程起不来 = 假"变红"）
    env["ACC_RESULTS_PATH"] = "../artifacts/_mut_acc_results.json"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", "tests/test_print_fields.py", "tests/test_acc_print_acct.py",
         "-p", "no:cacheprovider", "--tb=no"],
        cwd=str(ROOT / "backend"), capture_output=True, text=True, env=env,
        encoding="utf-8", errors="replace",
    )
    return r.returncode


ok = 0
for name, path, old, new in MUTS:
    before = md5(path)
    orig_bytes = path.read_bytes()               # ⭐ **字节级**备份（⛔ 用文本读回写会把 CRLF 转成 LF）
    text = orig_bytes.decode("utf-8")
    if old not in text:
        print(f"❌ {name}：锚点没找到（源码变了？本脚本要跟着改）")
        continue
    path.write_text(text.replace(old, new), encoding="utf-8", newline="")
    try:
        rc = run_pytest()
        verdict = "✅ 变红" if rc != 0 else "❌ 没红（断言没区分力！）"
        ok += 1 if rc != 0 else 0
        print(f"{verdict}  {name}  (pytest rc={rc})")
    finally:
        path.write_bytes(orig_bytes)             # ⭐ 字节级复原
    after = md5(path)
    print(f"    复原 MD5 一致 = {before == after}")
    if before != after:
        print("    ⚠️⚠️ 复原不一致 —— 必须手工检查该文件！")

# 收尾：跑一次确认全绿（复原后）
final = run_pytest()
print(f"\n复原后 pytest rc={final} {'✅（全绿）' if final == 0 else '❌（复原后仍有红！）'}")
print(f"反向灵敏度：{ok}/{len(MUTS)} 变红")
raise SystemExit(0 if ok == len(MUTS) and final == 0 else 1)
