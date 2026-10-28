# AG Grid Community 自定义集合筛选可行性

核实日期：2026-10-28。用途：为当前材料工作台是否保留 AG Grid、增加类似 Excel 的列筛选提供决策依据。官方资料及隔离合成数据小样已核，业务页接入尚未实施。用户同日确认仅作了解、当前先不做；本effort原地保留为参考，不进入实施排期，后续按用户安排恢复或退出。

## 结论

**可行。** 保留 AG Grid Community，通过官方 Custom Filter 扩展点，用现有 AntD 的 Checkbox、Input、Button 组成 `SetLikeFilter`，可以实现候选值搜索、多选、全选、重置、确定以及多列同时过滤。无需为这些基础能力引入 Enterprise Set Filter、完整 Column Menu 或新组件包。这里的“可行”由官方 API、模块归属和已安装声明支持；不能据此承诺自动拥有 Enterprise Set Filter 的全部细节、性能和 Excel Mode 语义。[自定义筛选](https://www.ag-grid.com/react-data-grid/component-filter/)、[多列过滤](https://www.ag-grid.com/react-data-grid/filtering/)、[模块](https://www.ag-grid.com/react-data-grid/modules/)

## 版本与证据边界

- 本地 `apps/frontend/package.json` 与实际安装包确认：`ag-grid-community` / `ag-grid-react` **36.2.0**、`antd` **6.6.7**、React **19.3.1**。AG Grid 本次访问的官方页面标注 **Version 36.2.0**，故不需要借用更高版本 API；下面关键接口又与本地 36.2.0 `.d.ts` 交叉核对。
- AntD 在线文档本次标注 **6.6.8**，比安装包新一个补丁。Checkbox/Input/Button 导出和 Table 筛选属性另由本地 6.6.7 声明确认，不能把在线页新增属性一概当成本地可用。
- 本地 AG Grid、AntD 是 pnpm patch 安装；已查看补丁。AG Grid 补丁仅修正 `iFrameworkOverrides`、`iCellRenderer` 的可选类型，未修改本次涉及的筛选接口/运行代码；AntD 补丁是 Button/Drawer/QRCode 的类型兼容修正。研究没有修改这些补丁。
- 对应本地证据：项目 [package.json](D:/dev/mtrl-workbench/apps/frontend/package.json:16)、[pnpm-workspace.yaml](D:/dev/mtrl-workbench/apps/frontend/pnpm-workspace.yaml:5)、[AG Grid 补丁](D:/dev/mtrl-workbench/apps/frontend/patches/ag-grid-community@36.2.0.patch:1)、[AntD 补丁](D:/dev/mtrl-workbench/apps/frontend/patches/antd@6.6.7.patch:1)。这些是本机版本证据；API 说明仍以以下官方文档和包声明为依据。

## 已证实的能力与限制

### 1. Set Filter 与 Column Menu 的归属

官方 Set Filter 页面标记 **Enterprise**；示例从 `ag-grid-enterprise` 导入 `SetFilterModule`。官方模块页说明 Enterprise 模块生产使用需要许可证。故不能通过仅安装 Community 而直接启用 `agSetColumnFilter` 获得免费 Set Filter。[Set Filter](https://www.ag-grid.com/react-data-grid/filter-set/)、[列过滤类型与导入示例](https://www.ag-grid.com/react-data-grid/filtering/)、[Enterprise 模块许可](https://www.ag-grid.com/react-data-grid/modules/#enterprise-modules)

官方完整 Column Menu 也标记 Enterprise，但同页明确 Community 可以打开 Column Filters。列筛选弹窗与完整列菜单是两个入口，不能把“无付费菜单”理解为“无法弹出筛选”。[Column Menu](https://www.ag-grid.com/react-data-grid/column-menu/)

### 2. 36.2.0 的 React Custom Filter 接口

| 路线 | 组件和过滤逻辑 | 确定/重置行为 |
|---|---|---|
| 推荐的新路线 | `enableFilterHandlers={true}`；`filter: { component: SetLikeFilter, doesFilterPass }`，或提供自定义 `handler`；组件 props 为 `CustomFilterDisplayProps` | `model` 是已应用模型；`state.model` 是 UI 模型；`onStateChange({ model })` 更新待应用值，`onAction('apply')` 可应用；`onAction('reset')` 可清除该列筛选 |
| 仍支持的传统路线 | 未启用 handlers；`filter: SetLikeFilter`；`CustomFilterProps` 配合 `useGridFilter({ doesFilterPass })` | `onModelChange` 立即应用，因此如要求“确定后生效”，组件须另存草稿，到确定时才调用；传统路线没有新路线的 `onStateChange/onAction` props |

新路线的 `useGridFilterDisplay` 只在需要生命周期等回调时使用，不是把 `doesFilterPass` 塞进该 hook；过滤逻辑归 `filter` 对象。候选值刷新可注册 `onNewRowsLoaded`、`onAnyFilterChanged`。传统路线的 `useGridFilter` 则必须提供 `doesFilterPass`。两条接口均已在本地 36.2.0 声明确认，不能混用。[新路线官方文档](https://www.ag-grid.com/react-data-grid/component-filter/)、[传统路线官方文档](https://www.ag-grid.com/react-data-grid/component-filter-legacy/)

上述 `doesFilterPass` 本地行过滤用于 **Client-Side Row Model**。如果未来改为服务端或无限行模型，需要由服务端执行相应筛选，不能宣称仅有自定义 UI 就能筛全库。[传统路线对 Row Model 的说明](https://www.ag-grid.com/react-data-grid/component-filter-legacy/#filter-callbacks)

按模块拆分注册时，集合筛选需要 Community 的 **`CustomFilterModule`**，本地行模型需要 **`ClientSideRowModelModule`**。官方新路线示例就是从 `ag-grid-community` 导入这两者；也可沿既有 `AllCommunityModule` 注册方式，它包含所有 Community 模块，无需重复注册。注册可通过 `ModuleRegistry.registerModules(...)` 或传给 grid 的 modules。无需导入 `SetFilterModule`、`ColumnMenuModule`。[官方模块注册](https://www.ag-grid.com/react-data-grid/modules/)

本地包声明/源码交叉核对位置：

- [React interfaces.d.ts](D:/dev/mtrl-workbench/apps/frontend/node_modules/.pnpm/ag-grid-react@36.2.0_react-_9f3e6a663d6fca4cc80b0e3914a7d98b/node_modules/ag-grid-react/dist/types/src/shared/customComp/interfaces.d.ts:20)：`CustomFilterProps`、`CustomFilterDisplayProps`；同文件 145、147 行为两个 hook。
- [Community iFilter.d.ts](D:/dev/mtrl-workbench/apps/frontend/node_modules/.pnpm/ag-grid-community@36.2.0_pa_591e62fd317466cd55fb138a9f8b920e/node_modules/ag-grid-community/dist/types/src/interfaces/iFilter.d.ts:79)：`ColumnFilter`；222 行起为 action、buttons，325 行起为 display props。
- [Community filterModule.d.ts](D:/dev/mtrl-workbench/apps/frontend/node_modules/.pnpm/ag-grid-community@36.2.0_pa_591e62fd317466cd55fb138a9f8b920e/node_modules/ag-grid-community/dist/types/src/filter/filterModule.d.ts:15)：`CustomFilterModule`。包内 `dist/package/main.esm.mjs` 的 `CustomFilterModule` 依赖 `ColumnFilterModule`，后者提供 `showColumnFilter/hideColumnFilter` 和筛选弹窗工厂。

### 3. 免费筛选弹窗入口

优先沿默认列头的筛选按钮打开自定义列筛选；不要设置 `suppressHeaderFilterButton: true`。如果确需自定义列头，官方 header props 的 `showFilter(buttonElement)` 可以锚定按钮；外部按钮也可调用 `api.showColumnFilter(colKey)`，关闭用 `api.hideColumnFilter()`。不需要为此启用完整 Column Menu。[默认列头模板、showFilter](https://www.ag-grid.com/react-data-grid/column-headers-components/)、[列筛选弹窗 API](https://www.ag-grid.com/react-data-grid/column-menu/#column-menu-api--events)

### 4. 数据源与候选值语义

官方保证：同一 grid 可以同时启用多列过滤，最终行必须通过**每一列**的过滤。对于自定义过滤器，`doesRowPassOtherFilter(node)` 专门回答该行是否通过“除当前列外”的其他过滤；`onAnyFilterChanged` 可刷新可选值。[多列 AND 规则](https://www.ag-grid.com/react-data-grid/filtering/)、[传统接口参数](https://www.ag-grid.com/react-data-grid/component-filter-legacy/#filter-props)

以下是由接口推导的实现选择，需在实施规格中明确，**不是 Community 自动提供的 Set Filter 行为**：

1. **候选全集**：完整本地 `rowData` 去重适合当前客户端全量加载前提；分页、已过滤的 displayed rows、DOM 当前可见行都不能当全集。也可按官方建议 `api.forEachLeafNode` 遍历本地行。[Accessing Rows](https://www.ag-grid.com/react-data-grid/accessing-data/)
2. **联动候选值**：若仿 Excel，可遍历全部 leaf nodes，再保留 `doesRowPassOtherFilter(node)` 为真的行，取该列值去重。不能简单从“所有筛选后的可见行”取值，否则当前列自己会把未选项删掉，用户难以扩大选择。也可以选固定全集，只让最终行联动；这是两种不同 UX。
3. **统一取值与键**：候选构建和 `doesFilterPass` 应使用同一值提取、空值和比较规则。列有计算值/`filterValueGetter` 时，不宜硬编码 `row[field]`。键与展示标签分开，避免相同名称、数字 `1`/字符串 `"1"`、空值或对象被误合并。官方 Set Filter 对空值、字符串 key、对象 key/label 有专门语义，可作设计参照，但自定义组件需要自行实现。[Set Filter 值规则](https://www.ag-grid.com/react-data-grid/filter-set-filter-list/)
4. **明确模型**：可约定 `null` 为不筛选；已启用模型中的空选择数组为零行；同列多值 OR、多列 AND。全选究竟是所有候选还是搜索结果、搜索是否只改变候选列表、重置是否立即生效、数据刷新时失效选项如何保留，必须单独确定。不要把“选择了当前候选全集”直接等同 `null`：取消其他列条件或增加新行时，两者可能产生不同结果。
5. **草稿与已应用值**：搜索和勾选只更新草稿，确定才应用；关闭重开与外部模型重置需回显一致。可让 AntD Button 调用新路线 `onAction`；若同时配置 AG Grid 自带 `filterParams.buttons`，会由 grid 渲染按钮，应避免两套按钮重复。无需假定它自动有 Enterprise Excel Mode 的所有联动行为。[Applying Filters](https://www.ag-grid.com/react-data-grid/filter-applying/)

### 5. AntD 控件与替换表格库

Checkbox、Input、Button 均由已安装 `antd` 直接导出：可用 `Checkbox` / `Checkbox.Group` 组织多选，用 `indeterminate` 表示部分选择；Input 放候选搜索文本，Button 执行全选/重置/确定。搜索、候选去重与筛选模型由组件实现；基础组合无需增加 npm 依赖。[Checkbox](https://ant.design/components/checkbox/)、[Input](https://ant.design/components/input/)、[Button](https://ant.design/components/button/)、[本地 6.6.7 导出](D:/dev/mtrl-workbench/apps/frontend/node_modules/.pnpm/antd@6.6.7_patch_hash=872ac_cf0e9480465d044502ed4e2d0f0c143d/node_modules/antd/es/index.d.ts:23)

若另行决定替换整个表格，AntD Table 已内置列 `filters`、`filterMultiple`（默认 true）、`filterSearch`，并通过 `onFilter` 判断本地行；也支持 `filterDropdown` 自定义面板。本地 6.6.7 `es/table/interface.d.ts` 115–124 行确认属性存在。但“有内置筛选”不能证明替换现有表格总体更划算，本次未审计编辑、虚拟化、列宽、合计和现有交互迁移成本。[AntD Table](https://ant.design/components/table/#column)

## 本次完成范围

官方资料分工完成文档与本地版本声明交叉核实，只新增此研究记录；主任务随后补做下述隔离小样。主要版本风险是 AntD 在线页已为6.6.8，以及未来AG Grid在线文档会滚动升级；实施时继续以项目锁定版本的声明为准。

## 本地运行验证与接入判断

本次主任务在`571549a5`及其当时未提交工作区上只读核源码；表格统一任务正在修改产品及依赖文件，本报告不接管这些改动。小样独立打包已安装的AG Grid Community36.2.0、React19.3.1及AntD6.6.7，单个本地HTML运行，不开放HTTP或借用真实副本。未导入Enterprise包。

505条合成数据的8组交互断言完成：候选来自完整数据并含未渲染的屏外值/空白、选择草稿确定后生效、多列AND与筛选事件同步合计、候选值排除本列条件而随其他列联动、搜索后全选搜索结果、空白独立筛选、全部取消得到零行，以及清除/序列化模型恢复。最终DOM和API复核为原数组505行、显示ID2一行、金额200、筛选模型为甲供应商AND机械，运行错误0。

原交互脚本在全部行为断言后因`Page.captureScreenshot`超时退出1；随后独立DOM/模型复核退出0。截图不记成功，不把该脚本整体报为退出0。此证据只证明合成小样的接口和基础行为，不代表业务页已完成接入或回归。[运行回执](D:/dev/mtrl-workbench/.artifacts/archive/share-feasibility/20261028-01/reports/poc-result.json)

小样还确认了两个版本接缝：遍历`api.forEachNode`需要`RowApiModule`（本项目已注册）；36.2的新式`doesFilterPass`通过`params.handlerParams.getValue(node)`取值，不能误用显示组件参数上的`getValue`。项目共用入口目前还需按采用路线接入`CustomFilterModule`。[现有模块注册](D:/dev/mtrl-workbench/apps/frontend/src/grid.ts:2)

### 实际成本主要在业务范围接线

- **通知书**：当前`shown`在React侧产生，合计、隐藏勾选计数和表头全选消费它；导出ID却经`forEachNodeAfterFilterAndSort`取得。只让网格新增过滤会使这些集合分离。应统一当前有效业务集合，再供合计、可见全选、批量操作准入和导出说明消费。[列表/合计](D:/dev/mtrl-workbench/apps/frontend/src/notices.tsx:79)、[导出ID](D:/dev/mtrl-workbench/apps/frontend/src/notices.tsx:197)
- **集采**：合计与列表外已选数量也由`shown`计算，同样需要同步处理。[集采范围](D:/dev/mtrl-workbench/apps/frontend/src/contracts.tsx:72)
- **库存**：已存在自有多列条件和多选值清单，候选取自完整粗筛集合，可复用思路；目前`values:[]`表示不筛选，且候选排除了空白，不能直接充作Excel式全部取消/空白过滤。当前库存导出明示按单月全部项目、不受页面列筛选影响，这一口径应保留。[现有筛选](D:/dev/mtrl-workbench/apps/frontend/src/inventory-api.ts:63)、[候选](D:/dev/mtrl-workbench/apps/frontend/src/inventory.tsx:56)、[导出口径](D:/dev/mtrl-workbench/apps/frontend/src/inventory.tsx:95)

建议先选一个普通业务页接入并核上述集合，再复用UI；当前没有为了这项功能更换整套表格库的技术必要。基础组件的开发量较小，但分享中“改造成本低”不能直接覆盖业务合计、选择、导出、草稿/焦点及列宽的接入成本。全量Set Filter的复杂模式、超大候选集性能和未来服务端分页不在本次小样的证明范围。

### AntD补丁版本安排

官方最新稳定版为6.6.8，本地为6.6.7。用户随后明确“先不升级，回头自己安排”，本次保持依赖。未来升级还要核本地6.6.7的TS7兼容补丁能否退出或需迁移，不能只改版本号。[官方6.6.8发布](https://github.com/ant-design/ant-design/releases/tag/6.6.8)、[变更记录](https://ant.design/changelog/)

本轮浏览器任务空间已关闭，临时源码/构建已释放；必要运行证据保留至2026-11-27。本轮run-closed的scope检查无错，总体退出1来自已有notice-dialog-reuse及process-material-20261027-01归档元数据/目录问题，实际结果保存于本轮归档reports/workspace-check.json。本研究记录留供方案裁定，不据此开始业务页改造。
