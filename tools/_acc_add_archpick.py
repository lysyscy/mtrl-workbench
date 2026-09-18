# -*- coding: utf-8 -*-
"""§四 契约同步（一次性 · 2026-09-18）：`TAIL-45` 补两点（`ACC-PRJ-SYNC-001/001-12 · 001-13`）。

① `001-12` = 「待人工建档」清单**留得住** ＋ 只认**最近一次成功同步** ＋ **逐条按当前档案现算**
② `001-13` = **选定一个仓库 ⇒ 就地建行**（候选只许来自 i8 名单 · 全名已有行即拒 · 仓库名被占用即拒）

⚠️ 走**结构操作**（`json.load` → 追加 → `dump(indent=2)`）；⚠️ `newline="\\n"`（交付面文件是 **LF**）；
⚠️ **幂等**：点已存在 ⇒ 跳过。
"""

import json
import pathlib

BASE = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\PRD\验收\验收基线.json")

NEW = [
    {"id": "001-12", "kind": "outcome", "cover": "§2.4.2",
     "claim": "**「待人工建档」那几条必须留得住、且只认最近一次成功同步**：全名对应 **≥2 个仓库**时"
              "系统**不自动建**、显式列出（原口径「列出让用户选，只建选中的那个」），而这清单原先"
              "**只在同步回执里出现一次**（刷新即丢）⇒ 必须能稳定读回**最近一次成功的「常用项目列表」同步**"
              "报出的那几条，并**逐条按当前档案现算**（已建过行的 / 候选仓库不足两条的**当场丢掉**）；"
              "⚠️ 同步**失败**（i8 取数失败 ⇒ 一行没建、档案没变）**不改这份清单** ⇒ 跳过没带清单的记录、"
              "认的是**最近一次成功**那次；⛔ 仍**不回溯**更早的成功记录（成功即换新，防「对着已解决的清单白干」）"},
    {"id": "001-13", "kind": "must-report", "cover": "§2.4.2",
     "claim": "**选定一个仓库 ⇒ 就地建行**（把「列出」补成「可点」）：候选只能**来自那次同步报出的 i8 名单**"
              "（§9.4：仓库名是 i8 的，⛔ 手填即拒）· 该全名**已有档案行**即拒（决策 2：普通项目 ↔ 仓库 = 1 : 1，"
              "也防「别人刚挑过」）· 该仓库名**已被别行占用**即拒；建档一律走**唯一出口**"
              "`repository.create_project`、类型判定走 `classify_name`（⛔ 不在页面层另立规则）；"
              "建完**该条即从清单消失**，且**同一项目的其余仓库不再建行**"},
]


def main() -> int:
    d = json.loads(BASE.read_text(encoding="utf-8"))
    c = d["cases"]["ACC-PRJ-SYNC-001"]
    have = {p["id"] for p in c["points"]}
    added = 0
    for p in NEW:
        if p["id"] in have:
            print(f"    （{p['id']} 已存在 ⇒ 跳过）")
            continue
        c["points"].append(p)
        added += 1
    print(f"ACC-PRJ-SYNC-001: {len(have)} → {len(c['points'])} 点（+{added}）")
    print("   criterion:", str(c.get("criterion"))[:120])

    d["asof"] = "2026-09-18"
    BASE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    back = json.loads(BASE.read_text(encoding="utf-8"))
    ids = [p["id"] for p in back["cases"]["ACC-PRJ-SYNC-001"]["points"]]
    print("\n=== 复核 ===")
    print("asof =", back["asof"], "· ACC-PRJ-SYNC-001 点数 =", len(ids))
    print("  ", ids)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
