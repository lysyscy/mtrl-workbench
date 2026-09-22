#!/usr/bin/env python
"""`T8` 反向灵敏度（m08 撤项）—— 在代码面塞回 `m08imp` ⇒ `audit_drift` 必须红；跑完复原。"""
from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
REPO = pathlib.Path(r"D:\dev\mtrl-workbench")
PROBE = REPO / "backend" / "app" / "mod08_inv" / "_t8_probe_tmp.py"
PROBE.write_text('# 假装有人把 m08imp 加回来了\nX = "m08imp"\n', encoding="utf-8")
try:
    # ⚠️ 别跑 `audit_drift.py` 单件 —— T8 是 doc_audit 接线进去的，单跑它**不含 T8**（实测假绿）。
    r = subprocess.run(
        [str(REPO / "backend" / ".venv" / "Scripts" / "python.exe"), "-c",
         "import sys; sys.path.insert(0, r'tools/audit');"
         "from audit_drift import check_cancelled;"
         "h = check_cancelled();"
         "print('T8 命中', len(h));"
         "[print('   -', x['rel'], x['what'], x['level']) for x in h]"],
        cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "").strip() or (r.stderr or "")[-300:])
    hits = [l for l in (r.stdout or "").splitlines()
            if "_t8_probe_tmp" in l and "红" in l]
    print(f"T8 命中：{'✓ 抓到复活（红）' if hits else '⚠️ 没抓到 —— 守卫是假的'}")
    sys.exit(0 if hits else 1)
finally:
    PROBE.unlink(missing_ok=True)
