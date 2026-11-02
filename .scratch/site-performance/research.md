# 全站 UI 性能：官方方案与本仓库适用边界

研究日期：2026-11-02。任务基线：父任务指定 HEAD `daf8a7fc`；本子任务只读现有源码和官方资料，只写本文，没有运行产品、修改代码、业务写入、提交或部署。已读取安装的 research、Impeccable optimize，以及 `.scratch/mechanical-performance/research.md`；context 已由主任务运行，不重复执行。

版本核对：`apps/frontend/package.json` 为 React 19.3.1、TanStack Query 5.104.5、AG Grid Community/React 36.2.0、Vite 8.3.5。下列 React 官方页当前标注 v19.3，AG 页标注 36.2.0，Query v5 链接重定向至仍标注 v5 的 latest。已用 Context7 核对 React 测量语义，再回到直接官方 URL。

这里采用的命令是 **optimize**。用户语境中的 optimism 按性能优化理解；**optimistic update** 是另一项技术，指 mutation 尚未完成便先更新 UI，不能由命令名称推导出业务授权。[TanStack：Optimistic Updates](https://tanstack.com/query/v5/docs/framework/react/guides/optimistic-updates)

## 1. 先统一证据口径：交互反馈、业务完成、INP 分开记录

INP 衡量页面访问期间合格点击、键盘、触摸交互到下一帧的延迟；通常取最慢交互，大量交互时排除部分异常值。Google 的良好阈值为 200ms，面向用户总体评估看页面访问的 p75。它不是某个自动化脚本从点击到等待“全部可用”的总耗时。[web.dev：INP](https://web.dev/articles/inp)、[Optimize INP](https://web.dev/articles/optimize-inp)

**适用建议（研究判断）**：少量账号的桌面工作台优先沿真实业务路径建立可复现的本地基线：首次进入、保活返回、切换月份/项目、输入、滚动、保存并读回。每条记录相同数据范围、构建模式、视口/字体与缓存状态；分别记录下一帧反馈、请求/响应字节、布局准备、读回完成。自动化 `wait` 还可能包含字体、网络、轮询和应用 readiness，只能命名为其实际测到的等待，不能宣称全站 INP 已通过。少量样本也不足以得出真实用户 p75。

Chrome Performance 可定位主线程、调用栈、网络与交互；React Profiler 的 `actualDuration` 只是本次 React 子树 render，`baseDuration` 是未优化重渲染的估计，二者都不是整次业务耗时。Profiler 有开销，普通 production build 默认关闭，生产测量需专用 profiling build。[Chrome Performance](https://developer.chrome.com/docs/devtools/performance/reference/)、[React Profiler](https://react.dev/reference/react/Profiler)

**本仓库对应**：`grid-layout.ts` 已有 `data-layout-timing`，可解释布局准备；它不是浏览器 INP。将应用时间戳与一次代表性交互 trace 对齐即可定位，不需要为所有页面先装监控平台。性能比较应使用 production 模式，并单独标记诊断 profiling build；AG 官方也要求生产模式比较滚动性能。[AG：Scrolling Performance](https://www.ag-grid.com/react-data-grid/scrolling-performance/)

## 2. 共享表格的共性候选：区分 DOM 虚拟化与全量预计算

AG 默认虚拟化只创建视口附近 DOM。`domLayout='autoHeight'` 默认无最大表体高度；36.2 支持主题参数 `autoHeightMaxBodyHeight`，超出后内部滚动并启用虚拟化。列级 `autoHeight` 是另一项功能：增加单元格高度监听，并关闭对应列的列虚拟化；其懒测高随滚动进行，可能改变滚动范围和位置。[AG：DOM Virtualisation](https://www.ag-grid.com/react-data-grid/dom-virtualisation/)、[Grid Layout](https://www.ag-grid.com/react-data-grid/grid-size/#minimum-and-maximum-height-with-auto-height)、[Row Height](https://www.ag-grid.com/react-data-grid/row-height/#auto-row-height)

**已存在/已完成**：项目已使用稳定行 ID、有界主表与虚拟化；共享 `grid-layout.ts` 已将单行快速判断、签名缓存、128 项 DOM 批测、批量表头读写及无关数值修改复用落实为代码。父任务提供机械页面投影由约 11.23MB 降至约 1.19MB 的先前证据；本文未重测，不把它扩展为其他页面的已证实收益。

**仍适用的检查**：`grid-layout.ts:116–206` 即使表体虚拟化，仍会遍历业务行、构造唯一文本任务并预计算行高；“可见 DOM 少”不能证明这些脚本/字体/测量成本已消失。仅在 trace 显示此段是瓶颈时，再比较更少 wrap 列、固定高度的单行表、按实际依赖失效，以及可接受的按需测高。保留完整文字和稳定滚动属于本产品约束，不能为减少首屏时间直接换成截断。

**重要兼容性风险**：`grid-layout.ts:239–254` 目前对所有 autoHeight 表等待每个业务 ID 都出现在 DOM。若仅增加 `autoHeightMaxBodyHeight`，虚拟化后全部行不会同时挂载，readiness 可能一直不满足。采用此参数必须同步重定义有界表体的完成判定，并验证首屏、滚动、行高和横向滚动条；这只是候选方案兼容性风险，不是已观察到的当前故障。

布局读写交错会触发强制同步布局；批量写入后批量读尺寸是成熟做法。现有批测已覆盖这一方向，不应把套一层 `requestAnimationFrame` 当作消除内部布局往返的证明。[web.dev：Layout thrashing](https://web.dev/articles/avoid-large-complex-layouts-and-layout-thrashing)

## 3. React 更新：保持引用和状态边界，按测量做 memo

`memo` 对经常以相同 props 重渲染、且 render 昂贵的组件最有价值；state/context 更新仍可触发 render，一个始终新建的对象/函数也可能使 memo 失效。官方建议先用 profiler 找热点，避免把全部组件机械包裹。[React：memo](https://react.dev/reference/react/memo)

AG 的稳定 `getRowId` 配合不可变数据会按 ID 和对象引用推断变化：变化行新对象、未变行保留引用、新列表承载列表变化。新数组不等于必须重建整张表。[AG：Updating Row Data](https://www.ag-grid.com/react-data-grid/data-update-row-data/)

**本仓库对应**：`main.tsx:31–50,81–105` 已有 route lazy、访问后保活、页面 memo 和 active/blocked 传递；不能将“尚未采用路由拆包/保活”列为新发现。后续只检查 profiler 证实昂贵的派生数组、共享 context 和 renderer，核实未变行引用是否在投影途中丢失。不要为消除一处 inline function 盲目加 useCallback。

React Compiler 是独立的构建期工具，主要优化更新中的重复渲染和计算；不会自动缓存组件/Hook 外所有函数，不同组件间也不共享同一计算缓存。官方支持渐进采用，并建议保留或谨慎测试现有手动 memo。[React Compiler Introduction](https://react.dev/learn/react-compiler/introduction)

**不宜默认引入**：当前 `vite.config.ts` 仅配置 `react()`，package 未见 compiler 依赖，不能因为使用 React 19 就声称 compiler 已启用；也无需把 compiler 改造或依赖升级作为本次全站优化前置。只有多个页面已测得相同 render 热点、现有局部方案不足时，才独立评估构建兼容性与收益。

## 4. Query 与保存回执：先减少重复取数，保留可信确认

Query 默认将缓存视为 stale，stale 查询可在挂载、聚焦、重连时后台刷新；`staleTime` 控制新鲜期限，`gcTime` 管无活跃观察者数据的保留，不是同一开关。手动定向 invalidation 可标脏并后台重读活跃查询；`staleTime:'static'` 还会阻止手动 invalidation，不适合作为业务表统一提速值。[Important Defaults](https://tanstack.com/query/v5/docs/framework/react/guides/important-defaults)、[Query Invalidation](https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation)

**已存在**：`main.tsx:67` 已关闭聚焦自动重读和 query/mutation retry；业务页多用 `enabled: active`、部分显式 `refetchOnMount:'always'`；公共保存队列及标脏后定向重读属于既有机制。保活页仍挂载，因此 active/enabled 切换和业务标脏才是核查重点，不能只数 mount。

**适用建议（研究判断）**：先按操作关联请求，找同一 query key 的重复重读、无关隐藏页刷新，以及相同投影的重复转换。可对真正稳定的参考数据单独定 staleTime；金额、归属、权限、撤销、累计结果不能全局延长新鲜期限而绕过失效规则。服务端 mutation 响应若已包含完整可信对象，可不可变地 `setQueryData`；若响应不能覆盖列表/聚合的真实依赖，保留定向读回。[Updates from Mutation Responses](https://tanstack.com/query/v5/docs/framework/react/guides/updates-from-mutation-responses)

**optimistic update 边界**：官方乐观缓存方案需要考虑取消并发查询、保存快照、失败回滚及最终重读；重读本身也可能失败。[Optimistic Updates](https://tanstack.com/query/v5/docs/framework/react/guides/optimistic-updates) 本项目 `cell-save.ts:20–22,89–106` 明确“写入获回应→读回→退出已提交草稿”，未知写入结果会停队列。可以立即显示输入草稿/保存中，让用户知道操作已接收；在可信回执/读回前，不应提前显示金额已确认、付款成功或撤销生效。优化不能把读回失败伪装成已核实成功，也不能为省等待自动重试未知写入。

## 5. 页面读取模型与 Excel：复用业务计算，分离呈现成本

成熟读模型可以返回按视图需要裁剪的 DTO/projection，并与写模型共用一个数据库；不要求引入第二数据库、消息系统或 Event Sourcing。官方也明确复杂 CQRS 会增加成本。[Microsoft：CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs#separate-read-models-and-write-models)

**本项目适用推论**：浏览器屏幕与 Excel 应复用领域计算、金额规则和筛选语义，但各自构造需要的呈现结构。页面 JSON 不需要为显示一批行去生成 workbook、解析 XLSX XML、传导出样式或携带各月历史全文。机械 `workbench.py:1027–1083` 的 `page_state` 已按当前月和屏幕消费者投影，完整 state/snapshot 保留导出契约；先复用这条已完成路径的经验，再根据各页实测找仍有相同耦合的接口。不要仅凭响应含多字段就删字段：初始化签名、累计核对、权限和草稿确认也可能是消费者。

## 决策清单

| 状态 | 本次采用方式 | 完成证据/边界 |
| --- | --- | --- |
| 适用 | 固定真实任务路径，分开请求、JS、布局、下一帧和读回等待 | 同输入前后对比；自动化总时长不冒充 INP |
| 已完成，复用证据 | 机械屏幕投影、共享批测、稳定 ID、保活/lazy、保存队列 | 不重复当成全站新优化；逐页确认消费者是否相同 |
| 有证据再实施 | 有界 autoHeight、局部 memo/投影缓存、参考数据 staleTime | 同时核 readiness、引用、失效和业务正确性 |
| 不宜默认引入 | GraphQL、SSR、CDN、worker、分页、compiler、依赖升级、监控平台 | optimize 是候选目录；当前没有证据说明这些是跨页瓶颈的解法 |
| 不宜改变 | 提前确认业务结果、跳过必要读回、对未知写入盲目 retry | 性能收益不替代真实业务回执和授权 |

本文提供映射与方案边界，不把配置形态当根因；全站是否存在同一种瓶颈，应由主任务逐页基线和代表性 trace 决定。
