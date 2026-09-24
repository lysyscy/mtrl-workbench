"""裁定出处哨 —— **凡写「用户裁定 / 拍板」，必须有①日期 ②出处**，核不到就标「待裁定」。

## 为什么要有它（2026-09-18 那次翻车）
给「删旧渲染层」排顺序时，我把 `mod03_notice/static/m03.html` 写进**「绝对不删」**，理由是
「**用户 2026-09-15 裁定 A** 保留不动」—— 用户当场对质「我什么时候裁定了 m03 保留不动」。
查证：那条「裁定 A」的**对象是"前端形态"**（别为它起 Vue3 工程），⛔ 不是"这个文件永远留"；
真正更晚的 `D18`（2026-09-17 用户拍板）恰恰写着「**旧服务端渲染层整体删除**」。
⇒ 一句**换了对象的概述**被当成硬约束，**替用户挡掉了本该他决定的事**。
（旁证：同一份记忆里还写着旧页「**未授权不动**」= 实现状态 —— 那**不是裁定**。）

## 两条规则（都只扫**活文档**：计划 + 执行情况；`归档-*.md` 是留痕，不扫）
| 规则 | 判什么 | 级别 |
|---|---|---|
| `C1` | 出现「用户裁定 / 拍板」的**同一行**里**没有日期**（`2026-09-15` / `9月15日` 之类） | ⛔ **红**（2026-09-24 起） |
| `C2` | 有日期但**没有出处**（如 `` `main.py:149` `` / `见 §19` / `memory` / 外部文档名） | ⛔ **红**（2026-09-24 起） |

⭐ **2026-09-24 用户裁定 `A`：上真出口**（原为"黄不判红"，`rc` 恒 0）—— 当天先把清单**清到 0**
（28 → 0：给每句补**可核的**日期与出处，⛔ 一处都没编），再收紧成红 ⇒ 这正是它当初自述的
「**等清单收敛了再收紧**」（与 `doc_audit` 的「疑似」同款节奏，只是这次真的走到了第二步）。
⚠️ **为什么当初是黄**（留痕，⛔ 别删）：本仓活文档里这类提法多、**历史提法**未必都带全 ⇒ 一上来判红会把整仓卡住。
⚠️ 显式写了「**待裁定**」的一律**放行**（那是诚实的写法：还没定就别当定论用）。
⭐ **它与 `shell_verify` 同族、形态不同**：`shell_verify` = **盖章式**（差异 ⇒ 红，`--snapshot` 盖章归零）；
本哨 = **清零式**（有黄 ⇒ 红，补日期/出处归零）。⛔ 两者**都不是**僵尸闸门。
⚠️ 本哨**只认字面**：它证明不了"你确实说过那句话"（那要人去核原话）—— 它只保证**每句都指得出日期与出处**，
   让人**两秒钟就能去核**。

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\audit\\claim_audit.py`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: 只扫**活文档**（⛔ 不扫 `归档-*.md`：那是历史留痕，按本仓"留疤不改"的规矩不动它）
DOCS = [
    ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md",
    ROOT / ".workbuddy" / "plans" / "执行情况-主文档.md",
]

#: 「这是一条裁定」的提法（含"裁定 A/B/C"这种代号）
CLAIM_RE = re.compile(r"用户(裁定|拍板)|裁定\s*[ABC]\b|已裁定|裁定过")

#: 日期（两种写法都认）
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\s*月\s*\d{1,2}\s*日|\d{1,2}\s*月")

#: 出处（指得出"去哪核"）：反引号里的 `文件:行` · `见 §x` · memory · 外部文档名
SRC_RE = re.compile(r"`[^`]*[:：]\s*\d+`|见\s*§|§\d|memory|\*\*§|`[^`]+\.md`")

#: 显式标了"还没定"的 ⇒ 放行
DEFER_RE = re.compile(r"待裁定|尚待裁定|未裁定")


def scan(path: Path) -> tuple[list[str], list[str]]:
    """→ `(缺日期的行, 缺出处的行)`；每条带 `行号: 摘录`。"""
    no_date: list[str] = []
    no_src: list[str] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not CLAIM_RE.search(line) or DEFER_RE.search(line):
            continue
        head = line.strip()[:110]
        where = f"{path.name}:{i}: {head}"
        if not DATE_RE.search(line):
            no_date.append(where)
        elif not SRC_RE.search(line):
            no_src.append(where)
    return no_date, no_src


def main(argv: list[str]) -> int:
    print("=" * 78)
    print(" 裁定出处哨 · claim_audit —— 「用户裁定 / 拍板」必须指得出日期与出处")
    print("=" * 78)
    print("\n扫描范围（活文档）：" + " · ".join(f"`{p.name}`" for p in DOCS))

    all_no_date: list[str] = []
    all_no_src: list[str] = []
    for p in DOCS:
        if not p.exists():
            print(f"\n⚠️ 找不到 {p}")
            continue
        nd, ns = scan(p)
        all_no_date += nd
        all_no_src += ns

    print("\n─ C1 · 有「用户裁定 / 拍板」但**同一行没有日期**")
    if all_no_date:
        print(f"   🟡 {len(all_no_date)} 处（⚠️ 补个日期，或改成「待裁定」）：")
        for x in all_no_date[:15]:
            print(f"     · {x}")
    else:
        print("   ✅ 无")

    print("\n─ C2 · 有日期但**没写出处**（指不出「去哪核原话」）")
    if all_no_src:
        print(f"   🟡 {len(all_no_src)} 处：")
        for x in all_no_src[:15]:
            print(f"     · {x}")
    else:
        print("   ✅ 无")

    n = len(all_no_date) + len(all_no_src)
    if n:
        print(f"\n⛔ 必须修 **{n}** 处（`C1` {len(all_no_date)} ＋ `C2` {len(all_no_src)}）⇒ **非零退出**")
        print("   两条出路（择一）：① 补**可核的**日期 ＋ 出处 —— 如 `（2026-09-24 用户裁定 · 见 §x.y）`")
        print("                      ② 若还没定 ⇒ 显式写 `待裁定`（那是诚实写法，本哨放行）")
        print("   ⚠️ 这是**提醒你把出处补齐**、不是故障 —— 但它是**真闸门**（2026-09-24 用户裁定 `A`）")
        return 1
    print("\n结论：**必须修 0**（`C1` 0 ＋ `C2` 0）✅")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
