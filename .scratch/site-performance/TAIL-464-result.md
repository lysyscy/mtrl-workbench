# TAIL-464 结果：过程资料读取（矩阵装配 + 机械屏幕读模型）

授权来源：主控消息 2026-11-02 22:45（本轮唯一授权，含只读 DB 探针窗口、产物组、写域与 H3 裁定）。
基线：分支 `codex/site-performance-20261102`，HEAD `daf8a7fce9aaf932a7d971daa7db178ae7becaa4`（`git diff --stat` 显示改动仅本票文件；报告为新增）。
运行：Python `3.15.1`，`backend/.venv`，Node `24.22.1` / pnpm `12.15.0`；真实只读库 `mtrl_workbench`、测试库 `mtrl_workbench_test`（后端 `tools/dev/backend_verify.py` 独占临时 schema）。

## 1. 真实输入规模（只读快照，非合成）

`mech_rows=205`、`projects=16`、`months=30`、`detail_cells=24`、`basis_rows=578`、`history_entries=0`（`tail464/probe_readonly.json`）。
`/api/m06/mech` 单次载荷 `3,264,194 B`，与 plan.md 记录的浏览器解码字节逐字一致 ⇒ 真实分布可复现。

## 2. 改动文件（产品 3 + 前端 1 + 夹具 5）

| 文件 | 改动 |
|---|---|
| `backend/app/mod06_proc/repository.py:39` | `mech_effective(..., *, compact=False, with_source=True)`：新增 `with_source` 关键字；`compact` 分支不变，`with_source=False` 时跳过 **全仓无人读** 的 `result['source']=deepcopy(...)` |
| `backend/app/mod06_proc/repository.py:92` | `load_mech(s, *, with_sources=True)`：默认完整契约不变；`with_sources=False` 只出 `ym/warehouse/project_id` + 6 原值；完整分支改调 `with_source=False`（它本来就丢弃 `state['source']`） |
| `backend/app/mod06_proc/repository.py:112` | 新增 `load_mech_screen(s)`：逐行 `mech_effective(compact=True)` —— **投影发生在复制之前**，签名仍按完整原来源 |
| `backend/app/mod06_proc/service.py:124` | `_load_report_data` 改用 `load_mech(s, with_sources=False)`：矩阵只取 6 原值（`domain.mech_by_month` 从不读 sources/签名） |
| `backend/app/mod06_proc/router.py:126` | `/api/m06/mech` 装配抽成 `_mech_payload(...)`（`:156`），**原端点行为与完整来源一字未改**；新增 `GET /api/m06/mech-screen`（H3 裁定：新开屏幕出口，不改瘦原端点） |
| `apps/frontend/src/process-api.ts:79` | `getProcess` 改读 `/api/m06/mech-screen`；类型/校验不变（本来就只声明 `mode`） |

夹具（按真实消费者约束调整，未为保猴补丁形状牺牲接口）：
`backend/tests/test_proc_report_data.py:196`、`test_process_export.py:123`、`test_process_material_manual.py:22,151` 的桩改为接受 `**kw`（新关键字是真实调用方参数，不是形状）；`apps/frontend/tests/test_process.py:57` 的"保存后只重读"集合改为 `{'m06/matrix','m06/mech-screen','history/status'}`。
新增判据：`backend/tests/test_page_m06.py::test_屏幕读模型与完整机械接口逐值同签名_只少来源明细`（只钉业务等值，不钉形状/耗时）。

## 3. 真实前后指标（CPU / SQL / bytes 分开；同快照 REPEATABLE READ + READ ONLY）

**机械读模型（`tail464/probe_after.json`，5 次中位）**

| 指标 | 原 `/api/m06/mech` | 屏幕 `/api/m06/mech-screen` |
|---|---|---|
| 载荷 bytes | 3,264,194 | **93,288**（34.99×，省 3,170,906） |
| `sources` 子树 bytes | 3,207,070（占 98.25%） | 36,164 |
| 进程内端点（装配+SQL，5 次中位） | 422.298 ms | 375.032 ms |
| JSON 编码中位（`probe_cpu.json`，9 轮，纯 CPU） | 300.443 ms | **12.963 ms** |
| SQL | 30 条 / 143.149 ms | 30 条 / 204.837 ms（同语句数；ms 差为并发噪声，**不归因改动**） |

业务等值（真实同源逐值）：`mech`/`count`/`columns`/`sections`/`effective_signatures`/`detail_signatures`/`effective_values`/`modes`/`month_sets` **全为 true**，`basis_leaked=false`，`pairs=205`。

**矩阵装配（`probe_after.json`）**

| 指标 | legacy（重做完整来源） | current（`with_sources=False`） |
|---|---|---|
| 端到端中位 | 664.707 ms | 587.833 ms（**波动大，不作结论**） |
| 载荷 bytes | 465,043 | 465,043 |
| SQL | 35 条 / 212.733 ms | 35 条 / 303.223 ms（同语句数） |
| `equal` | — | **true**（16 项目 16 矩阵逐值） |

CPU 归因（`probe_cpu.json`，一次取数后纯内存 9 轮，**SQL 不参与**）：`load_mech` 完整 **155.474 ms** → `with_sources=False` **0.559 ms**；`load_mech_screen` **61.153 ms**。这就是矩阵链路每次白做的来源构造成本（≈155 ms 纯 CPU），比端到端中位数差（76.9 ms）更可信。

**分层拆解（同样 205 行真实对象）**：`mech_effective` 完整 208.910 ms / 去丢弃副本 152.583 ms / 紧凑 **55.605 ms**；三种形态 `signature` 逐字相等、`values` 相等。wire 6,439,499 / 3,258,563 / 87,657 B。
结论：钱的分布 = ①屏幕不该拿 `basis`+`history`（载荷 98%）②`load_mech` 在矩阵链路白做整包来源 ③没人读的整包副本。

## 4. 实际命令与退出码

| # | 命令（省略已导出的 `PYTHONPATH` / `MTRL_*`） | 退出码 |
|---|---|---|
| 1 | `backend/.venv/Scripts/python.exe -B -X utf8 <files>/tail464/probe_readonly.py --out …/probe_readonly.json` | 0 |
| 2 | `… probe_after.py --out …/probe_after.json` | 0 |
| 3 | `… probe_cpu.py --out …/probe_cpu.json` | 0（首跑 1：探针自身 `'Rows' object has no attribute 'scalars'`，修探针后通过） |
| 4 | `python tools/dev/backend_verify.py --source-env D:/dev/mtrl-workbench/.env --test tests/test_page_m06.py::… --test tests/test_mechanical_source_protection.py::… -- -q` | 0（4 passed） |
| 5 | 同 14 个相关模块（page_m06 二节点 / source_protection / mechanical_workbench / mechanical_api / autosave / confirmation / proc_report_data / process_export / material_manual / layering / wired_m06 / split_cutoffs / empty_month_remove） | **0（158 passed）**，日志 `tail464/verify_final.log` |
| 6 | `cd apps/frontend && corepack pnpm typecheck` | 0 |
| 7 | `cd apps/frontend && corepack pnpm test:unit` | 0（29 passed） |

过程中两次**工具用法**失败（非产品问题）：`--test backend/tests/...` 带前缀 ⇒ `FileNotFoundError`（工具以 `backend` 为根）；`lease` 包装未带 `MTRL_EFFORT/RUN_ID/LIFECYCLE_OUTPUT` ⇒ `PermissionError`（已改为导出三个变量后直跑，输出仍落登记组）。

## 5. 最小具名检查（选择的理由）

- `test_page_m06.py::test_接口按分界月给机械值_历史段读快照` —— 历史段读快照 vs 正式段读手录的分流判据。
- `test_page_m06.py::test_屏幕读模型与完整机械接口逐值同签名_只少来源明细`（新增）—— 只验"同值/同签名/只少 basis"这个覆盖缺口。
- `test_mechanical_source_protection.py` 整模块 —— 完整来源契约、明细确认、`0` 与 `null` 三分、`source` 键去留。
- `test_proc_report_data.py` —— 矩阵"各来源各取 1 次 + 每仓 build_matrix 两次"的取数与等值判据（`with_sources=False` 的直接守卫）。
- `test_layering.py` —— 包间出口必须真转发（`load_mech` 仍每次经 `from app.mod06_proc import repository as R`）。
- `test_wired_m06.py` —— 原 `/api/m06/mech` 的文本契约（`"mech": out` 仍在 ROUTER 内）。

## 6. 保持不变的契约

- `mech_effective()` 默认 `compact=False, with_source=True` ⇒ `workbench.state()` 仍带 `'source'` 键（`test_mechanical_api.py:115` 判据不破）。
- `load_mech()` 默认完整 ⇒ `mod05_flow` / `mod07_setl` / `mechanical_export` 等旧消费者行为不变。
- `/api/m06/mech` 装配体原样（`_mech_payload` 只是抽出，字符串与键序未改）。
- `page_state()` 仍 compact；`SourceWithoutCopies` 判据继续防止页面复制来源。

## 7. 未验 / 资源状态

- **未验（缺授权/资源）**：真实浏览器与真实副本 Playwright（`apps/frontend/tests/test_process.py` 全文件）——本轮资源窗口只含只读 DB 与 backend_verify；真实 HTTP 端到端（含压缩、TTFB、浏览器 JSON.parse）——未起服务；真实保存→读回闭环在浏览器侧的观感；`frontend_measure.py` 的 `--stage all` 采集。
- **未纳入**：矩阵与机械两请求**合并**（真实测量显示矩阵装配只剩 ~3.6 ms/16 项目 CPU，收益不在合并，而在载荷与白做构造）；历史/缓存基础设施（非本票写域）。
- **前置失败（与本改动无关，未修）**：`tests/test_acc_init.py::test_过程资料机械手录入口保留` 与 `tests/test_page_m06.py::test_机械手录落库后表内取到_且重抓不覆盖` 失败于 `FakeSession` 无 `get_bind`（`repository.py:63 lock_mech_month`）；已核 HEAD 版 `tests/m08_helpers.py` 同样无 `get_bind` ⇒ 前置缺口。
- **资源状态**：只读 DB 窗口已用尽本轮；产物组 `site-performance-first-wave-20261102` **未 close**（留给后续票）；未动原票/plan/status/Git 索引，未提交、未派子代理、未领取下一票。

主控接收（2026-11-03）：保留默认完整`source`，仅load_mech跳过丢弃副本；补强含detail basis的投影判据并保持空月份原规范化。整合后过程来源、请求事实、集采、欠款导出与分层相关隔离检查通过（受管运行`000435-920925-39732`），原既有红与浏览器未验保持。
