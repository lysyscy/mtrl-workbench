#!/usr/bin/env python
"""`TAIL-173`（`A4` 顺手报的两件 · 用户裁定 `A`）的**契约面登记** · 一次性（2026-09-29）。

**规矩照旧**：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋
末尾一个 CRLF；**改前先做 round-trip 逐字节比对**，不等就**拒写**（⛔ 绝不文本替换交付面 JSON）。

**它做什么**（两条新判据，各自落在**最贴题**的用例上）：
  1. `ACC-RPT-EXP-001`（`MOD-06` 导出）＋ **1 点** `001-09`：`m06` 卡头不再出现那枚**永不出结果**的
     导出按钮（渲染后摘除；⛔ 切片一行未改）；
  2. `ACC-RPT-PROC-001`（`MOD-06` 现场三表口径）＋ **1 点** `001-10`：差异表**差额列只标方向**
     （原本整列标红 ⇒ 每行都是差异、"红"失去区分度）；
  3. `PRD/验收/用例索引.md`：两行各补**变更说明**（日期 ＋ 判据点号 ＋ 裁定代号）。

用法：`… _doc_tail173.py --check` / `--write`
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
BACKUP = REPO / ".workbuddy" / "backups" / "交付面-20260929-0945-TAIL173"

PLAN: tuple[tuple[str, int, tuple[tuple[str, str, str, str], ...], tuple[str, ...], str], ...] = (
    (
        "ACC-RPT-EXP-001", 8,
        (("001-09", "outcome",
          "`m06` 卡头**不再出现那枚永不出结果的导出按钮**：该页已有真入口「批量导出（先选项目）…」"
          "（按 17 列模板导出），而那枚「导出 Excel」**永远只会说「这一页还没有导出功能」**"
          "⇒ 并排摆着点一次空转 = 让用户以为坏了（§4.4 相似元素不制造歧义）；"
          "⚠️ 做法 = **渲染后摘除**（摘掉即可，⛔ 切片一行未改），⚠️ 兜底那句留着（别的页还在用）",
          "守则 §4.4"),),
        ("守则 §4.4",),
        "；⭐ **2026-09-29** 补判据点 `001-09`（`TAIL-173`-① · 用户裁定 `A`）：`m06` 卡头**摘掉那枚"
        "永不出结果的导出按钮**（该页已有真入口；那枚点了必然空转 = §4.4 相似元素歧义）—— ⚠️ 走"
        "**渲染后摘除**（`BIND.m06`），⛔ `V.m06` 切片一行未改（切片逐行对位 ＋ `test_tail04_pages.py` "
        "把 `data-act=\"exp\" data-t=…` 名单钉在源码上）",
    ),
    (
        "ACC-RPT-PROC-001", 9,
        (("001-10", "outcome",
          "差异表的**差额列只标方向、⛔ 不整列标红**：差异表每一行本来就是差异 ⇒ 整列红**没有区分度**"
          "（§4.5 颜色只承担语义）；方向由值上的符号承载（正 = 上调 / 负 = 下调），该列自带一句说明",
          "守则 §4.5"),),
        ("守则 §4.5",),
        "；⭐ **2026-09-29** 补判据点 `001-10`（`TAIL-173`-② · 用户裁定 `A`）：差异表**差额列只标方向**"
        "（原先整列 `color:var(--dg)` ⇒ 每行都是差异、红色失去区分度）—— 方向本来就在值里"
        "（`SIG = (n>0?'+':'')+M(n)`），另给该列一句悬停说明",
    ),
)


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def patch_index(write: bool, notes: list[tuple[str, str]]) -> list[str]:
    raw = INDEX.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    for case, note in notes:
        hits = [i for i, ln in enumerate(lines) if ln.startswith(f"| `{case}` |")]
        assert len(hits) == 1, f"用例索引里 `{case}` 命中 {len(hits)} 行（要 1 行）"
        i = hits[0]
        assert note not in lines[i], f"`{case}` 的变更说明已在 ⇒ 本脚本跑过了"
        row = lines[i].rstrip()
        assert row.endswith("|"), f"`{case}` 那行不以 `|` 收尾 ⇒ 表结构变了"
        lines[i] = row[:-1].rstrip() + note + " |"
        out.append(f"  用例索引.md `{case}` 行 ⇒ 已补变更说明（{len(note)} 字）")
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
    print(f"现有用例 {len(obj['cases'])} 条 · 判据点合计 {before}")
    added = 0
    notes: list[tuple[str, str]] = []
    for case, want_old, pts, cover_add, note in PLAN:
        c = obj["cases"][case]
        ids = [p["id"] for p in c["points"]]
        assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"{case}：编号不顺延 {ids}"
        assert len(ids) == want_old, f"`{case}` 现有 {len(ids)} 点（期望 {want_old}）⇒ 基线已变，先核再改"
        c["points"].extend({"id": p, "kind": k, "claim": cl, "cover": cov}
                           for p, k, cl, cov in pts)
        for sec in cover_add:
            if sec not in c["cover"]:
                c["cover"].append(sec)
        added += len(pts)
        notes.append((case, note))
        print(f"＋ `{case}` 加 {len(pts)} 点（{pts[0][0]}）· cover 补 {list(cover_add)}")
    for line in patch_index(args.write, notes):
        print(line)

    if args.write:
        BASELINE.write_text(_dump(obj), encoding="utf-8", newline="")
        back = json.loads(BASELINE.read_text(encoding="utf-8"))
        after = sum(len(v.get("points") or []) for v in back["cases"].values())
        assert after == before + added, f"点数不对：{before} ⇒ {after}"
        print(f"\n✅ 已写回：判据点合计 {before} ⇒ **{after}**")
        print("   ⚠️ 接着：全套 pytest（带 `ACC_RESULTS_PATH`）⇒ `acc_report` ⇒ 四态锚点 5 处 ⇒ 全闸门")
    else:
        print(f"\n（`--check`：⛔ 未写；写的话 {before} ⇒ {before + added}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
