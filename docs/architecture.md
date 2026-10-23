# architecture · 运行结构与工程约束

> **读者**：定位结构或改工程行为的人与Agent｜**回答**：运行拓扑、分层边界及共用实现约束。
> **何时读**：改模块边界、数据流或共用内核之前。业务取值回交付面；状态回主计划§0/§15。

## 一、运行结构与分层边界

FastAPI由NSSM托管，单worker；PostgreSQL同机，测试库与开发库物理隔离。抓取走HTTP，打印渲染在服务身份下运行；前端唯一落点是 backend/app/web/，原型已退为历史参考。
抓取只由人工点击触发，无调度器；失效重登限于本次人工链路，失败/超时不得自动重试登录。顶号告知与确认按交付面《说明书》§3.1.3执行。
目录职责见 README.md §三；模块映射见 docs/architecture/modules.md；运行与恢复入口见 docs/guides/deployment.md。

| 层 | 责任与边界 |
|---|---|
| core | 金额、时间、配置、鉴权等共用出口；不得import业务包。需要业务数据时定义loader/bind接口，由 backend/app/core_bindings.py 在装配层注入；取数实现留在数据主人包内。 |
| mod* | 一模块一包；包间只经对方service调用，不跨包直查表或import repository。service可以再导出repository函数；出口必须能够打桩替换。现有按设计的例外以 backend/tests/test_layering.py 与实现文件头为准。 |
| web | 判定与写入走后端；不照抄原型存储结构。文件清单/加载顺序见 backend/app/web/index.html；读取壳字节走 tools/audit/shell_source.py，读取语义走 tools/audit/shell_api.py。 |
| tools | 检查与操作工具的用途、读写边界见 tools/README.md；不以检查结果替代业务口径。 |
| ops | 服务、部署、备份与恢复；运行凭据从.env读取。初始化SQL的既有公开口令风险与处置边界见 docs/guides/deployment.md §二。 |

分层守卫见 backend/tests/test_layering.py；由C2判据守「不得跨包把对方模型当查询目标」，typing/domain/join条件的正当引用不受限。活的隔离自证在 tools/mut/_mut_layering.py；core业务注入不另抄取数实现。

## 二、共用实现约束

以下为工程实现的约束与查阅入口；本节《说明书》节号指 [材料科业务全流程说明书](requirements/材料科业务全流程说明书.md)，产品资料清单见 docs/requirements.md；`delivery/` 保留第三方原件及实际资源，不作为现行业务正文入口。

### 查询文本读取

共用纯读取落点为 `backend/app/core/query.py`；调用者及等价验证见 `backend/tests/test_report_query.py`。字段、默认值与合法性仍回各业务包及交付面主人；月份入口未改，调查与暂缓证据见TAIL-302票Comments。

### Excel工作簿读取

现行付款计划及过程资料导入使用 `backend/app/import_kit/workbook.py` 的开书、工作表枚举、网格遍历、合并坐标及资源释放，格式转换由 `backend/app/import_kit/readers.py` 持有。
选表、表头、映射、行筛选及确认写入由现行域声明和共享引擎承接。原集采专属读取链已随导入归档，来源及接回条件见 docs/archive/retired-imports-20261015/README.md。现行验证在 `backend/tests/test_excel_reading.py` 与 `tools/mut/_mut_excel_reading.py`；真实样表边界回TAIL-346及原TAIL-305 Comments。

### 金额

| 要点 | 依据 |
|---|---|
| 单位/精度/舍入/判定 → **回 §9.1**；存储形态 → **回技术栈 §3.2** | §9.1 · `DEV-P-03` |
| **计算一律 `Decimal`，禁 float**；**唯一出口 = `core/money.py`**（全站不得自写） | §9.1 · `§9.8.2-1（实现侧）` |
| 三档取值判据**有意不同、勿统一**：集采发票/付款金额 **> 0**；付款通知书三金额、手动新增、机械 6 列、大表手填、批量付款额、调整单金额 **≥ 0**；特殊费用手填项**允许 0 与负数** | §8.4 |
| 统计两金额**上限 = 审批金额**（超额**拦截并保留原值**，不警告不写库） | §4.2.5 |
| **禁**：`_cents` 后缀/整数分列入库（"比较转分"只是代码内动作） | §9.1 · 技术栈 §5-12 |

### 时间

| 要点 | 依据 |
|---|---|
| 对外参数一律 **`start_date` / `end_date`（ISO 闭区间）**；核算期仅兼容 | §9.2 |
| 各表**默认年月**：付款域类 = 当月；报表类 = 上月（**仅默认值，可改**） | §9.2 |
| 四种模式**共用一个选择器**；**抓取与导入只允许「单月」**；**不设"全局核算期"** | §9.2 |
| **归月展示可用 `substr`，但月份过滤必须用日期闭区间**（保索引 sargable） | 坑 1.2-6 |

### 旁路与手改保护（全书最重要的设计模式）

| 要点 | 依据 |
|---|---|
| 源数据**永不被人工修改**；人工判断走旁路载体 | §9.3 |
| 三处旁路：统计两金额 · 调整单 · 集采实际供应商 | §9.3 |
| ⚠️ **"不被导入覆盖" = 不被人工改以外的力量覆盖** —— **源字段仍跟随 i8 新值** | §4.2.7 |
| **留痕范围勿扩大勿缩小**：留痕 = 统计两金额 / 调整单(+必填备注) / 项目全名 / 项目状态；**不留痕** = 手改分类 · 集采实际供应商 · 合同纳入标记 · 剔除标记 · 撤单标记 · 展示名 · 会话级付款金额 | §9.3 |
| **自动预填也不得静默落库**（供应商匹配值须带「待确认」，人工确认才转正式值） | §8.4 |

### 幂等与并发

| 要点 | 依据 |
|---|---|
| 付款临界区（读余额 → 防超付 → 写流水 → 重算）**用 `SELECT … FOR UPDATE` 行锁**串行化；乐观锁只用于"改分类"等低频冲突（返回 409） | 坑 1.3-9 · 技术栈 §3.2 |
| **取号**：占位名序号 **事务内取号**（`SELECT MAX` + 行锁；唯一索引 + 退避重试兜底）；**必须补并发撞号测试** | 实施计划 §四-5 |
| **导入幂等** = 单事务内「先删自动行 → 再 `INSERT … ON CONFLICT` 上写」；**手动行不被触碰** | §9.5 |
| **长任务不持写事务**：打印/抓取**先取完数据、关掉写事务再渲染与投递** | 技术栈 §3.2 |
| ★ **无定时任务**（D9，用户拍板）：**不引入 APScheduler**，抓取一律**人工点击**触发。⚠️ 但**同一张表的抓取要串行化**（进程内互斥），防两人同时点同一张表 ⇒ 双份顶号 + 重复写入；每次抓取仍**留一条执行记录** | 用户拍板 2026-09-15（**覆盖**技术栈 §3.1 的「APScheduler 主选·一期启用」）；执行记录依据 §3.1.3 |

### i8 接入

| 要点 | 依据 |
|---|---|
| **纯 HTTP 登录（SM2）+ Cookie + 失效自动重登**，不起浏览器（Session 0 可用） | §3.1.2 |
| ⚠️ **登录含 KillOnlineUser（强踢）** ⇒ 抓取**一律人工点击**（D9），界面须**二次确认 + 明确告知会挤掉该账号其他在线会话**；❌ **抓取失败/超时不得自动重试登录**（重试 = 再次顶号）；失败**显式报出**并落执行记录 | 素材包 `delivery/PRD素材包-20260911/input/http_login.py` 注释 · §3.1.3 · 用户拍板 D9（2026-09-15） |
| 抓取**按时间全量、不分页**；触发方式：付款通知书 / 收发结存 / 库存单据 / **集采合同 = 全部人工点击**（★ D9 取消了集采的定时自动） | §3.1.2 · `API-01`…`04`（⚠️ `API-04` 的触发方式已按 D9 变更） |
| **统一降级**：接口不可用 → 手动下载 Excel → 系统导入 → 自动处理（抓取与导入**共用同一解析/落库管线**） | §3.6 · 技术栈 §3.2 |
| GBK 响应按 `response.encoding` 显式解码；子进程 stdout 用 `errors='replace'` | 技术栈 §8 · 坑 1.2 |
| 实现参考 → `delivery/PRD素材包-20260911/input/`（取数导出）· `app/`（旧后端）· `i8一键打印/反解件/`（打印，⚠️ 仅 `profiles_payment_bill.py` 反解完整） | ⚠️ **旁证，口径不得反推** |

### 打印链路（切片 1 核心）

| 要点 | 依据 |
|---|---|
| **版式一律取自 i8**（`getPrintDesign`），**不得自行设计**；本地只渲染与出纸 | `DEV-P-07` · `NG-11` |
| 两类 `printId` 分流（机械类 / 辅材·集采类） | `05-任务分解.md` §三-1 |
| 出纸：**IPP 直投**（不依赖打印驱动与桌面会话） | 技术栈 §2.4 / §3.1 |
| 每次打印**须留执行记录**，供看板提示「打印投递失败」 | §4.6 |

IPP回执按协议成功类别判定接收；属性替换或冲突提示核对出纸效果，不报“单据未投递”。已接收仍不代表已经出纸，现场完成状态须实际核实。

渲染器当前使用headless Chromium；不调用browser.close的防挂死处理仍在 backend/app/mod03_notice/print/render.py，退出与驱动回收由宿主负责。不得误删该处理；改生命周期时按真实服务身份复做。机器级浏览器路径见 docs/guides/operations.md §三与 docs/guides/operations.md。

### Excel

| 要点 | 依据 |
|---|---|
| **openpyxl 写模板/导出 + pandas 读入/透视/提取 + `zipfile` 打包** | 技术栈 §3.1 |
| 导出**与当前筛选一致**（行集合/合计行/取值）；模板**只管长什么样**，数据永远来自页面筛选结果 | §7.1 |
| 模板填充：数据区起点 = 标记文字 **`DATA_START`**（⚠️ **不依赖 Excel 定义名称**）；**尾部行块按实际行数派生**（不得写死行号、不得用"删行"让位）；**模板列未登记对应关系一律报错，不猜** | §7.1 |
| ⚠️ **风险**：「原表加数据透视表」纯代码难生成 → Plan B = 含透视表的模板注入数据 / 透视结果以数值输出 | 技术栈 §5-1 |

### 工程纪律与环境

- schema变更走Alembic；两库迁移一致。测试固定PostgreSQL，不可用时显式失败，不回退SQLite；外层事务/SAVEPOINT隔离，写路径API测试复用隔离会话，连接到开发库即熔断。
- 中间件顺序：IP白名单在内、request_id居中、CORS最外。N+1禁止；批量查询用JOIN/IN，统计SQL包含未删除条件；金额统计上线前用EXPLAIN ANALYZE核查全表扫描。
- deleted时间戳与业务撤销voided语义不同；快照保留金额原始精度。依赖规则见 docs/guides/deployment.md §六，行数与读取预算只回 docs/reference/thresholds.md，原计划的“超线禁合入”旧文字已退场。
- 本机事实与写文件/运行命令的坑回 docs/guides/operations.md §三/§四；方法回 docs/guides/development-and-verification.md。服务调用外部程序时，必须按服务账户身份复核路径可达。

### 安全操作历史

`core/history.py` 在 `session_scope` 事务内观察变更，`history_bindings.py` 装配允许的入口、模型和字段；可逆快照或不支持边界与业务写入同事务提交到 `operation_history`。账号绑定键由完整账号摘要生成，原账号不限长度；历史值仅留服务端。拟付款方式入口在同一业务事务内登记不支持边界。

`history_api.py` 核当前在用账号，按账号事务锁串行写入/撤销；重放核预期历史头、锁定目标及关联项目，比较完整值和 PostgreSQL xmin，整批通过后才修改。可信恢复以目标原事务版本和完整值共同续接，跨无关动作更新后续父守卫，遇实际修改该行的动作或版本断点即停；范围限同账号、同重放方向及最近barrier之后的有效历史。新条目在changes内保存target_version并随重放交换，无需schema迁移。旧条目缺少该凭据时仍校验自身并允许安全单步重放，但不推断跨动作续接，后续可能保守拒绝；不批改生产历史。拟付款方式的账号锁、业务更新、barrier及旧redo失效在同一事务提交。规则或表结构变化不猜测重放。

壳 `history.js` 持有摘要、写入等待和快捷键，静态按钮位于用户名左侧；复用 `API.send` 的统一跨页标脏和现有加载链。`api.js` 在写入后刷新历史（包含表单303回跳），切换账号立即清旧摘要。功能范围回《说明书》§1.5.1。

## 三、主题与壳加载

主题行为回交付面《说明书》§7.7与 docs/guides/frontend-design.md；以下只记录工程实现形态。
**结构规范（四条，缺一条就不算"一套合格的主题"）**

| # | 规范 | 落在哪（单一真源） |
|---|---|---|
| 1 | **一行种子 → 派生整套 67 个变量**（每个色值只写一次；"每套覆盖同一组变量名"由`构造`保证，不是靠人记） | `page.py` 的 `_derive()`＋`THEME_SEEDS` |
| 2 | **四档成组**：每个状态色按「主色 / 深字 / 浅底 / 浅边框」四档同套（§7.7 硬要求） | `_STATE_SEEDS` ＋ `_derive()` |
| 3 | ⭐ **侧栏三档文字 ＋ 选中项底 = 主色**：`--sb-hd`（品牌/悬停）· `--sb-tx`（普通项）· `--sb-mut`（编号/分组/页脚）；选中项底 = `--sb-on`（= 主色本尊），字 = `--on` | `_derive()` 的侧栏段 ＋ 壳 `.sb-*` 选择器 |
| 4 | ⭐ **可读性下限（硬闸门）**：凡"给人读的文字"，对比度 **≥4.5**（WCAG AA；本仓没有 ≥24px 的字号，⛔ 不许拿"次要文字"降标准）；纯装饰（分隔线）≥1.15 | 判据 `tests/test_theme.py::test_每套主题的关键配对都过对比度AA` ＋ 体检器 `tools/oneoff/_theme_contrast.py` |

主题身份、场景与风格的现行清单直接读取 backend/app/mod03_notice/page.py 的 THEME_SEEDS/THEME_SPEC；测试守护两表键集、10套独立主题及场景。改名或新增主题属于口径变更，沿用授权边界。

主题真源与派生见 backend/app/mod03_notice/page.py；全站同源、不在壳内另定义:root、CSS色值扫描和打印件隔离见 backend/tests/test_theme.py。服务端BASE_CSS和/static/theme.css使用同一真源。

**⛔ 三条不许动的红线**（`P3` 起就钉着 · 长期有效）：① 逐路 `soft()` 容错 ＋ **失败点名**（`test_wired_boot.py` 钉着）；
② `m07`/`m05` 对 `reloadMech` 的**依赖屏障**（现行 `LOAD_DEP`）；③ 写动作后**必须**回后端真实状态（不许靠"本地改＋不重拉"省请求）。

库存列表、过程资料与大表按各自入口取数；m06读矩阵与机械，m07读报表与机械，两页均不预拉库存全量。依赖清单直接读 `backend/app/web/shell/core.js` 的 `PAGE_LOAD` / `LOADERS` / `LOAD_DEP`，写后标脏保持全页新鲜度；变更前核对实际消费者，避免按旧依赖补回无用请求。

⚠️ **两条口径**：① **原型切片不许搬出 `index.html`**（旧U1逐行比对已退场；初始化期加载约束仍需遵守，变更前核对当前加载顺序和判据）；
② 改多文件加载须验证通过服务的真实脚本加载及顺序；按实际范围核验，执行入口见 docs/guides/development-and-verification.md §十一。

壳的语义读取入口是 tools/audit/shell_api.py，测试侧只转发的入口是 backend/tests/shell_src.py；剪刀清单由 backend/tests/shell_scissors.py 守护。

表格布局由 `backend/app/web/shell/view.js` 的 `layoutTable` 按隐藏列、实测宽度、冻结列顺序收尾，`layoutTables` 负责当前页面及单一防抖缩放入口；`runBind` 在页面步骤之后调用它，虚拟窗口仅对刚更新的表调用，不重跑页面步骤。重画前后的位置保护由同文件的 `saveTableScroll` 持有，不改变虚拟滚动仅换tbody的约束。

集采三张子表的新增、删除通过 `backend/app/web/shell/core.js` 的 `jcSubAct` 完成写后刷新：沿用 `jcAct` 重载真实列表，再以合同id定位当前行，由 `jcSubDlg` 对应弹窗读取一次明细。新增成功才清草稿；删除保留未保存草稿，拒绝或异常不清草稿。调用者不再保管跨刷新的行对象或自行安排重复重载。

合同关联候选由 `backend/app/mod11_jc/service.py` 的 `_link_candidates` 按请求批量读取通知书、项目与既有关联，沿全项目合同集派生序号，再逐条产出候选；人工推荐只对候选读取一次发票和付款事实，一键关联预览不逐条查通知书及关系。推荐证据和唯一匹配仍分开判断，确认时重新读取应付、锁定重读通知书的要求不变。

**列表页的「列身份」**（`TAIL-298` · `m11` 是样板）：一张表的列清单**一个主人** —— 业务包的 `domain.JC_COLUMNS`（`m11_jc`）⇒ ① 壳的表头由它**现生成**（`shell/pages-b.js::jcThead`，⛔ 壳里不再写列字面量）；② 屏幕行为（默认隐藏 / 钉列）只写**列 id**（`JC_HIDE_IDS` / `JC_PIN_IDS` = 后端 `key`，⛔ 不写列号 —— 列号是"位置"，加一列就得人肉同步且**漏改不报错**）；③ Excel 导出由它**派生**（`report_export/jc_export.py`：列集 = `JC_COLUMNS − PAGE_ONLY_KEYS`、表头字 = `export_label`（缺省 = `label`，屏幕注解不进 Excel）、合计列 = `SUM_KEYS`）。判据：`backend/tests/test_tail298_columns.py`（导出派生 ＋ **值级**键覆盖）· `backend/tests/test_ux_pages.py::001-61`（行为表 id ∈ 规格 ＋ 偏移量出来）· 真机 ㉝ `tools/probe/_shell_jcpin.py`；自证 `tools/mut/_mut_tail298_columns.py`。

TAIL-301补齐行与合计：`V.m11` 单元格按id绑定、由同份列清单排列，普通新列读同名行字段；API的 `sum_keys` 派生自 `domain.SUM_KEYS`，`pages-b.js::jcSumColumns` 按id查位并保留原求和算法。判据 `backend/tests/test_tail301_columns.py` 演练加列/调序，隔离自证 `tools/mut/_mut_tail301_columns.py`。

## 四、渲染层删改保护

该表是删改前的检查清单，不能推断每个旧文件/端点仍存在；历史行保留提醒，实况以代码、调用方和判据为准。

**删改前逐项核对调用方与保护判据**：

| # | 不删的东西 | 为什么要留 | 证据（文件:行） |
|---|---|---|---|
| 1 | `backend/app/web/index.html` | **这是新壳本体**，不是"旧层" | `backend/app/main.py`的`/app`托管 |
| 2 | ✅ **旧静态页 `m03.html` 已删（2026-09-19 · 批 4.5）** —— 此前**不在此列**（**订正**：按 `D18` 它在删除范围内）；其前置「批量打印 / 只导出 PDF / 打印机设置接进新壳」已于 2026-09-18 补齐（`TAIL-46`），`test_acc_pay_setup.py` 的断言同期改指新壳 ⇒ 该文件与其托管机制（`main.py` 的 `_PAGES`）一并删除 ✓ | `main.py`（`_PAGES` 已删）· `test_acc_pay_setup.py`（断言已指新壳） |
| 3 | `mod03_notice/page.py`（＋其拆出的 `list_page.py`） | 是**全站共用件**（`THEME_CSS`/`BASE_CSS`/`esc`/`sort_rows`/`nav_html`），`main.py`＋`mod04_plan/service.py` 等处都在用。⚠️ 2026-09-21 起 **`home/view.py` 不再在列**（该文件已删 —— 看板进了壳）；⭐ **2026-09-21 拆出 `list_page.py`**；⚠️ **本件仍是老调用方的入口**（`page.X` 一律再导出，⛔ 拆件不改调用方） | `backend/app/main.py`主题路由与实际调用方 |
| 4 | `/static/theme.css` 路由 | 主题**唯一真源**（改主题只改一处）；`test_theme.py` 有同源断言 | `backend/app/main.py`主题路由 · `backend/tests/test_theme.py` |
| 5 | `core/nav.py` | 服务端导航数据源（`nav_html` 使用）。⚠️ **2026-09-21：四条指向"暂留件"的入口已随四页搬进壳而删除** —— 它此后只服务**仍在的服务端渲染页**（现只剩登录页）；**新壳的侧栏另有自己的一份**（`backend/app/web/shell/view.js` 的 `NAV`） | `mod03_notice/page.py::nav_html` · `backend/app/web/shell/view.js` 的 `NAV` |
| 6 | **`POST /m05/opening` · `/m05/opening/delete` · `/m05/ledger/remark`** | ⚠️ **新壳正在用**（另有 `_e2e_m05_wired.py` 真机） | `web/index.html` 各 `API.*` |
| 7 | `GET /api/m03/notice-list` ＋ `list_data.py`（`build_page_data`/`columns`/`summary_row`/`_row_dict`）＋ `list_view.py` | **新壳 m03 的数据源**（数据侧已归位到 `list_data.py`，与 API 共用同一份） | `notice_api_router.py::get_notice_list` |
| 8 | 全部 `/api/m01…m14/*` JSON 端点 ＋ `/api/m03/settings/printer` | 新壳 `boot()`/`reload*()` 的唯一取数口 | `web/index.html` 各 `API.*` |
| 9 | `mod04_plan/plan_ui.py`·`plan_manual.py`·`project_views.py`·`mod06_proc/mech_ui.py` | **业务纯函数**（被 JSON API 复用），不是页面件 | `plan_api_router.py` · `mod06_proc/router.py` |
| 10 | `/healthz` | 启动健康检查 | `main.py` |

**每批的固定动作**（✅ 本尾巴已收官；⭐ **下一轮若要再删服务端渲染件，照这一节办**）：
① 删除前查引用与数据后果，按授权逐项处理，不绕过删除守卫。
② ⭐ **先搬观测面、再删页** —— 「借页面渲染看数据」的测试也算观测面（`m04` 那次回滚的教训：删页 = 观测面没了）；
③ 钉旧形态的断言一律**改指新壳 / 新出口**（⛔ 不删判据 —— 判据是"产品 claim"，形态变了要**搬断言**）；
④ 删任何模块页时**先看 `core/nav.py` 有没有指向"暂留件"的入口**，没有就补/改一条（否则暂留页连入口都没了 = 事实上被删）；
⑤ 提交与推送按 docs/agents/workflow.md执行；已提交的批次可用git revert回退；⑥ 修复与当前批相关的失败并复验，无关提示保留事实；
⑦ 收尾按 docs/agents/workflow.md核验；撤销无效绑定须注明原因与未全量刷新边界，历史绿数不能替代有效覆盖。
