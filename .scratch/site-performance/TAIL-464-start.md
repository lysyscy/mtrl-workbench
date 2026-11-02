# TAIL-464 开工报告（路线 A · 首轮开工批次）

2026-11-02 · DSH 执行者（系统提示可见 `workbuddy/deepseek-v4.1-flash`，请求 high）· 会话 `session-d976937c-38e0-41ab-923a-3ea7db4caae4`

- 基线：分支 `codex/site-performance-20261102`，HEAD `daf8a7fce9aaf932a7d971daa7db178ae7becaa4`（`git rev-parse HEAD` / `git rev-parse --abbrev-ref HEAD`，各 exit 0）。
- 运行配置：模型名仅系统提示可见；**reasoning effort 无任何工具输出回显**（`ops_discover_tools("list models reasoning effort")` 无匹配能力）⇒ 记「请求 high、运行配置未核验」。
- 本批次范围：读相关源码、建立可复现量测方案、确定首个候选与资源请求。**未执行真实数据库查询、`backend_verify`、浏览器或 HTTP 采样，未改产品代码与测试。**
- 本批次唯一新增文件 = 本报告。其余路径只读；未执行 `git add/commit/switch/reset/clean/stash`。
- 共用规格：Impeccable 4.8 optimize 的「固定真实输入 → 分阶段量测 → 再修主热点」。本阶段只做前两步的**准备**与**离线纯函数对照**，不宣称任何实测热点或性能收益。

---

## 1. 已核基线与相关文件归属

### 1.1 工作树状态（保护，不触碰）

`git status --porcelain`（exit 0）显示他人/本 effort 的既有改动：`M CONTRIBUTING.md`、`M docs/agents/issue-tracker.md`、`M docs/agents/workflow.md`、`M docs/guides/frontend-design.md`、`M docs/status.md`、`?? .impeccable/`、`?? .scratch/oilcard-management/`、`?? .scratch/site-performance/`、`?? .scratch/tails/issues/TAIL-464..472-*.md`、`?? .tmp-fees-width.py`、`?? DESIGN.md`、`?? PRODUCT.md`、`?? debug.log`。全部按保护处理；本报告只新增 `.scratch/site-performance/TAIL-464-start.md`。

### 1.2 归属表（本票写域＝`mod06_proc` 三件 + `process-api.ts`；其余为读）

| 路径 | 归属 | 本票动作 |
| --- | --- | --- |
| `backend/app/mod06_proc/repository.py` | **本票（464，共享 repository）** | 候选修改域 |
| `backend/app/mod06_proc/service.py` | **本票（464）** | 候选修改域 |
| `backend/app/mod06_proc/router.py` | **本票（464）** | 候选修改域（仅 `/api/m06/matrix`、`/api/m06/mech` 两个 GET 的装配段） |
| `apps/frontend/src/process-api.ts` | **本票（464）** | 候选修改域（`readProcess` 的 sources 校验/类型） |
| `backend/app/mod06_proc/workbench.py`、`workbench_api.py`、`workbench_view.py`、`mech_ui.py`、`domain.py`、`models.py` | 机械 workbench 实现与呈现，**由相应主人处理**（465 及 workbench 主人） | 只读；**本票不改** |
| `apps/frontend/src/process.tsx`、`process-export.tsx` | 465（过程呈现） | 只读；本票不顺带改 UI |
| `backend/app/report_export/{service.py,mechanical_export.py}` | 未分配 → 主控 | 只读；导出侧收益另列（§6.4） |
| `backend/app/mod05_flow/service.py`、`mod07_setl/big_service.py` | 467 / 集采域主人 | 只读消费者，靠 `service.load_mech` 默认行为不变 |
| `backend/app/core/{db,money,projects,history}.py`、共享 Grid/PageSurface/字体/缓存 | 主控共享 | 只读 |
| `backend/tests/**` | 各票具名检查；本票具名检查见 §2.4 | 本阶段只读，不改断言 |

---

## 2. 调用者、契约与现有最小检查

### 2.1 两个端点（`/api/m06/matrix` 与 `/api/m06/mech` 是两条**不同**的取数链）

- `GET /api/m06/matrix` → `router.py:69-79` `api_proc_matrix` → `service.build_matrices(s)`（`service.py:174-180`）：
  `_load_report_data(s)` **整体**取 `load_inv_rows` + `load_mech` + `load_history` + `load_cutoffs`（`service.py:118-122`），再按 `selected` 逐仓 `_matrix_for`（`service.py:125-138`，同快照 `build_matrix` 调两次 raw/adjusted + `diff_rows`/`diff_totals`/`column_totals`/`segment_totals`）。
  ⇒ **该路由一次请求里 `load_mech` 会把所有项目的全部机械行按「完整来源」构造一遍**，而矩阵装配只用 `mech_*` 六个原始列。
- `GET /api/m06/mech` → `router.py:91-169` `api_mech`：独立 `session_scope()`，再取 `repo.load_mech(s)`、`repo.load_history(s)`、`repo.load_cutoffs(s)`、`workbench.detail_signatures(s)`；对 details 中缺失月用 `workbench.effective(s, wh, ym)`（完整模式）补行（`router.py:114-120`）；`:153-159` 按 `D.column_source` 决定每月取快照还是手录；`:161-169` 装配 `sources`/`effective_signatures`/`effective_values` 全量送出。
  ⇒ 两路由**各有独立事务**（原子性不同），静态上是两次重复的机械/历史/cutoff 读取，但**不是同一 DB 快照**，不得在报告里说成"同一快照重复"。

### 2.2 `mech_effective` / `load_mech` 契约（逐字已核）

- `repository.py:34-36` `mech_sources(row)`：`stored = (row.source_batches or {}).get('__detail_sources', {})`，`return {column: deepcopy(stored.get(column, {'mode':'manual'})) for column in MECH_KEYS}` —— **每列一次 deepcopy**。
- `repository.py:39-57` `mech_effective(row, warehouse, ym, *, compact=False)`：
  - `values`：`format(to_money(getattr(row, column)), '.2f')`，`None`/`''` ⇒ `None`（**null / 0 / 空串三分**）。
  - `compact=True`：`sources = {column: stored.get(column, {'mode':'manual'}) ...}`（**无 deepcopy**）。
  - `compact=False`：`sources = mech_sources(row)`（6 次 deepcopy）。
  - `signature = sha256(json.dumps([values, sources, updated_at], ensure_ascii=False, sort_keys=True, default=str))` —— **两种模式签名逐字相等**（离线实测确认，见 §7）。
  - `result = {'warehouse','ym','values','sources','signature'}`；`compact` 再二次投影 `result['sources'] = {column: {'mode': ...}}`（**签名用的是投影前完整 sources，返回体用投影后**）。
  - `compact=False` 额外 `result['source'] = deepcopy(row.source_batches or {})`。
- `repository.py:91-99` `load_mech(s)`：逐行 `mech_effective(row, ...)`（**默认完整模式**），只输出 `{'ym','warehouse','project_id', 6 列原值, 'sources', 'effective_signature'}`。
  ⇒ **`state['values']` 与 `state['source']` 在这里被丢弃**，但那一份 `deepcopy` 已经付过。

### 2.3 字段消费者（决定"不能改什么"）

| 消费者 | 需要什么 | 证据 |
| --- | --- | --- |
| `/api/m06/matrix` 装配 | **只要 `mech_*` 六列原始值**，完全不读 sources/signature | `domain.py:201-214` `mech_by_month`；`domain.py:299-301` `row[key] = mech.get(ym, ...)[idx]` |
| `/api/m06/mech` → 前端屏幕 | **只要 `sources[wh][ym][col].mode` 字符串**、`effective_signatures`、`detail_signatures`、`effective_values` | `process-api.ts:15` 类型 `Record<...,{mode:string}>`；`:59` 只校验 `typeof columns[key].mode==='string'`；`process.tsx:85/:98/:105-112` |
| `/api/m06/mech` → 保存回执 | 完整来源 `basis`/`history`（写入后回执，不是读模型） | `test_mechanical_source_protection.py:89-94` |
| `workbench.state()` → 导出/快照链 | **完整来源**：`mechanical_export.py:92-106` 用 `sources[column]['basis']` 且以 `('amount' in basis and basis['amount'] is None)` 判"显式空" | `workbench.py:985-1004`（`effective()` 完整模式）、`workbench_view.py:32` |
| `workbench.page_state()` | **必须保持 compact 且不得 deepcopy** | `test_mechanical_workbench.py:54-132`（`SourceWithoutCopies` 让 `deepcopy` 抛 `AssertionError('page tried to clone discarded source/history facts')`） |
| `mod05_flow` / `mod07_setl` | 只要 `mech_2/mech_3` 或 6 列原值，**不读 sources** | `mod05_flow/service.py:261-273`、`mod07_setl/big_service.py:70-81`，均经 `service.load_mech` |

结论：**屏幕读模型可以只带 mode；完整来源仍是导出/快照/回执的契约，不能动。**

### 2.4 现有最小检查（本阶段未运行；判据文本已核）

| 判据 | 文件:行 | 保护的是什么 |
| --- | --- | --- |
| `test_process_get_exposes_same_source_and_signature_as_workbench` | `backend/tests/test_mechanical_source_protection.py:118-130` | **`/api/m06/mech` 的 `sources` 必须等于 `W.effective` 完整来源**、`load_mech` 的 `sources` 也必须等于它 ⇒ **直接锁死"把 `/mech` 改成 compact"** |
| `test_effective_keeps_unknown_cells_distinct_from_explicit_zero` | 同文件 `:46-52` | `0.00` / `''` / 未知 三分 |
| 同上 `:135-157`（PG） | 只读 `.mode` | compact 兼容 |
| `test_page_route_is_current_month_while_full_state_keeps_saved_contract` | `backend/tests/test_mechanical_api.py:105-117` | `'source' not in page['effective'][0] and 'source' in full['effective'][0]` ⇒ **`workbench.state` 必须保留 `'source'` 键**（即使全仓无读者） |
| `test_page_state_preserves_..._without_source_copies` | `backend/tests/test_mechanical_workbench.py:54-132` | `page_state` 不得 deepcopy 来源 |
| `test_接口按分界月给机械值_历史段读快照` | `backend/tests/test_page_m06.py:65-83` | 历史段（≤截止月）取快照、正式段取手录 |
| `test_zip_contents_names_and_sources_loaded_once` | `backend/tests/test_proc_report_data.py:118-134` | 各来源**各取 1 次**、`single_cutoff==0`、`mechanical_cutoffs==0` |
| `test_bucketed_matrices_keep_precedence_null_zero_order_and_document_trace` | 同文件 `:181-209` | 每仓 `build_matrix` **调两次**，raw/adjusted 与 legacy 全量结果相等 |
| `test_后端机械读数端点存在且形状对齐原型` | `backend/tests/test_wired_m06.py:39-45` | 端点与 `mech` 键存在（**文本断言，改装配时注意别动这两行**） |
| `apps/frontend/tests/test_process.py:23-57` | 真实副本 | 保存后只重读 `{m06/matrix, m06/mech, history/status}` |
| `apps/frontend/tests/test_process.py:176-178` | 真实副本 | 读 `sources` **只取 `.mode`** |

---

## 3. 首个可证伪热点、阶段指标与独立业务等值判据

### 3.1 静态计数（**是调用次数，不是 SQL 条数**）

- `/api/m06/matrix` 每次请求：`load_mech` 1 次 ⇒ `ProcMechManual` 全表 1 条 SELECT，然后**每行** 1 次 `mech_effective` 完整模式（= 6 次 `deepcopy` 列 + 1 次 `deepcopy(source_batches)` + 1 次签名 `json.dumps`）。
- `/api/m06/mech` 每次请求：`load_mech` 1 次（同上）、`load_history` 2 条全表 SELECT + 内存过滤、`load_cutoffs` 全表 1 条、`detail_signatures` 1 条 `Record.key LIKE 'details:%'` 全扫；再对 details 缺失月逐月 `workbench.effective()` （又来一次完整模式）。
- 两路由合计：`mech_effective` 完整模式至少跑 **2×行数**（matrix 一次、mech 一次，彼此独立事务）。
- **静态事实不可当 SQL 条数或耗时**：`execute` 次数需真实事件计数（§4.3 S1）。

### 3.2 三个候选假设（按"契约代价"从低到高；H1 是首个候选）

- **H1（首个候选，无接口变化）**：`/api/m06/matrix`（及同链路的 `export_proc`）付了 `load_mech` 的完整来源构造成本，但矩阵装配只用 `mech_*` 原始值。
  可证伪条件：真实快照上 `build_matrices` 内部耗时中，完整来源构造（`deepcopy`+签名）占比 **< 10%** ⇒ 假设不成立，不实施。
- **H2（无接口变化）**：`load_mech` 每行额外付一次 `deepcopy(row.source_batches)`，结果写入 `result['source']` 后**被 `load_mech` 直接丢弃**（`repository.py:96-98` 只取 `ym/warehouse/project_id/6 列/sources/effective_signature`；`grep` 全仓无 `state['source']` 读者；`tests` 亦无断言）。
  可证伪条件：真实快照上该副本占 `load_mech` 内部耗时 **< 10%** ⇒ 不实施。
- **H3（有接口变化，需主控裁定）**：`/api/m06/mech` 的 `sources` 对屏幕只需 `mode`，完整 `basis`/`history` 占单行载荷的绝对多数。
  **已知冲突**：`test_mechanical_source_protection.py:127`（`api_mech()['sources'] == state['sources']`）与 `:130`（`load_mech(...)['sources'] == state['sources']`）把完整来源钉死在 `/mech` 契约上。**本阶段不实施，只作为量测后的选项上报**；若实施必须先由主控与 workbench/导出主人共同裁定这条判据的去留。

### 3.3 阶段指标（S0–S6，同一请求内分阶段归集）

| 阶段 | 含义 | 采集方式 |
| --- | --- | --- |
| S0 | ASGI 路由入口→出口墙钟 | 包住路由函数 |
| S1 | SQL：语句条数 / 每条耗时 / 取回行数 | `before_cursor_execute` / `after_cursor_execute` 事件 |
| S2 | 事实读取与构造：`load_mech`、`mech_effective`、`deepcopy`、签名 | `perf_counter` 包裹（不改产品代码，探针里 monkeypatch 计时壳） |
| S3 | 装配：`build_matrix`×2、sources/signatures/effective_values 组装 | 同上 |
| S4 | 编码：`json.dumps` / `jsonable_encoder` 的 **bytes 与 ms** | 探针内 `len(encode(...))` |
| S5 | 传输：`encodedBodySize` / `decodedBodySize` / `transferSize`（含 gzip 前后） | 浏览器 `PerformanceResourceTiming` |
| S6 | 前端解码 + 渲染（`JSON.parse`、`readProcess` 校验、表格行） | DevTools/`performance.measure`，由主控调度 |

**必须分开报的四件事**（本票指名要求）：`sources` 子树字节、复制 CPU、SQL、编码；不得合成一个"总收益"。

### 3.4 三条证伪阈值（量测后逐条判，任一不达即"保持现状"）

1. `sources` 子树字节占单行载荷（或端点载荷）**< 20%**，且完整模式构造占端点内部耗时 **< 10%** ⇒ 不新增紧凑读模型，交付"保持现状的依据"。
2. 候选实现后端点内部耗时中位数改善 **< 10%**（且 p95 未改善）⇒ 不做接口形状变更。
3. S1（SQL）占端点内部耗时 **> 60%** ⇒ 优先级转 SQL/索引方向（不在本票读模型范围内），本票只记录证据。

### 3.5 独立业务等值判据（不用被测实现自己算期望）

对同一真实快照，逐项比对「原路径」与「候选路径」：

1. `matrices[wh].raw` / `.adjusted` 每行每月每列金额（含 null 与 `"0.00"` 区分）、行序（ym 升序唯一）、`totals`/`segments`（长度 4）/`diffs`/`diff_totals`/`cutoff_ym` —— 逐值相等。
2. `sources[wh][ym][col].mode` 逐格相等（`detail`/`manual`/`snapshot`）。
3. `effective_signatures[wh][ym]` 与 `detail_signatures[wh][ym]` 逐字相等（sha256 十六进制串）。
4. `effective_values[wh][ym][col]`：`None` / `"0.00"` / 其他两位小数字符串三分不变（对应 `test_mechanical_source_protection.py:46-52`）。
5. 历史段/正式段切分仍由 `domain.column_source` 唯一出口决定（`test_page_m06.py:65-83` 的"历史段读快照"必须仍过）。
6. 导出成品：`export_proc` 生成的 xlsx 逐格比对（`test_proc_report_data.py` 的 `workbook()` 读第 4 行起 B 列月份、C–R 列值），不得只比对结构。
7. 保存链路：`POST /api/m06/mech` / `/mech-cell` 后 `effective_values` 与来源 mode 的读回、`/mechanical` 手填回执里的 `basis`/`history` 不变。
8. 全部项目、全部月份仍一次可取（不得退化为首屏项目/当月/分页）。
9. 旧完整来源契约保持：`workbench.state`、`export_proc`、`/api/m06/workbench` 的 `'source'` 键与 `basis` 内容不变。

---

## 4. 可直接运行的量测方案（数据库参数一律占位符）

### 4.1 前置（主控授予后执行）

- 只读目标：`<READONLY_SOURCE_ENV>`（**只读账号/只读副本**）；正式 `.env`、DSN、Cookie、账号偏好**一律不读出、不打印**。
- 会话级保护：`SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;` + `SET TRANSACTION READ ONLY;`，结束 `ROLLBACK`。
- 独占时段：原/候选交替、同快照、同负载；期间不并行 `backend_verify`、预览采样或其它真实查询。
- 产物：进 `var/state/verification/<run>/`（经 `tools/artifact_lifecycle.py` 登记租约，结束回收），**不进 `.scratch/`**。
- 本阶段**不产生**任何日志/大 JSON/截图/临时脚本入库。

### 4.2 命令模板

```bat
:: ① 基线复核（只读）
git rev-parse HEAD
git rev-parse --abbrev-ref HEAD

:: ② 事实读取与发射端分段（进程内，只读会话，不起服务、不监听端口）
backend\.venv\Scripts\python.exe -B -X utf8 <run>\work\tail464_measure.py ^
    --source-env <READONLY_SOURCE_ENV> --repeat 5 ^
    --out var/state/verification/<run>\tail464-server.json

:: ③ 屏幕端字节与解码（复用既有离线测量工装，不启动/替换预览）
backend\.venv\Scripts\python.exe -B -X utf8 tools\dev\frontend_measure.py run ^
    --preview-run <PREVIEW_RUN_DIR> --baseline-summary <BASELINE_SUMMARY> --label tail464 ^
    --stage all
::    注：SCREEN_PAGES 只采 {'ledger','contracts','inventory'}，process 页要用 --stage all；
::    process 不进 screen 阶段是既有口径，改动需主控批准。

:: ④ 候选实现后的具名最小检查（独占测试目标）
backend\.venv\Scripts\python.exe -B -X utf8 tools\dev\backend_verify.py ^
    --source-env <TEST_SOURCE_ENV> ^
    --test tests/test_mechanical_source_protection.py ^
    --test tests/test_mechanical_api.py ^
    --test tests/test_mechanical_workbench.py ^
    --test tests/test_page_m06.py ^
    --test tests/test_proc_report_data.py ^
    --test tests/test_process_mechanical_confirmation.py ^
    --test tests/test_proc_split_cutoffs.py ^
    --test tests/test_layering.py ^
    --test tests/test_wired_m06.py ^
    -- -q
```

### 4.3 探针骨架（待主控批准后落地为一次性脚本）

```python
# tail464_measure.py —— 只读；不打印 DSN/参数；不写产品代码
import argparse, json, time, os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
# register_all() 后 import mod06_proc.repository as R, service as S6, domain as D

def open_readonly_session(env_path):
    url = os.environ["<READONLY_URL_ENV>"]        # ← 占位；脚本不 print
    eng = create_engine(url, pool_pre_ping=True)
    conn = eng.connect(); tr = conn.begin()
    conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    conn.exec_driver_sql("SET TRANSACTION READ ONLY")
    return Session(bind=conn), (tr, conn, eng)

class Meter:      # S1：语句条数/耗时；按 stage 归集
    ...

meter = Meter()
event.listen(session.connection(), "before_cursor_execute", meter.on_before)
event.listen(session.connection(), "after_cursor_execute", meter.on_after)

def timed(fn):                      # S2/S3：不改产品代码，只在这里包一层
    t0 = time.perf_counter(); out = fn(); return out, (time.perf_counter() - t0) * 1000

for i in range(args.repeat):        # 交替：原 → 候选 → 原 → 候选（同会话、同快照）
    rows, t_load = timed(lambda: R.load_mech(session))              # S2 原
    mats, t_mat  = timed(lambda: S6.build_matrices(session))        # S3 原
    payload = json.dumps(mats, ensure_ascii=False, default=str).encode()   # S4
    # 逐项比对见 §3.5；判定写入 JSON：sql_statements / ms_median / p95 / bytes / equal
```

**关键量（必须分开记录）**：`sources` 子树 `len(json.dumps(...))` 占整包比例；`deepcopy` 段耗时；签名 `json.dumps` 耗时；编码 `ms` 与 `bytes`；S1 语句数与每条耗时。

### 4.4 已知局限（量测前先写明）

- 本报告 §7 的**全部数字来自合成数据 + 纯函数**，只说明"成本结构随规模怎么变"，**不得当真实数据收益**。
- 合成基数的选择依据：`/api/m06/mech` 单次浏览器观察解码 3,264,194 B（plan.md 记录，2026-11-02 约 21:05–21:12）；§7 的 240 行 × 60 明细行 × 3 条 history 组合产生 3.42 MiB，**仅用于确认量级可复现，不代表真实分布**。
- `FakeSession` 不还原 `.where`，其 `execute` 次数 ≠ 真实 SQL 条数。
- 未取得独占时段前，§4.2 ②不执行。

---

## 5. 需要主控串行授予的资源与理由

| # | 请求 | 理由 | 影响面 |
| --- | --- | --- | --- |
| **R1** | **独占只读测量时段**（一个窗口，期间不并行 `backend_verify`/预览/其它真实采样） | 原/候选必须同快照、同负载交替；否则 10% 级差异会被邻路请求污染 | 阻塞 §3.4 判定 |
| **R2** | 批准把**一次性只读探针脚本**放进本轮 run 的 work 区（登记租约，结束回收） | §4.3 需要真实 DB 计时；不写成常驻工具、不进 `.scratch/` | 不写产品代码 |
| **R3** | 授权读取 `<READONLY_SOURCE_ENV>`（只读账号/只读副本，不打印 DSN） | 现有 `.env` 指向正式目标，**不得**用于探针 | 安全边界 |
| **R4** | 批准**进程内调用两个 GET**（TestClient，仅读，不起服务、不监听端口） | 只有进程内调用能同时量到 S1–S4；不批准则只做服务层对照 | 不触正式服务 |
| **R5** | 判定通过后，串行授予 `backend/app/mod06_proc/{repository,service}.py` 的写权（按 §6.1 顺序），`router.py` 与 `process-api.ts` **视 H3 是否获批**再放 | H1/H2 不需要改 `router.py`/前端 | 写权限 |
| **R6** | 就 `test_mechanical_source_protection.py:127-130` 的**契约去留**给出裁定（与 workbench/导出主人共同） | 该判据把"`/mech` sources = 完整来源"钉死；H3 若不获批，本票**永不做** sources 形状变更，只做 H1/H2 | 交叉/契约 |

---

## 6. 候选修改：精确文件、先后、交叉点

### 6.1 顺序（每步独立可回滚，前一步不改语义）

1. **C1 = H1 最小实现（无接口变化）**
   `backend/app/mod06_proc/service.py:118-122` `_load_report_data`：机械行改为**只取原始值**（不构造 sources/signature）。实现形态二选一，任一都保持 `service.load_mech` 的默认行为不变（`mod05_flow` / `mod07_setl` / 导出不受影响）：
   - 在 `repository.py` 增加 `load_mech_values(s)`（复用 `_snapshot_keys` 之外的 `MECH_KEYS` 直取），`service.py` 增加对应包间出口（**函数体内 `from app.mod06_proc import repository as R`**，守 `test_layering.py` 规则 D）；或
   - `repository.load_mech(s, *, with_sources=True)` 加关键字，`_load_report_data` 传 `with_sources=False`。
   验收：`test_proc_report_data.py:118-134`（各取 1 次）、`:181-209`（每仓 `build_matrix` 两次且与 legacy 相等）继续绿。
2. **C2 = H2（无接口变化）**
   `backend/app/mod06_proc/repository.py:39-57`：给"是否附 `result['source']`"加显式参数（默认 `True` 保 `workbench.state` 的 `'source'` 契约），`load_mech` 传 `False`（它本来就丢弃该键）。
   验收：`test_mechanical_api.py:105-117`（`'source' in full['effective'][0]` 仍真）、`test_mechanical_workbench.py:54-132` 继续绿。
3. **C3 = H3（有接口变化，**需 R6 裁定后才可做**）**
   `backend/app/mod06_proc/router.py:161-169` 把 `/api/m06/mech` 的 `sources` 投影为 `{mode}`（复用 `mech_effective(compact=True)` 的既有投影，投影必须在复制前）；同时 `apps/frontend/src/process-api.ts:15` 的类型本已只声明 `{mode:string}`（**无需改**），`readProcess` 校验也只需 `mode`（**无需改**）。
   **前置**：改 `test_mechanical_source_protection.py:127-130` 的判定（把"等于完整 sources"改为"mode 与完整 sources 逐格相等"，并由主控/主人确认这不是放宽保护）。
   若 R6 否决 ⇒ **C3 不实施**，`process-api.ts` 保持原样。

### 6.2 交叉点与禁止事项

- **`mod06_proc/workbench.py`**：`state()` 的完整来源、`page_state()` 的 compact 都**不动**（属 workbench 主人）。C2 的参数默认值必须保证 `workbench.effective()`（`workbench.py:116-124`）行为逐字不变。
- **`export_proc`**（`report_export/service.py:185-206`）复用 `build_matrices` ⇒ C1 会同时加速导出；但导出成品判据（`test_proc_report_data.py` 的 xlsx 逐格）必须仍绿。导出侧本身是否另做（P 次重复装配）不在本票写域。
- **`/api/m06/mech` 的 `workbench.effective()` 补行**（`router.py:114-120`）：它需要完整 `sources` 才能填 `basis`；C3 若实施，只投影**最终响应**，补行仍走完整模式。
- **不得**：把 compact 结果喂给 `report_export/mechanical_export.py:92-106`（会静默改变"显式空"判定，是**错值不是报错**）；加进程/全局 TTL 缓存；跨包直查 `repository`；改共享 Grid/PageSurface/字体/历史/缓存；顺手删 `test_wired_m06.py` 里的文本断言所依赖的 `mech` 键或端点行。
- **`service.load_mech` 的默认值必须保持完整**：`mod05_flow/service.py:261-273`、`mod07_setl/big_service.py:70-81` 都经它取数。

### 6.3 预期风险（未测，先登记）

- C1 若用"新增 `load_mech_values`"，`test_proc_report_data.py` 的 fixture 只 monkeypatch 了 `R.load_mech`，**新函数没被 patch** ⇒ 会打到真查询（`session=None`）。规避：新出口内部复用 `R.load_mech` 或在 fixture 允许的 `R.load_mech(...)` 形态上做参数化（**这也是我倾向 `with_sources=` 关键字而非新函数的原因**）。
- C2 的参数若写成位置参数会破外部调用；必须是关键字且默认 `True`。
- C3 即便获批，也会让前端 `readProcess` 的 `sources` 结构变化 —— 当前前端校验只要求 `mode:string`，**兼容**；但 `apps/frontend/tests/test_process.py:176-178` 的真实副本读取也只需 `mode`，兼容。

---

## 7. 实际执行的命令、原始退出码与未验项

### 7.1 已执行（全部只读/离线；工作树未改）

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `git rev-parse HEAD`、`git rev-parse --abbrev-ref HEAD` | 0 | `daf8a7fce9aaf932a7d971daa7db178ae7becaa4` / `codex/site-performance-20261102` |
| 2 | `backend/.venv/Scripts/python.exe -V` | 0 | `Python 3.15.1` |
| 3 | `$TEMP/tail464_probe.py`（`FakeSession` 跑真实 `R.load_mech`，1/50/200/200h3/800 行计时） | 0 | full 260/15822/80304/81996/437986 µs；compact 71/3929/23649/26962/96122 µs；比值 3.04–4.56×；**全部 `signature_equal=True`、`modes_equal=True`** |
| 4 | `$TEMP/tail464_probe2.py`（逐阶段归因，best-of-15） | 0 | 200 行/basis 20/hist 0：`mech_effective` 完整 344.3 µs、compact 110.8 µs；`deepcopy` 整包占完整模式 29.7%（basis 60 时 35.9%，加 history 39.8%；单行时 62.8%）；**签名 `json.dumps` 在新旧两模式都要付** |
| 5 | `$TEMP/tail464_probe3.py`（原型＝去掉被丢弃的 `result['source']`） | 0 | 200/60/h0：309.8 → 226.2 µs（−27.0%）；200/60/h3：894.0 → 542.0（−39.4%）；800/60/h3：954.0 → 573.1（−39.9%）；**`load_mech_contract_equal: true`、`sources_and_signature_equal: true`** |
| 6 | `$TEMP/tail464_probe4.py`（按行 json bytes） | 0 | 3 列/60 明细/3 history：full 18,494 B、compact 443 B、其中 `discarded_source_key` 18,185 B；**sources 子树占单行载荷 96.6–99.4%**；wire 比 16.3–90.4× |
| 7 | `$TEMP/tail464_probe5.py`（**装配+编码**端到端，`router.api_mech` 同形） | 0 | 240 行/60 明细/3 hist：装配 full 233.0 ms、compact 51.0 ms（4.56×）；投影完整→紧凑仅 **1.1 ms**；wire full **3,586,641 B（3.42 MiB）** vs compact 98,241 B（**36.5×**）；编码 full 34.8 ms vs compact 0.9 ms；240 行/20/0 与 30/20/0 两档同向 |
| 8 | `$TEMP/tail464_probe6.py`（三路取数对照） | **首次 1** → 修复后 **0** | 首次失败原文：`AttributeError: 'types.SimpleNamespace' object has no attribute 'project_id'`（探针伪对象缺列，非产品缺陷）。修复后：240/60/3 ⇒ `load_mech` 完整 230.5 ms、纯值 0.4 ms（576×）、compact 48.8 ms（4.72×）；wire 完整 3,600,720 B vs 纯值 44,160 B（81.5×）；`mode_equal`/`signature_equal` 均 True |
| 9 | `grep`/`sed` 只读核对（`process.py`、`router.py`、`service.py`、`repository.py`、tests） | 0（其中一次 exit 2，见下） | 见 §2 全部行号证据 |
| 10 | `grep -rn "build_page_data\|_load_report_data" backend/ apps/` | **2** | 唯一非零：`grep: backend/.pytest_cache: Permission denied`（该目录不可读，与结论无关；已改用限定路径重跑，exit 0） |

> §7 第 3–8 行**全部是合成数据 + 纯函数**，只证明"完整来源构造与载荷的成本结构"，**不构成任何真实数据上的性能收益声明**，也不得替代 §4 的真实只读采样。

### 7.2 未验项（如实登记）

1. **真实 DB 的 SQL 条数、单条耗时、取回行数** — 未测（无独占时段，禁真实查询）。
2. **`/api/m06/mech` 3,264,194 B / 2,546 ms、`/api/m06/matrix` 465,053 B / 2,607 ms 的归因**（排队 / SQL / 装配 CPU / 编码 / ASGI / 前端）— **完全未验**；本报告只给证伪条件与采集方案。
3. **真实数据规模**（项目数、机械行数、每列明细行数、history 条数、来源 mode 分布）— 未知；§7 的合成规模不代表生产。
4. **`backend_verify` / pytest 全部节点** — 未运行（需已确认专用测试库与独占目标）。
5. **导出成品 xlsx** — 未生成、未打开。
6. **前端**（`process.tsx` 渲染、`readProcess` 解码耗时、任何浏览器/HTTP 采样）— 未做。
7. **候选实现本身** — 未写进产品代码，只存在于 §7 的探针原型。
8. **H3 的契约冲突裁定** — 未做（需 R6）。
9. **模型/effort 运行配置** — 模型名仅系统提示可见，`reasoning effort` 无工具回显 ⇒ **未核验**。
10. **`projects_of` 的 docstring 与实现不一致**（`service.py:90-95` 说明含机械值，实现只取 inv+history）— 属观察点，**本票不改**，仅登记给主控。

---

## 8. 下一步（请主控裁）

1. **批准 R1–R4**（独占只读时段 + 一次性只读探针 + 只读来源 + 进程内 GET），我按 §4 产出真实快照上的**原/候选交替对照 JSON**（分 S0–S5，四类成本分开报）。
2. 按 §3.4 三条阈值判定：达标 ⇒ 进入 §6.1 的 **C1 → C2**（两步都不改接口，可独立量测）；不达标 ⇒ 本票交付"保持现状的依据"，不实施。
3. **R6（`test_mechanical_source_protection.py:127-130` 契约去留）** 请主控与 workbench/导出主人裁定；否决则本票**不做** `/api/m06/mech` sources 形状变更，`process-api.ts` 保持原样。
4. 导出侧（§6.2）请主控明确归属后再动 —— 本票只提供上限估计，不擅自扩域。
