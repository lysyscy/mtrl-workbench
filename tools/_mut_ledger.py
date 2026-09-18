# -*- coding: utf-8 -*-
"""台账成品（`TAIL-04` 片 2＋3）—— **反向灵敏度**（变异测试）：改坏 ⇒ 断言必须变红。

⚠️ 每条变异：改坏 → 跑**指定那条断言**（期望 FAIL / ERROR）→ **按 bytes 复原** → 核 MD5。
⚠️ 锚点一律打在**被判据真正覆盖的那一处**（打偏 = 锚点错，不是断言假绿）。
⚠️ 子进程带 `PYTHONIOENCODING=utf-8`（否则 pytest 输出里的 `✅` 撞 GBK ⇒ `UnicodeDecodeError` 噪音）
   ＋ `CODEBUDDY_SAFE_DELETE_ENABLED=0`（多轮 pytest 会撞 safe-delete 护栏 ⇒ 假红）。

用法： backend/.venv/Scripts/python.exe tools/_mut_ledger.py
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

L = "backend/app/report_export/ledger_export.py"
T = "tests/test_ledger_export.py"

MUTS = [
    ("M1 只填两个 sheet（第三张不管 ⇒ 模板示例数据留下）", L,
     "        specs.append(fee_spec(sections.get(SHEET_FEE) or {}, display=display, ym=ym))\n",
     "        pass  # 变异：第三个 sheet 不填\n",
     [T + "::test_模板示例数据一格不留", T + "::test_特殊费用月报表逐格等于手写期望"]),

    ("M2 期初行的月份写成 YYYY-MM（丢掉页面文本口径）", L,
     '    if row.get("is_opening") and len(ym) >= 7 and ym[4] == "-":\n',
     "    if False:\n",
     [T + "::test_期初行的月份是页面文本不是YYYY_MM"]),

    ("M3 月份列不设文本格式（会被 Excel 按日期吃）", L,
     "        ws.cell(row=plan[\"data_start\"] + i, column=col).number_format = TEXT_FMT\n",
     "        ws.cell(row=plan[\"data_start\"] + i, column=col).number_format = \"General\"\n",
     [T + "::test_月份列的数字格式是文本"]),

    ("M4 合计只用第一条数据行（尾块不随行数派生）", L,
     '        LEDGER_COL["other"]: sum_money([r.get("other_expense") for r in rows]),\n',
     '        LEDGER_COL["other"]: sum_money([r.get("other_expense") for r in rows[:1]]),\n',
     [T + "::test_合计行等于各数据行之和且紧随其后"]),

    ("M5 不压列（多月列照旧 ⇒ 单月列没生成）", L,
     "        collapse_months(fee_ws, ym)                       # ⚠️ 先压列、再填行\n",
     "        pass  # 变异：不压列\n",
     [T + "::test_特殊费用月报表的单月列由报告月生成"]),

    ("M6 标题照抄模板（别的项目名留在成品里）", L,
     '            wb[sheet]["A1"] = title_of(display, sheet)    # 标题里写着别的项目名 ⇒ 整格替换\n',
     "            pass  # 变异：不替换标题\n",
     [T + "::test_标题用展示名且不带项目二字"]),

    ("M7 标题多带「项目」二字（用户 2026-09-18 已裁不带）", L,
     '    return f"{display or \'\'}{TITLE_SUFFIX[sheet]}"\n',
     '    return f"{display or \'\'}项目{TITLE_SUFFIX[sheet]}"\n',
     [T + "::test_标题用展示名且不带项目二字"]),

    ("M8 zip 只打第一本（交付形态漏文件）", L,
     "        for p in paths:\n            zf.write(str(p), Path(p).name)\n",
     "        for p in list(paths)[:1]:\n            zf.write(str(p), Path(p).name)\n",
     [T + "::test_两个项目打成一个zip"]),
]


def _read(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()


def _fit(rel: str, text: str) -> bytes:
    """按目标文件的**行尾习惯**归一（本仓源码行尾不统一 ⇒ ⛔ 不能硬用 `\\n`）。"""
    data = _read(rel)
    return (text.replace("\n", "\r\n") if b"\r\n" in data else text).encode("utf-8")


def main() -> int:
    base = {rel: _read(rel) for rel in {L}}
    before = {rel: hashlib.md5(d).hexdigest() for rel, d in base.items()}
    print("基线 MD5:")
    for rel, h in before.items():
        print("   %-46s %s" % (rel, h))

    ok = fail = 0
    env = dict(os.environ, CODEBUDDY_SAFE_DELETE_ENABLED="0", PYTHONIOENCODING="utf-8")
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

    print("\n--- 收尾核对 ---")
    for rel in base:
        now = hashlib.md5((ROOT / rel).read_bytes()).hexdigest()
        assert now == before[rel], "%s 未逐字节复原！%s != %s" % (rel, now, before[rel])
        print("   %-46s 复原 ✓ %s" % (rel, now))
    print("\n结果：%d/%d 通过" % (ok, ok + fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
