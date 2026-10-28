# AG Grid 全量替换盘点与路线

2026-10-28。状态：分析完成，尚未实施迁移。用途：供用户确认迁移路线、代表版式和后续批次；实施规格吸收后退出本调查材料，历史由 Git 保留。

## 结论与推荐

建议以现有 **AG Grid Community 36.2.0** 完成当前 React 应用的业务表格统一，不增加第二个表格库，不默认采购 Enterprise。盘点覆盖侧栏注册的15个页面及其弹窗、子表、确认/回执与预览：已有 **11处AG业务表声明点**，待迁 **18个文件、34处原生业务表声明点**。数字是源码声明点，动态复用可能产生多个实例，并非34个页面或同时可见34张表。

全量统一可按下述路线推进，但不应承诺“逐个替换HTML标签且所有版式零变化”。普通清单、编辑明细和分组表头都有原生能力；复杂工作表的body合并、现有文字拖选、动态行高与业务顺序，需要逐类处理。最主要收益是交互和维护的一致性，不能未经测量承诺每张小表都会更快。

推荐范围是：**交互工作界面中的全部业务数据表采用AG Grid，正式Excel/PDF及打印文件继续由原模板生成。** 机械四页的屏幕预览也纳入评估，不先以“特殊报表”为由排除；遇到不能无损复现的工作表合并，优先提供标准网格的数据视图。PDF文档本身、第三方日期控件内部表格、普通表单/选择器/候选卡片不改成网格；卡片内部的发票明细仍纳入本次清单。

调查起始基线为829f3e11，通知书和test_read_ui当时有他人在途修改；收尾已推进到aa9cc766，该任务修复了金额失焦后的首次勾选。本调查没有覆盖或改动它们，也未改未跟踪的`.tmp-fees-width.py`。以下计数在收尾按实际源码复核；产品部署状态继续以[status](../../docs/status.md)及实际运行身份为准。

## 入口盘点

入口从[main.tsx注册表](../../apps/frontend/src/main.tsx#L31)交叉核对。扫描`table/BoundedTable/PreparedGrid/AgGridReact`声明，并读取业务数组、事件、调用分支和共用模块；没有发现第二套AntD Table或运行时createElement(table)入口。共享BoundedTable内部的1处table及PreparedGrid内部的1处AgGridReact不计作业务入口。

已有11处AG业务声明点：付款通知书、付款流水、逐月欠款双侧表、集采合同主表、库存、过程资料差异、特殊费用年度表、机械公司汇总、收发结存、焊材/气体年度提取、月度会大表。双侧/年度种类等由同一声明复用。它们已经共用主题、列宽策略和账号偏好，不要求为“统一”全部重写一次。

下表完整列出34处待迁声明。B1—B6对应后文批次；“保护点”是迁移必须维持的具体行为。

| ID | 表格/动态变体 | 源码入口 | 保护点 | 批次 |
|---|---|---|---|---|
| N01 | 项目档案主表 | [projects.tsx:202](../../apps/frontend/src/projects.tsx#L202) | 行内草稿、归档分区、完整业务顺序、拖排及导出顺序 | B2 |
| N02 | 项目修改留痕 | [projects.tsx:216](../../apps/frontend/src/projects.tsx#L216) | 旧值/新值/操作人原样展示 | B1 |
| N03 | i8各来源最近结果 | [i8.tsx:30](../../apps/frontend/src/i8.tsx#L30) | 按来源枚举显示，未知/无结果不冒充成功 | B1 |
| N04 | i8执行记录 | [i8.tsx:37](../../apps/frontend/src/i8.tsx#L37) | 50/100/200读取范围、动作筛选、错误明细 | B1 |
| N05 | 通知书剔除规则 | [rules.tsx:122](../../apps/frontend/src/rules.tsx#L122) | 编辑/删除及仅影响后续业务的规则语义 | B1 |
| N06 | 集采项目剔除名单 | [rules.tsx:194](../../apps/frontend/src/rules.tsx#L194) | 在用/停用、理由与操作人 | B1 |
| N07 | 机械报表项目匹配 | [rules.tsx:243](../../apps/frontend/src/rules.tsx#L243) | 项目键、别名草稿、保存冲突反馈 | B1 |
| N08 | 账号列表 | [users.tsx:74](../../apps/frontend/src/users.tsx#L74) | 本人/管理员权限、最后管理员保护、原操作弹窗 | B1 |
| N09 | 过程资料原始/调整矩阵 | [process.tsx:143](../../apps/frontend/src/process.tsx#L143) | 固定核算月、四组指标、历史手填、逐列和分组合计 | B6 |
| N10 | 机械四页成品屏幕预览 | [mechanical.tsx:113](../../apps/frontend/src/mechanical.tsx#L113) | 快照token、动态月份、项目定位、复杂二维合并 | B6 |
| N11 | 内租填数确认 | [mechanical.tsx:256](../../apps/frontend/src/mechanical.tsx#L256) | 原值/拟采用值及确认范围 | B4 |
| N12 | 采用机械明细金额确认 | [mechanical.tsx:258](../../apps/frontend/src/mechanical.tsx#L258) | 含税/不含税分别勾选、人工采用额保留 | B4 |
| N13 | 零租/包月可编辑明细 | [mechanical-details.tsx:30](../../apps/frontend/src/mechanical-details.tsx#L30) | row.id、按项目草稿、增删行、税率/净额、完整项目合计 | B4 |
| N14 | i8三类来源依据明细 | [mechanical-work.tsx:27](../../apps/frontend/src/mechanical-work.tsx#L27) | 来源周期/单号、三类来源复用，不重新取数 | B5 |
| N15 | 机械核对主表/已对平折叠表 | [mechanical-work.tsx:90](../../apps/frontend/src/mechanical-work.tsx#L90) | 报表/内部核对、原始差额/忽略留底、跟进入口 | B5 |
| N16 | 未归属取数发现 | [mechanical-work.tsx:100](../../apps/frontend/src/mechanical-work.tsx#L100) | 未归属金额不自动分配 | B5 |
| N17 | i8累计变化采用预览 | [mechanical-work.tsx:106](../../apps/frontend/src/mechanical-work.tsx#L106) | 勾选范围、减少依据、来源未齐保旧值 | B5 |
| N18 | i6历史数据 | [mechanical-work.tsx:111](../../apps/frontend/src/mechanical-work.tsx#L111) | 固定历史值与项目归属 | B5 |
| N19 | 核对依据金额表 | [mechanical-work.tsx:112](../../apps/frontend/src/mechanical-work.tsx#L112) | left/right/raw/ignored不可混算 | B5 |
| N20 | 跟进事项 | [mechanical-work.tsx:113](../../apps/frontend/src/mechanical-work.tsx#L113) | 事项状态与费用金额分离 | B5 |
| N21 | 原报导入批次总览 | [mechanical-import.tsx:75](../../apps/frontend/src/mechanical-import.tsx#L75) | 项目/月/类别、有效值与原报建议分别展示 | B4 |
| N22 | 每批原报明细与来源 | [mechanical-import.tsx:82](../../apps/frontend/src/mechanical-import.tsx#L82) | 原行ID/来源、待补字段、完整金额 | B4 |
| N23 | 原报修订冲突逐项采用 | [mechanical-import.tsx:83](../../apps/frontend/src/mechanical-import.tsx#L83) | current/incoming选择及未保存草稿阻断 | B4 |
| N24 | 批量付款成功流水回执 | [notice-payment.tsx:147](../../apps/frontend/src/notice-payment.tsx#L147) | 流水号与notice_id对应、不得重复付款 | B3 |
| N25 | 批量付款编辑/确认清单 | [notice-payment.tsx:147](../../apps/frontend/src/notice-payment.tsx#L147) | 每行方式/金额、移出、整批校验与未知结果锁 | B3 |
| N26 | 未满账期发票提醒 | [payment-terms.tsx:21](../../apps/frontend/src/payment-terms.tsx#L21) | 一条付款多张发票，本条付款金额不能重复计入 | B3 |
| N27 | 通知书关联付款流水 | [notice-flows.tsx:16](../../apps/frontend/src/notice-flows.tsx#L16) | 生效/撤销状态、撤销原因、全记录读取 | B1 |
| N28 | 打印/PDF任务的通知书清单 | [notice-print.tsx:47](../../apps/frontend/src/notice-print.tsx#L47) | 含搜索隐藏行的既定任务范围；文档本身不变 | B1 |
| N29 | 合同候选的供应商/贸易发票明细 | [notice-contract.tsx:36](../../apps/frontend/src/notice-contract.tsx#L36) | 同页多合同、多实例、比较信息及两步关联流程 | B3 |
| N30 | 自动关联预览/结果 | [notice-auto-link.tsx:30](../../apps/frontend/src/notice-auto-link.tsx#L30) | 预览不写、明确确认才关联、失败逐条保留 | B1 |
| N31 | 供应商/贸易公司发票子表 | [contract-subtables.tsx:98](../../apps/frontend/src/contract-subtables.tsx#L98) | 分页、外部新增草稿、历史未结口径、整表合计 | B3 |
| N32 | 合同付款子表 | [contract-subtables.tsx:99](../../apps/frontend/src/contract-subtables.tsx#L99) | 手工/实际流水/统计累计区分；合计取原API口径 | B3 |
| N33 | 甲方单位分类配置 | [contract-tools.tsx:79](../../apps/frontend/src/contract-tools.tsx#L79) | 分类草稿与下次抓取语义；同声明的ignore分支当前无调用入口，不顺带恢复 | B1 |
| N34 | 导出确认的项目顺序清单 | [ledger-controls.tsx:154](../../apps/frontend/src/ledger-controls.tsx#L154) | 既有项目选择/顺序偏好与文件顺序 | B2 |

N10复用四个sheet，N13复用零租/包月及多个项目，N14复用三类来源，N29按每个候选合同再复用供应商/贸易侧，N31复用两个发票种类。不能把静态声明数当作运行时实例数。卡片式项目选择、合同候选外框和付款引用Select不是遗漏的HTML数据表，不为统一表格一并改掉其任务流程。

## 需要先解决的具体难点

### 1. 机械年度报表不是一个普通的合并表头

后端[mechanical_export.py:271](../../backend/app/report_export/mechanical_export.py#L271)把年度项目名在第1列纵向合并，第293行又把总计第1—2列横向合并；前端直接消费rowspan/colspan。年度月份从快照数据动态生成（第231—237行），不是固定12列。

AG当前`colSpan`与同列新`spanRows`互斥，且横向合并不能跨固定区：[官方约束](https://www.ag-grid.com/react-data-grid/column-spanning/#column-spanning-constraints)。本地36.2.0校验还声明新`spanRows`与全局`enableCellTextSelection`、合并列编辑等不兼容，而本仓全局开启文字选择。校验声明不等于已经做过浏览器试验；不能由此夸大为AG完全不能纵向合并。旧`rowSpan`仍在，但依赖固定行高覆盖机制，有另一组限制，详见[研究](research.md#合并边界必须分别判断三个-api)。

推荐屏幕采用“项目/费用类别/动态月份/原合计字段”的标准行，项目名重复或以明确分隔行展示；项目小计留原业务位置，总计按任务选pinned或末行。只改变显示，不重算原报表金额。必须继续消费同一预览快照和snapshot_token，不用另一次workbench实时读取拼出看似相同的报表。第一张公司汇总可评估复用已有AG投影；年度月份列用真实月份身份，总计等固定角色用稳定colId，避免月份数量变化后列宽串位。

若用户要求屏幕精确保留全部原合并版式，应先对旧rowSpan路线做一张真实快照的固定行高/冻结/复制验证；不以自写DOM覆盖层或复制一个Excel渲染器绕过限制。正式Excel/PDF继续承担原版式是推荐备选，尚未据此删掉任何预览。

### 2. 多实例小表会暴露新的公共状态问题

N29会同时创建每个候选合同的供应商/贸易明细。直接给每个两列表套现有整页准备和独立工具条，会增加网格、观察器和版面开销。不能未经数据和测量就断言一定慢，也不应先强制改变已确认的两步关联界面。

应先验证最大真实候选场景；共用轻量小表配置、合理限宽，恢复入口融入所属任务工具区，不给每个微型表增加一整行工具条。同一个账号/表格身份的多个实例，应共享一次偏好状态并同步宽度/恢复；当前每个binding单独读写localStorage的方式尚未提供同窗口广播，不能只靠storage事件。偏好仍只保存列宽，既有本机、账号与表格范围保持，不扩成服务端或跨设备配置系统。

### 3. 拖的是全局业务顺序，不是当前显示数组

项目页先按状态/类型/关键词筛选，再显示排序；现有`move()`按完整项目列表和状态分组调用后端ord接口。AG的managed拖排不适合直接接这个语义，尤其外部先过滤rowData时，AG并不知道隐藏项目。

推荐原生unmanaged拖行事件＋现有业务move接口：拖拽识别和反馈交给AG；以真实源ID、目标ID映射完整业务顺序，保归档分区与当前筛选含义。不能把显示行index写成全局ord，也不能新增“先清空搜索才能拖”的前置要求。[官方unmanaged能力](https://www.ag-grid.com/react-data-grid/row-dragging-unmanaged/)。拖影、让位、失败恢复及活动排序时的行为需在代表路径核对，不重建自写拖拽引擎。

### 4. 金额、草稿和保存仍由业务模块持有

N13/N25/N31/N32等继续复用现有输入、草稿、权限、串行保存、确认与回执处理；先作为React cellRenderer接入，避免同时改成双击编辑或另建保存流程。若某列采用原生编辑器，需正确提交最后输入值；网格编辑结束/applyTransaction不是数据库保存或事务。金额仍沿字符串/Decimal约定，空、零、未知不互换；不启用AG默认数字推断来接管金额规则。

N26多发票展平时，付款金额按通知书只显示/汇总一次；不能把它复制成每张发票的金额。N32的合同付款合计仍取API给出的pay_sum，不能机械相加显示行；N13“只看待补”时的项目总额仍取完整项目。新增说明/分组行使用明确rowKind及显示ID，禁止参与业务选择、写入或重复合计。

aa9cc766的金额失焦后首次勾选保护、已有草稿guard、虚拟行卸载后的输入保留，是共用机制调整必须复验的代表行为。

## 公共模块路线：沿用已有能力

- 保留AG的ColDef/ColGroupDef作为列定义，不另建一套列描述语言，也不把BoundedTable改成运行时解析thead/tr再转网格的适配器。
- 沿用grid.ts、grid-widths和grid-presentation的职责。公共部分持有主题、尺寸/字体准备、原生列宽、账号偏好、只读/编辑接合和错误出口；页面持有业务数据、真实行ID、权限、草稿和保存。公共网格不自己请求业务API。
- 根据实际布局提供整页工作区、小型弹窗/卡片、报表数据视图三类约定；少量行可自然增高，大清单保持受限高度和虚拟化/既有分页。不能对所有表一律autoHeight、固定60vh、全开排序筛选或套用同一宽度上限。
- tableId/colId按表格角色稳定，项目、合同ID、月份等数据范围进入查询/草稿scope，不制造每个记录一套列宽配置。动态时间轴列与普通年度1—12月列按真实列语义区分，不能依赖会漂移的数字位置。
- 只注册实际采用的Community模块；当前没有默认注册分页/拖行等所有新能力。聚合、Master Detail、Batch Editing、内置xlsx导出等Enterprise功能不是默认迁移前提，已有后端导出和业务保存继续复用。
- 鼠标与普通文本输入基线保持，浏览器/组件默认行为自然保留；不恢复自写跨格Tab、方向键导航或额外全局快捷键。仅处理真实编辑器冲突，不为统一技术栈新增一套键盘规则。

## 迁移批次与先行验证

先做4个代表验证，再批量替换：①N29多实例只读小表及共享列宽；②N13项目分段、增删行和外部草稿；③N01筛选下业务拖排；④N10年度合并报表的标准AG数据视图。这里是后续实施的验证安排，本轮没有制作原型或运行迁移测试。先验证难点，可避免先迁十几张简单表后才发现公共路线不合适。

| 批次 | 纳入ID与声明点数 | 核心验收 |
|---|---|---|
| B1 支撑清单/配置 | N02—N08、N27、N28、N30、N33，共11 | 原操作/权限、状态与错误明细、少量行布局；涉及i8/打印的入口只在隔离副本测，不真实外呼 |
| B2 项目与顺序 | N01、N34，共2 | 完整ID顺序、归档分区、过滤/排序下拖排、导出项目顺序、失败恢复 |
| B3 付款与合同 | N24—N26、N29、N31、N32，共6 | 金额/方式草稿、整批确认、未知锁、分页/全部合计、多发票上下文与多实例偏好 |
| B4 机械明细与导入 | N11—N13、N21—N23，共6 | 稳定行ID、项目分段、净额与税率、增删草稿、导入仅保存明细、有效值另确认 |
| B5 机械核对 | N14—N20，共7 | 累计与单据差额分别处理、忽略留底/撤销、选择采用及减少依据、来源与事项 |
| B6 矩阵与成品数据视图 | N09、N10，共2 | 过程分组表头/两类合计；四页快照信息、动态月份、项目定位及导出token一致 |

合计34处；先行验证已经完成的对象直接进入对应批次验收，不再重做。每批独立可回退，业务接口和表结构默认保持；上线只交付完整构建，分别核源码、部署与人工验收，不在本轮分析中授权部署。

## 业界备选与本项目取舍

成熟设计系统确实允许按用途区分静态Table与交互DataGrid：[MUI](https://mui.com/material-ui/react-table/#data-table)强调结构灵活性与复杂数据功能的取舍，[Supabase](https://supabase.com/design-system/docs/ui-patterns/tables)明确按虚拟化、列宽调整和复杂编辑选Grid。Supabase同时公开了未来收敛到一个TanStack Data Table的意向；这是规划，不是已验证的通用替代方案。

因此有两个合理方向：A，按本次目标统一全部业务数据表为AG，并对极少数工作表采用标准数据视图（推荐）；B，统一交互和偏好协议，保少数纯展示/精确版式表（成熟备选，但不作为本次默认目标）。不建议当前另换TanStack/MUI或自组网格：本仓已具备AG底座、复杂表和相关验证，换库会重新承担编辑、虚拟化和状态接合成本。打印文件作为文档输出单独保模板，可同时用于A/B，不等于业务表格继续维护两套引擎。

## 完成判据与仍待验证事项

1. 34处清单逐项有迁移/验收结果，已有11处AG共同能力无回归；源码里的业务table/BoundedTable入口归零，动态弹窗/确认/回执也可达。不能仅凭grep归零宣称全量通过。
2. 列宽在各表与重复实例上按账号正确记忆/恢复；缩窗横滚、字号变化、完整金额/标识及动作可达。小表不因统一框架被撑成大空白或产生多层滚动。
3. 以真实ID核对行、勾选和业务范围，合计、导出与原数据不丢不串；中文组合输入、失焦保存/首次勾选、后续草稿和失败回执按受影响代表路径验证。原接口已覆盖的金额组合不在UI穷举。
4. 优先复用现有test_grid_widths、test_read_ui、test_project_history、test_export_dialogs、test_notice_association、test_invoices、test_process、test_mechanical_reports等覆盖，只补迁移后真实缺口；DOM断言更新为对应行为/行ID，原保护不能因换组件删除。
5. 只在受控真实副本运行写入验证；涉及i8、打印/正式业务写入仍守当次授权。界面迁移不默认要求重跑后端全量；若实际触及业务事务或共享写入，再按影响补对应验证。
6. 所有消费者退出后再删BoundedTable及无消费者的表格CSS/旧DOM适配。Excel/PDF模板、旧壳回退和424退役范围分别维护，不能因本目标扩大成旧壳删除或模板重写。

本轮实际完成：15页注册入口与全部表格声明的静态盘点、关键保存/顺序/报表来源阅读、36.2.0本地校验核实、官方及第一方实践研究。未执行：界面迁移、原型/运行测试、性能测量、数据库或真实业务操作、服务重启。最需要用户后续验看的取舍是机械年度报表等少数屏幕版式；多实例成本、原生拖排反馈和IME接合需在代表验证中实测，不写成已经通过。

官方能力、版本/许可和原生新旧合并API的逐项证据见[research.md](research.md)。正式产品的现行设计规则保持原文，实施方案确认后再同步frontend-design与architecture；本分析不作为暗改业务或部署的授权。
