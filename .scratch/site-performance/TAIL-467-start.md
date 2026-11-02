# TAIL-467 开工报告（路线 C · 首轮开工批次）

2026-11-02 · DSH 执行者（`workbuddy/deepseek-v4.1-flash`，请求 high）· 会话 `session-ebfe5a89-9916-40ea-9dcf-b08bd5b2c071`

- 基线：分支 `codex/site-performance-20261102`，HEAD `daf8a7fce9aaf932a7d971daa7db178ae7becaa4`（`git rev-parse HEAD` / `git rev-parse --abbrev-ref HEAD` / `git log -1`，各 exit 0）。
- 运行配置：系统提示可见 `deepseek-v4.1-flash`；**reasoning effort 未由任何工具输出回显** ⇒ 只记「请求/继承 high、运行配置未核验」。
- 本批次范围：源码核查、可复现量测方案、首个候选与资源请求。**未执行真实数据库查询、backend_verify、浏览器/HTTP 采样，未改产品代码与测试。**
- 本批次唯一新增文件 = 本报告。其余路径只读；未执行 `git add/commit/switch/reset/clean/stash`。

---

## 1. 已核基线与相关文件归属

### 1.1 工作树状态（保护，不触碰）

`git status --porcelain`（exit 0）显示他人/本 effort 的既有改动：`M CONTRIBUTING.md`、`M docs/agents/issue-tracker.md`、`M docs/agents/workflow.md`、`M docs/guides/frontend-design.md`、`M docs/status.md`、`?? .impeccable/`、`?? .scratch/oilcard-management/`、`?? .scratch/site-performance/`、`?? .scratch/tails/issues/TAIL-464..472-*.md`、`?? .tmp-fees-width.py`、`?? DESIGN.md`、`?? PRODUCT.md`。全部按保护处理。

### 1.2 归属表（本票只写 `mod05_flow` 三件；其余为读）

| 路径 | 归属 | 本票动作 |
| --- | --- | --- |
| `backend/app/mod05_flow/router.py`、`service.py`、`domain.py` | **本票（467）** | 候选修改域 |
| `backend/app/mod05_flow/repository.py` | `471` 与本票逐文件核开 | 本阶段不改；如需改先报主控与 471 |
| `backend/app/mod03_notice/{repository,notice_actions}.py` | 471（通知与流水核对） | 只读；发现调用点但不改 |
| `backend/app/mod06_proc/{service,repository}.py` | 464（路线 A） | 只读消费 `service.load_mech` |
| `backend/app/mod11_jc/**` | 468（路线 B）/集采域主人 | 只读消费 `service.build_list`、`debt_of_ledger` |
| `backend/app/report_export/service.py`（`export_ledger`） | 未分配 → 主控 | 只读；导出侧收益作为申请另列（§6.4） |
| `backend/app/core/{projects,money}.py`、共享 Grid/PageSurface/字体/历史/缓存 | 主控共享 | 只读 |
| `apps/frontend/src/flow.tsx`、`ledger*.tsx` | 未分配（本票不改） | 只读消费者确认 |

---

## 2. 调用者、契约与现有最小检查

### 2.1 端点与响应契约（已核源码）

- `GET /api/m05/debt` → `router.py:192-195` `api_debt` → `get_debt_data()._load`（`router.py:48-67`）：
  1. `svc.build_debt_live(s)` → 返回 `by_category`（material/mechanical/jc 顺序固定）、`total`、`by_project`（含「未判定」单列）、`mech_settle_ready`、`openings`（`id/category/category_label/project_id/project_key/project_label/cutoff/settle/paid`，金额 2 位字符串）。
  2. `data["by_project_category"] = [{project, jc, material, mech}(2 位字符串)]`（来源 `svc.total_debt_rows(s)["items"]`，行序 = `order_project_ids` 展示名升序）。
  3. 追加「待指定归属」行（仅当 `domain.debt_by_category(unassigned, [])` 的 material/mechanical 有非零），`jc` 固定 `"0.00"`。
- `GET /api/m05/ledger?project_id=&end_ym=` → `service.build_ledger`（`service.py:398-459`）：`sides` 顺序 = `dom.LEDGER_SIDES` = `(material, mechanical)`；行序 `shown.sort(key=(month, row_kind=="month", record_id or 0))`；行 token 由 `history.cell_token/record_token` 产出，导出侧 `report_export` 直接用同一 `sides`。
- `GET /api/m05/ledger/export` → `report_export.service.export_ledger`（`report_export/service.py:125-163`）→ **逐项目** `M5.build_ledger(...)["sides"]` + `M9.build_export_data` + `ledger_export.build_xlsx`，≥2 项目打 zip。
- `GET /api/m05/debt/export` → `svc.export_total_debt` → `total_debt_rows(order=...)` → `debt_export.build_xlsx`。

### 2.2 装配函数的生产调用点（已核，全仓 `grep`）

| 函数 | 调用点 |
| --- | --- |
| `build_debt_live` | `router.py:53`（债务页）、`mod03_notice/notice_actions.py:276`（手改统计金额后的欠款重算回执） |
| `build_debt` | `build_debt_live`；离线自检 `tests/test_page_m05.py:30`、`tests/test_request_local_reads.py:19` |
| `total_debt_rows` | `router.py:57`、`service.export_total_debt`；`tests/test_historical_balances.py` 直接调用 |
| `build_ledger` | `router.py:73`、`report_export/service.py:155`；`tests/test_page_m05.py`、`test_request_local_reads.py` |
| `notice_debt_views` | `service.py:85`（`opening_views` 内）、`:202`、`:322`、`:407`、`:484`、`router.py:60` |

### 2.3 响应字段的消费者（决定「不能删什么」）

- 前端：`apps/frontend/src/flow.tsx:40-43` 只消费 `by_project_category`（校验 `record(data) && Array.isArray(...)`，只映射 `{project,jc,material,mech}`）。`by_category`/`total`/`by_project`/`openings` **当前无前端消费者**。
- 但 `notice_actions.py:277` 用 `debt["by_category"]` 拼中文回执；`tests/test_page_m05.py`、`tests/test_acc_flow_debt.py`、`tests/test_historical_balances.py` 直接断言 `by_category`/`by_project`/`openings`/`total_debt_rows`。⇒ **本票一律保留全部字段与顺序**，不做「删无用字段」的顺手优化（那属于别的候选）。

### 2.4 现有最小检查（本阶段未运行，需 DB；判据文本已核）

| 节点 | 钉住什么 |
| --- | --- |
| `backend/tests/test_request_local_reads.py::test_m05_reuses_openings_and_keeps_ids_and_amounts` | `build_debt` 内 `opening_views` **恰一次**（`calls == [None]`）、`openings` 全字段含 `id/project_key/settle` |
| `...::test_m05_reads_ledger_openings_once_and_keeps_missing_side_none` | `build_ledger` 内 `M5.repo.list_openings` **恰一次**（`calls == [7]`）、行金额字符串、`opening_id is None` |
| `...::test_debt_projection_keeps_all_facts_and_reads_fresh_values` | 真会话：`notice_debt_views` **只有 1 条 SQL**、投影**不含** `payment_notice.fields`、**重读拿到新值**（禁跨请求缓存、禁加宽投影） |
| `backend/tests/test_acc_flow_debt.py::test_集采欠款必须由装配层注入不许恒零` | `build_debt_live` 不给 `jc_debt` 时必须现取（monkeypatch `M11.debt_of_ledger`）；且 `router.py`/`notice_actions.py` 源码须含 `build_debt_live` |
| `backend/tests/test_page_m05.py` | 离线组装层：`by_category` 顺序与标签、`by_project` 含「未判定」、台账两侧、`order_project_ids` 行序 |
| `backend/tests/test_debt_export.py::test_总欠款的口径与页面同源` | 源码级：`total_debt_rows` 内必须见 `dom.debt_by_category` 与 `build_list`，**不许**出现 `settle_stat/pay_stat` |

⇒ 任何候选都必须保持：`build_debt`/`build_ledger` 默认路径签名与调用次数不变（否则上表首两条会红），`build_debt_live` 仍须走 `M11.debt_of_ledger`。

---

## 3. 首个可证伪热点、阶段指标与独立业务等值判据

### 3.1 静态重复装配计数（**调用数，不是 SQL 轮次，不是性能结论**）

单个 `/api/m05/debt` 请求内（源码逐行核对，并用离线夹具探针实测一致，见 §7）：

| 被重复调用的组装件 | 次数 | 位置 |
| --- | --- | --- |
| `notice_debt_views`（1 次窄投影读 `debt_notice_rows`） | **5** | `build_debt:202`、`opening_views` 内 `:85`、`total_debt_rows:322`、其 `opening_views:323`、`router.py:60` |
| `opening_views`（内含 `repo.list_openings`） | 2 | `build_debt:203`、`total_debt_rows:323` |
| `project_index` | **4** | `build_debt:206`、`total_debt_rows:324`、`mechanical_settlements:263`（2 次调用各 1 次） |
| `mechanical_totals` → `mod06 load_mech` | 2 / 2 | `build_debt_live:257`、`total_debt_rows:325` |
| `mod11 build_list`（集采全量装配） | **2** | `debt_of_ledger:230`、`total_debt_rows:345` |

其中 `mod11 build_list` 自身还会 `list_contracts`（→ `PS.warehouse_index` → `all_projects`）+ `invoices_of_many` + `payments_of_many`（批量件内还有 `notices.stat_paid_of_many` 与 `flows.latest_effective_dates` 两次批量读）。

`/api/m05/ledger` 单请求：`notice_debt_views` 1、`repo.list_openings` 1、`mechanical_settlements` 1（→`project_index` 1）、`project_options`（→`project_index` 1）、`remarks_map` **2**（每侧一次）。

`/api/m05/ledger/export`（P 个项目）：`build_ledger` **P 次** ⇒ `notice_debt_views` **P 次**（每次全量窄投影）、`project_index` **2P 次**、`list_openings` P 次。

### 3.2 首个可证伪热点（候选一，可被数据推翻）

**命题**：`/api/m05/debt` 的耗时中有显著份额来自「同一请求内把同样五个事实源各取 2–5 次」（§3.1），把这五个事实在该请求内**各取一次**并交给现有纯金额函数，可显著降低该端点耗时与 SQL 轮次。

**证伪条件（写死，避免事后圆说）**：
1. 若原/候选在**同一只读快照**上，SQL 语句数下降但 **端点内部耗时下降 < 10%** ⇒ 说明成本不在重复取数（而在单次查询延迟、行构造、编码或 ASGI 排队），本票交付「保持现状的依据」，不实施。
2. 若重复部件的合计 SQL 时间 + 构造 CPU 占端点内部耗时 **< 20%** ⇒ 同上，不实施。
3. 若「原响应 vs 候选响应」在任一业务字段/顺序上不等（含零/负/未知/历史覆盖/待归属/集采跳过/机械来源）⇒ 立即停止，任何收益不得抵消。

**必须先量、不得先信的部分**：浏览器线索为 `/api/m05/debt` 19,495 B / 约 3,321 ms。**19 KB 的响应解释不了 3.3 秒** ⇒ 慢点可能在排队、单条 SQL 延迟或 ASGI/编码，本票不预设结论。

### 3.3 阶段指标（每次采样都要分别记录）

| 阶段 | 指标 | 采集方式 |
| --- | --- | --- |
| S0 请求排队 | 从进入 `_load` 到首条 SQL 的间隔 | 进程内计时 + 对照端点外时刻 |
| S1 SQL | 语句条数、返回行数、单条耗时之和、最慢 3 条的前缀（**不打印参数、不打印 DSN**） | SQLAlchemy `before/after_cursor_execute` 事件 |
| S2 事实装配 CPU | `notice_debt_views`、`opening_views`（`history.adjustments`）、`project_index`、`load_mech`（含 `mech_effective` 与 `deepcopy`）、`build_list` 各自耗时 | 按函数包裹计时 |
| S3 域计算 CPU | `debt_by_category`/`debt_by_project`/`total_debt`/`total_debt_rows` 的逐项目循环 | 同上 |
| S4 编码 | `jsonable_encoder` + `json.dumps(ensure_ascii=False)` 耗时与字节数 | 进程内 |
| S5 端点内部总耗时 | `_load` 全程（不含 ASGI/网络） | 进程内 |
| S6 真实 HTTP | 仅在主控另行授权时用既有采样入口；本阶段不做 | — |

### 3.4 独立业务等值判据（不复用被测实现自证）

1. **逐值 + 顺序**：`json.dumps(..., sort_keys=False)` 往返后 `==`；比较对象含 `by_category`（顺序 `material/mechanical/jc`）、`total`、`by_project`（含「未判定」单列与其位置）、`mech_settle_ready`、`openings`（逐条全字段，`id` 为真 id）、`by_project_category`（含末尾「待指定归属」行及其 `jc == "0.00"`）。键序变化也视为不等（前端解构 + 旧壳兼容）。
2. **独立复算**（用手工构造的固定小样本，不调 `debt_by_category`）：
   - 辅材 = Σ(未剔除辅材 `settle_stat`) − Σ(未剔除辅材 `pay_stat`) + 辅材期初（`opening` 仅在 `kind != "month"` 时全额计入；`kind == "month"` 只计与通知书差额）；
   - 机械 = 机械费有效两列（`mech_2/mech_3`）合计 − Σ机械 `pay_stat` + 机械期初；
   - 集采 = Σ（`tag == TAG_IN` 且 `project_key` 在名册）合同 `debt`，`quantize(0.01)`；
   - 「待指定归属」= 仅 `ownership_id is None` 且未剔除的行，按辅材 `settle−pay`、机械 `−pay`。
3. **零/负/未知**：`0` 必须出 `"0.00"`（不得留空/不得省键）；负数原样保留；`jc_debt=None` 必须是 `"0.00"` 而不是缺失；无日期行不计月但机械 `−pay` 仍进项目行。
4. **跳过与标签**：`jc_skipped` 计数相等（非 `TAG_IN` 或项目不在名册）；「待确认/不纳入」不得进集采金额。
5. **历史覆盖与 token**：台账两侧行 `token`（`cell_token`/`record_token`）逐行相等；期初行 `record_id` 与 `/api/m05/debt` 的 `openings[].id` 同源相等。
6. **导出口径**：`sides` 是导出的唯一输入（`ledger_export.build_xlsx` 不取数）⇒ 台账页与导出等值判据 = `sides` 深相等；导出成品的 `tpl_fill.verify_filled` 仍须通过（本阶段不跑）。
7. **新鲜度**：`notice_debt_views` 仍须每请求重读（`test_debt_projection_…` 的第 3 段）；任何事实只活在**本次请求的会话对象**内，不放进程级缓存。

---

## 4. 可直接运行的量测方案（命令与参数均为占位；本阶段不执行）

### 4.1 前置（由主控授予后执行）

- 只读目标：`<READONLY_SOURCE_ENV>` = 专用只读库/只读账号的来源配置文件（**不打印 DSN、不读凭据内容**）。
- 只读保证：脚本显式 `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ; SET TRANSACTION READ ONLY;`，结束时 `rollback()`，全程只发 SELECT。
- 产物：探针脚本放**本轮 run 的 work 区**（`tools/audit/workspace_paths.py` 登记），输出 JSON 报告进 `var/state/verification/<run>/`；**不写 `.scratch/`**（scratch 只放活动 Markdown/票）。
- 时段：主控独占测量窗口，期间不并行跑 `backend_verify`、前端预览或其它真实采样（避免前后对照被负载污染）。

### 4.2 命令模板

```bat
:: ① 只读对照采样（原路径 vs 一次事实装配，同一快照交替 N 次）
backend\.venv\Scripts\python.exe -B -X utf8 <run>/work/tail467_measure.py ^
    --source-env <READONLY_SOURCE_ENV> --repeat 5 --projects 10 ^
    --out var/state/verification/<run>/tail467-measure.json

:: ② 端点级（仅进程内 GET，不起服务、不写库；需主控单独批准）
backend\.venv\Scripts\python.exe -B -X utf8 <run>/work/tail467_measure.py ^
    --source-env <READONLY_SOURCE_ENV> --repeat 5 --in-process-endpoint ^
    --out var/state/verification/<run>/tail467-endpoint.json

:: ③ 具名最小检查（候选实现后；独占测试目标）
backend\.venv\Scripts\python.exe -B -X utf8 tools\dev\backend_verify.py ^
    --source-env <TEST_SOURCE_ENV> ^
    --test tests/test_request_local_reads.py ^
    --test tests/test_page_m05.py ^
    --test tests/test_acc_flow_debt.py ^
    --test tests/test_debt_export.py ^
    --test tests/test_acc_flow_led.py ^
    -- -q
```

### 4.3 探针脚本（待落地；与 §7 已验证的原型同源）

与 §7 跑通的 `original()` / `candidate()` 逐字相同，只把数据源从 `FakeSession` 换成真实只读 `Session`，并加事件计时与阶段包裹。要点：

```python
# tail467_measure.py（骨架）—— 只读；不打印 DSN/参数
import argparse, json, time, os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
# … register_all() 后 import M5 / P6 / M11 / domain / history …

def open_readonly_session(env_path):
    url = os.environ["<READONLY_URL_ENV>"]            # ← 占位；脚本不 print
    eng = create_engine(url, pool_pre_ping=True)
    conn = eng.connect(); tr = conn.begin()
    conn.exec_driver_sql("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    conn.exec_driver_sql("SET TRANSACTION READ ONLY")
    return Session(bind=conn), (tr, conn, eng)

class Meter:            # S1：语句条数/耗时；按 stage 归集
    ...
meter = Meter()
event.listen(session.connection(), "before_cursor_execute", meter.on_before)
event.listen(session.connection(), "after_cursor_execute", meter.on_after)

for i in range(args.repeat):        # 交替：原 → 候选 → 原 → 候选
    for name, fn in (("original", original), ("candidate", candidate)):
        meter.begin(name)
        t0 = time.perf_counter(); data = fn(session); dt = time.perf_counter() - t0
        enc = json.dumps(jsonable_encoder(data), ensure_ascii=False, default=str)
        payload[name].append({"ms": dt*1000, "bytes": len(enc.encode()),
                              "sql": meter.stage_sql(name), "data": enc})
# 判定：中位数对比 + 逐值相等（json 字符串比较，含键序）
```

判定输出（写进 JSON 报告）：`sql_statements_original/candidate`、`ms_median/p95`、`bytes`、各 stage 毫秒、`equal: true/false`、以及 §3.2 的三条证伪阈值是否触发。

### 4.4 已知局限（量测前先写明）

- `FakeSession`（现成夹具）**不还原 `.where` 过滤**，所以 §7 的 `execute` 次数只等于「会话交互次数」，**不等于真实 SQL 条数**；真实条数必须在真库上用事件计数（§4.3）。
- 合成规模数据（§7.3）只证明「重复装配随行数增长」，**不得当真实数据收益**。
- 台账导出侧只做「上限估计」（重复全量读 P 次 vs 1 次），未复刻 `build_ledger` 全逻辑到探针。

---

## 5. 需要主控串行授予的资源与理由

| # | 请求 | 理由 | 影响面 |
| --- | --- | --- | --- |
| R1 | **独占只读测量时段**（一个窗口，期间不并行 backend_verify/预览/其它真实采样） | 原/候选交替对照必须同快照、同负载；否则 3.3 s 级差异会被邻路请求污染 | 阻塞 §3.2 判定 |
| R2 | 批准新增**一次性只读探针脚本**到本轮 run 的 work 区（登记租约，结束回收） | §4.3 需要真实 DB 计时；不写成常驻工具、不进 `.scratch/` | 不写产品代码 |
| R3 | 授权读取 `<READONLY_SOURCE_ENV>`（只读账号/只读副本；不打印 DSN） | 现有 `.env` 是正式目标，**不得**用于探针；需要明确只读目标 | 安全边界 |
| R4 | 需要时批准**进程内 GET** `/api/m05/debt`（TestClient，仅读，不起服务、不监听端口） | 只有进程内调用能同时量到 S4 编码与 S5 端点内部总耗时；不批准则只做服务层（S1–S3）对照 | 不触正式服务 |
| R5 | 判定通过后，串行授予 `backend/app/mod05_flow/{domain,service,router}.py` 的写权（按 §6 顺序），并由主控决定 `report_export/service.py:148-159` 归谁 | 导出侧的 P 次重复装配不在本票候选域内，需主控分配 | 写权限 |
| R6 | 与 471 确认 `mod05_flow/repository.py` 的读取边界（本阶段**不改**；若后续需要「一次取全部期初」则先核 471） | `repo.list_openings(project_id=...)` 的批量形态变更会碰 471 的按对象读取 | 交叉 |

---

## 6. 候选修改：精确文件、先后、交叉点

### 6.1 顺序（每步都可独立回滚，前一步不改语义）

1. **`backend/app/mod05_flow/domain.py`**：新增纯容器 `@dataclass(frozen=True) class DebtFacts`（字段：`rows: list[NoticeDebtView]`、`openings: list[OpeningView]`、`index: dict`、`mech_by_month: dict[int, dict[str, Decimal]]`、`jc_rows: list[dict]`），附纯属性 `mech_totals()`、`unassigned_rows()`。**不 import Session**（守 `test_layering` 规则 A 与离线自检）。
2. **`backend/app/mod05_flow/service.py`**：
   - 新增 `assemble_debt_facts(s) -> DebtFacts`：各源**各读一次**（`notice_debt_views` 1、`history.adjustments(repo.list_openings(s, project_id=None), rows)` 1、`project_index` 1、`P6.load_mech` 1、`M11.build_list` 1）。
   - `build_debt(s, *, jc_debt=None, mech_settle_total=Decimal("0"), facts=None)`：`facts is None` 时**保持现有逐次取数路径**（满足 `test_request_local_reads` 首条 monkeypatch 计数）；给定 facts 时用 facts。
   - `total_debt_rows(s, *, order=None, facts=None)`：同上，`mechanical`/`index`/`rows`/`openings`/集采行全部取 facts。
   - `build_debt_live(s, **kw)`：`facts` 透传；**仅当 `jc_debt` 未显式给且给了 facts** 时用 facts 的 `jc_rows` 复算（算法与 `M11.debt_of_ledger` 逐字一致：`TAG_IN` 累加 + `quantize(0.01)`）；否则仍调 `M11.debt_of_ledger`（满足 `test_集采欠款必须由装配层注入不许恒零`）。
   - `build_ledger(...)`：**本批不改**（其重复只有 `project_index` 1 次 + 每侧 `remarks_map`，收益未证；导出侧的 P 次重复留给 R5 决定）。
3. **`backend/app/mod05_flow/router.py` `get_debt_data()._load`**：`facts = svc.assemble_debt_facts(s)` 一次；`svc.build_debt_live(s, facts=facts)`；`svc.total_debt_rows(s, facts=facts)`；「待指定归属」改用 `facts.unassigned_rows()`（不再第 5 次取通知书）。响应字段与顺序**一字不改**。

### 6.2 交叉点与禁止事项

- **`mod11 build_list` 的两次调用**：`debt_of_ledger`（总量，quantize）与 `total_debt_rows`（逐项目）。合并必须逐字保留 `TAG_IN` 判定、`project_key → pid` 映射（不在名册 ⇒ `jc_skipped += 1`）、quantize 只在总量那一处。
- **`mod06 load_mech`**：只消费 `service` 出口；`mech_effective` 的 `deepcopy(sources)` 与签名**不动**（那是 464 的读模型）。
- **`mod03_notice/notice_actions.py:276`**：不改；它不传 facts ⇒ 行为与今天完全一致（该回执本身只有 1 次装配，不是重复点）。
- **不得**：加进程/全局 TTL 缓存、跨请求复用事实、跨包直查 repository、改共享 Grid/PageSurface/字体/历史/缓存、动 `notice_debt_rows` 的窄投影（`test_debt_projection_…` 会红）。
- **`repository.py`**：本候选**不需要**改。若将来为导出做「一次取全部期初」，那是 repository 变更 ⇒ 先报 471。

### 6.3 预期风险（未测，先登记）

- `build_debt`/`total_debt_rows` 增加 `facts` 关键字，若外部还有未发现的调用者靠位置参数传参会破；已核全仓调用点均为关键字或单参（§2.2）。
- `project_index` 只取一次后，`build_debt` 的 `names` 与 `openings` 的 `project_key/project_label` 共用同一份索引 —— 语义不变（同请求同快照），但**跨请求新鲜度**仍由每次重读保证。

### 6.4 导出侧（不在本票写域，申请另分配）

`report_export/service.py:148-159` 对 P 个项目各调一次 `build_ledger`，每次全量重读通知书（§3.1）。静态上这比页面路由更贵；但该文件不属于 467 候选域，建议由主控在 467 判定后决定是否并入（或留给 472 收敛），本阶段只提供上限估计（§7.4）。

---

## 7. 实际执行的命令、原始退出码与未验项

### 7.1 已执行（全部为只读/离线；工作树未改）

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `git rev-parse HEAD` / `git rev-parse --abbrev-ref HEAD` / `git log -1 --format='%H %s'` | 0 | HEAD `daf8a7fc…`，分支 `codex/site-performance-20261102`，末条提交 `docs: record mechanical performance production release` |
| 2 | `git status --porcelain \| head -20` | 0 | 见 §1.1（保护） |
| 3 | `backend/.venv/Scripts/python.exe -c "import sys;print(sys.version)"` | 0 | `3.15.1 (main, Oct 21 2026, …) [MSC v.1951 64 bit (AMD64)]` |
| 4 | `… -c "import app.mod05_flow.service as M5, app.mod05_flow.router as R; print(...)"` | 0 | 无 DB 可导入（`{'material': '辅材', 'mechanical': '机械', 'jc': '集采'}`） |
| 5 | `$TEMP/tail467_probe.py`（离线调用计数 + 200 次计时） | **1（失败）** → 修复后 **0** | 失败原文：`RuntimeError: 项目行的取数口没接上 ⇒ project_index 拒做 —— 见 app.core_bindings.register_all()`。**教训**：离线探针必须先 `register_all()`（生产由 `app/main.py` 与 `tests/conftest.py` 顶层接线），否则 `project_index` 拒做。修复后输出：`{"build_list": 2, "load_mech": 2, "mechanical_settlements": 2, "mechanical_totals": 2, "notice_debt_views": 5, "opening_views": 2, "project_index": 4, "total_debt_rows": 1}`，`total_calls: 20`，夹具中位 1.410 ms / p95 2.678 ms，payload 833 B；台账请求 `{"load_mech":1,"mechanical_settlements":1,"notice_debt_views":1,"project_index":2}`，1.350 ms / 3,600 B |
| 6 | `$TEMP/tail467_equiv.py`（原路径 vs 一次装配，逐值+顺序） | 0 | `[OK] fixture默认` / `[OK] 边界行(零/负/无日期/机械零)` / `[OK] 空数据集`，`ALL_EQUAL= True` |
| 7 | `$TEMP/tail467_load.py`（会话交互次数） | 0 | fixture：原 `(23,0)` → 候选 `(9,0)`（少 14）；空集：原 `(21,0)` → 候选 `(8,0)`（少 13）。**这是 execute 调用次数，不是真实 SQL 条数**（夹具不还原 `.where`） |
| 8 | `$TEMP/tail467_scale.py`（**合成数据**规模敏感性） | 0 | 项目/通知书：`1/5`：2.8→1.3 ms；`20/2000`：118.7→34.3 ms；`50/20000`：1525.9→428.4 ms；`120/60000`：4954.9→1757.1 ms；四组均 `等值=True`。分解（50/20000）：`notice_debt_views` 143.3 ms、`total_debt_rows` 465.1 ms、`build_debt_live` 780.7 ms、`build_ledger(1 项目)` 199.9 ms |
| 9 | `$TEMP/tail467_export.py`（**合成数据**；P=10、N=20000） | 0 | 逐项目 `build_ledger × 10` = 2,630.1 ms，`calls={'notice_debt_views': 10, 'project_index': 20, 'list_openings': 10}`；单项目 232.3 ms、`project_index` 2 |

> §7 第 8、9 行为**合成数据**：只说明「重复装配的成本随行数增长」，**不构成任何真实数据上的性能收益声明**；夹具与合成数据均不得替代 §4 的真实只读采样。

### 7.2 未验项（如实登记）

1. **真实 DB 的 SQL 条数、单条耗时、端点内部耗时** — 未测（无独占时段、禁真实查询）。
2. **`/api/m05/debt` 的 3,321 ms 归因**（排队 / 单条 SQL / 装配 CPU / 编码 / ASGI）— 完全未验；本报告只给证伪条件和采集方案。
3. **backend_verify / pytest 全部节点** — 未运行（`tests/conftest.py` 顶层守卫要求已确认测试库，离线跑不了）。
4. **台账导出成品**（`ledger_export.build_xlsx` + `verify_filled`、zip）— 未运行、未打开文件。
5. **前端**（`flow.tsx` 渲染、`ledger.tsx` 标脏后失效、任何浏览器/HTTP 采样）— 未做。
6. **真实数据规模**（项目数、通知书行数、期初条数、集采合同数、机械行数）— 未知；§7.3 的合成规模不代表生产。
7. **候选实现本身** — 未写进产品代码，只存在于 §7 的探针原型。
8. **`build_ledger`/导出侧的候选** — 未设计到可实施粒度（只给了重复计数与上限估计）。
9. **模型/effort 运行配置** — 系统提示可见 `deepseek-v4.1-flash`，reasoning effort 无工具回显 ⇒ 未核验。

---

## 8. 下一步（请主控裁）

1. **批准 R1–R4**（独占只读时段 + 一次性只读探针 + 只读来源 + 进程内 GET 可选），我按 §4 产出真实快照上的原/候选对照 JSON。
2. 按 §3.2 三条阈值判定：达标 ⇒ 进入 §6 实施（先 domain 容器 → service `facts` → router 单次装配）；不达标 ⇒ 本票交付「保持现状的依据」，不实施。
3. 无论判定结果，导出侧（§6.4）请主控明确归属后再动。
