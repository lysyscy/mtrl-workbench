---
id: notice-fetch-261126
kind: plan
status: needs-human
parent: null
children: []
blocked_by: []
worktree: t3-a0519f43-082597183e4816c2
worktree_state: blocked
branch: null
managed_runs: ["notice-fetch-jc-review"]
remaining_acceptance: ["正式登录态真实 i8 抓取及自动关联尚未验收"]
next_step: "现场验收沿正式入口和当次授权；独立复核证据到期后，确认旧 T3 线程与本地内容去向，再复核工作树退出。"
updated_at: "2026-11-27T18:44:56+08:00"
---

# 付款通知书抓取与集采关联

2026-11-26，后台抓取、自动关联和手工批量关联随正式运行 `215529-339448-17560` 上线。隔离验证覆盖任务恢复、进度及关联结果。现场真实 i8 抓取留待验收。规则分别见[付款通知书抓取](../requirements/payments.md)和[集采通知书关联](../requirements/central-procurement.md#通知书关联入口)。

用户确认旧分支的开发工作已经完成并合入。正式登录态的 i8 抓取与自动关联仍需现场验证，可从正式入口执行。旧复核工作树内的受管组 `notice-fetch-jc-review` 已结项，四份独立复核证据按原登记保留至 2026-12-26。证据到期后确认旧 T3 线程已结案和树内其余内容的去向，再按收尾检查退出。开发前的交接稿已由正式规则和发布回执承接并清理。
