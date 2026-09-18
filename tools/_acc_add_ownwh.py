# -*- coding: utf-8 -*-
"""给 `ACC-PRJ-OWN-001` 加点 —— `TAIL-39`「兜底前先跑一次 i8 仓库名单」（2026-09-18）。

⚠️ **加点**（不是新增用例）⇒ 按纪律**只动 `验收基线.json` 一处**：
   说明书 `MOD-01` 能力 5/11 的验收列**本来就挂** `ACC-PRJ-OWN-001`，`用例索引.md` / `MOD-01.md` /
   `05-任务分解.md` 都是**用例级** ⇒ 不改。
⚠️ 改 JSON 两个细节：① 走**结构操作**；② **文件结尾没有换行** ⇒ ⛔ 别多写 `\n`（先做「往返逐字节一致」自检）。

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\_acc_add_ownwh.py`
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
        "id": "001-15",
        "kind": "must-report",
        "cover": "§2.5.1",
        "claim": (
            "**兜底前必须先跑一次 i8 仓库名单**（用户 2026-09-18 口述裁定：「在兜底前，系统的设计里应该有"
            "去仓库跑了一环这个逻辑，而且如果跑完没结果要在界面上提醒用户」）：链路 C 兜底 = **手填仓库名**"
            "新建具体小微 ⇒ 用户**凭猜**填就会留下与 i8 不符的**假档案行**，日后 i8 真建了仓库 ⇒ 系统**再建一行**。"
            "⇒ 建档前先查：**命中** ⇒ 给出它挂的项目全名（同名挂多条全给，⛔ 不替用户选）；**名单里没有** ⇒ "
            "如实说「没有」＋ 讲清后果（将来会再建一行）＋ 要人**显式确认**才允许建档；"
            "**取不到名单** ⇒ `degraded` ＋ 明说「**这不等于**名单里没有」（⛔ 两件事不许混为一谈）；"
            "⛔ 全程**不许静默**"
        ),
    },
    {
        "id": "001-16",
        "kind": "outcome",
        "cover": "§2.7.4 · §3.1",
        "claim": (
            "查名单这一环**只读**且判定走唯一出口：不落库、不建档、名单本身也不留档（与 "
            "`POST /api/m02/sync/warehouses` 同一口径）；名字比较 = **去首尾空白后精确比** —— ⛔ 不许把"
            "项目全名的**尾码剥离**（§2.3.2）用到**仓库名**上（仓库名是唯一标识 / 候选键 §2.7.4，剥了会认错行）；"
            "⚠️ 查名单**要登录 i8**、可能**强踢**在线用户 ⇒ `allow_kick` **默认 False**、**原样透传**，"
            "壳侧必须在**二次确认之后**才传 `True`（`D9`）"
        ),
    },
]


def main() -> int:
    path = resolve_baseline(None)
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    if json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8") != raw:
        print("⛔ 往返**不是**逐字节一致 —— 先别改")
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
    data["asof"] = date.today().isoformat()

    bak = path.with_name(f"_backup-acc_ownwh-{date.today().strftime('%Y%m%d-%H%M')}.json")
    shutil.copy2(path, bak)
    path.write_bytes(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    print(f"✅ {CASE}：{len(case['points'])} 点（新增 {added or '无'}）· asof={data['asof']} · 备份 {bak.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
