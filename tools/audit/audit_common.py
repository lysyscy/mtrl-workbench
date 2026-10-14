#!/usr/bin/env python
"""`doc_audit` 公共件 —— 常量表 ＋ 文档扫描基础设施（**纯搬运**，无逻辑改动）。

拆因：`doc_audit.py` 涨到 597 行（<600 但贴着 `T5` 硬上限）。
拆法：常量与基础设施 → 本件；`T1–T4` → `audit_drift.py`；`T5/T6` → `audit_meta.py`；
`doc_audit.py` 只留 `main()` 与报告打印（薄壳）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT: Path = Path(__file__).resolve().parents[2]

RED, YELLOW, SKIP = "红", "黄", "忽略"

# --------------------------------------------------------------- 数据（可维护）

#: 已废除术语 → (缘由, 现在的正确说法)
#: ⚠️ 加条目要**依据一次真实的改名/删除**，别把「你觉得不好听」的词加进来。
RETIRED_TERMS: dict[str, tuple[str, str]] = {
    "pay_amount_src": ("字段已删（2026-09-16）", "金额只取 ApproveAmt；该列已取消"),
    "付款金额（源）": ("字段已取消（2026-09-16）", "三金额：审批金额 / 付款金额 / 已付金额"),
    "四金额": ("已改为三金额（2026-09-16）", "三金额"),
    "四个金额字段": ("已改为三个（2026-09-16）", "三个金额字段"),
    "print/sign.py": ("模块已删（2026-09-15）", "print/signatures.py"),
    "render.py::build_print_html": ("函数已删（2026-09-15）", "service.render_notice_html()"),
    "SOURCE_FIELDS": ("常量已删（2026-09-16）", "—"),
}

# ------------------------------------------------------------ 已撤项（`T8` 的真源）
#
# ⭐⭐ **「如何标记才能让人/AI 永久记住某功能已被取消？」—— 答案就是这张表。**
#
# ⚠️ 为什么不能只写注释：撤项目前散落在**代码注释**里（如 `shell/core.js` 那句
#    「⛔ 别再加回来」）—— 而**注释没人每次读** ⇒ 下次（包括 AI）照着一片**残骸**
#    把它再做一遍（本项目已发生过：`mod12_diff` 撤了、判据还在、目录还在、壳里还渲染）。
# ⭐ 本表的用法**不是"留个记录"**，而是**守卫**：`T8` 每次 `doc_audit` 跑批都扫**代码面**，
#    命中即报 —— 这才是"永久记住"（**机器每次把它端到你面前**，⛔ 不靠人记得）。
#
# 与 `RETIRED_TERMS` 的分工：
#   `RETIRED_TERMS` = 「**术语改名**」（扫 `.md` 文档，提示"该改叫 X"）；
#   本表           = 「**整个东西被撤了**」（扫**代码**，提示"不得复活 / 还有残骸"）。
#
# 形态：`标识符 → (理由＋依据, 正确的替代路径, 是否已清干净)`
#   ⭐ 第 3 项 `clean` 是关键：
#     · `True`  ⇒ 已清干净 ⇒ 再出现就报**红**（复活 = 真出错）
#     · `False` ⇒ 还有残骸   ⇒ 每次报**黄**（提醒"这里还留着，去清"）
#   ⇒ 这样机制**一上线就有区分力**，而且**立刻暴露所有残骸**（⛔ 不用先清完才能上线）。
CANCELLED: dict[str, tuple[str, str, bool]] = {
    # ⚠️⚠️ 用户 2026-09-20 裁定：**MOD-12「差异登记」整个页面取消**。
    #    依据 = §5.8.3 明写「差异归属恒为「**库存单据**」——**不独立成模块**」
    #    ⇒ 差异**从来不该有自己的页面**；它只是**调整单的产物**。
    "mod12_diff": ("已撤（2026-09-20 用户裁定）· §5.8.3「差异归属「库存单据」（**不独立成模块**）」",
                   "差异去**库存单据打调整单**（`API.m08Adjust`）；差异表由后端按调整单算（`m06`）", True),
    "m12List": ("同上 —— 这 4 个接口指向已撤的页", "`m08Adjust`（写调整单）＋ `m06` 的差异表（读）", True),
    "m12Create": ("同上", "`m08Adjust`", True),
    "m12Delete": ("同上", "调整单的撤销走 `m08` 自己的路", True),
    "m12Status": ("同上", "差异状态由调整单派生，⛔ 不单独存", True),
    # ⭐ 表 `diff_record` 也已按用户裁定 drop（迁移 `c9e5f1a3b7d2`）。
    #   ⚠️ 登记它**不是**为了"禁提这个名字"（迁移文件里必然还要写），
    #   而是提醒：**谁要是再建这张表 / 再给它配接口，就是复活已撤的页**。
    "diff_record": ("表已 drop（用户 2026-09-20 夜裁定）· 迁移 `c9e5f1a3b7d2`",
                    "⛔ 不重建：差异的载体是**调整单**（`m08`），产出是**差异表**（`m06` 按调整单算）", True),
    # ⚠️⚠️ 用户 2026-09-22 裁定：**「库存单据手动导入」整个模块取消**（"给删掉，不要了"）。
    #    i8 接口不可用时的口径改为：**显式报错待人处理**（原因 + 请稍后重试），⛔ 不做手动兜底入口。
    #    已删：`import_api.py` / 壳 `V.m08imp` ＋ `imp08*` 动作 ＋ `API.m08ImpMeta` ＋ `LOADERS['库存导入']`。
    "m08imp": ("已撤（2026-09-22 用户裁定「库存单据手动导入给删掉，不要了」）",
               "库存数据唯一入口 = **i8 抓取**（`API-03`）；i8 不可用 ⇒ 显式报错待人处理", True),
    "imp08": ("同上 —— 壳侧动作 / 表单 id 已删", "（无替代：抓取是唯一入口）", True),
    "m08ImpMeta": ("同上 —— `API.m08ImpMeta` 已删", "（无替代）", True),
    "mod08_inv.import_api": ("同上 —— 编排与三条端点已删",
                             "抓取走 `fetch_service`（`upsert_details` 是同一套幂等落库出口）", True),
    # ⚠️ 2026-09-22/23（`TAIL-75` `B5c` / `B5c-2`）：**「过程资料历史导入」页与它的专属端点全部退休**
    #    —— 同一件事不留两个入口 ⇒ 过程资料的导入**只走「数据导入」页**（通用导入面）。
    #    已删：壳 `V.m06imp` ＋ `imp06*` 动作 ＋ `API.m06ImpData` ＋ 后端 `/api/m06/import/*` 五条
    #    ＋ `mod06_proc/import_api.py` 整件。⛔ 别再建"第二条导入路"。
    "m06imp": ("已撤（2026-09-22 `B5c`：过程资料导入整体搬进「数据导入」页）",
               "过程资料导入 = **通用导入面** `/api/imp/m06_proc/*`（壳「全局 → 数据导入」）", True),
    "imp06": ("同上 —— 壳侧动作已删", "同上（通用面四步：选域与文件 → 列映射 → 预览 → 确认）", True),
    "m06ImpData": ("同上 —— `API.m06ImpData` 已删（2026-09-23 `B5c-2`）",
                   "`API.impOptions(domain)` ⇒ `GET /api/imp/{domain}/options`", True),
    "mod06_proc.import_api": ("同上 —— 编排与五条端点已删",
                              "落库仍走 `importer.commit`（域钩子 `imp_spec.commit` 调的就是它）", True),
    # ⚠️⚠️ 用户 2026-09-23 裁定 **`B`**：**「历史付款导入」旧页撤掉**（`TAIL-75` `B5b` 第三步）——
    #    该域已挂上通用导入面 ⇒ 同一件事只留一个入口（与 `m06imp` 同款处置）。
    #    ⚠️ **代价已记账**（用户拍板时知情）：旧页按**源表列位置**读（无表头也读得动），
    #       通用面按**列名**认 ⇒ 判据 `ACC-FLOW-IMPORT-001/001-01` 同批**改写**（撤页的已知代价）。
    #    已删：壳 `V.m05imp` ＋ `imp05*` 四个动作 ＋ `IMP05` / `IMP05_STEPS` / `reportHtml` ＋
    #    `API.m05ImpMeta` ＋ `PAGE_LOAD`/`LOADERS` 那两行 ＋ NAV/TITLE/WIRED 三处登记
    #    ＋ 后端 `/api/m05/import/*` 四条 ＋ `mod05_flow/import_api.py` 整件。
    #    ⛔ 别再建"第二条导入付款流水的路" —— 入口 = 通用面 `/api/imp/m05_flow/*`。
    "m05imp": ("已撤（2026-09-23 用户裁定 `B`：历史付款导入整体搬进「数据导入」页）",
               "历史付款导入 = **通用导入面** `/api/imp/m05_flow/*`（壳「全局 → 数据导入」选 `历史付款流水`）", True),
    "imp05": ("同上 —— 壳侧四个动作（`imp05Pick/Parse/Ok/Rollback`）已删",
              "同上（通用面四步：选域与文件 → 列映射 → 预览 → 确认）", True),
    "m05ImpMeta": ("同上 —— `API.m05ImpMeta` 已删（列契约改由域声明 `imp_spec.SPEC` 给）",
                   "`GET /api/imp/m05_flow/schema`", True),
    # ⚠️ 2026-09-23（`TAIL-75` 余项 · **用户裁定**）：「集采台账」页里那个**页内导入向导**撤掉 ——
    #    用户原话：「**导入基本上只会在我刚开始使用系统时导入一次，之后就实时更新了**，所以只留通用面就好」
    #    ⇒ 与 `m05imp`/`m06imp` 同款处置（同一件事不留两个入口）。同批清掉 `m04` 的旧端点。
    #    已删：壳 `ACT.jcImportOpen/jcImportPick/jcImportRun/jcImportPickSheet/jcImportPj/jcImportMap/
    #    jcImportOk` ＋ `jcImportShow`/`jcImpResult` ＋ `jcImp*` 那组状态与工具 ＋ `CHG` 三处登记
    #    ＋ `BIND.m11` 注入的「⬆ Excel 导入台账」按钮 ＋ `API.m11ImportParse/m11ImportCommit`
    #    ＋ 后端 `/api/m11/import/parse|commit` 两条 ＋ 它们的入参 class 与 `_b64()`。
    #    ⛔ 别再建"第二条集采台账导入路" —— 入口 = 通用面 `/api/imp/m11_jc/*`。
    "jcImport": ("已撤（2026-09-23 用户裁定：集采台账页内导入向导整体搬进「数据导入」页）",
                 "集采台账导入 = **通用导入面** `/api/imp/m11_jc/*`（壳「全局 → 数据导入」选 `集采台账`）", True),
    "m11Import": ("同上 —— `API.m11ImportParse/m11ImportCommit` 与 `/api/m11/import/*` 两条端点已删",
                  "同上（列映射与匹配口径仍只有一份：`import_service.match_and_apply`）", True),
    # ⚠️ 2026-09-23（**同一条裁定**）：`m04` 付款计划的**页内导入面**同批连件删除 ——
    #    已删：`POST /api/m04/import/parse`（`TAIL-69` 第①步）· `/api/m04/import/confirm`（第②步）·
    #    `/api/m04/import`（一步式，2026-09-22 起**已软退役**的路由）· 入参 class `TokenRequest`。
    #    ⚠️ **域内解析出口保留**（`importer.parse_workbook` / `attach_projects` / `stage_payload` /
    #    `restore_rows` / `match_summary`）—— 与 `m05` 留 `parse_rows`、`m06` 留 `parse_sheet` 同款
    #    （域业务不随页面存亡；通用面的域声明也用着前两件）。
    "m04/import": ("已撤（2026-09-23 用户裁定：付款计划页内导入面整体搬进「数据导入」页）",
                   "付款计划导入 = **通用导入面** `/api/imp/m04_plan/*`（壳「全局 → 数据导入」选 `付款计划`）", True),
    "mod05_flow.import_api": ("同上 —— 编排与四条端点已删",
                              "落库仍走 `importer.commit`（域钩子 `imp_spec.commit` 调的就是它）；"
                              "`importer.parse_rows`（五列批解析）**保留**，与 `m06` 留 `parse_sheet` 同款", True),
}

#: `T8` 扫描面 —— **只扫代码**（文档面由 `T2`/`RETIRED_TERMS` 管）。
#: ⚠️ `demo/`（原型）**故意不在内** —— 原型是**历史留痕**，它留着 `V.m12` 是**正确的**。
#: ⚠️⚠️ **`backend/alembic/versions/` 也故意不在内** —— ⭐ 实测踩过：
#:   把迁移链扫进来后，**表名在迁移里出现是正常的**（`create_table` / `drop_table` 必然要写它），
#:   结果一条撤项登记凭空多出 **25 条黄**、还夹 1 条红（红在"新迁移的文件名"那句上）。
#:   ⇒ ⭐ **迁移链是"历史记录"，不是"复活"** ⇒ 本守卫⛔ 不扫它。
CANCELLED_SCAN_GLOBS: tuple[str, ...] = (
    "backend/app/**/*.py", "backend/app/**/*.js", "backend/app/**/*.html",
    "backend/tests/*.py",
    # ⭐⭐ 2026-09-24 修：工具**已迁进 `tools/audit/`**，而这里原先写着 `tools/*.py`（只匹配根那一层、
    #    实测根下 **0 件**）⇒ **`T8` 的「工具面」整片失守且静默**（`clean=True` 的撤项若在尺子里复活，
    #    没有任何尺子看得见）。⇒ 改成**按目录明确列举**（⛔ 不用一刀切递归）：
    #    · **收** `tools/audit/`（尺子自己）与 `tools/probe/`（真机探针 —— 它若还在测已撤功能，
    #      那**是真问题**，必须报）；
    #    · ⛔ **不收** `tools/mut/`（变异脚本**天生要引用**已删标识符才造得出违规）与
    #      `tools/oneoff/`（一次性脚本 = 历史叙事，与 `plans/archive/归档-*` 同性质）。
    # ⚠️⚠️ 2026-09-24 晚再修（`T18` 立起来当天抓的**第二例**）：**`tools/*.py` 已摘掉** ——
    #    09-24 那次只把 glob 改对了目录，却**留着根那一条**，而**根下 0 件 python** ⇒ 它**一条都不命中**
    #    = 那片"没人扫"。⭐ 教训：**"改对了主路径"不等于"清掉了死条目"** —— 后者只有 `T18` 看得见。
    "tools/audit/*.py", "tools/probe/*.py",
)

#: `T8` 跳过本机制自己（这张表与它两个使用者**必然**要写出那些标识符）
CANCELLED_SKIP_RELS: tuple[str, ...] = (
    # ⭐ 2026-09-24 修：这三条原写作 `tools/audit_common.py` 等（**旧路径**）⇒ 文件搬进 `tools/audit/`
    #    之后**永远匹配不到**（死配置）。而它们正是"必然写出那些标识符"的文件（`CANCELLED` 表自身 ＋
    #    两个使用者）⇒ 不豁免就会自己报自己。
    "tools/audit/audit_common.py", "tools/audit/audit_drift.py", "tools/audit/doc_audit.py",
)

#: ⭐⭐ **「原型 / 文档里留着撤项残片」是有意的，⛔ 别去清它**（用户 2026-09-20 裁定）。
#:
#: ⚠️ 来由：清理 `MOD-12` 时发现原型侧（`demo/`）与一堆文档里都有它的残片，而**清原型的代价极大** ——
#:   `V.m12` 是**原型切片**、`ui_parity` 按它**逐行对位**（仓 / 面必须同进同退），
#:   且一清就要连**原型导读的行号表** / **`_smoke` 的四检断言** / **追溯表** / **验收基线**一起重算。
#: ⇒ ⭐ 用户裁定：**原型不动，改为"在原型与文档各加一个标记说明"**。
#:
#: ⭐ 这是**对的做法**，理由是它符合本仓早已有的分层：
#:   · 原型 = **规格的留痕** —— 改它等于抹掉"当初为什么会撤"的证据；
#:   · 它同时是 `ui_parity` 的**基准** ⇒ 单边删会立刻报红。
#:   · ⭐ **2026-09-30 订正**（`TAIL-200` `A` 案）：`ui_parity` 的基准**已换成「最新那份壳快照」**
#:     ⇒ 上面那条"单边删会报红"**已不是理由**（原型现在只是**规格留痕**，不再是任何尺子的基准）——
#:     `U1`/`U5` 随后已**整半退场**（`TAIL-201`）。
#:     ⛔ 但**裁定不变**：原型与文档里的残片**照旧别清** —— 它记的是"当初为什么会撤"。
#:
#: ⭐ 已加的标记（**共 4 处，⛔ 别删**）：
#:   ① 原型 `demo/材料报表自动化工作台-交互原型.html` 的 `V.m12` 切片内（`V.m12=()=>{` 之后 6 行）
#:   ② 壳 `backend/app/web/index.html` 的 `V.m12` 切片内（**与 ① 逐行完全相同** —— 这样 `ui_parity` 的 `U1` 不漂）（⭐ 2026-09-30 `TAIL-201`：`U1` 已**退场** ⇒ 这条"不漂"的理由过期，本行只为留痕）
#:   ③ `demo/原型导读.md`：`m12` 段头的醒目说明 ＋ 两张表里 `MOD-12` 行的 ⛔ 标记
#:   ④ `PRD/99-追溯表.md`：`DEV-R-06` 行下的说明
#:
#: ⚠️ 所以本表**只登记"代码里的复活"**，⛔ **不管原型 / 文档里的残片** —— 那些是**留痕**。
CANCELLED_KEEP_IN_PROTO_AND_DOCS: tuple[str, ...] = (
    "demo/材料报表自动化工作台-交互原型.html",
    "demo/原型导读.md",
    "PRD/99-追溯表.md",
    "PRD/05-任务分解.md",
    "PRD/验收/验收基线.json",
)

#: **强豁免**：行文本身就在声明「它废了 / 别再用」⇒ 直接忽略，连黄都不报
HARD_EXEMPT: tuple[str, ...] = (
    "已取消", "已作废", "已删除", "已废除", "已删", "取消「", "不再取", "不再用",
    "勘误", "旧术语", "别再引入", "不得再写",
    # ⭐ 2026-09-23 补：本仓撤项（页面 / 端点）一贯写「**已下架**」「**已退休**」——
    #   它们与「已删」是同一个意思，却因不在词表里被判**红**（`m06imp` 那几行就是这样）
    #   ⇒ 补进来（⛔ 别反过来去改注释的措辞 —— 该迁就的是词表，不是人话）。
    "已下架", "已退休", "已下线",
    # ⚠️ 2026-09-23（`B5b` 第三步撤 `m05imp` 时踩到）：⚠️ **别往这里加裸动词**（「删除」「下架」「删掉」）——
    #   本表是**四条检查共用**的（`T1`/`T2`/`T3`/`T8` 都走 `_verdict`）⇒ 加一个泛词会把
    #   **T2（已废除术语）/ T3（幽灵路径）在文档里的命中**一起豁免掉（那两把就没区分力了）。
    #   ⭐ 正确做法 = **把行文写成带「已」的完成态**（「已删除」「已下架」），而不是放宽词表 ——
    #   词表只收**明确指向"它废了"的固定说法**。
)

#: **强豁免（模式版）** —— ⭐ 有些"它废了"的写法**中间会夹东西**，纯子串匹配会漏：
#:  ⚠️⚠️ **实测踩到（2026-09-20）**：`**已于 2026-09-20 删除**` ——
#:    「已」与「删」之间夹了日期 ⇒ `"已删" in text` **不成立** ⇒
#:    一条**完全正确、还写清了日期**的撤项说明被判**红** ✗
#:  ⭐ 而「写清哪天撤的」正是**最该鼓励**的写法 ⇒ 必须用**模式**匹配，⛔ 不能只比子串。
#:  ⚠️ 收紧边界（`[^，。；\n]{0,16}`）：只跨"日期 / 版本号"这类短插入，
#:    避免「已……删」跨半句话把正常行误豁免。
#: ⭐ 2026-09-24 补 **下架 / 退休 / 下线**：子串表里虽已有「已**下架**」，但本仓实际写法常是
#:    「**已随 `B5c` 下架**」「已按用户裁定…下架」（中间夹了标识符 / 日期）⇒ 只有模式版兜得住。
#:    实测：修 `T8` 扫描面后冒出的 3 条红（`tools/probe/_shell_legacy.py` 的 `m08imp`/`m06imp`/`m05imp`）
#:    **全是这种正确写法**被误判 ⇒ 按本表上方的老规矩（该迁就的是词表，不是人话）补词，⛔ 不改注释。
HARD_EXEMPT_RE: tuple[str, ...] = (
    r"已[^，。；\n]{0,16}(?:删|取消|作废|废除|撤|废|下架|退休|下线)",
)

#: **弱豁免**：邻近出现 ⇒ 降黄（人看一眼）。豁免窗口 = 命中行 ±2 行
#: ⚠️ 只放**明确指向「这是旧写法 / 外部件」**的词 —— 「计划 / 拟 / 历史 / 留痕」太泛，
#:    放进来会把大片正常行误豁免（那类由 `LENIENT_GLOBS` 按文件管更准）。
SOFT_EXEMPT: tuple[str, ...] = (
    "原名", "原先", "（原", "原「", "改成", "改为", "改取", "更正", "曾",
    "非本工程", "素材包", "老工程", "_tmp_", "源文件",
)

#: 文件级「留痕」白名单（**相对两侧根的完整相对路径**，glob）—— 命中只报黄
#: ⚠️ 别写成 `plans/*.md` —— 实际相对名是 `.codebuddy/plans/…`，少前缀就不匹配（踩过一次）。
LENIENT_GLOBS: tuple[str, ...] = (
    # ⭐ 2026-09-17 起：`plans/` 里**只有活文档**（按**严格标准**查），其余一律 `归档-*`（只留痕）
    #    ⇒ **一条 glob 覆盖全部归档件**。
    #    ⚠️ 别再逐份列（`2026-09-1[0-9]-*.md` / 各方案名）—— **逐份列 = 新归档件必然漏网**，
    #    这正是"计划文档悄悄过期却查不出来"的老路。
    #    ℹ️ `handoff/` 已于同日并入 `plans/`（history 条目 = `plans/archive/归档-历史单元条目.md`）。
    #    ⭐ 2026-10-01（`TAIL-204` 第 6 步）：`plans/` 根的活文档由**两份收成一份**（见 `HANDBOOK_REL`）。
    ".codebuddy/plans/archive/归档-*.md",
    # ⭐⭐ 2026-10-05（`TAIL-235` 丁-1）：`work/` 的**过程区**按留痕口径降黄。
    #    **为什么这两区降黄、三区不降**（分档是量出来的，不是拍的）：
    #    · `40-decisions/` = **裁定留痕**（"当初撤了什么、为什么"）⇒ 同理降黄。
    #      ⚠️ 量测实证：`D26` 的「已经按本条撤掉的（留痕 · 逐条可查）」那张表里，
    #      **逐条点名** `m05imp`/`m06imp`/`m08imp` ⇒ `T8`（已撤项复活 · 红）当场报 **2 红**。
    #      那是**撤项记录本身**（把"我们撤过什么"删掉才是篡改历史）⇒ 降黄，不动内容。
    #    · `10-designs/` + `30-troubleshooting/` = **过程留痕**（"当初为什么这么定"）⇒ 里面写的
    #      旧路径 / 旧数字**是对的**（改了反而是篡改历史，同 `T9`②「历史叙事里的旧数字别动」）。
    #      ⚠️ 量测：这两区一进扫描面就有 **9 处**这样的历史引用（`tools/_mut_t12.py` 搬家前地址、
    #      `artifacts/_probe_*.json` 探针产物…）⇒ 全判红就是**噪音源**，而本仓老话是
    #      **"噪音会把人逼到把判据关掉"**（`T21` 立条时同一段论证）⇒ 只报黄、看得见但不挡合入。
    #    · ⛔ **严判的那三档是**：注入档三件（`memory/*.md`）· 规则档（`rules/**`）·
    #      **`50-tickets/`** ＋ `work/README.md`。⚠️ 其中**票仓不降黄**最要紧：
    #      票是**在办工单**，它指向的文件**必须真存在** ——
    #      "票里别写死将来才建的文件名"这条规矩本仓**栽过两次**（当日 `T3` 立刻报红），
    #      降黄等于把那道保护关掉。
    ".codebuddy/work/40-decisions/*.md",
    ".codebuddy/work/10-designs/*.md",
    ".codebuddy/work/30-troubleshooting/*.md",
)

#: 合法的「幽灵用例号」—— 文档里明写「不建用例」的编号
KNOWN_ABSENT: frozenset[str] = frozenset({"ACC-X-ATT-001", "ACC-X-ATT-002"})

#: `T3` 只检查这些顶级目录开头的路径（`C:\…`、URL、SSH 一律不管）
TOP_DIRS: tuple[str, ...] = (
    "backend/", "tools/", "ops/", "docs/", "delivery/", "demo/", "PRD/", "app/", "tests/",
    "alembic/", "artifacts/", "frontend/", "static/", "scripts/", "input/",
    # ⭐⭐ 2026-10-05（`TAIL-235` 丁-1）：**治理区进 `T3` 的眼**。
    #    ⚠️ 此前**整个 `.codebuddy/` 不在表内** ⇒ 票仓 / 记忆档 / 规则档 / 决策档里写下的
    #    路径**一条都不被核** —— 实测当天扩面（同时把扫描面扩到治理区）当场捞出 **5 处真幽灵**
    #    （`tools/acc_report.py` 搬家前地址 · `app/core/models_registry.py` 挪位前地址 ·
    #    `tools/ui_parity_expected.txt` 已退场 · 票里写死"将来才建"的变异件名）。
    #    ⇒ 这不是"多查一点"，是**补上一整片没有守卫的地方**。
    ".codebuddy/",
    # ⭐⭐ 2026-10-05（`TAIL-236` 同批修 ①b）：**根 `work/` 也进这张表**。
    #   **起因（当天实测）**：`.gitignore` 的注释里留着旧落点、我照着它**在仓库根建了 `work/`**
    #   —— 而 `T3` / `T12` / `T14` **四层守卫没一层拦**（根 `work/` 不在任何判据眼里）。
    #   ⚠️ 本表的语义**不是**"根目录必须有这些目录"（`demo/` / `PRD/` / `app/` / `tests/` 都是
    #   相对**交付面**或 `backend/` 的写法，根上并不存在）—— 它是「**文档里可能出现、且该按仓库内
    #   路径去核**的前缀」。加 `work/` 的**效果**：`work/xxx.md` 这类引用当场被逼出来
    #   （真身都在 `.codebuddy/work/`；反向灵敏度 = `tools/mut/_mut_docaudit.py` 的 `M30`）。
    #   ⚠️ 同族还有一条**目录形态**的歧义 T3 管不了（`work/00-scratch/` 这种没有后缀的写法）
    #   ⇒ 那半边靠**仓库根白名单**（`ROOT_ALLOW` ＋ `T24`）与人工把写法写全。
    "work/",
)

#: ⭐⭐ **仓库根允许出现的常驻条目**（2026-10-05 · `TAIL-236` 同批修 ①b）—— **单一真源**。
#:
#: **为什么要有它**：`T12` 只管**根上的 md**（`ROOT_MD_ALLOW`），于是**目录与非 md 文件**
#:   落在根上**没有任何尺子看得见** —— 2026-10-05 实测：我在仓库根建了一个 `work/`（见上），
#:   而 `T3` / `T12` / `T14` 都没拦。`T24`（`audit_meta.check_drop_zones`）就是补这一片。
#:
#: ⚠️ **与 `.gitignore` 的分工**（⚠️ 是"职责不同"，⛔ **不是**"同一份清单的两份"）：
#:   · 本表 = **权威**的**常驻**条目（仓库骨架，长在仓里、随仓走）—— 少一条 ⇒ 根上那个条目就该报；
#:   · `.gitignore` = **额外容忍**的**可再生 / 本机暂存**条目（缓存、虚拟环境、构建产物…）。
#:   ⇒ `T24` 判"根上多出来的东西合不合法"时取**并集**（**允许重叠**：`artifacts` / `logs` 等
#:     两处都有 —— 以本表为准，重叠本身无害）。
#:   ⚠️ **已知妥协**：`.gitignore` 里加一行同名规则即可容忍根上某目录（旁路）—— 见 `check_drop_zones` 的 docstring。
#: ⚠️ **`README.md` / `AGENTS.md` 刻意不列**：根上的 `.md` 归 `T12`（`ROOT_MD_ALLOW`）
#:   ⇒ 列进来就是**同一件事两处写**（本仓最贵的病，必漂）。
#: ⚠️ 目录带尾斜杠、文件不带（判据按**名字**比，斜杠只是可读性）。
ROOT_ALLOW: tuple[str, ...] = (
    ".codebuddy/", ".git/", "artifacts/", "backend/", "docs/", "delivery/", "logs/", "ops/", "tools/",
    ".env", ".env.example", ".gitignore",
)

#: ⭐ 忽略规则文件本身（`T24` 拿它当"根上暂存件"的**第二份身份表**；`T25` 拿它当**被核件**）。
#:   ⛔ 路径只写这一处 —— 两个判据各写一遍就是"同一件事两处写"（老病）。
GITIGNORE_REL: str = ".gitignore"

#: ⭐⭐ **仓外归档根 = 显式白名单前缀**（2026-10-05 `TAIL-235` 丁-1）。
#:
#: ⛔⛔ **为什么必须是"显式登记"，而不能靠"字符凑巧不匹配"**（本条存在的全部理由）：
#:    2026-10-05 实测 —— 给一条指向**已搬走**文件的引用加个 `〔已归档〕` 前缀，
#:    `_PATH_RE` 的首字符类 `[A-Za-z0-9_]` 就不匹配了 ⇒ **整条从 `T3` 眼里消失**。
#:    而那 3 条里的 `ops/` **本来在 `TOP_DIRS` 内**（`T3` 该照到它们）⇒ 等于用一个前缀
#:    **主动消除了一道真实存在的保护**，而且**闸门 rc=0、全绿、没人看见**（本仓最贵那族假绿）。
#:    ⇒ 现在**两条路都显式化**：
#:      · **正路** = 写**仓外绝对路径**（落在本表内）⇒ `T3` 到那个根下**真核存在**；
#:      · **旁路** = 加标记前缀 ⇒ `T3` **认得出来**，剥掉标记后按仓内核，**核不到就报**。
#:    ⛔ 标记**不等于豁免** —— 这是它与"宽容免"的唯一区别。
OUTSIDE_ROOTS: tuple[str, ...] = ("D:/dev/.归档-mtrl",)

#: 仓外引用的**标记前缀**（⛔ 别扩成泛词：一个前缀只对应一种写法，泛词会把真幽灵一起赦掉）
OUTSIDE_MARKERS: tuple[str, ...] = ("〔已归档〕",)

#: ⭐ `T3` **局部**豁免：行文**本身就在说"那个路径已经不作数了"** ⇒ 直接放行。
#:
#: ⚠️⛔ **为什么不能加进 `HARD_EXEMPT`**：那张表是 `T1`/`T2`/`T3`/`T8` **四条共用**的
#:    （那张表的注释里已经写过一次教训：加一个泛词会把 `T2` 的命中一起赦掉）。
#:    这里要赦的是**"陈旧路径的告警"**这一件事 ⇒ 只给 `T3` 用，⛔ 不外溢。
#: ⚠️ 收词纪律：只收**明确指向"那个地址已作数/已搬走"**的整块说法，
#:    ⛔ 不收「原」「曾」这类泛指（`SOFT_EXEMPT` 已有，且只降黄不赦）。
#:    ⭐ 实证（`TAIL-235` 丁-1 量测）：`.codebuddy/memory/IDE-细节.md:226` 写着
#:    「⛔ 旧路径 `app/core/models_registry.py` 不存在了」—— 那是**故意留着的警示**，
#:    判它红等于**逼人把警告删掉**（本仓老路：为了让判据变绿而改坏东西）。
#:    ⚠️ 同批第二例：`IDE-细节.md:205` 补注「该登记簿**已退场**」——「已退场」也是同一类说法。
T3_OLD_PATH_HINTS: tuple[str, ...] = (
    "旧路径", "已不存在", "已退场", "已搬走", "已移出", "不在仓内",
    # ⭐⭐ 2026-10-06（`TAIL-238`）**第二类叙述豁免**：从「那个地址**已作数**」扩到
    #   「那个地址**本来就不成立 / 是我写错的**」。逐条判据（当轮量测，别处不抄）：
    #   · **为什么扩**：六天内 ≥10 次**误伤**，形状高度单一 —— 在**描述某次误报**的
    #     句子里顺手写了那个**不存在的相对路径**（票面最甚），而「记录一次故障」正是本仓
    #     天天在做的事 ⇒ 不收窄＝训练出「`T3` 一律当噪音」的坏习惯（真幽灵一起被忽略）。
    #   · ⛔ **为什么不用「整层放行票仓 + 日志」**（(C) 方案，当轮**量到 1 条真幽灵**）：
    #     ① 票仓**现存**真幽灵：`TAIL-235` 票面里的 `work/README.md`（根上那份早删了）；
    #     ② `TAIL-235` 票面**自认**它当年捞出过「票里写死将来才建的文件名」这一条真幽灵。
    #     ⇒ 整层放行＝**拿真保护换噪音**；(C) 的前提（真幽灵 0 条）**不成立**。
    #   · ⛔ **为什么不用「只在结构位判红」**（(A) 方案）：当轮量到**现有命中里 0 条**在
    #     markdown 链接 `[]()` 内 ⇒ (A) 等于把 `T3` 关掉（漏报一大片，比误伤更坏）。
    #     ⚠️ **条数别抄进注释**（会漂）—— 量它的探针与当轮读数在当日日志那节，重跑即可复现。
    #   · ⚠️ 当轮还量到一句：`journal/` **根本不在 `SCAN_GLOBS` 里**（本件 `SCAN_GLOBS` 的注释
    #     已写明「故意不在内」）⇒ 误伤的**发生地是票仓**，日志只是**记下这件事的地方**。
    #   · ⛔ **收词纪律**（同老规矩：泛词迟早被巧合命中）：每个词都要能独立回答
    #     「这个地址不成立 / 我写错了」。⚠️ **刻意不收「写死」** —— 它大量出现在**正确**的
    #     纪律句里（「⛔ 别写死件数与件名」）⇒ 收进去等于给活引用开门。
    #     ⚠️ 当轮实测：这批词对**现有命中的赦免数 = 0**（含那条真幽灵）。
    #   ⚠️ **代价（明写，别装看不见）**：这是**形态判据** ⇒ **可被绕过**（换个说法就又红了）。
    #     三道压制：① 词表窄（上面这条纪律）② **距离闸**（`T3_HINT_WINDOW`，词必须贴着
    #     那个路径）③ 反向灵敏度 `tools/mut/_mut_t3_narr.py`（真幽灵仍红 · 叙述句豁免 ·
    #     **票仓里不带叙述词的同类句仍红**〔钉住「不许只放宽一半」〕· 词离远了仍红；
    #     ⛔ 命中条数看该件自己的输出，⛔ 别抄进这里）。
    #     ⇒ 将来若真的被换词绕过，**该做的是把那个说法补进这一处**，⛔ 不是去关判据。
    #   ⚠️ 本表**同时**是 `T25`（`.gitignore` 落点）的豁免词表（同一份，⛔ 不另开）⇒ 那边同步变宽。
    "没建", "未建", "没创建", "误写", "写错", "裸路径", "裸写法",
)
#: ⚠️⚠️ **距离闸**：`T3_OLD_PATH_HINTS` 里的词必须**贴着那个路径**（前后各这么多字符内）才算豁免。
#: ⛔ 为什么不能"整行命中就算"（`/code-review` 当场实测的反例）：本票 `TAIL-235` 自己那行写着
#:    「`.codebuddy/memory/2026-09-29.md` 等**重复副本旧地址 19 处**」—— 「旧地址」是**句中描述词**
#:    （"重复副本的旧地址"），**恰好**遮住了一个**真幽灵**（该件真身已随甲1② 删掉）
#:    ⇒ **治假绿的东西自己成了假绿**。收窄词表 ＋ 加距离闸才是同一件事的两半。
#: ⚠️ 词表也**同步收窄过**（删掉"旧地址 / 原地址 / 不存在了"三个泛词 —— 泛词迟早被巧合命中）。
T3_HINT_WINDOW = 16

#: ⭐ `T3` **整段放行**的前缀（相对仓根）—— ⛔ 只放"那一段的件**按制度会消失**"的目录。
#:    唯一的登记项 `.codebuddy/backups/` = **保留期目录**（`T20` 判据管着它：顶层留 5 份 · 月度清）
#:    ⇒ 文档里点名其中**某一件**，被清掉那天就变成幽灵，而**没人该为它回头改文档**
#:    （该做的是把"那份备份已清"这句话留着，而不是把备份从历史叙述里抠掉）。
#:    ⚠️ **这是结构性放行、不是逐条赦免** —— 段内的路径**根本不看**。
#: ⛔ 别拿它放行"代码还没建"的目录（那类是真问题，见 `tools/mut/`）。
T3_SKIP_PREFIXES: tuple[str, ...] = (
    ".codebuddy/backups/",
    # ⭐ 2026-10-05（`TAIL-236` 同批修 ①b）：`.codebuddy/work/00-scratch/` **同族放行** ——
    #   它是 **TTL 14 天**的临时区（`T14` 管着，到期即清）⇒ 文档里点名其中某一支探针脚本，
    #   被清掉那天就变成幽灵，而**没人该为它回头改文档**（理由与上面那条逐字相同）。
    #   ⚠️ 起因：把 `work/` 加进 `TOP_DIRS` 后，这类引用第一次被照出来（`work/00-scratch/x.py`
    #   这种写法过去根本不匹配任何前缀 ⇒ 又一次"落在所有尺子之外"）。
    #   ⛔ 仍**只放行"按制度会消失"的目录** —— 别往里加"代码还没建"的那种（那是真问题）。
    ".codebuddy/work/00-scratch/",
)

#: 文档扫描面认的后缀（`.mdc` = **IDE 项目规则**，2026-10-05 `TAIL-235` 丁-1 起一并收）
DOC_SUFFIXES: tuple[str, ...] = (".md", ".mdc")

#: 「**给人看的（用户 / 新会话读到的第一份）**」那一件的相对路径（`T4` / `T6` 都读它）。
#: ⭐ 2026-10-01（`TAIL-204` 第 6 步）**换件**：原 `.codebuddy/plans/执行情况-主文档.md` —— 用户裁定
#:   「算给人看的，但…已不需要里面的大部分文字，可将绝大部分归档，**只留待办**」⇒ 待办并入
#:   **根 `README.md` 的 §〇**，该件归档（`plans/archive/归档-执行情况-已完成叙述-20261001.md`）。
#:   ⇒ 现在「给人看的那一页」= **`README.md`**（它同时是文档地图 —— 这是有意的：一张纸两用）。
#: ⚠️ 换的是**落点、不是标准** —— 两条判据都照旧，只是改查 `README.md`：
#:   ① `T4` 要求这一件里**至少有一处**四态数字（`must_have=True`，得"以真实数字开头"）；
#:   ② `T6` 要求这一件**指向计划**（含 `LEDGER_NAME`）。
HANDBOOK_REL: str = "README.md"

#: `T6` 尾巴台账（**唯一清点处** = 计划主文档 §15）—— 尾巴的单一清点处
LEDGER_REL: str = ".codebuddy/plans/开发计划-主文档.md"
LEDGER_NAME: str = "开发计划-主文档"
CLOSED_INDEX_REL: str = ".codebuddy/plans/票索引-已销号.md"
TAIL_MIN_CELLS: int = 6          # 表格行去掉首尾竖线后的最少格数（栏位齐全 = 含**落点** ＋ **阶段**）

#: `T6` 尾巴的**阶段受控词** —— 尾巴一登记就必须回答"在哪个阶段处理"（2026-09-17 用户裁定：
#: 「尾巴不能就简单地进总计划，肯定要分析尾巴合适在什么阶段处理」）。
#: ⭐ **只登记、不排期 ⇒ 判红**；能通过 = 这条尾巴的时机已经想清楚了。
TAIL_STAGE_RE = re.compile(r"^(?:M[0-8]|立刻|持续|随时|已做|已完成)")

#: `T6` 排期表（§14.3）—— 每条尾巴的编号必须在那里也有一行（**登记即排期**，两处一致）
TAIL_SCHEDULE_RE = re.compile(r"^#{2,3}\s*[\d.]*\s*逐条排期")

#: 路径解析时依次尝试的前缀（文档常省略 `backend/`）
PATH_ROOTS: tuple[str, ...] = ("", "backend/", "backend/app/")

#: ⭐ **顶部计数行的两处形态**（`T6` / `_tail_close.py` / `_tail_open.py` 共用 —— **形态只留这一份**）。
#: 2026-10-02（`/retro` 候选 1）收口：此前 `audit_meta.check_tail_ledger` 与 `tools/oneoff/_tail_close.py`
#: **各写一遍**（而 `_tail_open.py` 会成第三遍）⇒ 改一处形态必漏一处 = 本仓"同一件事两处写"的老病。
#: ⚠️ 两处**写法仍有轻重两式**：计划概览用简式；§15 顶部用带粗体与「条」的全式。
COUNT_MIN_RE = re.compile(r"(活跃 )\d+( · 已销号 )\d+")
COUNT_FULL_RE = re.compile(r"(活跃 \*\*)\d+(\*\* 条 · 已销号 \*\*)\d+(\*\* 条)")

def read_counts(text: str) -> tuple[int, int] | None:
    """从文本里读出 §15 顶部计数 `(活跃, 已销号)`；没有全式计数行则返回 `None`。"""
    m = COUNT_FULL_RE.search(text)
    if not m:
        return None
    nums = [int(x) for x in re.findall(r"\d+", m.group(0))]
    return tuple((nums + [0, 0])[:2])  # type: ignore[return-value]


def write_counts(text: str, counts: dict[str, int]) -> tuple[str, int, int]:
    """将简式与全式两处计数按真源重写，返回新文本及两处命中数。"""
    active = counts.get("活跃", sum(counts.get(k, 0) for k in ("一", "二", "三")))
    closed = counts.get("四", 0)

    def _sub(rx: re.Pattern[str]) -> tuple[str, int]:
        return rx.subn(lambda m: f"{m.group(1)}{active}{m.group(2)}{closed}{m.group(3)}" if rx is COUNT_FULL_RE
                       else f"{m.group(1)}{active}{m.group(2)}{closed}", text)

    text, n_min = _sub(COUNT_MIN_RE)
    text, n_full = _sub(COUNT_FULL_RE)
    return text, n_min, n_full

SCAN_GLOBS: tuple[str, ...] = (
    # ⭐⭐ 2026-09-21 文档体系重构后，扫描面 = **会被当口径读的那几层**（按 `README.md` 的四层）：
    #    ① 注入档 `.codebuddy/memory/MEMORY.md` ② 按需档（根 `README.md` · `ops/*.md` · 计划与服务承诺）
    #    ⛔ **不含** ③ 留痕档（`memory/journal/` · `plans/archive/归档-*.md` —— 旧术语/旧数字在那儿是**对的**）
    #       与 ④ 产物档（`artifacts/` —— 由 `T11` 管"回执"，不管措辞）。
    # ⚠️ **`CLAUDE.md` 已删除**（2026-09-21 用户裁定：换工具后**无人读取**）—— 它的必用内容已并入
    #    `MEMORY.md`（注入档）与 `细则.md`，过程叙事下沉到 `plans/archive/归档-历史单元条目.md`。
    # 2026-10-15工程正文迁入docs；旧ops薄入口退出普通扫描，仍在用的索引显式保留。
    "README.md", "AGENTS.md", "ops/README.md", "ops/delivery-surface.md", "docs/architecture.md", ".codebuddy/plans/*.md",
    # ⭐⭐ 2026-10-06（`TAIL-236` 第 4 批 · **实验**）：**仓内归档索引**进扫描面 ——
    #   `plans/archive/归档-*.md` 早就在 `LENIENT_GLOBS`（降黄那侧），而 `SCAN_GLOBS` 只有**非递归**的
    #   `.codebuddy/plans/*.md` ⇒ **那一片根本没被扫**（实测：扫描面里带 `archive` 的件 = 0）。
    #   ⇒ 索引件里写的**仓外绝对路径**（`OUTSIDE_ROOTS` 那套「真核存在」）**从来没被核过** ——
    #   仓外那份被清掉 ⇒ 指针变死，而**没有任何尺子会喊**（墓碑 ≠ 守卫）。
    ".codebuddy/plans/archive/*.md",
    # 2026-10-15专项迁移：Agent协议、绑定与新ADR实际进入扫描；T18仍核每条glob命中。
    "docs/agents/*.md", "docs/adr/*.md",
    "docs/architecture/*.md", "docs/guides/*.md", "docs/reference/*.md",  # 项目开发分册的现行正文；旧memory位置只留兼容指针。
    ".codebuddy/memory/MEMORY.md",
    # ⭐⭐ 2026-10-05（`TAIL-235` 丁-1）：**治理区整片进扫描面** —— 此前只有上面那份
    # `MEMORY.md` 一个治理区文件在被扫 ⇒ 票仓 / 规则档 / 决策档 / 过程区**没有任何尺子看得见**。
    # ⚠️ **档位是量出来的**（`TAIL-235` 丁-1 只读探针，`.codebuddy/work/00-scratch/`）：
    #   · `memory/*.md`（注入档三件）· `rules/**`（**每轮自动注入给用户看**）· `40-decisions/`（用户裁定）
    #     · `50-tickets/`（**在办工单**）· `work/README.md` ⇒ **严判**（命中即红）；
    #   · `10-designs/` · `30-troubleshooting/`（过程留痕）⇒ 由 `LENIENT_GLOBS` **降黄**。
    # ⚠️ `journal/`（逐日日志）**故意不在内** —— 它是**只追加留痕**（`README.md` §二③），
    #    里面的旧路径与旧数字**是对的**（同 `plans/archive/` 的口径）⇒ 别把它扫进来制造噪音。
    ".codebuddy/memory/*.md",
    ".codebuddy/rules/**/*.mdc",
    ".codebuddy/work/README.md",
    ".codebuddy/work/40-decisions/*.md",
    ".codebuddy/work/50-tickets/*.md",
    ".codebuddy/work/10-designs/*.md",
    ".codebuddy/work/30-troubleshooting/*.md",
    # ⚠️ 2026-09-24 **摘掉 `.codebuddy/memory/CHANGELOG.md`**（`T18` 立起来当天抓的第一例）：
    #    它是**搬迁前的旧地址**，该件现址 = `docs/reference/changelog.md`（`README.md`「工程基准档」那行）⇒
    #    这条 glob **一条都不命中** = 那一片**从没被扫过**（`docs/*.md` 已把它盖住 ⇒ 摘掉 = 零损失）。
)
DELIVERY_GLOBS: tuple[str, ...] = (
    "*.md", "PRD/*.md", "PRD/*/*.md", "demo/*.md", "demo/*/*.md",
)

#: ⭐⭐ **交付面文档的「页脚标记」**（2026-10-06 `TAIL-234` 立 · `T27` 的判据对象）—— ⛔ **全仓只此一份**。
#:
#: **形态** = 交付面每份件**末尾**那行 `> **本文件性质**：…`（`README.md` §四 的落款规矩）。
#: **为什么要有这条网**：2026-10-06 实测 —— `MOD-14.md` 的两条 `ACC-*` 验收清单条目**掉到了页脚之后**
#: ⇒ 渲染出来是页脚下面的孤行，而 `T1`–`T26` **没有一层能看见它**（用例号是真的 · 路径是真的 · 只是位置错了）。
FOOTER_MARKER: str = "> **本文件性质**"

#: ⭐ `T27` 的**扫描面** = 交付面**全部** md（⛔ 刻意比 `DELIVERY_GLOBS` 宽一档）。
#: ⚠️ 「落款后面掉了两行」这种事**不该只在那五个目录里查** —— 交付面以后加目录，
#:   窄扫描面会让新目录**先天不在守卫里**（本仓"判据存在 ≠ 被看见"那族：没人知道漏了哪一片）。
#:   代价 = 归档目录要显式排除 ⇒ 见 `FOOTER_EXCLUDE_PARTS`（那份清单就是为这张宽扫描面存在的）。
FOOTER_SCAN_GLOB: str = "**/*.md"

#: ⭐ `T27` 的**排除目录**（相对交付面根）—— 「页脚后有内容」在**归档留痕**里是**对的**，不是缺陷。
#: ⚠️ 清单来自实测（`TAIL-234` 当轮量 = 6 处全在 `.workbuddy/归档-audit/` 下的 5 份件里），⛔ 别凭想象加。
#: ⛔ **只放"按制度会留痕"的目录** —— 放进活目录等于把真缺陷赦掉。
FOOTER_EXCLUDE_PARTS: tuple[str, ...] = (".workbuddy",)

#: ⭐ `T28` 的扫描面 = **交付面 `PRD/` 全部 md**（相对交付面根）。⛔ 与 `DELIVERY_GLOBS` 不是一回事：
#:   那张是**漂移扫描面**（仓 + 面全扫），这张只管「PRD 规格件不许变短」这一件事。
PRD_DOC_GLOB: str = "PRD/**/*.md"

#: ⭐⭐ **活机器口径**（2026-10-05 · `TAIL-236` 第 2 批）：判「**某件还有谁在引用**」时，
#:   **代码侧**要扫哪几处 —— **六路，九条 glob**。⛔⛔ **全仓只有这一份定义**。
#:
#: **为什么必须是"一张表"**（当天已栽**两次**，第一次差点搬错件）：
#:   第一版量测只扫后端与 `tools/` 下的 `.py` ⇒ **漏了运维脚本与规则档两路**（壳的
#:   脚本与页面也漏了）⇒ 当场差点把「设计-交付包与迁移」（**被运维脚本引用**）当零引用
#:   死重搬走。⇒ 治法**不是"再补一处"**：口径只此一份，命令与尺子都 import 它，
#:   再由 `audit_meta` 的 `T23` 钉住「**缺一路必须报红**」。
#:
#: ⚠️ **与 `audit_meta.CODE_DIRS`（`T5` 用）不是同一件事** —— 那张是"哪些目录里的
#:    `.py` 要量行数"，这一张是"哪些**文件**算活机器"（含非 `.py` 的四类，且**不含**
#:    一次性留痕件）。⛔ 两张表**各自一处**、互相不抄；也别指望能互相推出来。
#:
#: 形态：`(glob, 这一路是什么, 参与扫描的后缀)` —— 后缀白名单是**第三半边**：
#:   ⛔ 只按 glob 收会把 `.pyc`、`__pycache__`、图片一并读进来（慢，且噪声）。
LIVE_MACHINE_GLOBS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("backend/app/**/*.py", "① 后端业务代码", (".py",)),
    ("backend/tests/**/*.py", "② 后端测试", (".py",)),
    ("tools/audit/**/*.py", "③ 尺子", (".py",)),
    ("tools/mut/_mut_*.py", "③ 反向灵敏度", (".py",)),
    ("tools/probe/**/*.py", "③ 真机探针", (".py",)),
    ("ops/*.ps1", "④ 运维脚本", (".ps1",)),
    (".codebuddy/rules/**/*.mdc", "⑤ 规则档（每轮自动注入给用户看）", (".mdc",)),
    ("backend/app/web/**/*.js", "⑥ 前端壳 · 脚本", (".js",)),
    ("backend/app/web/**/*.html", "⑥ 前端壳 · 页面", (".html",)),
)

#: ⭐⭐ 2026-09-24（用户裁定 **A**）：`T8` **从「只扫代码」扩到「也扫活文档」**。
#:   **为什么要扩**：文档面原来交给 `T2`（`RETIRED_TERMS`），但那张词表**不含**已撤的
#:   页 / 端点名 ⇒ 「用**现在时**描述已撤功能」这类（实测：`docs/architecture/modules.md` 把 `m05imp`、
#:   `m06imp`、`m04` 两步导入写成**现存功能**）**没有任何尺子看得见** ——
#:   ⚠️ 实证：把 `docs/*.md` 加进漂移扫描面（`SCAN_GLOBS`）之后，`doc_audit` **仍然必须修 0**。
#:   **怎么扩**：文档面**直接复用 `SCAN_GLOBS`**（它已是「会被当口径读的那几层」的**唯一定义**）
#:   ⇒ 两处口径用同一个常量，⛔ **不会再分裂**（本项目栽过"同一件事两个主人"）。
#:   ⚠️ `SCAN_GLOBS` 含 `.codebuddy/plans/*.md`（其中 `归档-*.md` 体积大）⇒ 那类由
#:      `LENIENT_GLOBS` 降成**黄**（留痕档里出现旧名是**对的**，只提示不判红）。
CANCELLED_DOC_GLOBS: tuple[str, ...] = SCAN_GLOBS

_ACC_RE = re.compile(r"ACC-[A-Z0-9]+(?:-[A-Z0-9]+)*")
_ACC_ID_RE = re.compile(r"^ACC-[A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}$")
#: 反引号里的**相对路径**（仓内相对路径的通用形态）。
#: ⭐⭐ 2026-10-05（`TAIL-235` 丁-1）：**首字符类加了 `.`** —— 此前是 `[A-Za-z0-9_]`
#:    ⇒ **以点开头的路径整条不匹配**，而本仓最重要的两类路径恰好都以点开头：
#:    `.codebuddy/…`（治理区）· 相对引用 `./x`。
#:    ⚠️ **这是个"改对了一处、另一处仍静默失效"的典型**：当天先把 `.codebuddy/` 加进 `TOP_DIRS`，
#:    量测却报"0 处命中"—— 看着像"治理区本来就干净"，真因是**正则压根不认它**
#:    ⇒ 判据与靶**配对不上**（本仓老话：加了半边的守卫比不加更坏，因为它让人以为已经守上了）。
#:    ⛔ 加 `.` 之后仍不会被误命中的两种形态（都因"只有一个点"而自然落空）：
#:    `` `.md` ``（只讲后缀）· `` `.codebuddy` ``（只讲目录）。
_PATH_RE = re.compile(r"`([A-Za-z0-9_.][A-Za-z0-9_./\\-]*\.[A-Za-z0-9]{1,5})`")
#: ⭐ **反引号 token 提取**（`T25` 扫 `.gitignore` 落点用 · `T26` 扫「落地位置」声明行用）——
#: ⛔ **只此一份**：这两处此前各写了一遍同一模式（`/code-review` 2026-10-05 指出 ——
#:   同一种正则两处写 = 改一处漏一处，本仓最贵的病）。
BACKTICK_RE = re.compile(r"`([^`\n]+)`")
#: ⭐ 反引号里的**绝对路径**（盘符开头）—— `T3` 用它核仓外白名单（见 `OUTSIDE_ROOTS`）。
#:   ⚠️ 它**只负责把 token 摘出来**，"这个盘符属不属于仓外"由 `OUTSIDE_ROOTS` 判 ⇒
#:   别的盘（`C:\…` / `D:\pgsql\…`）摘出来也会被放行，不会误报。
_OUTSIDE_PATH_RE = re.compile(r"`([A-Za-z]:[\\/][^`\n]+?)`")
#: ⭐ 反引号路径**前面带仓外标记**的写法 —— ⛔ **它不是豁免**，`T3` 剥掉标记后照核（见 `OUTSIDE_MARKERS`）
#: ⚠️⚠️ 首字符类**必须与 `_PATH_RE` 一样含 `.`**（`/code-review` 当场抓到：原先写 `[A-Za-z0-9_]`
#:    ⇒ 探针 `` `〔已归档〕.codebuddy/work/x.md` `` 在**标记分支与普通分支双双不匹配**
#:    ⇒ 那条路径对 `T3` **完全隐形** = 又一次"加了半边的守卫"。**判据与靶必须配对。**
_MARKED_PATH_RE = re.compile(
    "`(?:" + "|".join(re.escape(x) for x in OUTSIDE_MARKERS)
    + r")([A-Za-z0-9_.][A-Za-z0-9_./\\-]*\.[A-Za-z0-9]{1,5})`")
_PLACEHOLDER = re.compile(r"[*<>{}]|YYYY|MM|DD|\bX\b")
_ZONE_RE = re.compile(r"<!--\s*doc_audit:(current|history)\s*-->")
#: ⚠️ 只匹配**四态本身**，不要求 `四态 **N =` 这种前缀 —— 文件里的写法是
#: `四态 **绿 171 · 红 0 · 待建 16 · 未绑定 131**（合计 **318**）`，前缀形态并不固定。
#: （踩过一次：原正则带前缀 ⇒ 认不出 ⇒ **静默跳过**，把"改错了"读成"通过"。）
_STATUS_RE = re.compile(
    r"绿\s*(\d+)\s*·\s*红\s*(\d+)\s*·\s*待建\s*(\d+)\s*·\s*未绑定\s*(\d+)"
)


# ------------------------------------------------------------------ 基础设施


def read_env(key: str) -> str:
    f = REPO_ROOT / ".env"
    if not f.exists():
        return ""
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def delivery_root() -> Path | None:
    """产品资料根 = `.env` 的 `PRD_ACCEPTANCE_BASELINE`（delivery/PRD/验收/验收基线.json）上溯两级。"""
    p = read_env("PRD_ACCEPTANCE_BASELINE")
    if not p:
        return None
    path = Path(p)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve().parents[2]


def _is_lenient(rel: str) -> bool:
    from fnmatch import fnmatch
    return any(fnmatch(rel, g) for g in LENIENT_GLOBS)


def iter_docs() -> list[tuple[str, str, Path, list[str], list[str]]]:
    """→ [(侧, 相对名, 路径, 行, 每行所属区)]；区 = `current` / `history`。"""
    out = []
    seen: set[Path] = set()
    plan: list[tuple[str, Path, str]] = []
    for pat in SCAN_GLOBS:
        for p in sorted(REPO_ROOT.glob(pat)):
            # ⭐ 2026-10-05（`TAIL-235` 丁-1）：`.mdc`（**IDE 项目规则**）一并收 ——
            #    `.codebuddy/rules/**/RULE.mdc` 是 `alwaysApply` 的**每轮自动注入**件，
            #    此前它对所有尺子**完全隐形**（而它里面就出过一次错话，见该目录 `RULE.mdc:20`）。
            if p.is_file() and p.suffix in DOC_SUFFIXES and p not in seen:
                seen.add(p)
                plan.append(("仓", p, str(p.relative_to(REPO_ROOT))))
    root = delivery_root()
    if root:
        for pat in DELIVERY_GLOBS:
            for p in sorted(root.glob(pat)):
                if p.is_file() and p not in seen:
                    seen.add(p)
                    plan.append(("面", p, str(p.relative_to(root))))
    for side, p, rel in plan:
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        zone, zones = "current", []
        for l in lines:
            m = _ZONE_RE.search(l)
            if m:
                zone = m.group(1)
            zones.append(zone)
        out.append((side, rel, p, lines, zones))
    return out


def _near(lines: list[str], i: int, n: int = 1) -> str:
    """命中行 ±n 行的合并文本（豁免判定用 —— 勘误常写在下一行）。"""
    lo, hi = max(0, i - n), min(len(lines), i + n + 1)
    return "\n".join(lines[lo:hi])


def _verdict(near: str, lenient: bool) -> str:
    """返回 RED / YELLOW / SKIP（`near` = 命中行 ±2 行）。

    ⚠️ 强豁免查**两遍**：先子串（`HARD_EXEMPT`）、再**模式**（`HARD_EXEMPT_RE`）——
       后者兜「已**于 <日期>** 删除」这类**中间夹了东西**的正确写法（见该常量注释）。
    """
    if any(w in near for w in HARD_EXEMPT):
        return SKIP
    if any(re.search(p, near) for p in HARD_EXEMPT_RE):
        return SKIP
    if lenient or any(w in near for w in SOFT_EXEMPT):
        return YELLOW
    return RED


def _hit(code, side, rel, path, i, lines, zones, *, what, why, fix) -> dict:
    line = lines[i].strip()
    lenient = _is_lenient(rel) or zones[i] == "history"
    return {"code": code, "side": side, "rel": rel, "line": i + 1,
            "what": what, "why": why, "fix": fix, "text": line,
            "level": _verdict(_near(lines, i, 2), lenient)}
