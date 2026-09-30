# -*- coding: utf-8 -*-
"""收尾：把 `TAIL-35`（`m04` 导入 ＋ 手动行）销号写进**开发计划**（§15 ＋ §14.3 ＋ 计数 ＋ `TAIL-27` 状态）。

⚠️ 幂等；按**行首标记**定位、整行替换。
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

raw = PLAN.read_bytes()
if "TAIL-35` | `m04` 的导入与手动行**都已接通**".encode("utf-8") in raw:
    print("已是目标状态（TAIL-35 已销号）—— 无需重复执行")
    sys.exit(0)

lines = raw.decode("utf-8").splitlines(keepends=True)
TODAY = dt.datetime.now().strftime("%Y-%m-%d")
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def find_one(prefix: str, start: int = 0) -> int:
    hit = [i for i, l in enumerate(lines) if l.startswith(prefix) and i >= start]
    if len(hit) != 1:
        raise SystemExit(f"⛔ 行首标记 `{prefix}` 命中 {len(hit)} 次（应 1）")
    return hit[0]


# ---- ① §15 A 类：删 TAIL-35 行
i = find_one("| `TAIL-35` |")
del lines[i]
print("① §15 A 类：删除 TAIL-35 行")

# ---- ② §15 四、已销号：插一行
j = find_one("### 四、已销号")
k = next(idx for idx in range(j, j + 6) if lines[idx].startswith("|---|---|"))
lines.insert(k + 1, (
    "| `TAIL-35` | `m04` 的导入与手动行**都已接通** | **两件都做完**（" + TODAY + "）：① **手动行** —— 新增 "
    "`POST /api/m04/plans`（复用 `plan_manual.manual_row_payload`，与 PRG 端点**同一份判定**）；壳侧恢复原型"
    "「表内增行」草稿层（`plRowAdd`/`plRowEdit` 是**本地草稿**，一行不用改），`plRowSave` 改走后端。② **导入** —— "
    "新增 `POST /api/m04/import`（multipart，复用 `parse_workbook`→`attach_projects`→`repo.merge_month`）；壳侧恢复"
    "原型**一步式**弹窗（选月 ＋ 选文件），⚠️ **原先台账写的「三步预览」是推测**，按原型订正为**一步式、无预览**。"
    "③ ⚠️ 加完两段后 `router.py` 涨到 **668 行 > 600 禁合入** ⇒ **拆件**：新建 `plan_api_router.py`（JSON 端点）＋ "
    "`project_views.py`（项目匹配视图 · **中立件**，防 `router ↔ api` 循环 import）⇒ `router.py` 回到 **576 行**。"
    "**真机**：手动行「写 → 回读（审查判「无单据号」）→ 双 400 拒 → **复原**」全通；导入「造样例 xlsx → 导入 created:1 → "
    "回读 → **复原**」全通；壳自检「点＋手动新增 ⇒ **真的开出草稿行**（8 个可填格）」全通。断言 **12** 条 · "
    "反向灵敏度 **8/8**（首跑抓出 2 处 SKIP ＋ 1 处**子串假绿**，已改紧）· MD5 逐字节复原 · 四态 **487 不变** · 六把尺子全 0 | " + TODAY + " |"
) + "\n")
print("② §15 已销号：插入 TAIL-35 行")

# ---- ③ §15 顶部计数
c = find_one("> **当前状态（")
lines[c] = f"> **当前状态（{NOW}）**：A 类 **8** 条 · B 类 **1** 条 · C 类 **1** 条 · 已销号 **31** 条。\n"
print("③ §15 顶部计数：A 类 9 → 8 · 已销号 30 → 31")

# ---- ④ §14.3：TAIL-35 行改「已做」
m = find_one("| `TAIL-35` **`m04` 的「Excel 导入」与「手动行」")
lines[m] = (
    "| `TAIL-35` **`m04` 的「Excel 导入」与「手动行」缺壳侧入口** | ✅ **已做**（" + TODAY + "） "
    "| ③ **与 `TAIL-27` 同族**（单独的「接线」轮会把同一批文件来回进出）；后端判定早已就绪，只差 JSON 端点 ＋ 壳 "
    "| 已完成（手动行 `POST /api/m04/plans` ＋ 导入 `POST /api/m04/import` ＋ 壳侧接线 ＋ 拆件），见交接 §⑥ ＋ §15 已销号 |\n"
)
print("④ §14.3：TAIL-35 标「已做」")

# ---- ⑤ §15 TAIL-27 状态列：补 m04（导入/手动行）
t = find_one("| `TAIL-27` |")
lines[t] = lines[t].replace(
    "| 立刻 | 进行中（**壳已建 · `m03`/`m01`/`m04`/`m05`/`m06`/`m08`/`m07` 已接**） |",
    "| 立刻 | 进行中（**壳已建 · `m03`/`m01`/`m04`（含导入 ＋ 手动行）/`m05`/`m06`/`m08`/`m07` 已接**）"
    " ⇒ ⏭️ **余下 = `m02`/`m09`/`m10`/`m12`/`m13`/`m14`/`m15`** |",
)
if "含导入 ＋ 手动行" not in lines[t]:
    raise SystemExit("⛔ TAIL-27 状态列没改到（锚不匹配）")
print("⑤ §15 TAIL-27：状态列补上「m04 含导入 ＋ 手动行」＋ 余下页清单")

PLAN.write_bytes("".join(lines).encode("utf-8"))
print(f"\n写好：{PLAN.name} · {len(raw)} → {PLAN.stat().st_size} 字节")
print("下一步：跑 tools/doc_audit.py（T6 查台账 / §14.3 一致 / T5 查行数）")
