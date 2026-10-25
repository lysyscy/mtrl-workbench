# React 操作流畅度与动画研究

> 查询日期：2026-10-25。研究输出，尚未启动下一轮实施。字体和虚拟滚动只是候选；主线是实际操作的阻塞链路和连贯反馈。仅浏览一手文档/规范/维护者源码；未上传业务原件或截图。

## 结论与优先级

下一轮优先处理**库存筛选触发的自动行高测量与布局**，同时量化页面保活带来的重复工作，再据分段耗时决定数据/API方案。动画复用Ant Design和浏览器能力，作为及时反馈与状态连续性的补充。

本轮已经出现比“字体很大/数据很多”更直接的调用栈/热点证据：数据已缓存、窗口没有API请求、仅有12–24个渲染行DOM节点时（含固定区副本，并非逻辑行数），仍出现200ms以上输入/点击处理；主要几何读取采样来自AG自动行高创建链。因而不能预设加虚拟滚动、换字体或只优化网络就能解决这类卡顿。此结论只适用于本次库存动作热点，不能外推全站唯一根因。

| 顺序 | 目标与推荐方案 | 代价和决策门槛 |
| --- | --- | --- |
| P0 | 对库存自动行高做有界对照：固定/受控行高，完整中文通过键盘可达的展开/详情保留；减少单元格几何读取，检查自定义列宽适配触发 | 中；先保完整内容、金额、焦点和编辑，不能默默裁字；以布局自耗时与完整结果耗时验收 |
| P1 | 稳定页面更新边界，避免不相关保活页参与导航计算；减少库存候选值/筛选重复扫描；保留默认Query结构复用 | 低至中；Profiler与分段计时确认收益，保护草稿/历史/账号树 |
| P1 | 统一点击、输入、加载、切页和弹窗反馈；现有AntD + 短CSS动效 | 低；立即回显、可中断，动效不推迟可操作时刻 |
| P2 | 若冷加载仍受影响，量化模块下载/执行、字体；若全量库存读取仍贵，分解服务端到浏览器各段 | 中；先测哪段占大头，再挑窄投影、模块精简或系统字体 |
| P3 | 仅在前项不足时采用服务端分页/汇总，或CPU计算Worker；必要的原生长表再加虚拟器 | 中至高；需要API业务合同、正确性与端到端收益证据 |

以上是研究建议，未承诺收益。成熟做法是把交互拆成输入等待、事件处理、下一帧呈现三段，分别减少工作。[Chrome团队：Optimize INP](https://web.dev/articles/optimize-inp)（查询 2026-10-25）

## 证据分级

### 已有正式基线

[435–440回执](../../.artifacts/active/react-performance-polish/20261025-435-440/reports/delivery.md)的产品源码为5dc133e7；原98d2d66构建及84样本仍保留。通知书/合同/库存热ready中位约470/501/518ms；最终热样本仍有合同203ms、库存201ms单任务。多数冷ready上升，规则冷CLS最大.342。库存18198行、HTTP约11.36MB，独立顺序HTTP中位约410ms未改善；后端mapping试验更慢已撤回，不能据此断言SQL根因。欠款窄投影收益已经做完，不能外推到库存。

ready含networkidle、fonts.ready和两帧，是历史诊断代理，不是INP。保留8065验看实例与前后基线；8000绝对不动。

### 本轮新增交互诊断：已测热点，不是最终性能承诺

原始报告与轨迹归[交互诊断归档](../../.artifacts/archive/react-smoothness-research/20261025-diagnosis/reports/interactions.json)及同级traces，解释范围以interpretation.json为准，保留至2026-11-24。固定历史只读副本、Chrome156、1350×940、先加载库存再操作；仅前4动作窗口用于本轮热点判断，后4导航没有等待接口/懒加载就绪，存在跨窗口归属风险，排除归因。

| 动作 | 原始事件/长任务 | CPU采样热点 | 可以说明什么 |
| --- | --- | --- | --- |
| 选择全部期间，18198行 | click约280ms，processing251ms，最长任务254ms | getElementSize自耗时约133ms，其中自动行高调用链归组130.25ms；渲染行DOM节点12个（含固定区副本） | 已有行虚拟化，仍会因每个已渲染单元格行高测量阻塞 |
| 输入“钢” | beforeinput208/input200ms，最长任务190ms | getElementSize约106ms，自动行高归组104.42ms；渲染行DOM节点24个（含固定区副本） | 输入到结果更新可卡；脚本insertText可能interactionId=0，不称有效INP或真实IME验证 |
| 清全部筛选 | click约256ms，processing222ms，最长任务228ms | getElementSize约114ms，自动行高归组110.73ms | 数据已在本地，筛选后的网格重排本身值得先优化 |

前三个重动作的几何读取栈均主要来自 `s ← c ← setupCellAutoHeight ← setupAutoHeight ← setComp`；这些有效窗口无API请求。因此自动行高是**本次动作的重要已测热点**，并非凭minified函数名猜因。少量脚本动作及profiling开销不足以给p75/真实用户INP或无Profiler绝对耗时承诺；自动化“两帧”也不作纯浏览器响应指标。初次observer失败日志保留，不计通过。

### 源码事实和待证问题

| 位置 | 实际行为 | 仍需测量 |
| --- | --- | --- |
| `main.tsx:58–107` | visited页mounted+hidden/inert；location变化时映射所有已访问页；没有页面memo/Activity | 切页有多少隐藏页render/Effect，context传播多少工作 |
| QueryClient | retry=false、refetchOnWindowFocus=false；没有统一staleTime；查询随active启停 | 激活重读频率及合法新鲜度窗口；不再把已关闭的focus重读当问题 |
| `inventory.tsx:53`等 | 枚举候选值每render去重排序，筛选UI关闭也算；rows/汇总已有useMemo | 重复扫描占比，已有memo是否命中 |
| `inventory-api.ts:24–43` | 每次读取全量校验，数值cents校验后返回字符串；存在rows×adjustments检查 | 当前副本adjustments=0，嵌套扫描只是规模风险，不是本次大头 |
| `filterRows/sumRows` | 每行遍历19字段，活跃文本条件重复小写化；金额精确求和用BigInt | 预备活跃条件/数值边界、复用结果各省多少，不能删金额验证 |
| `grid.ts:34–70` | 已rAF合并适配；仍扫描渲染DOM、computedStyle、measureText与控件矩形；有编辑焦点保护 | 自定义适配与AG行高各自占比，触发几次，是否形成额外布局 |
| `grid.ts:1–5`、主题CSS | AllCommunityModule；部分抑制列虚拟化；已有hover和reduced-motion规则 | 模块执行时间、真实列数、AntD JS动效是否也尊重系统设置 |

## 方案一：先把表格几何工作减下来

AG官方说明：单元格 `colDef.autoHeight`增加尺寸监听，并使这些列持续渲染、停止这些列的横向虚拟化；动态高度随滚动变化可能带来滚动条跳动。这与本次热点吻合。[AG Row Height](https://www.ag-grid.com/javascript-data-grid/row-height/)（查询 2026-10-25）

推荐下一轮只选库存做有界对照：保持原内容/字段/数据，比较现行autoHeight与固定或受控行高；长中文提供完整可读、可键盘访问的展开或详情，金额不省略，最大字号下控件可达。不能为性能强行丢长文本，也不要求所有小表取消autoHeight。行高策略涉及阅读取舍，需让用户看到具体候选再落实。

列宽适配另测：读完一批几何再统一写入；按数据版本、字体/字号、容器宽度等真实依赖触发，保留编辑时延迟保护；能从已有列元数据确定的金额最小宽度不反复扫DOM。rAF仅改变执行时机，不减少同步测量。Chrome建议批量读后再写，避免forced reflow与读写交替。[布局与layout thrashing](https://web.dev/articles/avoid-large-complex-layouts-and-layout-thrashing)（查询 2026-10-25）

AG默认已有行/列虚拟化，项目rowBuffer=2；先核可见DOM和renderer自耗时，再恢复有依据的列虚拟化。固定列、需要自动行高的列不一定受益。保持rowData/columnDefs/对象配置引用稳定、稳定行ID以保留选择；不要所有事件监听器机械useCallback。[AG DOM Virtualisation](https://www.ag-grid.com/javascript-data-grid/dom-virtualisation/)、[React Best Practices](https://www.ag-grid.com/react-data-grid/react-hooks/)（查询 2026-10-25）

**两个autoHeight不同。** `domLayout='autoHeight'`控制整个grid随行数增长；`colDef.autoHeight`测量单元格行高。锁定AG36.2.0的本地源码已确认theme参数 `autoHeightMaxBodyHeight`，默认为none；内部 `_canScrollVertically`在normal或autoHeight有上限时允许纵滚。官方文档也说明封顶后滚动并虚拟化。它能约束整个grid，不会自动消除本次单元格autoHeight热点。大表优先保留现有normal有界视口，小弹窗可按需求选封顶autoHeight。[AG Grid Layout](https://www.ag-grid.com/javascript-data-grid/grid-size/)（查询 2026-10-25）；本地 `node_modules/ag-grid-community/dist/package/main.esm.mjs:453,23817,24985`只读核实。

单元格只是金额/文本格式时优先valueFormatter，少建DOM；已证实慢的非交互renderer可试AG自带deferRender，停止滚动后补内容。重要金额、编辑器和操作反馈不延迟。离屏 `content-visibility`不能阻止JS/请求，并可能测得零尺寸；当前hidden页不靠它解决重渲染。[AG Scrolling Performance](https://www.ag-grid.com/javascript-data-grid/scrolling-performance/)（查询 2026-10-25）

仅当原生BoundedTable真实行数大、DOM确为热点，再选TanStack Virtual；其headless模型保留现有样式，但布局、键盘和语义需自行维护。react-window是规则列表/网格的简化备选，不同时引入两套；AG表绝不外套第二层虚拟器。[TanStack Virtual](https://tanstack.com/virtual/latest/docs/introduction)、[react-window维护者仓库](https://github.com/bvaughn/react-window)（查询 2026-10-25）

虚拟化/行高验收覆盖纵向末端、横向全列/固定列、完整金额/长中文、最大字号、排序过滤选中、编辑行滚出/滚回、草稿焦点、Tab/方向键。只渲染局部时需正确总行列数和逻辑索引。[W3C Grid/Table Properties](https://www.w3.org/WAI/ARIA/apg/practices/grid-and-table-properties/)（查询 2026-10-25）

## 方案二：减少保活、查询和重复计算

### 页面边界

先比较“只访问一页”和“访问全部14页后返回”的同一交互；用Profiler确认隐藏页是否参与。React memo能跳过props未变的父级更新，但自身state/context仍能触发；新数组/函数/对象破坏浅比较。只给已证重页建立稳定边界，避免无关共享状态传遍页面；useLocation/context订阅本身仍可触发memo内页面。先试memo边界、稳定props和仅对active页计算非必要派生值，不全站机械memo，不为这次优化引入Compiler。[React memo](https://react.dev/reference/react/memo)（查询 2026-10-25）

锁定React19.3.1实际导出Activity和ViewTransition（主调查已执行typeof核实），不能沿旧资料称为“只有Canary”。Activity隐藏时保留状态/DOM、清理Effects，显示时重建；收到新props仍低优先级渲染，并非冻结。适合单个重页试验暂停订阅，但须核AG尺寸恢复、Effect清理、查询取消、草稿/保存队列、迟到回调和换号隔离。尤其核AG React封装清理Effect是否destroy GridApi、恢复滚动/编辑/草稿/historyguard/Query订阅；不直接替换全部保活机制。[React Activity](https://react.dev/reference/react/Activity)（查询 2026-10-25）

### 查询新鲜度与订阅

TanStack Query默认缓存stale，重新启用查询等场景可能重读；staleTime减少不必要重读，但先按业务新鲜度和写后失效契约选。参考字典与库存/金额不能同一刀切；不全局Infinity，更不使用会阻断invalidate的static。[Important Defaults](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults)（查询 2026-10-25）

默认structural sharing复用JSON兼容数据的未变分支。库存缓存结果仍为字符串/数值/布尔等JSON兼容结构，BigInt只用于校验和求和，不能据此关闭sharing；大树比较成本单独量。`select`适合计数/局部投影订阅，不能减少网络、解析和queryFn校验；稳定selector引用，校验错误留queryFn。[Render Optimizations](https://tanstack.com/query/latest/docs/framework/react/guides/render-optimizations)（查询 2026-10-25）

### 计算与调度

优先消除枚举候选值每render扫描；预编译活跃筛选条件、小写查询、数值边界；需要时建一次row_id索引。保留重复ID、金额精度、字段校验和错误语义。当前调整数0，不能优先修潜在O(NM)凑优化。

startTransition回调立即执行，只调整React状态优先级，不会把同步筛选/JSON/AG命令搬离主线程；受控输入本身不能Transition。useDeferredValue可使输入先回显、重列表稍后追上，不能自动减少请求和总工作。仅在测出React渲染阻塞时采用，并标明结果待更新，最终结果与输入条件一致。[React startTransition](https://react.dev/reference/react/startTransition)、[useDeferredValue](https://react.dev/reference/react/useDeferredValue)（查询 2026-10-25）

有必要分块的长计算才让出主线程；scheduler.yield仍有兼容边界，特性检测并回退。延后必须继续计完整结果、总CPU、取消及第二次输入，不能只把工作搬出观察窗口。[MDN scheduler.yield](https://developer.mozilla.org/en-US/docs/Web/API/Scheduler/yield)（查询 2026-10-25）

## 方案三：大数据与冷启动按分段证据选

库存读取拆成数据库执行/读取→Python装配/序列化→传输→JSON解析→readInventory→Query结构复用→筛选/求和→React/AG布局绘制。用同一次请求的标记或受控后端计时区分，不能把11.36MB或HTTP总时长当SQL证据，也不将独立HTTP与并行浏览器计时相减。

先消除重复工作、评估实际字段投影/压缩；若全量传输/解析/内存仍占大头，再设计服务端筛选排序分页与独立汇总。只在UI分页而响应仍全量返回，不能改善网络和解析。

| 数据模型 | 许可/能力 | 本项目边界 |
| --- | --- | --- |
| Client-Side | Community可用，全量本地处理 | 最少改动，全量响应成本仍在 |
| 服务端普通分页/Infinite Row Model | Infinite属Community，分块加载平面数据 | 需要API过滤排序、总计/导出/跨页选择合同 |
| Server-Side Row Model | Enterprise，按需分组/聚合，生产需商业许可 | 当前AllCommunityModule没有；服务端分页不等于必须购买SSRM |
| Viewport | Enterprise，服务端感知精确可见区/实时推送 | 当前无已证需求，不推荐增加复杂度 |

来源：[AG Row Models](https://www.ag-grid.com/javascript-data-grid/row-models/)、[Modules及许可](https://www.ag-grid.com/javascript-data-grid/modules/)（查询 2026-10-25）。

分页前先确认：全量筛选等价、排序带唯一稳定键、金额精确、总计覆盖整个筛选范围、导出完整、编辑按ID/版本、刷新新鲜度、取消与迟到响应、跨页选择和账号隔离。固定快照能比算法，不能证明生产新鲜度/真实保存。

Worker只在解析后筛选/汇总CPU持续显著时试：不能访问DOM，消息通常结构化复制，会增加内存和序列化成本。优先传ID/小结果，带版本/取消和错误通道；主线程阻塞下降且总完成时间/内存可接受才保留。[MDN Web Workers](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Using_web_workers)（查询 2026-10-25）

冷启动另测模块下载与执行。AllCommunityModule可按实际功能选择模块；约1.178MB的chunk名不能证明哪个库主导，先核模块图/源码映射和解析执行自耗时。已有路由lazy，不重复建议“加懒加载”；进一步拆包会影响首次操作等待。[AG Modules](https://www.ag-grid.com/javascript-data-grid/modules/)、[Vite异步chunk加载](https://vite.dev/guide/features.html#async-chunk-loading-optimization)（查询 2026-10-25）

若主题/组件挂载轨迹显示AntD运行时样式生成占主要时间，AntD6提供zeroRuntime/静态提取，但须核8主题、动态token、字号和CSS体积，不能默认导入全量静态CSS就更快。[AntD Customize Theme](https://ant.design/docs/react/customize-theme/)（查询 2026-10-25）

## 动画：补齐反馈连续性，不掩盖阻塞

默认方案复用AntD+CSS，不新增Motion/GSAP。AntD已有交互动效，可由theme token motion=false关闭；项目已有hover和reduced-motion CSS，但须核AntD的Modal/Select/Dropdown等JS动效是否随系统设置变化。[AntD主题与动效](https://ant.design/docs/react/customize-theme/)、[MDN prefers-reduced-motion](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-motion)（查询 2026-10-25）

| 操作 | 推荐反馈（设计候选，时长待验看） | 可操作要求 |
| --- | --- | --- |
| 导航 | 先及时更新选中/标题，内容区约120–180ms轻淡入 | 待加载内容明确；不等动画结束才接受输入 |
| 筛选 | 输入即时回显，结果区标明更新中，完成后计数明确 | deferred旧结果可辨；不为每行做入场 |
| 加载/刷新 | 固定几何的局部状态/骨架，已有数据保上下文 | 不反复闪整页，不让延迟spinner冒充不卡 |
| 弹窗/下拉 | 复用AntD焦点/键盘与入退场，必要时统一短时长 | 连续开关可打断，不二次叠加缩放 |
| 选择/保存 | 局部边框/颜色/短淡变，保存中和成功分开 | 成功依实际回执，不用动画替代错误或确认 |

优先transform/opacity，避免宽高/top/left、全屏模糊、全表transition、大批弹性动画和永久will-change；用掉帧与non-compositing轨迹验收。[Chrome团队：高性能动画](https://web.dev/articles/animations-guide)（查询 2026-10-25）。简单状态CSS即可，需要取消/反转/时序控制再用WAAPI并清理；它不会减少同步JS。[MDN WAAPI](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API)（查询 2026-10-25）

同文档document.startViewTransition已Baseline 2025，不应笼统称“尚不成熟”；旧浏览器需检测/无动画回退。React19.3.1实际有ViewTransition导出，react-dom没有startViewTransition导出，后者是浏览器Document方法，不能猜包API。可在轻页面/小边界试，避开全屏大表快照、保活节点重名、焦点异常；动画等更新完成后才开始，修不了更新前长阻塞，不为动效flushSync大表。[MDN startViewTransition](https://developer.mozilla.org/en-US/docs/Web/API/Document/startViewTransition)、[React ViewTransition](https://react.dev/reference/react/ViewTransition)（查询 2026-10-25）

## 字体候选：先比较系统字体，再决定是否值得维护子集

推荐隔离对照系统字体栈，React表面字体网络字节可明确验0；不承诺冷ready或热交互同比改善。Windows可从system-ui、Segoe UI、Microsoft YaHei UI/YaHei等实际字库核实。跨系统字形、字宽、400/500/600层次不同，须核中文/金额符号/负号/小数/全角字符、8主题4字号、CLS及列宽；打印和Excel保持原契约。[字体最佳实践](https://web.dev/articles/font-best-practices)（查询 2026-10-25）

若仍需固定中文字形，候选是允许修改的Source Han Sans/思源黑体+fontTools生成可复现WOFF2分片。OFL1.1允许修改分发，需保版权/许可，注意Reserved Font Name Source的修改命名限制，具体发行包再次核对。[Adobe仓库](https://github.com/adobe-fonts/source-han-sans)、[LICENSE](https://raw.githubusercontent.com/adobe-fonts/source-han-sans/release/LICENSE.txt)、[fontTools subset](https://fonttools.readthedocs.io/en/latest/subset/index.html)（查询 2026-10-25）

子集用通用字符覆盖/界面集，不仅裁当前业务名称，罕见汉字有fallback。unicode-range只要命中一个字符就下载该face整个文件；完整库兜底仍可能因一个全角符号触发。应考虑小符号/数字覆盖、必要字重和清晰回退，比较实际请求数/解析/CLS，不只报字节比例。[MDN unicode-range](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@font-face/unicode-range)（查询 2026-10-25）

## 下一轮最小验证计划

1. 保留原构建、原84样本、固定只读副本及8065运行记录；候选使用独立构建，在已核8065身份后停旧换新或受控同端口切换，任何时刻只保留一个预览，8000不动。本条是后续计划，不自动执行。锁定账号、浏览器、1350×940/DPR1、主题字号、HTTP缓存及CPU/网络条件；冷/热分开，不混统计。
2. 首选库存全部期间、输入、清筛选和滚动；再看通知书↔合同↔库存热切页、详情/Modal、主题/最大字号、规则冷加载。先5次筛查，稳定后至少10次成对对照，报告原始样本、中位、p95估计、最大值；小样本不冒称真实用户分位。
3. Event Timing按interactionId合并离散事件，记录输入等待/处理/呈现；显式16ms阈值，缺entry不等于0。脚本insertText不代表IME，滚动另看Frames/空白/掉帧。[W3C Event Timing](https://www.w3.org/TR/event-timing/)（2026-10-13草案，查询 2026-10-25）
4. Chrome Performance保留主线程/Bottom-up、网络、Layout/Forced reflow、GC、Frames及动画；标记JSON/校验/过滤/列宽完成与正确结果可操作时刻。最终验收用正常生产build，profiling仅归因。[Chrome Performance](https://developer.chrome.com/docs/devtools/performance/reference)（查询 2026-10-25）
5. React Profiler量render/commit和actualDuration；默认生产关闭、有仪器开销，不能替代网络/DOM布局绘制，也不与正常build直接比较。[React Profiler](https://react.dev/reference/react/Profiler)（查询 2026-10-25）
6. 同时报告“下一帧有反馈”和“条件对应完整结果完成”，继续计延后工作/总CPU与第二次输入，Lighthouse和ready只作冷启动/历史代理。

建议验收门槛（需在下一轮范围中确认）：

- 正确性硬门槛：金额、过滤排序、汇总导出等价，草稿/焦点/选择/滚动/账号隔离不退化；失败状态明确。
- 本机代表点击/键入p95实验目标≤200ms，输入回显争取≤100ms；不等同真实用户p75 INP。超标保留剩余段，不改ready定义过关。
- 目标热点布局/测量自耗时及重复工作有可复核下降；不再出现可重复>200ms单任务；完整结果时间/总CPU不超出实验噪声退化，有取舍单独报告。
- 60Hz固定环境连续滚动/开关≥5秒，先争取无>50ms长帧、无空洞/裁金额/焦点跳失；报告掉帧，其他刷新率另设帧预算。
- 规则冷CLS目标≤.1；正常/减少动态效果两种模式可完成同样操作。
- 字体候选验网络0字节；虚拟化候选验DOM随视口而非总行数增长；分页/Worker验契约与端到端收益。
- 完成受影响交互对照后，复用原84样本脚本查全站明显退化；保留较差/失败样本，不据研究启动423/424、生产加载或真实写入。

未做：下一轮产品修改、下一轮候选前后对照、生产/8000操作、业务写入、物理打印/真实IME/系统200%缩放；新增浏览器诊断仅作热点归因。未决：行高候选阅读取舍、Activity第三方兼容、分页新鲜度/导出合同、各候选无Profiler端到端收益。
