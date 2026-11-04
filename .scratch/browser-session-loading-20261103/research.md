# 同类数据工作台：加载与占位的实际实现（收敛版）

## 证据边界

只引用官方文档、官方示例与官方 GitHub 源码，URL 于 2026-11-03 实测 HTTP 200。**我未运行任何示例、未打开预览站**：标“主代理实看”的运行时现象为主代理观察，其余是源码/文档文本证据，只支持到“代码这样写”。AG Grid 官网当前 v36.2，本项目所用版本未核，其能力仅作概念参照。

## 案例一：Ant Design Pro / ProTable

- 场景：筛选表单＋分页表格的后台列表页，与本项目台账页最接近。<https://preview.pro.ant.design/list/table-list>、<https://procomponents.ant.design/components/table>
- 首次加载：antd `InternalTable.tsx` 用 `Spin` 包住整张表（含分页），是**覆盖式遮罩而非骨架**；`Table.tsx` 中 `searchNode` 先于 `renderTable()` 渲染，搜索栏不受表格遮罩影响。<https://github.com/ant-design/ant-design/blob/master/components/table/InternalTable.tsx>、<https://github.com/ant-design/pro-components/blob/master/src/table/Table.tsx>
- 切换查询：`useFetchData.tsx` 非轮询请求只 `setTableLoading(true)`，不清 `tableDataList`，旧行保留在遮罩下，旧请求由 `AbortController` 取消。`debounceTime = 20`（第 63 行）是**请求防抖**（合并连续触发），不是加载指示的展示门限，不能据此推出“短等待不显示占位”。<https://github.com/ant-design/pro-components/blob/master/src/table/useFetchData.tsx>
- 后台刷新：轮询走独立 `setPollingLoading(true)`（第 223–225 行），`Table.tsx` 仅追加 `-polling` class，不遮表格——首屏与刷新是两套标志。`Spin` 自带 `delay`（注释 "prevent flush"）与 opacity 过渡，表格行无过渡。<https://github.com/ant-design/ant-design/blob/master/components/spin/index.tsx>
- 路由层：主代理实看 preview 站捕获到**灰色路由骨架**；我此前引用的 ProLayout `PageLoading` 只是居中大号 `Spin`。两者分层不同、版本是否一致未核，**不能用源码推翻现场观察**，本文不对路由层形态下定论。

## 案例二：MUI X Data Grid（服务端数据模式）

- 链接：<https://mui.com/x/react-data-grid/server-side-data/>、<https://mui.com/x/react-data-grid/overlays/>
- 首次加载：`GridLoadingOverlay.tsx` 中 `variant` 默认 `'linear-progress'`、`noRowsVariant` 默认 `'skeleton'`，按 `rowsCount === 0` 二选一：有行用进度条覆盖，无行用骨架。骨架行数 `Math.ceil(viewportHeight / dimensions.rowHeight)`，列宽取 `computedWidth` 并随 `columnResize` 同步，几何与真实表一致。<https://github.com/mui/mui-x/blob/master/packages/x-data-grid/src/components/GridSkeletonLoadingOverlay.tsx>
- 切查询：文档说明默认清空可见行并显示 overlay；开 `dataSourceKeepPreviousData` 则保留旧行、overlay 叠在其上。**其中的失败重置仅是该数据源模式的实现选择**（注释理由：旧行已不满足新控件状态），与“请求失败时是否保留上一次成功结果”是两个不同问题，不能说成“失败清空是共识”。<https://github.com/mui/mui-x/blob/master/packages/x-data-grid/src/hooks/features/dataSource/useGridDataSourceBase.ts>
- 同文档另有 `dataSourceRevalidateMs` 与内存缓存等可选能力；本轮决策不据此引入轮询、缓存或时长默认值。

## 案例三：AG Grid（仅概念参照）

- <https://www.ag-grid.com/react-data-grid/overlays-overview/>、<https://www.ag-grid.com/react-data-grid/loading-rows/>：文档写明设 `loading=true` 显示 loading overlay；Client-Side Row Model 可改用 `loadingRows=true` 显示骨架行（示例 `loadingRows={{ rowCount: 10 }}`）；Server-Side Row Model 自行管理 loading 行。
- 其 GitHub 目录分层在 master 已变动，我未核对与 36.2 对应的实现文件，故不引用具体源码路径；旧版文档“整表遮罩只对某行模型有意义”这类绝对表述不再转述。官网 loading overlay 运行示例我未打开。

## 补充：react-admin

- `DatagridLoading.tsx` 用 `useTimeout(1000)`：1 秒内返回 `null`，之后才渲染**真实表头**＋`nbFakeLines = 5` 行灰块；`Placeholder` 是 `grey[300]` 纯色块，无动画。<https://github.com/marmelab/react-admin/blob/master/packages/ra-ui-materialui/src/list/datagrid/DatagridLoading.tsx>
- `ListView.tsx` 中 `ListToolbar` 与 `Content` 并列渲染（筛选先行、内容独立）；`useListController.ts` 用 TanStack Query 的 `placeholderData: previousData => previousData`，切页/切筛选保留上一份数据。<https://github.com/marmelab/react-admin/blob/master/packages/ra-ui-materialui/src/list/ListView.tsx>、<https://marmelab.com/react-admin/List.html>

## 对照表

| | 首次加载 | 切换查询 | 后台刷新 | 保留旧行 | 过渡 |
|---|---|---|---|---|---|
| ProTable | Spin 遮罩整表，搜索栏可用 | 遮罩下保留旧行，请求防抖＋取消旧请求 | 独立标志，不遮罩 | 是 | Spin opacity／可选 delay |
| MUI X | 无行骨架、有行进度条 | 默认清行；可选保留旧行 | 可选后台重校验 | 可选 | 骨架动画 |
| AG Grid | `loading` overlay 或 `loadingRows` 骨架行 | 未核 | 未核 | 未核 | 未观察 |
| react-admin | 1 秒后出真实表头＋5 行灰块 | 默认保留旧数据 | — | 是 | 无 |

## 有限共性

1. 可核对的三家（ProTable、MUI、react-admin）都把筛选/操作控件与表格内容分开渲染，表格区单独承担加载态；AG Grid 未观察，不计入。
2. 占位形态是**可选集合**而非唯一标准：整表遮罩（antd Spin）、骨架（MUI 无行时、AG Grid `loadingRows`、react-admin 门限后）、进度条（MUI 有行时）。
3. 首屏与后台刷新用不同标志、后者不遮挡可用内容——目前只有 ProTable 源码可证。
4. 请求防抖（合并触发）与展示门限（多快才显示占位）是两件事，不可互相替代。

## 工程建议（技术选择已受托，不再回问）

- 首次进入：表区给稳定占位（固定高度）＋克制 loading；骨架或遮罩属实现自由，不需业务裁定。
- 同条件重访：保留上次结果、后台静默刷新，命中时不遮罩（对应 MUI keepPreviousData、react-admin placeholderData）。
- 换条件：保留页面结构（筛选栏、表头、分页位），旧结果不得静默冒充新条件结果——清空或显著标注二选一，按“旧行是否会被误读为已筛选”判断。
- 失败：区分“本次请求失败”与“上一次成功结果仍在屏”，后者原位提示重试、不清掉已确认可观的数据；不新增自动轮询或自动重试。
- 动效克制：不引入扫光与长过渡；现有保存/草稿保护优先于刷新表现。

## 待核事实（非业务裁定）

1. 本项目实际使用的库与版本，决定上述能力是否可用。
2. Ant preview 的路由骨架属框架模板还是路由层，需与实际版本对齐后才能引用。
3. 台账表格行高是否定长，决定骨架几何能否对齐、是否仍会跳动。

## 未观察

四个示例的运行时观感（闪烁、遮罩透明度、骨架节奏、1 秒门限的实际感受）我均未亲自运行验证；主代理实看结论另行记录，两者不互相替代。
