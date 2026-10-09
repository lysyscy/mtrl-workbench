# 分诊标签（票的 `状态` 行用词）

> **读者**：开票 / 领票的 agent｜**回答**：票的 `状态` 行能用哪些词、每个词什么意思
> **何时读**：写票的 `状态` 行时｜⛔ 本页不新增口径（票的纪律见 `issue-tracker.md`）

票状态的定义与适用条件唯一主人为 `ops/agents/issue-tracker.md` §三；写Status时按该节选择。
五个分诊角色沿用 `needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`，本仓另用 `claimed` / `done` 表示在办与销号。机器受控词由 tools/audit/audit_meta.py 的TICKET_STATES消费。
阶段／时机由主计划§14.3与§15索引维护，与票状态分开。
