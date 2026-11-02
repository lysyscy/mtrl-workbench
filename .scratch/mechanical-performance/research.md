# 大型可编辑机械业务表格：官方性能方案研究

研究日期：2026-11-02。范围：为本次机械页性能调查提供成熟做法和选型依据，不将配置风险直接认定为本项目根因。项目根因以另一条测量工作流的现场数据为准；本文没有运行生产 SQL、修改业务数据或产品代码。

版本基线已从 `apps/frontend/package.json` 核对：React 19.3.1、AG Grid Community/React 36.2.0、TanStack Query 5.104.5、antd 6.6.7、react-virtuoso 4.18.19。研究先查询 Context7，再回到官方原文；AG Grid 当前页面标注 36.2.0，React 文档标注 v19.3，TanStack 页面属于 v5（原 v5 链接会重定向到 latest）。后端方案引用 SQLAlchemy 2.0/PostgreSQL 当前文档，仅作方法依据；没有在本子任务核对已部署后端版本。本文仅是研究交付，按项目活动 Markdown 约定保存，不是可自动清理的运行日志。

## 成熟做法：测量后选择，不超过六项

### 1. 先按业务范围取数，再决定是否按块加载

AG Grid 默认 Client-Side Row Model 一次接收数据，在浏览器执行排序、过滤等操作；正常虚拟化只减少 DOM，并不会省掉下载和持有全部数据的开销。Community 可选 Client-Side 或 Infinite Row Model；Enterprise 的 Server-Side Row Model 才提供服务端分组等更完整能力。官方没有要求一遇到大表就切换模型。[官方：Row Models](https://www.ag-grid.com/react-data-grid/row-models/)

**适用条件与建议（研究推论）**：若机械页实际只操作某项目、月份、用途，优先让后端按这些业务条件筛选，并把同样的条件放进查询缓存 key；如果筛选后仍有明显传输/内存问题，再评估分页或 Infinite。查询函数依赖的变量应进入 query key，才能独立缓存不同范围的数据。[官方：Query Keys](https://tanstack.com/query/v5/docs/framework/react/guides/query-keys)

**局限**：分页/按块之后，筛选、排序、总计、导出必须明确是在全业务范围还是当前块执行；不能用当前已加载行冒充全量合计。按月筛选属于业务接口设计建议，不是引用文档证明的本项目当前事实。是否需要分页，应由响应字节、行数、解析/计算时间和实际使用范围决定。

### 2. 给表格有效的可视范围，保留默认虚拟化

AG Grid 默认行、列虚拟化，只渲染视口附近的单元格；默认 `rowBuffer=10`，在上下各扩展缓冲区，实际像素范围以默认行高计算。[官方：DOM Virtualisation](https://www.ag-grid.com/react-data-grid/dom-virtualisation/)

**关键版本细节**：`domLayout='autoHeight'` 默认没有最大高度，表体会随内容长高并渲染全部行。但 36.2.0 当前官方文档支持主题参数 `autoHeightMaxBodyHeight`：超过上限时改为内部滚动并使用虚拟化。因此不能笼统断言所有 autoHeight 都不支持虚拟化；也不能只给外层容器加 CSS `max-height`，就假定已启用该机制。默认 `normal` 加有效高度是另一条直接路径。[官方：Grid Layout / Auto Height](https://www.ag-grid.com/react-data-grid/grid-size/#minimum-and-maximum-height-with-auto-height)

**适用条件与局限**：实际 DOM 行数随数据量线性增长、长任务主要落在布局/绘制时，优先比较有界表体方案。还要分清 `colDef.autoHeight`（单元格自动行高）与 `domLayout`：列自动行高会增加测量监听，并让这些列持续渲染、停止其列虚拟化。虚拟化不能消除全量数组转换、后端等待或所有行的汇总计算。[官方：Row Height](https://www.ag-grid.com/react-data-grid/row-height/#auto-row-height)

### 3. 用稳定业务行 ID，让编辑只替换变化的数据

为行提供稳定唯一的 `getRowId`，并采用不可变更新：变化行创建新对象，未变行保留引用，列表变化返回新数组。AG Grid 对新 `rowData` 会按 ID 与对象引用推断新增、更新、删除；有 row ID 的新数组并不等于无条件重建整张表。[官方：Updating Row Data](https://www.ag-grid.com/react-data-grid/data-update-row-data/)

增删改量已知时，也可用 `applyTransaction({ add, update, remove })`；官方说明通过 ID 找行比对象引用数组查找更适合大数据。React 侧应稳定 `columnDefs`、对象配置及需要参与网格判断的 callback 引用，避免无意义重置网格状态。[官方：Transactions](https://www.ag-grid.com/react-data-grid/data-update-transactions/)、[官方：React Best Practices](https://www.ag-grid.com/react-data-grid/react-hooks/)

**适用条件与局限**：单格编辑、少量新增/撤销时价值最高。稳定 ID 必须来自真实行身份，不能依赖当前排序序号。transaction 与不可变 `rowData` 是可选更新路径；选哪条要与现有状态主人一致，避免网格内部状态与查询缓存成为两个互不一致的数据源。它们不能自动省去应用自己在每次编辑时进行的全量映射/汇总。

### 4. 保存后定向更新缓存和相关视图，控制失效范围

TanStack Query 支持用 mutation 的服务端响应直接 `setQueryData`，避免立即为同一对象再请求一次；缓存更新必须不可变。若保存响应不足以重建可信列表或聚合，使用按业务范围定向的 `invalidateQueries`，其匹配支持前缀和 `exact`；默认会把匹配项标为过期，并后台重新请求活跃查询。[官方：Updates from Mutation Responses](https://tanstack.com/query/v5/docs/framework/react/guides/updates-from-mutation-responses)、[官方：Query Invalidation](https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation)

**默认机制已经存在**：Query 对 JSON 兼容数据默认做 structural sharing，尽量保留未变引用；其结果最外层对象不稳定，但 `data` 尽可能稳定。`select` 可缩小订阅结果，选择函数引用和原数据都不变时可跳过重复转换。[官方：Render Optimizations](https://tanstack.com/query/v5/docs/framework/react/guides/render-optimizations)

**适用条件与局限**：保存后出现多条重复请求、多个独立区域刷新时，先核 mutation 实际影响哪些查询。金额、归属、月汇总和撤销可能跨行联动，不能为减少请求而漏更新真实依赖。必要的网格显示刷新优先 `refreshCells`（变化检测），`redrawRows` 会把行从 DOM 移除并重建，官方建议仅在前者不适用时使用。[官方：View Refresh](https://www.ag-grid.com/react-data-grid/view-refresh/)

### 5. 只优化测得昂贵的渲染器和计算

AG Grid 官方建议先移除自定义 cell renderer 作对照，再逐个加回定位；纯文本变换可考虑 value formatter，减少额外 DOM。已证实慢的 renderer 可以 `cellRendererParams.deferRender=true`，滚动时先显示骨架，停止滚动后再完成渲染。此举改变呈现时机，并不让昂贵工作凭空消失。[官方：Scrolling Performance](https://www.ag-grid.com/react-data-grid/scrolling-performance/)

React `useMemo` 只在依赖不变的更新中避免重复计算，不能加速首次计算；应先测耗时和依赖变化情况。对于 AG Grid 昂贵 `valueGetter`，Value Cache 默认关闭，可在测得确有成本时评估；数据变化通常会使缓存过期。`valueCacheNeverExpires` 会把失效责任交给应用，官方示例明确可能展示旧计算值，不应作为金额业务的盲目提速开关。[官方：useMemo](https://react.dev/reference/react/useMemo)、[官方：Value Cache](https://www.ag-grid.com/react-data-grid/value-cache/)

如果调用栈主要花在读取元素几何值，应核是否在循环中先改DOM/样式再读尺寸；这会强制浏览器同步计算布局。Chrome团队建议按阶段组织DOM读写，避免每个元素单独触发布局。需要先创建的测量节点可统一创建后再统一读取，并核测量结果不变；不是给循环套一层requestAnimationFrame就能消除循环内部的交错读写。[官方：Avoid large, complex layouts and layout thrashing](https://web.dev/articles/avoid-large-complex-layouts-and-layout-thrashing)

**适用条件与局限**：脚本调用栈显示数值转换、派生数组、renderer 或 getter 占主要时间时再采用。不要因页面引入了 antd/Virtuoso/AG Grid 就断言其必慢，也没有证据要求更换整套技术栈。

### 6. 分层测量，用相同业务场景比较收益

Chrome Performance 可以区分主线程脚本、渲染/绘制、调用栈与交互延迟；React Profiler 的 `actualDuration` 衡量子树本次 render，`baseDuration` 是无 memo 优化时的估计，并不是网络/数据库耗时，也不是整次用户操作总时长。Profiler 有额外开销，普通生产构建默认禁用，需专用 profiling build。[官方：Chrome Performance](https://developer.chrome.com/docs/devtools/performance/reference)、[官方：React Profiler](https://react.dev/reference/react/Profiler)

开发模式和生产模式要分别标记：StrictMode 的额外 render/effect 检查只发生在开发模式；它可以放大现场耗时，但不能据此排除生产页面同样存在低效代码。AG Grid 官方要求用生产模式做性能比较。[官方：StrictMode](https://react.dev/reference/react/StrictMode)、[官方：Scrolling Performance](https://www.ag-grid.com/react-data-grid/scrolling-performance/)

服务端要分 SQL 执行、取回结果、ORM 对象构建和应用处理；SQLAlchemy 官方分别说明这些阶段可能成为瓶颈。只有 SQL 执行确实慢时，才继续看查询计划和索引，避免把请求慢直接等同数据库慢。PostgreSQL 的 `EXPLAIN ANALYZE` 会实际执行语句，需在本任务授权的只读/隔离目标按需使用；本文未执行。[官方：SQLAlchemy Performance](https://docs.sqlalchemy.org/en/20/faq/performance.html)、[官方：PostgreSQL EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html)

## 交给本项目测量来选择

| 观察到的主要证据 | 首选候选 | 要证实的改善 | 不能据此声称 |
| --- | --- | --- | --- |
| 响应大、行数多、解析/持有成本高 | 项目/月/用途服务端筛选；必要时分页/Infinite | 字节、行数、解析时间和峰值内存下降 | 换成 Enterprise 就必然快 |
| 已渲染行接近全部数据，布局/绘制占主导 | 有界表体及虚拟化；收紧自动行高 | 同场景 DOM 数及布局/绘制时间下降 | 后端和数组计算也已优化 |
| 单格保存牵动全行/全页与重复请求 | 稳定 ID/引用；局部更新和定向失效 | 变化行、提交与请求数收敛，金额/汇总仍正确 | 所有刷新都可删除 |
| 脚本主要落在 getter/renderer/派生计算 | 对应局部算法、memo 或呈现延后 | 同交互该调用栈耗时下降 | 普遍加 useMemo 已解决原因 |
| 请求等待为主 | 按层计时，再按证据优化 SQL/ORM/响应 | 对应慢段下降 | 前端虚拟化足以解决等待 |

没有在本文使用任何跨项目宣传跑分或承诺固定提速比例。后续选择应复用同项目、同月份/用途、同数据量和同操作路径的前后证据，并把首次进入、切换筛选、滚动、编辑后保存分别观察。
