# TAIL-470 结果：月度会大表读取与切月（机械取数口径 / 手填历史请求内复用）

授权来源：主控 2026-11-03 派单（含唯一只读 DB 探针 + backend_verify 时段、写域、禁项）。
基线：分支 `codex/site-performance-20261102`，累计 `8673a52c`（未推送）；本票改动全在工作树，未 add/commit。
运行：`backend/.venv` Python 3.15.1；库 `mtrl_workbench_test`（backend_verify 独占临时 schema）；只读探针固定 `default_transaction_read_only=on` + `statement_timeout=30000` + `connect_timeout=5`，事务 `REPEATABLE READ / READ ONLY`，结束 rollback/close/dispose。

## 1. 真实输入规模（只读快照，非合成）

固定输入：`default_month=2026-10`，对照月 `2026-09`（库内**唯一**有手填历史的月）。
`analysis_big_manual` **9 行 / 1 个月（2026-09）/ 9 仓 / 54 格槽 / 11 个非 NULL 值**，序列化后 **1,163 B**；`analysis_big_month_project` 10 行、`analysis_big_project` 10 行、`project` 20 行 ⇒ 大表实出 **9 个业务行**。
`proc_mech_manual` **205 行 / 30 个月 / 16 仓**；`inv_detail` **18,287 行 / 25 列**。

## 2. 量测结论：热点是机械旁路表的**取数口径**，不是传输也不是装配

2026-10 分段（`measure_pre_v2.json`，median of 3，ms）：`_amounts` 整包 **529.853**，其中 `_mech_amounts` **376.994**、`load_amounts` 109.868、`MAIN_MATERIAL_PORT` 25.006、`load_balances` 1.005；而 `selection_data` 2.750、`assemble_rows` 0.213、`totals_row` 0.138、`load_manual` 1.169。
⇒ 装配/合计/手填读取都在毫秒级以下；整条路由 483.025 ms 中约 78% 在机械取数。

机械成本归因（`measure_mech_attribution.json` / `measure_mech_column_weight.json`）：
- `load_mech(with_sources=False)` 141.975 ms，而只取 8 列 tuple 的窄投影 **2.242 ms**（**省 139.733 ms，98.4%**）⇒ 成本几乎全是 ORM 实体构造。
- `source_batches` 列 JSON 总计 **4,377,620 B**（单行最大 **1,207,220 B**），`warehouse_name` 仅 5,099 B；`entity_all_columns` 90.442 vs `narrow_10_columns` 2.924 vs `source_batches_only` 118.382 ⇒ 该超大 JSON 列的反序列化是主因。
- 默认出口 `with_sources=True` 每行再算 `mech_effective` 的整包来源深拷贝 + sha256 签名，**大表只用 warehouse/ym/mech_0..5，这两项一律被丢弃**。响应侧 `_amounts` 只取 1,635 B。

## 3. 改动（后端 2 文件 + 新增检查 1；前端未改）

| 文件 | 改动 |
|---|---|
| `backend/app/mod07_setl/big_service.py:70` | `_mech_amounts` 改 `P6S.load_mech(s, with_sources=False)`；docstring 记录「本表只要 warehouse/ym/mech_0..5，默认出口的 sources＋effective_signature 一律被丢弃却要按行现算」。同一写法已在 `mod06_proc.service._load_report_data` / `mod05_flow.service:315` 使用，非新机制 |
| `backend/app/mod07_setl/big_service.py:161` | `build_big_data` 内 `manual = R.load_manual(s)` 只读一次，供 `B.assemble_rows(...)` 与出参共用，结果新增 `"manual"` 键 |
| `backend/app/mod07_setl/api.py:226` | `api_big` 取 `data["manual"]`（保留 `load_manual(s)` 回退给打桩/旧调用）⇒ 每请求全表手填读 **2 次 → 1 次**；出参 11 个字段一项未减 |
| `backend/tests/test_tail470_big_reads.py`（新增，3 条） | ①`_mech_amounts` 必须且只以 `with_sources=False` 调用，取值与完整出口独立复算一致；②`build_big_data` 带 `manual` 且等于 `R.load_manual(s)`；③一次读取里 `load_manual` 恰被调 1 次、`manual` 与库内同值、字段集合仍 11 项、行序 = `selected`、`auto.hw_cum` 仍出字符串 `"600.00"` |

前端 `apps/frontend/src/{big.tsx,big-api.ts}` **未改动**（理由见 §6）。未改月报/提取语义、未动共享 Grid 自然高度与保活机制、未改 `load_mech` 所在的 `mod06_proc`（不在本票写域）。

## 4. 真实前后指标（同快照 A/B；CPU / SQL / bytes 分开）

**同快照交替 9 轮**（`measure_ab.json`；把改动前实现原样复原为局部函数，避免跨进程抖动）：

| 指标 | 原 | 现 | 差 |
|---|---|---|---|
| 2026-10 `mech` 中位 | 298.354 | 91.865 | **−206.489 ms** |
| 2026-10 整条路由 中位 | 422.080 | **222.140** | −199.940 ms（**−47.4%**） |
| 2026-09 整条路由 中位 | 430.503 | **237.429** | −193.074 ms（**−44.8%**） |
| 响应逐字节相等 | — | `true`（两月） | 业务等值 |

**端到端请求**（`measure_pre_v2.json` → `measure_post_final.json`，同脚本同输入）：2026-10 483.025 → **321.991**（SQL **30 → 27** 条，8,515 B **逐字节相等**）；2026-09 558.555 → **210.867**（27 条，8,482 B 相等）。`_amounts` 529.853 → 197.444；`mech_amounts` 376.994 → 107.629；`stage_sql` 112 条/563.065 ms → 107 条/470.830 ms。

**手填复用**（`measure_request_sql.json`）：`api_big` 相对 `build_big_data` 的额外全表读 **1 → 0**，每请求少 1 条 `analysis_big_manual` 查询（三样本共 3 条），`load_manual` 单次 1.169 → 0.960 ms、连取两次 3.209 → 1.726 ms。

**成品等值**（`export_parity.json`，`big_export.body_spec` 纯函数，未落盘 xlsx、未跑 POST）：两月 `spec_equal / tail_equal / day_rows_equal / totals_equal / carry_n_equal` 全 `true`（9 行、111 格）。

**业务等值复核**（探针内独立复算，两月均 `independent_ok=true`）：手填值逐格 vs 裸 SQL、带入值/来源月 vs 独立实现、行序与 seq 唯一性、合计逐列 `core.money.sum_money` 复算 —— `manual_vs_sql / carry_vs_sql / rows_shape / totals` 四项 mismatch 均为 `[]`。

## 5. 实际命令与退出码（产物组 `site-performance-tail470-20261103`）

| # | 命令（省略公共参数与产物路径） | 退出码 |
|---|---|---|
| 1 | `python -B -X utf8 <files>/probe_tail470.py --phase pre` | 0（首跑 `independent_ok=false` 系探针自身判据写错，修正后 0；首跑产物另存 `*_attempt1.json` 不覆写） |
| 2 | `… probe_tail470_mech.py` / `probe_tail470_mech2.py` / `probe_tail470_mech3.py` | 0 / 0 / 0 |
| 3 | `… probe_tail470_ab.py` / `probe_tail470_reqsql.py` / `probe_tail470_export.py` | 0 / 0 / 0 |
| 4 | `… probe_tail470.py --phase post`（两次：`measure_post_mech.json`、`measure_post_final.json`） | 0 / 0，两次均 `byte_equal_to_baseline=true` |
| 5 | `backend_verify … --test tests/test_tail470_big_reads.py -- -q` | **1 首次**（断言把 `"600.00"` 写成 `Decimal`）→ 修后 **0** |
| 6 | 同上 6 模块：`test_tail470_big_reads` / `test_acc_rpt_big` / `test_tail311_bulk_materials` / `test_big_export` / `test_report_query` / `test_layering` | 全 **0** |
| 7 | `<files>/mutate_tail470.py --mutant mech|manual|api --run` | 三者均 **exit 1（检查判红）且 `restored_ok=true`**（sha256 复原核对见 `mutant_*.json`） |

变异自检第一轮 `api` 变异**未被捕获**（exit 0）：新检查只打了 `S.R.load_manual`，而 `api.py` 用 `from ... import load_manual` 的独立绑定；补 `monkeypatch.setattr(api, "load_manual", counted)` 后三处变异全部判红。

## 6. 采用 / 保持结论

- **采用**：`_mech_amounts` 走 `with_sources=False`；`build_big_data` 手填历史一次读取并复用。两处都在本票写域，且响应逐字节不变。
- **保持（不加 `api_big_screen`）**：全量 `manual` 实测仅 **1,163 B / 请求**（屏幕投影省 1,173 B ≈ 响应 13.8%，`other_fields_byte_identical=true`、`screen_rows_equal=true`），编码 <0.2 ms。真实规模下**无净收益**，按票内「无净收益给保持证据」处理；`/api/m07/big` 11 字段完整契约原样保留，React 不消费顶层 `manual` 这一点仍由 `big-api.ts` 类型与校验双证。
- **保持（前端未改）**：库内实出 **9 行**，`columns` 重建的 `measureText` 为 9 行 × 约 20 列、`autoHeight` 自然高度只管 9 行 ⇒ 真实规模下无法证出可归因的绘制成本；且 `domLayout:'autoHeight'` 的自然高度与按月保活属**共享 Grid 机制**（本票只读，需变更须主控具名 patch）。切月回访时缓存数据即时渲染、后台按 `staleTime:0` 复验（复验期控件禁用，是既有的一致性保护），不改成不失效缓存。
- **已量化、未做、交主控**：`proc_mech_manual` 剩余 ~90–140 ms 需要窄投影出口（只取 8 列 tuple 比实体构造快 **139.733 ms / 98.4%**），但该出口在 `mod06_proc`（不在本票写域）⇒ 跨域改动不擅自做；`load_amounts` 的 109.868 ms（18,287 行 `inv_detail`）同属 mod08 取数口径。

主控接收（04:25）：采用已实测的共享金额窄投影，在原`mod06_proc.repository.load_mech(with_sources=False)`只SELECT身份/月份及六值，默认完整出口不变。同一强制只读快照7对、205行逐字节相等，中位ORM原值读取88.031→3.752ms（仅此阶段，非整页）；证据归first-wave组`controller/value-projection.json`。独立测试保null/0、身份与完整来源，连同过程/欠款/大表相关隔离检查通过，受管运行`042326-438996-30748`已清理schema/临时目录。

## 7. 未验 / 既有失败 / 资源状态

- **未验**：真实浏览器与真实副本（首帧几何、`autoHeight` 长表自然滚动、切月后草稿/列宽/滚动保持、`__bigFrames`）——本轮窗口禁 HTTP/浏览器/preview，只能记未验；真实 HTTP 端到端（TTFB/gzip/JSON.parse）同样未验。前端 Node 侧 CPU/工具等待**不作** INP 或全页提升。
- **两个既有失败（与本票无关，已核基线相同）**：`tests/test_approved_report_exports.py::test_monthly_formulas_have_caches_and_preview_has_results`（`annual.max_column` 11≠10，`report_export/mechanical_export.py` 自基线未改）；`tests/test_acc_init.py::test_过程资料机械手录入口保留`（`FakeSession` 无 `get_bind`，栈在 `mod06_proc/repository.py:63 lock_mech_month`，`mod06_proc/` 与 `test_acc_init.py` 自基线未改）。
- **未纳入**：`/api/m07/big` 顶层 `manual` 的仓内代码消费者仍只有前端类型未声明；若未来要删需另开票改完整出口。
- **资源状态**：只读 DB 探针窗口已用尽（无后台任务/无遗留连接）；产物组 `site-performance-tail470-20261103` 未 close（留主控统一判 close/hold），未给 `site-performance-first-wave-*` 重登记或改 owner；未改原票/plan/status/高水位，未 git add/commit/push/switch/reset/clean/stash，未派子代理，未领下一票。
