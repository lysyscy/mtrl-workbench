"""`TAIL-193`（防扩散墓碑判据）**销号** ＋ 同批把交接材料里的条数改准。

五类手术（⛔ 每步断言「**恰好命中一次**」，任一处不满足 ⇒ **一个文件都不写**）：
  ① §一 A 类表：删掉 `TAIL-193` 那一整行（销号不释放编号 ⇒ ⛔ 别改成占位）；
  ② §四 已销号表：在表头下一行插入新行（⚠️ 该表**没有** `|---|` 分隔行）；
  ③ §14.3 排期行 ⇒ ✅（整行替换：按**行首前缀**定位 ⇒ 锚点里不含中文引号，免得引号形态不一致改不动）；
  ④ 两处计数行（§0 与 §15 顶部，写法略有不同）；
  ⑤ 交接材料两处条数：入门口令那行的「A 类 8 条」＋ 三处「`TAIL-193`–`195`」⇒ 改 `TAIL-194`–`195`。

⚠️ 行手术（①②）**排在任何字符串替换之前**。⚠️ 本文件是 **CRLF**（读 `newline=""`、写回 `\r\n`）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail193_close.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

A_ROW_PREFIX = "| `TAIL-193` | ⭐ **防扩散：给「唯一出口」挂墓碑判据**"
SEC4_HEAD = "| # | 事项 | 销号依据 | 日期 |"
SEC43_PREFIX = "| `TAIL-193` ⭐ **防扩散：给"          # ⚠️ 到此为止（后面是中文引号，不写进锚点）
NEXT_LINE_PREFIX = "  ⏭ **等用户点**（台账 §一 A 类"

COUNT_SEC0 = "A 类 **8** 条 · B 类 0 · C 类 **0** · 已销号 **190**"
COUNT_SEC15 = "A 类 **8** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **190** 条"

STALE_TAIL_RANGE = "`TAIL-193`–`195`"
FIXED_TAIL_RANGE = "`TAIL-194`–`195`"

SEC43_NEW = (
    "| `TAIL-193` ⭐ **防扩散：给「唯一出口」挂墓碑判据**（金额解析/格式化 · 项目归并/匹配 · 日期月份 · 仓库名校验） | "
    "✅ **已办（2026-09-29）** ⇒ 见 §15 §四 | "
    "**落点** = `backend/tests/test_dup_guards.py`（**登记册 = 唯一主人**）＋ `tools/oneoff/_tail193_measure.py`（对账 · 只读）"
    " ＋ `tools/mut/_mut_tail193.py`；⚠️ **存量一处未动**（各副本判定口径**刻意不同** ⇒ 拍平会改业务行为）；"
    "⚠️ 其中两族**当前没有唯一出口**（`金额·格式化` / `项目·匹配`）⇒ 将来真要收口就从它们开始 | "
    "触发 = `TAIL-192` 办完后用户「继续」 |"
)

SEC4_NEW = (
    "| `TAIL-193` | ⭐ **防扩散：给「唯一出口」挂墓碑判据**（**只防新增 · ⛔ 不动存量**）："
    "新建 `backend/tests/test_dup_guards.py` —— **5 族 · 22 处存量副本**逐条登记"
    "（`金额·解析/归一` 5 · `金额·格式化` 8 · `项目·匹配` 2 · `时间·年月` 4 · `文本归一` 3），"
    "每族写明**唯一出口**（⚠️ 其中 `金额·格式化` 与 `项目·匹配` **当前没有出口** ⇒ 登记册如实写「暂无」，⛔ 不编一个出来）；"
    "判据**两半**：多一处 ⇒ 红（别再写第 N+1 份）· **少一处也红**（那是好方向 ⇒ 销号那一行）；"
    "⭐ 反向灵敏度 `tools/mut/_mut_tail193.py` **5/5**（4 靶各插一份新实现 ⇒ 必红 ＋ ⭐ **第 5 靶在唯一出口 "
    "`core/money.py` 里插同名函数 ⇒ 必须仍绿**，证明 `owner_files` 不是哑的）；"
    "⚠️ **一处口径订正**：审计件 §三 `P1-5` 的计数（6 / 9 / 6 / 8+ / 4）是**更宽的正则**扫出来的，"
    "按**函数定义名**重测为 **5 / 8 / 2 / 4 / 3**；且它那句「**仓库名校验/排序 4 处**」实测**对不上** —— "
    "那一族的真身是 **4 个 `_norm`（文本归一）**（其中一个已是薄转发） | "
    "用户 2026-09-29「继续」（出处 = `.codebuddy/memory/2026-09-29.md` §㊾） | 2026-09-29 |"
)


def _once_text(text: str, needle: str, what: str, want: int = 1) -> None:
    n = text.count(needle)
    if n != want:
        raise SystemExit(f"⛔ {what}：期望命中 {want} 处，实测 {n} 处 ⇒ 停手（一个文件都不写）")


def build(raw: str) -> str:
    assert "\r\n" in raw, "本文件应当是 CRLF"
    lines = raw.split("\r\n")

    # ① 删 A 类那一行
    hit = [i for i, ln in enumerate(lines) if ln.startswith(A_ROW_PREFIX)]
    if len(hit) != 1:
        raise SystemExit(f"⛔ §一 A 类表里的 `TAIL-193` 行：期望 1 处，实测 {len(hit)} 处 ⇒ 停手")
    del lines[hit[0]]

    # ② §四 表头下一行插入
    hit = [i for i, ln in enumerate(lines) if ln.strip() == SEC4_HEAD]
    if len(hit) != 1:
        raise SystemExit(f"⛔ §四 表头：期望 1 处，实测 {len(hit)} 处 ⇒ 停手")
    lines.insert(hit[0] + 1, SEC4_NEW)

    text = "\r\n".join(lines)

    # ③ §14.3 整行替换
    _once_text(text, SEC43_PREFIX, "§14.3 的 `TAIL-193` 行前缀")
    old43 = next(ln for ln in text.split("\r\n") if ln.startswith(SEC43_PREFIX))
    text = text.replace(old43, SEC43_NEW, 1)

    # ④ 两处计数
    _once_text(text, COUNT_SEC0, "§0 的计数行")
    _once_text(text, COUNT_SEC15, "§15 顶部的计数行")
    text = text.replace(COUNT_SEC0, COUNT_SEC0.replace("**8**", "**7**").replace("**190**", "**191**"), 1)
    text = text.replace(COUNT_SEC15, COUNT_SEC15.replace("**8** 条", "**7** 条").replace("**190**", "**191**"), 1)

    # ⑤ 交接材料：入门口令条数 ＋ 三处尾巴区间
    lines = text.split("\r\n")
    hit = [i for i, ln in enumerate(lines) if ln.startswith(NEXT_LINE_PREFIX)]
    if len(hit) != 1:
        raise SystemExit(f"⛔ 入门口令「下一步」行：期望 1 处，实测 {len(hit)} 处 ⇒ 停手")
    lines[hit[0]] = (
        "  ⏭ **等用户点**（台账 §一 A 类 **7 条**，条数看 §15 顶部）—— `TAIL-192`/`TAIL-193` **已办**，"
        "别再按它们接续；台账原文见 §15 §一"
    )
    text = "\r\n".join(lines)

    _once_text(text, STALE_TAIL_RANGE, "交接材料里的「`TAIL-193`–`195`」", want=3)
    text = text.replace(STALE_TAIL_RANGE, FIXED_TAIL_RANGE)

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
