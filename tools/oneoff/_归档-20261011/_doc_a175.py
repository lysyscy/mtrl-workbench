#!/usr/bin/env python
"""`TAIL-175`（大表首列区固定）的**契约面登记** ＋ 顺手修 1 处交付面断链 · 一次性（2026-09-29）。

**规矩照旧**：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋
末尾一个 CRLF；**改前先做 round-trip 逐字节比对**，不等就**拒写**（⛔ 绝不文本替换交付面 JSON）。

**它做什么**（三件）：
  1. `ACC-UI-SHELL-001` ＋ **1 点** `001-55`：大表**首列区（序号 ＋ 项目名称）固定** ——
     表头第 1 行前两格 / 数据行前两格 / 合计行 `colspan="2"` 首格都挂 `.fl`；
     第 2 列用静态算式 `calc(39px * var(--fscale))` 让开首列的宽（真机量过：六种组合偏差 0）；
     屏幕上是否**真的严丝合缝**由真机 **㉜**（`tools/probe/_shell_bigpin.py`）看管。
  2. 该用例的 `source` 把真机段补全（原文只列到 ㉙，而 ㉚/㉛/㉜ 早已存在并被判据点引用）。
  3. `PRD/验收/用例索引.md`：① `ACC-UI-SHELL-001` 行补**变更说明**；
     ② ⭐ 顺手修一处**交付面断链**（`demo/_links.js` 报 `test_tail04_pages.py` **×1 FAIL**）——
        它缺 `tests/` 前缀 ⇒ 落进 `KNOWN` 白名单之外（`_links` 的 FAIL = 需处理的断链）；
        改法 = 补前缀（`tests/test_tail04_pages.py`），⛔ **不动** `_links.js` 的白名单口径。

用法：`… _doc_a175.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
FACE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")
BASELINE = FACE / "PRD" / "验收" / "验收基线.json"
INDEX = FACE / "PRD" / "验收" / "用例索引.md"
BACKUP = REPO / ".workbuddy" / "backups" / "交付面-20260929-1013-TAIL175"

SOURCE_OLD = "＋ 真机段 ㉔/㉕/㉖/㉗/㉙（`tools/probe/_shell_*`）"
SOURCE_NEW = "＋ 真机段 ㉔/㉕/㉖/㉗/㉙/㉚/㉛/㉜（`tools/probe/_shell_*`）"

POINT = {
    "id": "001-55",
    "kind": "outcome",
    "claim": "**大表（月度会大表）的首列区固定**：20 列横表往右填那 6 个手填列（机械费测算 / "
             "合同价 / 产值累计…正好落在最右）时，「**序号 ＋ 项目名称**」（表头第 1 行前两格 —— 它们 "
             "`rowspan=\"2\"`；数据行前两格；合计行 `colspan=\"2\"` 的首格）都挂 `.fl`（sticky-left），"
             "否则**看不见自己在给哪个项目填**（会填错行）；第 2 列的 `left` 写成静态算式 "
             "`calc(39px * var(--fscale))`（= 首列的宽，真机量过六种「视口 × 档位」组合偏差 0）。"
             "⚠️ 屏幕上是否**真的严丝合缝**离线判不了 ⇒ 由真机 ㉜ 看管",
    "cover": "守则 §5.9 · §4.2",
}

INDEX_NOTE = (
    "；⭐ **2026-09-29** 补判据点 `001-55`（`TAIL-175` · 用户裁定 `A`）：**月度会大表的首列区固定** —— "
    "20 列横表往右填手填那 6 列时「序号 ＋ 项目名称」跟着滚走 ⇒ 看不见自己在给哪个项目填（会填错行）"
    "⇒ 表头第 1 行前两格 ＋ 数据行前两格 ＋ 合计行 `colspan=\"2\"` 首格都挂 `.fl`，"
    "第 2 列用静态算式 `calc(39px * var(--fscale))` 让开首列的宽（真机量过：六种「视口 × 档位」偏差 0；"
    "**屏幕上的严丝合缝**由真机 **㉜** `tools/probe/_shell_bigpin.py` 看管）；"
    "⚠️ `BIG_THEAD` 是 `U5` 逐字一致项 ⇒ 同批**镜像原型**；同批把本用例 `source` 的真机段补到 ㉜"
)

#: 交付面断链：`demo/_links.js` 报它 ×1 FAIL（缺 `tests/` 前缀 ⇒ 落到 `KNOWN` 白名单之外）
LINK_BAD = "`test_tail04_pages.py`"
LINK_OK = "`tests/test_tail04_pages.py`"


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def patch_index(write: bool) -> list[str]:
    raw = INDEX.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    out: list[str] = []

    # ① `ACC-UI-SHELL-001` 行补变更说明
    hits = [i for i, ln in enumerate(lines) if ln.startswith("| `ACC-UI-SHELL-001` |")]
    assert len(hits) == 1, f"用例索引里 `ACC-UI-SHELL-001` 命中 {len(hits)} 行（要 1 行）"
    i = hits[0]
    assert INDEX_NOTE not in lines[i], "变更说明已在 ⇒ 本脚本跑过了"
    row = lines[i].rstrip()
    assert row.endswith("|"), "该行不以 `|` 收尾 ⇒ 表结构变了"
    lines[i] = row[:-1].rstrip() + INDEX_NOTE + " |"
    out.append(f"  用例索引.md `ACC-UI-SHELL-001` 行 ⇒ 已补变更说明（{len(INDEX_NOTE)} 字）")

    # ② 修交付面断链（缺 `tests/` 前缀）
    bad = [i for i, ln in enumerate(lines) if LINK_BAD in ln]
    assert len(bad) == 1, f"`{LINK_BAD}` 命中 {len(bad)} 处（要 1 处 —— `_links` 就是这么报的）"
    j = bad[0]
    assert LINK_OK not in lines[j], "前缀已在 ⇒ 本脚本跑过了"
    lines[j] = lines[j].replace(LINK_BAD, LINK_OK)
    out.append(f"  用例索引.md 第 {j + 1} 行 ⇒ 交付面断链已修（补 `tests/` 前缀，落到 `KNOWN` 白名单）")

    if write:
        INDEX.write_text(nl.join(lines), encoding="utf-8", newline="")
    return out


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
    print(f"交付面备份在位：{'✅' if BACKUP.exists() else '⛔ 先备份再改'} {BACKUP}")
    if not BACKUP.exists():
        return 1

    before = sum(len(v.get("points") or []) for v in obj["cases"].values())
    c = obj["cases"]["ACC-UI-SHELL-001"]
    ids = [p["id"] for p in c["points"]]
    assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"编号不顺延：末位 {ids[-1]}"
    assert len(ids) == 54, f"`ACC-UI-SHELL-001` 现有 {len(ids)} 点（期望 54）⇒ 基线已变，先核再改"
    assert obj["cases"]["ACC-UI-SHELL-001"]["cover"].count("守则 §5.9") == 1, "该用例 cover 里没有 §5.9"
    c["points"].append(POINT)
    print(f"＋ `ACC-UI-SHELL-001` 加 1 点（{POINT['id']}）· cover {POINT['cover']}（用例 cover 已有 §5.9 ⇒ 不重复加）")

    src = c["source"].count(SOURCE_OLD)
    assert src == 1, f"`source` 里的真机段原文命中 {src} 次（要 1 次）"
    c["source"] = c["source"].replace(SOURCE_OLD, SOURCE_NEW)
    print(f"· `source` 真机段补齐 ⇒ ㉔/㉕/㉖/㉗/㉙/㉚/㉛/㉜")

    for line in patch_index(args.write):
        print(line)

    if args.write:
        BASELINE.write_text(_dump(obj), encoding="utf-8", newline="")
        back = json.loads(BASELINE.read_text(encoding="utf-8"))
        after = sum(len(v.get("points") or []) for v in back["cases"].values())
        assert after == before + 1, f"点数不对：{before} ⇒ {after}"
        print(f"\n✅ 已写回：判据点合计 {before} ⇒ **{after}**")
        print("   ⚠️ 接着：全套 pytest（带 `ACC_RESULTS_PATH`）⇒ `acc_report` ⇒ 四态锚点 5 处 ⇒ 全闸门")
    else:
        print(f"\n（`--check`：⛔ 未写；写的话 {before} ⇒ {before + 1}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
