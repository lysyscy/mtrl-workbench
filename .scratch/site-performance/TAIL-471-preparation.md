# TAIL-471 准备（源码/离线，未运行任何 live 资源）

基线 `8673a52c`（branch `codex/site-performance-20261102`）。本阶段只读源码、登记证据组；**未执行 probe、未改产品代码、未占 DB/HTTP/浏览器/pytest/preview**。

## 1. 归属与写域边界

| 项 | 值 |
| --- | --- |
| 本票候选写域 | `apps/frontend/src/notice-flows.tsx`、`flow-api.ts`；`backend/app/mod05_flow/{router,service,repository}.py`；`backend/app/mod03_notice/{list_view.py,notice_api_router.py}` 的所选核对链；对应具名检查 |
| 只读登记（不改） | `contract-subtables.tsx:164`（读全部 notice-list，事实）；`mod11_jc/service.py:614-634`（第三处全量合同装配）；`notice_api_router.py:561-601` 导出（全量捞后按 id 挑）；`flow.tsx:56`（流水页全量 `['flows']`） |
| 禁止 | 合同候选消费者缩集、金额/默认 flows 语义、467 事实路径（`notice_pay_actions.py:78,160`）改动 |

## 2. 真实消费者（单对象链的精确入口）

- 弹窗：`notices.tsx:195`「查看流水」→ `:150 viewFlows` → `:246 <NoticeFlows notice={flowNotice}>` ⇒ **每次一个 notice_id**。
- 弹窗读取：`notice-flows.tsx:14-15` `useQuery(['notice-flows', id]) → loadFlows(signal).filter(f => f.notice_id === notice_id)`。
- 请求：`flow-api.ts:17` 字面 `/api/m05/flows?year_month=`（**全部月份**）。后端 `router.py:177-191` 五参数，**无 notice 维度**。
- 装配：`mod05_flow/service.py:154-156` 全量 `all_notice_rows`（无 limit）+ `project_index` + `list_flows` 全量逐条 `_flow_dict`（13+ 键）⇒ 前端再丢 99%+。
- 付款核对：`notices.tsx:248` → `notice-payment.tsx:53-67` `GET /api/m03/payment-preview?ids=…` → `notice_api_router.py:506-510` `build_page_data(..., notice_ids=ids)`。

## 3. 已核热点（静态，均有源码行）

**H1 弹窗 = 全量取+本地筛**：`flow-api.ts:17` 无 notice 参数 ⇒ 每打开一个通知书重抛一次全量响应；`['flows']` 与 `['notice-flows',id]` 同 URL 异 key（`flow.tsx:56` vs `notice-flows.tsx:14`），`staleTime:0`（`main.tsx:73`）⇒ **无跨 key 复用**，两次请求各自全量。

**H2 payment-preview 只下推了通知书、没下推事实**：`list_view.py:187-195` 在**传了 notice_ids 时仍** `_flows_by_notice`（`list_flows` 全量）、`_links_by_notice`（`links_by_notice` 全量）、`_traces_by_notice`（`stat_trace_index` 全量）；唯一已下推项是 `:192 contracts.linked_suppliers(session, notice_ids)`。

**H3 build_flows 自身重复**：`service.py:155 projects = project_index(s)` 与 `:187 project_options(s)`（内部 `:91` 再调 `project_index`）⇒ 同请求两次全项目行。

**H4 弹窗序不可想当然**：`list_flows` 为 `pay_date DESC, id DESC`（`repository.py:35-38`）；`flows_of_notices` 为 `pay_date, id` **ASC**（`:41-47`）⇒ 直接换函数会**翻行序**。

**反证/边界（不可删的依据）**：`_flows_by_notice` 注释（`list_view.py:254-259`）要求**含已撤销**流水；`_flow_dict` 失联时 `amount_approved=None`（非 0）；`list_view` 8 键投影与弹窗 13+ 键**不是同一投影**；`NoticeRow.jc_supplier` 由 `linked_suppliers` 覆盖（`list_view.py:189-193,239`）—— **只传 `links_of` 而不给 suppliers 会静默改值**。

## 4. 原/候选同源等值判据（同快照，同一只读事务内交替）

1. 弹窗：候选 `rows` 与「全量 `build_flows` 结果按 `notice_id` 过滤」**逐条全等**（13+ 键逐值，含 `status_label`/`created_by` 空串/`revoked_at`/`request_id`），**行序全等**（必须仍是 pay_date DESC, id DESC）。
2. 已撤销与失联：目标通知书的 `revoked` 流水必须在；`notice_id IS NULL` 流水**按现状被过滤掉**（两路径都丢，属既有语义，不得顺手改）。
3. 空选：`payment-preview ids=[]` ⇒ `items==[]`（`repository.py:167-169` 返回 `[]`）；`flows_of_notices([])`/`links_by_notice([])` 不查库返回空（`test_tail310_selected_pay.py::test_selected_links_and_default_full_query` 已具名断言）。
4. 全量：`/api/m05/flows?year_month=` 不带 notice 参数时输出**逐字节等同**今日；`notice-list` 无 notice_ids 时行为不变。
5. payment-preview：候选 `items` 与今日逐字段全等（`_api_item` 全集，重点 `jc_supplier`/`has_link`/`edited_fields`/`amount_paid`/`has_effective_flow`/`has_any_flow`），`payment_methods` 同值。
6. 新鲜度：两路径都在**同一请求内**重读事实；不得引入跨请求缓存；付款前 `readPaymentContext`（`notice-payment.tsx:98`）与 `notices.tsx:102-103` 权威重读**不动**。

## 5. 阶段指标（分计，不合并成单值）

| 阶段 | 原 | 候选 | 采集 |
| --- | --- | --- | --- |
| S1 事实读 | `list_flows` 全量 + `stat_trace_index` 全量 + `links_by_notice`×2 全量 | 按 ids 三路 | SQLAlchemy `before/after_cursor_execute`：语句数 + 每语句 `cursor.rowcount` |
| S2 装配 | `_flow_dict`×全部流水 + `project_index`×2 | 仅目标流水 + 1 次 | `perf_counter` 包裹 |
| S3 序列化 | `json.dumps` 全量 payload | 目标 payload | `len(.encode())` |
| S4 端点 | 端点内总耗时 | 同 | 进程内 TestClient GET（需主控批） |
| S5 前端解析/绘制 | `flow-api.ts` 校验 + ReadGrid | 同 | **本阶段不测**；真实副本用 `data-layout-state` 到 `ready` 计时（`business-grid.tsx:56-81`） |

不把 S1–S4 的 Node/Python CPU 冒称 INP 或全页提升；前端绘制单列。

## 6. 只读 probe（已写好、已离线编译+导入自检；**未运行**、未连库）

脚本实体：`.../groups/site-performance-tail471-20261103/files/tail471_probe.py`（14.6KB）。已做且仅做：`py_compile` 通过、`--help` 通过、模块导入通过、`_median/_p95` 自检通过。**未执行 `run()`**，无 DB/网络。

```
backend\.venv\Scripts\python.exe -B -X utf8 ^
  "C:\Users\Administrator\AppData\Local\AgentArtifacts\projects\mtrl-workbench\groups\site-performance-tail471-20261103\files\tail471_probe.py" ^
  --source-env <READONLY_SOURCE_ENV 的绝对路径> ^
  --repo-root D:\dev\mtrl-workbench ^
  --notice-id <已知有流水的通知书ID> ^
  --ids <付款选中集,逗号分隔> --repeat 5 ^
  --out "C:\...\site-performance-tail471-20261103\files\tail471-probe.json"
```

`--notice-id` 缺省自动取 `payment_flow` 里最近一条非 NULL `notice_id`；`--ids` 缺省等于 `--notice-id`。脚本行为：
- 配置只经 `Settings(_env_file=<绝对路径>)`，`url` 只在局部变量；**不打印 DSN/字段**；报告里 `source.env` 只记 `<redacted>`。
- 事务 `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` + `SET TRANSACTION READ ONLY`，只发 SELECT，`finally` 里 `rollback()`。
- 交替 `original → candidate` × repeat，测两条链：`flows`（弹窗）与 `preview`（付款预览）。
- 同时跑一条**证伪**：`build_rows(links_of=…)` 不补 suppliers ⇒ `jc_supplier` 是否变值（`supplier_hazard`）。

输出键：`equal_flows`/`equal_preview`（json 文本逐字比较，含键序与行序）、`flows.original|candidate{rows,bytes,sql,rows_read,ms_median,ms_p95}`、`preview.{同}`、`revoked_in_original`、`supplier_hazard{rows,jc_supplier_diffs,hazard_confirmed}`、`error`（有则带 `traceback` 末 4 层）、`finished_at`。

已知局限（写死在脚本里的取舍）：候选 `flows` 用 `get_notices_by_ids([id])` 而非全量通知书字典；候选 `preview` **故意不传 `links_of`**（传了会触发 §3 的 `jc_supplier` 隐患），因此 preview 侧只量到 flows+traces 下推的真实量级；`_restricted_traces_of` 是逐对象 N 次查询（正是要量「N 次 vs 1 次全量」的取舍）。

## 7. 候选修改（仅列，未落代码）

- `backend/app/mod05_flow/repository.py`：新增按对象流水读，显式 `ORDER BY pay_date DESC, id DESC`（不复用 ASC 版翻转）；空 ids 不查库。
- `backend/app/mod05_flow/service.py` + `router.py`：`/api/m05/flows` 增可选 notice 维度；缺省路径输出不变；`build_flows` 同请求只调一次 `project_index`。
- `apps/frontend/src/flow-api.ts` + `notice-flows.tsx`：按对象请求；**必须同步改** `apps/frontend/tests/unit/flow-api.test.mjs:15`（现钉死 `/api/m05/flows?year_month=`）。
- `backend/app/mod03_notice/list_view.py`：`build_rows` 增 `suppliers=None` 注入口（否则传 `links_of` 会丢 `jc_supplier` 覆盖）；`notice_api_router.py:506-510` 传受限 `flows_of`/`links_of`/`traces_of`（需新增按 ids 的留痕索引）。

## 8. 现有具名检查（未运行）

`backend/tests/test_tail310_selected_pay.py`（禁全量出口、原序、空集不查库）、`test_notice_list_source.py`（include_archived）、`test_tail283_flow.py::test_装配不逐行查库`、`test_notice_association.py:26`、`apps/frontend/tests/unit/flow-api.test.mjs`。跑法：`backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/backend_verify.py --source-env <TEST_SOURCE_ENV> --test tests/<file> -- -q`。

## 9. 未验 / 失败 / 资源去向

- 未验：真实行数/bytes/SQL 差额、绘制耗时、`stat_trace` 按 ids 的 N 次查询 vs 1 次全量取舍 —— 全部待 §6 实测。
- 失败一次：`tools/artifact_lifecycle.py register` 两次 `{"error":"[Errno 13] Permission denied"}`（`.lock` 被并发持有，`msvcrt.LK_NBLCK` 的表现）；随后用同一固定 root 直调 `register()` 成功。
- 资源：已登记 `site-performance-tail471-20261103`（owner `dsh-tail471`，kind `evidence`，state active），files 目录 `.../groups/site-performance-tail471-20261103/files`，内含 `tail471_probe.py`（唯一文件，无 JSON、**未 lease**）。未触碰 `.scratch/site-performance/` 其他文件、原票、plan/status。
- 下一步：等主控分配 DB 窗口后跑 §6；期间无 live 资源占用。
