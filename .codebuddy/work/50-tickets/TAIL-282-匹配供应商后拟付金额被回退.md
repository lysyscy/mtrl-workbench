# TAIL-282: 匹配供应商后手改的「付款金额」被回退

**What to build:** 在付款通知书页把某行的「付款金额」（本次拟付）手工改掉之后，接着去匹配/保存/采用/放弃集采供应商，改过的那个数**不许被刷新冲掉** —— 现在会被冲回「审批金额－已付金额」。这个覆盖仍只是**本次页面会话**的临时值：整页刷新就散（不落库、不写 Storage）；真付过款、撤销过款、审批金额或已付金额变了之后，旧草稿要**作废**并按最新事实重算，免得拿一个过期数字去付款。

**Blocked by:** None (can start immediately) —— ⚠️ 与 `TAIL-281`（集采付款子表显示与解绑收敛）可能同文件（`shell/actions.js`），开工前先确认它的处置，避免两批差异混成一票。

**Status:** done

- [x] 手改「付款金额」（审批 1000 / 已付 200 / 派生 800 ⇒ 手改 300）后，走**匹配、手动保存、采用、放弃**四条供应商路径，页面仍然显示 300；再触发一次 `reloadNotices()` 也还是 300。
- [x] 同时改两行（A=300、B=120）：对 A 做供应商操作**不影响 B**；不同通知书的草稿**不会串到一起**。
- [x] 手改成 **0** 是有效值（`!= null` 判定）：重拉后仍显示 0，不回落到派生值。
- [x] 供应商保存**失败**（抛错 / `ok:false`）不清掉已改金额；只有后端读回确认后关联才算变了。
- [x] 真**付款成功**、**撤销付款成功**、**审批金额变化**、**已付金额变化**之后，该通知书的旧草稿**失效**并按最新 `approve-paidOf` 重算（旧值不得继续用于支付）。
- [x] 整页刷新后恢复派生默认值；**不写数据库**、不写 `sessionStorage`/`localStorage`；⛔ 不许拿「统计付款金额」`stat_paid` 当拟付草稿的容器。
- [x] 失效/恢复点只有**一处共用出口**（⛔ 不许在 `jcLinkAct`、`reloadM05`、`editss` 各写一遍）。
- [x] 口径不变量：统计付款金额、已付金额、欠款数字**都不被这个拟付覆盖改动**；超额度付款仍被后端整批校验拦住。
- [x] 补一条聚焦测试（`reloadNotices` + 供应商读回 + 草稿恢复/失效），并跑既有 m03 回归：`test_acc_sup_match.py`、`test_wired_m03_list.py`、`test_wired_m03_pay.py`、`test_acc_jc_pay_link.py`、`test_acc_pay_stat.py`。

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：用户提供的《剩余三项问题（R3/R4/R6）只读审查与实施交接书》**第 2 章（R3）**（原六项审查件 R3；同件 R1/R2/R5 已于 2026-10-10 完成并提交 `4ddcfd5`）。不做会怎样：用户先算好「这次付多少」，一匹配供应商数字就被冲回默认值 —— 他要么重填一遍，要么以为系统没接受他的输入。落点：`shell/base.js`（`payOver/payEff`）· `shell/actions.js`（`editss`、`jcLinkAct`、`supManualSave/supMatchRun/supAccept/supReject`）· `shell/core.js`（`adaptNotice/reloadNotices`）。阶段 / 时机：随时。

**排期四问（`§14.3` 同源）**：①**不改口径** —— 覆盖仍是「本次会话的临时拟付」，不是 `stat_paid`、不落库；⛔ 四种禁改法见交接书 §2.2（写 `stat_paid`／加 `pay_amount_override` 字段／停掉供应商重拉／让付款后的旧覆盖永久有效）。②**要改**是因为它是可完全由代码解释的故障：`reloadNotices` 用 `items.map(adaptNotice)` 重建行对象 ⇒ `payOv` 随之消失。③**改哪一层**：把草稿按 `notice_id` 从易被重建的行对象里剥离，界面继续只经 `payEff` 取数。④**怎么算做完**：上列 9 条验收（含真机交互复现），不新建数据库字段。

**未验 / 边界**：本票只落票，未实施任何代码；根因链是**静态源码**推导（交接书标注「源码确定 + 现场症状高置信推断」）。⚠️ 若现场实际手改的是「统计付款金额」那一列而不是「付款金额」，需先定点核对列义再动手。

**2026-10-11 · 落账（agent）｜实施完成。** 九条验收落实，口径未动（仍只是**本次会话**的临时覆盖，不写库、不写 Storage、不碰 `stat_paid`）。

- **改法（3 处实现，一条链）**：① `shell/base.js`：新增按 `String(n.id)` 的会话草稿表 `PAY_OV` ＋ 唯一的保留/作废出口 `payOvEntry`（连**创建时的金额事实**「审批额 / 后端已付汇总」一起存，事实一变即作废）＋ 写 `setPayOv` / 显式失效 `dropPayOv` / 重拉对账 `reconcilePayOv`；`payOver/payEff` 仍是页面唯一读出口（四个消费者一行未改）。② `shell/actions.js`：`editss(k='pay')` 改写草稿出口；`batchPayOk` 成功分支**立即**对本次付款的通知书 `dropPayOv`（⛔ 不等 `reloadNotices` —— 它可能失败）；`revOk` 成功分支按受影响的 `notice_id`（`f.nid`，⛔ 不是 `flow_id`）失效。③ `shell/core.js`：`reloadNotices` 重建 `NO` 后 `reconcilePayOv()`（事实变了的 / 列表不再返回的一律作废）。
- **隔离真机反例（先红后绿）**：新增 `backend/tests/test_tail282_pay_draft.py`（4 条，复用 `ui_page` fixture，只替换 `API.notices` 回包）。**改代码前**跑第 1 条：`assert 800 == 300` —— 正是票面故障（手改 300 被整体换行对象冲回默认）；改后 `4/4` 绿。覆盖：四条供应商路径重拉后仍 300 / 两行不串值 / `0` 有效且行内判不可付 / 供应商写失败不清草稿 / 已付额变（200→400 ⇒ 600）与审批额变（⇒ 500）作废旧草稿 / **付款成功但列表刷新失败**⇒草稿已清且**不伪造新已付** / **撤销成功但刷新失败**⇒草稿已清且 TAIL-281 回执仍在。
- **判据改造（过时实现形态 → 口径）**：`test_wired_m03_pay.py::test_壳里本次应付为0也不可付` 原先逐字钉 `payOver(n)?N2(n.payOv):…`（那是**实现写法**，也正是本票故障本体）⇒ 改成钉口径：默认仍是 `N2(n.approve-paidOf(n.id))`、`.payOv` 不再出现在壳里、草稿有共用出口；零金额不可付那三条断言原样保留。
- **反向灵敏度**：`tools/mut/_mut_m03pay.py` **9/9 命中、MD5 逐字节复原**（其 M1 锚点早已过期、静默「未验证」⇒ 本轮同批指回唯一出口 `const bad=rows.filter(n=>ntPayBlock(n));`，变异意图未改）。
- **相关回归**：`test_shell_ui_workflow.py` 全件 18 项 · `test_tail282_pay_draft.py` 4 项 · `test_wired_m03_pay.py` 9 项 · `test_wired_m03_list.py`/`test_acc_sup_match.py`/`test_acc_jc_pay_link.py`/`test_acc_pay_stat.py`/`test_notice_action_api.py`/`test_tail281_jc.py` 等一并跑过（合并计入下面的按影响总数）。
- **整轮按影响核验**（`_run_rulers.py --paths …`）：8 项审计 rc=0 · **140 项 pytest rc=0（160 s）** · **真机壳自检 rc=0（console/page 错误 0）** · **壳基线盖章 `20261011-0246`** · `BAD: []`。
- **未验 / 边界**：① 本机无真实付款数据复现，现场那条"用户实际手改的确实是「付款金额」列"仍按交接书 §5.2 保留为**未验**（若实际是「统计付款金额」列，须另做定点审查，⛔ 不许两列同时改）；② 未提交（提交须另获授权）。

**2026-10-11 · 两轴 `/code-review`（基点 `14d53aa`，与本票/283 同一轮）。** 两轴的完整报告与逐条处置写在 **`TAIL-283` Comments**（同一次 review 覆盖两票）。属本票的条目：

- 【Standards · 硬违规·**已修**】本批新判据没有反向灵敏度 ⇒ 新增 `tools/mut/_mut_tail282_283.py`，其中 **M1–M4 逐条点本票的 4 条真机用例**：①覆盖挂回行对象（原故障复现）②草稿不再比对金额事实 ③付款成功不再瞬作废 ④撤销成功不再作废 ⇒ 各条对应用例**分别变红**，MD5 逐字节复原。
- 【Standards · 判断项·**已修**】`test_wired_m03_pay.py` 的 `".payOv" not in SHELL` 全文负扫 ⇒ 收窄到拟付草稿出口那一段（并保留"`n.payOv` 不许回壳"这条判词）。该条判据此后由 M1 守。
- 【Spec · **已修**】本票 9 条验收框此前仍是 `[ ]` ⇒ 逐条勾上；Spec 轴查"缺失 0 · 越界 4 · 实现可疑 3"，与本票相关的越界项（`test_wired_m03_action.py` 5 条旧腐化、三支变异锚点）均已在落账写明理由。
- 【Spec · 待确认 · **本轮不动**】「付款项目」列与其筛选仍经 `NO` 缓存（后端已给 `project_key`/`project_display`）—— 不属本票范围，理由同 `TAIL-283` Comments。
