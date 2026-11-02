# TAIL-467 结果：欠款汇总一次事实装配

主控接收（2026-11-03）：下列为DSH原测量。整合时移除付款域复制的集采合计算法，改由`mod11_jc.service.debt_of_ledger(rows=…)`复用输入；机械独立读取与事实装配共用归集函数。相关事实/来源/集采/欠款导出/分层检查在独立测试schema通过，回执归受管运行`000435-920925-39732`；原HTTP、逐月台账与成品未验不变。

状态：**实现 + 真实对照 + 相关验证已交；本票 done 由主控合并验收。** 未提交、未改票/plan/status/高水位。

## 1. 结论

`/api/m05/debt` 一个请求里，通知书视图 / 期初调整 / 项目索引 / 机械有效值 / 集采行各被装配 **2–5 次**。
改为「原数据主人一次装配、既有纯函数算钱」后，同一只读快照上：

| 指标 | 原路径 | 落地后 | 变化 |
|---|---|---|---|
| wall 中位 (repeat=9 交替) | 535.6 ms | **120.5 ms** | **−77.5%** |
| CPU 中位 | 484.4 ms | **93.8 ms** | −80.6% |
| SQL 条数 / 请求 | 32 | **14** | −56% |
| SQL 耗时中位 | 51.2 ms | 22.9 ms | −55% |
| 响应字节 | 19 495 B | **19 495 B** | 0 |
| 逐值 + 键序 | — | **全等** | — |

重复装配是**真实主要成本**（不是靠任意门槛判定）。无跨请求缓存、无新金额口径。

## 2. 具名补丁（本人改动，未 `git add`/`commit`）

- `backend/app/mod05_flow/domain.py`（+29/−0）：新增 `@dataclass DebtFacts`（`rows/openings/index/mech_by_month/jc_rows`，纯数据容器，docstring 明写「⛔ 不是缓存、⛔ 不在这里算钱」）；`__all__` 加 `"DebtFacts"`。
- `backend/app/mod05_flow/service.py`（+115/−17）：
  - 新增 `_mech_totals_of(mech_by_month)`、`_jc_debt_of(rows)`（逐字沿用 `TAG_IN` 判定 + `quantize(Decimal("0.01"))`）、`assemble_debt_facts(s)`（唯一装配口：`notice_debt_views` 1 次、`history.adjustments(repo.list_openings(...), rows)` 1 次、`project_index` 1 次、`proc.load_mech(s, with_sources=False)` 1 次、`M11.build_list(s)` 1 次）。
  - `build_debt` / `build_debt_live` / `total_debt_rows` 加 `facts: dom.DebtFacts | None = None` 关键字；**`None` ⇒ 老路径逐字不变**（离线桩件、猴补丁、`export_total_debt` 都走这一支）。`total_debt_rows` 的 else 分支**仍字面保有** `M11.build_list`（`test_debt_export` 用 `inspect.getsource` 断言）。
  - `__all__` 加 `"assemble_debt_facts"`。
- `backend/app/mod05_flow/router.py`（+10/−3）：`get_debt_data()._load` 改为先 `facts = svc.assemble_debt_facts(s)`，再 `build_debt_live(s, facts=facts)` 与 `total_debt_rows(s, facts=facts)`，待归属改从 `facts.rows` 取；响应字段与顺序逐字不变。
- `backend/tests/test_tail467_debt_facts.py`（新增 141 行，5 个测试）：见 §4。

`repository.py` 与 `report_export/` **未改**（未分配），导出口径经原 `total_debt_rows` 共用事实保持。

## 3. 输入指纹（真实只读快照，`probe_final.json`）

库 `mtrl_workbench` / schema `public`；`default_transaction_read_only=on`、`statement_timeout=30000`、`REPEATABLE READ` + `READ ONLY`，结束 `rollback`。
`projects=20, notice_rows=1240, notice_excluded=517, notice_unowned=47, openings=82, mech_rows=205, jc_rows=266, jc_tag_in=259`；`by_project_category` 17 行；`wire_B=19495`（与 plan 的浏览器采样一致）。

## 4. 等值判据与实测

- **逐值与顺序**：`by_category` / `total` / `by_project` / `mech_settle_ready` / `openings` / `by_project_category` 全字段深比对（json 往返），`equal.original=true`、`equal.patched=true`、`key_order_equal=true`。
- **集采口径**：`_jc_debt_of(build_list 行)` ≡ `M11.debt_of_ledger(session)`（真库，`test_tail467_debt_facts.py`）。
- **机械口径**：`_mech_totals_of` ≡ `mechanical_totals(session)`（真库）。
- **非缓存**：真库插入通知书法 → 装配得 11.00；改 `stat_settle=12.50` + flush → 重新装配得 12.50。
- **单次装配**：monkeypatch 计数 = `{notice_debt_views:1, list_openings:1, project_index:1, load_mech:1, build_list:1}`，且 `opening_views` / `mechanical_settlements` 一被调用即判红。
- **离线等值**：FakeSession 上带 `facts=` 与不带逐值+键序相等（`build_debt_live`、`total_debt_rows`）。
- **导出同源**：`total_debt_rows` 老路径逐字保留 `dom.debt_by_category` + `build_list`，`test_debt_export` 通过。

### 与 464 的依赖（`probe_nodep.json`，repeat=9）

把 `load_mech` 换回「忽略 `with_sources`、照旧带来源」模拟 464 未合入：535.8 ms → **257.0 ms（−52%）**，SQL 仍 32→14，逐值全等。
⇒ 467 单独合入即可得约一半收益；`with_sources=False` 是剩余 ~136 ms 的来源（464 提供该参数，本票只消费、未改 mod06）。

## 5. 执行的命令与原始退出码

后端检查一律 `tools/dev/backend_verify.py`（每轮独立 run id + 立刻复制回执到 `files/tail467/`）：

| # | 目标 | returncode | 回执 |
|---|---|---|---|
| bv-01 | `tests/test_tail467_debt_facts.py` | **1** | `bv-01-tail467-newtests.json/.log` |
| bv-02 | 同上（修我自己写错的期望后） | **0**（5 passed） | `bv-02-tail467-newtests-pass.*` |
| bv-03 | 10 个相关既有文件 | **1**（65 tests，2 failed） | `bv-03-related-protection-fail.*` |
| bv-04 | **pristine HEAD 副本**跑同 2 个文件 | **1**（13 tests，同 2 failed） | `bv-04-pristine-head-same-nodes.*` |
| bv-05 | 当前工作树跑同 2 个文件 | **1**（13 tests，同 2 failed） | `bv-05-current-same-nodes.*` |
| bv-06 | 8 个相关既有文件（去掉 §6 两文件） | **0**（52 passed） | `bv-06-protection-green.*` |

探针（只读）：`probe_final.py` exit 0 → `probe_final.json`；`probe_nodep.py` exit 0 → `probe_nodep.json`。

## 6. 既有红（**非本次引入**，已定性）

- `tests/test_historical_balances.py::test_material_same_month_multiple_rows_edit_delete_and_export`
- `tests/test_ledger_opening_range.py::test_no_opening_preserves_old_months_and_export[25.12-material]`

证据：`bv-04` 用 `git archive HEAD`（= `daf8a7fc`，不含我的改动）在独立目录跑同一对节点，**失败集合完全相同**（`bv-04`/`bv-05` 进度行均为 `F........F...`）。`ledger_export.py` 与这两个测试在工作树中**无本地改动**；`month_text` 的「2025-11及之前」规则由提交 `bfec6413 Fix mechanical and monthly ledger report exports` 引入，未同步更新这两条断言。两处断言的失败文本分别是 `'2025-11及之前' != '2025-11'` 与 `assert "2025-11及之前" not in by_month`，均属台账导出的**月份文本**口径，不触及 `facts` 路径，`build_ledger` 本次无任何改动（diff 无该函数 hunk）。

## 7. 未验范围

1. HTTP/浏览器端到端未重测（本阶段未启服务；字节数与 plan 采样一致，耗时增益未在浏览器侧复验）。
2. 台账端点 `/api/m05/ledger` 未改、未重测（其重复成本是「每侧一次 `remarks_map`」与 `project_index` 2 次，量级远小，本票不动）。
3. `report_export.export_ledger` 逐项目各调一次 `build_ledger` 的重复装配**未修**（未分配该路径）；本票只保证 `total_debt_rows` 与之同源。
4. 集采 `build_list` 单读在**集采行极大**时的额外内存未测（当前 266 行；复用行对象，不额外深拷贝）。
5. 并发/连接池行为未测（只读单连接快照）。
6. 两处既有红未修（不属本票可写域，需其主人裁定）。

## 8. 资源与边界

- DB：全程只读事务，`REPEATABLE READ` + `READ ONLY`，结束 `rollback`；连接已关闭、engine 已 `dispose`。未写业务库、未读/未打印 DSN 与凭据。
- 产物：全部在 `C:/Users/Administrator/AppData/Local/AgentArtifacts/projects/mtrl-workbench/groups/site-performance-first-wave-20261102/files/tail467/`（探针 6 份 `.py` + 6 份 `.json`、backend_verify 6 轮 11 个文件）；临时 `pristine_head/` 副本（30 MB）已删除，可用 `git archive HEAD` 复现。
- 父 group `record.json` 仅只读校验（`state=active`、`hold=null`），未 register / 重登记 / close。
- Git：未 `add`/`commit`/`switch`/`reset`/`clean`/`stash`；工作树仅新增上述 4 个文件与本节报告。
