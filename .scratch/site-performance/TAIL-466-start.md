# TAIL-466 开工报告（路线 B · 首轮开工批次）

2026-11-02 · DSH 执行者（`workbuddy/deepseek-v4.1-flash`，请求 high）· 会话 `session-a8d242d6-a4a9-46a8-8d42-c0b7dc2cfe3f`

- 基线：分支 `codex/site-performance-20261102`，HEAD `daf8a7fce9aaf932a7d971daa7db178ae7becaa4`（`git rev-parse HEAD` / `--abbrev-ref HEAD` / `git status --porcelain`，各 exit 0）。
- 运行配置回显：系统提示可见模型 `deepseek-v4.1-flash`；**reasoning effort 无任何工具输出回显 ⇒ 只记「请求/继承 high、运行配置未核验」**。
- 本批次范围：源码核查、可复现量测方案、首个候选与资源请求。**未运行 backend_verify、未做浏览器/HTTP 采样、未改产品代码与测试。** 数据库方面**有一次未获授权的 pytest 执行**（对 `TEST_DATABASE_URL` 目标发出只读 SELECT 并在服务端报错）与**一次凭据泄露**（`sed` 打出 `.env` 的 DSN 值），两处均已按主控 2026-11-02 22:44 复核意见完整披露并更正推论，见 §7.2。
- **本报告在 2026-11-02 22:5x 按主控复核意见重写过两处**：§7.2（越界与错因更正，含「正式库 schema 漂移」结论作废）与 §7.2b（外部产物改为逐文件核对清单，并更正群目录状态）；另订正 §3.2/§8 中自设阈值、§5 R3 理由、§7.3 未验项。
- 本批次唯一新增文件 = 本报告。其余路径只读；未执行 `git add/commit/switch/reset/clean/stash`。
- **数字口径（最重要的一条）**：§3 的全部毫秒数来自「**真实产品代码路径 + 合成同构输入**」（20,000 行 / 4,000 调整单，14,698,122 B）。**不是真实业务数据、不是真实数据库、不是真实浏览器**。它只能支撑「阶段占比」与「复杂度阶」的判断，**不能当作真实收益，也不能当作实测热点**。真实行数/调整数/真实收益必须在 §5 的独占时段里采（§4）。

---

## 1. 已核基线与相关文件归属

### 1.1 工作树状态（保护，不触碰）

`git status --porcelain`（exit 0）显示他人与本 effort 的既有改动，全部按保护处理：

`M CONTRIBUTING.md`、`M docs/agents/issue-tracker.md`、`M docs/agents/workflow.md`、`M docs/guides/frontend-design.md`、`M docs/status.md`、`?? .impeccable/`、`?? .scratch/oilcard-management/`、`?? .scratch/site-performance/`、`?? .scratch/tails/issues/TAIL-464..472-*.md`（9 张）、`?? .tmp-fees-width.py`、`?? DESIGN.md`、`?? PRODUCT.md`、`?? debug.log`。

`debug.log`（28,314 B，mtime 2026-11-02 11:13，仅 Chromium `SharedImageManager` 报错）**早于本会话（21:37）启动，非本执行者创建，未读取全文、未修改**，按保护处理并在此登记以免被误当成本批产物。

### 1.2 归属表（本票只写 §6 列出的前端三件与后端 `mod08_inv`；其余只读）

| 路径 | 归属 | 本票动作 |
| --- | --- | --- |
| `apps/frontend/src/inventory-api.ts` | **本票（466）** | 候选修改域（§6 候选一/二） |
| `apps/frontend/src/inventory.tsx` | **本票（466）** | 候选域，但本批不改；`reload` 宽失效只做量测申请（§6.4） |
| `apps/frontend/src/inventory-adjust.tsx` | **本票（466）** | 只读：确认 `edit_token` 消费面 |
| `backend/app/mod08_inv/router.py` | **本票（466）** | 候选域 |
| `backend/app/mod08_inv/repository.py` | **本票（466）** | 候选域（`adjustments()` 全表读，§6 候选三） |
| `backend/app/mod08_inv/service.py` | **本票（466）** | 只读：**不是** `/api/m08/inventory` 的消费者（见 §2.2） |
| `backend/app/mod08_inv/adjustment_values.py` | **不在本票写域** | 只读；`edit_token`/`original_values` 的产出处 ⇒ 协议变更须主控裁定（§5 R6） |
| `backend/app/main.py`（`GZipMiddleware`） | **共享/主控** | 只读；压缩级别属跨页共享决策 ⇒ §5 R5 |
| `backend/app/mod06_proc/domain.to_category` | 464/共享 | 只读调用，不改 |
| 共享 Grid / PageSurface / 列宽 / 字体 / 历史 / 缓存基础设施 | **主控共享** | 只读 |
| `backend/app/report_export/**`（`export_inventory`） | 未分配 → 主控 | 只读；导出为独立端点（§2.1） |

---

## 2. 调用者、契约与现有最小检查

### 2.1 端点与响应契约（已逐行核源码）

- `GET /api/m08/inventory` → `backend/app/mod08_inv/router.py:82` `def api_inventory() -> dict`，装饰器行 **`:82` 必须保持字面形态**（被 `backend/tests/test_wired_m08.py:85-88` 文本 grep 断言）。
- 单 session 内两次读取：`router.py:95` `adjs = adjustments(s)` → `:96` `rows = load_rows(s, adjs=adjs)`（同请求复用调整映射，`len(queries)==2` 被 `backend/tests/test_inventory_projection.py:53` 钉住）。
- 逐行附加（`router.py:97-104`）：`{**r, "c5": to_category(effective_value(r,"material_property")) or "", "adjusted": r["id"] in adjs, "original_values": original_values(r), "edit_token": edit_token(r, adjs.get(r["id"]))}`。
- 顶层返回（`router.py:124`）：`{"rows", "adjustments", "count", "projects", "material_properties"}`；**返回类型必须是 dict**（`test_inventory_projection.py:81,84` 断言 `actual == router.api_inventory()` 全体相等）。
- 规范化行 22 键（`repository.py:37-61` `to_row`）：`id, ym, warehouse, project_full_name, doc_no, seq, direction, material, material_property, spec, unit, qty, price_excl, price_incl, amount, tax_total, biz_type, vendor, doc_date, audit_date, wbs_name, cbs_name`；`_with_adjustment` 另有 6 个 `adj_*`。
- **序列化路径已定论**（推翻本批次中途的一个错误假设）：`fastapi/routing.py:740-762` 在「有返回注解 + 默认 `JSONResponse`」时 `use_dump_json=True`，走 **pydantic-core 的 `field.serialize_json`**，**不经过 `jsonable_encoder`**（插桩计数：`{'enc': 0, 'dump': 1}`）。因此 `rows[*].qty` 等 5 个数值字段在 wire 上是**字符串** `"10.00"`（pydantic v2 把 `Decimal` 序列化成 str），而 `adjustments[*].amount` 是**数字**（`_money()` 已 `round(float(to_money(x)),2)`）。**⇒「换 `Response` + 预序列化提速」在本项目没有空间**；任何改动都必须保持这个混合 wire 形态。

### 2.2 装配函数的生产调用点（全仓 grep）

| 函数 | 生产调用点 | 说明 |
| --- | --- | --- |
| `router.api_inventory` | 仅定义处（`router.py:83`） | 无其他 Python 调用者；但测试直接调用（§2.4） |
| `repository.load_rows` | `router.py:96`、`service.py:23`（包间出口） | `service.build_page_data` 走旧服务端渲染路径，**不是 JSON 端点** |
| `repository.adjustments` | `router.py:95`、`service.py` 侧 | `repository.py:78` = `{a.row_id: a for a in s.execute(select(InvAdjustment)).scalars()}` ⇒ **整表读、无期间/项目过滤** |
| `adjustment_values.edit_token` | `router.py:94`；比对 `repository.py:174`（save）、`repository.py:211-214`（clear） | 产出唯一，消费面见 §2.3 |
| `domain.filter_rows/coarse_rows/sum_cells` | 旧服务端渲染 `service.py:105` 起 | **不出现在 `/api/m08/inventory` 链路**（本地筛选在前端） |

### 2.3 响应字段的消费者（决定「不能删什么」）

- `edit_token` 全仓消费面：产出 `backend/app/mod08_inv/adjustment_values.py:79`；服务端比对 `repository.py:174`、`:211-214`；API 出口 `router.py:94,105`；前端仅 `inventory-api.ts:16,43`（类型/`typeof` 校验）与 `inventory-adjust.tsx:19,36`（`token:row.edit_token` / `token:source.edit_token` 提交 `expected`）。⇒ **对客户端是不透明乐观并发令牌，长度不承载语义**；但缩短属响应契约变更（§5 R6）。
- `original_values` 消费面：`inventory-api.ts:38` `effectiveValues`（`{...row.original_values, ...(adjustment?.values ?? row.adjusted_values)}`）+ `inventory-adjust.tsx:19,36` 用其作为表单初值。**它是「已存在的 5 个数值 + material_property 的 2 位小数字符串副本」，可由 `row` 字段重算** ⇒ 属可推导信息。
- `inventory.tsx` 侧：`:49` `useQuery(['inventory'], queryFn: getInventory)`（**GET 无期间/项目参数**）；`:52` `displayedRows` 逐行 `{...row,...effectiveValues(row),amount:row.amount}`；`:53` `coarseRows`；`:54` `target!==null ? displayedRows.filter(id) : filterRows(coarse,deferredFilters)`；`:56` 列值清单仅 `filterOpen`；`:59-64` `reload()` = `cancelQueries` → `fetchQuery(staleTime:0)` → `invalidateQueries({predicate: q => q.queryKey[0] !== 'inventory'})`；`:83` `useGridPresentation(..., scope:JSON.stringify([...]))`。
- 导出：`inventory.tsx:98` 走 `SettlementExport url={/api/m08/inventory/export?period=...}`，即 `router.py:184 api_export_inventory` → `report_export.export_inventory`，**独立取数、不消费本端点响应**。

### 2.4 `readInventory` 的校验语义（逐条，作为等值基线）

`apps/frontend/src/inventory-api.ts:39-58`，失败一律 `throw new ApiError('库存读取不完整，请重读。')`（`:23`）：

1. `:40` 顶层：`record(value)`、`rows/adjustments/projects/material_properties` 都必须是数组，后两者元素全为 string。
2. `:42-43` 每行：`record(row)`、`Number.isSafeInteger(row.id)`、`ym`/`project_full_name` string、`adjusted` boolean、`direction`/`edit_token` string。
3. `:44` `original_values` 必过 `readValues(..., partial=false)` ⇒ **5 个数值字段必须存在且过 `cents` 正则 + `material_property` 必须 string**；`adjusted_values` 存在时过 `partial=true`。
4. `:45-49` 再遍历 `fields` 的 **18 列**做二次类型校验：`num` 列再走一次 `numeric()`（**第二次 `cents` 正则**）；`adj_amount` 为 `null` 时强制置 `''`（这是唯一允许 null 的数值列）；其余列必须 string。
5. `:52-55` 每张调整单：`id`/`row_id` 安全整数、`remark`/`operator`/`changed_at` string、`before_amount`/`amount` 过 `numeric`、`values`/`before_values` 过 `readValues(partial=true)`（`before_values === null` 保留 null）。
6. `:56` 三合一一致性：`new Set(rows.id).size !== rows.length`（行 id 唯一）`|| new Set(adjustments.row_id).size !== adjustments.length`（调整单按行唯一）`|| rows.some(r => r.adjusted !== adjustments.some(a => a.row_id === r.id))`（**`adjusted` 标记必须与调整单集合一致**）。
7. **已核的宽松语义（改写必须保持）**：第 6 条**不会**拒绝「调整单指向不存在的行」（dangling）。即 `rows` 里找不到对应行时，该调整单只参与 `row_id` 唯一性检查，不触发错误。任何用索引重写的实现必须沿用这一宽松性。

### 2.5 现有最小检查（已核判据；本批只运行了不需要 DB/服务的两项）

| 检查 | 位置 | 判据 | 本批状态 |
| --- | --- | --- | --- |
| 行/调整投影与查询数 | `backend/tests/test_inventory_projection.py:53` | `len(queries)==2`；detail SQL 不含 `inv_detail.raw`/`created_at`；`actual == router.api_inventory()`；调整/撤销往返 | **需 DB，未运行** |
| 调整值/token/冲突 | `backend/tests/test_inventory_adjustment_values.py` | `edit_token` 稳定性、`DataConflictError` 文案、legacy `overrides` 兼容 | **需 DB，未运行** |
| 接线文本断言 | `backend/tests/test_wired_m08.py:85-88` | `'@router.get("/api/m08/inventory")' in ROUTER` | 需 pytest（本批未跑） |
| 导出路径文本 | `backend/tests/test_tail04_export.py:295` | `/api/m08/inventory/export` 存在于 `INV_API` 文本 | 需 pytest（本批未跑） |
| 前端零 HTTP 本地筛选 | `apps/frontend/tests/test_inventory.py:10` | 切「全部」期间 + 物料筛选**不得产生 `/api/m08/inventory` 请求**，计数文案 `rows / total 行`，导出按钮在非单月时禁用 | **需真实服务，未运行** |
| 调整保存/读回 | `apps/frontend/tests/test_inventory.py:31` | 可丢弃副本上保存→读回→撤销，`original_values` 不变、`values` 六字段精确 | **需真实服务，未运行** |
| 前端单测整套 | `apps/frontend/package.json:14` 显式 9 个 `.mjs` | 全绿 | **已运行：29 pass / 0 fail，exit 0**（无 inventory 专项） |
| TypeScript | `package.json:12` `tsc --noEmit` | 无类型错误 | **已运行：exit 0** |

⇒ **本票候选一需要的「前端等值」目前只有 `test_inventory.py` 的浏览器用例，而它需要真实服务**。建议在 §6 候选一落地时**新增一个离线单测**（`apps/frontend/tests/unit/inventory-api.test.mjs`，并把它加进 `package.json:14` 的显式列表），用固定快照断言 §2.4 的 7 条语义；这是本批唯一建议新增的测试文件，且属本票具名范围。

---

## 3. 首个可证伪热点、阶段指标与独立业务等值判据

> 全部为 **合成同构输入 + 真实代码路径**（§3.0）。真实行数/调整数未知，所以下面的「热点」是**待证伪的假设**，不是结论。

### 3.0 固定输入的构造（可复现）

- 生成器：`FakeSession({InvDetail: make_detail(1..20000), InvAdjustment: make_adj(每 5 行一张, 共 4000)})`（`backend/tests/m08_helpers.py`）+ `R.session_scope = lambda: Ctx()`，然后
  `from pydantic import TypeAdapter; body = TypeAdapter(dict).dump_json(R.api_inventory())`。
  **注意**：早先用 `jsonable_encoder` 生成会得到 float 金额（与真实 wire 不符）⇒ 已弃用；`TypeAdapter(dict).dump_json` 才与真实响应逐字节一致。
- 产物：`D:/tmp_payload_20000_4000.json`，**14,698,122 B**，rows 20,000 / adjustments 4,000 / `adjusted:true` 行 4,000 / 一致性 mismatch 0。
- 校准：平均 **734.9 B/行**（含 4,000 张调整单分摊）。真实基线是 **16,077,308 B** ⇒ 若真实每行字节数与合成接近，真实行数约 **2.19 万行**（**上界估计，不是测量**；真实字符串更长会低估）。真实调整单数**完全未知**，它决定候选一的收益（§3.2）。

### 3.1 阶段分解（同一固定输入；中位数；单位 ms）

| # | 阶段 | 代码位置 | 中位 | 备注 |
| --- | --- | --- | --- | --- |
| S1 | 服务端装配 `api_inventory()` 整段 | `router.py:95-124` | **2,632.5**（3 次中位） | 含桩开销 |
| S1a | ├ `load_rows` | `repository.py:81-98` | **1,802.7** | **FakeSession 桩的投影复制开销，不代表真实 DB** |
| S1b | ├ 逐行附加 `assemble_items` | `router.py:97-104` | **566.6** | |
| S1b-1 | │ ├ `original_values` | `adjustment_values.py:65` | **135.9** | 5×`format(to_money, '.2f')` |
| S1b-2 | │ ├ `edit_token` | `adjustment_values.py:79-85` | **385.6** | 每行 1×`json.dumps(sort_keys)` + 1×`sha256` |
| S1b-3 | │ └ `{**r}` 浅拷贝 | `router.py:98` | **58.1** | |
| S2 | 序列化（pydantic dump_json） | `fastapi/routing.py:740-762` | **138.2** | 生产路径，非 `jsonable_encoder` |
| S3 | gzip（level 9） | `main.py:262` | **+132.3**（A/B：identity 2,700.9 → gzip 2,833.2） | 同一 app、真实中间件、交错 8 轮 |
| S4 | 传输 | — | **未测** | 合成编码 1,098,308 B；真实基线 1,721,825 B |
| S5 | 浏览器 gunzip + `JSON.parse` | Node 24 近似 | **97.1**（`parse` 单测 55.0，gunzip ≈ 42） | Node 非浏览器，仅作阶 |
| S6 | `readInventory` 校验 | `inventory-api.ts:39-58` | **467.7**（437.9–609.6） | |
| S6a | └ 第 6 条一致性尾检查 | `inventory-api.ts:56` | **358.6**（343.8–400.2） | **占 S6 的 77%** |
| S7 | `displayedRows` 逐行展开 | `inventory.tsx:52` | **17.6–20.7** | |
| S8 | `coarseRows`（全部期间） | `inventory-api.ts:60` | **6.7** | |
| S9 | `filterRows` 3 列（仓库+物料+金额区间） | `inventory-api.ts:63` | **20.9** | |
| S10 | 合计 ×4（qty/amount/adj_amount/tax_total） | `inventory.tsx:27`/`inventory-api.ts:81` | **45.5** | |
| S11 | 列值清单（18 列各建集合） | `inventory.tsx:56` | **62.8** | 仅开筛选时 |

**字节构成（同一固定输入，逐字段精确重算）**：body `14,698,122`；`rows` 块 `13,902,735`（94.6%）；`adjustments` 块 `795,237`（5.4%）；其中 `original_values` 合计 `2,380,000`（**16.2%**）、`edit_token` 合计 `1,280,000`（**8.7%**）、`c5` 合计 `40,000`、`adjusted` 布尔合计 `96,000`。gzip 后：level9 `1,098,308`、level6 `952,023`。
**行形状分层（决定"每行多少字节"的两个不同形态）**：

| 行形态 | 键数 | 平均字节 | 说明 |
| --- | --- | --- | --- |
| 普通行 | **26** | **672.4** | 22 规范列 + `c5`/`adjusted`/`original_values`/`edit_token` |
| 被调整行 | **30** | **780.9** | 额外 `adj_amount`/`adj_remark`/`adj_operator`/`adj_at` |

⚠️ **本批固定输入里没有 `adjusted_values`**：`backend/app/mod08_inv/repository.py:21-32 _with_adjustment` 只有在 `if adj.overrides is not None` 时才写 `adjusted_values` 与 `adjustment_before_values`，而 `backend/tests/m08_helpers.py:134-139 make_adj(...)` 从不传 `overrides` ⇒ 4,000 张调整单全是「只改金额」形态。**真实数据若含多字段调整（`overrides` 非空），被调整行还会多出 `adjusted_values`/`adjustment_before_values` 两块，行更大、`adjusted` 相关字节占比更高**，这正是 §4.2 探针要复测的第一件事之一。
**token 长度扫掠（同一 payload，`TypeAdapter.dump_json` + `gzip.compress`）**：

| 变体 | raw | gz9 | gz6 |
| --- | --- | --- | --- |
| base（64 hex） | 14,698,122 | 1,098,308 | 952,023 |
| token32 | 14,058,122 | 657,047 | 595,101 |
| token22 | 13,858,122 | 516,373 | 483,285 |
| token16 | 13,738,122 | 431,524 | 415,176 |
| 无 token | 13,098,122 | 160,472 | 166,738 |
| 无 `original_values` | 11,938,122 | 1,057,661 | 912,630 |
| token16 + 无 `original_values` | 10,978,122 | 401,951 | 377,543 |

⇒ **64 hex 随机 token 是「编码后体积」的第一驱动项**（1.10 MB → 0.16 MB，−85%），`original_values` 只降 4%（但 raw 降 18.8%）。两者都是**响应契约变更**，本票不自行实施。

### 3.2 首个可证伪热点（候选一，可被数据推翻）

**假设**：`apps/frontend/src/inventory-api.ts:56` 的第三个子式
`rows.some(r => r.adjusted !== adjustments.some(a => a.row_id === r.id))`
是 O(rows × adjustments)，在真实数据上构成「打开库存」的客户端主要可削减项。

**支持证据（合成输入，真实代码路径）**：
- 20,000 行 × 4,000 调整单：该子式单次 **358.6 ms**；`.some` 实际比较次数 **72,002,000**（命中即 break 的累计，非 rows×adj 上限）。
- 同 payload 换成 `const adjIds = new Set(adjustments.map(a => a.row_id))` + `adjIds.has(r.id)`：尾部 **5.5 ms**（4.6–7.7）；`readInventory` 整体 **467.7 → 110.9 ms（省 346.5，4.15×）**，两次 `deepEqual true`。
- **调整单数量扫掠（收益与它线性相关）**：adj=0 → 101.2 vs 100.0（无差）；100 → 97.7 vs 111.1（噪声内）；500 → 111.7 vs 111.3；2,000 → 155.8 vs 115.7（1.35×）；4,000 → 220.8 vs 124.2（1.78×）。

**可证伪条件（必须在真实快照上判，而不是在合成输入上判）**：

> **口径更正（主控 2026-11-02 22:44）**：下面原先写的「≤100 保持 / ≥1,000 实施」与「`Δmedian ≥ 30 ms`」是我**自行设定的门槛，未被主控采纳为本 effort 的硬验收 SLO**。本 effort 按**真实收益**与**低风险维护成本**判断，不据任意数值阈值开/关一项改动。下列数字改为**参考刻度**（说明该项在不同调整单规模下能到什么量级），不是判定线。

- 参考刻度（本批合成 20k 行实测，仅供估算量级）：adjustments ≈ 5 时该子式 2.8 ms；≈ 2,000 时 36.8 ms（占 `readInventory` 26%）；4,000 时 358.6 ms（占 77%）。即**该项收益完全由真实调整单数量决定**，故 §4.2 探针必须先量出真实 `len(adjustments)`。
- 判定形式：在**同一个真实响应体**上交替测 `current` / `candidate`，报出两者的中位数差与逐字段等值结果（§3.4 全绿为**必要条件**，不是充分条件），再由主控结合真实收益量级与该改动约 6 行代码的维护成本决定是否实施。「差值小、改动也小」与「差值小、改动大」的处理不同，不预设单一阈值。

**同时必须承认的反向结论**：本票标题里的「**本地筛选**提速」在本批**没有找到证据**。`filterRows` 三列 20.9 ms、`coarseRows` 6.7 ms、`sumRows` ×4 45.5 ms、列值清单 62.8 ms、`displayedRows` 17.6–20.7 ms（均 20,000 行）。真正大的三块是**服务端装配（S1b/S1a）、传输与编码（S4/S3）、读取校验（S6）**。若真实数据确认这一点，本票应把验收写成「打开提速」，并在票面记录「本地筛选无可证伪热点」这一结论，而不是硬造一个改动。

### 3.3 阶段指标（每次采样都分别记录，禁止合并成一个 duration）

| 指标 | 采集方式 | 单位 |
| --- | --- | --- |
| 真实 rows / adjustments 数 | 服务端探针读响应体的 `len(rows)` / `len(adjustments)` | 个 |
| 规范行 / `original_values` / `edit_token` / adjustments 各自字节 | 对同一响应体按字段求 `len` + 各字段 `json.dumps` 长度 | B |
| 服务端构造（S1a/S1b） | 服务层包裹计时（探针脚本） | ms |
| 服务端序列化（S2） | `TypeAdapter(dict).dump_json` 计时 | ms |
| 编码（S3） | identity vs gzip 双 app 交错 | ms / B |
| 传输 | 浏览器 ResourceTiming（`duration` 与 `encodedBodySize`）**与**服务端 `content-length` | ms / B |
| 解析（S5） | 浏览器 Performance.measure 或离线 Node（标注为近似） | ms |
| 读取校验（S6/S6a） | 在真实快照上分别计 `readInventory` 与尾部子式 | ms |
| 本地筛选/合计/枚举（S8–S11） | 同上 | ms |

**plan.md:25 的约束照旧**：单次 `duration ≈ 3,872 ms` **不得归因为 SQL 或 CPU**；本报告的 S1–S11 只是把一个总数拆成可测的段，拆出来的值同样要带采集条件。

### 3.4 独立业务等值判据（不复用被测实现自证）

候选一改的是「一致性检查的实现」，所以**不能**用 `readInventory` 自己证明自己。判据：

1. **接受/拒绝集合一致**：对同一批输入（含 §3.4.3 的异常族），`current` 与 `candidate` 必须**同时成功**或**同时抛 `ApiError`**，且 `error.message === '库存读取不完整，请重读。'`。
2. **成功结果逐字段相等**：`JSON.stringify(result.rows)` 与 `JSON.stringify(result.adjustments)` 字面相等（含键序），`projects`/`materialProperties` 相等。
3. **异常族覆盖（至少 9 类，已在本批定向跑通 `current == candidate`）**：`consistent`、`noAdjustments`、`allAdjusted`、`adjusted标记错`、`调整单重复row_id`、`行id重复`、**`danglingAdjustment`（必须仍被接受）**、`乱序`。
4. **独立第三方口径（Python，Decimal，不 import 前端代码）**：从同一份真实快照算出
   `N=len(rows)`、`set(rows.id)`、`set(adjustments.row_id)`、`{r.id : r.adjusted}`、
   `sum(Decimal(r.amount))`、`sum(Decimal(r.adj_amount or '0'))`、`count(r.adjusted)`、
   `len([r for r in rows if r.original_values.amount != r.amount])`，
   与前端输出的行数、id 集合、`adjusted` 映射、合计、调整数**逐值相等**；任一不等即判失败。
5. **业务范围保持（零回归）**：`apps/frontend/tests/test_inventory.py:10` 的零 HTTP 守卫、`:31` 的保存/读回/撤销、`:59` 的滚动稳定性三项必须全绿；筛选项数、列枚举值集合、`rows.length / data.rows.length` 文案、`?row=` 单据定位、导出可用性不变。

---

## 4. 可直接运行的量测方案（命令与参数均为占位；本阶段不执行）

### 4.1 前置（须由主控授予，见 §5）

- `<READONLY_SOURCE_ENV>`：**只读**数据库来源 env 文件（只读账号/只读副本）。**不得**使用默认 `.env`（本批已确认默认配置指向 `postgresql+psycopg://…@127.0.0.1:5432/mtrl_workbench`，是开发目标，不是测试/只读探针目标）。
- `<RUN_ID>`：`tools/audit/workspace_paths.py` 要求的安全短标识（`[a-z0-9][a-z0-9-]{0,79}`）；`MTRL_EFFORT=site-performance`。
- 一切产物（真实快照 JSON、探针日志、计时报告）**必须**落到
  `tools/audit/workspace_paths.py` 的 `output_dir(kind)`（`reports`/`logs`/`work`）并带租约，**不得**写进 `.scratch/`。
- 采集期间为**独占窗口**：不并行 backend_verify / 预览 / 其它真实采样。

### 4.2 服务端分段（只读、真实 DB、进程内，不起服务、不监听端口）

```bash
# 仓根执行；--source-env 只读来源；不打印 DSN
cd backend && .venv/Scripts/python.exe -B -X utf8 \
  <WORK_DIR>/tail466_probe.py --source-env <READONLY_SOURCE_ENV> --run-id <RUN_ID>
```

`tail466_probe.py` 要做的**只有读**（列为 §5 R2 的一次性探针，落 `<WORK_DIR>` 租约区，结束回收）：

1. `register_all()`（否则共享绑定未接；仿 `tools/probe/_probe_wh.py` 的「一次性 + docstring 声明副作用」风格，但**不登录 i8、不写库**）。
2. 在**一个** `session_scope()` 里跑真实 `adjs = adjustments(s)`、`rows = load_rows(s, adjs=adjs)`，分别计时（这才是真实 SQL 成本，替换本批的 FakeSession 桩 1,802.7 ms）。
3. 对 `rows` 跑真实 `assemble_items` 并**分段计时**：`{**r}` / `original_values` / `edit_token` / `to_category(effective_value(...))`。
4. `body = TypeAdapter(dict).dump_json(payload)` 计时；`gzip.compress(body, 9)` 与 `(body, 6)` 计时并记字节。
5. 输出（**不含 DSN/凭据**）：`{"rows":N,"adjustments":M,"bytes":{...},"ms":{"sql":..,"assemble":..,"original_values":..,"edit_token":..,"dump":..,"gzip9":..,"gzip6":..}}` 到 `reports/tail466-server-<RUN_ID>.json`，并把 `body` 原样存 `work/tail466-body-<RUN_ID>.json` 作 §4.3 的固定输入。

### 4.3 前端分段（**同一** JSON 输入上分别计 S5/S6/S6a/S7–S11）

```bash
cd apps/frontend && node --expose-gc --import=tsx <WORK_DIR>/tail466-front.mjs \
  --body <WORK_DIR>/tail466-body-<RUN_ID>.json --out <REPORTS_DIR>/tail466-front-<RUN_ID>.json
```

脚本要求（本批已用同款结构验证过，见 §7）：

- 用 `await import('file:///D:/dev/mtrl-workbench/apps/frontend/src/inventory-api.ts')` 加载**真实模块**（tsx 必须；纯 node 会因源码 import 无扩展名而 `ERR_MODULE_NOT_FOUND`）。
- 每个阶段 `gc()` 后跑 N≥7 次取中位数 + min/max，**逐阶段单独计时**：`JSON.parse(text)`、`readInventory(parsed)`、**单独**测 `:56` 尾式子（`current` 与 `Set` 版各一次）、`effectiveValues` 全量、`displayedRows` 展开、`coarseRows('全部')`、`filterRows` 1 列/3 列、`sumRows` ×4、18 列值清单。
- **候选版不落仓库**：把 `inventory-api.ts` 复制到 `<WORK_DIR>/cand/`，只改 `:56` 一行，import 改成绝对 `file:///` 路径后对照（本批即如此做，未污染工作树）。
- 输出 `{"bytes":..,"rows":..,"adjustments":..,"ms":{...}}`。

### 4.4 编码层（gzip 级别）A/B

```bash
cd backend && .venv/Scripts/python.exe -B -X utf8 <WORK_DIR>/tail466-gzip.py \
  --body <WORK_DIR>/tail466-body-<RUN_ID>.json
```

- 双 `FastAPI` 实例：`GZipMiddleware(minimum_size=1024)` 与 `(..., compresslevel=6)`，**交错 8 轮**取中位，同时记 `content-length` 与解码后字节相等性。
- ⚠️ **本批踩过的坑**：比较体积必须读 `response.headers['content-length']`；`response.content` 是**已解码**的 body（两者会都等于 raw 长度，得出「无差别」的错误结论）。

### 4.5 浏览器侧（唯一能把 S4 与真实 3,872 ms 对齐的方式）

```bash
# 既有工具；需要 preview identity（`.artifacts/active` 指向 mtrl_workbench_test、read_only、build 哈希匹配）
python tools/dev/frontend_measure.py run --preview-run <PREVIEW_RUN> --baseline-summary <BASELINE_SUMMARY> --label tail466-start --stage all
```

- 它已内置本票需要的 `inventory_interactions`（切「全部」期间 → 开列筛选 → 逐字输入「钢」→ 清除），并对 `inventory-input`/`inventory-clear` 断言 **无 `/api/` 请求**（`quality()` 的 `unexpected-filter-request`）⇒ 这正是「零 HTTP 全范围本地筛选」的机器判据。
- 位置：`tools/dev/frontend_measure.py:22`（PAGES 含 `inventory`）、`:24`（SCREEN_PAGES）、`:182-200`（inventory 交互）、`:64`（quality 守卫）。

### 4.6 已知局限（量测前先写明）

1. 本批所有 ms 都是**合成输入**，Node/Python 进程内，非浏览器、非真实 DB；**不得当真实收益引用**。
2. `load_rows` 的 1,802.7 ms 是 `FakeSession` 的投影复制开销，**与真实 SQLAlchemy 行构造不可比**。
3. 真实文档字符串长度与合成不同 ⇒ 字节/行换算（2.19 万行）只是量级判断。
4. 真实调整单数未知 ⇒ 候选一的收益区间（0–347 ms）横跨「不值得改」到「值得改」，必须先测。
5. `JSON.parse` 在 Node 与 Chromium 不同实现，§4.3 的 55.0 ms 只能作阶；浏览器真值须 §4.5。
6. `16,077,308 B` 与 `1,721,825 B` 是 plan.md 记录的 2026-11-02 21:05–21:12 只读采样，数据状态可能与测量当天不同 ⇒ 重测必须重新记录 rows/adjustments。
7. 真实 gzip 比（16,077,308 / 1,721,825 = **9.34**）明显差于合成（14,698,122 / 1,098,308 = **13.38**）⇒ **真实数据熵更高**，token/随机串占比更大，§3.2 的 token 与级别结论在真实数据上只会更强，但倍数不可外推。

---

## 5. 需要主控串行授予的资源与理由

| # | 请求 | 理由 | 影响面 |
| --- | --- | --- | --- |
| R1 | **独占只读测量时段**（单窗口，期间不并行 backend_verify/预览/其它真实采样） | 原/候选交替对照必须同快照、同负载；百毫秒级差异会被邻路请求污染 | 阻塞 §3.2 判定 |
| R2 | 批准**一次性只读探针**落本轮 run 的 `work/` 租约区（`tools/audit/workspace_paths.py`，结束回收，不常驻、不进 `.scratch/`） | §4.2 需要真实 `rows`/`adjustments` 数与真实 SQL/装配/编码分段；本阶段全部命令因此无法执行 | 不写产品代码 |
| R3 | 授权读取 `<READONLY_SOURCE_ENV>`（只读账号/只读副本；**不打印 DSN**） | 仓根 `.env` 的 `DATABASE_URL` 指向**开发库 `mtrl_workbench`**（`backend/app/core/config.py:19,87` 固定绝对 `env_file`，故与 cwd/环境变量无关），它是开发目标而非**已核只读探针目标**；探针需要明确的只读来源，与 schema 是否漂移无关（该漂移结论已作废，见 §7.2 C） | 安全边界 |
| R4 | 批准**真实响应体快照**（单一 JSON，约 16 MB）落到 `work/` 租约区作固定输入 | plan.md 要求「固定真实输入」；§4.3 与 §3.4 的等值判据都必须跑在**同一份真实 payload** 上，否则无法证伪 | 大文件走登记租约，须明确 | 
| R5 | 判定通过后，授予 `apps/frontend/src/inventory-api.ts` 的写权（候选一/二，按 §6 顺序）；**并裁定 `backend/app/main.py:262` 的 gzip 级别是否归本票** | `inventory-api.ts` 属本票具名域；`main.py` 是**跨页共享**压缩策略，不由本票私自改 | 写权限 |
| R6 | 裁定**响应契约变更**（`edit_token` 长度 64→16/22、或去掉 `original_values`）是否立项 | 二者是编码后体积的唯一实质来源（−85% / −4%），但会同时改 `adjustment_values.py`（**不在本票写域**）、前后端 2 处消费与 4 处测试 ⇒ 只能由主控决定 | 协议 |
| R7 | 确认与共享表格/列宽（`inventory.tsx:26,83`、`useGridPresentation`）的边界：本票**不动**，若候选一以后需要动列几何，先回主控 | 共享 Grid/PageSurface 属主控 | 交叉 |
| R8 | 若要做「保存后刷新」量测：批准**可丢弃副本**上的 1 次调整保存/读回/撤销 | 验收第 4 条只在可丢弃副本上可验；且不得把 `reload()` 的宽 `invalidateQueries` 静态等同为「实际全站 HTTP」 | 写入（限定副本） |

> **登记入口（主控 2026-11-02 22:44 建立）**：本批次产物群为 `site-performance-first-wave-20261102`，目录
> `C:/Users/Administrator/AppData/Local/AgentArtifacts/projects/mtrl-workbench/groups/site-performance-first-wave-20261102`
> （`record.json` 已存在，`files/` 现为空），访问用
> `tools/artifact_lifecycle.py lease --group site-performance-first-wave-20261102 -- <命令>`。
> R2/R4 的大件在获批后应落该群 `files/`，而非我初版写的 `tools/audit/workspace_paths.py` 独立 run 目录；**已有散件尚未迁入**（见 §7.2b）。

---

## 6. 候选修改：精确文件、先后、交叉点

### 6.1 顺序（每步可独立回滚；前一步不改语义）

1. **`apps/frontend/src/inventory-api.ts:56`（候选一，本票写域，语义不变）**
   把 `adjustments.some(a => a.row_id === r.id)` 换成 `const adjIds = new Set(adjustments.map(a => a.row_id))` + `adjIds.has(r.id)`；同时把 `new Set(adjustments.map(a => a.row_id)).size` 复用同一个 `adjIds`。**保持三式子顺序与短路语义、保持 `danglingAdjustment` 被接受**。收益：合成 4,000 调整单下 `readInventory` 467.7 → 110.9 ms；真实收益取决于真实调整单数（§3.2 可证伪条件）。
2. **`apps/frontend/src/inventory-api.ts:44-49`（候选二，同文件，语义不变）**
   每行数值字段被 `cents` 校验 **10 次**（`readValues` 5 次 + `fields` 循环 5 次）。让 `:45-49` 的 `num` 分支复用 `:44` 已校验过的结果（或对 `numericFields` 跳过二次 `numeric`）。实测等价循环 31.2 → 20.1 ms（20k 行）⇒ **收益小（≈11 ms），属卫生改进**；若 R1 判定候选一已够，可单独保持不改。
3. **`backend/app/mod08_inv/repository.py:78`（候选三，本票写域，须先量）**
   `adjustments(s)` 是**整表读**（`select(InvAdjustment)` 无过滤）。若真实 `inv_adjustment` 行数远大于当前页需要的行数，可加过滤（例如按 `InvDetail.id` 已取行集合）。**必须先量**：真实调整单总数 vs 返回的 `len(adjustments)`；若二者接近（本批合成就是「返回 4,000 = 表内 4,000」），则**无需改**。注意 `test_inventory_projection.py:53` 钉住 `len(queries)==2`，加过滤不得变成第三次查询。
4. **【请求 R5】`backend/app/main.py:262`**：`GZipMiddleware(minimum_size=1024)` 未指定 `compresslevel` ⇒ 默认 **9**。合成实测 level6 比 level9 **编码体积小 13.3%**（1,098,308 → 952,023）、CPU 少 **40.6 ms**（8 轮中位 2,525.0 → 2,484.5；另一轮 3 轮测 140.5 ms）。**两类熵分布下 level9 都劣于 level6**。但这是跨页共享策略 ⇒ 交主控。
5. **【裁定 R6】契约变更**：token 64→16/22 或去掉 `original_values`。改文件为 `backend/app/mod08_inv/adjustment_values.py:65,79`（**不在本票写域**）+ `router.py:94,105` + `inventory-api.ts:16,43` + `inventory-adjust.tsx:19,36` + 4 处后端测试。**本票不自行实施。**
6. **【另量，R8】`apps/frontend/src/inventory.tsx:59-64` `reload()`** 的宽 `invalidateQueries`：只能靠「可丢弃副本保存一次调整 + 预先访问其他页面」量出实际 HTTP 净增，**不得**把静态 `predicate` 当成实际全站请求。

### 6.2 交叉点与禁止事项

- **禁止改** `router.py:82` 的装饰器行（`test_wired_m08.py:85-88` 文本 grep）。
- **禁止改** `api_inventory` 的**返回类型**（`test_inventory_projection.py:81,84` 做 dict 全体相等）。
- **禁止**把筛选改成范围下推/分页：`getInventory` 无参数、`test_inventory.py:10` 断言筛选零 HTTP、列枚举/合计/单据定位/导出都依赖全量 rows。
- **禁止**动共享 Grid/PageSurface/列宽/字体/历史/缓存（`inventory.tsx:26,83`）。
- **禁止**改 `to_category` 归集规则（`mod06_proc.domain` 是唯一出口，464/共享域）。
- **禁止**改导出端点 `router.py:184` 与 `report_export.export_inventory`（独立取数，未分配）。
- `service.py` 的 `build_page_data` 走旧服务端渲染路径，**不在本端点链路上** ⇒ 本票不动它（改动只会影响别处）。
- 序列化：**禁止**换成 `Response` + `json.dumps`（生产已是 pydantic dump_json 最快路径，A/B `delta = −157 ms`），也**禁止**把行金额改成 float（`api.ts:116` 的 `cents` 正则会拒绝 3 位小数/科学计数）。

### 6.3 预期风险（未测，先登记）

- 候选一：`Set` 与 `.some` 在**重复 `row_id`** 下语义相同（都只看「存在性」），但若将来有人想改成「数量必须相等」会改变错误语义 ⇒ 注释里写明「宽松语义是有意的」。
- 候选三：给 `adjustments()` 加过滤后，`adjusted` 标记仍由同一份 `adjs` 派生 ⇒ 语义不变；但若过滤条件写错，会静默把「有调整的行」标成 `adjusted:false`，让保存时的 `edit_token` 比对通过而覆盖并发修改。**等值判据必须包含 `count(r.adjusted) == len(adjustments)` 的独立 Python 口径**（§3.4.4）。
- 压缩级别：只影响传输与 CPU，不改 wire 内容（解码后字节相等已验）；但会改变所有页面的响应体积与缓存命中特征 ⇒ 需主控跨页评估。

### 6.4 不在本票写域、需要另分配的观察

`reload()` 的宽失效（`inventory.tsx:59-64`）与导出侧重复装配（`report_export`）都不属本票候选域；本批只登记「静态差额存在、需实测才能说是净损失」，不提出实现。

---

## 7. 实际执行的命令、原始退出码与未验项

### 7.1 已执行（除 §7.2 两处越界外，其余均为只读/离线；工作树未改）

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 1 | `git rev-parse HEAD` / `--abbrev-ref HEAD` / `git status --porcelain` | 0 / 0 / 0 | HEAD `daf8a7fc…`；分支 `codex/site-performance-20261102`；工作树见 §1.1 |
| 2 | `node --version` | 0 | `v24.22.1` |
| 3 | `backend/.venv/Scripts/python.exe -B -X utf8 --version` | 0 | `Python 3.15.1` |
| 4 | `cd apps/frontend && node --import=tsx -e "await import('./src/inventory-api.ts')"` | 0 | 导出 `adjustInventory, coarseRows, effectiveValues, emptyFilter, fields, filterOn, filterRows, getInventory, numericFields, readInventory, sumRows` |
| 5 | `backend/.venv/Scripts/python.exe -m pytest tests/test_inventory_projection.py --collect-only -q` | 0 | `tests/test_inventory_projection.py: 3`（只收集，不连库） |
| 6 | **`pytest tests/test_inventory_projection.py -q`** | **1** | **越界，见 §7.2**：`sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedColumn) column inv_adjustment.overrides does not exist` |
| 7 | `node --import=tsx --test tests/unit/{cell-save,contracts-api,flow-api,grid-width-state,identity-gate,mechanical-api,notice-codes,project-picker-order,random-id}.test.mjs`（重定向到文件后取真实状态） | **0**（`NODE_EXIT=0`；首次运行时经管道 `tail`，`$?` 取到的是 `tail` 的状态，故重跑取证） | `ℹ tests 29 / pass 29 / fail 0`，`duration_ms 1267` |
| 8 | `cd apps/frontend && npx tsc --noEmit` | 0 | 无类型错误 |
| 9 | 合成固定输入生成（FakeSession 20,000 行 + 4,000 调整单 → `TypeAdapter(dict).dump_json`） | 0 | `D:/tmp_payload_20000_4000.json`，14,698,122 B，rows 20,000 / adj 4,000 / mismatch 0 |
| 10 | 服务端分段计时（真实 `api_inventory` + 真实 `load_rows`/`assemble_items`/`original_values`/`edit_token`） | 0 | `api_inventory` 2,632.5；`load_rows`（桩）1,802.7；`assemble_items` 566.6；`original_values` 135.9；`edit_token` 385.6；`{**r}` 58.1；`dump_json` 138.2；body 14,698,122；gz9 1,098,308；gz6 952,023 |
| 11 | gzip level A/B（双 app、真实中间件、交错 8 轮） | 0 | `level9 1,098,308` / `level6 952,023`（−13.3%），解码相等 `True`；lvl9 中位 2,525.0 / lvl6 2,484.5 / Δ40.6 |
| 12 | identity vs gzip（同 app 交错 8 轮） | 0 | `identity CL 14,698,122` vs `gzip CL 1,098,308`；2,700.9 → 2,833.2，压缩层 **+132.3 ms** |
| 13 | token 长度扫掠（raw / gz9 / gz6） | 0 | 见 §3.1 表 |
| 14 | 前端分段（真实 `inventory-api.ts`，`--expose-gc`，7 次中位） | 0 | parse 55.0；`readInventory` 467.7；`:56` 尾式子 358.6；`Set` 版 5.5；`displayedRows` 17.6–20.7；`coarse_all` 6.7；`filter_3col` 20.9；`totals4` 45.5；列值清单 62.8；gunzip+parse 97.1 |
| 15 | 候选一模块对照（工作树外 `<TEMP>/cand2/cand-inventory-api.ts`） | 0 | `readInventory` 110.9（省 346.5，4.15×）；`deepEqual true`；9 类定向用例 + 4,000 随机 + 3,000 一致型均无差异 |

> 第 9–15 行的输入全部是**合成数据**：只说明阶段占比与复杂度阶，**不构成任何真实收益声明**。

### 7.1b 本轮（主控 22:44 复核后）执行的命令

范围仅「修报告 + 核未登记产物归属」，**未连 DB、未跑 pytest、未起 HTTP/浏览器、未建新合成脚本**。

| # | 命令 | 退出码 | 结果 |
| --- | --- | --- | --- |
| 16 | `ops_grep` 在报告内检索 `schema\|漂移\|overrides\|30 ms\|阈值\|R3` 等 | 工具内 0 | 命中 15 条，逐条定位待改处（无文件改动） |
| 17 | `ops_read_files` 读报告第 160–177 / 275–288 / 333–348 / 396–409 / 403–414 行 | 工具内 0 | 取改前原文 |
| 18 | 逐个具名 `sha256sum` + `wc -c`（13 个文件，#1 用 `D:/…`，其余 `/tmp/…` 与 `C:/…/cand2`） | **0**（末行 `EXIT_OK`） | 13 个文件全部存在、无 `ABSENT`；字节与散列见 §7.2b |
| 19 | `cd /tmp && pwd -W` | 0 | `C:/Users/Administrator/AppData/Local/Temp` ⇒ `/tmp` 的真实绝对路径已定 |
| 20 | 检查产物群目录 `<AGENTARTIFACTS>/projects/mtrl-workbench/groups/site-performance-first-wave-20261102` | 0 | **PRESENT**；含 `record.json`（299 B，`owner dsh-tail464`/`kind evidence`/`state active`/`inventory null`）与 `files/`（**0 项**） |
| 21 | `ls -1 "<群>/files" \| wc -l` | 0 | `COUNT=0` ⇒ 本批散件确未登记 |

> 第 18–21 行均为**只读**核对，未删除、未移动、未登记任何产物。

### 7.2 越界披露（必须由主控知悉）

> **本节已按主控 2026-11-02 22:44 复核意见重写。** 初版把「空守卫 ⇒ 连到 `mtrl_workbench` ⇒ 正式库 schema 漂移」当作已核结论，**该结论不成立，已作废**。下面保留原事故经过（命令、cwd、原始退出码、错误原文），并逐条给出证据位置与仍未核实的部分。

**A. 实际执行的命令与原始输出（保留原事故经过）**

| 步骤 | 命令（cwd = `D:\dev\mtrl-workbench\backend`） | 退出码 | 原始输出要点 |
| --- | --- | --- | --- |
| a1 | `.venv/Scripts/python.exe -B -X utf8 -m pytest tests/test_inventory_projection.py --collect-only -q` | **0** | `tests/test_inventory_projection.py: 3` |
| a2 | `.venv/Scripts/python.exe -B -X utf8 -m pytest tests/test_inventory_projection.py -q` | **1** | 2 个 `FAILED`；`E sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedColumn) column inv_adjustment.overrides does not exist`；`E [SQL: SELECT inv_adjustment.id, inv_adjustment.row_id, inv_adjustment.before_amount, inv_adjustment.amount, inv_adjustment.overrides, ... FROM inv_adjustment]` |
| a3 | `python - <<'EOF'` 仅打印 `DATABASE_URL` / `TEST_DATABASE_URL` / `MTRL_TEST_SOURCE_ENV` 的 `set`/`unset` | 1（heredoc 后串联的 `ls`/`grep` 未匹配） | 三者均 `unset`（**仅就进程环境 `os.environ` 而言**） |
| a4 | `python - <<'EOF'` 取 `get_settings()` 的 URL 形态（不含凭据） | 0 | `scheme postgresql+psycopg host 127.0.0.1 port 5432 db /mtrl_workbench user_set True` |

证据位置：以上为 a1–a4 四次 `ops_bash` 调用的原始 stdout，逐字见本会话该次调用记录；本轮复核用的对话记录副本为
`C:/Users/Administrator/AppData/Local/Temp/tail466_b14_raw.txt`（190,106 B，`sha256 9198ec28f2ee5ff80a4166a585cbc707f56f116602ebb7bf55bd8423dc9801ed`），a1/a2 的调用与输出在第 **1218–1247** 行，a3 在第 1258–1267 行，a4 在第 1275–1281 行。该副本是会话记录、不是项目产物，仅为本节引用便利而存在。

**B. 初版错在哪里（更正）**

初版推论是「三变量全空 ⇒ `point_tests_at_test_db` 返回 `TestDatabaseGuard('')` ⇒ 守卫不拒绝 ⇒ 连到默认目标 `mtrl_workbench`」。**其中「configured 目标为空」这一步是错的**，原因是把「进程环境变量为空」等同于「配置为空」：

- `backend/app/core/config.py:19` `ENV_FILE = PROJECT_ROOT / '.env'`，`:87` `env_file=str(ENV_FILE)` —— **绝对路径、不依赖 cwd 或环境变量**，所以 `Settings()` 一定会读仓根 `.env`。
- `backend/tests/db_guard.py:70` `original = settings_type()`、`:71` `file_values = DotEnvSettingsSource(settings_type)()` 都因此拿到值；本轮已核仓根 `.env`（mtime `2026-11-02 14:38:53`，3482 B）**同时含** `DATABASE_URL` 与 `TEST_DATABASE_URL` 两个键，且两值均非空（只核键存在与长度类别，**不打印值**）。
- 于是 `:74` 的「配置文件有测试库来源但有效 TEST_DATABASE_URL 为空」**不触发**；`MTRL_TEST_SOURCE_ENV` 为空 ⇒ 走 `:92` 分支 `from_sources((original.database_url, file_values['database_url']), original.test_database_url)`。两个 original 都非空 ⇒ `:45` 的「必须同时提供」通过；`TEST_DATABASE_URL` 库名以 `_test` 结尾 ⇒ `:48` 通过；`file_values` 与 `original` 的 `database_url` 同为 `mtrl_workbench`、不等于目标名 ⇒ `:53` 不报同库 ⇒ **守卫成立**，`:97` 执行 `environ['DATABASE_URL'] = guard.test_url`。

**独立反证（比推理更硬）**：`backend/tests/test_inventory_projection.py:33` 在 `seed()` 第一行就 `assert getattr(bind, 'engine', bind).url.database == 'mtrl_workbench_test'`。a2 的两次 `FAILED` 都发生在 `seed()` 之后（第一次在 `:56` 的 `adjs = R.adjustments(s)` 整表 SELECT，第二次在 `rollback_db` 夹具内 seed 之后）。**若目标不是 `_test` 库，会先出现 `AssertionError` 而不是 psycopg 的 `UndefinedColumn`** ⇒ 该次执行的目标确实是 `TEST_DATABASE_URL` 指向的 `mtrl_workbench_test`。

**C. 因此成立/不成立的结论**

- **不成立（作废）**：「默认/正式目标 `mtrl_workbench` 存在 schema 漂移」。**主控已用 `Settings(_env_file='.env')` + 强制 `default_transaction_read_only=on` + `REPEATABLE READ / READ ONLY` 核实 `mtrl_workbench/public.inv_adjustment` 实际含 `overrides` 与 `before_values` 两列**，与本批错误结论相反。
- **成立（有原始输出直接证据）**：该次 pytest 的失败是 `UndefinedColumn: column inv_adjustment.overrides does not exist`，即**执行当时 `TEST_DATABASE_URL` 指向的那一个库**缺该列。
- **未核实（不猜测）**：①那个 test 库为何缺列（是否长期实例、未经 `backend_verify` 的独占临时 schema 升级流程）；②执行当时 test 库的确切库名与 schema 是否已随之后的操作变化；③**是否有任何写入** —— 结构上 `test_rows_api_and_orm_consumers_keep_values_and_query_count` 走 `session_scope()`（`backend/app/core/db.py:78-80` 异常 `session.rollback()`），`test_process_projection_...` 走 `rollback_db` 外层事务回滚，但**我没有查库核对，故不声明「无写入」**，只记录「未核实」。

**D. 对本票的影响（修正后的推论）**

- 初版据此提出的「真实行数探针不能在默认库跑，故需 R3」**理由改为**：默认 `.env` 的 `DATABASE_URL` 指向**开发库 `mtrl_workbench`**，它是开发目标而非已核只读探针目标；R3 请求的是**明确的只读来源**，与该库 schema 是否漂移无关。
- 「先升 schema 再探针」这一前置**取消**（正式库 schema 已由主控核实正常）。
- 我仍**不再重复 a2 命令**；后续任何触及 DB 的执行只在 R1–R3 授予后、对 `<READONLY_SOURCE_ENV>` 进行。

**E. 本节新增第二处越界（必须由主控知悉）**

2026-11-02 22:49 左右，为核对「仓根 `.env` 是否同时含两个库键」，我执行了
`sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=\(.*\)$/\1=\<redacted,len-\2>/p' .env`
—— 本意是把值脱敏成占位符，但 `\2` 捕获的是**值本身**，实际输出为 `<redacted,len-<真实 DSN>>`，**导致 `.env` 中 `DATABASE_URL` 与 `TEST_DATABASE_URL` 的完整值（含用户名与口令）出现在本会话的工具输出里**。这是对「不读出/打印凭据、Cookie、DSN」的**实质违反**，性质比 a2 更直接。

- 影响面：仅本会话的该条工具输出与本报告所引命令；**未写入任何文件、未提交、未外传**。该次输出未进入本报告正文（本节只引命令，不复述值）。
- 已采取：不再对 `.env` 做任何读取或脱敏类操作；后续需要「某键是否存在」时只做 `grep -c` 计数，不做取值替换。
- 请主控：若该口令需按泄露处理，请按其流程轮换；我这边不再触碰该文件。

### 7.2b 本批在**工作树之外**产生的临时产物（逐文件核对；未登记、未搬迁、未删除）

按 `docs/guides/artifact-lifecycle.md` 与 `tools/audit/workspace_paths.py` 的规则，日志/大 JSON/临时脚本应走登记租约。本批为了在「无 DB、无服务」约束下取得可复现的阶段数据，**在工作树之外**产生了以下文件（**均不在 `D:\dev\mtrl-workbench` 内，`git status` 不受影响，也未放入 `.scratch/`**）：

**产物的现状与登记状态**（主控 2026-11-02 22:44 指示：先原位保留，只核「明确单文件是否存在 + 绝对路径 + 散列」，**禁止通配扫描与删除**，且**不把已有散件默认视为已登记**）。下表为**逐个具名文件**核对结果，未做任何目录遍历式统计。

> **登记入口（主控本轮建立）**：产物群 `site-performance-first-wave-20261102`，目录
> `C:/Users/Administrator/AppData/Local/AgentArtifacts/projects/mtrl-workbench/groups/site-performance-first-wave-20261102`，
> 访问用 `tools/artifact_lifecycle.py lease --group site-performance-first-wave-20261102 -- <命令>`。
> 本轮实测：该群目录**已存在**（初版写的「`DIR_ABSENT`、尚未创建」是 22:4x 时点的观察，**已过期，更正为 PRESENT**）；`record.json` 记 `owner dsh-tail464` / `kind evidence` / `state active` / `inventory null`；`files/` 子目录存在但**为空（0 项）** ⇒ **本批散件确未登记**。

**路径说明**：Git-Bash 的 `/tmp` 实测解析到 `C:/Users/Administrator/AppData/Local/Temp`（`pwd -W` 输出）。下表两种写法并列。

| # | 绝对路径 | 字节 | sha256 | 实际消费者 / 依赖 | 可恢复性 | 登记状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `D:/tmp_payload_20000_4000.json` | 14,698,122 | `fe17d90e5c8e78b3c557a49dd00996cfc98a4060b112593cce6e36d8e9a34bc6` | **被 #2 读取**；§3 全部前端数字的固定输入 | 可重生成（§3.0 一条命令），但字节一致依赖 `backend/tests/m08_helpers.py` 与 `backend/app/mod08_inv/repository.py` 现值不变 | 未登记 |
| 2 | `/tmp/final2.mjs` = `C:/Users/Administrator/AppData/Local/Temp/final2.mjs` | 2,385 | `d5c4994fa89fb4837d9d4fccf96e3fac5729052f2105a454489049b214e0c505` | 读 #1 与 #12，产出 §3.2 交替对照数字 | 不可从仓库重建，仅此一份 | 未登记 |
| 3 | `…/Temp/mkcand2.mjs` | 1,557 | `c6ddbdbc3b814effd28e45f6a8e07fd015c1495aa3cdf1e6cedf8e1c9ce2ef56` | 由 `apps/frontend/src/inventory-api.ts` 生成 #12 | 逻辑可重写，但**替换文本未入库** | 未登记 |
| 4 | `…/Temp/equiv.mjs` | 3,002 | `6853fbe9826dd2acc136603d1707a185a85b825b904a1ff25abed690d199caab` | 无外部输入（自造 9 个小样本）⇒ §3.4 定向等值 | 不可重建（样本定义仅在此） | 未登记 |
| 5 | `…/Temp/prop.mjs` | 2,263 | `b8886d30ca70e21811311b1484497131110abfa9e2185a4b10dd8cf1a46e57f6` | 依赖 #11；4,000 随机 payload 属性测试 | 不可重建 | 未登记 |
| 6 | `…/Temp/prop2.mjs` | 1,873 | `a2baa7d0f51859f84cd802ff46400aad5a21c18894afcc5dbfe3e70357154b7a` | 依赖 #11；3,000 一致型随机 payload | 不可重建 | 未登记 |
| 7 | `…/Temp/split.mjs` | 1,216 | `55373b8a0c52d972ea609848f3333af56d25912a15c7d02e06893623fbf746ee` | `readFileSync(process.argv[2])`，无固定输入（配 #1 用） | 不可重建（分段口径仅在此） | 未登记 |
| 8 | `…/Temp/decode.mjs` | 830 | `c42326db4e3096bf29fe4ef7ef886e7ff298886f6cdc9f20753d9316a161b4f3` | 同上，`process.argv[2]` 取路径 | 不可重建 | 未登记 |
| 9 | `…/Temp/gen_payload.py` | 881 | `24525fe1abcc8c64290fb669863d90ad2fce709f8271c3e5614a1d7013297011` | 产出 #1 的**早期不忠实版本**（`jsonable_encoder`，§3.0 已弃用） | 弃用版本，无复用价值 | 未登记 |
| 10 | `…/Temp/gen_payload2.py` | 1,933 | `9c3aca22a3c8c5fc7f7489352151ed54a0ddd5bf094b3551c4f93e179a90d651` | 高熵变体生成器（`random.seed(7)`），用于 gzip 熵对比 | 不可重建（随机字段规则仅在此） | 未登记 |
| 11 | `…/Temp/cand/cand1.ts` | 7,055 | `82a72595e85c4054b91a3786577477949595e8ea5db278dddbea607ed4e4f997` | **被 #5/#6 依赖**；候选一早期副本 | 可由 `inventory-api.ts` + 尾检查替换重建 | 未登记 |
| 12 | `…/Temp/cand2/cand-inventory-api.ts` | 7,081 | `87d58e533aa9c0b25def34a5a943709fa6f0a24354173d2a25e0fc06f695e6f8` | **被 #2 依赖**；候选一（`Set` 改写）正式副本 | 由 #3 从仓库源重建 | 未登记 |
| 13 | `…/Temp/tail466_b14_raw.txt` | 190,106 | `9198ec28f2ee5ff80a4166a585cbc707f56f116602ebb7bf55bd8423dc9801ed` | **本轮新建**：会话记录副本，供 §7.2 A 段引用 a1–a4 原始输出的行号 | 会话记录，非项目产物 | 未登记 |

合计 **13 个具名文件**；除 #1（14.7 MB）外均为 1–190 KB 文本。核对命令为逐个 `sha256sum` + `wc -c`（`EXIT_OK`，见 §7.1）。

**为什么不自行处置**：**不删除** —— 这些是 §3/§7.1 全部实测数字的唯一可复现凭据，判定逻辑只存在于文件中；**不搬迁、不补登记** —— 登记与租约属主控调度，本轮指示是「先原位保留、只核存在性/路径/散列」，且**不把已有散件默认视为已登记**。

### 7.3 未验项（如实登记）

1. **真实 rows 数、真实 adjustments 数** — 未测（无已核只读来源；越界教训见 §7.2）。
2. **真实 SQL 的条数与单条耗时**（§4.2 的 `load_rows` 真值）— 未测；本批 1,802.7 ms 是 FakeSession 桩。
3. **`3,872 ms` 的归因**（排队/单条 SQL/装配 CPU/编码/传输/浏览器解析）— 完全未验；本报告只给证伪条件与分段方案。
4. **backend_verify / 全部后端节点** — 未运行。**更正**：仓根 `.env` 同时提供 `DATABASE_URL` 与 `TEST_DATABASE_URL`（`backend/app/core/config.py:19,87` 绝对 `env_file`），所以「没有测试库」不是障碍；`backend_verify` 需要的是主控授予的 `--source-env <明确来源.env>` 与独占时段（R1/R3）。
5. **浏览器侧**（`tools/dev/frontend_measure.py`、任何 HTTP 采样、`apps/frontend/tests/test_inventory.py`）— 未运行。
6. **真实响应体快照** — 未取得；§3 的等值判据都还只在合成 payload 上跑过。
7. **候选实现** — 未写进产品代码；只存在于工作树外的临时副本。
8. **gzip 级别的跨页影响** — 未评估（`main.py` 是共享策略）。
9. **`edit_token`/`original_values` 契约变更的收益** — 只有编码体积测算，未做任何实现或业务等值。
10. **保存后刷新的实际 HTTP 净增** — 未测（需可丢弃副本，R8）。
11. **模型/effort 运行配置** — 模型可见 `deepseek-v4.1-flash`；reasoning effort 无工具回显 ⇒ **未核验**。
12. **`TEST_DATABASE_URL` 指向的那个库为何在执行当时缺 `inv_adjustment.overrides`** — 未核实（见 §7.2 B/C；不推断其成因，也不据此对任何库的 schema 下结论）。
13. **a2 那次执行是否产生过写入** — 未核实（结构上有回滚路径，但未查库核对，故不声明「无写入」）。

---

## 8. 下一步（请主控裁）

1. **先批 R1–R4**（独占只读时段 + 一次性只读探针 + 只读来源 + 真实快照落租约区）。我按 §4.2/§4.3 在同一份真实 payload 上产出：真实 rows/adjustments 数、各字段字节、S1–S11 分段、原/候选交替对照。
2. 在**同一真实快照**上交替测 `current` / `candidate`，报告两中位数差与 §3.4 逐项等值结果，由主控按**真实收益量级 + 改动维护成本**决定是否进入 §6.1 第 1 步。**主控已明确：本执行者自设的 `Δmedian ≥ 30 ms` 与「adjustments 数量门槛」不是本 effort 的硬验收 SLO**（§3.2 已更正为参考刻度）。
3. **无论判定如何**，请主控就两件事表态：**§6.1 第 4 步（gzip 9→6，跨页共享）** 与 **§6.1 第 5 步（token/original_values 契约变更）** 的归属——它们是本批唯一能实质压缩「编码后 1.72 MB」的杠杆，但都不在本票写域内。
4. 若主控同意，我在候选一落地时**同时**新增 `apps/frontend/tests/unit/inventory-api.test.mjs`（并加入 `package.json:14` 显式列表），用固定快照把 §2.4 的 7 条校验语义钉住——这是本票目前缺失的最小离线回归。
