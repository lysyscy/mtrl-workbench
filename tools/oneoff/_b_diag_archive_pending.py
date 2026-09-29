#!/usr/bin/env python
"""问题 B 取证（2026-09-29 · **只读** · 一次性）：**回执说「待人工 2 条」、而 `m01` 那张卡是空的**。

用户的原始描述（`.codebuddy/memory/2026-09-29.md` §㉞）：
> 项目档案页「同步常用项目列表」回执说「**有 2 条［一个全名挂多个仓库］需人工定向 —— 去 m01 的
>  『待人工建档』卡处理**」，而**那张卡是空的** ✗。

**两条链路（先说清，⛔ 别混）**：
  · **回执的数** = 那次同步 **当场的 `plan.manual`**（原始命中）⇒ `router.sync_common_projects` 的
    `counts["manual"]` / `sample`；
  · **卡片的清单** = 那条运行记录 `detail[archive_pending]` 读回来，再**逐条按当前档案现算**
    （`archive_pending.live_items`）—— ⭐ 两个丢条条件：① 该全名**已经建过行**；② 那条 i8 名单里
    **剩下未被占用**的候选 **< 2 个**（只剩 1 个 ⇒ 下次同步系统自己就建了）。
⇒ 所以"回执说有、卡片没有"这件事**可能是设计使然**（清单是**线索**、档案现在才是**真相**）——
  ⭐ 真问题在**别的**：卡里**看不出来**那几条去哪了（`live_pending` **本来就返回 `dropped`**）。

**本脚本干什么**：把那份清单**逐条摊开**，把两个丢条条件**各算一遍并打出来** ⇒ 用数据说话
（⛔ 不猜）。⛔ **只读**：一句 `session.add` / 一个写端点都没有。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_b_diag_archive_pending.py`
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "backend"))

from _m8_rehearse2 import read_env                            # noqa: E402 —— 复用既有的 `.env` 读取

env = read_env()
url = env.get("TEST_DATABASE_URL", "")
dbname = url.rsplit("/", 1)[-1].split("?")[0] if url else ""
if not url:
    print("⛔ 根 `.env` 没有 `TEST_DATABASE_URL` ⇒ 停手")
    sys.exit(2)
if "_test" not in dbname:
    print(f"⛔ 安全闸：库名 `{dbname}` 不含 `_test` ⇒ **停手**（本脚本只打测试库）")
    sys.exit(2)
os.environ["DATABASE_URL"] = url                              # ⚠️ 必须在 import app.* 之前
print(f"=== 问题 B 取证（库 = {dbname} · 只读）===\n")

from app.core.db import session_scope                          # noqa: E402
from app.mod01_projects import archive_pending as AP           # noqa: E402
from app.mod01_projects.domain import norm_full_name           # noqa: E402
from app.mod01_projects.repository import all_projects         # noqa: E402

with session_scope() as s:
    src = AP.latest_pending(s)
    print(f"① 最近一次「常用项目列表」同步：found={src['found']} · "
          f"run_record_id={src['run_record_id']} · at={src['at']!r} · 报出 {len(src['items'])} 条待人工")
    if not src["found"]:
        print("   ⛔ 连那条记录都没认出来 ⇒ 卡片为空是**另一回事**（不是「现算丢掉了」）")
    taken, have_full = AP._snapshot(s)
    projs = all_projects(s)
    print(f"② 当前档案：{len(projs)} 行 · 已占用仓库名 {len(taken)} 个 · 已有全名 {len(have_full)} 个")

    print("\n③ 逐条「现算」（两个丢条条件各算一遍 —— ⭐ 这就是卡片为空的原因清单）：")
    for i, raw in enumerate(src["items"], 1):
        full = str(raw.get("name_full") or "")
        whs = [str(w) for w in (raw.get("warehouses") or []) if str(w)]
        have = norm_full_name(full) in have_full
        left = [w for w in whs if w not in taken]
        why = ("① 已经建过行" if have else
               ("② 剩下的候选不足 2 个（" + "、".join(whs) + " 里只剩 " + "、".join(left or ["0 个"]) + "）"
                if len(left) < 2 else "✅ 仍然成立（本该出现在卡上）"))
        print(f"   [{i}] {full}")
        print(f"       phid={raw.get('phid') or '（空）'} · 当时报的仓库={whs} · reason={raw.get('reason') or '（无）'}")
        print(f"       现算 ⇒ 已有行={have} · 未被占用={left} ⇒ 丢弃理由：{why}")

    live = AP.live_items(s)
    print(f"\n④ 卡片实际会画：{len(live)} 条（报出 {len(src['items'])} − 现算丢掉 "
          f"{len(src['items']) - len(live)} = {len(live)}）")
    print(f"   `live_pending` 回包里的 `dropped` = {len(src['items']) - len(live)}"
          " —— ⭐ 这个字段**已经算好了**；问题只剩「壳上有没有把它画出来」。")
    print("\n（⛔ 本脚本没有写任何东西；测试库保持原样。）")
