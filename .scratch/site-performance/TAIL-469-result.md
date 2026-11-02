# TAIL-469 结果：收发结存月报 + 年度提取（按需装载 / 请求内事实复用 / 屏幕读模型）

授权来源：主控 2026-11-03 派单（m00001，含唯一只读 DB 探针 + backend_verify 时段、写域、禁项）。
基线：分支 `codex/site-performance-20261102`，HEAD `3c5712ed`（未推送）；本票改动全在工作树，未 add/commit。
运行：`backend/.venv` Python 3.15.1；Node/pnpm 经 DSH 运行时；库 `mtrl_workbench_test`（backend_verify 独占临时 schema）。

## 1. 真实输入规模（只读快照，非合成）

固定输入：月报 `ym=2026-09`；提取 `year=2026`、`status=在建`；库 `mtrl_workbench_test`。
`setl_detail=1839` 行 / `2` 个月（当月 `879` 行）/ 13 仓；`inv_detail` 入库 `8904` 行 / 10 个月；`project=20` 行。
输出：月报 `9` 仓行；年度网格 焊材 `10` 行、气体 `9` 行；`annual_totals` 年份 2025/2026。
真值（`probe-tail469-round1.json` `settlement_payload_vs_sql_mismatch=[]`、`extract_invariant_mismatch=[]`）：
`total == balance + Σcells`、`prior == 年首前累计`、月报四金额合计 == 独立 SQL 复算。

## 2. 改动文件（后端 4 + 前端 1 + 新增检查 1）

| 文件 | 改动 |
|---|---|
| `backend/app/mod07_setl/repository.py:56` | 新增 `load_month_rows(s, ym)`：与 `load_rows` 同一 `to_row` 投影，只把月筛交给已存在的 `SetlDetail.ym` 索引；`load_rows` 原样保留（`big_service` 仍用，470 范围） |
| `backend/app/mod07_setl/service.py:20,46` | 新增独立一行 import（:19 原 import 行一字未动 = 变异锚点 `_mut_m07bal.py:33`）；`build_page_data` 改 `D.warehouse_rows(load_month_rows(s, ym), ym)` —— **`rows_of` 二次按月过滤保留**，表体/合计唯一出口不变 |
| `backend/app/mod07_setl/service.py:165` | `annual_grids(...)` 增 `balances=` / `context=` 关键字（**默认仍自取**，同一请求内复用；⛔ 无跨请求缓存——结余是手录历史必须现读）；`build_extract_data` / `build_extract_export` 传入已取事实 |
| `backend/app/mod07_setl/extract.py:105` | `extract_amounts` 加**调用内**按物料名记忆化 `hits`：`match_kind` 是纯函数（只依赖 名称×类别×规则），只省重复判定；规则仍来自本次入参、金额口径 `sum_money` 一字未动 |
| `backend/app/mod07_setl/api.py:65,127,150` | 抽 `_annual_out` / `_balances_out`（完整出口与读模型共用，保证同源同值）；`api_extract` 复用已取 `balances`，**完整契约一项未删**；新增 `GET /api/m07/extract-screen` 只发 `annual` + `balances` |
| `apps/frontend/src/settlement-api.ts:38` | `getExtract` 改读 `/api/m07/extract-screen`；类型/校验不变（`readExtract` 本就只声明并校验 `annual`/`balances`） |
| `backend/tests/test_tail469_screen_reads.py`（新增 5 判据） | 月报按月装载 == 全量装载（四个月 + 独立复算）；装载语句确实带 `setl_detail.ym =`；屏幕读模型与完整接口逐值同签名只少三项；提取页网格与导出网格仍逐值一致且结余为手录值；记忆化与独立复算一致、近名「氧气瓶」仍不进气体、换规则立刻生效 |

## 3. 真实前后指标（CPU / SQL / bytes 分开；同快照 REPEATABLE READ + READ ONLY）

**月报（`probe-tail469-round4.json`，10 轮交替，ms）**

| 指标 | 原（全表 `load_rows`） | 现（`load_month_rows`） |
|---|---|---|
| 端点中位 / 最小 / p90 | 82.035 / 72.488 / 93.148 | **37.973 / 23.272 / 46.742**（中位 −53.7%） |
| `load_rows` 单点中位（round3） | 139.351（SQL 8.795，1839 行） | **49.522**（SQL 2.617，879 行） |
| SQL 条数 / ms | 1 / 4.412 | 1 / 2.828 |
| 响应 bytes | 1,497 | 1,497（**逐字节相等**） |

差的来源是 ORM 行构造（1839→879 行），不是 SQL。当月路径分段（`probe-tail469-round7.json`，10 轮）：
`load_month_rows` **44.114 ms**（min 25.3 / p90 64.1）+ `domain.warehouse_rows` **3.833 ms** = `build_page_data` 整包 **51.230 ms**，其余装配（summary/manifest/zip_name/空态/计数）**3.284 ms（6.4%）** ⇒ API 丢弃的那几项成本可忽略，不为此改契约。

**年度提取（同文件，10 轮交替，ms）**

| 指标 | 改造前口径（还原） | 现（复用 + 记忆化） |
|---|---|---|
| `api_extract` 中位 / 最小 / p90 | 124.637 / 105.719 / 135.306 | **106.377 / 85.16 / 117.465**（中位 −14.6%） |
| `api_extract_screen` 中位 / 最小 / p90 | — | 102.647 / 67.472 / 142.717 |
| SQL 条数 / ms | 3 / 16.578 | 3 / 17.084（同语句数，差为噪声，不归因） |
| 响应 bytes（完整出口） | 9,052 | 9,052（**逐字节相等**） |
| 响应 bytes（屏幕读模型） | — | **4,655**（省 4,398 B；`amounts` 2,654 + `annual_totals` 1,687 + `kinds` 19 不发给屏幕） |

端点内部耗时分解（round3，`load_amounts` 是主成本）：`load_amounts` 166.035｜`load_balances` 2.283｜`_project_context` 2.006｜`annual_grids` 4.012｜`extract_year_totals` 0.477｜整包编码 1.013 ms。
`load_amounts` 再拆（round2）:抓取 `load_original_inbound` 74.473（8904 行）/ 纯规则匹配 33.831 ms。
规则记忆化单独对照（round3，10 轮含取数）：plain 171.871 → memo 139.503 ms（中位 −32.4 ms，≈19%）。

**重复事实读取（`probe-tail469-round5/6.json`，同一只读快照调用计数）**

| 每请求调用次数 | 原 | 现 |
|---|---|---|
| `match_kind`（提取端点） | 17,808 | **4,132**（−76.8%，同名物料只判一次） |
| `load_balances`（`api_extract`） | 2 | **1** |
| `_project_context`（`build_extract_data`） | 2 | **1** |
| `load_balances` / `_project_context`（`build_extract_export`） | 2 / 2 | **1 / 1** |

业务等值（round4，全部 `true`）：`settlement_new_vs_old`、`extract_new_vs_old_full`、`screen_annual_vs_full`、`screen_balances_vs_full`；`screen_keys=["annual","balances"]`、`full_keys=["amounts","annual","annual_totals","balances","kinds"]`。
`extract_old` / `settlement_old` 是**按改前口径还原**的对照（非旧二进制）。交叉校验：改前实际端点（round1–3，改动落盘前跑）`api_extract` 124.87 / `api_settlement` 75.482，与还原对照 124.637 / 82.035 同量级 ⇒ 还原可信。
月度/年度快照与原同源独立业务预期一致：`probe-tail469-round1.json` 两项 mismatch 均为 `[]`。

## 4. 实际命令与退出码

| # | 命令（省略已导出的写域/组参数；产物组 `site-performance-tail469-20261103`） | 退出码 |
|---|---|---|
| 1 | `backend/.venv/Scripts/python.exe -B -X utf8 <files>/probe_tail469.py --out …/probe-tail469-round1.json` | 0 |
| 2 | `… probe_tail469_round2.py --out …/round2.json` | 0 |
| 3 | `… probe_tail469_round3.py --out …/round3.json` | 0 |
| 4 | `… probe_tail469_round4.py --out …/round4.json`（改后，10 轮交替） | 0 |
| 5 | `… probe_tail469_round5.py --out …/round5.json`（改后调用计数；首跑 1 = 探针对 `D.WAREHOUSE_KEY` 未导入，修探针后 0） | 0 |
| 6 | `… probe_tail469_round6.py --out …/round6.json`（service 层计数） | 0 |
| 7 | `… probe_tail469_round7.py --out …/round7.json`（月报分段计时） | 0 |
| 8 | `tools/dev/backend_verify.py --source-env D:/dev/mtrl-workbench/.env --test tests/test_tail469_screen_reads.py -- -q` | **1 首次**（新增检查自身断言写错：未命中仓不建桶 → `KeyError`，改成 `"甲仓" not in …` 后 0）→ **0** |
| 9 | 同上，7 个模块（m07_balance / wired_m07 / acc_setl_001 / acc_setl_ext_001 / tail266_inventory / report_query / path1_weldgas） | 0 |
| 10 | 同上，16 个模块（prj_auto / rpt_big / setl_fetch / big_export / dup_guards / inventory_projection / mechanical_workbench / operation_history / probe_cleanup / project_delete / promote_pending / tail04_export / tail269_history / tail311_bulk_materials / wired_m07_big / layering） | 0 |
| 11 | 同上，**最终合并 6 模块**（新增检查 + acc_setl_001 + acc_setl_ext_001 + m07_balance + tail266_inventory + wired_m07）→ `groups/033209-119464-14312` | **0（48 passed，`cleanup_completed=true`）** |
| 12 | `apps/frontend` `pnpm run typecheck`（`tsc --noEmit`） | 0 |
| 13 | `apps/frontend` `pnpm run test:unit` | 0（33 passed / 0 failed） |

## 5. 最小具名检查（选择理由）

- `tests/test_tail469_screen_reads.py`（新增，5 条）—— 本票唯一覆盖缺口：①按月装载与全量装载逐值等价（含桩忽略 WHERE 的场景）；②装载语句确实按月过滤（防"改了调用但没减行"）；③`extract-screen` 与 `/api/m07/extract` 的 `annual`/`balances` 逐值同签名、只少三项；④页面网格与导出网格仍逐值一致（`test_tail266_inventory.py:80` 判据在本文件内以真实桩再钉一次）；⑤记忆化不改值、近名不误命中、规则即时生效。
- `tests/test_acc_setl_001.py` / `test_acc_setl_ext_001.py` —— 月报、提取的既有独立业务复算（仓库集合、行数、四列合计、归档筛选、矩阵月份连续），直接守卫本次两处取数改动。
- `tests/test_tail266_inventory.py` —— `annual_grids` 与 `build_xlsx` 逐值一致、`build_extract_data` 与 `build_extract_export` 的 annual 结构一致、`big_service` 共用 amounts。
- `tests/test_m07_balance.py` —— 反向守卫：`build_extract_export` 必须真读 `load_balances(s)` 且早于 `extract_template_grid(`、不得出现 `balances=None`；`S.load_balances is R.load_balances`（service 未包一层）。
- `tests/test_wired_m07.py` —— 七个既有端点的文本契约与 `S.save_balance_cell(` / `load_balances(s)` 字符串未破（旧完整出口必须原样保留）。
- `tests/test_layering.py` —— 本票未新增跨包 `repository` import（新增 `load_month_rows` 走本包 repository）。
- 前端 `typecheck` + `test:unit` —— `settlement-api.ts` 只改 URL，类型与既有单测回归。

## 6. 保持不变的契约

- `/api/m07/extract` 出参仍是 `amounts` / `annual` / `annual_totals` / `kinds` / `balances` 五项，值逐字节不变（导出与既有脚本消费者不受影响）；`/api/m07/settlement` 出参、`_s`/`_i` 字符串与 `null` 语义不变。
- 月报表体仍经 `domain.warehouse_rows`/`rows_of` 二次按月过滤与 `resource_code` 排序；空月 `rows=[]`、`counts` 三项、`balance_ok`（`all(is_balanced) and bool(rows)`）不变。
- 年度网格：当前年完整 12 列 + 历史结余列、`2025-11 及之前` cells 仍为 `None`（"不可得 ≠ 0"）、`sum_row` 14 项、归档/继承名单与「全部」下的陌生仓库规则不变；`total == balance + Σcells`。
- 结余不跨请求缓存（手录历史每次现读）；`save_balance_cell` / POST 写路径与 `history_bindings` 未动。
- 未改：`big_service.py`、`load_rows`、`__all__` 既有项语义、共享 grid/cache/history、前端布局与列宽逻辑。

## 7. 未验 / 资源状态

- **未验**：真实浏览器与真实副本 Playwright（`apps/frontend/tests/test_settlement.py` 全文件、`__annualFrames` 首帧几何、`region` 名与 `total` 列文本）——本轮窗口禁 HTTP/浏览器，只能记未验；真实 HTTP 端到端（TTFB、gzip、浏览器 JSON.parse）同样未验。
- **未纳入**：`amounts` 的全量字典在生产带宽下是否还有别处消费（仓内唯一代码消费者是探针 `tools/probe/_e2e_m07bal.py:67`，非产品；若未来要删需另开票改完整出口）；提取的 `load_original_inbound` 抓取 74.5 ms 仍在（属 mod08 取数口径，跨包，本票不动）。
- **保持结论（未改）**：`annual_totals` 仍随完整出口计算（1,687 B / 0.5 ms 级），因为它是完整契约的一部分且无实测净收益证据支持删除；月报的 `summary`/`manifest`/`zip_name` 仍在 service 内构造（API 丢弃，成本 <1 ms，未证明显著，不擅自改契约）。
- **资源状态**：只读 DB 探针窗口已用尽；产物组 `site-performance-tail469-20261103` 未 close（留给主控统一判 close/hold）；未改原票/plan/status/高水位，未 git add/commit/push，未派子代理，未领下一票。
