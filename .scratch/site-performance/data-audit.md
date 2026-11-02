# 全站 API 与读取链静态审计

2026-11-02。基线已核：`daf8a7fce9aaf932a7d971daa7db178ae7becaa4`，分支 `codex/mechanical-derivation-fix-20261102`。本轮仅静态读取源码及既有机械性能证据，没有访问业务库、外部 i8、浏览器业务接口，没有更改源码、正式数据、配置、服务或 Git 状态；唯一新文件为本文。已有无关修改原位保留。

请求的审计配置为 gpt-6.1-sol / high / fresh；工具没有暴露可独立核验的运行配置元数据。本文为活动审计 Markdown，按 `docs/agents/workflow.md:17` 留在 `.scratch`；未产生需登记的截图、trace、数据库副本或运行日志。

## 判断边界

- **确认的是源码行为，尚非确认的性能瓶颈**：以下调用展开、字段消费与刷新范围可以静态确认；调用数不等于 SQL 次数、SQL 执行时间或响应耗时。未经实测不称 N+1、不排名绝对慢页、不估收益比例。
- 既有机械证据可直接复用：`.scratch/mechanical-performance/verification.md:7–25` 已证明当前月 page、原来源敏感签名、全月累计和屏幕/Excel 业务行分离；正式加载 `fbb42d23` 及本机 421/337ms 样本见该文 `:37–41`。这些指标不外推到别的页面或电脑。
- 页面注册表完整范围为 `apps/frontend/src/main.tsx:31–46` 的 15 个入口。账号独立 QueryClient 见 `:65–85`；保活页 `:101–105` 接收 `blocked || !active`。因此“缓存里有查询”不能直接推定它仍 enabled 或会立即发 HTTP。
- 现有 `TAIL-450` 的 P2 同请求事实复用与低优先所选付款预览下推仍由原票持有，本文只更新静态定位，不另开重复主题、不改状态。

### 父任务新增的浏览器线索（不是本审计重测）

父任务在同日正式只读浏览器、1280×720、1.12字号、默认当前月取得以下单次 ResourceTiming，消息直接交给本审计；原始测量与回执由父任务持有。请求可能交叠且受排队/并发影响，duration 不能归因为该端点 CPU/SQL，也不能按路由等待相加。encoded 指浏览器记录的编码响应体，非总传输字节。

| 端点 | decoded body | encoded body（已提供者） | duration 单次线索 |
| --- | ---: | ---: | ---: |
| `/api/m08/inventory` | 16,077,308 B | 1,721,825 B | 3,872 ms；当前月屏幕 0 行 |
| `/api/m06/matrix` | 465,053 B | — | 2,607 ms |
| `/api/m06/mech` | 3,264,194 B | — | 2,546 ms |
| `/api/m05/debt` | 19,495 B | — | 3,321 ms |
| `/api/m05/ledger` | 25,079 B | — | 2,900 ms |

这些线索提升“过程来源投影”和“库存读取/客户端准备”的量测价值；欠款小响应仍慢的原因不能仅靠字节数推断。父任务还观测过程当前14行、measured256、prepare1117ms（字体1.7ms），这是父任务的布局时间戳，不与上述HTTP相加，也不在本只读数据审计中确诊前端热点。

## 页面与端点矩阵

“主要读取”包括首次进入、切范围及页面内已有按需读取；配置/打印/抓取只列入口类别，不执行它们。所有页面共享当前账号历史读取 `/api/history/status`（`history.tsx:48–49`）和壳身份读取 `/api/m15/users`（`main.tsx:133`）；它们不是各页独立复制的 QueryClient。

| 页面 | 主要读取及范围 | 缓存/装配特点 | 屏幕与成品出口 |
| --- | --- | --- | --- |
| `/` 首页 | `/api/m03/notice-list?period=`，全部通知书 | 与通知书共用 `['notices']`，`home.tsx:8–11`；只用计数也消费同一列表，不能先把共享设计判为重复请求 | 无屏幕 Excel 生成 |
| `/projects` 项目档案 | `/api/m01/projects?status=all`、`/promote-pending`、`/archive-pending`、`/trails?limit=8`；删除/同步按需 impact/config | 档案扩展形状独立 key，`projects.tsx:85–88,224–225`，不可混同轻量项目候选 | export 仅用户动作，`:174` |
| `/i8` i8 接入层 | `/api/m02/fetch/records?limit=50/100/200`、`/api/m14/settings` | 记录有界，类型本地过滤，`i8.tsx:35,53–56`；读现有记录不调用外部 i8 | 无自动 Excel/外部抓取 |
| `/notices` 付款通知书 | `/api/m03/notice-list?period=`、全部项目；按需 payment-preview/context、关联候选、归属、单通知书流水 | 主列表全量，本地筛选；`notices.tsx:81–83`；付款预览为 ids，但底层附属集合仍全量（候选 4） | 打印/PDF 为独立 `/api/m03/batch` 动作，`notice-print.tsx:38`；不参与普通首屏 |
| `/debt` 欠款台账 | `/api/m05/debt`、全部项目、`/api/m05/ledger?project_id=&end_ym=` | `flow.tsx:38–46` + `ledger.tsx:148–153`；欠款现行响应同时计算旧摘要及新按项目分类（候选 1）；台账有账号/项目/截止范围 | ledger/debt export 按用户选择，`ledger-controls.tsx:67` |
| `/ledger` 付款流水 | `/api/m05/flows?year_month=`、`/api/m05/stats?granularity/year/quarter/bucket`、全部项目；撤销信息按需 | `flow.tsx:55–68`，全量流水本地筛选；统计另取服务端聚合，不能视为相同读模型 | `/api/m05/flows/export` 按行 ID/顺序独立生成，`:94` |
| `/contracts` 集采台账 | `/api/m11/list`、全部项目；`/api/m11/detail?id=`、候选/归属/配置按需 | `contracts.tsx:74–75` 主表全量，本地筛选；合同详情/子表共用端点但不同校验和 key，不据此直接合并 | export/print-export 为独立动作，`contract-export-api.ts:5` |
| `/process` 过程资料 | `/api/m06/matrix` 与 `/api/m06/mech` 并行，再全部项目 | `process.tsx:61–62`、`process-api.ts:75–78`；全部项目/月份原始+调整矩阵及差异；两 HTTP 的来源读取重复、机械来源完整（候选 2） | `/api/m06/export` 独立；屏幕直接消费业务矩阵 `service.py:174–180` |
| `/settlement` 收发结存月报 | `/api/m07/settlement?period=` | 选月响应，但 `service.py:43` 先 `load_rows(s)` 再内存按月汇总；源码行为确认，尚无收益证据，未单列新候选 | screen 为仓汇总 JSON；按需 settlement/export |
| 同页焊材/气体提取 | `/api/m07/extract?year=&status=`，只在提取 tab active 时启用 | `settlement.tsx:28–29,74–90`；screen 使用年度网格/结余，但响应另有全月 amounts/全年度 totals（候选 3） | screen 与模板共用 annual/domain 计算；extract/export 按需 |
| `/big` 月度会大表 | `/api/m07/big?period=`、全部项目 | `big.tsx:52–66`；各访问月保活但只当前月 enabled；响应另带全量手填历史，当前 React 不消费（候选 3） | screen 直接业务行；POST big/export 可能固定当月选题，**有写语义**，不当只读性能探针 |
| `/inventory` 库存单据与调整单 | `/api/m08/inventory`、在建项目；抓取配置/执行记录按需 | `inventory.tsx:49–56` 全量 rows/adjustments，本地期间/项目/列筛选；后端已复用同请求调整映射 `router.py:96–98`；刷新差额见候选 5 | screen 无 Excel；inventory/export 仅明确单月动作 |
| `/fees` 特殊费用 | `/api/m09/fee/year?year=&pj=`、全部项目 | `fees.tsx:50–51`、`fees-api.ts:41`；后端项目/年份事实 `service.py:82–108`，未见普通页面依赖 Excel | 屏幕年度行，不自动生成 workbook |
| `/mechanical` 机械费 | `/api/m06/workbench/page?ym=`、全部项目 | `mechanical.tsx:130–131`；当前月紧凑来源，累计仍全月事实；`workbench.py:1027–1083` | `company_rows` 与 Excel 共享业务投影；preview/export 只按需，普通打开/切表/保存无 workbook |
| `/rules` 规则配置 | `/api/m14/rules`、`/jc-ignore`、`/mech-match` | 三组配置并行 enabled，`rules.tsx:64–75,152,212`；未见高量级响应证据 | 无 Excel |
| `/users` 用户管理 | `/api/m15/users` | `users.tsx:39`；与壳身份用同端点但独立语义/生命周期，先保账号核验边界；未读取任何凭据响应 | 无 Excel |

本次未发现除已修机械外，其他标准页面仍在首屏通过 Excel workbook→JSON 生成屏幕的证据。`mod07` 和过程页已经使用业务行/矩阵读取；不能把“Excel 也复用此业务服务”当作“屏幕生成 Excel”。

## 高价值候选（最多五项）

### 1. 欠款同请求一次事实组装：沿用 TAIL-450 P2

**确认的静态行为**：`backend/app/mod05_flow/router.py:48–64` 在一次 debt 请求依次调用 `build_debt_live`、`total_debt_rows`、`notice_debt_views`。`service.py:202–203` 与 `:322–325` 各取通知书并经 `opening_views` 再取一次；`opening_views` 在 `:84–85`。展开为 5 次 `notice_debt_views`、2 次 `mechanical_totals`、2 次集采列表装配（集采入口在 `:255–258,339–345`，`mod11_jc/service.py:219`）。这是与原票相同的调用计数，不是实测 SQL 次数。

**成熟策略**：像过程 `service.py:118–138` 的请求内分桶和库存 `router.py:96–98` 的调整映射复用，由数据主人一次装配通知书视图、期初调整、项目索引、机械及集采事实，然后把它们交给现有纯金额计算函数。不要加进程/全局 TTL 缓存或跨域直查。当前 DebtPage 只消费 `by_project_category`（`flow.tsx:40–43`），其余摘要是否有 API 兼容消费者需保留核对，不直接从旧端点删。

**最小可证伪测量**：同一只读快照，原/候选交替各两次；计 SQL 执行次数/时间、事实装配调用次数与 CPU、状态构造/编码耗时、响应字节；原 JSON 逐值相等（含顺序）。若只减少薄函数调用而 DB/CPU/端到端无实际净收益，保持当前职责，不扩大抽象。没有金额/标签/跳过/未归属相等证据就停止。

### 2. 过程资料屏幕的机械来源投影与双读取复用

**确认的静态行为**：`apps/frontend/src/process-api.ts:75–78` 并行请求 matrix/mech；matrix 经 `backend/app/mod06_proc/service.py:118–122,174–180` 取全部库存、机械、历史和 cutoff；`router.py:108–113` 的 mech 再取机械、历史、cutoff 和明细签名。两请求的原子性也不同，不能因并行就称同一个数据库快照。`repository.py:91–98` 为每个月调用 `mech_effective` 默认完整 sources；`:34–36` 深拷贝来源；`router.py:161–169` 把它们全量送出。当前 React 的来源检查只读 `mode`（`process-api.ts:54–65`），金额/有效签名/明细签名另有字段。

**成熟策略**：优先复用机械页 `repository.mech_effective(..., compact=True)`（`:39–56`）保原来源敏感签名而只传 mode；投影必须在复制之前发生。事实读取可由一次请求拥有明确输入快照，再产矩阵与编辑 token；是否合成 page 端点先由数据量/一致性收益测量决定。保全部项目/月份本地切换能力，不能简单只给首屏项目、当月或先分页；过程资料本来就是完整横向历史表。

**最小可证伪测量**：不先改接口，记录两现行响应解压 bytes、sources 子树 bytes、load_mech/mech_effective/deepcopy 构造耗时和 SQL。以内存同对象紧凑投影作对照，再由来源主人候选构造证明前置复制确实消失。逐项目/月/列核矩阵、`effective_values`、有效签名、明细签名和 mode 一致；先保原 `/mech` 完整兼容出口。若 sources 体积很小或装配不是热点，不先做新合成协议。此处没有沿用旧机械11.23MB样本冒充过程响应的实测体积。

### 3. MOD07 屏幕专用投影：不发送不用的全量历史，不重复取同一事实

**确认的静态行为**：

- extract：`backend/app/mod07_setl/api.py:105–127` 返回全部项目/月 `amounts` 和所有年度 `annual_totals`，同时返回当前年 `annual` 与 balances。React `settlement-api.ts:10,23–35` 与 `settlement.tsx:98–113` 只消费年度网格/结余，未消费 amounts/annual_totals。`api.py:107` 取一次 balances，`:108` 的 `annual_grids` 又在 `service.py:167–168` 读一次 balances。
- big：`big_service.py:165–166` 装配行时读 `R.load_manual(s)`，`api.py:196–209` 随后再读一次并序列化全部月份/项目手填历史。React `big-api.ts:17–20,24–48` 验证 manual_keys/fmts 和行内 `manual.value/from`，没有消费顶层全量 `manual`。已有后端 B.assemble_rows 负责上次值带入，不能因为旧注释说前端需要就推定当前 React 仍需要此对象。

**成熟策略**：像机械 `page_state` 保旧完整契约、新屏幕投影只构造消费者字段；请求内 annual_grids 接受已取 balances/project context，big 一次 load_manual 给 assemble_rows 和兼容消费者复用。保持服务端全历史用于带入和累计，删传输字段不等于删历史事实，也不等于将 SQL 过滤到当前年/月。

**最小可证伪测量**：每端点单独测原响应顶层字段 bytes、load_manual/load_balances 次数及构造/编码 CPU。先 extract 或 big 单端点做小批，不捆绑两个实现；所选年/月的完整行、顺序、合计、历史结余 null/0、归档/继承名单、`manual.from` 与导出同值相等。若全历史体积/重复查询低到收益不足，先仅复用本请求事实，不增新 API。只 GET 读测，不调用会固定选题的 POST big/export。

### 4. 单对象核对的范围下推与缓存身份：沿用 TAIL-450 低优先候选

**确认的静态行为**：

- 所选付款预览虽传 ids（`backend/app/mod03_notice/notice_api_router.py:506–510`），`list_view.py:187–195,246–278` 仍读全量流水/关联/留痕后仅选通知书。原票已有此项；不另开题。
- 单通知书“付款流水”弹窗用独立 `['notice-flows',id]`，但 `apps/frontend/src/notice-flows.tsx:14–15` 调全量 loadFlows 后过滤；`flow-api.ts:17` 请求全部月份，后端 `mod05_flow/service.py:154–156` 为全部流水装全部通知书和项目字段。多次查看不同通知书可能复取同一全量集合，但未测实际 HTTP/Query 缓存命中。
- 集采付款候选 `contract-subtables.tsx:164` 也用合同专属 key 读取全部 notice-list；这是事实，不据此缩减合法候选集合。

**成熟策略**：已有 `flows_of_notices`、`links_by_notice` 可按 IDs 下推；也可在确需完整候选的地方共享原 `['notices']`/`['flows']` 的可信读取，避免每个对象另建同响应缓存。先明确“当前服务器核对”还是“同次可信缓存展示”，不能拿 stale 旧缓存绕过付款前重新核对。未知写入的可靠读回仍强制权威读取。

**最小可证伪测量**：固定同一通知书 ID/付款选中集，比全量行数与目标行数、读取/序列化 bytes、相同新鲜度下打开两个不同对象的 HTTP 数及耗时。比较全部字段/顺序，包含已撤销、失联流水；`flows_of_notices` 与旧全量倒序可能不同，必须显式保持原序。若量级很小，不增加端点/缓存协议。本项优先级低于前3项。

### 5. 库存全量规范行、客户端装配与保存刷新：先量阶段成本

**确认的静态行为**：库存16MB响应不能归为“携带i8 raw/source原文”。`backend/app/mod08_inv/repository.py:81–98` 明确只 select 22 个规范列，`to_row:35–61` 只构造规范行及调整值；ORM/raw 由另一出口 list_details 保存给原单/刷新消费者。`router.py:96–124` 在完整规范行上附 `c5/adjusted/original_values/edit_token`，并另带完整 adjustments。`inventory-api.ts:59` 的 GET 无期间/项目参数，`:60–61` 本地按核算月、仓库、方向和调整状态过滤，`inventory.tsx:52–56` 再做有效值映射与列筛选。父任务当前月0显示行并不等于全量没有数据。

客户端 `inventory-api.ts:56` 对每个 row 调 `adjustments.some` 检查行与调整匹配。可以确认其最坏工作量随 rows×adjustments 增长，但没有实际调整单数量和CPU采样，不能直接称为实测热点。成熟的小规模索引方法已在后端 `router.py:96–98` 使用 row_id→调整映射；若测量命中此处，可在读取校验中建立 Set/Map 保相同一致性检查。

**有界策略**：先按响应顶层/字段字节、row/adjustment数量、JSON解析、readInventory校验、effectiveValues映射和后续筛选/布局分段量测。若规范行/原值与调整值重复传输确有大成本，再评估紧凑读模型并由客户端保原显示/校验形状；若考虑范围下推，需要明确保全范围选择、零HTTP本地筛选、列枚举、完整合计、通知书/差异跳转定位和导出语义，不将“当前月0行”当作直接删除全量读取的授权。SQL范围下推与仅减少传输是不同方案。

**已存在且应保留的成熟模式**：`docs/architecture/writes-and-history.md:7–11`：全账号缓存统一标脏 `refetchType:'none'`，只立即可靠读取当前工作区与当前账号 history；其他页激活时重读。机械 `mechanical.tsx:207–210`、过程 `process.tsx:87–90`、合同 `contracts.tsx:96–99`、费用 `fees.tsx:60–63`、大表/提取已采用，不维护人工“写→页”依赖表。

**确认的静态差额**：库存调整调用 `inventory.tsx:59–63` reload，先取库存，再用默认 refetchType 失效所有非 inventory keys；调整的写成后读回失败和未知保护归 `inventory-adjust.tsx:38–62`。台账 `ledger.tsx:185–195` 当前项目可靠读回后立即 invalidate debt；在欠款页 debt 同时 enabled，的确存在额外读取意图，但页面上的欠款摘要需要更新，不能机械删去。History `history.tsx:68,90` 和 flow-revoke 全局重读是显式恢复/撤销动作，不等同普通格内保存，先保其语义。

**不能从源码确认的结论**：main 对隐藏页 blocked，所以不能把库存的宽 invalidate 写成“当前触发全站立即 HTTP”，也不能宣称它是主要慢点。正常库存页可能只重读 history/少量同页查询；需量测当前 enabled/active key。

**最小可证伪测量**：只在可丢弃副本保存一条库存调整，预先访问其他页面后切回；记录 invalidated/active/enabled keys、实际 HTTP 次数、当前库存与 history 可靠读取顺序和耗时。对照 none + 当前工作区/history 时，其他页面下次激活仍读最新金额/分类；写成后历史失败仍保持正确“已写成、读回失败”状态，未知/后续草稿不被解除或覆盖。若当前没有额外请求净收益，则保持明确差额记录，不把统一形式当优化目标。

库存读取的第一步无需写副本：同一只读输入量测上述构造/编码/解析/校验阶段；若改 Set/Map 或投影，以相同JSON/校验错误和完整过滤结果作对照。只有保存刷新差额需要上述写副本测量，不向正式库保存来证明它。

## 执行边界与停止条件

1. 第一轮优先从候选2或5的已见较大响应选一个测量；候选1的同请求复用沿原票继续，不能凭单次HTTP排序确诊。一次只核一个真实热点，不并行扫正式库，不对“有全量字段”一律分页。通知书/流水/库存的全量集合承担本地零 HTTP 筛选、完整金额/合计/选择与导出范围；改变范围要先证明这些消费者仍正确。
2. 源数据、历史、明细版本、基线、幂等回执留在数据库；紧凑字段从原数据主人投影。金额计算仍归现有 domain/core money，签名仍包含原来源/版本，不能换成“只对金额求哈希”。未知 i8 仍未知，null、0、空文本与缺失事实不混。
3. 请求内复用不跨账号/请求缓存；跨请求读取身份由账号独立 QueryClient 与项目/月/范围 key 共同确定，不另建跨账号共享缓存。当前账号校验失败保树/草稿并阻断网络意图，迟到旧账号响应不得发布。壳身份与用户管理虽同端点，不凭相同 URL 合并生命周期。
4. 正常保存、未知结果、已写成后读回失败分别判定；读回完成前保已提交显示及后续草稿，不用放弃草稿解除 unknown lock。必要时复用 cell-save/use-cell-save/HistoryGuard，不能以减少 GET 为由绕开可靠读回。
5. 最小测量同时回答“减少了什么”和“保住了什么”：阶段 CPU/SQL/编码/HTTP/bytes 分开计；同源顺序/金额/来源/token 等值是前置条件。结果无净收益或业务等值不清就停，不为累计通过数扩测。

本轮完成标准是静态审计与可执行量测候选，未实施任何候选，也未接受新的性能 SLO。与 TAIL-450 重叠的采用项继续在原票收敛，其他新候选由父任务整合裁定；本文不自动形成排期、提交或部署授权。
