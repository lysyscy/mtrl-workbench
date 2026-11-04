# TAIL-481 报表与维护页加载接入 · 实施与验证证据

- 票：`.scratch/tails/issues/TAIL-481-报表与维护页加载接入.md`（blocked_by 477，477 已 done）
- 共同规格：`.scratch/browser-session-loading-20261103/spec.md`（2026-11-04 用户修订版）
- 复用样板：TAIL-477 欠款台账（`apps/frontend/src/ledger.tsx`）、478/479/480 已合入的读取车道
- 共享机制（只读，未改）：`apps/frontend/src/read-region.tsx`、`apps/frontend/src/read-region.css`
- 工作树：`D:\dev\mtrl-workbench\var\worktrees\browser-session-loading-20261104`
- 分支 / 基点：`codex/browser-session-loading-20261104` / 22cc48f8（当前 HEAD 9efebc87，未提交本次改动）
- 记录时间：2026-11-04 23:00
- 范围声明：本票只改 6 个页面及其自身 CSS + 1 个必要行为测试修正 + 1 个新 GUI 行为例文件。`apps/frontend/src/i8.tsx` / `i8.css` 归 476，未触碰。

## 一、结论摘要

改动前这 6 个页面的共同缺陷是三件事叠在一起：

1. **整页被一次读挡在首帧之前**。`rules.tsx`、`users.tsx` 的分块/整节带着 `data-page-loading={query.isPending?true:undefined}`；`apps/frontend/src/page-surface.tsx:34` 的 `if (node!.querySelector('[data-page-loading]')) return;` 因此在待读期间永不认定首帧完成。筛选与工具栏本可先用，却被一起藏住。
2. **读取中/失败/为空三种状态被同一处三元表达式顶掉内容**。`big.tsx`、`settlement.tsx`、`fees.tsx`、`users.tsx`、`rules.tsx`、`projects.tsx` 都是 `{query.isPending ? <p role="status">正在读取…</p> : query.data && …}`，读失败时表格整块消失、页面跳动；`users.tsx` 与 `projects.tsx` 甚至没有"失败但保留上次结果"的分支。
3. **状态字与业务数字挤在同一行**，`big.tsx` 的项目数、`settlement.tsx` 的汇总行、`fees.tsx` 的金额表在首次未知时干脆不渲染，用户无法区分"还没读到"和"读到 0"。

本次按已合入的共同机制接入，不做逐页自创：`readPhase` 判六态、`ReadStatusLane` 提供唯一恒定状态槽、`ReadFailure` 负责失败与保留说明+可达重试、`ReadPlaceholder` + `.read-reserve` 在未知期间撑住内容盒。业务金额、保存链、草稿、列宽、权限门控逐项保持原样（见 3.5）；没有新增轮询、缓存 TTL、自动重试或任何遮盖式实现。

## 二、修改清单

| 文件 | 类型 | 内容 |
| --- | --- | --- |
| `apps/frontend/src/big.tsx` | 改（+23/−5） | 去掉 `isPending ? 正在读取… : data &&` 结构；:157-160 新增 `.big-read-status` 车道（自身失败 + 项目清单失败各一条，可同行）；:164 未知期间渲染 `.big-grid.big-read-reserve.read-reserve` + `<ReadPlaceholder rows={6}>`；:146 项目数改为 `data ? 'N 个项目' : error ? '项目数尚未读取' : reading ? '正在读取项目数…' : '尚未读取项目数'`；:153-155 保存队列 `error` 段收窄为 `{error && …}` 并保留 `重读核对`（同时 `refetch` 项目清单）；:86-87 新增 `readState` / `placeheld` |
| `apps/frontend/src/big.css` | 改（+7） | `.big-read-status{--read-status-pad:calc(16px * var(--fscale))}`、`.big-month > .big-read-status{margin:calc(8px * var(--fscale)) 0}`（车道是 `div`，不受既有 `.big-month > p` 规则约束）、`.big-read-reserve{padding:8px 16px}` |
| `apps/frontend/src/settlement.tsx` | 改（+22/−4） | `Monthly`：删掉独立 `<p role="alert">…重读</p>`，:57-59 改用 `.settlement-read-status` + `ReadFailure`（保留文案"收发结存更新失败，保留上次结果。"），:60 未知期间 `.settlement-grid.settlement-read-reserve` 占位 rows=8，:48-49 计算 `readState`（空判据 = 行数为 0）。`Extract`：:118-120 同一车道（保留文案"库存年度汇总更新失败…"，空判据 = 两个 kind 都无行），:124 占位 rows=8；:114 保存队列段收窄为 `{error||uncertain}` 并保留 `重读核对` / :117 `已核对，保留输入继续`；`AnnualTable` 未动（保持 `domLayout:'autoHeight'` 自然高度与合计行） |
| `apps/frontend/src/settlement.css` | 改（+7） | `.settlement-read-status{--read-status-pad:…16px}`、`.settlement-read-reserve{padding:8px 16px}`、`.settlement-grid.settlement-read-reserve{min-height:calc(260px * var(--fscale));height:auto}` |
| `apps/frontend/src/fees.tsx` | 改（+18/−2） | :74-77 计算 `readState`：`readPhase(query)==='stale' && !ready → 'error'`（错范围的旧载荷不是"保留结果"，不能拿它冒充更新失败），`query.data && !ready → 'reading'`，其余走标准判据；`placeheld = data===undefined \|\| !ready`（`ready` 仍是渲染门，旧范围金额永不上屏）；:106-109 新增 `.fees-read-status`（自身失败 + 项目清单失败）；:111 未知期间占位 rows=6；:104 保存队列段收窄为 `{error\|\|uncertain}` 并保留 `重读核对` |
| `apps/frontend/src/fees.css` | 改（+6） | `.fees-read-status{--read-status-pad:…16px}`、`.fees-read-reserve{padding:8px 16px;min-height:calc(280px * var(--fscale))}` |
| `apps/frontend/src/users.tsx` | 改（+12/−3） | :68 去掉 `data-page-loading`（首帧不再被整页读取挡住，权限区与标题先发布）；:76-78 `.users-read-status`；:79 未知期间 `.users-table.users-read-reserve` 占位 rows=8；删除原来只在 `isError && !data` 时出现的错误分支（现在 stalled/首次失败都走 `ReadFailure`）；计数 `账号列表{data && …}` 不变，未读到不显示 0 |
| `apps/frontend/src/users.css` | 改（+5） | `.users-read-status{--read-status-pad:0;margin:0 0 calc(10px * var(--fscale))}`、`.users-read-reserve{padding:0;min-height:calc(240px * var(--fscale));max-height:none}` |
| `apps/frontend/src/rules.tsx` | 改（+38/−19） | 三块各自去掉 `data-page-loading`；删除局部 `ReadFailed` 组件（六处调用点全部改为车道，:54 组件定义随之移除）；`ExclusionRules` :86-87/:119-122、`JcIgnore` :159-160/:188-191、`MechMatch` :221-222/:238-241 各自 `readState` + `.rules-read-status` + 占位 rows=4；空判据按各自数据（规则 0 条 / 名单 0 条 / 匹配 0 条）；保留"集采项目剔除名单为空；…"与"还没有机械报表项目匹配规则。"原空态；`＋ 增加规则` 仍 `disabled={!writable || !data || data.kinds.length===0}`，`AliasActions` 行内保存报错未动 |
| `apps/frontend/src/rules.css` | 改（+5） | `.rules-read-status{--read-status-pad:0;margin:0 0 calc(10px * var(--fscale))}`、`.rules-table.rules-read-reserve{padding:0;min-height:calc(160px * var(--fscale));max-height:none}` |
| `apps/frontend/src/projects.tsx` | 改（+26/−3） | :203-205 `projectsRead`/`projectsPlaceheld`/`trailsRead`；两个待办列表（`promote-pending` / `archive-pending`）由三元链改为 `.project-pending-region` 包裹 + `.project-read-status.project-pending-status`（原来一个"重读待办"按钮同时管两路读，现在各自命名、各自重试）；主列表 :222-225 车道 + `.project-table.project-read-reserve` 占位 rows=8（`共 N 个项目` 仍只在有数据时出现）；留痕 :226-228 只在读取中/失败时出车道 |
| `apps/frontend/src/projects.css` | 改（+7） | `.project-read-status{--read-status-pad:0}`、`.project-read-reserve{padding:0;min-height:calc(320px * var(--fscale))}` |
| `apps/frontend/tests/test_preview.py` | 改（+6/−2） | `test_real_read_failure_retry_and_session_expiry`：项目档案首读失败后的重试按钮由 `重读项目` 改为共享的 `重试读取`（`ReadFailure` 固定按钮文案），并补 teardown `unroute_all(behavior='ignoreErrors' if report.failed else 'wait')`，避免故意挂起的路由在失败用例里卡住拆解 |
| `apps/frontend/tests/test_report_maintenance_read_lanes.py` | 新增（288 行） | 6 页 8 个行为例，见第四节 |

未触碰：`read-region.tsx` / `read-region.css`（共享，只读）、`page-surface.tsx`、`grid-presentation.tsx`、`business-grid.tsx`、`main.tsx`、`api.ts`、`notice-fetch.tsx`、`ui.css`、`style.css`、`package.json`、`i8.tsx` / `i8.css`（476）、478/479/480 的页面文件、`backend/`、`apps/browser-extension/`、spec/票/status/index、Git（未提交、未推送）。

## 三、控制与数据流依据

### 3.1 首帧门控
`apps/frontend/src/page-surface.tsx:34`：`if (node!.querySelector('[data-page-loading]')) return;`。所以只要页面里还有元素带这个属性，首帧永不发布。本票把 `rules.tsx`（3 处）与 `users.tsx`（1 处）的属性去掉后，`grep -rn "data-page-loading" apps/frontend/src/` 只剩三处，都不是本票可动文件：`i8.tsx:154`（476）、`main.tsx:107`（Suspense fallback，禁改）、`page-surface.tsx:34`（判断方本身）。页面因此可以在数据未到前先发布框架与筛选。

### 3.2 六态判定与"不冒充空"
统一用 `readPhase(read, empty)`：`isError ? (data===undefined ? 'error' : 'stale') : data===undefined ? (isPending&&isFetching ? 'reading' : 'idle') : (empty ? 'empty' : 'ready')`。要点是本票**只用它判状态，不用它造数据**：`placeheld = data === undefined`（fees 额外 `|| !ready`）决定是否渲染占位，`data &&` 决定是否渲染真实内容，两者互不越界。因此"读失败且从未有数据"= `error` + 占位留空（`.read-placeholder-quiet`，占位条 `visibility:hidden` 而不是消失），"读失败但已有数据"= `stale` + 旧结果照常显示 + 车道说明"…更新失败，保留上次结果。"，绝不会把失败画成空表或 0。

### 3.3 恒高槽与占位几何
`apps/frontend/src/read-region.css` 的 `.read-status` 固定 `height:var(--control-h)`（`ui.css:1` 为 `calc(32px * var(--fscale))`），因此六态之间车道高度不变；页面只给自己声明内边距变量（`.big-read-status` / `.settlement-read-status` / `.fees-read-status` 为 16px，`.users-read-status` / `.rules-read-status` / `.project-read-status` 为 0）。内容盒由 `.read-reserve{overflow:hidden}` + 页面 `min-height` 撑住：big 6 行、settlement 月表 8 行 / 提取 8 行、fees 6 行、users 8 行、rules 4 行、projects 8 行，行高来自共享 `.read-placeholder{grid-auto-rows:calc(38px * var(--fscale))}`。自然长页保持自然高度：`big`/`settlement`/`fees`/`AnnualTable` 原本就是 `domLayout:'autoHeight'`，本次没有改成固定高度一屏，占位只是首次未知时不塌陷。

### 3.4 查询身份切换不串旧明细
- `big.tsx`：按 `ym` 分月挂载，旧月 `<div hidden inert>`，切月只显示当月容器，别月数据不上屏；`useGridPresentation` 的 `scope`/`identity` 都用 `ym`。
- `settlement.tsx`：`Monthly` 用 `['settlement',ym]`，`Extract` 用 `['extract',year,status]`，占位判据只看当前 key 的 `data`；上一核算月的汇总行与表格在占位期间不再作为当月的数字出现。
- `fees.tsx`：保留既有 `ready = data.year===year && data.project===project` 作为唯一渲染门，错范围载荷既不渲染也不被当成"保留结果"（3.2 的 `stale && !ready → error`）。
- `projects.tsx` / `rules.tsx` / `users.tsx`：无查询身份维度（全量档案 / 全量规则 / 全量账号），切的是本地筛选，`rows` 由 `data` 派生，未知期间 `.result` 不出现（`test_read_ui.py:37` 依赖这一点）。

### 3.5 未动的写入链与权限门（逐项核过，不只是"表达式没改"）
去掉整页 `data-page-loading` 后，工具栏比原来更早可见，因此逐个核了它依赖的数据是否已就绪：

- `users.tsx`：`isAdmin = current?.role==='admin'`，`current` 来自 `data?.me` —— 数据未到时 `isAdmin` 为假，`转让管理员`/`＋ 新增账号` 天然禁用（实测表达式 :72-73）；行内 `disabled={!isAdmin}`、`disabled={!writable||!(isAdmin||self)}`、`lockAdmin(user)`（最后一个在用管理员不可停用/删除）全部原样；`writable = active && !blocked && Boolean(me)` 未改。`TransferDialog users={data?.users ?? []}` 只在 `isAdmin` 为真时可打开，而 `isAdmin` 需要数据，故不存在空名册可用的入口。
- `big.tsx`：`选择项目与排序…` 保持 `disabled={controlsDisabled || !!projectsError || !query.data}`（`!query.data` 就是"大表未读到"门）；导出 `disabled={controlsDisabled || !query.data?.rows.length}`；`controlsDisabled` 链未改。
- `settlement.tsx`：月表导出 `disabled={!query.data?.rows.length || query.isFetching || query.isError}`；提取导出 `disabled={!query.data || query.isFetching || query.isError || busy || dirty || uncertain}`；两者都比原来更严格或相同。
- `fees.tsx`：`disabled=blocked||!active||!me||uncertain||!ready||!query.data?.can_edit||query.isError`，`ready` 内含范围匹配，`can_edit` 来自后端权限位。
- `projects.tsx`：`unavailable = editableDisabled || inlineSaving>0`，`editableDisabled = blocked||!me||busy||projects.isError||projects.isPending`；导出另有 `||!rows.length` 与运行时 `项目列表尚未准备好，请稍候。` 兜底；`saveField`/`rereadField`/`changeStatus`/`move`/`exportRows` 一行未改。
- `rules.tsx`：`＋ 增加规则` 的 `!data` 门在数据未到时始终成立；两处输入行与"加入剔除名单"/行内"保存"仍是 `!writable||busy`。
- 草稿/列宽/金额：`useCellSaveQueue`（big / settlement extract / fees）用法未改，草稿比较与 `original` 语义未动；`useGridPresentation` 的 `table`/`scope`/`identity` 参数未改，所以"按账号+表持久化列宽""编辑期间保持实际列宽""合计行"都不受影响；金额展示仍走 `money()`。

### 3.6 保存/核对段落为什么保留
保存队列的 `error`/`uncertain` 段落是**写入语义**（回执丢失 → 结果待核实 → 必须人工核对），与读取状态不同源，所以没有并进读取车道，而是原位保留在车道之前：
- `big.tsx:153-156`：`{error && …待核实…重读核对}`、`{uncertain && …已核对，继续}`，`big` 的车道在其后 —— 这样 `.big-month` 内**第一条** `role=alert` 仍是保存队列那条（`tests/test_big.py:118-121` 断言其含"待核实"并点 `重读核对`）。
- `settlement.tsx:114-117` 与 `fees.tsx:104-105` 同理（`tests/test_fees.py:106` 点 `重读核对`）。

## 四、检查与未验项

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| TypeScript 全量类型检查 | `cd apps/frontend && ./node_modules/.bin/tsc --noEmit` | EXIT=0（改动前、改完后各跑一次，均 0）。中途有一次瞬时失败 `src/i8-browser-relay.ts(255,62): error TS2304: Cannot find name 'EMPTY_ROUND_MS'`，该文件是 476 并行写入中的未跟踪文件（23 秒后其常量已落地），与本票无关；紧随其后重跑 EXIT=0 |
| 共享读取单元测试 | `cd apps/frontend && node --import=tsx --test tests/unit/read-region.test.mjs tests/unit/cell-save.test.mjs` | EXIT=0，11 pass / 0 fail |
| 新 GUI 用例语法 | `backend/.venv/Scripts/python.exe -m py_compile apps/frontend/tests/test_report_maintenance_read_lanes.py apps/frontend/tests/test_preview.py` | EXIT=0 |
| `data-page-loading` 残留 | `grep -rn "data-page-loading" apps/frontend/src/` | 仅 `i8.tsx:154`（476）、`main.tsx:107`（禁改）、`page-surface.tsx:34`（判断方） |
| 旧文案残留 | `grep -rn "正在读取月度会大表\|正在读取收发结存\|正在读取库存年度汇总\|正在读取费用\|正在读取账号列表\|正在读取剔除规则\|正在读取集采项目剔除名单\|正在读取机械报表项目匹配\|重读待办\|重读留痕" apps/frontend/tests/` | 无命中（旧测试不依赖被替换的文案） |
| 单测注册表 | `node -e "…package.json scripts['test:unit']"` | 仍为既有 19 个文件清单；package.json 只读，未注册新单测文件 |
| 改动规模 | `git diff --stat`（本票 13 个已跟踪文件） | 13 files changed, 147 insertions(+), 36 deletions(-) |

新增行为例（`apps/frontend/tests/test_report_maintenance_read_lanes.py`，8 例，用 `test_preview.py` 的 `server`/`browser_page`/`login` fixture，走真实前端与真实后端只读接口，靠 `page.route` 挂起真实请求来观察"未知期间"）：

1. `test_big_month_read_keeps_its_lane_and_reserved_table_box` —— 挂起 `**/api/m07/big?*`：`.page-loading` 为 0 且月份筛选已可见；`.big-read-status [role=status]` 恰 1 条；`.big-read-reserve .read-placeholder` 恰 1 条；`.big-count` 为"正在读取项目数…"且不含"0 个项目"；`选择项目与排序…` 禁用。转 503 后：车道出现 `role=alert` + `重试读取`、状态字消失、占位转 quiet、车道高与占位盒 y 位移 <1px；点重试后占位消失、`.big-count` 含"个项目"、表格可见。
2. `test_settlement_month_read_failure_reports_in_place` —— 挂起 `**/api/m07/settlement?*`：汇总行不出现、占位在、失败后 `role=alert`+重试+quiet、盒位不变、重试后汇总行出现。
3. `test_settlement_switching_the_month_drops_the_previous_month` —— 先等首月表就绪，再把核算月改到 `2020-01`：旧月汇总行立刻消失、车道开始播报，放开后汇总行出现且含 `2020-01`。
4. `test_settlement_extract_read_failure_is_not_an_empty_year` —— 切到"焊材 / 气体提取"，`**/api/m07/extract-screen?*` 恒 503：车道 `role=alert`+重试、占位 quiet、`焊材年度汇总` region 不出现（失败不被画成空年）。
5. `test_fees_switching_the_year_keeps_no_previous_amounts` —— 挂起 `**/api/m09/fee/year?*` 后把年份改到 2020：`特殊费用年度表` 不出现、车道播报、占位在、`增加手填项` 禁用；放开后表出现、占位消失。
6. `test_users_list_reports_its_own_read_and_gates_the_actions` —— 挂起 `**/api/m15/users`：`.page-loading` 为 0（整页不再被读挡住）、车道播报、`.users-count` 不出现（不显示 0）、`.users-table`（非占位）不出现、`＋ 新增账号` 禁用；503 后 `role=alert`+重试；重试后计数出现。
7. `test_rules_blocks_read_independently_and_report_in_place` —— `**/api/m14/rules` 恒 503：三块都在，只有第一块出车道与占位，另两块无占位（各自读各自报），`＋ 增加规则` 禁用；重试后占位消失。
8. `test_projects_first_read_publishes_the_page_and_keeps_the_list_box` —— 挂起 `**/api/m01/projects?status=all` 后 reload：`.page-loading` 为 0、车道播报、占位在、`项目搜索` 可用（筛选先发布）、`.projects-page .result` 不出现、`导出 Excel` 禁用；503 后 `role=alert`+重试且 `.result` 仍不出现、盒位不变；重试后 `.result` 与 `.project-table` 出现。

未验项（据实列出，不计为通过）：
- **上述 GUI 用例一次都没有运行过**。执行边界禁止在本会话起 vite/HTTP/浏览器/真实 i8，只做了 `py_compile` 语法检查；它们的真实通过需要主控在登记真实副本上跑（见第六节）。
- 因此 `.users-read-status` / `.project-read-status` 的实际渲染高度、占位盒与成功表格的像素级衔接、以及在真实缩放（`ui_scale_css`）下的间距，都只是按共享 CSS 推演，未经视觉确认。
- `projects.tsx` 两个待办列表在真实数据下"有内容时是否仍与原来同位置"未在浏览器观察（逻辑上是 `.project-pending-region` 恒在、内部按需加车道）。
- 未做任何真实 i8 抓取、业务写入、导出、启停、部署、Git 提交或推送。

## 五、共享机制建议（交主控串行处理）

1. `ReadFailure` 的按钮文案固定为"重试读取"，而各页原有"重读项目/重读待办/重读留痕/重读核对"文案随之消失。本票已同步 `tests/test_preview.py:98`。若主控希望保留页面化文案，最小改法是给 `ReadFailure` 增加可选 `retryText`（共享文件，非本票可改）。
2. `page-surface.tsx` 的 `[data-page-loading]` 判断是"整页硬门"。现在只剩 `i8.tsx`（476）与 `main.tsx` 的 Suspense fallback 携带它；建议整轮结束后由主控核一次全局 `grep`，并把该属性收敛为"仅路由级兜底"语义，避免后续页面再误用成读取态。
3. `main.tsx` 的 QueryClient 已设 `retry:false`（`apps/frontend/src/main.tsx:69`），所以失败页不会自动重试、必须人工点"重试读取"——这与规格"不自动重试"一致，建议作为共同前提写进 spec 备注。
4. `users.tsx` 的 `TransferDialog users={data?.users ?? []}` 在数据缺失时会拿到空名册。当前仅管理员可开、管理员身份来自数据，故实际不可达；若将来把入口挪到不依赖数据的位置，需要在对话框内补"名册尚未读取"提示（共享改动，本票未动）。

## 六、真机验证代表清单（由主控在登记真实副本执行）

| # | 入口 | 操作 | 期望 |
| --- | --- | --- | --- |
| 1 | `/preview/big` | 进入后在月份读返回前观察 | 筛选（核算月）先可用；一行状态槽在播报；表格区域预留且不显示"0 个项目"；`选择项目与排序…` 禁用 |
| 2 | `/preview/big` | 让该月读取失败（DevTools 离线/断开一次） | 状态槽内出现一行告警 + "重试读取"；网格区域不消失、不跳动；项目数显示"项目数尚未读取"；点重试恢复 |
| 3 | `/preview/settlement` | 切核算月到另一月 | 旧月汇总行与表格立即让位（不显示为当月数字）；新结果到达后再出现；列宽与合计行保持 |
| 4 | `/preview/settlement` → 焊材 / 气体提取 | 切年份并让读取失败 | 两套自然高度表不出现（不冒充空年），状态槽报错可重试；恢复后表与合计行自然展开 |
| 5 | `/preview/fees` | 挂起后切年份/项目 | 旧范围金额不留在屏上；状态槽播报；`增加手填项` 禁用；恢复后表出现且列宽仍按账号持久化 |
| 6 | `/preview/users` | 首次进入（读挂起） | 页面框架与标题先出现、不再"整页正在读取"；无"（在用 0…）"假计数；`＋ 新增账号`/`转让管理员` 禁用；失败后一行告警可重试 |
| 7 | `/preview/rules` | 让剔除规则读失败 | 三块独立：只有第一块出占位与告警，另两块照常显示；`＋ 增加规则` 禁用；重试后恢复且"已更新"回执样式照旧 |
| 8 | `/preview/projects` | 首次进入读挂起 | 筛选/搜索先可用；`共 N 个项目` 不出现（不冒充 0）；导出禁用；失败后一行告警可重试、列表区域不塌陷 |
| 9 | `/preview/projects` | 正常进入后拖拽排序 + 改字段 + 导出 | 与改动前一致（行序、草稿、导出行集） |
| 10 | 任一带保存队列的页面（big/settlement 提取/fees） | 制造一次回执丢失 | 保存队列"待核实"告警仍在读取车道**之前**出现，`重读核对` 可点，`已核对，继续` 生效 |

外部动作熔断：以上全部为只读观察与界面操作；不触发真实 i8 抓取、不落业务写入、不导出到正式目录、不改权限、不启停服务。

## 七、覆盖清单（全站同类读取区域归属）

| 区域 | 归属 | 处置 |
| --- | --- | --- |
| `big.tsx` 月度大表 / 项目清单 | TAIL-481 | 已接入（车道 + 占位 + 保留） |
| `settlement.tsx` 收发结存 / 库存年度汇总 | TAIL-481 | 已接入（两块各自车道） |
| `fees.tsx` 年度费用 / 项目清单 | TAIL-481 | 已接入（含错范围降级） |
| `projects.tsx` 档案 / 两个待办 / 留痕 | TAIL-481 | 已接入（四块各自车道）；删除/同步对话框内的小读保持原"核对影响…/重读影响"实现（模态内单次读，不属于页面框架+数据分区） |
| `rules.tsx` 三块 | TAIL-481 | 已接入（三块独立） |
| `users.tsx` 账号列表 | TAIL-481 | 已接入，并去掉 `data-page-loading` |
| `i8.tsx` / `i8.css` | **TAIL-476** | **排除**：按主控指示转归 476（含本地执行记录加载），本票未改；其 `data-page-loading`（`i8.tsx:154`）仍在 476 的范围内 |
| `history.tsx` 操作历史（`HistoryControls`） | 站点顶栏，非本票页面 | 无需改：`main.tsx:100` 渲染在 `.account-area`，不承载页面框架与数据分区；文案已是"操作历史未能读取。"+ `重读核对`，诚实且可达，未见整页遮挡 |
| `ledger.tsx` 台账 | TAIL-477（样板） | 无需改：自有 `.ledger-content` + `retainedHeight` + `aria-busy` 布局，语义等价 |
| `notices.tsx` / `inventory.tsx` / `flow.tsx` / `process.tsx` / `mechanical.tsx` / `contracts.tsx` / `contract-subtables.tsx` / `oilcard*.tsx` | 478 / 479 / 480 | 只读，未改（已各自接入共享车道） |
| 模态内单次读：`contract-dialog.tsx:85`、`notice-contract.tsx:118`、`notice-flows.tsx:17`、`notice-maintenance.tsx:92`、`notice-print.tsx`、`inventory-fetch.tsx:45`、`contract-tools.tsx:42`、`oilcard-receive.tsx:97`、`oilcard.tsx:201`、`payment-terms.tsx:15`、`appearance-preferences.tsx:99`、`flow-revoke.tsx:36` | 各自票（478/479/480）或非本票共享文件 | 无需改（本票写域外）：均为弹窗/单元格/偏好面板内的单次读，没有"框架先发布 + 数据分区"结构，现有"正在读取…/重读…"已按状态区分且失败可达；如主控要求统一，应作为共享机制后续项串行处理 |
| `main.tsx:107` Suspense fallback、`page-surface.tsx:34`、`read-region.*` | 共享/禁改 | 只读 |
