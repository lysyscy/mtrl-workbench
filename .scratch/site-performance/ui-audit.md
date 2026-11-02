# 全站前端共性性能只读审计

2026-11-02；任务给定基线 `daf8a7fc`，分支 `codex/mechanical-derivation-fix-20261102`。本报告只读源码和既有证据；未运行新浏览器测量、构建、业务写入、服务操作或产品改动。允许的唯一新增文件为本说明。以下“确认”只表示调用/循环/依赖存在，不表示它已经造成用户可感知性能故障。

已读 Impeccable `reference/optimize.md`。采用其“先定位真实瓶颈、修最大项、前后测量、不牺牲功能”的方法；本项目已明确鼠标/输入法及业务表格约束优先，不由通用建议扩大键盘、视觉或移动端工作。已有 route lazy/memo、AG 虚拟行、字体分片、paint containment、布局复用及批量表头测量不重新列为缺失能力。

## 覆盖和共用边界

`apps/frontend/src/main.tsx:31–46` 注册 15 页；`:49–50` 统一 memo，`:65–85` 每账号 QueryClient，`:101–105` 仅挂载已访问页并传 `blocked || !active`。`page-surface.tsx:13–43` 只在首次可见发布前监听本页 DOM/QueryCache、等待字体，完成后释放监听；`:46` 用 hidden/inert 保活并提供 PageActivity。

| 路由 | 数据/展示主人及共享入口 | 主要查询门控 |
| --- | --- | --- |
| `/` | `home.tsx:10–19`，无网格；与通知书同 `['notices']` | active && !blocked |
| `/projects` | `projects.tsx:208` BusinessGrid normal，`:209` ReadGrid 留痕 | `:85–88` !blocked；根已把隐藏页 blocked 置真 |
| `/i8` | `i8.tsx:62,71` ReadGrid，小摘要 autoHeight/记录 normal | `:35,55` !blocked |
| `/notices` | `notices.tsx:214,237` PreparedGrid/单行策略 | `:81,83` active && !blocked |
| `/debt` | `flow.tsx:38–46` 三块完整欠款 Bars；`ledger.tsx:101,115` 双侧 PreparedGrid normal | `flow.tsx:39–40` 与 `ledger.tsx:148–153` |
| `/ledger` | `flow.tsx:87,117` PreparedGrid normal，统计 Bars | `:55–63` active && !blocked |
| `/contracts` | `contracts.tsx:148–199` 直接 AgGridReact，共享 widths/retainedColumns，固定单行 | `:74–75` active && !blocked |
| `/process` | `process.tsx:205` BusinessGrid 矩阵 normal；`:213–215` PreparedGrid 差异 autoHeight | `:61–62` active && !blocked |
| `/settlement` | `settlement.tsx:44–57,134–137` PreparedGrid 月报/两张年度 autoHeight | `:28–29,34,78` 页面和子 tab 均 active 门控 |
| `/big` | `big.tsx:58` 已访问月份保活；`:134,154` PreparedGrid autoHeight | `:54,66` active && !blocked |
| `/inventory` | `inventory.tsx:83,111–113` PreparedGrid normal，文本测量适配 | `:49–50` active && !blocked |
| `/fees` | `fees.tsx:88,98` PreparedGrid autoHeight | `:50–51` active && !blocked |
| `/mechanical` | `mechanical.tsx:86,88` summary PreparedGrid normal；`mechanical-details.tsx:88` BusinessGrid；`mechanical-work.tsx` ReadGrid | `mechanical.tsx:130–131` !blocked；已轻量 page，无 Excel preview |
| `/rules` | `rules.tsx:124` 等 ReadGrid 配置小表 | `:64–75` enabled=active && !blocked |
| `/users` | `users.tsx:75` ReadGrid autoHeight | `:39` active && !blocked |

BusinessGrid 在 `business-grid.tsx:39–44` 消费 PageActivity；ReadGrid 在 `:58,71–75` 只在 active 时首次字体/拟宽。PreparedGrid 将 rows/totals 直接交 AG（`grid-presentation.tsx:55–60`），尺寸准备在 `grid-layout.ts:77` 因 inactive 直接退出。故源码不支持“所有隐藏页仍重复 HTTP/深测量”的笼统结论。数据观察器、保活 React 树和 AG 实例仍存在，属于下面可测的另外一类成本。

## 优先候选及可证伪测量

### 1. 大结果的尺寸准备存在全行规划成本（优先库存）

确认的源码模式：`grid-layout.ts:116–120` 为 wrapping/render 列遍历所有 rows 汇集字串；`:153–165` 再按全行×相关列执行 text/signature 并构造 plannedRows；`:169–171` canvas 快速判单行；`:176–199` 才以最多128单元格分批实测/富控件 portal。`:203–206,233` 再组装并应用全部行高。已有缓存、8ms后让帧、未变数值复用（`:95–109`）有效，不能按循环存在便说每次输入都会重测。

覆盖：所有 PreparedGrid/BusinessGrid。库存 `inventory.tsx:26,83` 是文本适配的大结果候选；过程/费用/大表/台账则可能有富控件成本。默认富控件 signature 为每列 `JSON.stringify(row)`（`grid-render-layout.ts:30–36`）；process 的自定义 signature 也序列化整 row（`process.tsx:193–195`）。机械明细已经采用 textOnly/singleLine，不能套用旧“renderer28”问题。

最小测量：固定同一库存快照、字号、视口，采一次首次进入、一次“全部”范围切换、一次仅文字列本地筛选；同时读最新 `data-layout-timing` 的 reused/measured/rows，Performance 调用栈中分别量化字串规划、signature、canvas、DOM/portal、AG 更新。以原数据量及合成成倍重复量区分 O(rows×columns) 成本，不能只看工具点击时长。若主线程热点不在这里或当前样本无可感阻塞，则暂缓。

潜在成熟方向：复用当前不可变输入的列级文本/签名结果；按实际几何依赖缩窄富列签名；只有证实规划本身是长任务后才考虑有界分段。收益证明应同时减少该阶段CPU与最长任务/交互到下一帧，而非仅减少 measured 数。不得以抽首屏样本替代完整金额/标识下限，也不得拿固定行高裁掉必要错误/长文。

### 2. 集采搜索/勾选重建列时重复全量金额测宽

确认的源码模式：`contracts.tsx:181` 的 baseColumns 依赖 shown、picked。每次搜索/勾选进入 `:163–166`，对各金额列重新映射全部 rows+total，格式化 money，再调用 numberColumnWidth 和 completeColumnWidth。numberColumnWidth 本身创建 canvas 并遍历去重值（`grid.ts:37–44`）。这与 completeWidths 自身已有 memo（`contracts.tsx:149–156`）是两条不同路径；这里只确认重复计算，不声称已引起卡顿。新列定义亦经过 retainedColumns（`:187–188`）及 AG；稳定 row ID 不代表整行一定重建。

覆盖/共性：集采是最直接反例；库存 `inventory.tsx:69–73`、过程 `process.tsx:203`、大表 `big.tsx:109–119`、费用 `fees.tsx:78–86` 也按完整值保护宽度，但多数 memo 依数据/范围，不能一并认定依赖错误。

最小测量：同一集采快照，只做一次无业务写入的行勾选与一次搜索字串输入；profile 定位 amount formatter/canvas/columnDefs commit 与实际 cell renderer mount。若一次纯勾选的主要成本确在全量测宽，可把完整结果几何与选择/搜索 UI 依赖分开，保现行完整结果和搜索合计口径。前后比较相同行数下的计算次数、CPU、输入/勾选到绘制；只少 useMemo 执行而用户指标未变，则如实报告局部收益。

### 3. 多页/多月份保活后的隐藏派生、观察器和实例累积

确认的源码模式：PageSurface 隐藏但不卸载；query enabled 暂停发起读取不等于移除观察器。首页与通知书共享 notices（`home.tsx:11,14–16`；`notices.tsx:81–94`），全部项目查询又被多页消费。共享数据更新可使隐藏页重新派生 rows/筛选/合计并发布给其仍存的 AG；例如通知书 `:84` 逐行扩展、逐行 find 项目。大表还在 `big.tsx:53–58` 为每个访问月保留整个 BigMonth；其矩阵与草稿保留是明确交互需求。

尺寸准备已在 inactive 停止；但 `ledger.tsx:117–127` 的尺寸回调/ResizeObserver 以及 `mechanical.tsx:88–97` 的 fitHeight 观察器没有独立 active 早退。列宽偏好通道也有意同步同账号/表的多实例（`grid-width-state.ts:57–62,110–125`）。这些均可能很便宜，目前没有隐藏页成本实测，不能直接当故障或取消必要同步。

最小测量：同一 visible 页、同一个只读刷新/共享缓存数据更新，比较只访问该页与已访问全部15页（另加多个大表月份）的 Performance/React commit、AG model events、DOM节点与JS heap；归因到具体隐藏主人。请求数应单独记，不能用零HTTP证明零CPU。若只随保活实例数增加而耗时/heap显著增加，再局部暂停非必要派生或延迟数据呈现，保 Query 真值和草稿主人；不默认改成卸载页面/TTL清缓存。

### 4. autoHeight 自然长表的全DOM提交及首显等待

确认的源码模式：月报/年度提取/月度会大表/费用/差异采用 domLayout=autoHeight（覆盖表中已列）。`grid-layout.ts:237–254` 明确等待全部已知 row ID 的 DOM、AG帧队列和横滚占位后首次发布；这些表因既有自然高度需求不享有普通 normal 表的垂直虚拟窗口。ReadGrid 小表也多为 autoHeight，但预期量小，先核实际行数。

最小测量：只挑真实结果最长的一张 autoHeight 报表，记录行数、DOM/控件数、AG render/style/layout/paint、自有 prepare 与 mounted 等待分别耗时；再看同范围重读、滚动是否仍有长任务。可复用一次库存 normal 表作为机制对照，不能把表业务差异当因果。若真实规模有限且无明显成本，则不动。若证实瓶颈，可先研究不改变页面自然滚动/短表结束位置的浏览器跳过离屏渲染策略；对 content-visibility 的尺寸估计、冻结列、合计、复制和滚动位置需实际证明，再谈采用。直接改为固定高度内滚或分页会冲突现行要求，不在本轮技术裁量内。

### 5. 首次字体准备的扫描范围存在页际差异（低优先）

确认的源码模式：PageSurface 的 scopes 是所有 `[data-page-chrome]`（`page-surface.tsx:23–31`），loadElementFonts 遍历文字和输入并逐节点读 getComputedStyle（`appearance-ready.ts:40–53`）。通知书/库存/机械等按工具区划界；项目 `projects.tsx:202`、流水 `flow.tsx:107`、集采 `contracts.tsx:194`、i8 `i8.tsx:57`、规则/账号则在整个根上标 chrome，可能把已挂载表区/嵌套 width-header 也纳入首次字体扫描。仅首次发布阶段，完成后观察器已释放，不能据此说持续全站重扫字体。

最小测量：针对候选首显慢页，记录 scopes 数、重复包含的文本节点数、loadElementFonts CPU/字体请求/等待；与表自身字体准备重叠部分做归因，复用缓存字体做一组对照。若扫描成本微小且并行不阻塞则暂缓；如确为首显热点，可对齐已采用工具区/表区主人，保真实字重/中文字库就绪和首次稳定显示，不切回字体闪换。

## 既有证据可以证明和不能证明什么

- `.scratch/mechanical-performance/verification.md:15–25,39–41` 可复用：同源响应11,234,328B→1,192,714B；真实副本page HTTP327/341ms；零租布局准备约169–243ms，对比原约946ms；正式page421/337ms。证明已实施机械链路及共享表头代表收益，不证明其余页面或真实用户INP。
- `diagnosis.md:41–50` 可复用：相同17表头的逐个写读417/415ms vs 批量26/31ms、高度一致；269业务行只挂载21行，原零租已有行虚拟化。该热点已经修复，不重复列为候选。
- `docs/status.md:35–39` 保留现有反例：普通保存曾有列宽跳动、草稿回旧值/滚动覆盖，现有定向验证已通过。新优化必须保这类失败条件；不为审计重做写测。
- `docs/status.md:53` 明确旧夜间本机代理指标不足证明库存全量准备、滚动或整体加载提速；因此本报告把库存列为首测候选，而非已确认退化。

最终排序应由当前样本的成本占比决定。无需同时实施五项；第一项证伪即可移到下一项，没有证明净收益的候选保留现状。
