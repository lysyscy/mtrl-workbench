#!/usr/bin/env python
"""`A7` 逐页（`m11` 集采台账）的**契约面登记** · 一次性（2026-09-29）。

**规矩照旧**：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋
末尾一个 CRLF；**改前先 round-trip 逐字节比对**（不等 ⇒ 拒写）；**改前先备份交付面**。

**它做什么**：`ACC-UI-SHELL-001` ＋ `001-60`：**集采抓取按钮要写清后果**（会登录 i8 ＋ ⚠️ 可能顶号）
—— 原来那枚按钮**一个字提示都没有**，而 `m01`「同步仓库名单」/ `m02` 两个同步都写了；而集采抓取
**还会顶号**（`D9`）⇒ 用户点下去才知道。＋ `PRD/验收/用例索引.md` 补变更说明。

用法：`… _doc_a7.py --check` / `--write`
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
        "id": "001-60",
        "kind": "outcome",
        "claim": "**会顶号的动作，提示必须写在按钮上**：`m11` 卡头「抓取采购合同信息」原**一个字提示都没有**"
                 "（无 `title`），而 `m01`「同步仓库名单」写「会登录 i8，需二次确认」、`m02` 两个同步同款；"
                 "集采抓取**还会顶号**（`D9`：登录会顶掉该账号的其它在线会话 ⇒ 同事正在用 i8 时不能点）"
                 "⇒ 提示补到按钮上（与确认弹窗**同一口径**，⛔ 不新增口径）。判法两半："
                 "① 那枚按钮**必须有 `title`**；② 提示里**必须写清后果**（会登录 `i8` ＋ 可能顶号）",
        "cover": "守则 §2.4 · §4.4",
    },
)

INDEX_NOTE = (
    "；⭐ **2026-09-29（`A7` 逐页 · `m11` 集采台账）** 补判据点 `001-60` **会顶号的动作，提示必须写在按钮上** —— "
    "该页「抓取采购合同信息」原**一个字提示都没有**（`m01`「同步仓库名单」/ `m02` 两个同步都写了；而集采抓取"
    "**还会顶号** `D9`）⇒ 补到按钮上（与确认弹窗同一口径）；⚠️ 同批量测留下的**待裁**：该页合同主表 20 列，"
    "**行身份列（序号 / 材料名）没钉**，而 4 个可编辑列（付款方式 / 备注 / 存档号 / 寄回日期）正好在最右 ⇒ "
    "往右填时看不见「在给哪条合同填」（同族 `TAIL-175`）；⚠️ **不能照抄大表那份静态偏移**（真机实测：首列宽随视口变"
    " —— 1440/1920 是 29、2560 是 34）⇒ 立 `TAIL-180` 请用户选做法"
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
    assert len(ids) == 59, f"`ACC-UI-SHELL-001` 现有 {len(ids)} 点（期望 59）⇒ 基线已变，先核再改"
    c["points"].extend(POINTS)
    print(f"＋ `ACC-UI-SHELL-001` 加 {len(POINTS)} 点（{POINTS[0]['id']}）")
    for line in patch_index(args.write):
        print(line)

    if not args.write:
        print(f"\n（`--check`：⛔ 未写；写的话 {before} ⇒ {before + len(POINTS)}）")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    backup = REPO / ".workbuddy" / "backups" / f"交付面-{stamp}-A7"
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
