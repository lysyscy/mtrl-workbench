# TAIL-283: 付款流水页补通知书信息，兼修「操作人／流水号」两处列义

**What to build:** 付款流水那一页光看现有九列对不上账 —— 补上这笔流水**来自哪张付款通知书**的几件事：通知书日期、通知书名称、收款单位、审批金额、分类（辅材/机械/集采）。同时把两处**一直在骗人**的列义改对：「操作人」现在显示的其实是创建时间，「流水号」现在显示的其实是数据库行号（真业务流水号在库里、导出却在用行号）。页面看到的、Excel 导出的、搜索匹配的必须是**同一个东西**。

**Blocked by:** None (can start immediately) —— ⚠️ 与 `TAIL-281`、以及在办的 m11/m05 壳改动可能同文件（`shell/core.js`、`shell/proj.js`、`index.html`、`shell/pages-a.js`），开工前先确认它们的处置，避免两批差异混成一票。

**Status:** done

- [x] 五列上身且**一条流水一行、批量取数**（复用 `build_flows` 已预读的 notices 字典 ⇒ ⛔ 不许逐行查库 N+1，⛔ 不许依赖前端 `NO` 缓存有没有载入）：通知书日期（`doc_date`）· 通知书名称（`fields['BillName']`，与通知书列表同一取值口径）· 收款单位（`payee`，⛔ 不许拿集采供应商替代）· 审批金额（`amount_approved`）· 分类（沿用既有中文类别出口，⛔ 不另造枚举）。
- [x] 「操作人」列显示 `created_by`（不是 `created_at`）；旧记录缺操作人**如实留空**；页面与 Excel 同义。
- [x] 「流水号」列、关键词搜索、Excel「流水号」列三处都读**真 `flow_no`**；撤销按钮与 `export_flows(ids)` 的定位**仍是数据库 `id`**（⛔ 不许把文本 `flow_no` 当接口 id）；旧流水 `flow_no` 为空时给稳健显示（留空或经测试确认的回退），⛔ 不编造编号。
- [x] **合计只加实付金额**：审批金额在同通知书的每行重复显示供对照，**不纵向求和**（1000 审批 + 两笔 300/200 ⇒ 合计 500，不是 2000）。
- [x] `notice_id` 为 NULL 或通知书已失联的流水**照旧能查**（⛔ 不许被内连接过滤掉），新列留空或「—」，⛔ 审批金额未知**不伪 0**（别用 `numOr0` 糊过去）。
- [x] 已撤销流水在「全部／已撤销」可见并带原因，不进生效合计；历史导入的空付款方式**保持不变**（⛔ 不兜底成「现汇」）。
- [x] 页面结构跟着改全：`FL_THEAD` 表头 · 每行 `<td>` · 合计行（**金额列下标不再写死 4**）· `sumRowOf` 的 leadSpan · 空态 `EMPTYROW(thCount(...))` · 宽表横滚与固定列仍对齐。
- [x] 新增金额列按**数值**排序（⛔ 不许字典序 `100 < 20`）。
- [x] 导出与页面一一对应：仍只收**当前可见流水的数据库 id 顺序**，列头/字段/`MONEY_KEYS` 同步，金额是数字而非文本；补**逐格** Excel 测试（⛔ 不得拿 `test_tail04_export.py` 冒充 —— 那是收发结存/库存导出的）。
- [x] 站点回归：`test_acc_flow_list.py`、`test_acc_flow_pst.py`、`test_wired_m05.py`、`test_page_m05.py`、`test_tail04_pages.py`、`test_shell_render.py`；「付款统计/欠款/多笔付款撤销」行为一律不变。

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：用户提供的《剩余三项问题（R3/R4/R6）只读审查与实施交接书》**第 4 章（R6）**（同件第 4.3 节的两处列义缺陷是原审查的额外发现，并到本票一起修，理由见 4.3：「一并解决更能避免页面与 Excel 对不上」）。不做会怎样：对账时看不出这笔钱是哪张单、谁办的；「操作人」一列写着时间，「流水号」一列写着行号，导出与页面还各说各话。落点：`mod05_flow/service.py`（`_flow_dict`/`build_flows`）· `mod05_flow/router.py`（`export_flows`）· `report_export/fl_export.py`（`COLUMNS`）· 壳 `core.js/proj.js/pages-a.js/index.html`。阶段 / 时机：随时。

**排期四问（`§14.3` 同源）**：①**业务口径一个字不改** —— 只加「这笔流水来自哪张通知书」的展示信息，统计/欠款/已付两态计算全不动。②**要改**是因为现在页面与 Excel 对不上账，且有两处列义是错的（不是缺功能，是**说错话**）。③**改哪一层**：后端 `_flow_dict` 一处加字段（已有 `notices` 字典，无需新表）⇒ 适配层 `adaptFlow` ⇒ 表头/行/合计/排序 ⇒ 导出映射，一条链改完。④**怎么算做完**：上面 10 条验收 ＋ 交接书 §4.6 的反例矩阵（含「通知书失联」「同单两笔」「历史导入空付款方式」三个刁钻场景）。

**未验 / 边界**：本票只落票，未实施任何代码；五列的**源字段**已由原审查核实（含「单据名 = `fields['BillName']`，不是模型独立列」这条易错点），但**列的选择与顺序**属审查建议，若用户另有取舍以用户为准。⚠️ `flow_no` 改显示后，**导出接口的入参仍是 id 列表**（`FlowExportIn.ids` 按 id 定位与排序的约定不能改）。

**2026-10-11 · 落账（agent）｜实施完成。** 十条验收落实；统计/欠款/集采口径一个字未动，未新增表/列/迁移/API。

- **后端**：① `mod05_flow/service.py::_flow_dict` 用**已预读**的通知书字典补五项（`doc_date` / `fields['BillName']` / `payee` / `amount_approved` / `category_label`，复用本域 `CATEGORY_LABELS`）；`n is None`（NULL / 已删除）⇒ 五项留空、审批额 `None`，⛔ 不 join 过滤、⛔ 不拿 0 冒充。② `router.export_flows` 改为**显式 `load(year_month="")`**（原先 `load()` 落默认当月 ⇒ 历史月份屏幕上有、导出来是空的，注释与运行代码正相反，一并改对）；映射真 `flow_no`；合计基数**只取生效**流水。③ `report_export/fl_export.py`：14 列（首列 `flow_no`，⛔ 数据库行号不进导出）、`MONEY_KEYS={amount,amount_approved}`（写数字）与 `TOTAL_KEYS={amount}`（参与合计）**拆开**、新增 `total_rows` 透传（全已撤销时补一条只作求和基数的零，与屏幕零合计一致）。
- **壳**：`core.js::adaptFlow` 修 `op=created_by`（旧取 `created_at`）、补 `flowNo/docDate/billName/payee/categoryLabel/amountApproved`（未知走 `null`，⛔ 不过 `numOr0`）；`proj.js::FL_THEAD` 扩 15 列；`index.html::V.m05` 行 15 格 ＋ `data-flow-id`，`sumRowOf` 下标 `{9:…}` / `leadSpan:9`；`pages-a.js` 的 `flDocNo`/关键词改读后端 `doc_no`/`flow_no`（⛔ 不再经 `NO` 缓存），新增 `flDomIds`（导出按**屏幕行序**，含"虚拟滚动时只留窗口 ⇒ 退回数组序、⛔ 不悄悄少导行"的护栏）；`actions.js::EXP_ROUTES` 加 `ids` 出口、`ACT.exp` 用之；`revDlg` 标题/「流水号」与成功回执都显示真 `flow_no`（⛔ 按钮 `data-fid` 与 `flowRevoke` 仍用 `f.id`）。
- **附带修正（先反例后改）**：全站排序的「合计行」识别原先扫**整行文本** ⇒ 「通知书名称」是自由文本，一张叫「…合计…」的单会让**普通数据行**被钉表尾。**改前**真机复现 `['200','100']`（期望 `['100','200']`）⇒ 收窄为「`sumrow` 类 ＋ **只看首格**」，跨列提示行仍由 `<td>` 数兜住。
- **测试**：新增 `backend/tests/test_tail283_flow.py`（装配五项/失联与真 0 两分/不 N+1；端点 → base64 → `openpyxl` **逐格**：全量装配、行序跟传入 id、首列是真流水号、合计只加实付、审批额不参与、全已撤销写零合计且无伪数据行、没挑到行不留幽灵合计）；`test_shell_ui_workflow.py` 新增 3 条 m05 真浏览器用例（新列与列义/失联行、合计与导出按屏幕行序、排序合计行反例）；`test_naive_export_parity.py`（FL 的 `total_keys` 旧假设）与 `test_tail04_pages.py`（补 FL 表头↔导出列逐字对应）同步新口径；`test_wired_m03_list.py` 的排序形态断言同步。
- **反向灵敏度**：`tools/mut/_mut_tail04_pages.py` **18/18 命中、SKIP 0、MD5 逐字节复原**（含按新形态更新的 `EXP_ROUTES` 锚点），末尾全套 pytest rc=0；`tools/mut/_mut_sort.py` 3/3（`applySorts` 改过）。
- **同批修掉先前留下的测试腐化**（每条都用 HEAD 版壳/实现复跑证实"红是先前就有的"，与 282/283 无关）：`test_wired_m03_action.py` 5 条（`ntRevoke/ntTrace` 变 `async` 的切片锚、「查看流水 / 查看关联」入口搬家、合同块补全 11 项）；`test_shell_ui_workflow.py::test_撤销付款跳转只定位生效流水`（`ntRevoke` 改走 `ntLoadFlows`，替身要给在 `API.flows` 上）；`tools/mut/_mut_m05wired.py` M3/M7/M8 三条过期锚点。
- **整轮按影响核验**（`_run_rulers.py --paths …`）：8 项审计 rc=0 · **140 项 pytest rc=0（160 s）** · **真机壳自检 rc=0（console/page 错误 0）** · **壳基线盖章 `20261011-0246`** · `BAD: []`。
- **未验 / 边界**：① 未在本机真库上点一次真实导出比对字节（逐格断言走的是隔离装配 ＋ 真端点，⛔ 不碰生产数据）；② 虚拟滚动（≥400 行）时导出退回数组序——该分支**只有护栏与注释，没有真机反例**（本机数据量到不了阈值）；③ 未提交（提交须另获授权）。

**2026-10-11 · 两轴 `/code-review`（基点 `14d53aa`，工作区未提交差异）。**

**Standards 轴（`matt-standards-reviewer`）**：硬违规 1 条 · 判断项 3 条。
- 【硬违规·**已修**】本批新增 / 改形的判据**没有对应反向灵敏度**（违 `ops/agents/issue-tracker.md` §四「自证」＋ `ops/前端设计守则-以使用用户为中心.md` §0「新增／修改判据时按仓内流程补隔离反向灵敏度」）—— 本批新用例在 `tools/mut/` 里 grep 0 命中。⇒ 新增 `tools/mut/_mut_tail282_283.py`：**14 条变异 · 命中 14/14 · MD5 逐字节复原**，逐条点名本批的新用例（草稿挂回行对象 / 事实比对 / 付款与撤销作废 / 失联伪 0 / 全量装配 / 合计并审批额 / 零合计行 / 操作人取错列 / 关键词拿行号 / 单据编码回 `NO` / 合计行下标 / `ids` 行序出口 / 排序整行扫）；`mut_cover` 台账 114 → **115**，`--check` 一致。
- 【判断项·**已修**】`router.export_flows` 原用**合成行** `[{"amount":"0.00"}]` 逼内核写合计行（语义只活在调用方、内核看不见；将来 `TOTAL_KEYS` 加列会**静默补 0**）⇒ 共用内核加**显式参数** `total_always`（默认 `False` ⇒ 其余三页零影响，已跑四页导出件确认），调用方改用之；`_mut_tail04_pages.py` 的对应锚点同步。
- 【判断项·**已修**】`test_wired_m03_action.py` 一处注释把归因写错（「流水记录 ID」**不是本轮改的** —— 实测它在 HEAD 版壳里早已如此，是那条断言先前就过期、被更靠前的失败挡着没暴露）⇒ 按事实改写。
- 【判断项·**已修**】`test_wired_m03_pay.py` 的 `".payOv" not in SHELL` 是**全文负扫**（违该文件开头"断言一律在切片里找、不到全文里撞"的纪律；此后任何注释写到 `.payOv` 都假红，报错还把人指向"实现又挂回行对象"）⇒ 收窄到拟付草稿出口那一段。

**Spec 轴（`matt-spec-reviewer`）**：缺失 0 · 越界 4 · 实现可疑 3（硬违规 0）。
- 【**已修**】两票 19 条验收框此前仍是 `[ ]`（勾没打，Status 已是 done）⇒ 逐条勾上。
- 【**已修**】票面 #3 的**第三处**口径（关键词搜索读真 `flow_no`）**此前没有判据** ⇒ 补进 `test_shell_ui_workflow.py`：在 `NO` 为空的 fixture 里，按流水号 / 单据编码都搜得到、按数据库行号搜不到；并由上列两条变异守。
- 【越界 4 条 · 均已在落账里写明理由】`applySorts` 合计行判定收窄（先有真机反例）· `test_wired_m03_action.py` 5 条旧腐化 · 三支变异脚本锚点 · README 两行。
- 【待确认 · **本轮不动**】「付款项目」列与其筛选仍经 `ntOf`→`NO` 缓存（后端其实已给 `project_key`（仓库名）/`project_display`）⇒ 该通知书不在 `NO` 里时这一列恒「—」、筛选候选项为空。⛔ 不改的理由：它不在两票验收内；且该列取值走的是**归属档案**（`dispCell`，与导出的 `project_display` 并非同一条口径）⇒ 要动先得定"以哪个为准"，属**另一张票**。
- 【未验 3 条】现场"用户手改的确是「付款金额」列"仍标未验 · 虚拟滚动分支无真机反例 · 本轮 review 只跑一次（`issue-tracker` §四：是否二次 review 由用户定）。

**复核后按影响整轮重跑**（含内核与新增变异件）：8 项审计 rc=0 · **140 项 pytest rc=0（118 s）** · **真机壳自检 rc=0（console/page 错误 0）** · **壳基线盖章 `20261011-0323`** · `BAD: []` · `mut_cover` 台账一致（115 变异件）。
