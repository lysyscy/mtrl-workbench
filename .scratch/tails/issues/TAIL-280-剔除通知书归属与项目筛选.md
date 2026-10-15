# TAIL-280: 剔除通知书可按明确归属筛项目，不阻断导入

**What to build:** 剔除通知书能按可确定的项目归属筛选，历史回填与以后导入共用规则；缺档案或小微不明确仍留空，不阻断、不建档、不改变剔除和统计。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 新导入及重抓剔除单唯一可判归属写入，已有归属保持。
- [x] 判不出的剔除单留空，不阻断整批、不自动建档。
- [x] 历史只回填空归属，金额、剔除来源及统计范围不变，现场项目筛选可用。
- [x] 相关核验通过，按授权提交推送；房租特殊情况不处理。

## Comments

**2026-10-10 · 开工。** 用户授权以上方案及历史数据回填、提交推送。追溯18325ed/TAIL-29：规则剔除单跳过归属校验是为避免2张机关工程单挡住整批61张；跳过阻断合理，完全不尝试归属导致筛选失效。当前复用refill_ownership及resolve_ownership，仅补空归属，判不出的不要求处理。基点excluded-owner-start.json；影响导入组装、归属回填及现有通知书项目筛选，不改剔除规则或数据库结构。

**2026-10-10 · 实施与数据回填。** 导入成功写入后，一次批量查询本批空归属剔除单，再复用refill_ownership；匹配现有档案、只补空值，不建档、不参加整批阻断，归属回填数量写现有抓取回执。已有归属/剔除状态受保护；§4.2.2补充现行规则。`excluded-owner-backfill.py` rc=0：执行时432张剔除单，385张补归属、39张未判定；对全部剔除单逐字段断言除空归属外全部不变，金额、剔除来源、状态均保持。变更前行快照`excluded-owner-data-before.json`只留scratch。FKTZS2026070741执行前已为非剔除、归属1，未列入回填，未对其做恢复或修改房租规则。

核验：`_run_rulers.py --since excluded-owner-start.json --explain`按既有_pytestscope核对影响，局部pytest不更新权威四态。初轮`pytest test_excluded_ownership.py test_acc_prj_own.py test_acc_jc_pay_link.py -q` rc=0（19项）；补选曾误写不存在test_acc_nt_import.py导致rc=1，纠正为test_merge.py后`pytest backend/tests/test_excluded_ownership.py backend/tests/test_acc_prj_own.py backend/tests/test_acc_jc_pay_link.py backend/tests/test_rules_store.py backend/tests/test_wired_archive_chain.py backend/tests/test_notice_actions.py backend/tests/test_merge.py -q` rc=0（58项）。真实导入回归用伪i8取数、实际执行器及事务回滚，验证可判/不可判、新导入/重抓/已指定归属；隔离副本断开回填调用时新增回归rc=1。未真实登录i8抓取。
`ops/server_ctl.ps1 -Action restart` rc=0；syntax_audit、wiring_audit、bytes_guard、doc_audit均rc=0；`excluded-owner-live.py` rc=0，现场太康龙源按项目筛到61张剔除单。壳源码未变，shell_verify rc=0差0，沿用有效快照。现场初次探针因目标单已被恢复、随后因首样本人工剔除而失败，核实后改用真实剔除状态断言，应用行为未为探针改动。

最终`tools/probe/_shell_smoke.py` rc=0（39段、无console/page错误）。本轮约数分钟，主要耗时为完整壳约两分钟；历史数据写入已完成，代码/资料可交付。未修改房租剔除规则、未登录i8抓取、未刷新权威四态、不追加双轴review；按用户授权提交推送。历史回填只作用当前数据库，其他数据库可复用本票对应scratch脚本与既有回填函数执行，Git推送本身不携带数据修改。
