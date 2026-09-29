#!/usr/bin/env python
"""`A5`（`m07`）留痕：`TAIL-174` **销号** ＋ `TAIL-175` **建尾巴** ＋ 计数（2026-09-29）。

盘账规矩（`TAIL-168` 那轮的教训）：**销号 = 三处一起动**（§三 移出 · §四 补行 · 计数改）；
新建尾巴 = **两处**（§三 挂出来 ＋ §14.3 给排期）。
⚠️ 这些行都很长 ⇒ 一律**脚本读盘 → 按前缀定位 → 改 → 写回 → 再读盘校验**（⛔ 不手抄、不混用编辑器）。

用法：`… _tally_a5.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"

C_HDR = "| # | 事项 | 现状 | 你只需说 | 阶段 / 时机 | 状态 |"
L_HDR = "| # | 事项 | 销号依据 | 日期 |"
A173_S = "| `TAIL-173` ⭐ "

SCHED_NEW = (
    "| `TAIL-174` ⭐ **`A5` `m07` 逐页收口**（大表 0 行必须给空态 · 见 §四） | ✅ **已做（2026-09-29 · 留痕，别删）** |"
    " 逐页推进**第 5 页**。**量测先行**：`V.m07` 119 行 · 9 动作 · 3 张表（收发结存 7 列 / 提取 5 列 / **大表 20 列两行表头**）·"
    " 收发结存与提取两族**本就有空态**、判据也齐 ⇒ 本批只留 1 条真缺陷：**大表 0 行时只剩三级表头**（含「后端备好却没人调用」的死代码那半） |"
    " ⛔ 其余逐条对守则后放过并写明理由：结余格的 0 与未录入分得开（`EXT_BAL_NOTE` ＋ `placeholder`）· 主材累计不可得给「—」不写 0 ·"
    " 提取表刻意不可排（有判据）· 大表手填不参与欠款（有判据）| 用户 2026-09-29「A，然后继续」 |"
)
SCHED_NEW2 = (
    "| `TAIL-175` ⭐ **大表（20 列横表）没有固定列**（`A5` 顺手查出 · 属**用户可见的设计变化** ⇒ 没擅自改） | ⏳ **待你一句话**（`C` 类 · 见 §三） |"
    " 大表横向宽度 `min-width:1620px`（20 列 / 三级表头）；**首列（序号 / 项目名称）不固定** ⇒ 用户往右填「机械费测算 / 合同价 / 产值累计」时"
    " **看不见自己在给哪个项目填**（手填 6 列正好落在最右边几列）⇒ 会填错行。⚠️ 本仓既有做法见 `m06` 表①② 与 `m07` 收发结存："
    "**首列 `.fl`（sticky-left）表头与数据行一起钉**（`TAIL-170`-③ 那轮统一过 3 张勾选表）—— 大表当年**没做**（两行表头下 sticky 要另算 top 偏移，不是一行代码的事） |"
    " ⭐ 只等你一句话；⚠️ 真做要**先量真机**（横滚时两行表头 + 合计行会不会错位） |"
)
C_NEW = (
    "| `TAIL-175` | ⭐ **大表（月度会大表）没有固定列**（20 列横表 · 往右填就看不见项目名） | 大表 `min-width:1620px`、**首列不固定** ⇒"
    " 手填 6 列（开工时间…备注）正好在最右 ⇒ 用户**不知道自己填的是哪个项目**（会填错行）。⚠️ 房内既有做法 = 首列 `.fl` 让**表头与数据行一起钉**"
    " （`m06`/`m07` 收发结存都已这样；`TAIL-170`-③ 统一过 3 张勾选表）—— 大表当年没做 |"
    " 回一句：**`A`** 给大表首列加固定（我先真机量两行表头 + 合计行的错位风险，再动手）／ **`B`** 不动（保持现状）／ **`C`** 改成别的形式（你说） |"
    " 随时（等你一句话） | ⏳ **待你裁定** |"
)
L_NEW = (
    "| `TAIL-174` | 🧾 **大表 0 行时必须给空态**（`A5` 逐页 · ⛔ 未改任何口径）：月度会大表原先 0 行时 `return ''` ⇒ 用户看到一张"
    " **只剩三级表头的大空表**（20 列横表、没有「为什么空 / 下一步」）—— 与 `m04`（`A3`）/`m06` 同族，本批第 3 例。"
    "⇒ 接上**后端早就备好、却全仓没人调用**的那句（`big_domain.empty_text`，随 `/api/m07/big` 的 `empty_text` 给；⛔ 壳里不编第二份）"
    "＋ 同批把它的措辞**改准**（原文「还没勾项目 —— 点上方「选题」挑几个」与口径「**未选题 = 取全部候选**」打架 ⇒ 会把人指去点一个点了也不变的地方）；"
    "⚠️ 跨列数走 **`thCols`**（大表是**两行**表头：`<th>` 23 / 实列 20 ⇒ `thCount` 会多算 3 列） | 判据 = 新判据 1 条"
    "（`ACC-RPT-BIG-001/001-20`，含后端那半边：文案调 `big_domain.empty_text` **看返回值**判，⛔ 不抠源码——文件里那段注释**引述**了旧写法作留痕）"
    "＋ 全套 pytest **100%** ＋ 四态 **631 → 632** ＋ 12 把尺子 rc=0 ＋ `doc_audit --ui` 必须修 0 ＋ **后端重启**（`/app` = 200）"
    "＋ **盖章** `20260929-0954` ＋ ⭐ **真机一次性验证** `tools/oneoff/_a5_m07_empty.py`（`thCols(BIG_THEAD)` = **20** · `thCount` = 23 ·"
    " `BIG_EMPTY` 拿到了后端那句 · 空态行 `colspan=\"20\"` 能画出来）＋ `_shell_smoke` rc=0（㉛ 全 ✅ · 无 console 错误）；"
    "**改前已备份交付面** ⇒ `.workbuddy/backups/交付面-20260929-1000-A5/`；脚本 = `_doc_a5_m07.py` | 2026-09-29 |"
)
COUNTS = (("C 类 **0** · 已销号 **171**", "C 类 **1** · 已销号 **172**"),
          ("C 类 **0** 条 · 已销号 **171** 条", "C 类 **1** 条 · 已销号 **172** 条"))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = PLAN.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    t = raw.replace("\r\n", "\n") if nl == "\r\n" else raw
    L = t.split("\n")

    c = [i for i, l in enumerate(L) if l.strip() == C_HDR]
    s = [i for i, l in enumerate(L) if l.startswith(A173_S)]
    h = [i for i, l in enumerate(L) if l.strip() == L_HDR]
    assert len(c) == 1, f"§三 表头命中 {len(c)}（期望 1）"
    assert len(s) == 1, f"§14.3 的 TAIL-173 行命中 {len(s)}（期望 1）"
    assert len(h) == 1, f"§四 表头命中 {len(h)}（期望 1）"
    # ⚠️ 只有 §三 有分隔行；§四 那张表**没有**（表头后直接是台账行）⇒ 别一刀切断言
    assert L[c[0] + 1].startswith("|---"), "§三 表头下一行不是分隔行 ⇒ ⛔ 别插错位置"

    # ① §三：挂 `TAIL-175`（表头 → 分隔行 → 数据行）
    L.insert(c[0] + 2, C_NEW)
    off = 1
    # ② §14.3：`TAIL-174` ✅ ＋ `TAIL-175` ⏳（插在 TAIL-173 那行之后）
    si = s[0] + off
    L.insert(si + 1, SCHED_NEW)
    L.insert(si + 2, SCHED_NEW2)
    off += 2
    # ③ §四：`TAIL-174` 销号行（表头 → 数据行；这张表**没有**分隔行）
    hi = h[0] + off
    hi += 1 if L[hi + 1].startswith("|---") else 0
    L.insert(hi + 1, L_NEW)
    out = "\n".join(L)
    for old, new in COUNTS:                      # ④ 计数两处
        n = out.count(old)
        assert n == 1, f"计数片段命中 {n} 次（期望 1）：{old!r}"
        out = out.replace(old, new, 1)
    print(f"§三 ＋1（`TAIL-175`）· §14.3 ＋2 · §四 ＋1（`TAIL-174`）· 计数 2 处 ⇒ {len(L)} 行（原 {len(t.splitlines())}）")

    if args.write:
        PLAN.write_text(out.replace("\n", nl) if nl == "\r\n" else out, encoding="utf-8", newline="")
        b = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
        print("   回读校验：§三 挂出", b.count("| `TAIL-175` | ⭐ **大表"),
              "· §14.3 两行", b.count("| `TAIL-174` ⭐ "), b.count("| `TAIL-175` ⭐ "),
              "· §四 销号行", b.count("| `TAIL-174` | 🧾"),
              "· C 类 1", b.count("C 类 **1**"), "· 已销号 172", b.count("已销号 **172**"))
    else:
        print("（`--check`：⛔ 未写）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
