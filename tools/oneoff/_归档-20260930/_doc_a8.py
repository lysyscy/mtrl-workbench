#!/usr/bin/env python
"""`A8` 逐页（`imp` 数据导入）的**契约面登记** · 一次性（2026-09-29）。

**它做什么**：`ACC-UI-SHELL-001` ＋ `001-63`：**四步条同屏只许一条 ＋ 当前步要亮**
（用户 2026-09-26 报的「两条一模一样的四步条」修复，此前**零机器判据**）＋ 用例索引同行补变更说明。

用法：`… _doc_a8.py --check` / `--write`
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
        "id": "001-63",
        "kind": "outcome",
        "claim": "**四步条同屏只许一条，且当前步要亮**：用户 2026-09-26 按截图报过「**两条一模一样的四步条**」"
                 "⇒ 裁定「**只留卡里那条**」（修复落在 `V.imp` 的 `return`：⛔ 不再在卡外又画一遍），"
                 "但**此前没有任何机器判据** —— `lgSteps` / `IMP_STEPS` 只出现在 `legacy.js` 里"
                 "（测试与探针零引用）。⇒ 本批挂上三条：① `V.imp` 里画步骤条**只许 1 次**"
                 "（⚠️ **剥块注释再数** —— 注释里引述的那个写法不算实现）；"
                 "② 四步 = ① 选域与文件 / ② 列映射 / ③ 预览校验 / ④ 确认落库；"
                 "③ 当前步 `on`、走过的 `dn`。真机那半（屏幕上真的只有一条、当前步真的亮）由 "
                 "`tools/probe/_shell_legacy.py` ⑳ 段看着（它真上传真解析走完 ①②③）",
        "cover": "守则 §5.9 · §4.4",
    },
)

INDEX_NOTE = (
    "；⭐ **2026-09-29（`A8` 逐页 · `imp` 数据导入）** 补判据点 `001-63` **四步条同屏只许一条 ＋ 当前步要亮** —— "
    "用户 2026-09-26 报的「两条一模一样的四步条」当年只靠一句注释记着（`lgSteps` / `IMP_STEPS` 零引用）"
    "⇒ 本批挂上判据；⚠️ 同批**订正一处过期注释**（`lgSteps` 原写「三步条 / `at` = 0/1/2」，而 `IMP_STEPS` "
    "是四项）＋ **零行为改动**（该页真机面早由 `tools/probe/_shell_legacy.py` ⑳ 段覆盖：①②③④ · 真上传真解析）"
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
    assert INDEX_NOTE not in lines[i], "这一段变更说明已在 ⇒ 本脚本跑过了"
    row = lines[i].rstrip()
    assert row.endswith("|"), "该行不以 `|` 收尾 ⇒ 表结构变了"
    lines[i] = row[:-1].rstrip() + INDEX_NOTE + " |"
    if write:
        INDEX.write_text(nl.join(lines), encoding="utf-8", newline="")
    return [f"  用例索引.md `ACC-UI-SHELL-001` 行 ⇒ 已补 `A8`（{len(INDEX_NOTE)} 字）"]


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
    assert len(ids) == 62, f"`ACC-UI-SHELL-001` 现有 {len(ids)} 点（期望 62）⇒ 基线已变，先核再改"
    c["points"].extend(POINTS)
    print(f"＋ `ACC-UI-SHELL-001` 加 {len(POINTS)} 点（{POINTS[0]['id']}）")
    for line in patch_index(args.write):
        print(line)

    if not args.write:
        print(f"\n（`--check`：⛔ 未写；写的话 {before} ⇒ {before + len(POINTS)}）")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    backup = REPO / ".workbuddy" / "backups" / f"交付面-{stamp}-A8"
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
