"""`TAIL-192` 办完之后，**把交接材料里"待你点"的四处说法改准**（`HANDOFF-20260929-01` · 修订 3 原地增量更新）。

⚠️ 为什么必须同批改（不是顺手）：§13.6 是**当前状态表**（本表自己的规矩：接手后**在行内增量更新**）——
不改 ⇒ 下次会话（或用户照入门口令粘贴）会**再把 `TAIL-192` 做一遍**、并按错的条数（A 类 9 条）判断剩多少。

四处：
  ① 入门口令的「已确认限制 ④」整行（原写"尚未获批 —— 别当成已授权"）；
  ② 入门口令的「已确认的下一步」整行（原写"A 类 **9 条**"＋"可先做 `TAIL-192`"）；
  ③ §13.6 状态行里那句「四尾 `TAIL-192`–`195` **待做**」；
  ④ 「接续动作」那一格里的 `C. 没说话 ⇒ 先做 TAIL-192`（整格改写）。

⚠️ 格子边界用 **`" |"`**（表行里唯一的界符）；⚠️ 锚点里**不含中文引号**（避免引号形态不一致改不动）。
⚠️ 锚点必须**恰好命中一次**（⛔ 不合格就一个文件都不写）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail192_handoff.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

SRC = "（出处 = `.codebuddy/memory/2026-09-29.md`）"

#: ① 入门口令 · 已确认限制 ④（整行替换；按**行首子串**定位）
LIMIT_LINE_PREFIX = "  ④ ⚠️ 结构审计 P0 四件（`TAIL-192`）"
LIMIT_LINE_NEW = (
    "  ④ ✅ 结构审计 P0 四件（`TAIL-192`）**已办并销号** —— 明细见 §15 §四；"
    f"⚠️ 同族剩下的 `TAIL-193`–`195` 仍待用户点 {SRC}"
)

#: ② 入门口令 · 已确认的下一步（整行替换）
NEXT_LINE_PREFIX = "  ⏭ **等用户点**（台账 §一 A 类"
NEXT_LINE_NEW = (
    "  ⏭ **等用户点**（台账 §一 A 类 **8 条**，条数看 §15 顶部）—— `TAIL-192`（结构审计 P0 四件）**已办**，"
    "别再按它接续；台账原文见 §15 §一"
)

#: ③ 状态行里那句过期的尾巴数（子串替换）
STALE_TAILS = "四尾 `TAIL-192`–`195` **待做**"
FIXED_TAILS = (
    "`TAIL-192` **已办并销号**（2026-09-29 " + SRC + "）· 其余 `TAIL-193`–`195` **待做**"
)

#: ④ 「接续动作」那一格里 `C. 没说话` 那半句（**整格改写**：从锚点到该格结尾 `" |"`）
C_ANCHOR = "**C. 没说话** ⇒"
C_NEW = (
    "**C. 没说话** ⇒ ⭐ **先问用户下一步**（`TAIL-192` **已办并销号** ⇒ 见 §15 §四；"
    "台账 §一 还剩 `TAIL-193`–`195` ＋ `TAIL-188`/`TAIL-06`/`TAIL-21`/`TAIL-59`/`TAIL-64`）。"
    "⛔ 旧的两张批次表（文档审计 / 逐页推进）**都已作废**、别再摆"
)


def _once(text: str, needle: str, what: str) -> int:
    n = text.count(needle)
    if n != 1:
        raise SystemExit(f"⛔ {what}：期望恰好命中 1 处，实测 {n} 处 ⇒ 停手（一个文件都不写）")
    return text.index(needle)


def build(raw: str) -> str:
    assert "\r\n" in raw, "本文件应当是 CRLF"
    text = raw

    # ① / ②：整行替换（行首子串定位 ⇒ ⛔ 不受引号形态影响）
    for prefix, new, what in (
        (LIMIT_LINE_PREFIX, LIMIT_LINE_NEW, "入门口令 · 已确认限制 ④"),
        (NEXT_LINE_PREFIX, NEXT_LINE_NEW, "入门口令 · 已确认的下一步"),
    ):
        lines = text.split("\r\n")
        hit = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
        if len(hit) != 1:
            raise SystemExit(f"⛔ {what}：期望恰好命中 1 行，实测 {len(hit)} 行 ⇒ 停手")
        lines[hit[0]] = new
        text = "\r\n".join(lines)

    # ③：状态行里的尾巴数（子串）
    _once(text, STALE_TAILS, "§13.6 状态行 · 尾巴数")
    text = text.replace(STALE_TAILS, FIXED_TAILS, 1)

    # ④：「接续动作」格里 C 那半句 ⇒ 整格改写（界符 = `" |"`）
    i = _once(text, C_ANCHOR, "§13.6 接续动作 · `C. 没说话`")
    end = text.index(" |", i)
    text = text[:i] + C_NEW + text[end:]

    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="真写（默认只干跑）")
    ap.add_argument("--check", action="store_true", help="显式的干跑（本仓惯例）")
    args = ap.parse_args()

    raw = PLAN.read_text(encoding="utf-8", newline="")
    new = build(raw)
    print(f"字节：{len(raw.encode('utf-8'))} → {len(new.encode('utf-8'))}"
          f" · 行数 {len(raw.splitlines())} → {len(new.splitlines())}")
    print("四处锚点均已按「恰好一次」校验 ✓")
    if not args.write:
        print("\n（--check 干跑结束；加 --write 才落盘）")
        return 0
    PLAN.write_text(new, encoding="utf-8", newline="")
    print("\n✅ 已写回 .workbuddy/plans/开发计划-主文档.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
