#!/usr/bin/env python
"""`A6` 逐页（`m01` 项目档案）的**契约面登记** · 一次性（2026-09-29）。

**规矩照旧**：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋
末尾一个 CRLF；**改前先做 round-trip 逐字节比对**，不等就**拒写**；**改前先备份交付面**（脚本自己备）。

**它做什么**（2 条新判据，都是本批新写的守卫）：
  1. `ACC-UI-SHELL-001` ＋ `001-56`：**空态指路的按钮名必须真实存在**（`m01` 指路原写着
     「＋ 新增项目」而全站没有那个按钮 ⇒ 用户按指路找不到东西、卡住；同族第 2 例 = `A2` 的 `m03`）；
  2. `ACC-UI-SHELL-001` ＋ `001-57`：**删除确认里不许把要求句甩给用户**（原句是从《说明书》§7.2
     原样搬来的「必须列出删除影响范围」= 写给实现的要求，不是给用户看的话）＋ `cover` 补 `守则 §1.1`；
  3. `PRD/验收/用例索引.md`：`ACC-UI-SHELL-001` 行补**变更说明**。

用法：`… _doc_a6_m01.py --check` / `--write`
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

POINTS = (
    {
        "id": "001-56",
        "kind": "outcome",
        "claim": "**空态指路点名的入口必须真实存在**：`m01` 项目档案的空态原写「或点右上角「＋ 新增项目」"
                 "建档」，而那一页（乃至全站）**没有这个按钮**（卡头只有「同步仓库名单」「同步常用项目列表」"
                 "「导出 Excel」）⇒ 用户按指路去点 = **找不到东西、卡住**；⚠️ 同族第 2 例：`A2` 那轮 `m03` "
                 "的指路写着「＋ 新增」而按钮叫「＋ 手动新增通知书」。判法两半：指路点名的入口**真的存在**"
                 "（按 `data-act` ＋ 标题文案认）＋ **那句旧指路整串**不许回来（墓碑；⛔ 不拿「新增项目」"
                 "四个字去撞 —— 将来真加了同名按钮会误红）",
        "cover": "守则 §2.1 · §4.2",
    },
    {
        "id": "001-57",
        "kind": "outcome",
        "claim": "**删除确认里不许把「要求句」甩给用户**：`m01` 删除确认弹窗第一句原是从《说明书》§7.2 "
                 "**原样搬来**的「必须列出删除影响范围（§7.2）」—— 那是写给**实现**的要求，不是给用户的话"
                 "（用户在删除前要知道的是「删了会怎样」）⇒ 改成人话「⚠️ **删除不可撤销** —— 先看清它会影响到"
                 "下面哪些地方」（下面本来就列着影响范围）。判法两半：那句要求句整串不许回来（墓碑）＋ "
                 "弹窗里必须留下**人话的后果**说明；⚠️ `（§7.2）` 这个出处标记**保留**（用户 2026-09-27 裁定 `B`）",
        "cover": "守则 §1.1 · §2.5 · §2.4",
    },
)

INDEX_NOTE = (
    "；⭐ **2026-09-29** 补判据点 `001-56`/`001-57`（`A6` 逐页 · `m01` 项目档案）："
    "① `001-56` **空态指路点名的入口必须真实存在** —— 该页空态原写「或点右上角「＋ 新增项目」建档」，"
    "而**全站没有那个按钮**（卡头只有两个 i8 同步 ＋ 导出）⇒ 用户按指路找不到东西、卡住"
    "（同族第 2 例：`A2` 那轮 `m03`）⇒ 改成点名真实入口 ＋ 墓碑钉住旧句；"
    "② `001-57` **删除确认里不许把要求句甩给用户** —— 原句是从《说明书》§7.2 原样搬来的"
    "「必须列出删除影响范围」= 写给实现的要求 ⇒ 改成人话「删除不可撤销 —— 先看清它会影响到下面哪些地方」"
    "（`（§7.2）` 出处标记按 2026-09-27 裁定 `B` 保留）；该用例 `cover` 同批补 `守则 §1.1`"
)


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def patch_index(write: bool) -> list[str]:
    raw = INDEX.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    hits = [i for i, ln in enumerate(lines) if ln.startswith("| `ACC-UI-SHELL-001` |")]
    assert len(hits) == 1, f"用例索引里 `ACC-UI-SHELL-001` 命中 {len(hits)} 行（要 1 行）"
    i = hits[0]
    assert INDEX_NOTE not in lines[i], "变更说明已在 ⇒ 本脚本跑过了"
    row = lines[i].rstrip()
    assert row.endswith("|"), "该行不以 `|` 收尾 ⇒ 表结构变了"
    lines[i] = row[:-1].rstrip() + INDEX_NOTE + " |"
    if write:
        INDEX.write_text(nl.join(lines), encoding="utf-8", newline="")
    return [f"  用例索引.md `ACC-UI-SHELL-001` 行 ⇒ 已补变更说明（{len(INDEX_NOTE)} 字）"]


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

    before = sum(len(v.get("points") or []) for v in obj["cases"].values())
    c = obj["cases"]["ACC-UI-SHELL-001"]
    ids = [p["id"] for p in c["points"]]
    assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"编号不顺延：末位 {ids[-1]}"
    assert len(ids) == 55, f"`ACC-UI-SHELL-001` 现有 {len(ids)} 点（期望 55）⇒ 基线已变，先核再改"
    c["points"].extend(POINTS)
    if "守则 §1.1" not in c["cover"]:
        c["cover"].append("守则 §1.1")
    print(f"＋ `ACC-UI-SHELL-001` 加 {len(POINTS)} 点（{POINTS[0]['id']}/{POINTS[1]['id']}）"
          f"· cover 补 守则 §1.1")
    for line in patch_index(args.write):
        print(line)

    if not args.write:
        print(f"\n（`--check`：⛔ 未写；写的话 {before} ⇒ {before + len(POINTS)}）")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    backup = REPO / ".workbuddy" / "backups" / f"交付面-{stamp}-A6"
    for p in (BASELINE, INDEX):
        dst = backup / p.relative_to(FACE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)                      # ⚠️ 改前先备份（本件只改这两件）
    print(f"✅ 已备份交付面 2 件 ⇒ {backup}")

    BASELINE.write_text(_dump(obj), encoding="utf-8", newline="")
    back = json.loads(BASELINE.read_text(encoding="utf-8"))
    after = sum(len(v.get("points") or []) for v in back["cases"].values())
    assert after == before + len(POINTS), f"点数不对：{before} ⇒ {after}"
    print(f"\n✅ 已写回：判据点合计 {before} ⇒ **{after}**")
    print("   ⚠️ 接着：全套 pytest（带 `ACC_RESULTS_PATH`）⇒ `acc_report` ⇒ 四态锚点 4 处 ⇒ 全闸门")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
