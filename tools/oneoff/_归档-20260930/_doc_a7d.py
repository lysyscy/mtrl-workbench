#!/usr/bin/env python
"""`TAIL-182`（`A` 案 · 启动失败横幅不许盖住内容）的**契约面登记** · 一次性（2026-09-29）。

**它做什么**：`ACC-UI-SHELL-001` ＋ `001-62`：**启动失败横幅不许盖住内容**（原 `position:fixed;top:0;z-index:9999`
⇒ 压在页首、卡头按钮全点不着）＋ `PRD/验收/用例索引.md` 同行补一句变更说明。

用法：`… _doc_a7d.py --check` / `--write`
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
        "id": "001-62",
        "kind": "outcome",
        "claim": "**启动失败横幅不许盖住内容**：`core.js::bootErrorBanner()` 那条横幅原是 "
                 "`position:fixed;left:0;right:0;top:0;z-index:9999` ⇒ **压在页面之上** ⇒ 页首那一带的"
                 "**卡头按钮全都点不着**（真机实测：`#jcTradeBtn` 被它挡住、`intercepts pointer events` "
                 "连重试 57 次；`elementFromPoint` 拿到的正是它）—— 守则 §4.6 的反例原文就是"
                 "「提示条盖住可点区（本仓真例：`.toast` 吃掉浮层点击）」，同一族。"
                 "⇒ 改成**进布局流**（插在 `main` 里 `#view` 之前 ＋ `flex:0 0 auto`，⛔ 不挂 `body` —— "
                 "`html,body{overflow:hidden}` 会把它裁掉），且**不会滚走**（滚动容器是 `.view`，它是兄弟）。"
                 "判法：横幅 `position` 不是 `fixed`/`absolute` ＋ 下缘在卡头之上 ＋ **卡头按钮正中间 "
                 "`elementFromPoint` 就是那枚按钮**（真机 ㉞ · `tools/probe/_shell_bootbar.py`）",
        "cover": "守则 §4.6 · §5.5",
    },
)

INDEX_NOTE = (
    "；⭐ **2026-09-29 用户裁定 `A`（全局件 · `TAIL-182`）**：**启动失败横幅不许盖住内容** —— 它原是 "
    "`position:fixed;top:0;z-index:9999`（压在页首、卡头按钮全点不着：真机 `intercepts pointer events` "
    "连重试 57 次）⇒ 改成**进布局流**（插在 `main` 里 `#view` 之前 ＋ `flex:0 0 auto`；⛔ 不挂 `body` —— "
    "`html,body{overflow:hidden}` 会裁掉它），且**不会滚走**（滚动容器是 `.view`）；判据 `001-62` ＋ 真机新段 **㉞**"
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
    return [f"  用例索引.md `ACC-UI-SHELL-001` 行 ⇒ 已补 `TAIL-182`（{len(INDEX_NOTE)} 字）"]


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
    assert len(ids) == 61, f"`ACC-UI-SHELL-001` 现有 {len(ids)} 点（期望 61）⇒ 基线已变，先核再改"
    c["points"].extend(POINTS)
    print(f"＋ `ACC-UI-SHELL-001` 加 {len(POINTS)} 点（{POINTS[0]['id']}）")
    for line in patch_index(args.write):
        print(line)

    if not args.write:
        print(f"\n（`--check`：⛔ 未写；写的话 {before} ⇒ {before + len(POINTS)}）")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    backup = REPO / ".workbuddy" / "backups" / f"交付面-{stamp}-A7d"
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
