# -*- coding: utf-8 -*-
"""给 `ACC-PRJ-OWN-001` 加点 —— `TAIL-42`「人工覆盖三类判定」（2026-09-18）。

⚠️ **这是"加点"，不是"新增用例"** ⇒ 按纪律**只动 `验收基线.json` 一处**：
   `用例索引.md` / `MOD-01.md` / `05-任务分解.md` 那三处是**用例级**的，加点不改它们
   （说明书 `MOD-01` 能力 5「三类项目自动判定（双轨 ＋ **人工可覆盖**）」的验收列**本来就挂** `ACC-PRJ-OWN-001`）。
⚠️ 改 JSON 的两个细节（本仓实测过）：① 走**结构操作**；② **本文件结尾没有换行** ⇒
   写入时**不许**多写一个 `\n`（先做「往返逐字节一致」自检，过了再改）。

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\_acc_add_prj_type.py`
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acc_report import resolve_baseline  # noqa: E402

CASE = "ACC-PRJ-OWN-001"

NEW_POINTS = [
    {
        "id": "001-12",
        "kind": "outcome",
        "cover": "§2.2.1",
        "claim": (
            "三类判定的**人工覆盖**（根因：有的壳全名**不含「小微」**⇒ 被误判成普通项目）："
            "人能把一条行在「普通项目 ⇄ 小微壳」之间纠正 —— 走**唯一出口**（`repository.set_type`），"
            "并**留痕**记下类型前后值（人工介入判定是例外，例外要有据）；"
            "⛔ 「具体小微」**不由人工指定**（它要挂在壳下并占一个仓库名，由链路产生）⇒ 明确拒；"
            "已经是该类型 ⇒ 明确拒（不写空留痕）"
        ),
    },
    {
        "id": "001-13",
        "kind": "outcome",
        "cover": "§2.2.1",
        "claim": (
            "人工覆盖**要「粘住」**：该全名在档案里**已是壳**（含人工纠正来的）⇒ 之后同族仓库的"
            "**判定与建档一律按壳处理**（走判定唯一出口的 `manual_override`，⛔ 不是另写一条规则）—— "
            "否则下次同步又会把同族仓库建成普通项目，材料侧再遇同一仓库仍会重复处理"
        ),
    },
    {
        "id": "001-14",
        "kind": "must-report",
        "cover": "§2.3.1 · §2.7.2",
        "claim": (
            "改类型的**仓库名与不变式**（仓库名是候选键 §2.7.4）：改成「普通项目」**必须显式给出仓库名**"
            "（不给 ⇒ 拒，⛔ 不猜一个填上；被别的行占用 ⇒ 拒）；改成壳 ⇒ 仓库名**让出去**（壳不挂仓库）；"
            "该行**下有具体小微** ⇒ 拒并列出它们（§2.7.2 壳 ⇄ 小微不变式，⛔ 不造孤儿行）"
        ),
    },
]


def main() -> int:
    path = resolve_baseline(None)
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))

    again = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    if again != raw:
        print("⛔ 往返**不是**逐字节一致 —— 先别改（多半是结尾换行的事）")
        return 1

    case = data["cases"][CASE]
    have = {p["id"] for p in case["points"]}
    added = []
    for p in NEW_POINTS:
        if p["id"] in have:
            print(f"· {p['id']} 已在，跳过")
            continue
        case["points"].append(p)
        added.append(p["id"])

    data["asof"] = date.today().isoformat()          # ⚠️ 项目当前时点 = 2026-09-18

    bak = path.with_name(f"_backup-acc_prj_type-{date.today().strftime('%Y%m%d-%H%M')}.json")
    shutil.copy2(path, bak)
    path.write_bytes(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    after = json.loads(path.read_bytes().decode("utf-8"))
    print(f"✅ {CASE}：{len(case['points'])} 点（新增 {added or '无'}）· asof={data['asof']}")
    print(f"   备份 = {bak.name}")
    print(f"   复核：条数 {len(after['cases'][CASE]['points'])} · 结尾无多余换行 = "
          f"{not path.read_bytes().endswith(b'\n')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
