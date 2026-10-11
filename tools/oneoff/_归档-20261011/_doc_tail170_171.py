#!/usr/bin/env python
"""`TAIL-170` ＋ `TAIL-171` 的**契约面登记**（用户 2026-09-29 裁定「都按推荐做」）· 一次性脚本。

**规矩照旧**：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋
末尾一个 CRLF；**改前先做 round-trip 逐字节比对**，不等就**拒写**（⛔ 绝不文本替换交付面 JSON）。

**它做什么**（两个用例各加判据点，逐个对应本轮**新写**的 pytest）：
  1. `ACC-UI-SHELL-001`（守则驱动的壳页级判据）＋ **4 点**：
     `001-50` 导出按钮必须写清导的是什么（真导出写范围 / 无落点如实说）·
     `001-51` 字面 `disabled` 的按钮必须写清为什么灰 ·
     `001-52` 勾选表的固定列（表头 ⇄ 数据行 / 草稿行 / 合计行）同进同退 ·
     `001-53` 空态的**真机**判据在位（`tools/probe/_shell_empty.py` ㉛）；
  2. `ACC-PAY-MANUAL-001`（`m03` 手动行）＋ **1 点**：`001-08` 手动行「保存」必须挡重入；
  3. `PRD/验收/用例索引.md`：两行各补**变更说明**（日期 ＋ 判据点号 ＋ 裁定代号）。

用法：`… _doc_tail170_171.py --check` / `--write`
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
BACKUP = REPO / ".workbuddy" / "backups" / "交付面-20260929-0855-TAIL170"

SHELL_CASE = "ACC-UI-SHELL-001"
MANUAL_CASE = "ACC-PAY-MANUAL-001"

SHELL_POINTS: tuple[tuple[str, str, str, str], ...] = (
    ("001-50", "outcome",
     "**每个导出按钮都写清「导的是什么」**：4 处**真导出**写「导出当前筛选下看到的这些行」；"
     "另 3 处**没有落点**的兜底（`m06` 朴素那份 / `m08` 朴素那份 / 已取消的差异清单）**如实写「还没有落点」**"
     "—— ⛔ **不许给它们编一个范围**（编了就是假话）",
     "守则 §2.4"),
    ("001-51", "must-report",
     "**置灰必须说明原因**：模板里字面 `disabled` 的按钮，**同一处必须有 `title`** 写清「为什么灰 / 怎么解锁」"
     "（2026-09-29 实测：24 处里 **10 处**没有 ⇒ 已逐处补齐；⚠️ 全站那一批是**跨页**的事，只能成批统一）",
     "守则 §4.6 · §5.5"),
    ("001-52", "outcome",
     "**勾选表的固定列「同进同退」**：表头首格带 `.fl`（sticky-left）的表，它的**数据行 / 草稿行 / 合计行**"
     "首格也必须带 `.fl` —— 否则横向滚动时**表头那格浮着、行里那颗勾选框滚走**（错位，3 张勾选表都中招）",
     "守则 §4.4 · §5.9"),
    ("001-53", "outcome",
     "**空态有真机判据**：`tools/probe/_shell_empty.py`（㉛）在真机上把 `m04` 的日期筛到**没有数据的月** ⇒ "
     "屏幕上必须给空态（为什么空 ＋ 下一步），再筛回当月 ⇒ **正常路没被改坏**（有行、合计行还在）。"
     "⚠️ 此前**全站没有任何真机探针验过「空态」**（`_shell_states.py` 只管 加载 / 错 / 重试）",
     "守则 §2.1 · §5.4"),
)

MANUAL_POINTS: tuple[tuple[str, str, str, str], ...] = (
    ("001-12", "outcome",
     "**手动行「保存」必须挡重入**：连点两次会落**两行**（手动行**没有**「单据号唯一约束」这道天然闸 —— "
     "同一笔补两行在业务上是合法状态）⇒ 只能由界面挡：按钮禁用 ＋「保存中…」，且闸上在**本地校验之后**"
     "（校验是早退的，先上闸会把按钮卡死）",
     "守则 §5.5"),
)

SHELL_COVER_ADD = ("守则 §2.4", "守则 §4.4", "守则 §4.6", "守则 §5.4", "守则 §5.5", "守则 §5.9")
MANUAL_COVER_ADD = ("守则 §5.5",)

SHELL_NOTE = (
    "；⭐ **2026-09-29** 补判据点 `001-50`…`001-53`（`TAIL-170`/`TAIL-171` · 用户裁定「都按推荐做」）："
    "量出三件**跨页**账（导出按钮只有 1/8 写范围 · 置灰 10/24 没理由 · 固定列只钉了表头 3 张勾选表）"
    "⇒ **成批统一补齐**（⛔ 不在某一页顺手改 —— 那会造出「第四种状态」）；另补**空态的真机判据**"
    "（此前全站没有真机探针验过空态）。⛔ 判词对既有 49 点一字未改，只是新增 ＋ 该用例 `cover` 补守则那几节"
)
MANUAL_NOTE = (
    "；⭐ **2026-09-29** 补判据点 `001-12`（`TAIL-171`-②）：手动行「保存」**补挡重入** —— 与 `m04` 的 "
    "`plRowSave` 同款缺陷（连点两次落两行），⚠️ 手动行没有「单据号唯一约束」这道天然闸 ⇒ 只能界面挡"
)


def _dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def patch_index(write: bool) -> list[str]:
    raw = INDEX.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    for case, note in ((SHELL_CASE, SHELL_NOTE), (MANUAL_CASE, MANUAL_NOTE)):
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
    for case, pts, cover_add in ((SHELL_CASE, SHELL_POINTS, SHELL_COVER_ADD),
                                 (MANUAL_CASE, MANUAL_POINTS, MANUAL_COVER_ADD)):
        c = obj["cases"][case]
        ids = [p["id"] for p in c["points"]]
        assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"{case}：编号不顺延 {ids}"
        want_old = 49 if case == SHELL_CASE else 11
        assert len(ids) == want_old, f"`{case}` 现有 {len(ids)} 点（期望 {want_old}）⇒ 基线已变，先核再改"
        c["points"].extend({"id": pid, "kind": k, "claim": claim, "cover": cov}
                           for pid, k, claim, cov in pts)
        for sec in cover_add:
            if sec not in c["cover"]:
                c["cover"].append(sec)
        added += len(pts)
        print(f"＋ `{case}` 加 {len(pts)} 点（{pts[0][0]}…{pts[-1][0]}）· cover 补 {len(cover_add)} 节")
    for line in patch_index(args.write):
        print(line)

    if args.write:
        BASELINE.write_text(_dump(obj), encoding="utf-8", newline="")
        back = json.loads(BASELINE.read_text(encoding="utf-8"))
        after = sum(len(v.get("points") or []) for v in back["cases"].values())
        assert after == before + added, f"点数不对：{before} ⇒ {after}"
        print(f"\n✅ 已写回：判据点合计 {before} ⇒ **{after}**")
        print("   ⚠️ 接着：全套 pytest（带 `ACC_RESULTS_PATH`）⇒ `acc_report` ⇒ 四态锚点 5 处 ⇒ 全闸门")
    else:
        print(f"\n（`--check`：⛔ 未写；写的话判据点 {before} ⇒ {before + added}）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
