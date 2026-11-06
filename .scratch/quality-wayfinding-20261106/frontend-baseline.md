# TAIL-484 前端具名覆盖基线

2026-11-06。调查者：`/root/frontend_baseline`；主控持有 TAIL-484。本记录仅调查前端，供全库基线整合及 TAIL-485/487 选取代表场景；不是全站达标或本轮运行验收。

## 取证身份与方法

- 实际 HEAD：`6d01f996dd46a86c204aeb2568aad58d82c2034d`。`git log -1 -- apps/frontend` 为 `7156a5aef8d45b54e7db8769a87e0f94080873e3`；`git diff --name-only 7156a5ae HEAD -- apps/frontend` 为空。调查时前端源码、测试、依赖无 dirty；主根其他 dirty 与新地图文件由各自任务持有，本调查没有修改。
- 已加载版本复用 [status](../../docs/status.md) 和 [通知书金额发布记录](../notice-amount-deepening-20261106/implementation.md) 的 `7156a5ae` 发布回执。主控随后消息确认已核正式前端7156代码相符、提权status为Running及`/app`200，沙箱不可见误差另行区分；这份现场核验由主控持有。本子调查没有请求正式服务、浏览器或当前用户页面。
- 读取项目 AGENTS、CONTRIBUTING、CODING_STANDARDS、workflow、frontend-design、frontend architecture、TAIL-483/484 及固定质量参考。按 writing-for-agents 编写接续材料。没有使用 Hindsight recall/retain；未声称自动注入已提供项目证据。没有读用户凭据或业务原件，没有运行测试/构建/服务/数据库/i8，没有新增脚本、截图、运行产物或工作树。
- 范围为 `apps/frontend` 自有源码、依赖/构建装配、前端相关测试及已具名旧证据。以下“所有者”是源码职责主人，不推测个人维护者。可达性以 `main.tsx` 注册表与 import/调用链确定；每页保活并不等于后台查询仍启用，根入口向隐藏页传 `blocked || !active`（`main.tsx:110`）。
- 深度分开：**源码已核**为阅读当前实现的指定链；**旧运行证据**仅证明原版本、原输入及原场景；**静态风险/假设**需最小定向验证；**未深查**有具名缺口。测试存在不计为本轮通过，历史通过数不当覆盖率。

## 依赖、构建与源外内容

`package.json:6–37` 与 `pnpm-lock.yaml:175–234` 一致：pnpm 12.15.0，Node 要求 >=24.22.1，React/React DOM 19.3.1、React Router 8.5.0、TanStack Query 5.104.5、AG Grid Community/React 36.2.0、AntD 6.6.7、rc motion 1.3.3、react-virtuoso 4.18.19、Valibot 1.5.0、decimal.js 10.6.0、dayjs 1.11.23、uuid 14.0.3；Vite 8.3.5、TS 7.0.2、plugin-react 6.1.2、tsx 4.23.15、React types 19.3.0。锁文件前一 YAML 文档锁 pnpm 自举，第二文档锁应用依赖，不能只读开头就误报“没有前端依赖”。未安装/升级，也未以外部最新文档推断本锁版本行为。

| 具名模块 | 主人、消费者与本次结论 | 现有保障与缺口 |
|---|---|---|
| 工具链与入口 | `index.html`、`vite.config.ts:4–11`、`tsconfig.json:12–25`、`package.json`、`pnpm-workspace.yaml`、锁文件。base 只允许 `/app/`、`/preview/`，严格 TS，skipLibCheck=false；Vite 仅配置 react 插件，未配置 React Compiler。 | 当前 package 逐文件列入 26 个 unit 文件；不因测试目录存在就假设自动运行所有未来文件。最近金额发布有 typecheck/build/unit/CI 历史证据。当前实装 node_modules 与运行 Node 未另核；本票不重跑。 |
| 6 份声明补丁 | `patches/ag-grid-community@36.2.0.patch`、`antd@6.6.7.patch`、cascader 1.22.0、image 1.10.0、menu 1.5.0、picker 1.12.2。workspace 与 lock patch hash 已登记；抽核修改路径均为 `.d.ts`。 | 旧 TAIL-450 明确保留严格可选属性兼容，不是新待偿债；升级时才核上游声明是否吸收及删除条件。没有对第三方实现进行自有源码质量签署。 |
| 生成/外部内容 | `node_modules` 为第三方安装物；tests 下 `__pycache__`、`.pytest_cache` 为运行缓存；`assets.d.ts`、`vite-env.d.ts` 为编译声明。正式构建/manifest 是产物，归发布器。 | 本次不清理、扫描第三方全量或把缓存作为模块。旧壳退役结论归 TAIL-424，不能把旧壳当在用第二前端。 |

## 16 个实际页面入口

路由唯一注册表为 `src/main.tsx:33–49`。以下文件均相对 `apps/frontend/src/`；测试相对 `apps/frontend/tests/`。所有业务 API 权限、金额权威和事务最终归后端，前端拒绝不等于服务端安全验收。

| 入口 / 责任所有者、消费者 | 当前源码已核的行为与判断 | 测试、旧证据及最小缺口 |
|---|---|---|
| `/` 首页：`home.tsx:10`、`home.css`；消费者为待办深链/通知书 | 与通知书共用 `['notices']` 和 `readNotices`，从同列表派生待办，根树按页 lazy。保持现状：三处短查询已有共同 key/解析器，旧审计未发现值得新建查询层的成本。 | `test_home.py`、`test_read_lanes.py:208`；旧全站/加载证据。新数据下待办数量与深链范围未本轮运行。 |
| `/projects` 项目档案：`projects.tsx:76–153`、`projects.css`；候选供各业务页、导出和i8同步 | 档案扩展列表、两个待办和留痕独立 key；格内保存核回执 ID、更新权威缓存，保 uncertain 草稿；拖拽有完整排序主人。待办/留痕读取有浅检查，见 F3。 | `test_preview.py:134`、`test_project_history.py`、`test_read_ui.py`、`test_grid_migration.py:102`、`test_report_maintenance_read_lanes.py:259`、`test_acceptance_b.py:27`。E2/E6加载证据可限定复用；坏200嵌套项与拖拽高规模成本未深查。 |
| `/i8` 接入层：`i8.tsx:104`、`i8.css`、`i8-api.ts`；消费者为本机配置、连接状态和已有执行记录 | 现有记录读取与真实抓取分开；记录限制由页面选择，通道归账号 I8SessionProvider。连接恢复是当前在用功能，不能据旧“刷新需重连”恢复旧流程。 | `test_i8_session.py`、unit relay/recovery；E3。只读页面不代表已调用i8；真实所有来源端点不在此基线验证内。 |
| `/notices` 付款通知书：`notices.tsx:57–241`、`notices.css`、`notices-api.ts` | 全量列表本地范围/搜索，选择身份为 notice_id；普通金额独立 queue，`StatCell`不按普通busy锁后续输入；refresh返回可靠列表并等必要历史；textOnly三列优化仍在。全量派生/宽度成本见 H1，不能从 useMemo 判性能达标。 | `test_write_receipts.py`、`test_grid_widths.py`、`test_read_ui.py`、`test_acceptance_b.py:8`、unit notice-amounts/codes。E4/E5；最后金额入口改动后未新增GUI，旧连续编辑覆盖不能升级成新端点端到端证据。 |
| `/debt` 欠款：`flow.tsx:33–64` + `ledger.tsx:133–247`、`ledger-api.ts`、`ledger.css` | 三类非零项目汇总自然展开，下方双侧台账独立准备；编辑归账号/项目/月，自己的版本队列、显示发布保护及共享 exportGuard 保持。与 CellSaveQueue 顺序不同已有慢读反例未复现问题，保持独立实现。 | `test_ledger.py`、`test_ledger_layout.py`、`test_debt_loading.py`、`test_shared_controls.py`、`test_export_dialogs.py`；E1/E2/E4。长会话 map 增长、金额/归属及全导出组合需后端风险证据，不能只看前端。 |
| `/ledger` 付款流水：`flow.tsx:66–144`、`flow-api.ts`、`flow-revoke.tsx`、`flow.css` | 流水与付款统计独立查询/状态，金额以 cents/decimal 聚合，服务端 shape 校验；notice深链不依赖欠款。排序 comparator 的 Number 使用与常见实际金额范围尚未针对性核验，不将其推断为金额计算错误。 | `test_read_lanes.py:134,181`、`test_ledger_layout.py:45,115`、unit flow-api；E1/E6。峰值全量本地筛选与实际撤销/导出对应后端验证未本轮追完。 |
| `/contracts` 集采台账：`contracts.tsx:70–162`、`contracts-api.ts`、`contracts.css` | 主表全量/本地筛选，inline-field-queue串行离格+推进，按稳定id回读；自己的列宽原生路径继续保留；已有行编辑默认 materialOnly，新建可全字段。合同编辑/子表消费者由原路径管理，不宣称不可达完整编辑器已GUI全验。 | `test_contracts.py`、`test_contract_export.py`、`test_contract_oilcard_read_lanes.py`、unit contracts-api/inline-field-queue；E4/E5/E7。当前UI主路径已核；完整字段编辑器仅接口存在，所有隐藏分支未深查。 |
| `/process` 过程资料：`process.tsx:56–170,202`、`process-api.ts`、`process.css` | 全项目矩阵/来源并行读取；原始、调整、差异三视图，草稿含项目/月/列/版本；机械来源切换显式确认；未知结果核对不把空当零；矩阵用 BusinessGrid，差异独立准备。 | `test_process.py`、`test_process_mechanical_loading.py`、unit cell-save/business-time；E1/E2。当前大矩阵性能与真实多项目连续切换未重测，不恢复横向完整总表外的实验布局。 |
| `/settlement` 收发结存/年度提取：`settlement.tsx:27–166`、`settlement-api.ts`、`settlement.css` | 月报和年度子页各有active，按范围 key读取；月报/年度自然高度，完整年度合计取服务端sum_row；历史结余共用queue；i8月抓取/导出为明确动作。 | `test_settlement.py`、`test_report_maintenance_read_lanes.py:83,119,145`、`test_i8_fetch_entrypoints.py`；E1/E3/E6。最大仓库/年度行数未知，autoHeight规模需实测后才谈虚拟化。 |
| `/big` 月度会大表：`big.tsx:54–131`、`big-api.ts:24–55`、`big.css` | 访问过的月实例保留草稿，active限制query与layout；每月稳定warehouse ID、冻结名单与POST导出保护，空产值不转零。近期empty→content尺寸修复已吸收。嵌套hidden月累积仅H2。 | `test_big.py`、`test_grid_widths.py:38`、`test_report_maintenance_read_lanes.py:33`；E2/E6/TAIL-482。9项目是旧可得最大样本，不是未来峰值；跨多月会话资源未知。 |
| `/inventory` 库存/调整：`inventory.tsx:31–119`、`inventory-api.ts`、`inventory-adjust.tsx`、`inventory-calculation.ts`、`inventory.css` | 全量规范行保持本地筛选；枚举只弹层开启才生成，deferredFilters不改变最后结果；有效值/原值与差异定位分开；reload只等库存和必要history。调整写入校验和未知锁保留。 | `test_inventory.py`、unit inventory-api/business-time；E1/E4。旧18287行解析成本优化可解释机制，不证明当前传输/绘制已快；调整计算完整业务组合由后端/既有协议持有，本票未重审公式。 |
| `/fees` 特殊费用：`fees.tsx:46–117`、`fees-api.ts`、`fees.css` | 年/项目响应须与当前范围一致才发布；手填项及月份由item_id身份，queue保护；自然高度完整12月，不按低行数猜无需布局检查。 | `test_fees.py`、`test_fee_items.py`、`test_report_maintenance_read_lanes.py:166`；E2/E6。新增丢回执已有具名测试；旧月度readFees/getFees出口见退出候选R1。 |
| `/mechanical` 机械费：`mechanical.tsx:124–223`、`mechanical-api.ts`、`mechanical-details.tsx`、`mechanical-work.tsx`、`mechanical.css` | 当前月轻page接口；公司汇总、零租、包月、核对四职责；保存按提交月回读，签名/版本及已采用事实区分；导出消费台账guard；页面不构造Excel。 | `test_mechanical_reports.py`、`test_mechanical_details.py`、`test_process_mechanical_loading.py`、unit mechanical-api；E0/E2。当前非空核对工作区规模、动态来源提示与四表输出需限定旧证据，不重开已关闭性能effort。 |
| `/oilcard` 油卡管理：`oilcard.tsx:68–157`、`oilcard-api.ts`、`oilcard.css` | 档案/账户按request_id及version，新档先保本地后保存；总览与档案查询并行；ledger/linkage锁传父级，普通备注和结构变更分别处理。 | E2/E4/E7/E8；unit oilcard-*；当前浏览器tests以加载/子链为主，不能把空档案或mock备注当非空完整油卡验收；真实旧台账接续仍是TAIL-474业务缺口。 |
| `/rules` 规则配置：`rules.tsx:24–100`、`rules.css` | 三分区独立读取、按前驱首次位置发布；规则不重算旧单据；标签清理为呈现。新增规则失败处理见F1，不将现有小数据量当永久性能保证。 | `test_rules.py`、`test_report_maintenance_read_lanes.py:231`、`test_first_display_retained.py:38`；E2/E6。新增请求丢回执恢复尚缺定向证据；后端幂等/唯一性待主控分区核。 |
| `/users` 用户管理：`users.tsx:39–113`、`users.css` | 显式账号列表/角色/最后管理员UI保护；普通用户本人改密和管理员操作分开。可查看明文是当前产品入口，不由本报告自行删除；后端实际权限另核。状态/恢复操作见F2。 | `test_users.py`、`test_preview.py:125`、`test_report_maintenance_read_lanes.py:194`。现有测试不是完整授权矩阵；当前选择小账号量但需实际权限底线，未读任何真实密码。 |

## 共享机制与页面内模块的所有权

下表补足上一表没有逐项展开的在用子模块。导入可达已核；“未深查”不会因同组一个测试存在而转成已验证。

| 具名机制 / 包含文件 | 源码主人、实际消费者与本次判断 | 相关保障 / 未检查 |
|---|---|---|
| 账号/路由/保活 | `main.tsx:68–180`、`page-activity.ts`、`page-error.tsx`。每账号独立QueryClient；身份暂时失败保树并inert，确认换号才重建；visited最大16路由。lazy错误独立边界，重载消费历史/草稿guard。 | unit identity-gate、`test_preview.py`、`test_page_loading.py`、`test_font_recovery_protection.py`。Q7/Q9机制保持；后端session验证不在此签收。 |
| 网络与精确显示 | `api.ts:26–89,96–128` 管身份门、AbortSignal、HTTP/坏JSON、下载文件名、cents/decimal/money；域`*-api`作形状/语义适配。`random-id.ts`使用uuid安全源。所有域消费。 | unit identity-gate/random-id；未知写入共用 uncertainWrite。不能仅有TypeScript断言就当runtime校验；F3是具体剩余薄点。 |
| 主题/字体/样式 | `appearance-ready.ts:5–53`、`appearance-preferences.tsx:32–104`、`ui-provider.tsx:11–47`，以及 `styles.css`、`style.css`、`ui.css`、`ui-theme.css`、`appearance-preferences.css`、`business-period.css`。主题色权威仍为后端notice/page/theme_react；组件只消费CSS roles。固定CSS顺序，全页JS继续lazy；切偏好核回读，不靠通知先报成功。 | `test_startup_styles.py`、`test_users.py:16`。`ui-theme.css:64–74`局部130ms反馈/减少动效，MotionProvider稳定；保持现状。八主题、1.12/1.25/1.4、窄窗的当前全站视觉矩阵未做。 |
| 首读发布/保活隔离 | `page-surface.tsx:13–53`、`read-region.tsx:18–45,67–120`、`read-region.css`。PageSurface只等chrome字体及明确loading；FirstReadRegion按子grid准备完成发布原节点；失败不冒空，后继放行不倒退。所有路由及小表消费。 | unit read-region及全部read-lanes、first-display、font-recovery。E2/E6机制证据可复用；a5之后read-region及多页CSS有变，旧每帧几何数值不当当前测量。 |
| 深表格呈现 | `grid.ts`公共模块/主题/数值下限；`grid-presentation.tsx:23–69`装配；`grid-layout.ts:40–184`保留列定义、同几何复用、字体、portal及128项批测；`grid-render-layout.ts`从原生ColDef派生渲染测量。库存、通知书、流水、欠款、机械汇总、报表及BusinessGrid消费。 | `test_async_layout_ownership.py`、grid widths/startup/process tests；E0/E1/E2/E6。取消token及cleanup有旧交错反例；DOM有界不等于总工作量有界，真实慢点见H1。 |
| 轻/复杂网格适配 | `business-grid.tsx:37–99`的BusinessGrid走PreparedGrid，ReadGrid走原生autoHeight并等真实行/scrollbar；调用方原生ColDef，不另造DSL。项目、规则、用户、合同子表、油卡、机械细表等消费。 | `test_grid_migration.py`、`test_first_display_retained.py:60`、read-lanes；不自动将小表迁成深测量。所有autoHeight大规模尚未实测。 |
| 列宽所有权 | `grid-width-owner.ts`、`grid-width-state.ts`、`grid-widths.tsx:10–81`、`grid-manual-widths.ts`。账号/表格localStorage与实例内存通道；完成原生拖拽才存手动列，显式恢复保排序等；React发布前解除手调min/max。三路：PreparedGrid、ReadGrid、contracts主表。 | unit grid-width-state、`test_grid_widths.py`、`test_grid_migration.py:12`；旧A3三路装配保持。需真实同步修改成本才推进统一；本票不预设重构。 |
| 全文/枚举/集合筛选 | `grid-text.tsx`、`grid-single-line.css`、`enum-tag.tsx`、`grid-value-filter.tsx`、`grid-value-filter-model.ts`、`grid-value-filter.css`。完整短值下限/截断才提示；类别与状态分离；集合筛选目前油卡充值/发票消费，不能扩称全站已推广。 | unit grid-value-filter、table-selection/grid-widths；油卡真实大集合的交互成本/金额全量合计未本轮运行。 |
| 保存队列/历史 | `cell-save.ts:23–142`、`use-cell-save.ts:6–20`、`inline-field-queue.ts`、`history.tsx:36–100`。公共queue先快照→写回执→可靠读回→退役对应草稿；未知结果停队；集采inline queue保blur/推进，欠款另有版本协议。History重核同一operation_id，统一guard、全局恢复属显式历史动作。 | unit cell-save/inline-field-queue，write-receipts/ledger/process/shared-controls；E4/E5。不合并语义不同队列；并非所有页使用公共queue，规则/用户另见F1/F2。 |
| 弹窗/弃稿 | `business-modal.tsx:6–26`、`dialog-close.tsx:7–49`、`business-modal.css`。AntD壳只持关闭/焦点恢复，dirty/busy归调用者；弃稿统一文案，保原input/Esc，不恢复退役键盘增强。 | `test_dialog_confirmations.py`、`test_shared_controls.py:7`、机械设置tests；E4代表动态减少动效原节点保持。全部任务宽度及极窄状态未验。 |
| 时间/项目/导出范围 | `business-time.ts`纯闭区间与北京月份；`time-picker.tsx`日期/范围控件；`ledger-controls.tsx:15,57,71,84`项目选择与顺序/导出；`project-picker-order.ts`、`project-drag-image.ts`。通知书/流水/库存/报表/机械/集采消费，显示与导出名单独立。 | unit business-time/project-picker-order；`test_export_dialogs.py`、`test_mechanical_reports.py:76`、`test_grid_migration.py:102`。范围语义各业务保留，不能按通用组件压成一种。 |
| i8通道/抓取动作 | `i8-browser-relay.ts`、`i8-relay-recovery.ts`、`i8-session.tsx:37–120`；`i8-fetch.tsx:29–100`、`i8-report-fetch-api.ts`、`i8-report-fetch.tsx`、`inventory-fetch.tsx`。账号通道拥有连接意图/停止，抓取动作拥有同步锁/回执与重读，inventory/settlement各月待核状态，通知书/合同/机械复用。 | unit relay/recovery/fetch-submit/maintenance-mode，`test_i8_session.py`、`test_i8_fetch_entrypoints.py`；E3及后续单测。真实来源认证/取消/响应范围属于跨前后端专项，前端mock不能替代真实日常各端点。 |
| 通知书关联/归属/维护 | `notice-maintenance.tsx`、`notice-contract.tsx:83–107`、`notice-supplier-step.tsx`、`notice-auto-link.tsx`、`notice-association.css`、`notice-contract.css`。关联两步、候选react-virtuoso、unknown留窗，readBack复用父refresh返回列表；归属/自动关联有各自业务入口。 | `test_notice_association.py`、`test_dialog_confirmations.py`、unit maintenance-mode；E4单次恢复读取已吸收。所有候选金额匹配/多供应商组合由后端业务验证，未穷举。 |
| 通知书付款/打印/粘贴 | `notice-cell-save.tsx`；`notice-payment.tsx`、`notice-payment-grid.tsx`、`payment-context.ts`、`payment-terms.tsx`；`notice-flows.tsx`、`notice-print.tsx`、`notice-paste.tsx`、`notice-fetch.tsx`。金额intent、日期核对、实际付款及PDF/物理打印、已存在编码选择各有主人。 | unit notice-amounts/codes/fetch-submit、write-receipts/acceptance_b/association。此次未真实付款或打印；付款对象/上下文/回执及输出范围需后端与既有模板证据。 |
| 集采编辑/工具/导出 | `contract-dialog.tsx`、`contract-tools.tsx`、`contract-export.tsx`、`contract-export-api.ts`。主表新建/材料编辑、抓取/甲方配置、报表范围显式传递；receipt与域API适配保分工。 | contracts/contract-export/grid-migration tests；E7主入口限定。全字段编辑器当前可达条件须保留记录，不把未走GUI当完成。 |
| 集采子表恢复 | `contract-subtables.tsx`、`contract-subtables-api.ts`、`contract-subtables.css`、`use-contract-subtables.ts:9–36`、`contract-subtable-workspace.ts:45–144`、`contract-subtable-recovery.ts`、`contract-subtable-overage.ts`。每账号/合同workspace持草稿、稳定request_id、先恢复后回写、三侧独立未知锁，父guard仅消费summary；sessionStorage持久化失败明确反馈。 | 3组unit及overage、`test_invoices.py`；E7同源码可直接复用3条真副本代表，不重开旧候选。 |
| 库存/材料报表导出 | `inventory-adjust.tsx`/`inventory-calculation.ts`调整草稿与计算；`process-export.tsx`、`settlement-export.tsx`承接服务端成品及POST未知恢复；`process-api.ts`、`big-api.ts`、`settlement-api.ts`保null/0、实际范围、模板输出边界。 | inventory/process/big/settlement/export tests；E1/E2/E6。屏幕网格不是Excel/PDF生成源，不能用屏幕值代表导出全部内容。 |
| 机械编辑/核对 | `mechanical-details.tsx`持明细输入和弹窗；`mechanical-work.tsx`持来源核对、历史起点、i8预览选择采用；`mechanical-api.ts`持当前月投影/来源签名/未知累计/回执适配。 | mechanical-details/reports tests、unit mechanical-api；E0/E2。不把未知累计或首次空抓取变零；复杂来源选择、跨月竞争仍需后端签名验证。 |
| 油卡账本/核对/转账 | `oilcard-ledger.tsx`、`oilcard-ledger-api.ts`、`oilcard-ledger-edits.ts`、`oilcard-reconciliation.tsx`、`oilcard-transfer.tsx`、`oilcard-date.tsx`、`oilcard-export.tsx`。充值/退款/双边转账按身份版本、总台账；核对读归后端聚合。 | unit oilcard-ledger-edits/transfers、E8。真实余额/重复转账/总台账导出须追原油卡各票运行证据；本调查没有新非空运行样本。 |
| 油卡发票/接收/联动 | `oilcard-invoices.tsx:56–135`、`oilcard-invoice-dialogs.tsx`、`oilcard-invoice-api.ts`、`oilcard-receive.tsx`、`oilcard-batch-api.ts`、`oilcard-linkage.tsx`、`oilcard-linkage-api.ts`。原件SHA/票据身份、分配、批次request_id、费用/大表启用有窄契约；备注只等本表/history，其余动作仍核账户。 | unit oilcard-invoices/batches、read-lanes；E4备注仅mock，E7后端三项深化，E8原功能。不能称真实旧台账接续/非空发票流程已本轮核验。 |

## 旧证据复用台账

不复述全部旧测试数量；需要执行时沿原文找到输入、构建和失败日志。下列版本差异已用只读 Git 核过：`b8ee0b24→HEAD`涉及多页面、读取区域、i8、queue、子表；`a5c3b896→HEAD`仍涉及多页CSS/加载、i8、子表及金额入口；`17495586→HEAD`仅前端金额cell/API及其测试。因此“同方案仍在”与“原计时仍是当前基线”分别判。

| ID / 来源、版本 | 仍可复用的结论 | 不可外推 / 最小补证 |
|---|---|---|
| E0 机械性能；Git `642725be3d8fcb157dbeb0b66ed205f2fb758869:.scratch/mechanical-performance/verification.md`，产品 `fbb42d23` | 当前月page、不构造Excel、屏幕/Excel共用投影的职责仍在；原真实副本六代表与7421格对照是历史有效证据。 | 旧1.12、1280×900、1.19MB响应/327–341ms不是当前跨机器预算。后续月份模型/i8核对已变，当前完整回归另按变化选。 |
| E1 全站性能；同Git `.scratch/site-performance/completion.md`，候选`d5a97eaf`、发布`8e4512ce` | 15路由阶段的保活尺寸修复、库存18287行/747调整 Set 校验、过程轻投影、请求内复用、单通知书范围下推已有历史对照，当前代码有相应机制。 | 当时无油卡路由；当前16路由不能继承“全站通过”。部分探针无效、默认月无数据失败、凭据事件等原限制保持；只取有效样本。 |
| E2 [加载整改验证](../loading-structure-20261105/verification.md)，累计`9b8e0ccd`、发布`b8ee0b24` | 八页首读、保活隐藏不穿透、异步portal owner、字体重载guard有具体失败→修复证据。当前PageSurface/grid-layout/page-error机制未退出。 | 这是几何/发布证据，不是五次冷热性能结果；油卡为空。后续read-region、CSS、grid-presentation已变，不把原每帧尺寸直接套当前。 |
| E3 [会话/加载证据目录](../browser-session-loading-20261103/evidence/TAIL-478-481-acceptance.md)、[日常抓取](../browser-session-loading-20261103/evidence/TAIL-476-daily-live.md)，`90720465/fcc1512a/797dfe36` | 原真实通知书17条浏览器会话抓取、无登录/强踢是具名历史事实；原其他页读取状态检查可定位保护意图。 | 此次只读取status指针、未完整重读这组每份原回执；其后relay恢复源码有变。不能据旧17条宣称当前所有i8来源现场验收或自动恢复全通过。 |
| E4 [性能审计](../performance-architecture-audit-20261106/audit.md)与[整改](../performance-architecture-audit-20261106/implementation.md)，`d82f969f→ed1e966a/a5c3b896` | 通知书两格连续输入、关联恢复一次读取、库存无关查询失败隔离及油卡备注边界已吸收；通知书三列textOnly旧五次对照首进1781.1→1506.6ms。A3列宽装配和A4台账明确保持。 | 本地未提交记录，不将其当远端永久已保存材料。当前金额入口及其他首读/CSS后变；1.12、物理屏幕、滚动、长期内存不在该性能结论；油卡备注仅模拟，真实发票0条。 |
| E5 [通知书金额深化](../notice-amount-deepening-20261106/implementation.md)，`7156a5ae` | 当前前端与此版本完全一致。单格只发id/field/value；157 unit、81后端及正式构建历史可复用，各证据层仍分开。 | 原文明确未新GUI/独审；当前金额接口的完整浏览器连续编辑可列最小联通缺口，不重复所有金额组合。 |
| E6 [审计整改](../audit-remediation-20261105/implementation.md)，`67111c60` | flow/debt坏200边界、empty→content自动下限、两页8项代表等有具名依据；当前源码继续该设计。 | 不是全库质量认证；先前五次性能仍缺第二档大表、指定月四组合；后续源改变的几何不能原数复用。 |
| E7 [三项架构深化](../architecture-deepening-20261106/implementation.md)，`17495586` | 集采workspace前端文件至HEAD未改；explicit discard/F5、丢回执同ID恢复、只写一次及7项workspace行为证据可限定复用。油卡原件/用油编排是后端深化，前端契约消费者仍在。 | 未做全站GUI；完整合同编辑器非此次GUI覆盖。后端具体两项吸收由后端分区核，前端报告不重复签事务。 |
| E8 油卡 [原交付入口](../../docs/status.md)与 [阶段交付](../../docs/status.md)，`a70ce4e7/a6fdd73a` | 原票453–463/独立审查/合并发布存在；可追到各功能原证据，真实旧台账另有TAIL-474。 | 本次未逐份读完每张油卡票原运行报告；不能以总票done给每个油卡金额/收票/联动路径签“运行已覆盖”。优先列明非空数据代表。 |

### 此前三项深化及其后的候选

已明确找到的三项是 E7：油卡原件接收、集采子表workspace、用油接续编排，均已有实施/发布记录，不重新设成任务；前端集采实现已核 `use-contract-subtables.ts:13` 到 `ContractSubtableWorkspace`。随后通知书金额intent为E5第四项，已吸收。另有性能审计A1/A2/A5/A6/A7已完成，A3列宽共同装配、A4台账及整体动效风格明确保持。若地图所谓“此前三个候选”指另一份未给路径的临时HTML，需要主控提供该文件逐项对照，不能凭数量相同认作同一组。

## 当前具名发现、静态风险、假设与保持项

| ID / 等级 / Q、P | 可达源码事实及实际影响边界 | 最小下一步，不预定重构 |
|---|---|---|
| F1 高可信静态恢复风险；Q6/Q7/Q8、P9 | 规则新增 `rules.tsx:90–100` POST成功丢回执后仍保同表单，catch只显示“没能保存…重试”；此路径无 uncertainWrite、稳定request_id或结果查询。前端允许再次提交是可达事实，是否生成重复规则须核后端约束。 | 先核 `/api/m14/rules` 创建契约及唯一性；若未幂等，用隔离副本一次成功但丢回执，观察保存数与重试。现有 `test_rules.py` 保“不重算旧剔除”，未专测此失败。 |
| F2 待核交互风险；Q2/Q7/Q9 | `users.tsx:51–62` 的run无同步锁/busy；恢复与启停按钮`:88–91`未按请求在途禁用。重复点击可能发多个相同动作；本票未证业务损害，后端set-state幂等可能令其低收益。 | 后端核status/restore是否幂等、历史是否重复；先确认真实后果，再选择一个慢请求双击反例。不得将前端按钮缺锁直接称越权漏洞。 |
| F3 高可信读取边界风险；Q6/Q7、P9 | `projects.tsx:89–91` 两个待办只检查items数组/source对象，trails数组后 `as Trail[]`；不像flow/contracts的逐字段解析。畸形嵌套项可进入后续布局/按钮。当前正常服务端返回未见失败。 | 选择真实渲染必用字段做一条坏200反例；核是本区ReadFailure可重试、还是PageError/错误默认值。只补明确可达字段，不全站无差别schema化。 |
| H1 待测成本假设；Q1/Q5、P6 | `notices.tsx:87–97,175–185` 全量映射、project.find、搜索/selected与shown匹配、金额下限；`grid-layout.ts:120–175`按全结果构造文本/签名，DOM批量128仍有总工作。既有三列textOnly缩短首读，不能据此宣布剩余步骤热点。 | 复用1261原列表/266默认结果的来源口径，当前版本先分网络、解析、过滤/下限、layout/paint；固定动作完成定义。无收益证据保持，不预设Map/cache/分页。 |
| H2 长会话/隐藏子页假设；Q1/Q7 | `big.tsx:55–60` visited月份只增不减，各月保树；settlement子tab用hidden但传active，顶层PageSurface保留尺寸机制并不直接覆盖所有内层隐藏box。保存草稿是有意消费者，不能直接删保活。 | 只有多月/多tab真实使用或可复现慢点时，记录同状态DOM/heap/AG队列及草稿保留；本轮无泄漏证据，不默认20轮长期测试。 |
| R1 可能未用的旧前端出口；Q5、P8 | `fees-api.ts:3–27` 的FeeRow/FeeData/readFees/getFees仅本文件出现；实际页用`:40` getFeeYear。定向检索src/tests未找到消费者，后端月度API和 `test_fee_items.py`仍有有效业务。 | 只记前端出口可达性待确认；若以后退出，核构建/import/外部脚本后只删无消费者前端定义，保后端契约及有效业务测试。不是本票清理授权。 |
| K1 保持；Q3/Q5 | 主题后端唯一roles、CSS固定顺序、MotionProvider稳定、普通保存静默、已退役快捷键不恢复；这些有现行产品规则和近期证据。 | 可见新回归再具体处理；不能以通用质量文档重写整站交互或恢复键盘导航。 |
| K2 保持；Q5/P3/P5 | 三类表格、独立台账队列、全量本地筛选有各自当前用途；共享金额显示虽经notices-api兼容再导出，真正cents/money已归api.ts。仅import路径相似/文件较长不足以另造全局层。 | 若真实规则变更需要多处同步且产生遗漏，再做具体影响演练；本票不以目录或重复数裁架构。 |

## 前端相关测试的具名责任与可信度

- 快速纯逻辑/契约：package脚本内 `business-time`、`cell-save`、`contract-subtable-overage/recovery/workspace`、`contracts-api`、`flow-api`、`grid-value-filter`、`grid-width-state`、`i8-browser-relay/i8-relay-recovery`、`identity-gate`、`inline-field-queue`、`inventory-api`、`mechanical-api`、`notice-amounts/codes/fetch-submit/maintenance-mode`、`oilcard-batches/invoices/ledger-edits/transfers`、`project-picker-order`、`random-id`、`read-region` 共26个文件。这些分别保护金额/身份/异步/契约，不靠数量证明整站。
- 运行/隔离主人：`conftest.py:11–41`只接已登记真实副本，写入fixture复核disposable；`test_preview_copy.py`保护副本边界、凭据排除和外呼阻断；`test_preview.py`含正式构建资产/真实读取/权限/会话及格内写回；`live_data.py`、`preview_select.py`是数据选择与虚拟下拉辅助。`live_data.open_page:31`仍用networkidle，所以引用它的普通行为测试不能直接用其完成时间作性能终点。
- 共享显示：`test_startup_styles.py`、`test_page_loading.py`、`test_async_layout_ownership.py`、`test_font_recovery_protection.py`、`test_first_display_retained.py`、`test_grid_widths.py`、`test_grid_migration.py`、`test_table_selection.py`、`test_dialog_confirmations.py`、`test_shared_controls.py`、`test_read_ui.py`。其中真实hook DOM小样的异步owner测试不等于业务页性能trace。
- 读取状态：`test_read_lanes.py`、`test_debt_loading.py`、`test_contract_oilcard_read_lanes.py`、`test_process_mechanical_loading.py`、`test_report_maintenance_read_lanes.py`。有受控延迟/坏响应，验证加载与错误呈现；不能据mock认定真实金额、权限或外部集成通过。
- 领域/导出：`test_home.py`、`test_project_history.py`、`test_acceptance_b.py`、`test_write_receipts.py`、`test_notice_association.py`、`test_contracts.py`、`test_invoices.py`、`test_contract_export.py`、`test_ledger.py`、`test_ledger_layout.py`、`test_export_dialogs.py`、`test_process.py`、`test_big.py`、`test_settlement.py`、`test_inventory.py`、`test_fees.py`、`test_fee_items.py`、`test_mechanical_details.py`、`test_mechanical_reports.py`、`test_i8_session.py`、`test_i8_fetch_entrypoints.py`、`test_rules.py`、`test_users.py`均已有具名路径；测试函数名/关键fixture已检索，不声称逐条断言和全部运行日志已深审。
- 最小验证缺口先由风险选择：E5金额新端点的一条浏览器连续编辑联通；F1/F2须后端契约先行；F3一条坏200；油卡非空真实代表及当前性能条件另由选景票决定。不重复运行全部已有绿例，不建立固定用例数量门槛。

## 代表动作及数据规模来源

这些是客观候选，不是用户已选痛点。选择后才固定版本、隔离数据、机器/浏览器、主题/字号、视口、缓存和完成定义。

| 候选任务 | 规模来源与可信边界 | 起止/保留行为、最低需补 |
|---|---|---|
| 通知书首进、保活返回、精确搜索、连续两金额格 | E4旧1261总通知书、266默认未付清、精确搜索1条；E6旧首页未关联深链3条。当前真实计数未读。 | 导航/输入→当前正确表与合计绘制，取本次请求/布局标记；连续编辑核下一格即时输入、原格不退、未知不重投。优先用常规1920×1080/1.12，并与旧字号1分开。 |
| 库存期间/列筛选、定位、调整后读回 | E1旧18287行/747调整；前轮原响应约16MB是旧条件。不能以当前月显示0行判断全量空。 | 筛选输入→正确行/完整合计；保原/有效值及零HTTP本地筛选，定位实际滚动容器。规模和长文本先从副本元数据确认。 |
| 集采统一搜索、勾选、子表开关/丢回执恢复 | status历史发布271合同；E1旧勾选交互对照，E7子表真实增删/同ID恢复。当前侧明细行数未知。 | 鼠标动作→选中/摘要/子表ready；手调宽、草稿、金额与两侧超额提示保持。先量当前完整列表，不把旧毫秒当预算。 |
| 大表切月、年度提取、费用展开/保存 | E6读2025-12至2026-10，最大大表9项目；没有第二档更大真实样本。年度/费用峰值未知。 | 范围切换→仅新范围金额且自然高度完成；保整页滚动/合计、月草稿和POST导出名单。不要捏造更多真实行凑组合。 |
| 欠款切项目、下一格输入、失败读回；流水搜索/深链 | E4慢写读回64帧未复现旧值回退；具体当前项目/月份峰值未知。 | 明确跨项目隐旧值、保空间和草稿；流水深链不等待欠款。若复测目标无新差异，复用旧正确性证据，不强并队列。 |
| 机械四工作区切换、零租连续编辑、公司汇总 | E0原page约1.19MB，四表7421格同源对照；具体当前明细行/项目数须新副本统计。 | 不生成Excel的页面链、签名/源状态/草稿保持；只对可得范围定标，不拿旧单次327ms扩到所有月份。 |
| 油卡总览/充值/非空发票及备注/联动 | E2空档案；E4发票0条故只mock备注；E8旧309来源均待确认不能当已计账样本。当前有效非空代表未知。 | 优先补真实已登记非空集合与相应金额/归属/原件；在此之前不排“优化油卡性能”或称完整业务已覆盖。 |
| 项目/规则/用户首读与失败恢复，主题/缩放 | E1规则29行、用户4行是旧样本；项目数未在已读证据固定。 | 小集合先静态和可达失败，F1–F3定向补证；共享主题只选不同表格职责代表，完整八主题矩阵须有具体影响理由。 |

## 提交给主控的边界

本次已具名登记16路由、共享UI/网络/状态、页面内模块、测试/工具链、外部/生成内容及一个疑似无消费者出口；已核近期整改吸收和旧证据的版本差异。没有宣布任何业务域全维达标，也没有发现足以直接启动表格、缓存或框架重构的当前性能根因。前端底线待与后端分区合并：实际权限、金额权威、事务/幂等、导出文件及真实i8仍需各自证据。原件和所有无关状态保持，本调查唯一写入为本Markdown。
