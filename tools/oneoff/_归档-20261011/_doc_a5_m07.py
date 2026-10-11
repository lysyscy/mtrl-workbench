#!/usr/bin/env python
"""`A5`（`m07` 收发结存与月度会大表逐页）· 把 1 条**新写**的守卫登记进契约面（一次性 · 2026-09-29）。

**规矩照旧**：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋
末尾一个 CRLF；**改前先做 round-trip 逐字节比对**，不等就**拒写**（⛔ 绝不文本替换）。

**它做什么**：`ACC-RPT-BIG-001`（活动大表）加 **1 点** `001-20`：**大表 0 行时必须给后端那句空态**
（⛔ 不许只剩三级表头；跨列数走 `thCols` 而非 `thCount`；文案主人是后端 `big_domain.empty_text`）
＋ `用例索引.md` 该行补变更说明。

用法：`… _doc_a5_m07.py --check` / `--write`
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
BACKUP = REPO / ".workbuddy" / "backups" / "交付面-20260929-1000-A5"
CASE = "ACC-RPT-BIG-001"

POINTS = ((
    "001-20", "outcome",
    "**大表 0 行时必须给空态**（为什么空 ＋ 下一步），⛔ 不许只剩**三级表头**（20 列横表空着 = 用户"
    "以为页面坏了）；⚠️ 文案的主人 = 后端 `big_domain.empty_text`（随 `/api/m07/big` 的 `empty_text` 给，"
    "壳⛔ 不编第二份）；⚠️ 跨列数走 **`thCols`**（大表是两行表头，`thCount` 会多算 3 列）",
    "守则 §2.1 · §5.4",
),)

COVER_ADD = ("守则 §2.1", "守则 §5.4")

NOTE = (
    "；⭐ **2026-09-29** 补判据点 `001-20`（`A5` 逐页 · `m07`）：**大表 0 行时必须给空态** —— 原先"
    "`if(!rs.length) return '';` ⇒ 只剩三级表头的大空表（与 `m04`/`m06` 同族）；文案接**后端那句**"
    "（`big_domain.empty_text`，此前是**死代码**、全仓没人调用）＋ 同批把它的措辞改准（原文说"
    "「还没勾项目」与「未选题 = 全部候选」的口径不符）；⚠️ 跨列数必须走 `thCols`（两行表头，`thCount` 会多算）"
)


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def patch_index(write: bool) -> str:
    raw = INDEX.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    hits = [i for i, ln in enumerate(lines) if ln.startswith(f"| `{CASE}` |")]
    assert len(hits) == 1, f"用例索引里 `{CASE}` 命中 {len(hits)} 行"
    i = hits[0]
    assert NOTE not in lines[i], "变更说明已在 ⇒ 本脚本跑过了"
    row = lines[i].rstrip()
    assert row.endswith("|"), "该行不以 `|` 收尾 ⇒ 表结构变了"
    lines[i] = row[:-1].rstrip() + NOTE + " |"
    if write:
        INDEX.write_text(nl.join(lines), encoding="utf-8", newline="")
    return f"  用例索引.md `{CASE}` 行 ⇒ 已补变更说明（{len(NOTE)} 字）"


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

    c = obj["cases"][CASE]
    ids = [p["id"] for p in c["points"]]
    assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"编号不顺延：{ids}"
    assert len(ids) == 19, f"`{CASE}` 现有 {len(ids)} 点（期望 19）⇒ 基线已变，先核再改"
    before = sum(len(v.get("points") or []) for v in obj["cases"].values())
    print(f"现有用例 {len(obj['cases'])} 条 · 判据点合计 {before} · `{CASE}` 现 {len(ids)} 点")
    c["points"].extend({"id": p, "kind": k, "claim": cl, "cover": cv} for p, k, cl, cv in POINTS)
    for sec in COVER_ADD:
        if sec not in c["cover"]:
            c["cover"].append(sec)
    print(f"＋ `{CASE}` 加 {len(POINTS)} 点（001-20）· cover 补 {list(COVER_ADD)}")
    print(patch_index(args.write))

    if args.write:
        BASELINE.write_text(_dump(obj), encoding="utf-8", newline="")
        back = json.loads(BASELINE.read_text(encoding="utf-8"))
        after = sum(len(v.get("points") or []) for v in back["cases"].values())
        assert after == before + len(POINTS), f"点数不对：{before} ⇒ {after}"
        print(f"\n✅ 已写回：判据点合计 {before} ⇒ **{after}**")
    else:
        print(f"\n（`--check`：⛔ 未写；写的话 {before} ⇒ {before + len(POINTS)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
