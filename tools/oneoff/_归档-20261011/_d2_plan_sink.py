"""文档审计 2026-09-29 队列 · 第 2 条**能真正做到的那半**：§13.6 那三面「墙」→ 截短 ＋ 全文下沉。

## ⚠️ 为什么不是原推荐（"把过程叙事搬走 ⇒ 行数降下来"）

推荐时我的假设是：**§13.6 的过程叙事撑高了行数**。一量就否了 ——
那三处叙事各是 **一整行**（`len(splitlines())` 各算 **1 行**）：`状态` 行 ~2.4k 字、
`核验续记` 行 ~3.6k 字、`入门口令` 里那句 `已确认的下一步` ~4.4k 字 ⇒ **加起来 3 行**，而计划超预算是 **8 行** ✗。
⭐ 且 §15 §四 的销号行**一行都不能搬**（`T6` 要求编号 `1..N` 全在表内、销号不释放编号）
⇒ **"搬走叙事 ⇒ 省行"这条路在本仓不存在**（台账按设计每条一行；叙事是单行、压不出行来）。
⚠️ 而"删空行凑够 8 行"是**合规表演**（不减少阅读负担、只在糊弄尺子）⇒ ⛔ 我不做。

## 那本脚本做什么

**做真正对症的那件**：那三行不是"行数"问题，是**可读性**问题 —— 接手的人要在一行里**穿过上万字**，
`grep` 也难用（整行命中、无法定位）。本仓对这件事的既有机制就是**「原处只留截短版 ＋ 全文下沉归档」**
（09-23 那次 §15 台账过程散文、09-27/09-29 两次交接材料，都是这么办的）。
⇒ 三行**逐字**进 `归档-历史单元条目.md`（新增一节，append-only），原处换成**截短版 ＋ 可搜到的指针**。

⚠️ 截短时守三条：① **不复述**四态数字 / 计数（本仓口径：进度只认 §0 ＋ 四态 ＋ §15 ＋ 简略版）——
少一处副本 = 少一处会漂的地方；② 凡留了「用户裁定」字样 ⇒ 同句必须留**出处**（`claim_audit` 的 `C1`/`C2`）；
③ ⛔ 一行都不删 —— 原文照进归档。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_d2_plan_sink.py --check` / `--write`
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
ARCH = ROOT / ".workbuddy" / "plans" / "归档-历史单元条目.md"
STAMP = "下沉于 2026-09-29（计划 §13.6 · 状态行 / 核验续记 / 已确认的下一步 —— 三行全文）"

#: (标签, 行首标记, 截短版)  —— ⚠️ 标记取**唯一前缀**，不靠行号（行号会漂）
TARGETS: list[tuple[str, str, str]] = [
    ("状态行",
     "| **状态** | ⭐ 前端系统性重构**已收官**",
     "| **状态** | ⭐ **前端逐页推进计划 `A1`–`A11` 已整表走完**（`m05`→`m03`→`m04`→`m06`→`m07`→`m01`·`m02`→`m11`→`imp`→"
     "`m08`·`m09`·`m10`→`m13`·`m14`·`set`·`m15`→`home`，**16 屏全覆盖**）；⏭ **下一步等用户点**（台账 §一 还剩 A 类长线，"
     "条数看 §15 顶部计数）｜⚠️ 用户对看板口径 =「**不加东西**」，等他点 ｜⛔ **本行不复述逐批过程** —— "
     "逐批的收口内容（判据号 / 反向灵敏度 / 盖章 / 量测数字）已**逐字下沉** `.workbuddy/plans/归档-历史单元条目.md`"
     "（搜「**" + STAMP + "**」）|"),
    ("核验续记",
     "| **交接状态 / 接手核验续记** |",
     "| **交接状态 / 接手核验续记** | ⭐ **材料已核对 · 待接手核验**（源任务编号与接手任务编号：本宿主未提供 ⇒ 走手动入口）"
     "｜⛔ **本行不复述逐批核验** —— 接手核验续记（含四态涨数、各处盖章、当场查出的口径漂移与修法）已**逐字下沉**"
     "`归档-历史单元条目.md`（搜「**" + STAMP + "**」）｜⭐ 现况**只认四处**：§0 现状快照 ＋ 四态报表 ＋ §15 台账 ＋ 简略版 |"),
    ("已确认的下一步",
     "已确认的下一步（用户 2026-09-29 回「A，然后继续」）",
     "已确认的下一步：⭐ **逐页推进计划 `A1`–`A11` 已整表走完** ⇒ ⏭ **等用户点**（台账 §一 剩 A 类长线，"
     "条数看 §15 顶部计数）｜⛔ **本行不复述逐批过程** —— 各批的收口内容（`TAIL-169`–`TAIL-187` 的判据 / "
     "反向灵敏度 / 量测数字 / 放过理由）已**逐字下沉** `归档-历史单元条目.md`（搜「**" + STAMP + "**」）"),
]


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", newline="")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    apply = a.write and not a.check

    raw = read(PLAN)
    eol = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.splitlines(keepends=False)
    print(f"计划：{len(lines)} 行 · {eol.replace(chr(13),'CR').replace(chr(10),'LF')}")

    if STAMP in read(ARCH):
        print("⏭ 归档里已有本节 ⇒ 视为已做过，停手（幂等）")
        return 0

    picked: list[tuple[str, str, int, str]] = []
    for label, marker, short in TARGETS:
        idx = [i for i, l in enumerate(lines) if l.startswith(marker)]
        if len(idx) != 1:
            print(f"   ⛔ `{label}`：按标记 `{marker[:28]}…` 命中 **{len(idx)}** 行（要 1）⇒ 停手，别猜")
            return 2
        i = idx[0]
        picked.append((label, marker, i, short))
        print(f"   ✓ {label}：第 {i + 1} 行 · {len(lines[i])} 字 ⇒ 截短为 {len(short)} 字")

    if not apply:
        print("\n🧪 --check（干跑）：会把上面三行**逐字**追加进归档（新增一节）＋ 原处换截短版")
        return 0

    # ① 全文进归档（append-only）
    body = "".join(f"{lbl}原行（逐字 · {len(lines[i])} 字）：\n{lines[i]}\n\n" for lbl, _, i, _ in picked)
    arch = read(ARCH).rstrip("\r\n")
    arch += (eol + eol + f"## {STAMP}" + eol + eol
             + "> 依据：文档审计 2026-09-29 队列第 2 条 —— **原处只留截短版 ＋ 指针**（本仓既有机制；"
               "09-23 §15 台账过程散文、09-27/09-29 两次交接材料同办）。" + eol
             + "> ⚠️ 为什么不「搬走叙事省行数」：那三行各是**一整行**（共 3 行），而计划超预算是 8 行；"
               "且 §15 §四 销号行受 `T6` 保护（编号 `1..N` 全在表内）**一行都不能搬** ⇒ 详见脚本头注。" + eol + eol
             + body)
    ARCH.write_text(arch, encoding="utf-8", newline="")

    # ② 原处换截短版（⛔ 单行替换，行数不变）
    for _, _, i, short in picked:
        lines[i] = short
    PLAN.write_text(eol.join(lines) + eol, encoding="utf-8", newline="")
    print(f"\n🔧 已落盘：归档 +{len(body.splitlines())} 行 · 计划仍 **{len(lines)} 行**（截短不省行、只省阅读）")
    print("   下一步：`doc_audit`/`audit_meta`/`audit_drift`/`claim_audit` 必须修 0 ＋ 人工看一眼 §13.6 还读得通")
    return 0


if __name__ == "__main__":
    sys.exit(main())
