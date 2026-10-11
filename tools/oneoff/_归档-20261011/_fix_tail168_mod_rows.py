#!/usr/bin/env python
"""`TAIL-168`：修交付面 `MOD-*.md` 里那 **5 行「多打一个 `|`」的能力行** ＋ 补 `MOD-06` 一处认领（2026-09-29）。

**成因**（已查实，⛔ 不是"删了行"）：`tools/probe/_audit_face.py` 的尺子 `A` 报「`MOD-03` 缺 14 ·
`MOD-04` 缺 11 · `MOD-10` 缺 2·3 · `MOD-14` 缺 6」—— 查下来那 5 行的编号**都在**，只是被写成了
`|| 14 | …`（**首列多一格空** ⇒ 6 格）⇒ 按「首格 = 编号」解析的尺子**看不见它们**。
证据：交付面 `_backup-20260915-1824` 等老快照里这几行是**正常**的 `| 14 | …` ⇒ 是**后来某轮编辑**多打的。
⚠️ 同样形状的行在《说明书》里**还有 33 处、但那是刻意的层级缩进**（`ENT-01` 的续行 `| | | 字段 | …`）⇒ ⛔ **一个都不许动**。

**它做什么**（两件 —— 只删多余的那个 `|`／只往末列补一个已存在的用例号，⛔ 正文一个字不改）：
  1. 5 行：`|| N | ` ⇒ `| N | `（`MOD-03` #14 · `MOD-04` #11 · `MOD-10` #2/#3 · `MOD-14` #6）；
  2. `MOD-06` 能力表 **#9「过程资料历史导入」**末列补一个 `· ACC-PROC-IMPORT-001`
     （该用例 `module = MOD-06`、讲的就是历史导入的**识别口径** ⇒ 主人是这一行；尺子 `B` 要的就是这个认领）。

**自检**（写完必过）：① 每个 MOD 的能力编号变成 `1..N` **连续**；② 每个文件行尾 round-trip 一致（⛔ 不文本替换）。

用法（工程根）：`… _fix_tail168_mod_rows.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
MODDIR = FACE / "PRD" / "02-功能规格"

#: 文件 → [(说明, 原文, 改写后)]（⚠️ 原文一律**带行首那半个表格**，保证唯一）
EDITS: dict[str, list[tuple[str, str, str]]] = {
    "MOD-03.md": [("#14 行多打一个 `|`（集采付款的特殊处理）", "|| 14 | **集采付款的特殊处理**", "| 14 | **集采付款的特殊处理**")],
    "MOD-04.md": [("#11 行多打一个 `|`（实际执行偏离的处理）", "|| 11 | 实际执行偏离的处理", "| 11 | 实际执行偏离的处理")],
    "MOD-10.md": [
        ("#2 行多打一个 `|`（机械费源头）", "|| 2 | 机械费的**源头**", "| 2 | 机械费的**源头**"),
        ("#3 行多打一个 `|`（结算金额派生）", "|| 3 | ⭐ **「结算金额」由源头派生、只读**", "| 3 | ⭐ **「结算金额」由源头派生、只读**"),
    ],
    "MOD-14.md": [("#6 行多打一个 `|`（全局一致性清单展示）", "|| 6 | 全局一致性清单的**展示**", "| 6 | 全局一致性清单的**展示**")],
}

#: `MOD-06` 补认领：能力 #9（过程资料历史导入）末列已有 `ACC-RPT-PROC-002` ⇒ 补 `ACC-PROC-IMPORT-001`
MOD06_OLD = "§5.2.5 · §9.3 | — | `ACC-RPT-PROC-002` |"
MOD06_NEW = "§5.2.5 · §9.3 | — | `ACC-RPT-PROC-002` · `ACC-PROC-IMPORT-001` |"

ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|")
HEAD_RE = re.compile(r"^\|\s*#\s*\|\s*能力")


def cap_numbers(lines: list[str]) -> list[int]:
    for i, ln in enumerate(lines):
        if HEAD_RE.match(ln):
            nums: list[int] = []
            for ln2 in lines[i + 1:]:
                if not ln2.startswith("|"):
                    break
                m = ROW_RE.match(ln2)
                if m:
                    nums.append(int(m.group(1)))
            return nums
    return []


def read_text(p: pathlib.Path) -> tuple[str, bool]:
    """→ (规范化文本, 是否 CRLF)。⛔ 顺带做行尾 round-trip 自检（不等就拒写）。"""
    raw = p.read_bytes()
    crlf = b"\r\n" in raw
    t = raw.decode("utf-8").replace("\r\n", "\n")
    back = t.replace("\n", "\r\n") if crlf else t
    assert back.encode("utf-8") == raw, f"{p.name}：行尾 round-trip 不一致 ⇒ ⛔ 别写"
    return t, crlf


def sub1(t: str, old: str, new: str, where: str) -> str:
    n = t.count(old)
    assert n == 1, f"{where}：命中 {n} 次（期望 1）—— ⛔ 先核原文"
    return t.replace(old, new, 1)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    # ① 收前状态
    print("改前能力编号：")
    pre: dict[str, list[int]] = {}
    for name in list(EDITS) + ["MOD-06.md"]:
        t, _ = read_text(MODDIR / name)
        pre[name] = cap_numbers(t.split("\n"))
        miss = sorted(set(range(1, max(pre[name]) + 1)) - set(pre[name])) if pre[name] else []
        print(f"  {name:<12} {pre[name]}{'  ⛔ 缺 ' + str(miss) if miss else ''}")

    # ② 逐文件词法替换（含 MOD-06 补认领）
    out: dict[str, tuple[str, bool]] = {}
    for name, edits in EDITS.items():
        t, crlf = read_text(MODDIR / name)
        for desc, old, new in edits:
            t = sub1(t, old, new, f"{name}｜{desc}")
        out[name] = (t, crlf)
    t6, crlf6 = read_text(MODDIR / "MOD-06.md")
    t6 = sub1(t6, MOD06_OLD, MOD06_NEW, "MOD-06.md｜#9 补认领")
    out["MOD-06.md"] = (t6, crlf6)

    # ③ 改后自检：能力编号 1..N 连续（尺子 `A` 的口径）
    print("\n改后能力编号（自检 = 1..N 连续）：")
    ok = True
    for name, (t, _) in out.items():
        nums = cap_numbers(t.split("\n"))
        miss = sorted(set(range(1, max(nums) + 1)) - set(nums)) if nums else [1]
        flag = "✅" if not miss else f"⛔ 仍缺 {miss}"
        ok &= not miss
        print(f"  {name:<12} {nums}  {flag}")
        if not miss and pre.get(name) != nums:
            print(f"        ＋ 认领/编号变化：{pre.get(name)} ⇒ {nums}")
    if not ok:
        print("\n⛔ 自检没过 ⇒ 不写")
        return 1

    if not args.write:
        print("\n（`--check`：⛔ 未写任何文件）")
        return 0

    # ④ 备份 + 写回
    bk = REPO / ".workbuddy" / "backups" / f"交付面-{stamp}-TAIL168"
    bk.mkdir(parents=True, exist_ok=True)
    for name, (t, crlf) in out.items():
        shutil.copy2(MODDIR / name, bk / name)
        (MODDIR / name).write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
    print(f"\n✅ 已写回 {len(out)} 个件；改前备份 ⇒ {bk}")
    print("   ⚠️ 接着必跑：tools/probe/_audit_face.py（期望「必须修 0」）＋ doc_audit --ui（交付面四检）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
