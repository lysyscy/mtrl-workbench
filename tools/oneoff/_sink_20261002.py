"""一次性：把计划 `§13.6` 入门口令里那块**前几轮的「下一步」留痕**逐字下沉到归档件。

**为什么**（`HANDOFF-20261002-03`）：计划 **1799 / 1800 行** —— 只剩 1 行余量，
下一轮写 `TAIL-218` 台账必撞 `T10` 读预算 ⇒ 先按用户 2026-09-20 的口径
（「主文档只留法规＋现状＋排期＋台账，做完的过程**逐字下沉**」）把这块搬走。

做法（⛔ 逐字，不是重写）：**按行边界**整块剪切 ⇒ **原样追加**到
`.codebuddy/plans/archive/归档-历史单元条目.md` 的新一节 ⇒ 计划原处只留 3 行指针。

⚠️⚠️ **按字节读写、原样保留换行符** —— ⛔ 别用 `read_text`（它做 universal-newline 转换，
   会把整份文件的 CRLF 悄悄改成 LF ⇒ **假差异**，本仓踩过）。
两条断言：① 块首/块尾各命中 1 次；② 下沉后**块原文逐字节出现在归档件里**（round-trip）。

用法：`python tools/oneoff/_sink_20261002.py`（**干跑**）· 加 `--apply` 才写盘。
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".codebuddy" / "plans" / "开发计划-主文档.md"
ARCHIVE = ROOT / ".codebuddy" / "plans" / "archive" / "归档-历史单元条目.md"

HEAD = "⛔ **以下为前几轮的「下一步」留痕**"
TAIL = "  ⚠️ **硬约束**：批次必须**赶在产包（去办公室前一天）之前收口**"
SECTION = "## 下沉于 2026-10-02（计划 §13.6 入门口令 · 前几轮的「下一步」块）"

POINTER = [
    "⛔ **前几轮的「下一步」块（`TAIL-209`–`214` 那段逐批实况）已逐字下沉** ⇒",
    "`.codebuddy/plans/archive/归档-历史单元条目.md`（搜「**下沉于 2026-10-02（计划 §13.6 入门口令 · 前几轮的「下一步」块）**」）。",
    "⭐ **当前那份「下一步」在上面**（`TAIL-218` 批 2）—— ⛔ 别照下沉的那块开工。",
]


def _read_raw(p: pathlib.Path) -> tuple[str, str]:
    """→ `(文本, 换行符)` —— 按字节读，**不做换行转换**。"""
    raw = p.read_bytes()
    text = raw.decode("utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    return text, nl


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真写盘（默认只干跑）")
    args = ap.parse_args()

    plan, plan_nl = _read_raw(PLAN)
    arch, arch_nl = _read_raw(ARCHIVE)
    print(f"换行符：计划 = {plan_nl!r} · 归档 = {arch_nl!r}")

    lines = plan.split(plan_nl)
    heads = [i for i, l in enumerate(lines) if l.startswith(HEAD)]
    tails = [i for i, l in enumerate(lines) if l.startswith(TAIL)]
    assert len(heads) == 1, f"块首命中 {len(heads)} 次（期望 1）⇒ 位置变了，停手"
    assert len(tails) == 1, f"块尾命中 {len(tails)} 次（期望 1）⇒ 位置变了，停手"
    a, b = heads[0], tails[0]
    assert a < b, "块首在块尾之后 —— 停手"
    block = lines[a:b + 1]
    block_text = plan_nl.join(block)
    print(f"块 = 第 {a+1}~{b+1} 行（{len(block)} 行 · {len(block_text.encode('utf-8'))} 字节）")
    print("块首：", block[0][:70])
    print("块尾：", block[-1][:70])

    new_lines = lines[:a] + POINTER + lines[b + 1:]
    new_plan = plan_nl.join(new_lines)
    print(f"\n计划：{len(lines)} 行 ⇒ {len(new_lines)} 行（预算 1800 ⇒ 余 {1800 - len(new_lines)}）")

    assert SECTION not in arch, "归档件里已经有这一节了 ⇒ 别搬第二次"
    add = (f"{arch_nl}{arch_nl}---{arch_nl}{arch_nl}{SECTION}{arch_nl}{arch_nl}"
           f"> 原处 = 计划 `§13.6` 的「入门口令（可复制）」块内。**逐字搬，一行未改**"
           f"（`tools/oneoff/_sink_20261002.py`）。{arch_nl}{arch_nl}"
           + block_text + arch_nl)
    new_arch = arch.rstrip(arch_nl) + arch_nl + add

    assert block_text in new_arch, "round-trip 失败：块原文没逐字进归档件"
    print(f"归档：{len(arch.split(arch_nl))} 行 ⇒ {len(new_arch.split(arch_nl))} 行")

    if not args.apply:
        print("\n（干跑 —— ⛔ 没写盘。确认无误后加 `--apply`）")
        return 0
    PLAN.write_bytes(new_plan.encode("utf-8"))
    ARCHIVE.write_bytes(new_arch.encode("utf-8"))
    print("\n✅ 已写盘（按字节写，换行符未变）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
