#!/usr/bin/env python
"""`TAIL-117` **销号**（用户 2026-09-29 裁定「117 销号」）· 一次性。

**为什么可以销**：它是**照《前端设计守则》逐处重构前端**的**主项** —— 它的两套排期都**已走完**：
  ① 审计清单 `§五` 的 **8 个批次**（0–7）全部完成（每批都有判据 ＋ 反向灵敏度 ＋ 盖章）；
  ② **2026-09-29 起**改成的「**自主逐页推进**」（17 屏 × 7 步 · 计划件
     `work/10-designs/设计-前端逐页推进计划-20260929.md`）⇒ 今天 **`A1`–`A11` 整表走完**（16 屏全覆盖）。
  ⇒ 本行原先挂的时机是「随时（自主推进）」—— 现在**没有待办动作**了，留着会让"进行中"虚高。

**它改什么**：`§一` 删 `TAIL-117` 行 ⇒ `§四` 加一行（依据 ＋ 出处）；计数 `A 5 → 4` · `已销号 185 → 186`；
`§14.3` 那一行的**末格**（状态）改成 `✅ 已办`（⚠️ 按**单元格**定位、⛔ 不靠整行长串锚点）。**不写 `§10`**
（那是"前端口径变更"的账，销号不是口径变更）。

用法：`… _a12_close117.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

PLAN = pathlib.Path(__file__).resolve().parents[2] / ".workbuddy" / "plans" / "开发计划-主文档.md"

SRC = "出处 = §13.6 接手核验续记 ＋ `.codebuddy/memory/2026-09-29.md`"

ROW_DONE = (
    "| `TAIL-117` | 🧾 **「照《前端设计守则》逐处重构前端」主项销号**（2026-09-29 **用户裁定**「117 销号」· "
    + SRC + "）：它的**两套排期都走完了** —— ① 前端审计清单 `§五` 的 **8 个批次（0–7）全部完成**"
    "（报错人话化 / 内部编号与开发话术清理 / 相似元素与颜色语义 / 数字口径 / 长文案与优先级 / 四态统一 / "
    "残骸清理 / 颜色细读 —— 每批都带判据 ＋ 反向灵敏度 ＋ 盖章）；② 2026-09-29 起改成的「**自主逐页推进**」"
    "（17 屏 × 7 步 · `work/10-designs/设计-前端逐页推进计划-20260929.md`）⇒ **`A1`–`A11` 整表走完**"
    "（`m05`→`m03`→`m04`→`m06`→`m07`→`m01`·`m02`→`m11`→`imp`→`m08`·`m09`·`m10`→`m13`·`m14`·`set`·`m15`→`home`，"
    "**16 屏全覆盖**）；⇒ ⛔ 无待办动作（用户裁定：调试告一段落、进入收口） | "
    "依据 = ① 守则 `§10` 变更记录里那 **8 个批次**各自的「判据 ＋ 反向灵敏度 ＋ 盖章」行；"
    "② 逐页计划的 `§三` 进度块（`A1`–`A11` 各自的「量测先行 / 本批收口 / 放过理由」＋ `TAIL-169`–`TAIL-187` "
    "共 19 条尾巴的销号行）；③ 四态 **641 绿 / 0 红** ＋ 12 把尺子 rc=0 ＋ 真机全段 rc=0（盖章 "
    "`20260929-1302`） | 2026-09-29 |"
)


def _cells(line: str) -> list[str]:
    return line.strip().strip("|").split("|")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = PLAN.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")

    # ── 1) §一：删 `TAIL-117` 行 ────────────────────────────────────────
    hA = [i for i, ln in enumerate(lines)
          if ln.strip() == "| # | 事项 | 来源 | 不做会怎样 | 落点 | 阶段 / 时机 | 状态 |"]
    assert len(hA) == 1, f"§一 表头命中 {len(hA)} 行"
    drop = [i for i in range(hA[0] + 1, len(lines))
            if lines[i].startswith("| `TAIL-117` |")]
    assert len(drop) == 1, f"§一 的 `TAIL-117` 行命中 {len(drop)} 行"

    # ── 2) §14.3：把那一行的**末格**改成「✅ 已办」（按单元格定位）──────
    hS = [i for i, ln in enumerate(lines)
          if ln.strip() == "| 尾巴 | 建议时机 | 理由（四问） | 前置 / 触发 |"]
    assert len(hS) == 1, f"§14.3 表头命中 {len(hS)} 行"
    # ⚠️ **只扫本表**（到第一个非 `|` 行为止）：§14.3 之后别的段落里也可能出现同一个编号，
    #    不设边界就会把"别处提到它"也当成排期行（实测踩到：命中 2 行）。
    end14 = hS[0] + 1
    while end14 < len(lines) and lines[end14].startswith("|"):
        end14 += 1
    row117 = [i for i in range(hS[0] + 1, end14) if lines[i].startswith("| `TAIL-117`")]
    for i in row117:
        print(f"  · §14.3 第 {i + 1} 行：{_cells(lines[i])[1].strip()[:60]}")
    assert len(row117) == 1, f"§14.3（第 {hS[0] + 1}–{end14} 行）里的 `TAIL-117` 行命中 {len(row117)} 行"
    # ⚠️ ⛔ **别按 `|` 切格数**：本表的单元格里会出现 `|词1|词2|`（那个关键字格式自带竖线）⇒
    #    切出来会多出几格（实测：期望 4 格、切出 5 格）。**只认"最后一个 `|…|` 就是状态格"**。
    _row = lines[row117[0]].rstrip()
    assert _row.endswith("|"), "该行不以 `|` 收尾 ⇒ 表结构变了"
    _head, _last = _row.rsplit("|", 2)[0], _row.rsplit("|", 2)[1]
    # ⚠️ 状态格现在写的是 `✅ **进行中（…）**`（那个 ✅ 是**进行中**的记号）⇒ 判据要认"进行中"三个字，
    #    ⛔ 不能只看有没有 ✅（实测：只看 ✅ 会误判成"已办过"而拒写）。
    assert "进行中" in _last and "已办" not in _last, f"状态格不像『进行中』：{_last.strip()[:40]}"
    print(f"  ✅ §14.3 命中第 {row117[0] + 1} 行：`TAIL-117`（状态格现为「{_last.strip()[:24]}…」）")

    # ── 3) §四：加销号行 ───────────────────────────────────────────────
    hD = [i for i, ln in enumerate(lines) if ln.strip() == "| # | 事项 | 销号依据 | 日期 |"]
    assert len(hD) == 1, "§四 表头不唯一"
    # ⚠️ **只在 `§四` 这张表里查重**（⛔ 别用"在 §一 之后"当边界 —— `§14.3` 那行也在它之后，
    #    实测把排期行当成了销号行、直接拒写）。
    _end4 = hD[0] + 1
    while _end4 < len(lines) and lines[_end4].startswith("|"):
        _end4 += 1
    assert not any(lines[i].startswith("| `TAIL-117` |") for i in range(hD[0] + 1, _end4)), \
        "`TAIL-117` 已在 `§四` 里"

    print(f"  ✅ §一 命中第 {drop[0] + 1} 行：`TAIL-117`（待删）· §四 表头第 {hD[0] + 1} 行（待插）")
    if not args.write:
        print("\n（`--check`：⛔ 未写；§一 −1 / §四 ＋1 / §14.3 改末格）")
        return 0

    # ⚠️ 顺序：先改 §14.3 的末格（按**当时**的行号），再删 §一、最后插 §四
    r = row117[0]
    lines[r] = _head + "| ✅ **已办（2026-09-29）** ⇒ 见 §15 §四 |"
    lines.pop(drop[0])
    hD = [i for i, ln in enumerate(lines) if ln.strip() == "| # | 事项 | 销号依据 | 日期 |"]
    assert len(hD) == 1, "删行后 §四 表头不唯一"
    lines.insert(hD[0] + 1, ROW_DONE)
    PLAN.write_text(nl.join(lines), encoding="utf-8", newline="")
    print("✅ 已写：§一 −1（`TAIL-117`）· §四 ＋1（销号）· §14.3 末格 ⇒ ✅ 已办")

    # ── 4) 计数两处 ────────────────────────────────────────────────────
    for old, new, what in (
        ("A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **185**",
         "A 类 **4** 条 · B 类 0 · C 类 **0** · 已销号 **186**", "§0.2"),
        ("A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **185** 条",
         "A 类 **4** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **186** 条", "§15 计数行"),
    ):
        raw = PLAN.read_text(encoding="utf-8", newline="")
        n = raw.count(old)
        assert n == 1, f"{what} 计数锚点命中 {n} 次"
        PLAN.write_text(raw.replace(old, new, 1), encoding="utf-8", newline="")
        print(f"✅ 已写：{what} 计数（A 5 → 4 · 已销号 185 → 186）")

    print("\n接着：`audit_meta`（`T6`：编号 / 计数 / 排期两表一致）⇒ `doc_audit`")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
