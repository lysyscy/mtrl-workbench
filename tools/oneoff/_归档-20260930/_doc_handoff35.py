# -*- coding: utf-8 -*-
"""收尾：把本轮（`TAIL-35` = `m04` 导入 ＋ 手动行 ＋ 拆件）写进**执行情况**与**当日 memory 日志**。

⚠️ 幂等；按行首标记定位。
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / ".workbuddy" / "plans" / "执行情况-主文档.md"
MEM = ROOT / ".workbuddy" / "memory" / "2026-09-18.md"

NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
text = DOC.read_text(encoding="utf-8")

if "`TAIL-35` 销号" in text:
    print("已是目标状态 —— 无需重复执行")
    sys.exit(0)

lines = text.splitlines(keepends=True)


def find_one(prefix: str, start: int = 0) -> int:
    hit = [i for i, l in enumerate(lines) if l.startswith(prefix) and i >= start]
    if len(hit) != 1:
        raise SystemExit(f"⛔ 行首标记 `{prefix}` 命中 {len(hit)} 次（应 1）")
    return hit[0]


# ---- ① 版本行
v = find_one("> **当前版本**：")
lines[v] = (
    f"> **当前版本**：{NOW}（实测）· ⭐⭐ **`TAIL-35` 销号：`m04` 的 Excel 导入 ＋ 手动行两条壳侧入口接通**"
    "（手动行 `POST /api/m04/plans` · 导入 `POST /api/m04/import`（multipart））；⚠️ **加完把 `router.py` 顶到 668 行 "
    "> 600 禁合入** ⇒ **当场拆件**（`plan_api_router.py` ＋ 中立件 `project_views.py`）⇒ 回到 **576 行** · "
    "⚠️ **原台账写的「导入三步预览」是推测**，按原型订正为**一步式** · ⏭️ 下一轮 = 其余页（`m02`/`m09`/`m12`/`m13`/`m14`/`m15`）\n"
)
print("① 版本行已更新")

# ---- ② §⑥ 插入
j = find_one("## ⑥ 当前状态")
lines.insert(j + 1, f"""
- **⭐⭐ 本轮（{NOW} · 实测）`TAIL-35` 销号：`m04` 的 Excel 导入 ＋ 手动行**（用户 2026-09-18 指示「继续按推荐、只做不需要裁定的」）
  · **背景**：接 `m04` 时这两条**故意没接**（如实标注「未接通」）—— 因为都不适用「改内存 → 调后端」那套短路径；
    硬接会变成「造演示行的假成功」与「填了却存不进去」，**比不做更糟**。本轮补齐。
  · **① 手动行**：新增 **`POST /api/m04/plans`**（复用 `plan_manual.manual_row_payload` ＋ `repo.create/update_manual_row`，
    与 PRG 端点 `POST /m04/row/save` **同一份判定**）；壳侧 **从原型逐字取回**三个本地动作 ——
    `plRowAdd`/`plRowEdit`（**本地草稿层、不落库** ⇒ 一行不用改）、`plRowCancel`（原就未改）；
    只把 `plRowSave` 改成 async 走后端。⭐ **判定全部留后端**：⛔ 前端不再复写「年月必填 / 项目必选 / 金额非负」三道校验。
    ⚠️ **口径核对**：《说明书》§4.3.3.1 只写「**年月必填**」、**项目未标必填**（后端「允许为空 ⇒ 标未匹配」是对的）；
    原型前端要求「项目必选」是原型自己的实现 ⇒ 按「判定唯一出口 = 后端」不保留。
    ⚠️ **失败时保留已填内容**（§4.3.3.1）：catch 分支**不清草稿层**（已用断言钉住）。
  · **② 导入**：新增 **`POST /api/m04/import`**（**multipart**，`parse_workbook` → `attach_projects` → `repo.merge_month`，
    §9.5 幂等）；壳侧恢复原型**一步式**弹窗（选月 ＋ 选文件 ＋ 导入按钮）。
    ⚠️ **订正一处台账错误**：`TAIL-35` 原写「导入 = 选文件 → 预览 → 确认**三步**（与服务端三步页同一形态）」——
    **查原型后确认是错的**：原型 `plImport` 是**一步式弹窗、没有预览步**（服务端 `/m04/import` 也是一页一步）
    ⇒ 按「原型即交互规格」**不做预览**，并把台账描述订正。
  · **③ ⚠️ 拆件（本轮自抓的一处硬线违规）**：加完两段后 `mod04_plan/router.py` 涨到 **668 行 > 600**（`doc_audit` 的 `T5`
    **当场报红**）⇒ 按纪律拆件：新建 **`plan_api_router.py`**（JSON 端点）＋ **`project_views.py`**（项目匹配视图 ·
    **中立件**：`project_briefs` / `project_label`，**防 `router ↔ api` 循环 import** —— 本仓踩过这个坑）
    ⇒ `router.py` 回到 **576 行**，`router.include_router(plan_api_router)` 汇总。
  · ⭐ **真机证据（写 → 回读 → 复原，全部复原到库 0 行）**：
    · 手动行：新增 ⇒ 回读（审查正确判为「**无单据号**」· `is_manual=True`）⇒ 负数 / 非法月份**双 400 拒** ⇒ 删除复原；
    · 导入：**造样例 xlsx**（表头 `项目 / 其他支出…/ 该流程金额 / 本月预付款金额 / 付款时间 / 付款方式 / 备注`）⇒
      `created:1` ⇒ 回读（审查判「单据号查不到」· `is_manual=False`）⇒ 删除复原 ⇒ **直查库 `plan_row` = 0 行**；
    · 壳侧：`_shell_smoke.py` 新增 `⑥b` —— 点「＋ 手动新增计划行」**真的开出草稿行**（8 个可填格），验完收起、**不落库**；零 console 错误。
  · ✅ **验证**：断言 **12**（`test_wired_m04.py（已归档，付款计划页面已退出）（已归档，付款计划页面已退出）`，其中 1 条是**改写**的：原断言钉「未接通」这个**临时状态**，
    接线后完成使命 ⇒ 改钉「已接通」＋加 5 条接线断言）· ⭐ **反向灵敏度 8/8**（**首跑抓出 3 处问题**：
    2 处变异点**不唯一**（PRG 与 JSON 端点同名调用）⇒ 改断言为「进函数体取切片」；
    1 处 **子串假绿**（`_manual_row_payload(` 含 `manual_row_payload(`）⇒ 加词边界）· MD5 逐字节复原 ·
    四态 **487 不变** · 六把尺子全 0（`chain_audit` 仍红 = `TAIL-04`/未开工，与本轮无关）。
  · ⏭️ **下一轮**：**其余页接线**（`m02` i8 接入层 / `m09` 特殊费用月报表 / `m14` 规则配置 这三页后端已实现、只差接线；
    `m10`/`m12`/`m13`/`m15` 属未开工阶段）。⚠️ `TAIL-30`-③（B③ 指认）属 **C 类，待用户一句话**。
  · ℹ️ **§15 A 类现剩 8 条**，其中 5 条是 **M5/M6 硬等**（`TAIL-04`/`TAIL-07`/`TAIL-21`/`TAIL-25`/`TAIL-32`②–⑤）、
    2 条**持续**（`TAIL-06` 行数 / `TAIL-20` `T7a`）、1 条**进行中**（`TAIL-27` 其余页）——
    ⇒ **不需要用户裁定、且当下能动的只剩 `TAIL-27` 其余页**。

""")
print("② §⑥ 已插入本轮条目")

# ---- ③ §⑦ 换新一轮
s = find_one("> ⭐ **本轮任务（2026-09-18 01:4")
ends = [i for i, l in enumerate(lines) if l.startswith("> ⏭️ **下一件**：") and "TAIL-35" in l]
if not ends:
    raise SystemExit("⛔ §⑦ 找不到结尾锚")
e = ends[-1]
if not (s < e and e - s < 30):
    raise SystemExit(f"⛔ §⑦ 区间异常：{s} → {e}")
lines[s:e + 1] = [
    f"> ⭐ **本轮任务（{NOW} · 实测）—— `TAIL-35` 销号：`m04` 的导入 ＋ 手动行**\n",
    "> ✅ 手动行 `POST /api/m04/plans`（判定复用 `manual_row_payload`）＋ 导入 `POST /api/m04/import`（multipart）；\n",
    "> 壳侧 `plRowAdd`/`plRowEdit` **从原型逐字取回**（本地草稿层，一行不改）、`plRowSave` 改走后端、导入恢复原型**一步式**弹窗。\n",
    "> ⚠️ **顺带自抓一处硬线违规**：`router.py` 涨到 668 行 ⇒ **当场拆件**（`plan_api_router.py` ＋ 中立件 `project_views.py`）⇒ 576 行。\n",
    "> ⚠️ **订正**：原台账写「导入三步预览」是**推测**；原型是**一步式**，按原型不做预览。\n",
    "> ⭐ **真机**：手动行（写/回读/双 400 拒/复原）· 导入（造样例 → created:1 → 回读 → 复原，**直查库 0 行**）· 壳自检（点按钮**真的开出草稿行**）。\n",
    "> ✅ **验证**：断言 **12** 条 · **反向灵敏度 8/8**（首跑抓出 2 处不唯一 ＋ 1 处子串假绿，已改紧）· 四态 **487 不变** · 六把尺子全 0。\n",
    "> ⏭️ **下一件**：**其余页接线**（`m02`/`m09`/`m14` 后端已实现、只差接壳；`m10`/`m12`/`m13`/`m15` 属未开工阶段）。\n",
]
print("③ §⑦ 已换成新一轮")

DOC.write_text("".join(lines), encoding="utf-8")
print(f"写好：{DOC.name}")

# ---- ④ memory 日志（append-only）
log = MEM.read_text(encoding="utf-8")
if "TAIL-35 销号" in log:
    print("④ memory 日志已有本轮条目 —— 跳过")
else:
    log += f"""

---

## {NOW[11:]} · `TAIL-35` 销号：`m04` 导入 ＋ 手动行（用户指示「只做不需要裁定的」）

**做法**：新增 `plan_api_router.py`（`POST /api/m04/plans` 手动行 ＋ `POST /api/m04/import` multipart 导入 —— 判定一律复用
`plan_manual.manual_row_payload` / `importer` / `repo.merge_month`）；壳侧 `plRowAdd`/`plRowEdit` **从原型逐字取回**
（它们是**本地草稿层、不落库** ⇒ 接线后一行不用改），只把 `plRowSave`（落库）与 `plImportOk`（上传）改走后端。

**⭐ 三条新经验**
1. **加端点会把 router 顶破 600 行** —— 本轮 668 行被 `doc_audit` 的 `T5` **当场报红**。
   ⇒ ⭐ **拆件时先看有没有「两个路由件都要用的私有函数」**：有 ⇒ 必须先抽**中立件**
   （本轮 = `project_views.py`），否则 `router ↔ api` **循环 import**。
2. **台账里自己写的描述也可能是推测** —— 原 `TAIL-35` 写「导入 = 选文件 → 预览 → 确认三步」，**查原型后是错的**：
   原型 `plImport` 是**一步式、没有预览**。⇒ ⭐ **写台账也要回原型核一遍**（别把自己的推测写成口径）。
3. ⭐ **反向灵敏度再次抓出「断言被同族代码喂饱」**：`manual_row_payload(` 在 `router.py` 里有 **2 处**（PRG ＋ JSON）
   ⇒ 变异点不唯一（报 SKIP）；改成 `_manual_row_payload(` 后又**照样绿**（**子串**喂饱）
   ⇒ 断言改成「**进各自函数体取切片**」＋ **词边界** `(?<![A-Za-z_])` 才变红。通法不变：**断言要钉在那一处逻辑自己的作用域里**。

**⚠️ 一处需用户知情**：《说明书》§4.3.3.1 只写「**年月必填**」、**项目未标必填**（后端「允许为空 ⇒ 标未匹配」是对的）；
原型前端却要求「项目必选」⇒ 按「判定唯一出口 = 后端」（`D18`）**不保留前端那道**。

**数字**：四态 **487 不变** · 六把尺子全 0 · 反向灵敏度 **8/8** · 断言 **12** 条 · 真机写库 2 次均**复原**（直查库 `plan_row` = 0）。
`TAIL-35` 销号（§15 A 类 9 → **8** · 已销号 30 → **31**）。
"""
    MEM.write_text(log, encoding="utf-8")
    print("④ memory 日志已 append")

print("\n下一步：跑 tools/doc_audit.py 复核")
