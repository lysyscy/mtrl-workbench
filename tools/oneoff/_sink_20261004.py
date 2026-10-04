"""批 1 清淤：把主文档 §13.6 里「**修订 8–23**」那批历史交接行**逐字下沉**到归档件。

**为什么是这批**：入门口令自己就写着「⛔ 别按 `-20261002-05` / `-20261002-03` / … 及更早的接续」——
那批**已经被它自己宣布作废**了，却还占着主文档 **17 行 × 平均 ~2000 字**（字墙最大的一处）。

口径：**逐字下沉、一行未改**（原处只留**一行**指针）；**干跑优先**；写盘前做 **round-trip 断言**
（搬走的原文必须**逐字**出现在归档件里）；写盘后再复核"原处已无、指针在"。

用法：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_sink_20261004.py          # 干跑
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_sink_20261004.py --apply  # 真写盘
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".codebuddy/plans/开发计划-主文档.md"
ARCH = ROOT / ".codebuddy/plans/archive/归档-交接区陈旧叙述-20261004.md"

START_MARK = "修订 8）"      # 第一行：`| ⭐ **2026-09-30 晚 · 增量（修订 8）** | …`
# ⚠️ 那批行的**编号不是顺序的**（实测：… 修订 19 / **23 / 22 / 21 / 20**）⇒ 端点只能按
#    「**最后一行**」标 —— 用「修订 23）」会**漏掉后面三行**（22/21/20 会留在原处 ⇒ 半搬 = 更乱）。
END_MARK = "修订 20）"       # 最后一行：`| ⭐⭐ **2026-10-02（之三）· 交接 `HANDOFF-20261002-03`（修订 20）** | …`

ARCH_HEAD = (
    "\n## 下沉于 2026-10-04（计划 §13.6 · 历史交接行 修订 8–23）\n"
    "\n> ⛔ **只留痕、别当现状读** —— **逐字搬来、一行未改**。\n"
    "> 当前交接材料 = 计划 §13.6 表里**最新那一行** ＋ 表下方的**入门口令**。\n"
    "\n"
)

POINTER = (
    "| 📦 **修订 8–23 的历史交接行**（2026-10-04 逐字下沉） | "
    "归档件 = `.codebuddy/plans/archive/归档-交接区陈旧叙述-20261004.md`"
    "（搜「**下沉于 2026-10-04（计划 §13.6 · 历史交接行 修订 8–23）**」）"
    "—— ⛔ **别按它们接续** |"
)


def _nl_of(lines: list[str]) -> str:
    for l in lines:
        if l.endswith("\r\n"):
            return "\r\n"
        if l.endswith("\n"):
            return "\n"
    return "\n"


def main(apply: bool) -> int:
    plan_txt = PLAN.read_bytes().decode("utf-8")
    lines = plan_txt.splitlines(keepends=True)

    i0 = next((i for i, l in enumerate(lines) if START_MARK in l), None)
    i1 = next((i for i, l in enumerate(lines) if END_MARK in l), None)
    if i0 is None or i1 is None or i0 > i1:
        print("⛔ 找不到起止行（段形态变了？）⇒ 未写盘")
        return 1

    block = lines[i0:i1 + 1]
    # ⚠️ 这批行里有**续行**（一行表格单元格里换过行 ⇒ 下一行不以 `|` 开头）⇒ 判据只能是：
    #    ① 整块**不许**出现标题行（`#`）—— 那说明起止标定错了、跨出了表格；
    #    ② 整块**不许**含「修订 24 / 修订 25」（那是**当前**那一批，⛔ 不能搬）。
    for k, l in enumerate(block):
        if l.lstrip().startswith("#"):
            print(f"⛔ 第 {i0 + k + 1} 行是标题（跨出表格了）：{l[:70]!r} ⇒ 未写盘")
            return 1
        if "修订 25" in l or "修订 24" in l:
            print(f"⛔ 第 {i0 + k + 1} 行是**当前**那一批（修订 24/25）⇒ 拒搬：{l[:70]!r}")
            return 1

    moved = "".join(block)
    print(f"① 起 L{i0 + 1} · 止 L{i1 + 1} · 共 {len(block)} 行 · {len(moved)} 字")
    print(f"② 原处将只留 1 行指针，主文档预计省 {len(block) - 1} 行")

    nl = _nl_of(lines)
    new_plan = "".join(lines[:i0]) + POINTER + nl + "".join(lines[i1 + 1:])

    arch_lines = ARCH.read_bytes().decode("utf-8").splitlines(keepends=True)
    arch_nl = _nl_of(arch_lines) if arch_lines else nl
    arch_new = "".join(arch_lines) + ARCH_HEAD.replace("\n", arch_nl) + moved

    # ⭐ round-trip 断言：搬走的原文必须**逐字**在归档新文本里
    if moved not in arch_new:
        print("⛔ round-trip 断言不过（归档件里找不到逐字原文）⇒ 未写盘")
        return 1

    if not apply:
        print("③ 干跑 —— ⛔ 未写盘（要写盘加 --apply）")
        print("   指针行预览：", POINTER[:110], "…")
        return 0

    PLAN.write_bytes(new_plan.encode("utf-8"))
    ARCH.write_bytes(arch_new.encode("utf-8"))

    after = PLAN.read_text(encoding="utf-8")
    if moved in after:
        print("⛔ 复核不过：下沉后原处**仍在**")
        return 1
    if POINTER[:24] not in after:
        print("⛔ 复核不过：指针没写进去")
        return 1
    print(f"✅ 已写盘：主文档 {len(lines)} → {len(new_plan.splitlines())} 行；归档件已追加逐字原文")
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))
