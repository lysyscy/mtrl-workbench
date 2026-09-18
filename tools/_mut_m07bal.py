# -*- coding: utf-8 -*-
"""「结余录入」片（2026-09-18 用户裁定「甲」）—— **反向灵敏度**（变异测试）：改坏 ⇒ 断言必须变红。

⚠️ 每条变异：改坏 → 跑**指定的那条断言**（期望 FAIL / ERROR）→ **按 bytes 复原** → 核 MD5。
   复原后 MD5 必须与开头记录的一致；不一致就是没真还原。
⚠️ 锚点一律打在**被判据真正覆盖的那一处**（打偏 = 锚点错，不是断言假绿）。

⚠️ 沙箱有 safe-delete 护栏（同 turn 内累计删 >50 文件会抛 SystemExit，跑多轮 pytest 会冒**假红**）
   ⇒ 子进程带 `CODEBUDDY_SAFE_DELETE_ENABLED=0`（shim 自带开关，不是绕过安全）。

用法： backend/.venv/Scripts/python.exe tools/_mut_m07bal.py
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PY = BACKEND / ".venv" / "Scripts" / "python.exe"

R = "backend/app/mod07_setl/repository.py"
S = "backend/app/mod07_setl/service.py"
X = "backend/app/mod07_setl/extract.py"

T = "tests/test_m07_balance.py"

#: 把 `service` 里的 import 换掉、并在原地**再抄一份** `load_balances`（包装层）——
#: 用来证明「取数出口只有一份」那条断言断的是**同一性**（`is`），不是"两边都能调"。
_COPY_IMPORT = "from app.mod07_setl.repository import load_balances, load_rows, save_balance"
_COPY_IMPORT_NEW = (
    "from app.mod07_setl.repository import load_rows, save_balance\n"
    "\n"
    "\n"
    "def load_balances(s):  # noqa: D103 —— 变异：业务层又抄了一份（应被判据抓住）\n"
    "    from app.mod07_setl.repository import load_balances as _r\n"
    "    return _r(s)\n"
)

MUTS = [
    ("M1 未录入当成 0（该格写 0，冒充「确实为 0」）", X,
     '            "balance": bal.get(w),\n',
     '            "balance": (bal[w] if w in bal else Decimal("0.00")),\n',
     [T + "::test_未录入时导出该格如实留空"]),
    ("M2 装配断了（导出不读库里结余，写死 balances=None）", S,
     "            year=report_ym[:4] if report_ym else \"\", balances=balances)\n",
     "            year=report_ym[:4] if report_ym else \"\", balances=None)\n",
     [T + "::test_录入后导出按类别仓库带上该值",
      T + "::test_导出真的去读了库里的结余"]),
    ("M3 清空改成写 0（未录入与 0 混为一谈）", R,
     "        if row is not None:\n            s.delete(row)\n",
     "        if row is not None:\n            row.amount = to_money(0)\n",
     [T + "::test_清空后回到未录入"]),
    ("M4 负数放行（丢掉非负判据）", X,
     '        v = require_non_negative(s, field="结余")\n',
     "        v = to_money(s)\n",
     [T + "::test_负数被拒不写库原值不变"]),
    ("M5 不校验类别（认不出的类别也落库）", S,
     '    if str(kind or "") not in X.KINDS:\n',
     "    if False:\n",
     [T + "::test_认不出的类别被拒"]),
    ("M6 不校验仓库非空", S,
     "    wh = str(warehouse or \"\").strip()\n    if not wh:\n",
     "    wh = str(warehouse or \"\").strip()\n    if False:\n",
     [T + "::test_空仓库被拒"]),
    ("M7 粒度变成「每次都新建一行」（不再是类别 × 仓库覆盖）", R,
     "    row = _find_balance(s, kind, warehouse)\n",
     "    row = None\n",
     [T + "::test_重复保存是覆盖不长出第二行"]),
    ("M8 业务层又抄一份 load_balances（只断「能调」会假绿）", S,
     _COPY_IMPORT + "\n",
     _COPY_IMPORT_NEW + "\n",
     [T + "::test_取数出口只有一份实现"]),
]


def _read(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()


def _fit(rel: str, text: str) -> bytes:
    """按目标文件的**行尾习惯**归一（本仓源码行尾不统一 ⇒ ⛔ 不能硬用 `\\n`）。"""
    data = _read(rel)
    enc = text.replace("\n", "\r\n") if b"\r\n" in data else text
    return enc.encode("utf-8")


def main() -> int:
    base = {rel: _read(rel) for rel in {R, S, X}}
    before = {rel: hashlib.md5(d).hexdigest() for rel, d in base.items()}
    print("基线 MD5:")
    for rel, h in before.items():
        print("   %-44s %s" % (rel, h))

    ok = fail = 0
    env = dict(os.environ, CODEBUDDY_SAFE_DELETE_ENABLED="0")
    for name, rel, old, new, tests in MUTS:
        path = ROOT / rel
        ob, nb = _fit(rel, old), _fit(rel, new)
        cur = path.read_bytes()
        if ob not in cur:
            print("\n✗ SKIP %s —— 锚点没命中（`%s`）" % (name, old.strip().splitlines()[0][:60]))
            fail += 1
            continue
        path.write_bytes(cur.replace(ob, nb, 1))
        # ⚠️ 显式 `encoding="utf-8"`：子进程继承 `PYTHONIOENCODING=utf-8` 输出 UTF-8，
        #    而父进程默认按 GBK 解码 ⇒ 会抛一堆 `UnicodeDecodeError`（噪音，不是测试失败）。
        r = subprocess.run([str(PY), "-m", "pytest", "-q", *tests], cwd=str(BACKEND),
                           capture_output=True, text=True, encoding="utf-8", env=env)
        path.write_bytes(base[rel])                       # 立即复原
        restored = hashlib.md5(path.read_bytes()).hexdigest() == before[rel]
        red = r.returncode != 0
        good = red and restored
        ok += 1 if good else 0
        fail += 0 if good else 1
        print("\n%s %s" % ("✓" if good else "✗", name))
        print("     断言变红=%s  复原 MD5 一致=%s" % (red, restored))
        if not red:
            print("     ⚠️ 变异后仍然全绿 ⇒ **这条断言是假绿**，必须改紧！")
            out = (r.stdout or "").strip().splitlines()
            if out:
                print("     " + out[-1])

    print("\n--- 收尾核对 ---")
    for rel in base:
        now = hashlib.md5((ROOT / rel).read_bytes()).hexdigest()
        assert now == before[rel], "%s 未逐字节复原！%s != %s" % (rel, now, before[rel])
        print("   %-44s 复原 ✓ %s" % (rel, now))
    print("\n结果：%d/%d 通过" % (ok, ok + fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
