#!/usr/bin/env python
"""`TAIL-180`（`B` 案 · `m11` 行身份区固定）的**契约面登记** · 一次性（2026-09-29）。

**规矩照旧**：`json.loads` → 改 dict → `json.dumps(indent=2, ensure_ascii=False)` ＋ 每行 CRLF ＋
末尾一个 CRLF；**改前先 round-trip 逐字节比对**（不等 ⇒ 拒写）；**改前先备份交付面**。

**它做什么**：
  · `ACC-UI-SHELL-001` ＋ `001-61`：**集采台账的行身份区必须钉住，且偏移必须按屏幕实测**
    （`m11` 20 列 · 330 行，4 个可编辑列在最右 ⇒ 往右滚去填时要看见自己在给哪条合同填；
    ⚠️ 本页 **偏移必须量出来**（列宽随视口变：29 / 34px）、**每渲染一次都要重量**、
    **钉的必须是连续前缀**）；
  · `PRD/验收/用例索引.md` 同行的变更说明补一句（`B` 案已落地 ＋ 顺带查出的 `TAIL-182`）。

用法：`… _doc_a7b.py --check` / `--write`
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
        "id": "001-61",
        "kind": "outcome",
        "claim": "**集采台账的行身份区要钉住，且偏移必须按屏幕实测**：`m11` 合同主表 **20 列 · 330 行**，"
                 "而 **4 个可编辑列**（付款方式 / 备注 / 存档号 / 寄回日期）**正好在最右** ⇒ 往右滚去填它们时，"
                 "**行身份区（勾选框 ＋ 序号 ＋ 合同日期 ＋ 材料名）必须留在视野里**（否则看不见在给哪条合同填，"
                 "**会填错行**）。⚠️ 本页三条硬要求：① **偏移必须量出来**（列宽随视口变 ——"
                 "「勾选框」列 1440/1920 时 29px、**2560 时 34px**，静态算式必错位）；"
                 "② **每渲染一次都要重量**（`render()` 重建整张表，隐藏 / 显示贸易公司三列还会改剩下的列宽）；"
                 "③ **钉的必须是连续前缀**（序号与材料名中间隔着「合同日期」⇒ 一并钉上）。"
                 "屏幕上是否真严丝合缝 + 隐藏列后是否重量：真机 **㉝**（`tools/probe/_shell_jcpin.py`）",
        "cover": "守则 §5.9 · §4.2",
    },
)

INDEX_NOTE = (
    "；⭐ **2026-09-29 用户裁定 `B`（`A7` 逐页 · `m11`）**：`TAIL-180` 已按「钉住**行身份区**"
    "（勾选框 ＋ 序号 ＋ 合同日期 ＋ 材料名）」落地 —— 判据 `001-61`；⚠️ 实现**不能照抄大表那份静态算式**"
    "（真机实测本页列宽随视口变：勾选框列 29 / 34px）⇒ 走**渲染后按表头实测设 `left`** ＋ **每渲染一次重量**"
    "＋ 隐藏三列后重量；⚠️ 同批量测**另查出一条全局件的问题**：启动失败横幅（`core.js::bootErrorBanner`，"
    "`position:fixed;top:0`）**盖住页首并吃掉点击**（卡头按钮点不着）⇒ 立 `TAIL-182` 请用户裁"
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
    return [f"  用例索引.md `ACC-UI-SHELL-001` 行 ⇒ 已补 `B` 案 ＋ `TAIL-182`（{len(INDEX_NOTE)} 字）"]


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
    assert len(ids) == 60, f"`ACC-UI-SHELL-001` 现有 {len(ids)} 点（期望 60）⇒ 基线已变，先核再改"
    c["points"].extend(POINTS)
    print(f"＋ `ACC-UI-SHELL-001` 加 {len(POINTS)} 点（{POINTS[0]['id']}）")
    for line in patch_index(args.write):
        print(line)

    if not args.write:
        print(f"\n（`--check`：⛔ 未写；写的话 {before} ⇒ {before + len(POINTS)}）")
        return 0

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    backup = REPO / ".workbuddy" / "backups" / f"交付面-{stamp}-A7b"
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
