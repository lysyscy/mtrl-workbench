# TAIL-326: 付款计划非法金额整批拒写并移除无业务调用的暂存转发层

**What to build:** 付款计划非法金额整批拒写并移除无业务调用的暂存转发层

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 非法流程金额或预付款金额提交整批拒绝，已有同月计划金额及行集合不变。
- [x] 合法金额与可空字段按既有规则导入；暂存读写和非法token保护保持。
- [x] 删除无业务调用的staging转发层，测试与当前引用改到实际预览载具。

---

## Comments

**2026-10-14 · 建票（agent）。** 来源：用户2026-10-14确认审计第2至7项修复并测试个人技能｜不做会怎样：重导可能把正确金额覆盖成零｜落点：backend/app/mod04_plan/imp_spec.py；backend/app/import_kit/staging.py｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：已隔离复现；有明确错误结果；按原出口最小修复；现有测试边界可复用

**2026-10-14 · 开工。** 共同范围、采用记录、固定评审起点、分派与隔离约定见 .codebuddy/work/50-tickets/TAIL-325-付款批次按唯一通知书登记.md 的共同实施输入；本票无阻塞，按本票验收实施。

**2026-10-14 · 实现者交付与主Agent聚焦核验。** B在m04域金额转换前拒绝显式None的解析错误，保留空串/零/未映射可选列及未匹配项目语义。原缺陷2场景失败rc=1，旧值变零、旧行被删、新行加入均由独立金额预期与行集合揭示；修复后底座及新旧HTTP20项通过rc=0，见 artifacts/audit-fixes-B-red.log、artifacts/audit-fixes-B-green.log。删除staging转发层，测试直达preview_store并用tmp_path；老HTTP夹具改用外层PG回滚事务。主Agent补删wiring_expected两项，历史记录保持。

**2026-10-14 · 统一验收与收尾。** 逐条验收已满足；累计Standards/Spec均无发现，统一证据、旧失败归因与个人技能实跑结论见 .codebuddy/work/50-tickets/TAIL-325-付款批次按唯一通知书登记.md Comments。生产服务未重启；按本批最终Git回执提交推送。
