# TAIL-478 通知书／库存／付款流水／首页加载接入 · 实施与验证证据

- 票：[TAIL-478 通知书库存流水加载接入](../../tails/issues/TAIL-478-通知书库存流水加载接入.md)
- 共同规格：[spec.md](../spec.md)
- 复用样板：[TAIL-477.md](./TAIL-477.md)、[TAIL-477-acceptance.md](./TAIL-477-acceptance.md)、[TAIL-479.md](./TAIL-479.md)
- 工作树：`D:\\dev\\mtrl-workbench\\var\\worktrees\\browser-session-loading-20261104`
- 分支／基点：`codex/browser-session-loading-20261104` / `9efebc87`（累计起点 `22cc48f8`）
- 记录时间：2026-11-04（本地时间；浏览器时区不可用，未做时区换算）
- 本文档分两轮：第二轮（本节 §一、§二、§三、§五）是主控要求的共用呈现整合，覆盖第一轮的结论。

## 一、结论摘要

### 1.1 第一轮：四页各自的读取分区

477 在 `apps/frontend/src/read-region.tsx` 提供六态判定（`readPhase`）、无值占位（`ReadPlaceholder`）、原位失败 + 重试（`ReadFailure`）与 `.read-announce`，并在欠款汇总做出「网格之前的恒高状态槽」。本票不复用欠款的**形状**（`.debt-overviews` 三卡 + 8 行骨架是欠款页几何），只复用**实际适用的机制**：六态判定、无值占位（行条不含金额/条数/百分比）、原位失败 + 重试、恒高状态槽、旧结果保留并说明更新未成功。

四个页面各自的读取门改成「框架/工具先可用，数据区自行报告」，金额、权限、字段、排序、合计、导出、保存、撤销、列宽、字号主题、滚动策略、查询身份、草稿生命周期、付款弹窗与业务提交链均未改写；没有新增轮询、缓存时长、延迟、自动重试、键盘增强或风格重做。

### 1.2 第二轮：共用呈现收敛（主控整合）

第一轮把「恒高槽」的 CSS 在四个页面各写一份、把 `read-region` 的共享呈现留在 `flow.css` 里，并且为了迁就一条过期断言保留了库存页「仅因自身数据 pending 就整页不发布」的旧门。第二轮逐条修正：

1. **共享呈现独立成文件并由组件自己加载。** 新增 `apps/frontend/src/read-region.css`，`apps/frontend/src/read-region.tsx:1` 直接 `import './read-region.css'`。这样**不是**靠 `styles.css` 的 `@import` 顺序（那是主控写域），而是靠模块图：任何页面 import `read-region` 就必然加载这套样式。现有 **13 个消费者**（见 §5.1）全部自动生效。
2. **六处重复的恒高槽收敛成一套共享 class + 一个小组合组件。** 新增 `ReadStatusLane`（`read-region.tsx:67`），渲染 `.read-status` + 页面追加 class，槽的几何（恒高、flex 并列、文本截断、按钮不裁）全部由 `read-region.css` 提供；页面只剩两个变量：`--read-status-inset`（槽在区域内缩进）与 `--read-status-pad`（notice 内缩进）。八个消费点已切换（欠款、通知书、库存、流水统计、流水列表、过程、机械、首页），页面 CSS 里对应的重复规则已删除。
3. **同槽多条失败可辨认、各自重试、按钮不被裁。** `ReadFailure` 增加可选 `label`（`read-region.tsx:84`），消息渲染为 `项目清单：…`；`.read-status>.notice{flex:1 1 0}` 让同槽两条失败**并排等分**（不是两行），`.read-status>.notice>.ant-btn{flex:none}` 保证两个「重试读取」都不会被 `overflow:hidden` 裁掉。此前只有 477 的欠款槽有按钮不收缩规则，其余三处没有。
4. **流水页的 `projectQuery` 失败从流内行移进稳定槽**（`flow.tsx:144`），不再在已有结果刷新失败时推移表格；判据不再是「行数」而是「read 自己的 `readPhase`」。
5. **库存页移除旧整页门。** `inventory.tsx:98` 的 `data-page-loading` 已删除，工具区在自身数据读取期间即可用；`page-surface.tsx:34` 的发布门仍保留（它只等 `[data-page-chrome]` 字体 + 页内是否还有 `data-page-loading`），身份/权限/字体就绪约束一条未动。
6. 为不破坏既有断言，改造过程中**保留了原有 class 名**（如 `.notice-read-status`、`.process-read-status`、`.debt-overviews-status` 依旧是元素 class 列表中的一项），既有测试选择器继续命中；只把新几何的归属搬到共享文件。

## 二、修改清单

### 2.1 共享呈现层（本轮新增／修改）

| 文件 | 类型 | 内容 |
|---|---|---|
| `apps/frontend/src/read-region.css` | **新增（35 行）** | `.read-announce`（sr-only，不占可见行）、`.read-placeholder`（`grid-auto-rows:calc(38px*var(--fscale))`，`>span` 7px 高、`nth-child(2n)` 72%／`(3n)` 88%、pill、`--sf2`）、`.read-placeholder-quiet>span{visibility:hidden}`、`.read-reserve{overflow:hidden}`、`.read-status`（`display:flex;align-items:stretch;gap:6px;height:var(--control-h);margin:0;padding:0 var(--read-status-inset,0);overflow:hidden;flex:none;min-width:0`）、`.read-status>.notice`（`flex:1 1 0`、`min-width:0`、`flex-wrap:nowrap`、`padding:0 var(--read-status-pad,10px)`、`font-size:12px`、`line-height:1.4`、`border-radius:var(--radius-card)`、`overflow:hidden`）、`.read-status>.notice>.read-failure-text`（单行省略号）、`.read-status>.notice>.ant-btn,.read-status>.ant-btn`（`flex:none` + 紧凑尺寸）。注释里写明：槽在 idle/reading/ready/empty/error/stale 六态都在；一个区域两条 read 在同一槽并排；页面只提供两个变量。 |
| `apps/frontend/src/read-region.tsx` | 修改（+23/−2，92 行） | `:1` 新增 `import './read-region.css';`；`:67` 新增导出 `ReadStatusLane({phase, announce, className, children})` → `<div className={className?`read-status ${className}`:'read-status'} data-read-phase={phase} aria-busy={phase==='reading'||undefined}>{children}{phase==='reading'&&<p className="read-announce" role="status">{announce??'正在读取…'}</p>}</div>`；`:84` `ReadFailure({read, retained, label})`，新增 `label?: string`，消息为 `{label?`${label}：`:null}{note}{read.error?.message}`。`readPhase`／`ReadPlaceholder`／`ReadState` 的既有行为与文案未改。 |

### 2.2 八个消费点的迁移（状态槽 class 与对应 CSS）

| 页面 | 文件 | 内容 |
|---|---|---|
| 欠款（477 已验） | `flow.tsx:53`、`flow.css` | 槽容器换成 `ReadStatusLane`，`className="debt-overviews-status"` 保留（`test_debt_loading.py:149` 仍命中）；`flow.css` 里 477 的 `.debt-overviews-status` 几何规则删除，改由共享层提供；欠款卡片几何（`.debt-overviews*`、`.debt-overviews .flow-card-body`、`.debt-overviews .flow-bars`）逐字未动。 |
| 通知书 | `notices.tsx:243-244`、`notices.css:72-76` | 槽换 `ReadStatusLane`（`className="notice-read-status"`），槽内两条 `ReadFailure`：本列表 `query`（`stale` 时 `retained='列表更新失败，保留上次结果。'`）与次要 `projects`（`label="项目清单"`）；原先槽外那行 `projects.isError`（第 250 行附近，在表格之后）已删除，能力（原位 + 自己的重试）保留。占位 div 追加 `read-reserve`。CSS 只剩 `.notice-read-status{--read-status-pad:calc(13px*var(--fscale))}` 与 `.notice-read-reserve{padding:8px 13px}`。 |
| 库存 | `inventory.tsx:98/116-117`、`inventory.css:53-57` | `:98` **移除** `data-page-loading`；槽换 `ReadStatusLane`（`inventory-read-status`），槽内两条 `ReadFailure`（`query` 的 `retained='读取更新失败，保留上次读取的内容。'`、`projects` 的 `label="项目清单"`），原槽外 `projects.isError` 行删除；占位追加 `read-reserve`。CSS 只剩两个变量/内边距。`controls.current.unavailable`（含 `query.isFetching`、`presentation.state==='updating'`）、`reload()` 逐字未改。 |
| 流水统计 | `flow.tsx:135-136`、`flow.css:70-77` | 槽换 `ReadStatusLane`（`flow-read-status payment-stats-status`）；占位 `.payment-stat-reserve read-reserve`；CSS 保留 `.payment-stats>.flow-card-body{display:flex;flex-direction:column}`、`.payment-stat-columns{height:auto;flex:1 1 auto;min-height:0}`、`.payment-stat-reserve{flex:1 1 auto;min-height:0;padding:8px 16px}`。卡片外框高度仍是 `clamp(200px,27dvh,300px)`，未改。 |
| 流水列表 | `flow.tsx:144-145` | 槽换 `ReadStatusLane`（`flow-read-status flow-list-status`），槽内两条 `ReadFailure`：`flows`（`stale` 时 `retained='流水更新失败，保留上次结果。'`）与 **`projectQuery`（`label="项目清单"`）——从流内行移入**；槽外旧的「重读项目」行已删除。占位 `.flow-grid .flow-read-reserve read-reserve`。`writable`（含 `!flows.isFetching`）、导出按钮 disabled、`exportFlows`、`chooseProject`、通知书定位滚动 effect、`presentation` 参数逐字未改。 |
| 首页 | `home.tsx:5/24-38`、`home.css:17-25` | 槽换 `ReadStatusLane`（`home-read-lane`）；`data-page-loading` 保持已移除；三张 tile 恒渲染，数字槽 `counted ? 真实数字 : .home-tile-count-reading > span`（不写 0）；CSS 只剩 `.home-tile-count-reading`（保持 28px×1.2 行高）、其 `span`、`.home-read-lane{--read-status-pad:0}`、`.home-updating`。 |
| 过程（479 输入） | `process.tsx:168-171`、`process.css:60-62` | **机械迁移**：原 `.process-read-status` div 换成 `ReadStatusLane`（class 名保留），`data-read-phase`/`aria-busy` 语义由组件等价产生；槽内两条 `ReadFailure`（`query`、`projects` 带 `label="项目清单"`）内容不变；CSS 只留 `.process-read-status{--read-status-inset:calc(16px*var(--fscale))}`。**479 的数据/保存/核对逻辑一行未动。** |
| 机械（479 输入） | `mechanical.tsx:294-297`、`mechanical.css:24-26` | 同上，机械迁移；槽内 `state` 与 `projects` 两条失败不变；CSS 只留 `--read-status-inset`。**479 的报表/保存/待核实逻辑一行未动。** |

### 2.3 测试

| 文件 | 类型 | 内容 |
|---|---|---|
| `apps/frontend/tests/unit/read-region.test.mjs` | 修改（+49/−1，110 行，8→10 例） | 顶部用 `node:module` 的 `registerHooks` 把 `.css` 解析成空模块、把 `antd/es/button` 解析成 `p=>p.children`（tsx 不做 CSS 变换，也不解析 AntD 的 ESM 入口，见 §4.1）；`read-region.tsx` 改为动态 `await import`。新增两例：`a lane is present in every state and only speaks while it is reading`（idle/ready 不说话、reading 恰好一条 `role=status`，三态都有 `read-status` 与 `data-read-phase`）；`two failed reads in one lane stay apart, each naming itself and retrying itself`（同槽两条失败同时渲染、`项目清单：` 前缀可辨、两处「重试读取」）。 |
| `apps/frontend/tests/test_startup_styles.py` | 修改（+40/−9） | 删除**过期**的 `test_inventory_waits_for_its_own_first_reads`（原来要求 `.page-loading` 含「库存」且「库存核算期间」按钮藏起来），替换为两条覆盖新预期、但不放宽业务断言的行：`test_inventory_tools_publish_while_its_own_first_read_is_pending`（页面已发布、工具栏可点、数据区占位、`[role=grid]` 为 0、计数文案「尚未读取」而不是 0 行、槽 `data-read-phase=reading` 恰一条 status；放行后 status/reserve 归零、`aria-busy=false`、计数匹配 `^\d+ / \d+ 行$`）与 `test_inventory_tools_publish_while_the_project_list_is_pending`（次要依赖挂起时页面仍发布、期间按钮可点、表格最终可见）。 |
| `apps/frontend/tests/test_read_lanes.py` | 新增（189 行，6 例，第一轮已交付） | 选择器在收敛后**无需改名**（旧 class 名保留；`.notice-read-status [role=status]` 现在由共享 `read-announce` 提供）。 |

未触碰：`grid-presentation.tsx`、`grid-layout.ts`、`page-surface.tsx`、`main.tsx`、`styles.css`、`ui.css`、`style.css`、`package.json`、`notices-api.ts`、`flow-api.ts`、`inventory-api.ts`、`notice-payment.tsx`（付款弹窗）、`notice-print.tsx`、`notice-fetch.tsx`、`ledger.tsx`、`DebtPage` 的业务渲染（`flow.tsx:36-68` 只换槽容器）、后端、共享规格、票状态、索引、Git。

## 三、控制与数据流依据

### 3.1 首帧门控（page-surface 的硬规则）

`apps/frontend/src/page-surface.tsx:34`：`if (node!.querySelector('[data-page-loading]')) return;` —— 页内只要还有任何 `[data-page-loading]` 后代，PageSurface 就不发布首帧（`.page-view` 保持 `visibility:hidden` + `inert`，并显示 `.page-loading`）。`:25-26` 的注释明确写「These pages own their table boundaries; only their existing tool areas contribute to the page's first font preparation. **Data reads stay parallel.**」

因此本票的处理是：

- `flow.tsx`、`home.tsx`、`inventory.tsx` 三页**都不再有** `data-page-loading`：原来它把数据读取挂在整页首帧上，与上述边界直接冲突（`main.tsx:106` 的 Suspense fallback 已负责路由分包首帧）。
- `notices.tsx` 本来就没有，保持不加。
- **第一轮曾为迎合 `test_startup_styles.py:202-216` 而保留库存页的 `data-page-loading`，理由是「既有断言已锁定该行为」。第二轮确认该理由不成立**：那条断言描述的是本票要修的旧行为（整页等待自身数据），共同规格要求工具框架与数据区分区加载，测试不覆盖新要求。处理方式是按实际门控源码移除该属性、把过期断言改写成新预期，而不是删用例或放宽业务断言（见 §2.3）。
- 全站剩余 `data-page-loading` 只在 `i8.tsx:57`、`rules.tsx:115/184/231`、`users.tsx:64`、`main.tsx:106`（Suspense fallback）——非本票写域，未动。

### 3.2 六态判定与「不冒充」

四页统一用 `readPhase()`，不自写 `isPending/isError` 组合：

- `reading`（`isPending && isFetching`，`data===undefined`）→ 槽内只有 sr-only `read-announce`，数据区放 `ReadPlaceholder`（`aria-hidden`，无金额/条数/百分比）。没有新增延迟或最短展示时间，占位本身就是纯空间。
- `error`（失败且无历史数据）→ `ReadFailure` + `重试读取`，占位切 `quiet`（保留空间但不说仍在读取）；**不写成空态**。
- `stale`（失败但有历史数据）→ `ReadFailure` + `retained` 文案，旧结果留在位上。
- `empty`／`ready` → 真表格；`empty` 的空态仍由既有 `overlayNoRowsTemplate` 表达（「当前筛选条件下没有付款通知书…」／「当前筛选条件下没有库存单据」／「当前筛选没有付款流水。」），未新增第二种空态文案。

**「不显示错误范围数据」**：`stats` 的 queryKey 含 `gran/year/quarter/bucket`，`flows` 是固定 key + 本地 `filter`。切统计窗口＝新 key，`stats.data` 为空 → `statsPlaceheld` 为真 → 统计区显示占位而不是上一窗口的金额。切流水筛选只改本地 `filter`，`flows.data` 不变，不触发读取，也不隐藏已显示的表格。

### 3.3 一套槽如何不推移、不遮挡

共享槽（`read-region.css`）在所有阶段都占 `var(--control-h)`（`ui.css:1`：`calc(32px * var(--fscale))`），空/读取/失败三态同高；长文案单行省略号截断而不换行增高；「重试读取」按钮 `flex:none` 常驻可点。**样式的归属不再分散：**

```
.read-status{display:flex;align-items:stretch;gap:6px;height:var(--control-h);margin:0;padding:0 var(--read-status-inset,0);overflow:hidden;flex:none;min-width:0}
.read-status>.notice{flex:1 1 0;min-width:0;…;flex-wrap:nowrap;padding:0 var(--read-status-pad,10px);…}
.read-status>.notice>.read-failure-text{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.read-status>.notice>.ant-btn,.read-status>.ant-btn{flex:none;…}
```

各区域仍靠既有布局规则避免挤压表格（这些规则一条未改）：

- 通知书：槽是 `.notice-card` 的直接子元素且不是 `.notice-grid`，命中 `ui.css:71` 的 `.workspace .page-view .notice-card>:not(.notice-grid){flex-shrink:0}`，不参与表格的 `flex:1 0 calc(240px…)` 分配。
- 库存：槽在 `.inventory-summary` 之后、网格之前，`.inventory-page` 是 `flex-direction:column`（`ui.css:68`），`>:not(…grid…){flex-shrink:0}`（`ui.css:69`）保证不挤压网格。
- 流水：槽是 `.flow-list` 子元素，命中 `flow.css:66` 既有 `.flow-list>:not(.flow-grid){flex:none}`，`.flow-list>.flow-grid{flex:1 0 calc(280px…)}` 不变。
- 统计：`.payment-stats>.flow-card-body` 外框高度仍是 `clamp(api)` 值；只把它改成 `display:flex;flex-direction:column`，槽 `flex:none`、占位/列区 `flex:1 1 auto`，故内部换态不改卡片外框。
- 首页：槽在 `.home-todos` **之后**，槽内文案变化不移动三张 tile；tile 数字槽在读取中保持同一行高。
- 过程/机械：`.process-read-body`／`.mechanical-read-body` 的 `flex:1 1 auto;min-height:0` 与槽的 `flex:none` 配合，表区不变（479 已验的 toolbar y 不变仍成立）。

### 3.4 保留下来的门控（刻意不改）

- `notices.tsx:96` `unavailable = … || query.isPending || query.isError || query.isFetching`：**保持不变**。它同时是付款／批量打印／工具／导出／保存草稿的禁用真源，`batchUnavailable = unavailable || !picked.size || hidden > 0`。刷新期间旧行仍在屏上，若此时开放付款就是在「可能已被替换的行集」上下单；票验收第 3 条要求保通知书选择／付款保护，因此本票只改「读什么、在哪报告」，不放宽可操作窗口。
- `inventory.tsx` 的 `controls.current.unavailable`（含 `query.isFetching`、`presentation.state==='updating'`）未改：调整单入口在刷新期仍关闭。
- `flow.tsx` 的 `writable`（含 `!flows.isFetching`）与导出按钮 disabled 未改：撤销在刷新期仍关闭。
- `notices.tsx` 的焦点 effect 仍等 `!query.isFetching`（定位必须等数据换完）；另一处仍等 `presentation.state==='ready'`。
- 写后重读链（`notices.tsx refresh()`、`inventory.tsx reload()`）逐字未改。
- 保存/未知回执类提示（`notices.tsx` 的 warning／error／draftUncertain／draft、`mechanical.tsx` 的 `needsRead`／`saves.error`／`saves.uncertain`／`process.tsx` 的 `error`／`uncertain`）**全部留在原位**，没有并入读取槽——它们不是读取状态。

### 3.5 「重读不卸载表格」

`grid-presentation.tsx` 的 `visible = !concealed && state!=='preparing' && state!=='error'`，而 `grid-layout.ts:286` 的 `concealed` 只在 `identity` 变化时为真。因此同条件重读时 `state='updating'` 但 `visible` 仍为真 —— 已发布的表格不会被隐藏。

本票的占位分支只在 `placeheld`（`idle|reading|error`，即**尚无数据**）时替换表格，所以：

- 首次读取 → 占位；数据落地 → 挂载 `PreparedGrid`（先 `preparing` 隐藏，随后 `ready`）。
- 同条件重读（`isFetching && data` 存在）→ `placeheld` 为假 → **表格保持挂载**，编辑器、焦点、滚动都不受影响（对应 `apps/frontend/tests/test_read_ui.py:47-69` 要求重读期间 `pay_amount='321.09'` 与焦点保持）。
- 重读失败（`stale`）→ 仍然 `placeheld` 为假 → 旧表格留位，只多一条 `ReadFailure`。

### 3.6 首页共享通知书缓存

`home.tsx:11` 与 `notices.tsx` 使用同一 `['notices']` queryKey 且都是 `refetchOnMount:'always'`。首页因此不需要自己的读取组件：同一个缓存条目、同一份 `readNotices` 归一化逻辑（`live()` 过滤在页面内本地计算），本票只把「这份读取的状态」从「整页隐藏 + tile 消失」改成「tile 恒在 + 数字槽留空 + 槽内报告」。tile 计数仍由同一行集本地过滤得出（`TAIL-421` 约束：tile 数等于深链落地行数），未引入新的计数来源。

## 四、验证

### 4.1 已执行（本机源码树，全部记录原始退出码）

| 命令 | 结果 |
|---|---|
| `cd apps/frontend && ./node_modules/.bin/tsc --noEmit` | **EXIT=0**（最后一轮：CSS 收敛、`read-region.css` 归一为 CRLF 之后） |
| `cd apps/frontend && node --import=tsx --test tests/unit/read-region.test.mjs` | **EXIT=0**，`tests 10 / pass 10 / fail 0` |
| `cd apps/frontend && npm run test:unit`（19 个文件） | **EXIT=0**，`tests 94 / pass 94 / fail 0` |
| `cd apps/frontend && python -m py_compile tests/test_startup_styles.py tests/test_read_lanes.py` | **EXIT=0** |
| `git diff --numstat`（本票相关 15 个已跟踪文件） | 见 §7 |
| `git status --porcelain` | `?? apps/frontend/src/read-region.css`、`?? apps/frontend/tests/test_read_lanes.py` |

过程记录与偏差（保留教训）：

- 仓库工作树是 **CRLF**（`core.autocrlf=true`，HEAD blob 为 LF）。用 bash heredoc／python 写文件曾产生混行（`flow.tsx`／`flow.css`／`home.tsx`／`read-region.tsx`／`read-region.css`），已全部归一为 CRLF 并复跑 `tsc` 与单测；归一后 `read-region.tsx` 92 CRLF / 0 LF-only、`read-region.css` 35 CRLF / 0 LF-only。
- **`tsx` 4.23.15 不处理 `import './x.css'`**（`SyntaxError: Unexpected token '{'`）。`src/assets.d.ts` 的 `declare module '*.css'` 与 `src/vite-env.d.ts` 的 vite/client reference 让 `tsc --noEmit` 与 `vite build` 都正常，但 node+tsx 单测会崩。解决方式写在 `tests/unit/read-region.test.mjs` 里（`registerHooks` 把 `.css` 解析为空模块），**没有改 `package.json`**（那是主控写域）。
- 同一单测里 `antd/es/button` 也必须 stub（tsx 不解析 AntD 的包内 ESM 入口，真模块会让 `renderToStaticMarkup` 报 `Element type is invalid`）；stub 成 `p=>p.children` 后，断言只针对「谁说了什么」，不针对 AntD。
- 中途 `tsc` 报过 `src/notices.tsx(30,10) TS6133`（引入未用，与 `noUnusedLocals` 冲突）、`home.tsx` 遗留未用 `Button` import，均在同轮修正。
- 一次全量 `tsc` 曾报 `src/oilcard.tsx(175,9): error TS6133: 'archivePhase'`，`grep` 该符号在文件中**已无出现**；紧接着复跑 `tsc` 即 `EXIT=0`。视为同工作树并行写入（油卡页由 480 会话编辑）期间的瞬时读到中间态，**不是本票改动导致**；因该文件不在本票写域，未介入修改。主控构建前请在稳定窗口复跑一次。

### 4.2 新增／调整的具名行为检查

**单元层（本会话已运行，`read-region.test.mjs` 10 例）**：六态判定 5 例（未获准读／首读中／有行与无行／首读失败不是空表／失败后保结果）＋ 占位 2 例（sr-only 宣告、占位不含金额/条数/百分比、失败占位保留空间不说在忙）＋ 槽 2 例（六态都在、只有 reading 时说话；同槽两条失败并排、各自命名、各自重试）＋ 1 例既有。

**GUI 层（本会话未运行，见 §4.3/§6）**：`apps/frontend/tests/test_read_lanes.py` 6 例（第一轮交付，选择器在收敛后仍有效）＋ `test_startup_styles.py` 两条改写后的库存用例。逐条意图：

1. `test_notice_list_keeps_its_reserved_box_while_the_first_read_lands` —— 挂起 `**/api/m03/notice-list?*`：搜索框可点可聚焦；槽内 `role=status` 恰 1；`.notice-read-reserve .read-placeholder` 恰 1；`region[name=付款通知书列表]` count 0；记录 `.notice-grid` 框；放行后 region 可见、框**完全相等**、槽清空、占位消失、搜索仍聚焦。
2. `test_notice_list_failure_reports_in_place_and_is_not_an_empty_list` —— 首读 503：槽内 `.notice[role=alert]` + 「重试读取」；无 `role=status`；region count 0；`.read-placeholder-quiet` 恰 1；`.notice-grid` 的 y 与 height 变化 <1px。
3. `test_inventory_first_read_failure_is_reported_in_place` —— `**/api/m08/inventory` 503：`.page-loading` count 0；槽内 alert + 「重试读取」；`.inventory-count-feedback` 为「尚未读取」（**不冒充 0 行**）；`.inventory-grid.inventory-read-reserve` 存在；解除后点重试 → `aria-busy=false`、占位消失、框不变。
4. `test_flow_statistics_and_flows_publish_independently` —— 同时挂起 stats 与 flows：两条槽各有 1 个 `role=status`、两处占位各 1、`流水关键词` 可输入；先放统计 → `.payment-stat-columns` 可见、统计占位与状态清空而流水占位仍在；再放流水 → `aria-busy=false`、占位与状态清空、`.flow-grid` 框不变。
5. `test_flow_statistics_failure_reports_in_place_without_moving_the_list` —— 就绪后点「按月」（新 queryKey）：统计槽 alert + 「重试读取」；无 `role=status`；`.payment-stat-reserve .read-placeholder-quiet` 恰 1；**`.payment-stat-columns` count 0**（不显示上一窗口金额）；`.flow-grid` 仍 `aria-busy=false` 且框不变。
6. `test_home_keeps_its_tiles_while_the_todo_read_is_in_flight` —— 挂起 `**/api/m03/notice-list?*` 进首页：`.home-todos` 可见、`.home-tile` 恰 3、`.home-tile-count-reading` 恰 3（**读取中不写 0**）、槽内 `role=status` 恰 1；放行后占位 0、状态 0、首个 `.home-tile-count` 匹配 `^\d+$`、`.home-todos` 框不变。
7. `test_inventory_tools_publish_while_its_own_first_read_is_pending`（新）—— 挂起 `**/api/m08/inventory`：`.page-loading` 0、`.page-view:not([hidden])` 可见、「库存核算期间」可见且可点、「列筛选」可点、`.inventory-grid.inventory-read-reserve` 可见、`.inventory-grid [role="grid"]` 0、计数「尚未读取」、槽 `data-read-phase=reading` 且 1 条 status；放行后 status/reserve 归零、`aria-busy=false`、计数匹配 `^\d+ / \d+ 行$`。
8. `test_inventory_tools_publish_while_the_project_list_is_pending`（新）—— 挂起 `**/api/m01/projects`：`.page-loading` 0、期间按钮可点、项目选择器可见、表格最终可见。

### 4.3 本会话无法执行、必须由主控在原登记环境跑

- 上述 GUI 用例：本会话 `python -c "import playwright"` → `ModuleNotFoundError: No module named 'playwright'`（当前 Python 未装 playwright；按票不安装、不启停预览服务、不访问 HTTP/浏览器）。
- 任何 GUI 实看、真实副本四页的加载全过程与「编辑保存读回」（票验收第 4 条代表场景）。按约定统一由主控构建真实副本后执行，本会话未 `vite build`。
- 真实 i8 抓取、正式付款、任何业务写入：**未执行**（票执行边界要求熔断）。

### 4.4 既有断言的风险点（需主控在真实浏览器确认）

1. `test_startup_styles.py` 的 notices 用例（`:150`）`assert table.bounding_box() == before`：本票路径是「占位 div `.notice-grid.notice-read-reserve`」→「`PreparedGrid` 的 `.notice-grid` surface」，两者高度都来自 `notices.css` 的 `.notice-grid{height:62dvh;min-height:300px}`，`box-sizing:border-box` 下内边距不改外框，因此**理论上完全相等**；但这是本票唯一「同一 class 在不同分支渲染」的推论，**未经浏览器实测**。若实测有偏差，主控可把占位改为常驻 `PreparedGrid` + `preparing` 隐藏态（该路径已被 477 验证），代价是首读期要挂载 AG Grid。
2. `test_first_page_waits_for_fonts_and_return_keeps_page`（`:9-63`）要求冷字体挂起时 `region[name=付款通知书列表]` 不可见：本票在 `placeheld` 时不挂 `role=region`，满足；放行后该 region 由 `PreparedGrid` 的 `preparing`→`ready` 上屏。
3. `test_inventory.py:24` 要求 `.inventory-grid` 最终 `aria-busy=false`：占位 div 不带 `aria-busy`，该属性只由 `PreparedGrid` 的 surface 提供，故占位期间没有该属性——该用例等待的是数据落地后的真网格。
4. `test_home.py` 用 `.home-tile`／`.home-tile-count` 文本比对真实计数：本票在成功读取后仍渲染真实数字，结构未变。
5. `test_debt_loading.py:149` 要求 `.debt-overviews-status .notice` 恰 1：欠款槽换成 `ReadStatusLane` 后 class 名保留、`ReadFailure` 结构未变；该用例同时依赖 `:98` 的 `data-read-phase`，由组件等价生成。
6. `test_process_mechanical_loading.py` 依赖 `.process-read-status[…]`／`.mechanical-read-status[…]`／`.process-read-body .read-placeholder`／`.mechanical-read-body .read-placeholder`：class 名保留、占位仍在 `.process-read-body`／`.mechanical-read-body` 内，选择器全部仍命中；`data-read-phase` 与 `aria-busy` 语义不变。
7. `test_ledger_layout.py:48-60` 要求 `.flow-grid` 高度稳定（>240 且搜索后变化 <1px）：本票只把槽从「流内 `ReadState` 行」换成恒高槽、占位仍带 `.flow-grid` 的既有 flex 尺寸，理论不改高度；未实测。

## 五、共享机制：现状与剩余建议

### 5.1 消费者清单（共享样式实际生效范围）

`import ... from './read-region'` 的页面共 **13 个**；因为 `read-region.tsx:1` 自带 CSS import，这 13 个页面**都实际加载** `read-region.css`：

| 已改用共享槽 `ReadStatusLane`（8） | 只消费占位/失败组件、槽仍为页面自有（5） |
|---|---|
| `flow.tsx`（欠款、流水统计、流水列表 3 处）、`notices.tsx`、`inventory.tsx`、`home.tsx`、`process.tsx`、`mechanical.tsx`、`contracts.tsx`、`contract-subtables.tsx` | `oilcard.tsx`、`oilcard-invoices.tsx`、`oilcard-ledger.tsx`、`oilcard-linkage.tsx`、`oilcard-reconciliation.tsx` |

- `contracts.tsx`／`contract-subtables.tsx` 的 `ReadStatusLane` 采用由**集采/油卡会话（TAIL-480）在其写域内完成**；本票只提供共享层，未编辑这两个文件，其 `--read-status-pad` 变量写在各自 CSS。
- 5 个油卡页仍用页面自有槽 + `read-announce`：它们不在本轮指令范围（479/480 写域），但已因模块图自动获得新的共享呈现样式；其 `.oilcard-read-reserve` 只补本页内边距/外框，`overflow` 交给 `.read-reserve`。
- 结论：**"确保所有消费者实际加载"这一条由模块图保证，不依赖 `styles.css` 的 `@import` 顺序**，后续新增页面 import `read-region` 即自动获得。

### 5.2 剩余建议（不由本票改）

1. `ReadState`（`read-region.tsx:31`）现在**没有任何消费者**（13 个页面都用 `readPhase` + `ReadFailure` + `ReadPlaceholder`）。建议主控在下一轮整合时删除，避免两套表达并存后被误用。（本票未删：它是 477 已交付的公共导出。）
2. 5 个油卡页的自有槽（`.oilcard-*-status` 形态）与 8 个已收敛槽仍是两套。建议 480 会话收敛到 `ReadStatusLane`，本票不越界。
3. `contracts.css:89-90`／`contract-subtables.css:27-28` 只留了变量与 reserve 内边距/外框，形态已与共享层一致；若后续继续收敛，保持"页面只给变量"的约定即可。
4. `package.json` 的 `test:unit` 列表：本票**没有新增单元测试文件**（`read-region.test.mjs` 是既有文件，只加了用例），因此**不需要**改 `package.json`。若后续把槽的可测逻辑再抽纯函数另开文件，才需要追加。

## 六、未验项与限制

- §4.2 的 8 条 GUI 用例**未运行**：本会话无 playwright、且按指令不启停预览、不访问浏览器。因此「工具区先可用」「失败不推移」「不冒充空表/0 行」「统计与流水独立」「失败不清空主表」「首页不写假 0」目前只有源码控制流依据 + 单元层依据（`read-region.test.mjs` 的六态与双失败例）。
- `test_startup_styles.py` 的 notices 框不变断言、`test_ledger_layout.py` 的流水高度稳定断言，未在真实浏览器验证（见 §4.4 第 1、7 条）。
- `flow.css` 中 `.payment-stat-columns` 由 `height:100%` 改为 `height:auto;flex:1 1 auto;min-height:0`：统计卡内部几何在 1280/1920 两档以及 `@media(max-width:1000px)` 下的表现未经实测。
- 真实副本上的通知书选择/付款保护、库存调整保存、流水撤销与导出（各自门控未改，但加载态叠加其上的组合）未在真实副本复核。
- 未做全站回归、窗口矩阵、真实 i8 抓取、部署或提交。
- 并行会话同时编辑 `process.tsx`／`mechanical.tsx`（479）与 `contracts*`／`oilcard*`（480）。本票对 479 两个文件只做**机械迁移**（槽容器 + CSS 变量），业务逻辑一行未动；`tsc`/单测是在这些并行改动都在树上时取得的，未单独隔离。§4.1 里那次瞬时 `oilcard.tsx TS6133` 属并行写入窗口，非本票改动。

## 七、稳定源码窗口与最小 GUI 节点建议

### 7.1 稳定窗口

- 基点 `9efebc87`；分支 `codex/browser-session-loading-20261104`。
- 本票（含两轮）改动：**2 个新增文件** `apps/frontend/src/read-region.css`（35 行）、`apps/frontend/tests/test_read_lanes.py`（189 行，第一轮）；**15 个已跟踪文件**（`git diff --numstat`）：
  `read-region.tsx 23/2`、`flow.tsx 15/8`、`flow.css 11/16`、`notices.tsx 8/2`、`notices.css 6/0`、`inventory.tsx 9/3`、`inventory.css 6/0`、`home.tsx 19/13`、`home.css 10/1`、`process.tsx 13/3`、`process.css 5/0`、`mechanical.tsx 13/5`、`mechanical.css 3/0`、`tests/unit/read-region.test.mjs 49/1`、`tests/test_startup_styles.py 40/9`。
- 共享文件在 `9efebc87` 上本票未触碰：`grid-presentation.tsx`、`grid-layout.ts`、`page-surface.tsx`、`main.tsx`、`styles.css`、`ui.css`、`style.css`、`package.json`。
- `read-region.tsx` 与新增 `read-region.css` 是**主控授权**给本轮的共享呈现写域；`flow.css` 只改流水/统计区段与删掉 477 的槽几何（欠款卡片几何未动）；`process.tsx`／`mechanical.tsx` 只做槽容器机械迁移。
- 全部文件已归一为 CRLF；`tsc --noEmit` = 0、`npm run test:unit` 94/94、`py_compile` = 0 之后未再改动源码。

### 7.2 最小 GUI 节点建议（主控构建真实副本后按此顺序跑）

按"每页一次即可覆盖本票新增缺口"的粒度，建议 6 个节点（节点 1、2、3、4 用挂起；5、6 用 503）：

1. **通知书首读保留框**：`docs` 无（纯 UI）——登录后进 `付款通知书`，DevTools/route 挂起 `**/api/m03/notice-list?*`，断言：搜索框可聚焦；`.notice-read-status [role=status]` 恰 1；`.notice-read-reserve .read-placeholder` 恰 1；`region[name=付款通知书列表]` 为 0；记录 `.notice-grid` 框 → 放行后 region 可见且**框完全相等**、槽与占位归零。
2. **库存工具先可用 + 不冒充 0 行**：挂起 `**/api/m08/inventory`，进 `库存单据与调整单`：`.page-loading` 为 0、「库存核算期间」可点、「列筛选」可点、`.inventory-grid.inventory-read-reserve` 在且 `[role=grid]` 为 0、计数文案「尚未读取」、槽 `data-read-phase=reading` 恰 1 条 status；放行后 `aria-busy=false`、计数匹配 `N / M 行`。
3. **流水统计与列表各自发布**：进 `付款流水`，同时挂起 `**/api/m05/stats?*` 与 `**/api/m05/flows?*`：两槽各 1 条 status、两处占位各 1、`流水关键词` 可输入；只放 stats → `.payment-stat-columns` 可见而流水占位仍在；再放 flows → `aria-busy=false`、`.flow-grid` 框不变。
4. **首页 tile 恒在、不写假 0**：挂起 `**/api/m03/notice-list?*`，进 `首页`：`.home-todos` 可见、`.home-tile` 3、`.home-tile-count-reading` 3、槽 1 条 status；放行后占位 0、首个 `.home-tile-count` 是纯数字、`.home-todos` 框不变。
5. **流水统计失败不推列表**：流水页就绪后对 `**/api/m05/stats?*` 返回 503 并点「按月」：统计槽 alert + 「重试读取」、`.payment-stat-reserve .read-placeholder-quiet` 恰 1、`.payment-stat-columns` 为 0、`.flow-grid` 仍 `aria-busy=false` 且框差 <1px。
6. **同槽两条失败并排可辨、按钮不裁**（覆盖 §3.3 的第 3 条修正；本会话只有单元依据）：在 `付款流水` 同时让 `**/api/m05/flows?*` 与 `**/api/m01/projects` 失败，或在 `过程资料`/`机械费报表` 同时让主读取与 `**/api/m01/projects` 失败：断言槽内 `.notice` 恰 2、两条 `role=alert`、第二条文本以「项目清单：」开头、两处「重试读取」均可见且**中心点 `elementFromPoint` 命中按钮**（不是被 `overflow:hidden` 裁掉），槽高度仍是 `--control-h`（`getBoundingClientRect().height` 与空态相同）。

（节点 6 同时是 479 两个页面的补验；若时间只够一页，优先 `过程资料`，它的两条失败都是首屏即可触发。）

## 八、第二轮窄集成修正（2026-11-04/05）

主控诊断复跑报出两例失败，根因都在测试侧：在 `page.goto(..., wait_until='domcontentloaded')` 之后立刻 `assert held`，此时页面尚未挂载发起读取，路由拦截列表仍为空。本轮只改 `apps/frontend/tests/test_read_lanes.py`（本票新增文件，源码未动）：

1. 通知书首读例：搜索框可聚焦断言之后，先 `expect(page.locator('.notice-read-status')).to_have_attribute('data-read-phase','reading')`，再 `assert held`。
2. 通知书失败例：`goto` 之后同款等待，再 `assert held`。
3. 流水独立例：`#page-title` 断言之后，先分别等 `.payment-stats-status` 与 `.flow-list-status` 的 `data-read-phase` 为 `reading`，再 `assert stats` / `assert flows`。

三处都等"真实相位"而不是固定 `sleep`（等待均带显式 `timeout=20000`，不依赖默认短超时）——槽只有在其请求已存在时才报 reading，等它出现即等于等读取已发起，同时不依赖挂载耗时。检查：`apps/frontend` 下 `node_modules/.bin/tsc --noEmit` = 0；`node --import=tsx --test tests/unit/read-region.test.mjs` = 10/10 pass；`py_compile` = 0。

未验：上述 6 例本轮**未在浏览器运行**（本会话无 playwright），须由主控在登记真实副本复跑；§七 的 6 个节点不变。
