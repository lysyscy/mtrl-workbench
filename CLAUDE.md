# 材料报表自动化工作台 · 给 AI 的入口（`CLAUDE.md`）

> 本文件是**换开发工具时的第一入口**（2026-09-20 从 CodeBuddy 切到 Claude Code 时建立）。
> ⚠️ 它**只做导航与纪律**，⛔ **不重复口径** —— 口径的唯一出处是下面那两份活文档 ＋ 交付面 PRD。

## 0. 这是什么

科室内部（**2 人**）的局域网工具：把 i8 里的材料/付款数据抓回来，做**付款台账 · 欠款 · 报表 · 集采台账**。
两个代码面：
- **仓** = 本仓库（FastAPI 后端 `backend/app/` ＋ 唯一前端壳 `backend/app/web/`）
- **面** = 交付面（`$PRD_ACCEPTANCE_BASELINE` 上溯两级，见 `.env`）—— 原型 `demo/` ＋ PRD

## 1. ⭐ 开工前必读（按序，⛔ 别跳）

| 文件 | 定位 | 读多久 |
|---|---|---|
| `.workbuddy/plans/执行情况-主文档.md` | **给用户看的一页**（现状 / 下一步 / 要你做什么） | 1 分钟 |
| `.workbuddy/plans/开发计划-主文档.md` | **给 AI 的完整版** —— 规则 · 口径 · 台账 · 接手 · 闸门 | ⚠️ 3114 行，**按需查，别通读** |
| `tools/chain_expected.txt` | **链路认领表**（全站 11 条链路的端到端）—— 唯一完成度口径之一 | 按需 |
| `PRD/验收/验收基线.json`（在**面**） | **判据真源**（526 个判据点） | 机器读 |

⚠️ **开发计划 §0 现状快照**（0.1–0.4）是"先读这段"—— ⚠️ 但 **2026-09-20 时它已过期**（见 §6 末），
以**本文件 §5 的数字** ＋ `tools/doc_audit.py --block` 刷出来的为准。

## 2. ⭐ 跑批尺子（收工前必跑；⛔ 别只跑前 5 个）

```powershell
cd D:\dev\mtrl-workbench
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONDONTWRITEBYTECODE='1'
cd backend; .venv\Scripts\python.exe -m pytest -q tests/ -p no:cacheprovider --tb=line; cd ..
foreach($t in @('syntax_audit','wiring_audit','ui_parity','chain_audit','asset_audit','claim_audit',
                'cover_gap','prg_form_audit','audit_drift','audit_meta','shell_verify','sticky_probe')){
  backend\.venv\Scripts\python.exe "tools\$t.py" > $null 2>&1; "$t=$LASTEXITCODE" }
backend\.venv\Scripts\python.exe tools\acc_report.py | Select-String '判据点合计'
backend\.venv\Scripts\python.exe tools\doc_audit.py          # 含 T8 撤项守卫
backend\.venv\Scripts\python.exe tools\doc_audit.py --ui     # ⭐⭐ 交付面四检（最易漏！）
```

⭐ **为什么必须含 `doc_audit --ui`**：它跑交付面四检（`_smoke`/`_doccheck`/`_links`/`_ids`），
而 `ui_parity` 的 **`U1` 只比「壳的 `V.<页>` 切片 vs 原型同名切片逐行一致」** ——
⚠️ **`ACT` / `CHG` 是顶层 const、不在任何 `V.` 切片内** ⇒ "**壳里加了动作、原型没同步**"它**查不出来** ✗
⇒ ⭐ **只有 `_smoke`** 的两条能发现：`N6｜表单类动作必须在 CHG 里` ＋ `无死控件`（症状 = **点了没反应**）。

## 3. ⭐ 铁律（一票否决类，违反即返工）

1. ⛔ **口径没定就不动实现** —— 先查《说明书》/ PRD，找不到就问用户，**别自己发明**。
2. ⛔ **已应用的迁移不许改** —— 加列 / 删表一律**新写一条迁移**。
3. ⭐ **迁移必须打到两个库**：`TEST_DATABASE_URL`（给断言）＋ `DATABASE_URL`（给真机）。
   ⚠️ `down_revision` 用 **alembic API**（`ScriptDirectory.get_heads()`）算，⛔ **别用正则手算**（踩过：分叉成两个 head）。
4. ⛔ **不许留假值** —— 没数据就留空 / 标"待接通"，⛔ 不写 `—`/`0` 冒充；
   界面上有一列，后端就得**真有**那个字段（见 §7）。
5. ⭐ **判据化**：每个 claim 都要有**能证伪**的断言。⚠️ 写完先问一句
   **"什么样的实现会让它变红？"** —— 答不上来 = 这条断言没有区分力（本项目反复踩）。
6. ⛔ **文档 / 代码里的"已接 / 已完成"必须有落点** —— 没核过就宣称已接，是最贵的一类错。
7. ⭐ **改一处要顺手同步**（漏了**静默失效、不报错**）：`WIRED` · `PAGE_LOAD` · `CHG` ·
   两张登记表（`tools/*_expected.txt`）· ⭐ **界面上有「操作人/录入人」列 ⇒ 后端必须有字段**。

## 4. ⭐ 本仓的两个"机器守卫"（机制，⛔ 别绕过）

| 守卫 | 真源 | 守什么 |
|---|---|---|
| **`T8`** 撤项复活 | `tools/audit_common.py::CANCELLED` | 用户裁定**取消**的东西**不得在代码里长回来**。`clean=True` ⇒ 复活报**红**；`clean=False` ⇒ 还有残骸报**黄**（提示清理后改 True）。⚠️ 扫描面**只含业务代码**（`backend/app/**`、`backend/tests/`、`tools/`），⛔ **不含 `demo/`（原型是留痕）与 `backend/alembic/versions/`（迁移链是历史）**。 |
| **`U1`** 原型逐行 | `tools/ui_parity.py` ＋ `tools/ui_parity_expected.txt` | 壳的 `V.<页>` 切片必须与原型**逐行一致**。⚠️ 改切片 ⇒ **原型必须同改且同句**；登记簿**只准变短**。 |

⚠️ 另有 `T2`（已废术语 `RETIRED_TERMS`）· `T1`（幽灵用例号）· `T3`（幽灵路径）·
`T4`（四态数字）· `T5`（单文件 >400 须登记 / >600 禁合入）· `T6`（尾巴台账）· `T7`（判据覆盖）。

## 5. ⭐ 当前状态（2026-09-20 夜 · 暂停开发以换工具）

- **判据四态**：**526 = 绿 526 · 红 0 · 待建 0 · 未绑定 0**（⭐ 判据线 100% 全绿）
- **链路对账**：认领 **102** · 已接 **100** ⇒ ⭐ **必须修 2**（两条**真缺口**）：
  1. **`P4` 超付处置**：真源要三半 —— ① 流水照记 ✅ 有落点（`mod05_flow/repository.py`）·
     ⚠️ ② 挂提醒 **缺** · ⚠️ ③ 报告单列 **缺**
  2. **`X` 全局导出 Excel（`TAIL-04`）**：**逐页在做 · 8/14 → 10/14 页**
     ✅ 已做：逐月欠款台账 · 总欠款 · 过程资料 · 大表 · 结算 · 提取 · 库存单据 · 集采台账 ·
     **`MOD-01` 项目档案**（`report_export/pj_export.py` ＋ `POST /api/m01/projects/export`）·
     **`MOD-05` 付款流水**（`report_export/fl_export.py` ＋ `POST /api/m05/flows/export`）
     ⚠️ 剩 **2 页**：**`MOD-03` 付款通知书台账**（`NT_THEAD` · `NO` · `GET /api/m03/notice-list`）·
     **`MOD-04` 付款计划审查结果**（`PL_THEAD` · `PLs` · `GET /api/m04/plans`）
     ⛔ **`MOD-02` i8 接口清单不算列表页**（用户 2026-09-20 裁定）—— 它是**接口说明表**、无后端数据源
- **服务**：`127.0.0.1:8000`（`uvicorn app.main:app`，工作目录 `backend/`）
- **最新迁移 head**：`d1f3a5c7e9b2`（`payment_flow.created_by`）· 两库均已到
- ⭐ **`MOD-12`「差异登记」整页已取消**（用户 2026-09-20 裁定）—— 差异的载体 = 库存单据的**调整单**，
  差异表由 `mod06_proc` 按调整单算。⛔ 别把它加回来（`T8` 兜着）。

## 6. ⭐ 下一步（暂停时的位置）

1. ⭐ **`TAIL-04` 剩 2 页后端**：`MOD-04` → `MOD-03`（样板 = `report_export/jc_export.py` 朴素导出；
   口径 = 收 **id 列表**、按传入顺序出、列 = 页面表头去「操作」、取值 = 页面显示的值）
2. ⭐ **`exp` 改真分发**：壳里 5~7 个按钮用的是**同一个动作** `exp`（`data-act="exp" data-t="…"`）
   ⇒ ⭐ 把 `exp` 改成"按 `data-t` 分发到后端"的真实现即可 —— ⛔ **完全不用动任何 `V.` 切片**
   ⇒ ⭐ **`U1` 零风险、不必改原型**（⛔ 别去改那些按钮的 `data-act`）
3. **`P4` 超付 ②③**（挂提醒 ＋ 报告单列）
4. ⚠️ **主文档 `§0` 现状快照需刷新**（它的 `§0.2/0.3` 还写着「`m11`/`m12`/`m13`/`m15` 是空模块」，
   ⚠️ 全过期）· 以及 **`§14.4c`（260 行）/ `§14.4e`（1329 行）/ `§16`/`§17`/`§18` 待归档**
   （下沉到 `.workbuddy/plans/归档-历史单元条目.md`，本仓惯例是**留一行指向归档**）

## 7. ⚠️ 操作纪律（本机环境坑，踩过多次）

- ⭐ **删文件 / 删目录用专用工具**（CodeBuddy 的 `delete_file` 能删目录），
  ⛔ **别用 shell 的 `Remove-Item -Recurse`** —— 会触发审批、而审批弹窗常不可见 ⇒ **必然超时**。
- ⭐ **提交信息先落文件再 `git commit -F`**（`.workbuddy/scratch/CB_MSG.txt`）；
  ⚠️ **PowerShell 不支持 heredoc**（`<<'MSG'`）；也**别把"写文件"和"用它的命令"放同一批**（竞态）。
- ⚠️ **行尾**：工作区 CRLF、仓库存 LF（`autocrlf`）⇒ 做**文本替换锚点**时要**在 LF 归一化的副本上匹配**。
- ⚠️ **别写内联 `python -c "..."`**（PowerShell 引号会打架）⇒ 一律**落成脚本文件**再跑。
- ⚠️ **自检脚本造的数据必须在事务里回滚**（或清场放 `finally`）—— 只写在末尾，
  ⚠️ 一旦断言抛异常就**留下残行**（踩过：开发库被留了 4 条流水）。
- ⚠️ 自检要先 `import app.core.models_registry`（否则外键 `NoReferencedTableError`）；
  直接调 FastAPI 端点时 `Depends` 参数**不可调**，要自己传 loader。
