# TAIL-482: 大表产值累计为空时保存非零合同预估价后重读失败

**What to build:** 大表产值累计为空时保存非零合同预估价后重读失败

**Blocked by:** None

**Status:** ready-for-agent

- [ ] 核实空分子展示规则；复现output_rate空值MoneyError；补纯函数边界及真实副本保存读回验证，保留原金额与未知结果保护

## Comments

2026-11-05 · Created.

2026-11-05 · 用户要求单独开票，未要求在本次部署中实施。已在真实可丢弃副本复现：产值累计为空，保存非零合同预估价成功，随后大表GET返回500；output_rate调用to_money(None)抛MoneyError。前端保留输入并报告已保存、重读失败。后端计算相对加载整改基线未变化，正式业务数据未用于试写。详细路径及证据见[相邻问题](../../loading-structure-20261105/adjacent-finding.md)。
