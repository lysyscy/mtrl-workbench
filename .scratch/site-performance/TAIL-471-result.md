# TAIL-471 结果：通知书与付款流水按对象核对提速

主控接收（2026-11-03 05:00）：核具名差异及同源证据，保默认完整读取与默认ASC消费者。补强新增范围参数：省略/空串仍沿原语义，显式非法/非正整数id报错，不静默回退全量；四项按对象范围隔离检查复核通过，受管运行`045821-303250-24944`已清理临时schema/目录。真实浏览器弹窗与付款前核对连通仍待验。

分支 `codex/site-performance-20261102`；开工基线 `8673a52c`，量测时 HEAD `28230893`。
写域：`notice-flows` 弹窗链 + `payment-preview` 按所选 ID 的读取链。**未改**原票/plan/status/Git，未领下票。

## 1. 采用与否 —— 采用（两处热点均成立，业务等值已证）

| 热点 | 原口径 | 现口径 | 结论 |
|---|---|---|---|
| H1 单通知书弹窗 | `GET /api/m05/flows?year_month=` 全量装配后前端 `filter` | `GET /api/m05/flows?notice_id=` 只取该通知书 | 采用 |
| H2 所选付款预览 | `build_rows` 的 flows/links/traces 仍全量 | 三者在 `notice_ids` 非空时同步收窄 | 采用 |
| H3 `build_flows` 同请求两次 `project_index` | `:155` + `project_options` 内 `:91` | `project_options(s, projects)` 复用 | 采用（随 H1 顺带） |
| H4 `flows_of_notices` 升序 | 默认 `pay_date, id` ASC | **默认不变**，新增 `descending=True` 给 UI | 不采用「改默认」（会动合同明细分笔） |
| H5 合同 `payment_contexts` 全量合同装配 | `mod11_jc/service.py:622` `list_contracts` 后按 id 挑 | 未改 | 留给路线 B（本票只读登记） |
| H6 `export_notices` 全量捞再按 id 挑 | `notice_api_router.py:561-601` | 未改 | 不属本票写域 |

## 2. 精确差异（8 文件 +119/−27，另新增 1 个测试文件 129 行）

- `apps/frontend/src/flow-api.ts:16-18`：`loadFlows(signal?, noticeId?)`；`noticeId === undefined` ⇒ 仍请求字面 `/api/m05/flows?year_month=`（**流水页 `flow.tsx:56` 一字未变**）。
- `apps/frontend/src/notice-flows.tsx:15`：`loadFlows(signal, notice.notice_id)`，删掉本地 `.filter(flow => flow.notice_id === ...)`。
- `backend/app/mod05_flow/router.py:184-196`：`api_flows` 增 `notice_id: str = Query("")`；`picked.isdigit() and int(picked) > 0` ⇒ `svc.build_notice_flows`；否则原 `load(...)` 不动 —— `year_month` 不传=当月 / `''`=全部 的区别保留。
- `backend/app/mod05_flow/service.py:88-95,191,196-207`：`project_options(s, projects=None)`；`build_notice_flows`（`notice_ids_rows` → `project_index` → `flows_of_notices(descending=True)` → `_flow_dict`）。
- `backend/app/mod05_flow/repository.py:41-56`：`flows_of_notices(..., *, descending=False)`；`:333` `notice_ids_rows`（经 `mod03_notice.service.get_notices_by_ids`，不跨包直查 repository）。
- `backend/app/mod03_notice/repository.py:115-152`：`stat_trace_index` 抽 `_trace_index`；新增 `stat_trace_index_of`（空 `[]` ⇒ `{}` 不查库，仍**一次**查询）。
- `backend/app/mod03_notice/list_view.py:188,193,195,246,258,294`：三个代理改为把 `notice_ids` 转发下去；`_flows_by_notice(None)` 仍 `list_flows` 全量；8 键投影与分组**一字未改**。
- `apps/frontend/tests/unit/flow-api.test.mjs`：URL 断言改为按 `noticeId` 分支；新增第 5 个 test。
- 新增 `backend/tests/test_tail471_object_scope.py`（4 test）：弹窗=全量筛出全等 / router 只在有效 id 下推 / 收窄后投影与供应商不退空 / 空集合不查库。

## 3. 真实指标（同快照 `REPEATABLE READ, READ ONLY` 交替量，`--repeat 5..7`，来源 `D:/dev/mtrl-workbench/.env`）

证据目录 `.../AgentArtifacts/projects/mtrl-workbench/groups/site-performance-tail471-20261103/files/`（owner `dsh-tail471`）。

**H1 弹窗（notice 639，4 条流水；另 notice 175 = 含已撤销）**
| 量 | 原（全量装配后再筛） | 现（按对象） |
|---|---|---|
| 弹窗实际收到的响应体 | **382,081 B**（全量 512 条） | **3,102 B**（4 条） |
| 筛完的行数 / 载荷 | 4 行 / 3,102 B | 4 行 / 3,102 B（同一份） |
| 装配 CPU 中位 | 179.400 ms（run2 183.318） | **7.499 ms**（run2 6.521） |
| SQL 次数 | 3 | 3 |
| 读取行数 | **1,772**（per_stmt 1240/20/512） | **25**（1/20/4） |
| 编码 bytes→JSON | 0.317 ms | 0.285 ms |

全量接口快照（`full:flows`，512 条流水）：382,081 B 响应体、装配 201.77 ms、编码 20.711 ms、读取 1,792 行 —— 这是**在页面上打开任一通知书弹窗时今天真实拉取的量**。`flow.tsx` 流水页仍走这条，未变。
notice 175（含 1 条已撤销）：装配 189.005 → **6.798 ms**，读取 1,772 → **23** 行；撤销流水照常出行。

**H2 所选付款预览（`payment-preview?ids=`，1 张 → 5 张选中）**
| 选中 | 原装配 | 现装配 | 原读取行 | 现读取行 | 行数/bytes |
|---|---|---|---|---|---|
| 1 张（639） | 20.459 ms（run2 24.149） | **9.950 ms**（run2 9.478） | 693 | **27**（run2 27） | 1 / 1,275 B 两侧相同 |
| 5 张（含已撤销 175 + 3 张有合同关联） | 23.827 ms | **11.364 ms** | **700**（512/4/151/8/5/20） | **41**（8/4/4/0/5/20） | 5 / 6,387 B 两侧相同 |

## 4. 同源业务等值（判据）

- **载荷逐字相等**：`payload_sha256` 原/现两侧同值 —— flows `45470c91…`（notice 639）、preview `f94da559…`；run4（撤销+关联）`old:preview == new:preview`。四份 run 全部 `equal_flows=true`、`equal_preview=true`。
- **行序**：显式 `pay_date DESC, id DESC`（= `list_flows` 原序）；`test_tail471_object_scope` 钉住同日「已撤销在前」这条。
- **已撤销**：175 的 revoked 流水在弹窗与预览里都照常出现，`status/status_label/revoke_reason` 一致。
- **失联流水**（`notice_id IS NULL`）：真实库 **0 条**（已查），不属任何通知书的弹窗；`amount_approved=null` 与 `0.00` 的区分由 `_flow_dict` 原逻辑保留。
- **供应商不退空**：真实行核对 `has_link` / `jc_supplier` 非空 —— 639 `浙江万马股份有限公司`、129/130 `太康县许楼建材有限公司`、270 `河南双贤科技有限公司`；270 `has_any_flow=False` 且 `amount_paid=0.00`（零值不被回退）。这正是 `list_view.py:189-193` 「只传 links_of 不补 suppliers 会静默变值」那条反证 —— 实现里**两者一起收窄**。
- **空选 / 全量语义**：`notice_ids=[]` ⇒ 空（`empty_selection.rows=0`、`build_rows(notice_ids=[])==[]`，且不查库）；不存在的正id ⇒ `missing_notice.rows=0`；省略/空 `notice_id` 保原全量/年月口径；显式非法或非正整数id由主控接收时改为报错，范围检查已更新通过。
- **默认完整接口**：`/api/m05/flows` 不传 `notice_id` 时行为一字未变（`flow.tsx` 仍全量）；未改 `flows_of_notices` 默认 ASC。
- **付款前核对 / 未知读回 / 账号隔离**：未触碰 —— `notice-payment.tsx:98` 仍 `readPaymentContext` 权威重读、`notices.tsx:102-103` 仍 `cancelQueries+fetchQuery(staleTime:0)`、`main.tsx:73` 每账号新 `QueryClient`。弹窗新 key `['notice-flows', id]` 不进入任何付款判断路径，**没有引入可复用的陈旧缓存**。
- **合同合法全集**：`contract-subtables` 仍读全量 notice-list（只读，未改）；`flows_of_notices` 默认升序未动，合同明细分笔不受影响。

## 5. 检查（原码 + 真实退出码）

后端（唯一入口，测试库 `mtrl_workbench_test`，一次性 schema，结束 `cleanup_completed=true`、`error=null`）：
```
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/backend_verify.py \
  --source-env D:/dev/mtrl-workbench/.env \
  --test tests/test_tail471_object_scope.py -- -q                       # returncode 0，组 045211-892578-22088
... --test tests/test_acc_flow_list.py --test tests/test_tail283_flow.py --test tests/test_acc_flow_led.py \
    --test tests/test_notice_list.py --test tests/test_notice_association.py --test tests/test_notice_list_source.py \
    --test tests/test_tail310_selected_pay.py --test tests/test_jc_payment_context.py \
    --test tests/test_wired_m03_pay.py --test tests/test_tail471_object_scope.py --test tests/test_layering.py -- -q
                                                                          # returncode 0，组 045229-834731-25240
... --test tests/test_acc_jc_pay_link.py --test tests/test_request_local_reads.py \
    --test tests/test_notice_actions.py --test tests/test_ledger_export.py -- -q   # returncode 0，组 044410-021391-20428
... --test tests/test_layering.py --test tests/test_acc_prj_arch.py -- -q          # returncode 0，组 044531-344352-28092
```
前端：
```
cd apps/frontend && node --import=tsx --test tests/unit/flow-api.test.mjs   # 5 pass / 0 fail，EXIT=0
cd apps/frontend && npx tsc --noEmit                                        # EXIT=0
```
既有检查的覆盖点：`test_tail310_selected_pay.py` 的 forbidden 出口（付款不得走 `build_rows`/`list_flows`）仍绿；`test_tail283_flow::test_装配不逐行查库`（≤6 次、不随行数增长）仍绿；`test_acc_jc_pay_link` / `test_notice_association` 钉住关联唯一性与供应商权威值。

## 6. 未验 / 已知无关失败 / 资源去向

- **未跑** HTTP 层与浏览器：没有起 preview、没有点真实弹窗，故**渲染/INP/首屏**未测；本轮指标是服务端装配 CPU、读取行数、响应 bytes，**不代表全页提升**。
- **未跑** 既有无关失败项 `backend/tests/test_tail274_ledger.py::test_history_manual_auto_and_export_are_independent`：断言月份列 `'2025-11'`，实现（`backend/app/report_export/ledger_export.py:70-71`，commit `bfec6413`）产 `'2025-11及之前'`，`tests/test_ledger_export.py:49` 支持实现口径 ⇒ **测试旧于实现，与本票改动无关**（`git diff HEAD -- backend/app/report_export/ledger_export.py` 为空）。
- **未改**：`mod11_jc/service.py:622` 合同全量装配、`export_notices` 全量捞、`payment_stat_views` 等其它 `list_flows` 消费者。
- **资源**：无 live 资源占用。只读引擎全部 `connect_args={"connect_timeout":5,"options":"-c default_transaction_read_only=on -c statement_timeout=30000"}` + `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` + `SET TRANSACTION READ ONLY`，finally `rollback/close/dispose`；异常经 `_redact()` 脱敏，未打印 DSN/凭据。
- **生命周期**：证据沿用 `site-performance-tail471-20261103`（owner `dsh-tail471`，未重登记）；`register` 曾因 `.lock` 并发两次 `Permission denied`（已如实记录），后续统一走官方 `lease --` 入口。组状态留给主控判 close/hold。
- **探针**：`files/tail471_probe.py`（近似算法对照，run1–run4）、`files/tail471_verify.py`（**产品代码路径**对照，run1–run5）；JSON 每次独立保存，未覆写前次成功证据。
- 组内残留 `files/__pycache__/`（跑探针的运行产物）；主控若要 `close`（会逐个算 sha256），可先清该目录。
- 待主控：是否把本票 8 文件 + 新测试并入提交（本会话不 `git add/commit/push`）。
