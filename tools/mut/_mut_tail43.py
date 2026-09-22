# -*- coding: utf-8 -*-
"""`TAIL-43` 反向灵敏度（变异测试）：**故意改坏 6 处 ⇒ 对应断言必须变红**。

⚠️ 每条变异：改坏 → 跑指定断言（**期望 FAIL**）→ **按 bytes 复原** → 核 MD5。
   复原后 MD5 必须与开头记录的一致；不一致就是没真还原。

用法： backend/.venv/Scripts/python.exe tools/_mut_tail43.py
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PY = BACKEND / ".venv" / "Scripts" / "python.exe"

T = "backend/app/report_export/sheet_display.py"   # 拆件后显示区搬到这
E = "backend/app/report_export/tpl_engine.py"
K = "backend/app/report_export/kcdj_export.py"
S = "backend/app/report_export/setl_export.py"

MUTS = [
    ("M1 render 不丢弃区间外的旧行（僵尸行残留）", T,
     "    parts = []\n    for r in sorted(keep | hdr):\n",
     "    parts = []\n    for r in sorted(set(old) | keep | hdr):\n",
     ["tests/test_tail43_display.py::test_显示区无僵尸行且行区间随仓库数收缩",
      "tests/test_tail43_display.py::test_该月无该费用时透视如实为空且不留模板旧值"]),
    ("M2 无匹配记录写 0（冒充「确实为 0」）", K,
     "            if got:                                  # ⚠️ 无匹配记录 ⇒ 不写（⛔ 不写 0）\n"
     "                cells[c['letter']] = got[0]\n",
     "            cells[c['letter']] = got[0] if got else 0.0\n",
     ["tests/test_tail43_display.py::test_该月无该费用时透视如实为空且不留模板旧值"]),
    ("M3 verify_display 不做僵尸行检查", T,
     "        want_last = first + len(spec['rows'])            # 含总计行\n",
     "        want_last = 10 ** 6                              # 含总计行\n",
     ["tests/test_tail43_display.py::test_反向_把显示区换回模板旧值守卫必须报红"]),
    ("M4 两张显示区共用「过程资料」的列（静默错列）", K,
     "        sp[\"by_label\"], sp[\"total\"] = aggregate_grid(\n"
     "            data, sp[\"columns\"], nat2group,\n",
     "        sp[\"by_label\"], sp[\"total\"] = aggregate_grid(\n"
     "            data, sheets[0][\"columns\"], nat2group,\n",
     ["tests/test_tail43_display.py::test_安全费那张按规定自己的列聚合不许挪用过程资料的列"]),
    ("M5 收发结存不清显示区之外的行", S,
     "    last = r_grand\n    if ws1.max_row > last:\n",
     "    last = r_grand\n    if ws1.max_row > 10 ** 6:\n",
     ["tests/test_tail43_display.py::test_收发结存的显示区也不许留旧行"]),
    ("M6 整个显示区重建没接线（当作没传 sheets）", E,
     "    for sp in cfg.get('sheets', []):\n",
     "    for sp in []:\n",
     ["tests/test_tail43_display.py::test_显示区无僵尸行且行区间随仓库数收缩",
      "tests/test_tail43_display.py::test_三路一致_报表1与缓存与显示区逐格相同"]),
]


def _read(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()


def _fit(rel: str, text: str) -> bytes:
    """按目标文件的**行尾习惯**归一（本仓源码行尾不统一 ⇒ ⛔ 不能硬用 `\\n`）。"""
    data = _read(rel)
    enc = text.replace("\n", "\r\n") if b"\r\n" in data else text
    return enc.encode("utf-8")


def main() -> int:
    base = {rel: _read(rel) for rel in {T, K, S, E}}
    before = {rel: hashlib.md5(d).hexdigest() for rel, d in base.items()}
    print("基线 MD5:")
    for rel, h in before.items():
        print("   %-46s %s" % (rel, h))

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
        r = subprocess.run([str(PY), "-m", "pytest", "-q", *tests], cwd=str(BACKEND),
                           capture_output=True, text=True, env=env)
        path.write_bytes(base[rel])                       # 立即复原
        restored = hashlib.md5(path.read_bytes()).hexdigest() == before[rel]
        red = r.returncode != 0
        flag = "✓" if (red and restored) else "✗"
        ok += 1 if (red and restored) else 0
        fail += 0 if (red and restored) else 1
        print("\n%s %s" % (flag, name))
        print("     断言变红=%s  复原 MD5 一致=%s" % (red, restored))
        if not red:
            print("     ⚠️ 变异后仍然全绿 ⇒ **这几条断言是假绿**，必须改紧！")
            print("     " + (r.stdout or "").strip().splitlines()[-1] if r.stdout else "")

    print("\n--- 收尾核对 ---")
    for rel in base:
        now = hashlib.md5((ROOT / rel).read_bytes()).hexdigest()
        assert now == before[rel], "%s 未逐字节复原！%s != %s" % (rel, now, before[rel])
        print("   %-46s 复原 ✓ %s" % (rel, now))
    print("\n结果：%d/%d 通过" % (ok, ok + fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
