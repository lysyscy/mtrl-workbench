---
id: "TAIL-497"
kind: "ticket"
status: "needs-info"
parent: null
children: ["TAIL-498", "TAIL-499", "TAIL-500", "TAIL-501", "TAIL-502", "TAIL-510"]
blocked_by: []
worktree: null
worktree_state: "retired"
branch: null
managed_runs: []
remaining_acceptance: ["完成设备三账实际接续与业务流程验收"]
next_step: "按 TAIL-501、TAIL-502、TAIL-510 各自的待办核实。"
updated_at: "2026-11-27T18:44:56+08:00"
---

# TAIL-497: 设备三账协同决策地图

**Wayfinder 标签** wayfinder:map

- [ ] 形成可交接方案，能用真实案例验收三账协同

## Destination

形成可交接的设备台账协同方案。日常新增、调拨等业务各录一次，能追溯到工机具分布、流动资产盘点账面与分公司租赁费；能从同一套记录产生按月的 A:I 租赁打印版和半年度的 A:L 盘点打印版。

## Notes

- 用户要解决三账之间的摩擦，重点是设备对应、口径冲突、变更传递和明确的填写入口。
- 用户已确认以和会计对平的流动资产台账为财务基线。实物数量、账面数量与当月计租数量各有来源。租赁新月份带出上月，标记变化，保留不收费行。
- 延续只读原表边界。历史报数沿原样留存，按用户已确认的生效期处理更正。
- 本组票的父子关系、依赖与状态见各票的 frontmatter。开票后先做未阻塞的决策。Grilling 票使用 grilling 和 domain-modeling，Prototype 票使用 prototype。
- 方案验收通过后进入正式实现。工作台、Excel 的职责边界由入口票确定。

## Decisions so far

- [同一设备在三张台账里怎么对应](TAIL-498.md) · 以账面行为主，备注记账实差异，去向取调拨记录。

- [新增和调拨只录一次后如何影响三账](TAIL-499.md) · 新增送会计前完成登记，调拨先于计租确认，报废与财务核销分别记录。

- [跨月计租如何承接并处理例外](TAIL-500.md) · 新购按发票月份选择起收，调拨当月由经办人定归属，停收按生效月份处理。

## Not yet specified

机械费接入方式和启用范围取决于分公司租赁确认结果及接续方案。i8 的台账同步方式、核对与差异处置需等设备身份明确后再定。

## Out of scope

本路线的终点是实施方案。正式开发、生产写入、修改历史原表和补收历史差额属于另行工作。

## Comments

2026-11-14 · Created.
