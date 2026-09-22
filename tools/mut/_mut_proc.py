# -*- coding: utf-8 -*-
"""过程资料成品（`TAIL-04` 片 4a）—— **反向灵敏度**（变异测试）：改坏 ⇒ 断言必须变红。

⚠️ 每条变异：改坏 → 跑**指定那条断言**（期望 FAIL / ERROR）→ **按 bytes 复原** → 核 MD5。
⚠️ 锚点一律打在**被判据真正覆盖的那一处**（打偏 = 锚点错，不是断言假绿）。
⚠️ 子进程带 `PYTHONIOENCODING=utf-8` ＋ `PYTHONDONTWRITEBYTECODE=1`（后者防止在**交付面素材包**里
   写编译缓存 —— 那会把 `_doccheck` 的【素材包文件数】事实位顶高，2026-09-18 实测踩到）。

用法： backend/.venv/Scripts/python.exe tools/_mut_proc.py
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

PX = "backend/app/report_export/process_export.py"
S = "backend/app/report_export/service.py"
DOM = "backend/app/mod06_proc/domain.py"
T = "tests/test_process_export.py"

MUTS = [
    ("M1 差异表用「调整后」顶替（差额没算）", S,
     '            rows = adjusted if tab_no == D.TAB_ADJUSTED else D.difference_rows(raw, adjusted)\n',
     '            rows = adjusted if tab_no == D.TAB_ADJUSTED else adjusted\n',
     [T + "::test_差异表逐格等于调整后减原始_含负数与空态"]),

    ("M2 列序照域内顺序（临时设施 ↔ 周转材料 对调）", PX,
     '    "in_主辅材": "C", "in_工具": "D", "in_劳保": "E", "in_临时设施": "F", "in_周转材料": "G",\n',
     '    "in_主辅材": "C", "in_工具": "D", "in_劳保": "E", "in_临时设施": "G", "in_周转材料": "F",\n',
     # ⚠️ 目标必须**同时**跑"逐格"那条 —— 表头是从模板读的，光对调映射改不动表头 ⇒
     #    只跑查表头的那条会**假绿**（本文件第一次就是这么打偏的）。
     [T + "::test_逐格等于手写期望_含材料空态留空",
      T + "::test_十八列且列序照模板_临时设施在周转材料前"]),

    ("M3 尾块标签写进 A 列（小计 / 合计行被编了号）", PX,
     '        "tail": {OFF_SUB: (None, {TIME_COL: "小计", **sub}),\n'
     '                 OFF_TOTAL: (None, {TIME_COL: "合计：", **total})},\n',
     '        "tail": {OFF_SUB: ("小计", {TIME_COL: "小计", **sub}),\n'
     '                 OFF_TOTAL: ("合计：", {TIME_COL: "合计：", **total})},\n',
     [T + "::test_序号是系统行号且小计合计脚注行不编号"]),

    ("M4 时间列不设文本格式（会被 Excel 按日期吃）", PX,
     '        tpl_fill.set_text_format(ws, sheet_plan, TIME_COL)  # 「时间」列：写文本前先设文本格式\n',
     '        pass  # 变异：不设文本格式\n',
     [T + "::test_时间列是页面文本且数字格式为文本"]),

    ("M5 空态写 0（该留空的格子写了 0）", PX,
     "            if value is None:\n                continue                                    # 空态 ⇒ 该格留空（⛔ 不写 0）\n",
     "            if value is None:\n                cells[col] = Decimal(\"0.00\")\n                continue\n",
     [T + "::test_逐格等于手写期望_含材料空态留空"]),

    ("M6 差额算反了（原始 − 调整后）", DOM,
     "                (right if right is not None else Decimal(\"0.00\"))\n"
     "                - (left if left is not None else Decimal(\"0.00\")))\n",
     "                (left if left is not None else Decimal(\"0.00\"))\n"
     "                - (right if right is not None else Decimal(\"0.00\")))\n",
     [T + "::test_差异表逐格等于调整后减原始_含负数与空态"]),

    ("M7 取不到展示名就拿仓库名顶上（⛔ 用户已裁不许）", S,
     '        display = displays.get(key) or ""\n',
     '        display = displays.get(key) or key\n',
     [T + "::test_拒做取不到展示名"]),

    ("M8 合计只给第一段（四段变一段）", PX,
     '    total = {anchor: seg["total"] for anchor, seg in zip(TOTAL_ANCHORS, segments)}\n',
     '    total = {TOTAL_ANCHORS[0]: segments[0]["total"]}\n',
     [T + "::test_小计是数据区垂直求和且合计是四段横向之和"]),
]


def _read(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()


def _fit(rel: str, text: str) -> bytes:
    """按目标文件的**行尾习惯**归一（本仓源码行尾不统一 ⇒ ⛔ 不能硬用 `\\n`）。"""
    data = _read(rel)
    return (text.replace("\n", "\r\n") if b"\r\n" in data else text).encode("utf-8")


def main() -> int:
    files = {PX, S, DOM}
    base = {rel: _read(rel) for rel in files}
    before = {rel: hashlib.md5(d).hexdigest() for rel, d in base.items()}
    print("基线 MD5:")
    for rel, h in before.items():
        print("   %-48s %s" % (rel, h))

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
        print("   %-48s 复原 ✓ %s" % (rel, now))
    print("\n结果：%d/%d 通过" % (ok, ok + fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
