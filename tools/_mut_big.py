# -*- coding: utf-8 -*-
"""活动大表成品（`TAIL-04` 片 4b）—— **反向灵敏度**（变异测试）：改坏 ⇒ 断言必须变红。

⚠️ 每条变异：改坏 → 跑**指定那条断言**（期望 FAIL / ERROR）→ **按 bytes 复原** → 核 MD5。
⚠️ 锚点一律打在**被判据真正覆盖的那一处**（打偏 = 锚点错，不是断言假绿 —— 片 4a 实测踩过两条）。
⚠️ 子进程带 `PYTHONIOENCODING=utf-8` ＋ `PYTHONDONTWRITEBYTECODE=1`（后者防止往**交付面素材包**写编译缓存）。

用法： backend/.venv/Scripts/python.exe tools/_mut_big.py
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

BX = "backend/app/report_export/big_export.py"
TPL = "backend/app/report_export/tpl_fill.py"
T = "tests/test_big_export.py"

MUTS = [
    ("M1 列映射不再恒等（20 列反着排）", BX,
     'COL_OF_KEY: dict[str, str] = {c["key"]: get_column_letter(i + 1)\n'
     '                              for i, c in enumerate(B.BIG_COLUMNS)}\n',
     'COL_OF_KEY: dict[str, str] = {c["key"]: get_column_letter(len(B.BIG_COLUMNS) - i)\n'
     '                              for i, c in enumerate(B.BIG_COLUMNS)}\n',
     [T + "::test_列映射是恒等逐格等于域内核出口", T + "::test_两行逐格等于手写期望"]),

    ("M2 开工时间不设文本格式（会被 Excel 按数值吃）", BX,
     '        tpl_fill.set_text_format(ws, sheet_plan, YM_COL)        # 「开工时间」列：写文本前先设文本格式\n',
     '        pass  # 变异：不设文本格式\n',
     [T + "::test_开工时间是页面文本且数字格式为文本"]),

    ("M3 不可得的总额写 0（该留空的格子写了 0）", BX,
     '    tail_cells = {COL_OF_KEY[k]: (totals[k] if totals.get(k) is not None else "")\n'
     '                  for k in B.TOTAL_KEYS}\n',
     '    tail_cells = {COL_OF_KEY[k]: (totals[k] if totals.get(k) is not None else Decimal("0.00"))\n'
     '                  for k in B.TOTAL_KEYS}\n',
     [T + "::test_不可得的总额显式留空不写0"]),

    ("M4 合计行标签写进 B 列（A 列序号列被占用 / 行号错位）", BX,
     '    return {"sheet": SHEET, "rows": body, "tail": {0: (TOTAL_LABEL, tail_cells)}}\n',
     '    return {"sheet": SHEET, "rows": body, "tail": {0: (None, {"B": TOTAL_LABEL, **tail_cells})}}\n',
     [T + "::test_序号是系统行号且合计行不编号"]),

    ("M5 标题照抄模板（写死的日期没被替换）", BX,
     '    return _MON.sub(f"（{m}月份数据）", _CUT.sub(f"（数据截止{m}月{last}日）", text))\n',
     '    return text\n',
     [T + "::test_标题随核算月重写且当月末日按日历算"]),

    # ⚠️ 这条**必须体现"该功能不存在时的行为"** —— 第一版我把它改成 `if False:`，结果 `elif` 分支照样写了个
    #    空串、结果与"清空"**等价** ⇒ 变异**无害**（不是断言假绿，是变异打偏）。
    #    真正的"没有这功能" = 那格**压根不写**（也不记入 `written`）⇒ 模板公式留着 ⇒ 对账必须报。
    ("M6 引擎不认「空串 = 显式留空」（当作没给 ⇒ 模板公式留着）", TPL,
     '            if value == "":                                  # ⭐ **空串 = 显式留空**（清掉模板那格的公式 / 旧值）\n'
     '                ws.cell(row=r, column=ci).value = None\n'
     '                written.add((r, ci))\n',
     '            if value == "":                                  # 变异：当作"没给" ⇒ 跳过\n'
     '                continue\n',
     [T + "::test_不可得的总额显式留空不写0"]),
]


def _read(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()


def _fit(rel: str, text: str) -> bytes:
    data = _read(rel)
    return (text.replace("\n", "\r\n") if b"\r\n" in data else text).encode("utf-8")


def main() -> int:
    files = {BX, TPL}
    base = {rel: _read(rel) for rel in files}
    before = {rel: hashlib.md5(d).hexdigest() for rel, d in base.items()}
    print("基线 MD5:")
    for rel, h in before.items():
        print("   %-46s %s" % (rel, h))

    ok = fail = 0
    env = dict(os.environ, CODEBUDDY_SAFE_DELETE_ENABLED="0", PYTHONIOENCODING="utf-8",
               PYTHONDONTWRITEBYTECODE="1")
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
                           capture_output=True, text=True, encoding="utf-8", env=env)
        path.write_bytes(base[rel])
        restored = hashlib.md5(path.read_bytes()).hexdigest() == before[rel]
        red = r.returncode != 0
        good = red and restored
        ok += 1 if good else 0
        fail += 0 if good else 1
        print("\n%s %s" % ("✓" if good else "✗", name))
        print("     断言变红=%s  复原 MD5 一致=%s" % (red, restored))
        if not red:
            print("     ⚠️ 变异后仍然全绿 ⇒ **这条断言是假绿**，必须改紧！")

    print("\n--- 收尾核对 ---")
    for rel in base:
        now = hashlib.md5((ROOT / rel).read_bytes()).hexdigest()
        assert now == before[rel], "%s 未逐字节复原！" % rel
        print("   %-46s 复原 ✓ %s" % (rel, now))
    print("\n结果：%d/%d 通过" % (ok, ok + fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
