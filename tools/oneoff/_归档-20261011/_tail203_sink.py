#!/usr/bin/env python
"""`TAIL-203`（2026-09-30）· **把计划 §14.3 里"已办"排期行下沉成归档件，原处留指针**。

为什么要它（口径出处 = 计划 §13.2 ＋ `tools/audit/audit_meta.py` 的 `T13`）：
  · `T10`/`T13` 的线 = 计划 **1800** 行（`ops/阈值表.md` 第 31 行「一个数、两处用」）；实测 **1792**（余 8）
    ⇒ 下一批登记尾巴就可能撞上限。
  · `T13` 给的**合法腾法**原话：「把已完成的**过程块**逐字下沉，原处留 2~3 行指针」。
  · §14.3「逐条排期」现有 **77 表行 / 其中 72 行是已办**（`✅`）—— 已办行的留痕本体在 **§15 §四**
    （销号依据 ＋ 日期），排期表里再留一份 = 同一件事两处写。

⛔⛔ **三条红线（都已按源码核过，⛔ 别绕）**：
  ① **§15 §四 一行都不能搬** —— `T6` 把整段（一/二/三/四）的编号并起来查「`1..N` 顺延不跳号」；
     搬走 §四 ⇒ `nums` 变成 `[188,195,203]` ⇒ **当场判红「编号不连续」**。
  ② **只搬"编号已不在 §15 一/二/三 段"的行** —— `T6` 要求 **live（未销号）编号必须能在 §14.3 找到**；
     搬错一行 ⇒ 判红「登记了但没排期」。
  ③ **⛔ 不改任何一行的内容**（逐字搬）—— 下沉 = 换位置，⛔ 不是改写。

用法（仓根 · 先干跑）：
    backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_tail203_sink.py            # 只报要搬几行、搬到哪
    backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_tail203_sink.py --write    # 落盘（写前自动备份计划件）
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAN = REPO / ".workbuddy" / "plans" / "开发计划-主文档.md"
ARCH_DIR = REPO / ".workbuddy" / "plans" / "archive"
ARCH = ARCH_DIR / "归档-排期-已办尾巴-20260930.md"

BT = chr(96)          # 反引号
TAIL_ROW = re.compile(r"^\|\s*" + BT + r"?(TAIL-\d+)" + BT + r"?")
SEC = re.compile(r"^#{2,3}\s*([一二三四])\s*[、.]")
LEDGER_SEC = re.compile(r"^#{2,3}\s*[\d.]*\s*尾巴台账")
SCHED_SEC = re.compile(r"^###\s*14\.3")


def read_lines(p: Path) -> list[str]:
    """**保留每行自己的行尾**（本仓计划件是 CRLF）。

    ⚠️⚠️ 必须 `read_bytes().decode()` —— ⛔ **不能用 `read_text()`**：它默认走 *universal newlines*，
    会把 `\\r\\n` **归一成 `\\n`** ⇒ `splitlines(keepends=True)` 拿到的行尾全变成 `\\n` ⇒
    写回时**整份 1792 行从 CRLF 变 LF**（本仓实测踩过：脚本第一版就报 "行尾 = LF"，与实测 1792 CRLF 不符）。
    """
    return p.read_bytes().decode("utf-8").splitlines(keepends=True)


def live_numbers(lines: list[str]) -> set[str]:
    """§15 段里 **一/二/三** 段首格的编号 = **未销号**（`T6` 的 `live`）→ ⛔ 这些行不许搬。"""
    start = next(i for i, l in enumerate(lines) if LEDGER_SEC.match(l.strip()))
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    sec, out = "", set()
    for l in lines[start:end]:
        m = SEC.match(l.strip())
        if m:
            sec = m.group(1)
            continue
        if sec in ("一", "二", "三"):
            r = TAIL_ROW.match(l.strip())
            if r:
                out.add(r.group(1))
    return out


def sched_range(lines: list[str]) -> tuple[int, int]:
    s = next(i for i, l in enumerate(lines) if SCHED_SEC.match(l))
    e = next((i for i in range(s + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return s, e


HEAD = """# 归档 · 尾巴排期（**已办**那一半）—— 2026-09-30

> **读者**：要查「某条尾巴当初为什么排在那个时机」的人（含将来的我）｜**回答**：计划 §14.3「逐条排期」里**已办**那些行的**原文**
> **何时读**：怀疑「这条尾巴当初怎么排的」时；⚠️ ⛔ **别当现状读** —— 现状只看计划 §15 台账
> **状态**：留痕（只追加 · ⛔ 不回改）｜**关联**：`TAIL-203`（§15 §一）· 下沉口径 = 计划 §13.2 ＋ `T13`（`tools/audit/audit_meta.py`）
> **依据**：用户 2026-09-30「全按推荐」⇒ `TAIL-203`「两份活文档腾余量」；⛔ 内容**逐字**搬自计划 §14.3，一行未改

---

## 一、为什么会有这一份

计划 §14.3「逐条排期」的**用途 = 给「还没办」的尾巴排时机**（`T6` 的「登记即排期」守的就是它）。
而它当时 **77 表行里 72 行是已办**（`✅`）—— 已办行的**留痕本体在 §15 §四**（销号依据 ＋ 日期），
排期表里再留一份 = **同一件事两处写**，还把计划顶到 **1792/1800（余 8）**。
⇒ 按 `T13` 的合法口径（已完成的过程块**逐字**下沉、原处留指针）把**已办行**搬到这里，
计划 §14.3 从此**只留「还没办」的** ＋ 一行指针。

## 二、原文（逐字 · 按计划里的原顺序）

| 尾巴 | 建议时机（原单元格） | 理由（四问）／前置（原单元格） | 触发（原单元格） |
|---|---|---|---|
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    lines = read_lines(PLAN)
    nl = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    live = live_numbers(lines)
    s, e = sched_range(lines)
    rows = [(i, TAIL_ROW.match(lines[i].strip()).group(1)) for i in range(s, e)
            if TAIL_ROW.match(lines[i].strip())]
    move = [(i, n) for i, n in rows if n not in live]
    kept = sorted({n for _, n in rows} - {n for _, n in move}, key=lambda x: int(x.split("-")[1]))

    print(f"计划 = {len(lines)} 行 · 行尾 = {'CRLF' if nl == chr(13) + chr(10) else 'LF'} · §14.3 区间 {s + 1}-{e}")
    print("live（未销号 · ⛔ 不许搬）= " + " ".join(sorted(live, key=lambda x: int(x.split('-')[1]))))
    print(f"§14.3 表行 = {len(rows)} · **可搬（编号已不在台账活段）= {len(move)}** · 留下 = {len(kept)}（{kept}）")
    if not move:
        print("（无可搬 ⇒ 什么都不做）")
        return 0
    print(f"[干跑] 预计：计划 {len(lines)} → {len(lines) - len(move) + 1} 行"
          f"（−{len(move)} 已办行 ＋1 指针行）· 归档件 = {ARCH.relative_to(REPO)}")
    if not a.write:
        print("      ⇒ 加 --write 落盘（写前自动备份计划件）")
        return 0

    ARCH_DIR.mkdir(parents=True, exist_ok=True)
    bak = PLAN.with_name(PLAN.name + ".bak-20260930")
    shutil.copy2(PLAN, bak)

    arch = HEAD.replace("\n", nl) + "".join(lines[i] for i, _ in move)
    ARCH.write_text(arch, encoding="utf-8", newline="")

    ptr = (f"| ⬇ **已办的那 {len(move)} 行已下沉**（`TAIL-203` · 2026-09-30） | ⛔ 本表**只留「还没办」的** | "
           f"查已办行的原文 ⇒ {BT}.workbuddy/plans/archive/归档-排期-已办尾巴-20260930.md{BT}（**逐字**搬、一行未改） | "
           f"触发 = 谁问「这条当初怎么排的」" + nl)
    drop = {i for i, _ in move}
    first = min(drop)
    out = [lines[i] for i in range(len(lines)) if i not in drop]
    out.insert(first, ptr)

    PLAN.write_text("".join(out), encoding="utf-8", newline="")
    print(f"\n✅ 已下沉 {len(move)} 行 · 归档件 = {ARCH.relative_to(REPO)}")
    print(f"   计划 = {len(out)} 行（原 {len(lines)}）· 备份 = {bak.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
