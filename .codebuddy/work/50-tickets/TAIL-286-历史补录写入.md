# TAIL-286: 历史付款补录（二）：按用户批准的冻结清单，用共享付款准入判定（PayRow.block＋confirm_batch 逐笔）做一次受控写入——source=imported＋批次号，写入前复验、超付/空方式两类历史例外显式登记、写入后独立复算验收

**What to build:** 历史付款补录（二）：按用户批准的冻结清单，用共享付款准入判定（PayRow.block＋confirm_batch 逐笔）做一次受控写入——source=imported＋批次号，写入前复验、超付/空方式两类历史例外显式登记、写入后独立复算验收

**Blocked by:** TAIL-285（冻结清单＋用户逐条批准，含超付/空方式例外）；写入前备份与停服窗口；开工先确认 281 的处置

**Status:** ready-for-agent

- [ ] 新 `supplement.py`（落 `backend/app/mod05_flow/`，名字以设计稿 §4.4 为准）：`preflight`（只读三分类：可写/例外/必拒）＋ `commit`（事务内逐笔复验＋写入）；**判定零复制** —— 复用 `mod03_notice.domain.PayRow.block` 与 `confirm_batch`（**逐笔单行批 ＋ 该笔日期**），⛔ 不在本文件重写审批/关联/余额判定。
- [ ] 复验覆盖（任一不满足即"必拒"）：通知书存在且 `bill_no` 与清单一致 / 审批＝「已批」/ 未撤单未剔除 / 集采分类**必须已关联** / 金额>0 / 金额 ≤ 本次应付（按批内序累积）。
- [ ] 两类**历史例外**仅限清单标记行、且逐条入回执：超付（`overpay_approved`）、空付款方式（**存空**，⛔ 不兜「现汇」）；「其他」方式须有备注。
- [ ] 防重三道：`has_request_id(HIST#{batch}#{seq})`、内容指纹（`notice_id+pay_date+amount`）对库内**生效**流水、批内指纹；命中即拒并报。
- [ ] **不落半批**：批内任一行必拒 ⇒ 整批零新增流水（事务回滚）。
- [ ] `project_id = 通知书 ownership_id`（`None` 照实写）；写入后流水页「付款项目」列可见（口径修正理由见设计稿 §5.1）。
- [ ] 写入后 `stat_paid` 自动更新（未手改）；**手改过 `stat_paid` 的行保留人工值**，差异单独报告。
- [ ] 集采合同 `pay_sum`/欠款随补录正确（`build_detail` 复算）；`TAIL-276` 链路**零改动**（跑 `test_tail276_jc.py` 证明原样绿）。
- [ ] `rollback_batch` 复验：整批撤销留痕、`stat_paid` 回退、可观察。
- [ ] 执行流程落档：停服 → 备份（`.codebuddy/backups/`）→ 写 → 复算 → 起服；回执与清单归档 `artifacts/hist_supplement/`。
- [ ] 独立复算脚本（`_hist_verify.py`，落 `tools/probe/`，名字以设计稿 §4.5 为准）：按笔/按通知书/按项目/按付款日期/按集采合同**逐层对账**，与批准清单逐笔一致；例外逐条有据。
- [ ] 回归绿并报 exit code：新 `test_tail286_supplement.py` ＋ `test_acc_flow_import.py` ＋ `test_tail276_jc.py` ＋ 集采/流水相关；收工按影响跑 `_run_rulers.py --since`。

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：同 TAIL-285；设计稿 .codebuddy/work/10-designs/设计-历史付款补录与集采关联-20261011.md 第 4～7 节｜不做会怎样：不复验就落库＝未关联/未批/重复的款项混入流水，集采欠款随之失真；不落半批与内容级防重是本仓既有铁律｜落点：新 backend/app/mod05_flow/supplement.py ＋ 执行脚本 tools/oneoff/ ＋ 复算脚本 tools/probe/ ＋ 回执 artifacts/hist_supplement/｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①规模：只做这一轮一次性写入的受控入口，不做常驻 UI、不发新端点 ②要改：现有导入链不查集采关联闸/审批闸/内容级防重，直接 create_flow 批量写入是用户明令禁止的 ③改哪层：新编排层复用 mod03 判定与 mod05 唯一落库出口，判定零复制；脚本在停服窗口执行 ④做完＝12 条验收＋独立复算逐笔对账一致

### 前置与边界

- **Blocked by**：`TAIL-285` 的冻结清单 ＋ 用户逐条批准（含超付/空方式例外）；写入前需**停服窗口 ＋ 完整备份**（备份落点 `.codebuddy/backups/`）。
- 与 `TAIL-281`/`282`/`283` **零文件重叠**：本票只新增 `supplement.py`（落 `backend/app/mod05_flow/`）与 `tools/` 下脚本；⛔ 不碰 `mod05_flow/router.py`、`mod05_flow/service.py`、`mod11_jc/*`、`mod03_notice/notice_api_router.py`、`shell/*`。
- ⛔ 不改金额口径与集采派生（`contract_amounts`/`payments_of_many`/`sync_stat_paid`）；⛔ 不写 `jc_payment`；⛔ 不发新 HTTP 端点、不做常驻 UI。
- ⭐ **8 月慧能/宜化两块已由用户手工录入系统**（2026-10-11）⇒ 不在本次清单、**不得重复写入**；P6 复算也不把它们计入本次预期。
- **281 已入库并销号**（`14d53aa`，2026-10-11）——与本票**零文件重叠**（见上一条）；本票开工时 `git log --oneline -3` 复核一下即可，⛔ 不把两批差异混成一票。

### 未验 / 边界

- 本票尚未开工；上表是验收标准，不是已完成结果。
- 「现有 `importer.commit` 是否同步改 `project_id`」属**建议项**（设计稿 §5.1 附注），需用户点头，默认不做。
- 写入窗口、备份命令与 `pg_dump` 参数以本机 `.env` 的 `DATABASE_URL` 为准（设计稿 §八）。
