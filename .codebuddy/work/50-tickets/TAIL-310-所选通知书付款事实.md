# TAIL-310: 批量付款按所选通知书读取事实

**What to build:** 所选通知书付款不再受展示列表数量上限影响，按生效流水实际金额重算，保留整批先验后写和既有回执。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 所选旧日期 ID 即使在展示列表5000条之外也能付款；新路径不调用 build_rows、notice_rows、stat_trace_index 或全量 list_flows。用隔离夹具/SQL limit 反例证明，不制造5001条持久数据。
- [ ] 审批1000、实际有效流水300、人工 stat_paid=50 时本次默认应付为700；已撤销流水不计。Decimal 精度、分类空值兜辅材、草稿 None 与显式0、计划方式与现汇兜底保持；集采有关联可付、无关联拒绝。
- [ ] 输入 [B, missing, A, B] 的 created 顺序与重复次数保持现状，missing 跳过；撤单/剔除排除、全无目标仍报既有错误。仅查询所选唯一 ID 集合，空集合回空；无参数 links_by_notice 仍全量。
- [ ] 整批中任一未批、超额、非法方式或“其他”无备注时0流水；request_id 重复仍拒绝。所选通知书、流水、关联与写入使用同一传入 Session，全部 confirm_batch 成功后才写第一条，写入中异常可由调用方事务整批回滚。
- [ ] 原 HTTP 返回形状、默认方式和单笔流水断言保持；相关定向测试与分层检查通过，结果写局部出口。无产品侧无关改动，不改变列表展示 cap、重复/missing 策略或付款并发机制。

## 执行落点与最小方案

设计及取舍主人 = `.codebuddy/work/10-designs/设计-剩余重构最小方案-20261012.md` §3.1；业务规则回 `delivery/材料科业务全流程说明书.md` §4.2.5 / §4.4.2–4.4.4、`delivery/PRD/02-功能规格/MOD-03.md`。

- `backend/app/mod03_notice/notice_pay_actions.py`：内部所选事实组装替换 build_rows 取数；复用本包 `backend/app/mod03_notice/repository.py` 的 get_notices_by_ids，以及 `backend/app/mod05_flow/service.py` 的 flows_of_notices。按有效实际流水算 payable，by_id 建好后按原 ids 重放，继续使用 PayRow/confirm_batch/create_flow。
- `backend/app/mod11_jc/repository.py`：links_by_notice 增加可选 notice_ids，None 保持旧全量、[] 返回空；`backend/app/mod11_jc/service.py` 委托传递筛选。关联只认同 Session 的现有关系，付款不读前端缓存或人工统计金额。
- `backend/app/mod03_notice/notice_api_router.py` 入口契约保持，不新增 HTTP interface、通用 registry、对本包查询的浅包装或新的 Session。现状源码证据与范围取舍回设计§2，不重新全仓调查。

最低验证：复用/扩展 `backend/tests/test_notice_action_api.py` 的批量付款用例及 `backend/tests/test_acc_pay_verify.py`；新增行为从 apply_batch_pay/HTTP seam 验，至少覆盖上述 cap、实际/人工分叉、集采关联、顺序/重复/missing、整批拒写及回滚。真实事务用测试库回滚，按风险补必要反例，不每条配变异；核验选择按 `ops/agents/issue-tracker.md` §四。

第一批先执行本票，再串行做 TAIL-311（共用 MOD11 service；无技术前置）。当前批修错、相关测试、落账与提交在同一执行会话结束。TAIL-284/287、统计写入口封装、请求并发治理及真实39段/旧壳差58行均不进入本票验收。

---

## Comments

**2026-10-12 · 建票（agent）。** 来源：用户2026-10-12确认三票两批；设计-剩余重构最小方案-20261012.md｜不做会怎样：付款写动作受展示上限约束，并读无关流水与留痕｜落点：backend/app/mod03_notice/notice_pay_actions.py；backend/app/mod11_jc/service.py、repository.py｜阶段 / 时机：随时（第一批先做，与TAIL-311串行）｜**排期四问**（`§14.3` 同源）：①无技术前置②展示cap可静默遗漏所选ID③与311共用MOD11 service同批串行④所选ID金额、整批拒写和同Session可定向核验
