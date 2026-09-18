"""本轮台账与交接的更新（`TAIL-27` 第 8 页 `m09` 接线）。

- 计划 §15：`TAIL-27` 状态列 —— 已接清单加 `m09`、余下减一。
- 执行情况 §⑥：新起一条「本轮」块（最前面）。
- 执行情况 §⑦：新起一条「本轮任务」块（最前面）。

⚠️ 每处都断言锚**唯一命中**，改完立刻 `doc_audit` 复核。
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
EXEC = ROOT / ".workbuddy" / "plans" / "执行情况-主文档.md"

# ============================================================ ① 计划 §15 · TAIL-27 行
plan = PLAN.read_text(encoding="utf-8")
OLD_TAIL27 = ("**壳已建 · `m03`/`m01`/`m04`（含导入 ＋ 手动行）/`m05`/`m06`/`m08`/`m07` 已接**）"
              " ⇒ ⏭️ **余下 = `m02`/`m09`/`m10`/`m12`/`m13`/`m14`/`m15`**")
NEW_TAIL27 = ("**壳已建 · `m03`/`m01`/`m04`（含导入 ＋ 手动行）/`m05`/`m06`/`m08`/`m07`/`m09` 已接**）"
              " ⇒ ⏭️ **余下 = `m02`/`m10`/`m12`/`m13`/`m14`/`m15`**")
assert plan.count(OLD_TAIL27) == 1, f"⛔ TAIL-27 状态列锚命中 {plan.count(OLD_TAIL27)} 次（期望 1）"
plan = plan.replace(OLD_TAIL27, NEW_TAIL27)

# 「已接」清单里也补一句 m09 的做法（接在 m05 那句之后，保持行内叙述顺序）
OLD_NOTE = "⏭️ **下一步 = 其余 11 页接线 ＋ 删旧渲染层**"
NEW_NOTE = ("· **`m09` 已接线**（2026-09-18）：新增 `mod09_fee/api.py`（5 个 JSON 端点：读 `fee` ＋ 写 `add`/`name`/`amount`/`delete`，"
            "本层零判定、与 PRG 端点**同一出口** `service.act_*`）；壳侧删演示容器 `AWF`（含 3 个月演示手填值），"
            "四个写动作改走后端，候选与默认项目也由 `reloadM09()` 从后端落定（原先候选读 `ntPjList()`、默认项目**加载时求值**）；"
            "⭐ 顺带订正一处静默偏差：自动项原按 **单据日期** `iv.dd` 前缀算，口径要的是**核算年月** `inv_detail.ym`。"
            "⏭️ **下一步 = 其余 6 页接线 ＋ 删旧渲染层**")
assert plan.count(OLD_NOTE) == 1, f"⛔ 下一步锚命中 {plan.count(OLD_NOTE)} 次"
plan = plan.replace(OLD_NOTE, NEW_NOTE)
PLAN.write_text(plan, encoding="utf-8")
print("✅ 计划 §15 · TAIL-27 行已更新")

# ============================================================ ② 执行情况 §⑥ / §⑦
exec_src = EXEC.read_text(encoding="utf-8")

SEC6 = "## ⑥ 当前状态（**每次更新这一段**）\n\n"
SEC7 = "## ⑦ 本次任务（**替换成你要做的这一件**）\n\n"
assert exec_src.count(SEC6) == 1, "⛔ §⑥ 锚不唯一"
assert exec_src.count(SEC7) == 1, "⛔ §⑦ 锚不唯一"

BLOCK6 = """- **⭐⭐ 本轮（2026-09-18 08:20 · 实测）`TAIL-27` 第 8 页 `m09`（特殊费用月报表）接线**
  · **背景**：`m09` 的后端**一直有服务端渲染页**（`/m09`，`mod09_fee` 的 `service`/`view` 都在），
    但**没有 JSON API** ⇒ 壳里只能读原型模拟数据。本轮补 API ＋ 接线（与 `m07` 同一形态）。
  · **① 后端**：新增 **`backend/app/mod09_fee/api.py`（5 个端点）** —— 读 `GET /api/m09/fee?ym=&pj=`；
    写 `POST /api/m09/fee/add` · `/fee/name` · `/fee/amount` · `/fee/delete`。
    ⚠️ **本层零判定** —— 组装调 `service.build_page_data`、写动作调 `service.act_*`（与 PRG 端点 `/m09/add` `/m09/cell`
    **同一出口**）；金额出**字符串**（`numeric(18,2)` 精度保护）；`ops` 列按 `domain.PAGE_ONLY_KEYS` **剔除**；
    写动作**恒 HTTP 200 ＋ `ok` 标志**（「金额不合法」是 §5.5 的**可预期拒绝**，那句中文要原样给用户看）。
    `mod09_fee/router.py` 末尾 `router.include_router(api_router)` 汇总（`main.py` 不用改，同 `m07`）。
  · **② 壳侧**（11 处落地，一段一键脚本）：删演示容器 `AWF`（含 3 个月演示手填值）与只服务它的 `awfMut`/`awfMonth`；
    改 4 个后端派生态（`AWF_ROWS`/`AWF_AUTO`/`AWF_TOTAL`/`AWF_PJS`）；`awfList()` 仍返回 `[[项名, 金额], …]`
    ⇒ **`V.m09` 切片一行不用改**（`ui_parity` U1 零漂移）；四个写动作改走 `awfAct()`（**失败也看回执**、恒以后端为准重拉）；
    切月份 / 切项目 / 重置**都重新取数**；`WIRED` 加 `m09`；`boot()` 加一路 `soft('特殊费用月报表', reloadM09)`。
  · ⭐ **顺带订正两处「不报错地坏」**：
    · **自动项取数口径**：原壳按 **单据日期** `iv.dd` 前缀从 `IVs` 自算；口径要的是**核算年月**（`inv_detail.ym`，
      `domain` 顶部已注明）⇒ 两者在"单据日期跨月"时**不一致且不报错**。接线后读后端。
    · **默认项目「加载时求值」**：原 `awfPj = (pjSort(ntPjList())[0]||{name:''}).name` 写在数据层 ——
      `PJs` 是**异步填充**的 ⇒ 取数回来时它早已定死成空（**静默失去默认项目**）。改为由后端回包的 `project` 落定。
    ⚠️ **候选改与写路径同源**：原先读 `pjKeysOfRows(ntPjList())`（档案表全部，"能显示"但不保证后端认）⇒
      改读后端 `projects`（唯一出口 `build_candidates`）：**选得到的就写得了**。
  · **③ 一处工具改进**：`ui_parity` 的 `U2b`（已接线页不得留演示数组）原先只认 `const` 声明 ——
    而 `m09` 的演示容器在原型里是 **`let AWF = {…}`** ⇒ **漏掉它**。改成**逐页显式登记声明关键字**
    ＋ **必须带内容才算演示**（`= {}` / `= []` 是后端填充用的**空容器**）。
    ⚠️ 中途一度改成「三种一律认」⇒ **误报** `let MACH6 = {}` / `let WHM = {}`（它们是活容器）——
    说明原型里有条真实约定：**演示数据用 `const`、活容器用 `let`**。两个方向都验过（注入 `let AWF = {…}` ⇒ 报红；
    现状 ⇒ 0 误报；MD5 复原）。
  · ⭐ **真机证据**：
    · 读：`⑪ m09` 8 条 —— 表在线 · 演示容器**真的没了**（`typeof AWF === 'undefined'`）· 候选 == 后端（12 vs 12）·
      手填行数 == 后端 `manuals` · 自动项/合计 == 后端 · **切非默认项目仍与后端一致** ·
      **后端不认的项目被后端归一成候选第一个**；零 console 错误。
    · 写：`⑪b` 真机往返 —— 点「＋ 增加手填项」**真的落库并回读**（0 → 1 行）⇒ 点「删除」**回到原样**（后端也是 0）。
    · curl 补齐其余写动作：改名（`油卡使用`）· 金额合法（`12,345.67`）· **非法金额 `abc` ⇒ `ok:false` 且原值不变** ·
      **负数 `-88.5` 允许**（§5.5 最宽松一档）⇒ 复原 ⇒ **直查库 `fee_manual_item` = 0 行**。
  · ✅ **验证**：断言 **17**（`test_wired_m09.py`）· ⭐ **反向灵敏度 18/18**（**首跑抓出 3 处假绿**：
    断言放错用例 / 「后端剔除页面专用列」被文档注释里的 `domain.PAGE_ONLY_KEYS` **子串喂饱** / 变异点没改干净）
    · MD5 逐字节复原 · 四态 **487 不变** · 六把尺子全 0（`chain_audit` 仍红 = `TAIL-04`/未开工，与本轮无关）。
  · ⏭️ **下一轮**：`m02` i8 接入层（后端**已有** JSON API：`/api/m02/fetch/plan|preview|run` · `/sync/*` · `/fetch/records`，
    只差壳侧适配与接线）；`m10`/`m12`/`m13`/`m15` 后端仍是**空模块**（只有 `__init__.py`）⇒ 属未开工阶段。
    `m14` 注意：壳里那页是**规则配置**（剔除规则/分类/小微关键词），与后端 `/m14/settings`（系统设置 · **留服务端**）
    **不是同一页** ⇒ 要接得先给「剔除规则落库」补后端能力（新能力，走 §四 四处同步）。
    ⚠️ `TAIL-30`-③（B③ 指认）属 **C 类，待用户一句话**。

"""

BLOCK7 = """> ⭐ **本轮任务（2026-09-18 08:20 · 实测）—— `TAIL-27` 第 8 页 `m09` 特殊费用月报表接线**
> ① 后端 `mod09_fee/api.py`（5 端点，零判定）＋ `router` 汇总；② 壳侧删 `AWF` 演示容器、四个写动作走后端、
> 候选与默认项目由后端落定、`WIRED`/`boot` 纳管；③ ⭐ 顺带订正「自动项按单据日期算」与「默认项目加载时求值」两处静默偏差；
> ④ `ui_parity` 的 `U2b` 支持 `let` 声明的演示容器（正反两面都验过）。
> 真机：读 8 条 + 写往返 1 条 + curl 补齐改名/金额/非法拒绝/负数 + 复原（库 0 行）。
> 断言 17 · 反向灵敏度 18/18 · 四态 487 不变 · 六把尺子全 0。

"""

exec_src = exec_src.replace(SEC6, SEC6 + BLOCK6, 1)
exec_src = exec_src.replace(SEC7, SEC7 + BLOCK7, 1)
EXEC.write_text(exec_src, encoding="utf-8")
print("✅ 执行情况 §⑥ / §⑦ 已更新")
sys.exit(0)
