# mtrl-workbench｜剩余三项问题（R3 / R4 / R6）只读审查与实施交接书

> **文档用途：** 这是给后续开发 Agent / 本地 Codex 的**详细输入材料**，不是短提示词，也不是要求重新调查的研究计划。应优先依照本件给出的证据链、具体文件及现有结论实施最小修改；仅在版本已变化、材料存在冲突或确需补充细节时做**定点复查**。  
> **审查日期：** 2026-10-10  
> **仓库：** https://github.com/lysyscy/mtrl-workbench  
> **审查分支 / HEAD：** `master` / `58766573079b6c2e0eb986b39fde904643626fd5`  
> **操作声明：** 审查阶段只读使用已连接 GitHub 工具，未修改仓库、数据库、PR、Issue；**未执行** pytest、浏览器 E2E 或生产库查询。以下“已证实”表示**静态源码/文档证实**，不冒充动态复现或测试通过。  
> **用户实施组织：** ChatGPT 负责前期业务分析、代码探索、风险排查和方案收敛；本地 Codex 负责后续编码、验证及按仓库要求维护文档。希望尽量避免 Codex 再消耗上下文进行大范围探索。
> **⚙️ 状态（2026-10-11 更新）：** 原六项里的 **R1（焊材气体「2025-11及之前」按年份显隐）· R2（付款流水默认只看生效）· R5（发票子表草稿默认北京时间当日）已实施并提交**（`4ddcfd5`；口径回写见《说明书》§5.3.3 / §6.4.2 与 `docs/requirements/PRD/验收/验收基线.json` 三条 claim）⇒ 本件**已删去那三章**，只留下面三项。
> **剩下的三项已立票**（票为主，本件只作证据入口）：R3 → `TAIL-282` · R6 → `TAIL-283` · R4 → `TAIL-284`。

---

## 0. 快速结论：先读这一页

### 0.1 本次剩余三项与结论

| 编号 | 用户原话 / 目标 | 当前代码事实 | 最小解决方向 | 票 | 建议批次 |
|---|---|---|---|---|---|
| R3 | 匹配供应商后付款金额手改被退回 | 手改暂存 `n.payOv`；供应商写入成功触发 `reloadNotices()`；重拉 `NO=items.map(adaptNotice)`，`payOv` 消失 | 将临时拟付金额的生命周期从易被重建的行对象剥离，按通知书 ID 保留**本次页面会话**，真实付款等事件要失效/重校验 | `TAIL-282` | B |
| R4 | 项目删除没做完 | 有按钮/弹窗，三个影响项“待接通”，确认删除按钮 disabled，`delPjOk` 仅提示；后端无相应删除出口；引用外键有 `SET NULL`、`CASCADE`、`RESTRICT` 混用 | **独立实施安全删除第一阶段**：权威影响预览、只放行无业务引用的空项目；有业务引用禁止删除 | `TAIL-284` | D |
| R6 | 付款流水页信息更全，从付款通知书加一些列 | 后端 `_flow_dict` 已通过 `notice_id` 关联通知书；目前导出九数据列固定；**另发现**“操作人”显示 `created_at`，流水号显示行 ID 而非 `flow_no` | 建议增通知书日期/名称/收款单位/审批金额/分类；同步后端→适配→页面→导出，并修复现有列语义 | `TAIL-283` | C |

**建议执行顺序：B → C → D。** R4 不与界面调整混开发；R3 在切换供应商时是直接可由代码解释的故障，建议较早修；R6 涉及 Excel 导出契约，需要完整测试。

### 0.2 结论确定性标记

- **【源码确定】** GitHub 静态源码及现行文档直接支持；可按列明函数实施，无须大范围重新探索。
- **【高置信推断】** 存在完整静态调用链解释现场症状，但尚未浏览器复现、数据库复核。
- **【建议/待定】** 属于本次审查给出的最小方案，不等于用户已经逐字段作出业务裁决；尽量按默认方案做，无需为小选择启动全仓探索。
- **【未验证】** 当前运行态、真实数据库约束、现存数据行数、测试运行结果与部署情况均未验证。

### 0.3 必须保持的业务不变量

1. **付款流水**：一次实际付款一条流水；撤销保留记录、必填原因，撤销后退出生效金额统计；不得为了默认筛选隐藏而删除撤销历史。
2. **付款通知书三金额**：`amount_approved` 为审批金额（i8 源）；`stat_settle`、`stat_paid` 为旁路可手改统计；页面“付款金额”是**本次拟付默认 = 审批金额－已付金额**，`payOv` 是本次浏览器会话的临时覆盖，**不是 `stat_paid`**。
3. **已付金额**取生效流水汇总；审批金额决定“已付清/未付清”两态；统计付款金额影响欠款计算，两者不能互代。
4. **集采发票子表**：供应商、贸易公司两种 `kind` 共用发票模型与录入动作；发票日期必填、金额必须大于0、不另设上限；发票合计、结算金额、欠款金额均为现有后端派生出口。
5. **项目**：项目档案 `project.id` 是写操作身份；仓库名为跨业务数据重要归并键；小微壳/具体小微、归档联动、自动建档受现有不变量约束。删除项目不得把已发生的付款、结算、库存事实一起静默删掉或变得不可归属。
6. **页面与 Excel**：付款流水导出约定**当前筛选可见行、可见顺序**，除操作按钮外与页面数据列一一对应；不能只扩前端表头而留旧导出。

---

## 1. 已完成探索的仓库地图与证据入口

基线版本统一使用 GitHub 不可变提交进行定位。如执行时 master 已前进，**先比对目标文件是否变化**，不必从 README 开始全仓扫一遍。

### 1.1 当前架构要点

- 前端唯一壳：`backend/app/web/index.html` 及 `backend/app/web/shell/*.js`。不是 Vue/React；`V.mXX` 页面切片仍留在 `index.html`，行为接线在 `shell/actions.js`，共用表头在 `shell/proj.js`，状态/适配在 `base.js`、`core.js`，其他助手在 `pages-a.js`、`pages-b.js`。
- 付款通知书：`backend/app/mod03_notice/`（数据库模型、列表、匹配、动作）。
- 付款流水/欠款：`backend/app/mod05_flow/`（模型、service、repository、API、统计、导出）。
- 项目档案：`backend/app/mod01_projects/`。
- 集采合同、发票及付款子表：`backend/app/mod11_jc/`。
- 导出：`backend/app/report_export/`，包括 `fl_export.py`。
- 产品口径主人：`docs/requirements/材料科业务全流程说明书.md`；规格：`docs/requirements/PRD/02-功能规格/MOD-01.md`、`MOD-03.md`、`MOD-05.md`；验收：`delivery/PRD/验收/`。

### 1.2 精确文件/符号索引（后续 Agent 直接按这里打开）

| 范围 | 文件与位置（审查 HEAD 下大致行号） | 作用 |
|---|---|---|
| R3 | `web/shell/base.js:330-339` `payOver/payEff` | 拟付金额会话覆盖 |
| R3 | `web/shell/actions.js:357-397` `editss` | 手改付款金额、统计金额的不同动作 |
| R3 | `web/shell/core.js:119-146,198-216` `adaptNotice/reloadNotices` | 新建行对象导致 `payOv` 消失 |
| R3 | `web/shell/actions.js:25-42` `jcLinkAct` | 供应商操作成功后重拉通知书/集采 |
| R3 | `web/shell/actions.js:2380-2520` `supManualSave/supMatchRun/supAccept/supReject` | 供应商完整交互与调用链 |
| R4 | `web/shell/actions.js:1456-1490` `delPj/delPjOk` | 前端阻断删除，三个影响项待接通 |
| R4 | `mod01_projects/router.py` 项目路由 | 有创建/修改/归档/类型/排序，没有项目删除动作 |
| R4 | `mod01_projects/models.py`、`mod03_notice/models.py` 等 | 项目主键及各表外键策略 |
| R4 | `docs/requirements/材料科业务全流程说明书.md` §7.2、§9.4 | 删除前影响范围与硬删/软删原则 |
| R6 | `mod05_flow/service.py:108-135` `_flow_dict` | 已关联通知书与项目、可直接附加通知书字段 |
| R6 | `mod05_flow/service.py:137-189` `build_flows` | 批量取通知书/项目、返回流水行 |
| R6 | `mod03_notice/list_view.py:60-85,190+` | `bill_name=fields['BillName']` 的现成官方取值 |
| R6 | `mod03_notice/list_data.py:40-91` `columns/_row_dict` | 可选新增列在通知书列表中的展示名称/格式 |
| R6 | `web/shell/core.js:274-282` `adaptFlow()` | 流水行适配：`op` 当前错取时间，未传真 `flow_no` |
| R6 | `web/shell/proj.js:246` `FL_THEAD` | 流水表头固定10列含操作 |
| R6 | `web/index.html:878-902` `V.m05` | 流水行、固定金额合计下标4 |
| R6 | `web/shell/pages-a.js:310-320` | 关键词只匹配 `f.id` 与通知书编码；`flProjOf/flDocNo` 只用 `NO` 缓存 |
| R6 | `mod05_flow/router.py:108-153` `export_flows` | 按可见流水 ID 顺序导出，目前映射9列 |
| R6 | `report_export/fl_export.py:40-89` `COLUMNS` | Excel 列和金额列唯一配置 |

便于在 GitHub 网页中查阅：将上述路径拼到  
`https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/<路径>#L<行号>`。

---

## 2. R3｜匹配供应商后“付款金额”临时手改被回退（票 `TAIL-282`）

### 2.1 根因调用链【源码确定；现场症状为高置信推断】

```text
用户在 m03 修改某行“付款金额”
  -> ACT.editss（actions.js）识别 k === 'pay'
  -> n.payOv = v（只存在当前 NO 行 JS 对象，不落库）
  -> payEff(n) 优先读取 n.payOv，否则按 approve-paidOf 派生
  -> 用户匹配/保存/采用集采实际供应商
  -> jcLinkAct(...) 或 supManualSave(...) 成功
  -> await reloadNotices(); await reloadM11(); render();
  -> reloadNotices: NO = items.map(adaptNotice)
  -> adaptNotice 重新创建对象，没有 payOv 字段
  -> payEff(n) 回落到 approve-paidOf(n.id)
  -> 页面看起来“手工金额被退回”
```

`web/shell/base.js`：

```js
const payOver=n=>n.payOv!=null;
const payEff=n=>payOver(n)?N2(n.payOv):N2(n.approve-paidOf(n.id));
```

`actions.js::editss`：

```js
if(k==='pay'){
  n.payOv=v;
  render();
  // toast 明示：本次会话覆盖，刷新页面后回默认值，不改 i8 原值与统计付款金额
  return;
}
```

`core.js::reloadNotices`：

```js
const nt = await API.notices();
const items = nt.items || [];
NO = items.map(adaptNotice);
```

`actions.js::jcLinkAct`：成功后统一 `await reloadNotices(); await reloadM11(); render()`；单家供应商预填 `supMatchRun`、“采用” `supAccept`、“放弃” `supReject`、手动保存 `supManualSave` 都存在触发重拉的路径。该重载设计为保持后端供应商关联事实一致，本身**不能简单移除**。

### 2.2 关键业务区分【源码确定】

| 名称 | 源字段 / 逻辑 | 用户行为 | 持久化？ | 对欠款的作用 |
|---|---|---|---|---|
| 审批金额 | `amount_approved`（i8 源） | 只读 | 是（i8抓取） | 是业务基准 |
| 本次拟付“付款金额” | `payEff(n)`，可由 `payOv` 覆盖 | 为下一次付款临时调整 | **不落库** | 尚未实际付款，不改变欠款 |
| 已付金额 | 生效 `payment_flow` 求和 | 已发生的支付事实 | 派生 | 影响付款状态 |
| 统计付款金额 | `stat_paid`（旁路） | 可手改、留痕、再抓取受保护 | **落库** | 直接用于统计/欠款 |

**严禁“修复”成：** `payOv` 写入 `stat_paid`、新增数据库 `pay_amount_override`、禁止刷新供应商信息、让付款后的旧覆盖永久有效。四种方案都会改变原有业务口径或产生新的失真风险。

### 2.3 推荐实现及状态失效策略【建议方案】

**主方案：** 将临时拟付覆盖按 `notice_id` 独立保存在页面会话内的 JS Map/对象中；界面仍通过单一 `payEff` 取当前有效金额，并由 `editss` 更新。`reloadNotices` 不应因为重建 `NO` 直接抹掉覆盖。实现时注意：该覆盖不是浏览器持久化，刷新整个网页后仍应自动消失；若保留 `n.payOv` 兼容现有读法，恢复点必须集中而不是多处重复保存。

**失效/校验边界（尤其重要）：**

- **保留临时覆盖：** 单纯修改、确认或重新匹配集采供应商；无关通知书行变化；一般列表重新加载而审批/已付事实未改变。
- **不得无条件保留：** 该通知书实际付款登记成功、撤销付款成功、审批金额改变、已付金额改变、发生超付或原通知书不再存在等。可按 `notice_id` 失效，并根据最新 `approve-paidOf` 重新派生；具体失效策略应在一个共用出口，不要散落在 `jcLinkAct`、`reloadM05`、`editss` 等处。
- **手改为0的边界：** 0是有效覆盖值，使用 `!= null` 识别“有覆盖”，不可用真值判断而失效。
- **失败和并发：** 供应商保存失败不能清本来有效的金额覆盖；异步刷新先后顺序不要让旧回执覆盖新草稿；不要因刷新 `NO` 的引用替换导致外部对象被保留或过期。
- **金额合法性：** 继续使用现有 `numOf/badMoney` 与付款提交的服务端整批校验。可见“修改成功”不等于允许超额度或不安全付款。
- **新开浏览器页面/整页刷新：** 按既有设计，临时覆盖应消失，不写 sessionStorage/localStorage/数据库。

### 2.4 最小复现与验收矩阵

1. 准备某通知书：审批1000、已付200、派生拟付800。手工改为300。匹配供应商成功后仍显示300；再次 `reloadNotices()` 仍为300。
2. 同时手改 A=300、B=120，匹配 A 的供应商不能把 B 清掉；不同 `notice_id` 的覆盖绝不可串到一起。
3. 手工设0，重拉仍显示0而不是800。
4. 供应商无匹配/多候选/单候选“待确认”/手动录入、采用和放弃路径都覆盖。
5. 匹配失败/HTTP `ok:false` 后金额不回退；保存成功且 `NO` 后端读回才确认关联已变。
6. 支付成功或撤销后，旧拟付额不得持续覆盖新派生值；超过审批/未付的草稿不能因保留状态绕开支付校验。
7. 整页刷新后拟付额恢复派生默认；统计付款金额、已付金额、欠款数字均未被手改拟付额修改。

**现有回归入口：** `test_acc_pay_stat.py`、`test_acc_sup_match.py`、`test_wired_m03_list.py`、`test_wired_m03_pay.py`、`test_acc_jc_pay_link.py`；建议新增一个聚焦 `reloadNotices` + 供应商读回 + `payOv` 恢复/失效的前端测试。

---

## 3. R4｜项目删除未完成：功能缺口与数据破坏风险（票 `TAIL-284`）

### 3.1 当前不是“接口报错”，是主动未开放【源码确定】

`web/shell/actions.js::delPj` 已实现确认框，但除通知书以外，弹窗三项仍是常量“待接通”：

```text
关联付款流水：待接通（这一项还没做）
关联库存单据行：待接通（这一项还没做）
关联集采合同：待接通（这一项还没做）
```

随后提示“关联影响尚未全部读到，当前不能删除”，确认按钮自带 `disabled`；`delPjOk` 只 toast “删除这一项还没打通”。在 `mod01_projects/router.py` 未发现对应项目删除接口，`mod01_projects/repository.py` 也没有成熟的“项目全引用影响预览＋删除”出口。**前端数量目前不能作为安全删除的依据。**

### 3.2 删除政策【源码确定】

`docs/requirements/材料科业务全流程说明书.md`：

- §7.2：删除前必须列出**关联数据、统计影响**；确认后再执行删除并刷新。
- §9.4：按可复原性区分删除方式；可复原或用户自行录入的记录可硬删；无法复原且历史需要识别的主体如账号软删；本条是**全局原则**，不等于任意项目均可无条件硬删。
- 项目自身还有自动建档、仓库名识别、小微壳层级等业务条件；“删项目时业务记录仍保留”不能只做界面承诺，必须在模型及事务级证明。

### 3.3 已排查的外键影响（静态模型定义）

| 表/关联 | 模型所在 | 外键策略 | 对项目硬删的实际风险 |
|---|---|---|---|
| `payment_notice.ownership_id` | `mod03_notice/models.py` | `SET NULL` | 通知书与项目归属脱钩；影响按项目监控与欠款定位 |
| `payment_flow.project_id` | `mod05_flow/models.py` | `SET NULL` | 流水保留却失去项目身份，导出/统计出现未判定 |
| `opening_balance.project_id` | `mod05_flow/models.py` | `SET NULL` | 期初仍在但项目丢失，账起点无法按原项目查 |
| `plan_row.project_id` | `mod04_plan/models.py` | `SET NULL` | 付款计划行归属丢失 |
| `inv_detail.project_id` | `mod08_inv/models.py` | `SET NULL` | 库存原单仍有仓库名，但档案 FK 不再有效 |
| 过程资料/机械数据部分项目外键 | `mod06_proc/models.py` | `SET NULL`（部分表） | 过程资料可能丢失档案映射 |
| 月度会大表部分手录外键 | `mod07_setl/models.py` | `SET NULL` | 手录记录与档案脱钩 |
| `jc_contract.project_id` | `mod11_jc/models.py:125-130` | **`RESTRICT`** | 数据库设计**禁止**有集采合同时删除对应项目 |
| `jc_import_batch.project_id` | `mod11_jc/models.py` | `SET NULL` | 导入批次项目归属信息失去绑定 |
| `special fee` 项目外键 | `mod09_fee/models.py:31-32` | **`CASCADE`** | 可能级联删除用户录入的特殊费用业务数据 |
| `ledger_remark.project_id` | `mod05_flow/models.py:101-109` | **`CASCADE`** | 可能直接带走逐月台账备注 |
| `project_field_log.project_id` | `mod01_projects/models.py` | **`CASCADE`** | 项目全名/状态历史留痕可能被删 |
| `project.parent_shell_id` | `mod01_projects/models.py` | `SET NULL` | 小微壳被删后，具体小微失去所属壳，破坏层级不变量 |

**注意：** 以上是 ORM 声明，**未查实际数据库 schema**、Alembic 当前迁移状态和真实记录数。正式开发阶段只能在安全测试库核验约束，不可未经授权连生产库执行删除试验。

### 3.4 还有不能靠 FK 数清的关系【源码确定 + 分析】

- `mod07_setl/models.py` 中 `setl_detail`、`weldgas_balance`、大表项目/手录行使用 `warehouse_name`；项目删除未必级联删除这些记录，但一旦项目档案仓库名不再存在，自动汇总筛选、项目状态筛选或展示就可能遗漏。
- `mod06_proc/models.py` 存在若干仓库名键及项目外键混合使用；不能只统计 `project_id`，还应确认按仓库名归并的数据。
- `mod03_notice/models.py` 还含 `project_name` 文本与 `ownership_id`；只按名称匹配不足以证明行属于同一具体小微。影响预览应**以主键为核心，仓库名为辅助映射**，遵守写操作按 ID 定位的规则。
- 同步常用项目/仓库、占位行扶正可能重建已删除档案。删除空档案不一定表示“以后不再抓取这个项目”。如用户最终想要永久忽略，应是独立的规则需求，不要暗中纳入本次删除。

### 3.5 推荐分阶段范围【最小化建议】

**D1：本次只补“安全删除无业务依赖的项目”。**

1. 新增后端**只读影响预览**（入口由 MOD-01 暴露；跨模块读取应遵守现有 layering/包间 service 出口）。按 `project_id` 查询全量相关 FK，补充仓库名关联统计，能列出明细摘要而不仅是一个总数。对小微壳列出全部子项目，明确其状态。
2. 预览返回结构至少有：项目身份/类型/状态、受影响表及真实数量、保留/丢失的业务关系、是否允许删除、拒绝原因、提示用户的下一步（例如“此项目有付款流水，请归档而非删除”）。哪一项查询失败都应**拒绝删除而不是当0**。
3. 仅所有关键关联均为零、无层级牵涉且删除不会使未关联仓库业务失去主人时，开放真正的确认删除。
4. 删除动作必须在**同一数据库事务内重新计算影响并校验**，不能只信前端几秒前的预览结果；避免预览时为空、提交前被别的操作新建关联的竞态。
5. 只删被选定的那一条项目档案，严禁由“级联方便”扩大删除范围；若连修改留痕都不允许丢，则此类非业务引用如何处理需写明策略。推荐第一阶段保守禁止或清晰展示，不暗中删除历史记录。
6. 仅当后端返回明确可删除且二次确认完成，前端才启用“确认删除”；删除成功后重拉项目档案与引用它的候选，不产生本地“假成功”。
7. 已有关联付款/集采/库存/期初/特殊费用/备注等业务数据的项目一律阻止。**不做**自动转移、批量解绑、手工修约束、强制 CASCADE/SET NULL 以绕过保护。
8. 含具体小微的壳项目默认阻止删除；先维护既有层级与归档不变式，不在此次创建复杂的“整壳连子项目删除”能力。

**D2：不在当前交付范围。** 需要删除有业务引用项目时，必须先单独定稿“转归属/删除业务数据/归档替代”的业务裁决，再设计数据迁移及审计。绝不能把 D1 当 D2 实现。

### 3.6 强制反向测试

- 空项目：预览明细全部为0（经真实数据出口独立核验），可确认后只删该项目；其他项目行数、各业务表计数不变。
- 存在1条 `jc_contract`：必须拒绝，不得先删再等待数据库 `RESTRICT` 报错；原合同保持。
- 存在1条特殊费用或1条台账备注：必须拒绝，确保**零级联丢失**。
- 存在通知书、流水、付款计划、期初、库存、过程资料任一引用：必须拒绝；不产生 `project_id=NULL` 的新孤儿。
- 已有仓库名数据但无 FK：预览必须认到或明确给“不确定＝禁止”；不能以 FK 0宣称无关联。
- 小微壳带具体小微：不得删壳而制造孤儿；已归档项目也不因此自动可删。
- 预览后新建一条业务引用：提交时重检，应拒绝并保持所有数据。
- 影响预览某个数据源查询失败：禁止删除，保留明确错误；不得将未知折算0。
- 不触发 i8 同步或源数据重抓，不手工修改现有项目的分类/归属，不产生副作用。

**回归入口：** `test_acc_prj_list.py`、`test_acc_prj_arch.py`、`test_acc_prj_own.py`、`test_acc_prj_auto.py`、`test_wired_m01.py`、`test_acc_x_del.py`、`test_layering.py`、`test_acc_flow_debt.py`、`test_acc_jc_domain.py`。`test_acc_x_del.py` 覆盖的是全站删除分档/既有模块，不应误认为“项目删除已完成”。

---

## 4. R6｜付款流水页面补通知书信息，兼修两处已发现字段错位（票 `TAIL-283`）

### 4.1 当前实现与后端关联【源码确定】

`mod05_flow/models.py::PaymentFlow`：

```python
flow_no       # 独立业务流水号，例如 FL+时间戳+后缀
notice_id     # FK payment_notice.id，nullable，ondelete=SET NULL
project_id    # FK project.id，nullable，ondelete=SET NULL
amount, pay_date, pay_method, remark, created_by, created_at, status, revoke_reason
```

`mod05_flow/service.py::build_flows`：

```python
notices = {int(n.id): n for n in repo.notice_rows(s)}
projects = project_index(s)
raw = [_flow_dict(f, notices, projects) for f in repo.list_flows(s)]
```

`_flow_dict` 已有 `n = notices.get(f.notice_id)`，返回 `doc_no`、项目展示名、项目键、付款金额、方式、操作人、状态等，因此**无需新表、无需前端去请求整张付款通知书**，仅在这一个后端字典扩充字段，复用已载入的 `PaymentNotice`。

**通知书单据名准确来源已另行核实：** `mod03_notice/list_view.py::build_rows` 使用 `str((n.fields or {}).get('BillName') or '')` 构建 `bill_name`。不要猜 `PaymentNotice.bill_name` 是模型独立字段——现有 ORM 模型里没有该列。

### 4.2 本次建议新增的5列【审查建议；用户只说“加一些列”，尚未逐字段裁定】

| 页面新列 | 权威源 | 输出及注意事项 |
|---|---|---|
| **通知书日期/单据日期** | `PaymentNotice.doc_date` | 单据归属月，**不是**流水 `pay_date`；空源留空 |
| **通知书名称/单据名称** | `(n.fields or {}).get('BillName')` | 复用 `mod03_notice/list_view.py` 的现行口径，缺失为'' |
| **收款单位** | `PaymentNotice.payee` | 原样展示，不能用 JC 供应商替代 |
| **审批金额** | `PaymentNotice.amount_approved` | 数字金额列，**与本笔实付金额分开**，空关联不得伪装0 |
| **分类** | `PaymentNotice.category` | 映射为既有中文辅材/机械/集采，复用已有类别名称出口，不另自造枚举 |

建议位置：流水号、单据编码之后插“通知书日期/名称/分类/收款单位/审批金额”，再依现有顺序展示付款项目、实际付款日期、实付金额、付款方式、备注、操作人、状态、操作。精确顺序以“页面与导出一致、金额相邻可核对、宽表不过度杂乱”为准，不需要为排版新建用户配置系统。

### 4.3 顺便查明的两处已存在缺陷【源码确定】

**缺陷 1：“操作人”列实际上显示创建时间。**

`core.js::adaptFlow()` 当前：

```js
op: x.created_at || ''
```

`index.html::V.m05` 的第8个数据列却叫“操作人”，表格单元格打印 `f.op`。但后端 `_flow_dict` 同时返回 `created_by`（操作人）与 `created_at`（时间），而 `report_export/fl_export.py` 的“操作人”列已导出 `created_by`。因此页面与 Excel 语义不一致。**应令页面操作人读 `created_by`，旧记录若缺操作人应如实留空；创建时间若有展示需求另取准确表头。**

**缺陷 2：“流水号”列实际显示的是数据库流水行 `id`，而不是业务 `flow_no`。**

`mod05_flow/repository.py::next_flow_no` 会生成 `FL<时间戳><短后缀>`；`_flow_dict` 会返回 `flow_no`。但 `adaptFlow()` 只映射 `id:String(x.id)`，`V.m05` 第1列是 `${f.id}`，`fl_export.py` “流水号”也导出 `id`。同时前端关键词 `flVisible` 匹配 `f.id` + `flDocNo(f)`，与后端 `filter_flows()` 按真正 `flow_no` 的规则不同。

建议改正：

- 内部按钮/撤销 API 继续使用 `f.id`（数据库主键，**不能**直接换成文本 `flow_no` 传撤销接口）；
- 前端适配增加 `flowNo:x.flow_no||''`；“流水号”显示、对应 Excel 列和“流水号/单据编码”关键词使用**业务流水号**，必要时保留兼容按数据库行 ID 搜索以减少用户习惯变化；
- 如果有旧导入流水 `flow_no` 为空，**显示空或明确回退约定须经测试确认**，不能编造业务编号；
- 最终要求**界面、搜索、Excel 同一列真的是同一个 `flow_no`**。这个修补很贴近 R6，但它是审查额外发现，应在交付记录中单独标注。

### 4.4 必改的完整数据链

1. `mod05_flow/service.py::_flow_dict` 增加所需通知书字段：`notice_doc_date`、`notice_bill_name`、`notice_payee`、`notice_approved`、`notice_category_label`（字段名可按模块现有风格确定）；保留 `flow_no/created_by`。**一条流水一条、批量取数**，不改成每行新查数据库的 N+1。
2. `web/shell/core.js::adaptFlow` 增加新列对应字段，映射真 `flow_no` 和 `created_by`，保留 `id`/`nid` 供操作。**注意类型**：金额内部继续按现有金额转换处理，但缺关联的“未知审批额”应保持 `null/''`，不得调用 `numOr0` 误显示0。
3. `web/shell/proj.js::FL_THEAD` 增列；`web/index.html::V.m05` 同步行 `<td>`、表格属性、表头与合计行 `sumRowOf`：当前付款金额列是**固定下标4**，前插多列后必须重新指向真正实付金额列。`sumRowOf` 的 `leadSpan` 及 `EMPTYROW(thCount(FL_THEAD))` 同步检查。
4. `web/shell/pages-a.js` 的 `flVisible/flDocNo/flProjOf` 应优先使用**付款流水自己接口已返回的项目/单据字段**，不要仅靠当前页面 `NO` 缓存。当前 `flProjOf(f)` 和 `flDocNo(f)` 使用 `ntOf(f)`，当关联通知书未在缓存或丢失时，真实历史流水可能失去项目筛选/检索能力；这与 R6 的目标相关。**限定为必要的展示/查询改造**，不能改项目归属统计口径。
5. `mod05_flow/router.py::export_flows` 将新增字段映射到导出数据，且“流水号”传 `flow_no`、“操作人”传 `created_by`。接口仍只接受可见流水的 **ID 列表**，用来确定导出哪些行及顺序；**不要因第一列改显示业务流水号而把 POST 传参改成 flow_no**。
6. `report_export/fl_export.py::COLUMNS` 统一列头和字段，`MONEY_KEYS` 增加“审批金额”对应字段，**只实际合计本笔实付金额**，而非将每笔流水重复出现的审批金额纵向相加当成有意义的合计。现有合计约定可保持只合 `amount`。
7. 现有排序规则靠表头文本/数值类型识别；新增金额列的排序应为数值排序，避免字典序 `100 < 20` 式错误。
8. 宽表可能横滚；保持付款项目/单据标识易识别，无须新增列配置面板，现行 PRD 明确不做列设置面板或拖动列宽。

### 4.5 历史/异常数据与边界

- `notice_id IS NULL`、原通知书不存在：付款流水仍必须可查，不能被内连接过滤；新通知书列留空/—；实际金额、日期、状态、撤销原因保持原事实。
- 某条通知书多次付款：每条流水显示自己的付款金额和日期；审批金额可在两条流水重复出现用于**对照**，但不能把重复的审批金额作为账务合计。
- 已撤销流水：选“全部”/“已撤销”仍可查原因，不进入“合计（生效）”。
- 历史导入流水付款方式允许为空，不能因此兜底“现汇”或删行（`repository._method_of` 已区分 manual/imported）。
- 项目可能归档或已无档案：尽可能保留后端流出原有项目展示/键，勿因缺 `NO` 本地缓存变成孤立不可搜索。
- 原本后台 `FlowExportIn.ids` 以 `id` 定位并保持行序，**本约束不能改**；操作按钮撤销同样按数据库行 ID。

### 4.6 反例矩阵

| 场景 | 期望 |
|---|---|
| 同通知书两笔生效流水 | 两行分别呈现实付金额/付款日，通知书基本信息一致；合计只加两笔实付 |
| 已撤销第三笔 | 手动切“全部”能看到，原因可见，实付合计不计它 |
| 通知书已失联 | 流水不丢，原真实字段保留，新关联字段空，不伪0 |
| 业务 `flow_no` 与数值 `id` 不同 | 页面第一列、Excel“流水号”和搜索均使用同一真 `flow_no`；按钮仍按 `id` 撤销 |
| `created_by='甲'`、`created_at='2026-...'` | 页面与 Excel “操作人”均为“甲”，创建时间不能冒充姓名 |
| `amount_approved=1000`、两笔 `amount=300+200` | 审批金额可以重复显示用于查看；最终实际付款合计=500，**不是审批金额重复求和2000** |
| 历史导入付款方式为空 | 页面显示空/—，Excel 留空；不编造成现汇 |
| 页面按项目、月份、方式、状态、关键词筛选再导出 | Excel 行顺序/数据与当前可见行一致，无多余隐藏记录，金额为数字而非文本 |

**回归入口：** `test_acc_flow_list.py`、`test_acc_flow_pst.py`、`test_wired_m05.py`、`test_page_m05.py`、`test_tail04_pages.py`、`test_naive_export_parity.py`（此项需评估是否覆盖流水）、`test_shell_render.py`；建议新增专门流水 Excel 逐格测试。**`test_tail04_export.py` 主要是收发结存/库存导出测试，并不专门证明付款流水 Excel 正确**，不要只跑它就宣布 R6 完成。

---

## 5. 跨需求依赖与建议分批

### 5.1 同批/不应同批

| 交叉 | 共同点与风险 | 判断 |
|---|---|---|
| R3 + R6 | 都读取付款通知书但 R3 是 m03 会话状态，R6 是 m05 行映射 | 无强制先后，注意修复后重拉路径 |
| R4 + R6 | 项目删除可能造成历史流水项目归属缺失；R6 明确要保留无通知书/项目关联的流水 | R4 **必须独立**，不能通过改 R6 的 JOIN 遮蔽历史数据 |
| R4 + 仓库名文本键 | 焊材历史（`weldgas_balance`）、过程资料、大表手录按**仓库名**聚合；删除项目档案可能造成“有业务记录但页面筛选不见” | R4 预览需查询仓库名关联，不能仅按 FK 数0 |

### 5.2 优先级与验收方式

- **A（已完成 · 2026-10-10）：** 焊材气体历史列按年份显隐 · 付款流水默认只看生效 · 发票子表草稿默认北京时间当日。提交 `4ddcfd5`；口径回写 =《说明书》§5.3.3 / §6.4.2 ＋ `docs/requirements/PRD/验收/验收基线.json` 三条 claim。本件不再复述那三章的实现细节。
- **B（第二批）：** R3 拟付临时覆盖在匹配供应商刷新后保留、状态失效边界。强调真机交互复现，不新建数据库字段。
- **C（第三批）：** R6 五列信息+“操作人/流水号”已证实列义修正+Excel 一致性。变更路径较多但业务口径保持。
- **D（单独安排）：** R4 项目安全删除第一阶段，必须真实事务级反向测试，不能仅靠静态 HTML 检查。

---

## 6. 执行前的最小检查纪律（减少无效探索）

1. **先读本文件**，在开始前只检查当前 HEAD 与上述审查 HEAD 的差异。例如 `git rev-parse HEAD`、`git diff --name-only <审查SHA>..HEAD -- <已点名文件>`；若没变化，直接按下面任务范围动手。
2. 仓库已有 `AGENTS.md`、文档同步纪律、壳结构保护、验收基线管理规范。实施 Agent 仍须遵守这些规则，但不必把整个 `.codebuddy/` 历史全量加载上下文。
3. 先读任务**相关函数及已列测试**，不要无目的扫描全部 `backend` 下的代码文件。只有遇到实际调用依赖或测试失败，才作精确扩展。
4. 代码改动要形成**每个问题独立验收点**，尽量少加新的机制与迁移。涉及现有派生字段时，始终复用已有业务出口，不在前端/导出另算第二份。
5. 修改后按影响面运行已列回归与新反向测试；浏览器真机检查列数、滚动、默认筛选、供应商刷新和 Excel 实际内容。**报告实际运行命令与结果**，不能引用本次审查中的“历史任务已通过”冒充本次通过。
6. 付款、集采、项目删除涉及真实数据，**所有写入/删除测试必须使用隔离测试库或可证明的回滚会话**；生产库不做探索性写入、破坏性 E2E。
7. 输出：改了哪些文件、每项对照用户要求的验收证据、仍有什么不确定、与审查时发现的差异；遇到必须用户定案的**新增业务选择**再单独列出，而不是擅自扩大任务。

---

## 7. 可直接复制给 Codex 的三批详细执行指令

> 以下任务已包含本次调查发现，Codex 的目标是**最小实现并验证**。开发前仍应读取仓库 `AGENTS.md` 及必要工程规则；不需要对三项重新做全面只读审查。⚠️ 三张票都要走仓库自己的票协议（`docs/agents/issue-tracker.md`）。

### 批次 B：拟付金额会话态丢失——R3（`TAIL-282`）

```text
项目：lysyscy/mtrl-workbench。先读交接书第2章（R3）的完整已证实调用链，不要重新搜索整个付款系统。当前根因是 actions.js::editss(k='pay')把用户临时拟付金额存入 NO 行对象的 payOv，供应商匹配/手动保存/采用/放弃通过 jcLinkAct 或 supManualSave 调用 core.js::reloadNotices()，它执行 NO=items.map(adaptNotice)，新对象没有 payOv，base.js::payEff 回退到“审批金额－已付金额”。

请修复：临时覆盖按 notice_id 独立于可重建的 NO 行保存；供应商关联导致的普通 reloadNotices 不清除有效草稿；页面整页刷新仍应清零会话覆盖，不写数据库/Storage，不使用统计付款金额 stat_paid 作为拟付草稿容器，不停掉供应商后的真实后端重拉。真实付款成功、撤销成功、审批金额或已付金额变化时，对相应草稿失效或重校验，以免旧值被拿来继续支付。0 是合法覆盖，注意并发请求旧回执覆盖和不同通知书隔离。

必须覆盖单供应商命中并待确认、多候选、手动指定、采用、放弃、保存失败、2笔草稿并存、0金额、付款/撤销后的失效、刷新页面恢复派生值；统计付款金额、欠款与 i8 源数据保持原口径。只进行必要的相关 API/壳修改和回归测试。输出实际复现前/修复后事实，勿将审查推断宣称为已经执行的测试结果。
```

### 批次 C：付款流水增列、编号与操作人修正——R6（`TAIL-283`）

```text
项目：lysyscy/mtrl-workbench。先读交接书第4章（R6），重点文件：mod05_flow/service.py::_flow_dict/build_flows、mod03_notice/list_view.py 的 BillName 取值、web/shell/core.js::adaptFlow、pages-a.js::flVisible/flDocNo/flProjOf、proj.js::FL_THEAD、web/index.html::V.m05、mod05_flow/router.py::export_flows、report_export/fl_export.py::COLUMNS。

请把付款流水页新增以下五类来自关联付款通知书的信息：单据日期(doc_date)、单据名称(fields['BillName'])、收款单位(payee)、审批金额(amount_approved)、业务分类(category中文)，以现有 notice_id 和 build_flows 已预读的 notices 字典拼入一条流水行；不得逐行查询数据库，也不能依赖前端 NO 是否载入来决定信息是否可见。无法关联通知书的历史流水继续显示，新增未知字段空/—，审批金额未知不能伪造0。审批金额仅供对照，不应重复求和成为新的金额合计。

顺便修复两个已确认的现有错位：①“操作人”页面适配目前拿 created_at，实际应来自后端 created_by，旧值空就留空；②“流水号”表头当前呈现/导出的是数据库 id，但后端有真实 flow_no。第一列应改呈 flow_no，搜索应匹配真正流水号；保留数据库 id 作为撤销按钮与 export_flows(ids) 的唯一定位键，禁止将文本 flow_no 当接口 id。必要时对旧 flow_no 为空作稳健显示。

同步修改前端10列+5新列的表头/行、合计金额列索引（原 sumRowOf 下标4已不成立）、leadSpan、空态 colspan、排序，Excel导出映射与 numeric money_keys；导出依然仅收当前可见的数据库 id 顺序并与页面列一一对应，状态格仍含撤销原因。历史导入的空付款方式不得兜底改成现汇。保持统计、欠款和多笔付款/撤销业务行为不变。

执行静态接线、真实渲染、数值排序、两笔实付独立/审批金额重复展示但不合计、已撤销、缺关联、创建人显示、真实流水号、Excel逐格和导出筛选一致性测试；本文件第4.6节的反例必须覆盖。报告实际测试数据与通过范围，不顺手修改项目删除或历史导入逻辑。
```

### 批次 D：项目安全删除第一阶段——R4（`TAIL-284`）

```text
项目：lysyscy/mtrl-workbench。严格以交接书第3章（R4）的静态引用矩阵和已确认未实现现状为起点，遵守 docs/requirements/材料科业务全流程说明书.md §7.2/§9.4 与项目层级规则。不要把“按钮启用”当项目删除完成。

当前 web/shell/actions.js::delPj 仅显示弹窗，三项影响待接通，按钮 disabled，delPjOk 只 toast，后端没有项目删除路由。已有引用包括：payment_notice/payment_flow/opening_balance/plan_row/inv_detail/部分过程/大表为SET NULL；jc_contract为RESTRICT；special fee、ledger_remark、project_field_log为CASCADE；project.parent_shell_id为SET NULL；焊材历史、收发结存和过程资料还有 warehouse_name 文本键。直接删除存在业务脱钩/级联丢数/壳失去小微风险。

本次只实现D1：由 MOD-01 提供后端只读影响预览，按 project.id + 必要仓库名关系统计并列出真实影响（付款通知书、所有流水含撤销、付款计划、期初、库存、集采合同、特殊费用、台账备注、过程/收发/焊材历史及小微子项目等）。只在确认没有关键业务关联、不破坏小微壳和历史数据不变量时准许删除空/误建项目。任何影响查询不确定或失败=拒绝删除并说明原因。提交时在同一事务重新核验，禁止绕过RESTRICT、禁止CASCADE业务删数、禁止为通过验证而把项目FK批量置NULL、禁止“前端假计数”和静默成功。按真正可删除状态动态启用确认按钮，成功后刷新相关候选。

对有付款、集采、库存、期初、特殊费用、台账备注、小微层级或仓库名相关历史数据的项目，D1一律拒绝并给归档等安全替代；不在本次做关联业务记录的迁移/强制解绑，也不改变自动建档策略。

先补测试库可回滚的影响预览/事务删除正反案例，尤其 jc_contract RESTRICT、CASCADE风险、仓库名非FK关联、预览与提交之间出现新引用的竞态。再补前端弹窗联动的真实浏览器验证。运行现有MOD-01、ACC-X-DEL、债务、集采、layering相关测试。报告仅第一阶段完成边界，不宣传“任意项目都能删”。
```

---

## 8. 推荐验证清单与运行命令（由 Codex 执行，审查阶段未运行）

以下只列**相关范围**。如仓库 `pytest.ini`、自定义插件、Windows 虚拟环境等对运行有额外要求，以当前仓库规则为准；默认不要运行全仓巨大测试而浪费时间。审查者**未执行以下命令**：

```bash
# 从仓库根目录，运行前核实当前工作树是否已包含其他人的未提交修改。
# 使用已配置的隔离测试环境，避免写生产数据。

python -m pytest backend/tests/test_acc_sup_match.py backend/tests/test_wired_m03_pay.py backend/tests/test_acc_jc_pay_link.py -q   # R3
python -m pytest backend/tests/test_acc_flow_list.py backend/tests/test_page_m05.py backend/tests/test_wired_m05.py -q              # R6
python -m pytest backend/tests/test_acc_prj_arch.py backend/tests/test_acc_prj_own.py backend/tests/test_acc_prj_auto.py backend/tests/test_acc_x_del.py backend/tests/test_layering.py -q   # R4
```

⚠️ 本仓实际命令前缀是 `backend/.venv/Scripts/python.exe -X utf8 -m pytest tests/<件> -q`（工作目录 `backend/`），以仓库现行规则为准。

特别提醒：仓库里有“测试库内事务回滚”用例，也存在可能依赖服务/登录态的 E2E，**不应假设所有 pytest 都绝对只读**；后续实现 Agent 必须遵守仓库实际测试环境的安全规则。

**交付时最低证据：**

- R3：供应商匹配不冲掉临时金额，付款事实发生后旧草稿不再错误保留，整页刷新仍清空。
- R6：页面/导出五新列和两项列义一致；业务流水号 vs id 区分；金额只合实付，历史孤儿流水保留。
- R4：安全空项目可删；任何关联业务事实均拒删；无级联业务丢失、无孤儿、不破坏小微壳。

---

## 9. 审查范围、未证实项与禁止误读

1. **代码静态确认，不等于动态回归已成功。** 本轮通过 GitHub 读取实际仓库源码、说明书与已有测试文本；没有运行浏览器或数据库。不能把历史票写的“28 passed”等当成当前执行结果。
2. **R3 根因虽可由完整调用链解释，但未对用户实际操作画面做复现。** 若后续事实表明用户手工改的是“统计付款金额”而非“付款金额”，需定点核对具体列；本件所述 `payOv` 直接对应页面“付款金额”栏的已发现问题。
3. **R4 的数据库约束表是 SQLAlchemy 模型声明。** 实际数据库可能迁移不同步；后续应在隔离测试环境核对约束，不可直接操作生产数据尝试删除。
4. **R6 五列是审查方建议，不是用户逐列确认的最终名单。** 用户提出“看见的信息要全一些”；这五列优先体现通知书日期、事项、收款方、审批额、分类，最符合“核对付款流水”场景。无需自动加入所有通知书列。
5. **R6 两个已有列义异常是额外静态发现。** 若想极限缩小范围可以分成额外小票，但将其与付款流水增强一起解决更能避免页面与 Excel 对不上的已知问题。
6. **R4 暂不实现有业务引用项目删除。** 这是数据保护上的审查建议；未来如果用户明确要求删除含历史业务记录的项目，需要另行裁决，不可把跨模块数据迁移当成“补删除按钮”的自然延伸。
7. **保留历史记录的两种身份。** 真正业务流水号 `flow_no` 与数据库行主键 `id` 不同，二者是显示身份与操作定位身份，不能互换。
8. **本件已完成部分不再复述。** R1/R2/R5 的实现与口径已落进提交 `4ddcfd5` 与《说明书》/`验收基线.json`；要查那三项，去看代码、说明书与票，不要回到本件找它们的行为描述（本件已删）。

---

## 附录 A｜主要只读来源链接

- 仓库入口：<https://github.com/lysyscy/mtrl-workbench>
- 本次审查版本：<https://github.com/lysyscy/mtrl-workbench/commit/58766573079b6c2e0eb986b39fde904643626fd5>
- 项目说明书：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/docs/requirements/材料科业务全流程说明书.md>
- MOD-01 项目档案：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/docs/requirements/PRD/02-功能规格/MOD-01.md>
- MOD-03 付款通知书：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/docs/requirements/PRD/02-功能规格/MOD-03.md>
- MOD-05 付款流水：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/docs/requirements/PRD/02-功能规格/MOD-05.md>
- `base.js`：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/backend/app/web/shell/base.js>
- `proj.js`：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/backend/app/web/shell/proj.js>
- `core.js`：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/backend/app/web/shell/core.js>
- `actions.js`：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/backend/app/web/shell/actions.js>
- `index.html`：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/backend/app/web/index.html>
- `mod05_flow/service.py`：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/backend/app/mod05_flow/service.py>
- `mod05_flow/router.py`：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/backend/app/mod05_flow/router.py>
- `mod03_notice/list_view.py`：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/backend/app/mod03_notice/list_view.py>
- `mod11_jc/models.py`：<https://github.com/lysyscy/mtrl-workbench/blob/58766573079b6c2e0eb986b39fde904643626fd5/backend/app/mod11_jc/models.py>
- 三张票（本地）：`.scratch/tails/issues/TAIL-282-匹配供应商后拟付金额被回退.md`、`TAIL-283-付款流水补通知书信息与列义修正.md`、`TAIL-284-项目安全删除第一阶段.md`

**文档结束。** 后续 Codex 应以本件为预先完成的调查成果，集中额度在必要差异核查、实现、正反测试与真实交付证据上。
