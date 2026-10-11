#!/usr/bin/env python
"""`A3`（`m04` 付款计划逐页）· 把 3 条**新写**的守卫登记进契约面（一次性契约面改动 · 2026-09-29）。

**规矩照旧**（动交付面 `.json` ⛔ 绝不文本替换）：
  `json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋ 末尾一个 CRLF；
  **改前先做 round-trip 逐字节比对**，不等就**拒写**。

**它做什么**（两件）：
  1. `验收基线.json`：`ACC-PLAN-UI-001`（`m04` 页级）加 **3 个判据点** `001-09`…`001-11`
     —— 对应本批**新写**的 3 条 pytest（空态 / 置灰说明 / 挡重入），并把 `cover` 补上守则那三节；
  2. `PRD/验收/用例索引.md`：该用例行补**变更说明**（日期 ＋ 判据点号 ＋ 出处）。

用法（工程根）：`… _doc_a3_m04.py --check` / `--write`
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
BACKUP = REPO / ".workbuddy" / "backups" / "交付面-20260929-0845-A3"

CASE = "ACC-PLAN-UI-001"

NEW_POINTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "001-09", "outcome",
        "**筛选后 0 行 ≠ 一片空白**：列表空时必须给空态（**为什么空 ＋ 下一步**：换个筛选 / 去导入），"
        "⛔ 不许只剩表头 —— 用户会以为页面坏了、或不知道自己筛过头了（守则 §2.1）",
        "守则 §2.1 · §5.4",
    ),
    (
        "001-10", "must-report",
        "**置灰必须说明原因**：「删除选中」未勾选时禁用，**同一处**必须写明「未勾选时置灰 —— 先勾选行再用」"
        "（守则 §4.6：灰按钮不给理由；⛔ 不靠用户自己猜）",
        "守则 §4.6 · §5.5",
    ),
    (
        "001-11", "outcome",
        "**手动行「保存」必须挡重入**：连点两次会落**两行完全相同**的计划行 —— 而「同月完全相同的行」"
        "是本业务的**合法状态**（后端**故意不挡**重复、由「重复上报」提示）⇒ 只能由界面挡（按钮禁用 ＋"
        "「保存中…」），否则用户莫名多出一行（守则 §5.5）",
        "守则 §5.5",
    ),
)

COVER_ADD = ("守则 §2.1", "守则 §4.6", "守则 §5.5")

INDEX_NOTE = (
    "；⭐ **2026-09-29** 补判据点 `001-09`…`001-11`（`A3` 逐页 · `m04`）：本批**新写** 3 条守卫 —— "
    "**筛不到行必须给空态**（原先同一处槽位是空串 ⇒ 只剩表头）· **「删除选中」置灰必须写清为什么**"
    "（同批实测：全站 24 处 `disabled` 里 **10 处没有 `title`**，本条只钉本页，其余归跨页）· "
    "**手动行「保存」必须挡重入**（连点会落两行相同计划行 —— 后端**故意不挡**重复 ⇒ 只能界面挡）；"
    "⛔ 断言**未改**既有 8 条的判词，只是新增 ＋ 该用例 `cover` 补「守则 §2.1 / §4.6 / §5.5」"
)


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def patch_index(write: bool) -> str:
    raw = INDEX.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    hits = [i for i, ln in enumerate(lines) if ln.startswith(f"| `{CASE}` |")]
    assert len(hits) == 1, f"用例索引里 `{CASE}` 命中 {len(hits)} 行（要 1 行）"
    i = hits[0]
    assert INDEX_NOTE not in lines[i], "变更说明已在 ⇒ 本脚本跑过了"
    row = lines[i].rstrip()
    assert row.endswith("|"), f"该行不以 `|` 收尾 ⇒ 表结构变了：{row[-40:]!r}"
    lines[i] = row[:-1].rstrip() + INDEX_NOTE + " |"
    if write:
        INDEX.write_text(nl.join(lines), encoding="utf-8", newline="")
    return f"  用例索引.md `{CASE}` 行 ⇒ 已补变更说明（{len(INDEX_NOTE)} 字）"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    # ⚠️ 必须 `newline=""`（否则 `\r\n` 会被折成 `\n` ⇒ round-trip 永远不等）
    raw = BASELINE.read_text(encoding="utf-8", newline="")
    obj = json.loads(raw)
    rt = _dump(obj)
    if rt != raw:
        print("round-trip 逐字节比对：⛔ 不一致（⛔ 别写！）")
        for i, (a, b) in enumerate(zip(raw, rt)):
            if a != b:
                print(f"   首个差异 @{i}：原 {a!r} vs 我的 {b!r}")
                break
        return 1
    print("round-trip 逐字节比对：✅ 一致")
    print(f"交付面备份在位：{'✅' if BACKUP.exists() else '⛔ 先备份再改'} {BACKUP}")
    if not BACKUP.exists():
        return 1

    case = obj["cases"][CASE]
    ids = [p["id"] for p in case["points"]]
    assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"编号不顺延：{ids}"
    assert len(ids) == 8, f"`{CASE}` 现有 {len(ids)} 点（期望 8）⇒ 基线已变，先核再改"
    before = sum(len(v.get("points") or []) for v in obj["cases"].values())
    print(f"现有用例 {len(obj['cases'])} 条 · 判据点合计 {before} · `{CASE}` 现 {len(ids)} 点（{ids[0]}…{ids[-1]}）")

    case["points"].extend({"id": pid, "kind": kind, "claim": claim, "cover": cover}
                          for pid, kind, claim, cover in NEW_POINTS)
    for sec in COVER_ADD:
        if sec not in case["cover"]:
            case["cover"].append(sec)
    print(f"＋ `{CASE}` 加 {len(NEW_POINTS)} 点（001-09…001-11）· cover 补 {[s for s in COVER_ADD]}")
    print(patch_index(args.write))

    if args.write:
        BASELINE.write_text(_dump(obj), encoding="utf-8", newline="")
        back = json.loads(BASELINE.read_text(encoding="utf-8"))
        after = sum(len(v.get("points") or []) for v in back["cases"].values())
        assert after == before + len(NEW_POINTS), f"点数不对：{before} ⇒ {after}"
        print(f"\n✅ 已写回：判据点合计 {before} ⇒ **{after}**")
        print("   ⚠️ 接着：全套 pytest（带 `ACC_RESULTS_PATH`）⇒ `acc_report` ⇒ 四态锚点 5 处 ⇒ 全闸门")
    else:
        print(f"\n（`--check` 模式：⛔ 未写任何文件；写的话判据点会变成 {before + len(NEW_POINTS)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
