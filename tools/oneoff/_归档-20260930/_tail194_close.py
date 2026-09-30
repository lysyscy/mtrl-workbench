"""`TAIL-194`（`tools/oneoff/` 的保留口径 ＋ 机器眼）**销号** ＋ 同批把交接材料里的条数改准。

五类手术（⛔ 每步断言「**恰好命中一次**」，任一处不满足 ⇒ **一个文件都不写**）：
  ① §一 A 类表：删掉 `TAIL-194` 那一整行；
  ② §四 已销号表：表头下一行插入新行（⚠️ 该表**没有** `|---|` 分隔行）；
  ③ §14.3 排期行 ⇒ ✅（按**行首前缀**定位 ⇒ 锚点里不含中文引号）；
  ④ 两处计数行（§0 与 §15 顶部，写法略有不同）；
  ⑤ 交接材料：入门口令那行的条数（7 → 6）＋ 三处「`TAIL-194`–`195`」⇒ `TAIL-195`。

⚠️ 行手术（①②）排在字符串替换之前。⚠️ 本文件是 **CRLF**。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail194_close.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

A_ROW_PREFIX = "| `TAIL-194` | ⭐ **`tools/oneoff/` 的保留口径 ＋ 机器眼**"
SEC4_HEAD = "| # | 事项 | 销号依据 | 日期 |"
SEC43_PREFIX = "| `TAIL-194` ⭐ **`tools/oneoff/` 的保留口径 ＋ 机器眼**"
NEXT_LINE_PREFIX = "  ⏭ **等用户点**（台账 §一 A 类"

COUNT_SEC0 = "A 类 **7** 条 · B 类 0 · C 类 **0** · 已销号 **191**"
COUNT_SEC15 = "A 类 **7** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **191** 条"

STALE_RANGE = "`TAIL-194`–`195`"
FIXED_RANGE = "`TAIL-195`"

SEC43_NEW = (
    "| `TAIL-194` ⭐ **`tools/oneoff/` 的保留口径 ＋ 机器眼**（169 件 · 1195 KB） | "
    "✅ **已办（2026-09-29）** ⇒ 见 §15 §四 | "
    "**落点** = `tools/README.md` 文末「`oneoff/` 的保留与处置口径」那一段（**唯一主人**：三类件分开处置）"
    " ＋ **机器眼** = `T20` 扩到本目录（`tools/audit/audit_work.py` 的 `ONEOFF_MAX_FILES` / `ONEOFF_MAX_MB`，"
    "阈值登记在 `ops/阈值表.md`）＋ **只读量测件** `tools/oneoff/_oneoff_measure.py`（件数 / 容量 / 被引用 / 零引用）；"
    "⭐ 顺手订正一处**假阴性**：量测语料原只取**跟踪件**，而 `.codebuddy/memory/` **不入 git** 却引用了一批 oneoff 件"
    " ⇒ 会把「其实有出处」的判成零引用（重测：102 被引用 / 73 零引用，而非 60 / 118） | "
    "触发 = `TAIL-193` 办完后用户「按推荐继续」 |"
)

SEC4_NEW = (
    "| `TAIL-194` | ⭐ **`tools/oneoff/` 的保留口径 ＋ 机器眼**（它是全仓**唯一「没有保留期、也没有机器眼」**的目录）："
    "① `tools/README.md` 立**处置口径** —— 三类件分开：**常驻小工具**（`_run_rulers.py` / `_ps_*.ps1` / "
    "`_list_tails.py` / `_page_measure.py` / `_prepush_sensitive.py` / `_oneoff_measure.py`）⛔ 长期保留；"
    "**被引用的留痕件**（台账 / 设计件 / 判据 / 记忆提到文件名）⛔ 长期保留（删了就断链：`T3` / `_links`）；"
    "**零引用的** ＝ 候选 ⇒ **移进** `tools/oneoff/_归档-YYYYMMDD/`（可逆、⛔ 不盲删）；"
    "② **机器眼** = `T20` 扩到本目录（件数 200 / 容量 5 MB ⇒ 黄一行），阈值登记 `ops/阈值表.md`，"
    "自证 `tools/mut/_mut_t20.py` 的 `M3`；③ 新增**只读**量测件 `tools/oneoff/_oneoff_measure.py`。"
    "⭐ **实测（2026-09-29）**：**175 件（跟踪）· 1231 KB · 102 被引用 / 73 零引用**（⚠️ 首测**假阴性**："
    "语料只取跟踪件、漏了**不入 git** 的 `.codebuddy/memory/` ⇒ 报 60 / 118 ⇒ 已修并重测）；"
    "⭐⭐ **同批挖出 `_mut_t20.py` 的 ① 靶早就哑了**：它比「**命中条数**是否上升」，而该处**基线本就超线**时"
    "超线只报**一行**（`7 → 8` 个条目仍是 1 行）⇒ 变异「没抓到」是**假红**（当时 `backups/` 顶层 7 > 5，"
    "当场暴露）⇒ 判法改成**读报告里那个数**是否变大（`7→9` / `None→12` / `None→177`）；"
    "⚠️ **本轮未动 `backups/` 那 7 项**（属 `T20` 的**另一处**黄 ⇒ 移 / 清要用户点头） | "
    "用户 2026-09-29「按推荐继续」（出处 = `.codebuddy/memory/2026-09-29.md`） | 2026-09-29 |"
)


def _once_text(text: str, needle: str, what: str, want: int = 1) -> None:
    n = text.count(needle)
    if n != want:
        raise SystemExit(f"⛔ {what}：期望命中 {want} 处，实测 {n} 处 ⇒ 停手（一个文件都不写）")


def build(raw: str) -> str:
    assert "\r\n" in raw, "本文件应当是 CRLF"
    lines = raw.split("\r\n")

    hit = [i for i, ln in enumerate(lines) if ln.startswith(A_ROW_PREFIX)]
    if len(hit) != 1:
        raise SystemExit(f"⛔ §一 A 类表里的 `TAIL-194` 行：期望 1 处，实测 {len(hit)} 处 ⇒ 停手")
    del lines[hit[0]]

    hit = [i for i, ln in enumerate(lines) if ln.strip() == SEC4_HEAD]
    if len(hit) != 1:
        raise SystemExit(f"⛔ §四 表头：期望 1 处，实测 {len(hit)} 处 ⇒ 停手")
    lines.insert(hit[0] + 1, SEC4_NEW)
    text = "\r\n".join(lines)

    _once_text(text, SEC43_PREFIX, "§14.3 的 `TAIL-194` 行前缀")
    old43 = next(ln for ln in text.split("\r\n") if ln.startswith(SEC43_PREFIX))
    text = text.replace(old43, SEC43_NEW, 1)

    _once_text(text, COUNT_SEC0, "§0 的计数行")
    _once_text(text, COUNT_SEC15, "§15 顶部的计数行")
    text = text.replace(COUNT_SEC0, COUNT_SEC0.replace("**7**", "**6**").replace("**191**", "**192**"), 1)
    text = text.replace(COUNT_SEC15, COUNT_SEC15.replace("**7** 条", "**6** 条").replace("**191**", "**192**"), 1)

    lines = text.split("\r\n")
    hit = [i for i, ln in enumerate(lines) if ln.startswith(NEXT_LINE_PREFIX)]
    if len(hit) != 1:
        raise SystemExit(f"⛔ 入门口令「下一步」行：期望 1 处，实测 {len(hit)} 处 ⇒ 停手")
    lines[hit[0]] = (
        "  ⏭ **等用户点**（台账 §一 A 类 **6 条**，条数看 §15 顶部）—— "
        "`TAIL-192`/`TAIL-193`/`TAIL-194` **已办**，别再按它们接续；台账原文见 §15 §一"
    )
    text = "\r\n".join(lines)

    _once_text(text, STALE_RANGE, "交接材料里的「`TAIL-194`–`195`」", want=3)
    text = text.replace(STALE_RANGE, FIXED_RANGE)

    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="真写（默认只干跑）")
    ap.add_argument("--check", action="store_true", help="显式的干跑（本仓惯例）")
    args = ap.parse_args()

    raw = PLAN.read_text(encoding="utf-8", newline="")
    new = build(raw)
    before, after = raw.split("\r\n"), new.split("\r\n")
    print(f"行数：{len(before)} → {len(after)}（期望**相等**：删 1 ＋ 插 1）")
    print(f"字节：{len(raw.encode('utf-8'))} → {len(new.encode('utf-8'))}")
    print("五类手术均已按「恰好命中一次」校验 ✓")
    if not args.write:
        print("\n（--check 干跑结束；加 --write 才落盘）")
        return 0
    PLAN.write_text(new, encoding="utf-8", newline="")
    print("\n✅ 已写回 .workbuddy/plans/开发计划-主文档.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
