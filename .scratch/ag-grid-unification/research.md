# AG Grid 全表统一：能力、限制与取舍研究

日期：2026-10-28。范围：只读查阅官方资料、本地已安装包及共享网格入口；本文件是研究材料，未实施迁移、未运行应用/数据库/测试，未决定业务版式或许可采购。全仓表格入口清单由主任务另行盘点。

## 主结论

1. **以已安装 AG Grid Community 36.2.0 作为业务数据表的统一底座可行。** 普通编辑、分组表头、固定列、分页、行拖动事件、列状态 API 和虚拟化已有原生能力。默认不需要新增表格库或购买 Enterprise。[Community 与 Enterprise](https://www.ag-grid.com/react-data-grid/community-vs-enterprise/)
2. **“所有表用 AG Grid”可以作为技术目标，但无法同时承诺所有工作表的 body 合并、文字选择复制、直接编辑、固定区域与排序筛选均保持原样。** 新 `spanRows` 有严格的功能组合约束；旧 `rowSpan` 仍在 36.2.0 中，但采用固定行高覆盖机制。具体证据见下表及“合并边界”。
3. **全 AG 路线优先采用分组表头＋标准数据行＋重复标签＋应用计算的 pinned 合计。** 用原生网格的数据模型代替工作表式 body 合并，是本研究建议；它会改变报表视觉结构，应由用户裁定，不能据此直接改版。保留合并若是硬要求，则逐表证明组合可行，不能套全局开关。
4. 成熟第一方指南允许简单展示表、数据表、数据网格共存，强调按交互和数据规模选型。因此“统一组件/交互/状态”与“每张表必须同一渲染器”是两个不同决策。若全 AG 的代价集中在极少量固定报表，保留这些例外是有来源支持的备选，不是默认另造网格。见“行业实践”。

## 版本与本地核实

- [本仓 package.json](D:/dev/mtrl-workbench/apps/frontend/package.json:19) 固定 `ag-grid-community` 与 `ag-grid-react` 为 `36.2.0`；本地两个 `node_modules/*/package.json` 的 `version` 也均为 `36.2.0`。
- 本次访问的 AG Grid 当前官方 React 文档页面标注 **Version 36.2.0**，与已安装版本一致，不需要以升级为研究前提。动态官网以后可能变化，实施时继续以锁定包和对应文档为准；旧 `rowSpan` 文档特别注明档案版本，不能混为当前 `spanRows`。[当前行合并文档](https://www.ag-grid.com/react-data-grid/row-spanning/)
- [grid.ts](D:/dev/mtrl-workbench/apps/frontend/src/grid.ts:10) 已注册 `CellSpanModule`、`RowAutoHeightModule`、`PinnedRowModule`、`CustomEditorModule` 等；第 17 行全局配置 `enableCellTextSelection=true`、`ensureDomOrder=true`。**包支持某能力，不等于本仓已经注册全部相关模块或已经完成适配。** 例如原生文本/数字编辑器、分页与拖行模块应按实际采用核对注册。[官方模块说明](https://www.ag-grid.com/react-data-grid/modules/)

## 能力、限制与许可对照

以下“Community”表示能力属于已安装社区包；使用仍须注册相关模块和正确配置。标注“本地源码”表示验证器/实现事实，不表示已经做浏览器组合试验。

| 需求 | 原生能力与版本证据 | 实际约束与本仓建议 | 许可 |
|---|---|---|---|
| 普通可编辑明细 | `editable`、内置编辑器、自定义 React 编辑器；`readOnlyEdit` + `cellEditRequest` 可把状态交给应用。[保存值](https://www.ag-grid.com/react-data-grid/value-setters/) | 网格结束编辑不等于服务保存成功。保留现有草稿、校验、保存、失败回退和权限语义；不要把网格 `applyTransaction` 当数据库事务。 | Community |
| 分组表头 | `ColGroupDef.children`，可用 `marryChildren` 保持组内列相邻。[列组](https://www.ag-grid.com/react-data-grid/column-groups/) | pinned 边界会把同一表头组拆开；移动列也能拆组。固定报表应限制随意移列/固定，不能把分组表头当 body 合并。 | Community |
| 横向 body 合并 | `colSpan` 回调返回列数。[横向合并](https://www.ag-grid.com/react-data-grid/column-spanning/) | 不能跨 left/center/right pinned 区域；同一列不能同时 `colSpan` 与新 `spanRows`；矩形范围选择受限。合计标签不宜横跨固定区边界。 | Community |
| 新纵向 body 合并 | `enableCellSpan` + `spanRows` 合并相邻叶子行；回调可限定业务边界。[纵向合并](https://www.ag-grid.com/react-data-grid/row-spanning/) | 本地验证器声明：合并列不能同时编辑、拖行、`colSpan` 或旧 `rowSpan`；网格级文字选择/范围选择等还存在冲突。详细见下节。 | Community |
| 旧纵向 body 合并 | 当前类型仍有 `rowSpan`；当前实现保留 `legacyApplyRowSpan`。[本地类型](D:/dev/mtrl-workbench/apps/frontend/node_modules/ag-grid-community/dist/types/src/entities/colDef.d.ts:944) | 需 `suppressRowTransform=true`；按默认行高 × 行数覆盖其它行，不适合动态行高/autoHeight；排序筛选后边界由应用承担。不能把新 API 的兼容性直接套给它。 | Community，但不是默认优先方案 |
| 行拖排序 | managed 原生调整显示顺序；unmanaged 只发事件，由应用决定顺序。[managed](https://www.ag-grid.com/react-data-grid/row-dragging-managed/)、[unmanaged](https://www.ag-grid.com/react-data-grid/row-dragging-unmanaged/) | managed 限 Client-Side，无分页、无活动排序/过滤。外部先筛选再传 `rowData` 时，AG 不知道缺行，仍可能允许拖动；需要沿用完整业务列表/稳定 ID 的重排语义。 | Community |
| 弹窗小表/分页 | `domLayout='autoHeight'` 适合少量行；原生分页可限制显示量。[布局](https://www.ag-grid.com/react-data-grid/grid-size/)、[分页](https://www.ag-grid.com/react-data-grid/row-pagination/) | autoHeight 无默认高度上限，会渲染所有行；大弹窗列表应固定/限制高度并保留虚拟化或使用明确分页。`paginationAutoPageSize` 以默认行高估计，与动态行高混用不能恰好填满。 | Community |
| 行高与虚拟化 | normal 布局原生虚拟化；单列 `autoHeight` 依据内容测高。[行高](https://www.ag-grid.com/react-data-grid/row-height/) | autoHeight 列停用该列的列虚拟化并增加测量；懒测高会改变滚动范围/位置。只给确实多行的列开启。Infinite/Viewport 不支持可变行高。 | Community 基础能力；其它行模型另核 |
| 行选择、文字选择、复制 | 常规行选择与浏览器文字选择可用。`enableCellTextSelection=true` + `ensureDomOrder=true` 采用浏览器文字复制。[剪贴板](https://www.ag-grid.com/react-data-grid/clipboard/) | 鼠标选中文字与 Excel 式范围选择不同；Community 不自带 Enterprise 级范围复制粘贴。虚拟 DOM 下也不能默认承诺一次浏览器选择覆盖所有未渲染单元格。新 `spanRows` 与本仓文字选择默认值冲突。 | 文字选择 Community；Cell Selection/增强 Clipboard 为 Enterprise |
| 键盘默认行为 | 原生箭头移焦点，Enter/F2 编辑，Tab 接受值并跳下个单元格。[键盘](https://www.ag-grid.com/react-data-grid/keyboard-navigation/)、[编辑启停](https://www.ag-grid.com/react-data-grid/cell-editing-start-stop/) | 维持本仓鼠标和普通文本输入基线；浏览器/组件默认行为沿项目规则自然保留，不恢复自写跨格键盘体系，也不额外全局拦截。仅遇真实编辑器冲突时采用官方 suppress/focus API，须验证编辑器内正常输入。 | Community |
| 数字与中文编辑 | 原生数字编辑器有 min/max/precision/step/preventStepping；文本编辑器可复用。[数字编辑器](https://www.ag-grid.com/react-data-grid/provided-cell-editors-number/)、[编辑组件](https://www.ag-grid.com/react-data-grid/cell-editors/) | 内置 number 不能替代金额精度、空值、非法字符与后端契约；沿用现有 Decimal/字符串语义。中文 IME 首键、候选确认 Enter、组合中失焦保存的具体行为未由本次文档证明，列入代表性最小试验。 | Community；Rich Select 另属 Enterprise |
| 外部草稿与整单保存 | `readOnlyEdit` 让应用控制更新。[保存值](https://www.ag-grid.com/react-data-grid/value-setters/) | 复用业务草稿作为真源；触发保存前结束/提交当前编辑器值，再走现有业务接口。AG 的批量编辑 API 只是 UI 待提交值，也不等于业务事务。[Batch Editing 许可与语义](https://www.ag-grid.com/react-data-grid/cell-editing-batch/) | 外部状态 Community；原生 Batch Editing 为 Enterprise |
| 列状态持久化 | `getColumnState/applyColumnState/resetColumnState` 可管理宽度、顺序、可见性、固定与排序状态。[列状态](https://www.ag-grid.com/react-data-grid/column-state/) | 存储位置由应用负责。建议稳定 `colId`、视图/用户/状态版本分区；只恢复获准属性，不能从旧状态恢复报表禁用的排序、移列/隐藏。`undefined` 为不改，`null` 为清除，宽度不能为 null。 | Community API；现成高级列工具面板为 Enterprise |
| pinned 合计 | 用 `pinnedBottomRowData` 传应用已算合计。[固定行](https://www.ag-grid.com/react-data-grid/row-pinning/) | 直接提供 pinned 数据不参与排序、筛选、分组和行选择；应用必须定义“全部合计”还是“筛选合计”并主动更新，不能误以为自动聚合。无需采购聚合模块。 | Community |
| 打印布局 | `domLayout='print'` 让网格完整展开供浏览器打印。[打印](https://www.ag-grid.com/react-data-grid/printing/) | 仅 Client-Side；不虚拟化行列，大数据可能卡住；pinned 列在打印布局不固定。它不保证业务模板分页、签字栏、合并矩阵等格式。工作界面替换不应自动替换已有模板导出。 | Community |
| CSV 与 Excel | Community 提供 CSV；内置 `.xlsx` Export 是明确 Enterprise 能力。[版本差异](https://www.ag-grid.com/react-data-grid/community-vs-enterprise/)、[Excel Export](https://www.ag-grid.com/react-data-grid/excel-export/) | 不能因“使用 AG”默认接入需商业许可的 API。优先复用已有业务导出；即使有 Enterprise，默认导出也受当前排序、筛选、可见列影响，renderer 不是导出值。 | CSV Community；内置 Excel Enterprise |

## 合并边界：必须分别判断三个 API

### 新 `spanRows`

官方 36.2.0 正文说明它合并**相邻叶子行**，可与单元格 `autoHeight` 同用；内容超过合并行总高时，额外高度加到合并最后一行。它不是“所有纵向合并都不支持动态行高”。[当前官方说明](https://www.ag-grid.com/react-data-grid/row-spanning/)

但本地 36.2.0 验证器比正文列出了更多组合限制：

- 列级依赖：`editable`、`groupRowEditable`、`rowDrag` 只能 false/未设；`colSpan`、`rowSpan` 必须未设。
- 网格级冲突：`cellSelection`、`rowDragEntireRow`、`enableCellTextSelection`；特定单选点击选择配置也会警告。
- `enableCellSpan` 必须在创建时启用；支持 Client-Side/Server-Side，不能推导 Infinite/Viewport 可用。

证据：[本地 colDefValidations](D:/dev/mtrl-workbench/apps/frontend/node_modules/ag-grid-community/dist/ag-grid-community.js:46840)、[行模型校验](D:/dev/mtrl-workbench/apps/frontend/node_modules/ag-grid-community/dist/ag-grid-community.js:47747)。这些是源码声明的不兼容组合；本次没有运行这些组合，也没有据此断言它们必定报错或必定视觉损坏。

纵向合并缓存按 top/center/bottom 分区构建，因此不能把它当作可以跨 pinned 行区的长矩形；横向列固定则由左右独立容器承载，不等于纵向合并被一概禁止。[本地 RowSpanService](D:/dev/mtrl-workbench/apps/frontend/node_modules/ag-grid-community/dist/ag-grid-community.js:78400)

相同标签在排序/筛选后可能变成不同的相邻关系；回调至少要按真实业务分组 ID 判断，不能只比较显示名称。固定报表矩阵的行列若具有含义，应禁用破坏结构的默认排序、过滤、移列与旧状态恢复。这是由相邻合并模型和固定矩阵语义推导的建议，不是 AG 禁止所有排序筛选。

### 旧 `rowSpan`

36.2.0 类型仍保留 `rowSpan`，源码验证要求 `suppressRowTransform=true`；实现函数名为 `legacyApplyRowSpan`，高度为默认单行高 × `rowSpan`。新 `spanRows` 的 `enableCellTextSelection` 冲突校验不能直接外推为旧 `rowSpan` 也有同一校验。[类型](D:/dev/mtrl-workbench/apps/frontend/node_modules/ag-grid-community/dist/types/src/entities/colDef.d.ts:944)、[验证器](D:/dev/mtrl-workbench/apps/frontend/node_modules/ag-grid-community/dist/ag-grid-community.js:46829)、[实现](D:/dev/mtrl-workbench/apps/frontend/node_modules/ag-grid-community/dist/ag-grid-community.js:50406)

官方旧 32.0.0 档案说明：覆盖单元格仍存在、焦点可能进入隐藏格；需开发者保证不越过末行并处理背景；动态行高/autoHeight 不支持；排序筛选及范围选择有约束。这里只将档案用作旧机制解释，当前固定高度算法已由 36.2.0 本地源码核实，其余组合仍需最小试验。[官方旧机制档案](https://www.ag-grid.com/archive/32.0.0/react-data-grid/row-spanning/)

因此旧 API 可作为少量固定行高报表的候选原生方案，但不能仅因没有新验证警告就认定它能无损兼容文字选择、虚拟滚动、编辑、pinned 和打印。默认不新增自写 DOM 覆盖层来绕过限制。

### `colSpan`

当前官方明确：横跨 pinned 区域的 span 会被限制在当前区域；与同列 `spanRows` 互斥。文档没有把“旧 `rowSpan` 与 `colSpan`”列作同一项互斥，不应混写，但这也不是复杂二维合并在各种交互组合下完全受支持的保证。[横向合并约束](https://www.ag-grid.com/react-data-grid/column-spanning/)

## 全 AG 目标下的优先路线

建议统一已有 `grid.ts` 的主题、尺寸约定、文字选择、编辑接入、空状态与列状态使用方式；让业务页面提供数据、列定义、权限、草稿及保存操作。优先使用官方能力，封装只承担本项目重复契约，不重做虚拟化、排序引擎、选区或编辑生命周期。

对于工作表式矩阵，若用户接受版式调整：

1. **列结构放分组表头。** 用 `children` 表达指标组；固定区边界与组边界一致，必要时禁止移列/改变固定状态。[原生列组](https://www.ag-grid.com/react-data-grid/column-groups/)
2. **body 一行一个稳定业务记录。** 分类/项目/期间等标签逐行重复；需要视觉分隔时用行样式和明确标签，不隐藏真实数据。重复标签会增加文字，但无需合并缓存，也不与普通文字选择、编辑及虚拟化发生上述冲突。这是设计建议。
3. **合计用 `pinnedBottomRowData`。** 应用计算现有业务口径，标签写“合计”或“筛选合计”，不依赖 Enterprise `aggFunc`、Row Grouping 或 Grand Total 功能。[原生固定数据行](https://www.ag-grid.com/react-data-grid/row-pinning/)
4. **固定报表禁用自由排序筛选，清单表按原业务保留筛选。** 如果一个分类块有小计和明细的固定顺序，仅对单独明细随意排序会破坏结构；不要为了统一参数全开 `sortable/filter`。
5. **打印/正式导出继续遵守模板契约。** UI 网格适配不强制业务成品长成同一个网格；需要保留原合并模板时，让原导出路径承担文档结构。这是建议，未改变本仓任何导出实现。

该路线全部可由现有 Community 包承担，但**属于 UI 版式决策**，尤其是重复分类标签、取消 body 合并、合计位置变化，需先把代表界面差异交由用户裁定。保留精确原版式时，逐表评估原生 span，而不是默认开企业版或改组件库。

## 可信第一方实践：统一并不必然要求一个渲染器

| 来源 | 第一方实际指导 | 对本仓的启示（研究建议） |
|---|---|---|
| [MUI Table 指南](https://mui.com/material-ui/react-table/) | 同时提供接近原生 HTML 的 Table 与结构更严格、适合大量表格数据的 DataGrid；Table 页面本身包含合并单元格示例。 | 同一设计系统可以按数据结构选择渲染器。已有 AG 足以承担主数据表，不需要为了简单合并报表新增 MUI。 |
| [IBM Carbon Data table](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines) | 按用户需要附加功能；工具栏集中操作、搜索、过滤、显示设置；要求尺寸保持一致，并明确它不是电子表格应用的替代。 | 更值得统一的是表格周边操作、视觉密度和可预测行为，避免每张小表都强加全套网格控制。 |
| [Supabase Design System Tables](https://supabase.com/design-system/docs/ui-patterns/tables) | 明确区分 Table、Data Table、Data Grid；只有确需虚拟化、列宽调整、复杂编辑时才用 Data Grid，其余采用更简单灵活的数据表。 | 行业成熟路线允许少数静态报表例外；若用户仍选全 AG，则应明确接受标准行结构和对应体验取舍，而非宣称所有表天然等价。 |

Supabase该页“Future”同时表达了未来收敛到单个TanStack Data Table的意向，包含虚拟化、列宽和编辑插件；这是其公开规划，不能说成已经落地的统一组件或通用性能结论。它说明减少重叠实现是合理目标，也不能据此推导本仓应换库。对本仓而言，复用现有AG底座与重新组装一套网格的成本应分别评估。[原文规划](https://supabase.com/design-system/docs/ui-patterns/tables#future)

补充标准证据：W3C APG 区分静态 table 与交互 grid；grid 带焦点管理及方向键导航责任，table 中按钮/输入则沿页面 tab 序列。它没有要求所有表格必须升级成 grid，也不支持只给静态表添 `role=grid` 而不提供对应行为。[Table pattern](https://www.w3.org/WAI/ARIA/apg/patterns/table/)、[Grid pattern](https://www.w3.org/WAI/ARIA/apg/patterns/grid/)

以上来源证明设计取舍有成熟先例，不证明市场普及率，也不构成本项目必须采用其库或全套交互的要求。

## 实施前最小验证项

本轮仅提出验证题，不创建原型、不新增长期测试：

| 代表场景 | 应观察的具体结果 |
|---|---|
| 一张普通可编辑明细表 | 中文 IME 候选确认不误保存；负数/小数/空值不变义；点击保存能拿到尚在编辑器中的最后值；失败后草稿及显示一致。 |
| 一张最复杂矩阵 | 先比较标准行路线与原版式的信息完整性；若保留 span，分别验证跨度/pinned 边界、滚动、行高、文字选择与打印，不混用新旧 API 的结论。 |
| 一张有业务顺序的拖行表 | 无筛选完整顺序、外部筛选子集、活动排序、分页时分别明确能否拖动；保存的 ID 顺序与完整业务列表一致，失败可回退。 |
| 一张最大弹窗列表 | 正常高度、缩放与窄窗口下可读可选，表尾按钮可达；验证关闭再打开状态、分页与筛选后的选择身份。autoHeight 不把整个大列表一次展开。 |
| 列状态恢复 | 新增/删除列后回退正常；同名不同表不串状态；固定报表不能恢复破坏结构的历史顺序、隐藏或排序。 |
| 普通输入基线 | 网格自带箭头/Tab/F2 等行为与项目约定协调；输入框内移动光标、中文组合与正常 Tab 离开不受错误拦截。 |

不将上述题目理解为已通过。是否采用旧 `rowSpan`、是否改变报表版式、是否保留少数展示表例外，均尚待主任务结合完整入口盘点及用户目标作出结论。

## 研究动作与资料局限

执行了：读取适用仓库/公共指引、实际 package.json 与安装包版本、`grid.ts`、36.2.0 类型/验证器/合并实现；查阅 AG Grid 官方当前文档、旧机制档案及 3 份第一方组件指南和 W3C APG；保存本文件。

没有执行：产品代码/依赖/正式规则修改、服务/数据库操作、真实业务写入、浏览器原型、运行测试、Git 暂存/提交/推送。没有读取或修改他人在途文件及 `.tmp-fees-width.py`。本文件不声明全仓已盘点数量、迁移数量、性能通过或用户验收。

最大资料局限是：官方功能正文没有完整列出所有组合限制，因此已补充实际版本源码；源码校验仍不能替代真实浏览器中的 IME、文本选择、跨区滚动与复杂报表验证。Community 许可和 Enterprise 功能归属依据官方版本对照及各功能页，本研究不估算采购价格。
