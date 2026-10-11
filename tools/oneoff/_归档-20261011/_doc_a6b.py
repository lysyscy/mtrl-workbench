#!/usr/bin/env python
"""`A6b`（用户「按推荐」）的**契约面登记** · 一次性（2026-09-29）。

**规矩照旧**：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋
末尾一个 CRLF；**改前先 round-trip 逐字节比对**（不等 ⇒ 拒写）；**改前先备份交付面**（脚本自己备）。

**它做什么**：
  1. `ACC-UI-SHELL-001/001-57` **判词改成一般式** —— 原来只写「`m01` 那句」，
     而同日顺藤摸出 `m03`/`m05` **两处同族**（同一句话的变体）⇒ 只钉一处＝判据比条文弱
     ⇒ 判词与断言一起改成「`必须列出` 这类**要求句式**一律不许上屏」；
  2. ＋`001-58`：**点不通的按钮必须置灰，而且理由要看得见**（`TAIL-177` 的 `A` 案；
     ⭐ 真机实测：置灰按钮 `:hover` **成立** ⇒ `title` 有机会弹，但它只管"鼠标停在按钮上"的人
     ⇒ 理由必须上屏）；
  3. ＋`001-59`：**删除分档的界面说法必须与定案一致**（`m05` 期初行原写「按软删留痕处理」——
     后端就是真删、§9.4 定案把期初划在硬删档；`m14`「硬规矩」表原写改判前的「按类别分」说法）；
  4. `PRD/验收/用例索引.md`：`ACC-UI-SHELL-001` 行补**变更说明**。

用法：`… _doc_a6b.py --check` / `--write`
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

CLAIM_OLD = "判法两半：那句要求句整串不许回来（墓碑）＋ 弹窗里必须留下**人话的后果**说明；"
CLAIM_NEW = (
    "⭐ **同日顺藤摸出同族还有两处**（同一句话的变体）：`m03` 手动行「⚠️ 删除前**必须列出影响范围**」· "
    "`m05` 期初行「⚠️ 删除前**必须列出影响范围**」⇒ **判据不能只钉一处**（只钉 `m01` ＝「判据比条文弱」＝ "
    "另一种假绿）⇒ 判法两半（**一般式**）：① 「`必须列出`」这类**写给实现的要求句式**一律不许上屏"
    "（先剥块注释再判 —— 注释里会引述旧写法作留痕）；② 删除确认里必须留下**人话的后果**"
    "（`m01`「删除不可撤销」· `m03`/`m05`「先看清下面这些影响」各 ≥1 处）；"
)

POINTS = (
    {
        "id": "001-58",
        "kind": "outcome",
        "claim": "**点不通的按钮必须置灰，而且理由要看得见**：`m01` 的「删除」原本点得动 —— 弹确认框"
                 "（还替用户列了一半影响范围）→ 点「确认删除」→ 才被告知「尚未接通后端」⇒ **整套流程走完"
                 "什么都没发生**（守则 §5.5）⇒ 现在「确认删除」**置灰 ＋ 理由写在弹窗里看得见的地方**。"
                 "⚠️ 真机实测（`tools/oneoff/_a6b_check.py`）：置灰按钮的 `matches(':hover')` **仍然成立**"
                 "⇒ `title` **有**机会弹，但它只对「鼠标停在按钮上」的人有效（键盘 Tab / 触屏没有悬停）"
                 "⇒ 置灰理由**必须上屏**、`title` 只当补充；⚠️ 全站那批「置灰写理由」（约 27 处字面 "
                 "`disabled`）是否也只挂在 `title` 上，另立 `TAIL-178` 复核",
        "cover": "守则 §5.5 · §4.6 · §2.7",
    },
    {
        "id": "001-59",
        "kind": "outcome",
        "claim": "**删除分档的界面说法必须与定案一致**：① `m05` 期初行的删除确认原写「该行按**软删留痕**"
                 "处理（属核心业务数据）」—— 而 `mod05_flow.repository.delete_opening` 就是 `s.delete(row)`"
                 "（**真删**、行里没有留痕字段），《说明书》§9.4 的 2026-09-20 定案也把「**期初**」明确列在"
                 "**硬删**那一档 ⇒ 那句话给的是**假的安全感**（用户以为删了还能恢复）⇒ 改成人话"
                 "「真的删掉、删了不能恢复（需要时随时可以重新录入）」；② `m14`「硬规矩」表原写"
                 "「核心数据删除是『软删 + 留痕』；配置类是真删」—— 那是 §9.4 **改判之前**的「按类别分」说法 "
                 "⇒ 改成定案口径「按『删了能不能复原』分：可复原的 / 你自己录的 ⇒ 真删；只有账号是软删」",
        "cover": "守则 §4.2 · §2.5",
    },
)

INDEX_NOTE = (
    "；⭐ **2026-09-29（`A6b` · 用户「按推荐」）**：① `001-57` **判词与断言一起改成一般式** —— "
    "原只写 `m01` 那句，而同日顺藤摸出 `m03`/`m05` **两处同族**（同一句话的变体）⇒ 只钉一处 ＝ "
    "「判据比条文弱」；② ＋`001-58` **点不通的按钮必须置灰而且理由要看得见**（`TAIL-177` 的 `A` 案；"
    "⭐ 真机实测置灰按钮 `:hover` **成立** ⇒ `title` 有机会弹、但只管鼠标用户 ⇒ 理由必须上屏）；"
    "③ ＋`001-59` **删除分档的界面说法必须与定案一致**（`m05` 期初行原写「按软删留痕处理」而后端就是真删、"
    "§9.4 定案把期初划在硬删档＝**假的安全感**；`m14`「硬规矩」表原写改判前的「按类别分」说法）；"
    "该用例 `cover` 同批补 `守则 §2.7`（`001-58` 用）"
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
    assert len(ids) == 57, f"`ACC-UI-SHELL-001` 现有 {len(ids)} 点（期望 57）⇒ 基线已变，先核再改"
    # ① 001-57 判词改成一般式
    p57 = next(p for p in c["points"] if p["id"] == "001-57")
    assert p57["claim"].count(CLAIM_OLD) == 1, "`001-57` 判词里找不到要替换的那句（先核）"
    p57["claim"] = p57["claim"].replace(CLAIM_OLD, CLAIM_NEW)
    print("· `001-57` 判词 ⇒ 改成一般式（要求句式一律不许上屏 ＋ 三处同族都点到）")
    # ② 新增两点
    c["points"].extend(POINTS)
    if "守则 §2.7" not in c["cover"]:
        c["cover"].append("守则 §2.7")
        print("· 用例 `cover` 补 守则 §2.7")
    print(f"＋ `ACC-UI-SHELL-001` 加 {len(POINTS)} 点（{POINTS[0]['id']}/{POINTS[1]['id']}）")
    for line in patch_index(args.write):
        print(line)

    if not args.write:
        print(f"\n（`--check`：⛔ 未写；写的话 {before} ⇒ {before + len(POINTS)}）")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    backup = REPO / ".workbuddy" / "backups" / f"交付面-{stamp}-A6b"
    for p in (BASELINE, INDEX):
        dst = backup / p.relative_to(FACE)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)                      # ⚠️ 改前先备份
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
