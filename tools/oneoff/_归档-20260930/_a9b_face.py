#!/usr/bin/env python
"""`TAIL-185`（`A` 案）的**契约面改动** · 一次性（2026-09-29）。

**为什么必须改契约**：`ACC-INV-001/001-12` 的 claim 原文写的是「主表的朴素导出与「导出（含数据透视表）」
**并存互不影响**」—— 用户 2026-09-29 裁定 `A`（摘掉那枚朴素导出）之后，这句话**不再成立** ⇒
⛔ 只改壳不改 claim 就是守则 §4.1 的「说了不做」（界面与契约互相矛盾）。

**规矩照旧**：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋
末尾一个 CRLF；**改前先 round-trip 逐字节比对**（不等 ⇒ 拒写）；**改前先备份交付面**；
＋ `PRD/验收/用例索引.md` 同行补变更说明。

用法：`… _a9b_face.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
BASELINE = FACE / "PRD" / "验收" / "验收基线.json"
INDEX = FACE / "PRD" / "验收" / "用例索引.md"

OLD_CLAIM = ("主表的朴素导出与「导出（含数据透视表）」并存互不影响；"
             "后者提示必须与模板实际形态一致（不得声称与实例不符的形态）")
NEW_CLAIM = (
    "⭐ **2026-09-29（`TAIL-185` · 用户裁定 `A`）：卡头只留真入口** —— `m08` 主表那枚朴素「导出 Excel」"
    "点了只会走兜底说「这一页还没有导出功能」（⇒ 让用户以为坏了，守则 §4.6：看不到的功能不留『点了报错』"
    "的入口）⇒ **渲染后必须被 `BIND.m08` 摘除**（同 `m06` 那次 `TAIL-173`；⚠️ 切片 `V.m08` **一行不动** —— "
    "它是 `ui_parity` 的 `U1` 逐行对位原件，删行会让它后面所有行报漂移）；"
    "「导出（含数据透视表）」那份的提示必须与模板实际形态一致（不得声称与实例不符的形态）"
)

INDEX_NOTE = (
    "；⭐ **2026-09-29 用户裁定 `A`（`TAIL-185` · `A9` 逐页 · `m08`）**：`001-12` 的 claim 由"
    "「朴素导出与含透视那份**并存互不影响**」改成「**卡头只留真入口**：朴素那枚**渲染后被 `BIND.m08` "
    "摘除**」（点了必然空转 ⇒ 让用户以为坏了；同 `m06` 那次 `TAIL-173`）；⛔ **切片一行不动**"
    "（`U1` 逐行对位原件）；守卫同批改在 `tests/test_tail04_export.py`"
)


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def patch_index(write: bool) -> list[str]:
    raw = INDEX.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    hits = [i for i, ln in enumerate(lines) if ln.startswith("| `ACC-INV-001` |")]
    assert len(hits) == 1, f"用例索引里 `ACC-INV-001` 命中 {len(hits)} 行（要 1 行）"
    i = hits[0]
    assert INDEX_NOTE not in lines[i], "这一段变更说明已在 ⇒ 本脚本跑过了"
    row = lines[i].rstrip()
    assert row.endswith("|"), "该行不以 `|` 收尾 ⇒ 表结构变了"
    lines[i] = row[:-1].rstrip() + INDEX_NOTE + " |"
    if write:
        INDEX.write_text(nl.join(lines), encoding="utf-8", newline="")
    return [f"  用例索引.md `ACC-INV-001` 行 ⇒ 已补 `TAIL-185` 变更说明（{len(INDEX_NOTE)} 字）"]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = BASELINE.read_text(encoding="utf-8", newline="")
    obj = json.loads(raw)
    if _dump(obj) != raw:
        print("round-trip 逐字节比对：⛔ 不一致（⛔ 别写！）")
        return 1
    print("round-trip 逐字节比对：✅ 一致")

    c = obj["cases"]["ACC-INV-001"]
    hits = [p for p in c["points"] if p["id"] == "001-12"]
    assert len(hits) == 1, f"`ACC-INV-001/001-12` 命中 {len(hits)} 条"
    p = hits[0]
    if p["claim"] == NEW_CLAIM:
        print("⏭ 已应用（claim 已是新版）⇒ 无事可做")
        return 0
    assert p["claim"] == OLD_CLAIM, f"claim 与预期原文不符（基线已变，先核再改）：\n{p['claim'][:120]}"
    p["claim"] = NEW_CLAIM
    print("＋ `ACC-INV-001/001-12` 的 claim 已改为「卡头只留真入口」")
    for line in patch_index(args.write):
        print(line)

    if not args.write:
        print("\n（`--check`：⛔ 未写）")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    backup = REPO / ".workbuddy" / "backups" / f"交付面-{stamp}-A9b"
    for f in (BASELINE, INDEX):
        dst = backup / f.relative_to(FACE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)                      # ⚠️ 改前先备份
    print(f"✅ 已备份交付面 2 件 ⇒ {backup}")

    BASELINE.write_text(_dump(obj), encoding="utf-8", newline="")
    back = json.loads(BASELINE.read_text(encoding="utf-8"))
    got = [x for x in back["cases"]["ACC-INV-001"]["points"] if x["id"] == "001-12"][0]["claim"]
    assert got == NEW_CLAIM, "写回后 claim 不对"
    print("\n✅ 已写回（判据点总数**不变** —— 本条是改既有 claim 的文字，⛔ 不新增点）")
    print("   ⚠️ 接着：全套 pytest（`test_tail04_export.py` 的 `001-12` 同批改了守卫）⇒ 12 把尺子")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
