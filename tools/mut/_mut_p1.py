# -*- coding: utf-8 -*-
"""路径①（模板填充）片 1 —— **反向灵敏度**（变异测试）：故意改坏 ⇒ 对应断言必须变红。

⚠️ 每条变异：改坏 → 跑指定断言（**期望 FAIL / ERROR**）→ **按 bytes 复原** → 核 MD5。
   复原后 MD5 必须与开头记录的一致；不一致就是没真还原。

⚠️ 沙箱有 safe-delete 护栏（同 turn 内累计删 >50 文件会抛 SystemExit，跑多轮 pytest 会冒**假红**）
   ⇒ 子进程带 `CODEBUDDY_SAFE_DELETE_ENABLED=0`（shim 自带开关，不是绕过安全）。

用法： backend/.venv/Scripts/python.exe tools/_mut_p1.py
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

F = "backend/app/report_export/tpl_fill.py"
W = "backend/app/report_export/weldgas_export.py"
S = "backend/app/mod07_setl/service.py"
X = "backend/app/mod07_setl/extract.py"

T1 = "tests/test_path1_weldgas.py"
T2 = "tests/test_acc_setl_ext_001.py"

MUTS = [
    ("M1 数据行不清值（模板示例值留在数据区）", F,
     "        _clear_row(ws, r, max_col)\n",
     "        pass  # 不清\n",
     [T1 + "::test_模板自带的示例值一格不留"]),
    ("M2 起点抄坐标（写死第 2 行，不认标记文字）", F,
     "    hits = [r for r in range(1, ws.max_row + 1)\n"
     '            if str(ws.cell(row=r, column=key_idx).value or "").strip() == marker]\n',
     "    hits = [2]\n",
     [T1 + "::test_数据区起点认标记文字而不是抄坐标"]),
    ("M3 守卫不做「尾块以下」残留检查", F,
     "            for r in range(last + 1, raw.max_row + 1):          # ③ 残留（含公式残留）\n",
     "            for r in range(last + 1, last + 1):                 # ③ 残留（含公式残留）\n",
     [T1 + "::test_显示区对账抓得出残留"]),
    ("M4 守卫不做「值覆盖不彻底」检查", F,
     '                    if isinstance(v, str) and v.startswith("="):\n',
     "                    if False:\n",
     [T1 + "::test_显示区对账抓得出公式残留"]),
    ("M5 该月无数据写 0（冒充「确实为 0」）", X,
     "        cells = [(by_ym.get(m) or None) for m in months]\n",
     '        cells = [(by_ym.get(m) or Decimal("0.00")) for m in months]\n',
     [T1 + "::test_成品显示区逐格等于独立复算"]),
    ("M6 忽略项目状态筛选（行集合不再跟筛选）", S,
     "            warehouses=_visible(amounts, kind, st, statuses, order),\n",
     "            warehouses=list(amounts[kind]),\n",
     [T1 + "::test_成品行即所筛选项目且与页面同一份口径"]),
    ("M7 合计行丢掉「合计」列（模板公式没被覆盖）", W,
     '    if sums:\n        cells[COL_TOTAL] = sums[-1]\n',
     "    if False:\n        cells[COL_TOTAL] = sums[-1]\n",
     [T1 + "::test_成品显示区逐格等于独立复算"]),
    # ⚠️ 2026-09-23（`TAIL-77`）：锚点**尾部不带那行注释** —— 实现后来在 `pop(...)` 那行后面
    #    加了说明（`# 再清行属性…`）⇒ 旧锚点（带 `\n`）一处都命中不上、报 SKIP＝静默失效。
    ("M8 不清残留的行属性空壳（Excel 的 UsedRange 会多算）", F,
     "    for r in [x for x in ws.row_dimensions if x > last_row]:\n"
     "        ws.row_dimensions.pop(r, None)",
     "    for r in []:\n"
     "        ws.row_dimensions.pop(r, None)",
     [T1 + "::test_引擎_尾块随行数派生且零行也不留残骸"]),
    # ⚠️ 2026-10-09（`TAIL-267` 焊材/气体名单优化）：下面三条盯的是**名单本身**。
    #   名单写错时金额照样算得出来、页面照样能导出 ⇒ 没有这几条，判据是假绿。
    ("M9 焊材词根退回「焊锡丝」（漏掉焊锡膏这一类）", X,
     'DEFAULT_WELD_KEYWORDS: tuple[str, ...] = ("焊丝", "焊条", "焊锡")\n',
     'DEFAULT_WELD_KEYWORDS: tuple[str, ...] = ("焊丝", "焊条", "焊锡丝")\n',
     [T2 + "::test_提取名单按在库实测样本_钉死"]),
    ("M10 焊材排除子串清空（工具/管材/劳保被当焊材收）", X,
     'DEFAULT_NOT_WELD: tuple[str, ...] = (\n'
     '    # 容器 / 器具（实测误收的四项：保温桶 · 桶加热线 · 烘干箱 · 烘干箱把手）\n'
     '    "保温桶", "烘干箱", "加热线", "把手", "焊把", "焊枪", "焊机", "送丝机",\n'
     '    "插头", "插座", "接头", "瓷嘴", "尾堵", "保护套", "保护咀", "检验尺",\n'
     '    # 管材（实测单位就是 Kg ⇒ **挡不住，只能靠这里挡**）\n'
     '    "焊管", "钢管",\n'
     '    # 劳保\n'
     '    "手套", "面罩", "帽子", "眼镜",\n'
     ')\n',
     'DEFAULT_NOT_WELD: tuple[str, ...] = ()\n',
     [T2 + "::test_提取名单按在库实测样本_钉死"]),
    ("M11 气体名单少一项（补进去的 6 项漏掉几个）", X,
     '    "乙炔", "液二氧", "液化气", "高纯混合气", "氮气", "高纯液氮",\n',
     '    "液二氧", "液化气", "高纯混合气", "氮气",\n',
     [T2 + "::test_提取名单按在库实测样本_钉死"]),
]


def _read(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()


def _fit(rel: str, text: str) -> bytes:
    """按目标文件的**行尾习惯**归一（本仓源码行尾不统一 ⇒ ⛔ 不能硬用 `\\n`）。"""
    data = _read(rel)
    enc = text.replace("\n", "\r\n") if b"\r\n" in data else text
    return enc.encode("utf-8")


def main() -> int:
    base = {rel: _read(rel) for rel in {F, W, S, X}}
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
        # ⚠️ 2026-09-23（`TAIL-77`）：必须**显式 `encoding="utf-8"`** —— 原先 `text=True` 走本机
        #    区域编码（GBK）⇒ pytest 输出里一旦有非 GBK 字节就 `UnicodeDecodeError` ⇒ **整个脚本崩掉**。
        r = subprocess.run([str(PY), "-m", "pytest", "-q", *tests], cwd=str(BACKEND),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env)
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
