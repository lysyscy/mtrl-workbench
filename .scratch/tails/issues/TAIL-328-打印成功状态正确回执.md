# TAIL-328: 打印成功但替换属性时提示已投递且不引导重打

**What to build:** 打印成功但替换属性时提示已投递且不引导重打

**Blocked by:** None (can start immediately)

**Status:** done

- [x] IPP成功状态0x0000、0x0001和0x0002均显示已投递未核实，属性替换可提示但不报未投递。
- [x] 连接失败、畸形响应与明确打印错误仍拒绝，测试不连接真实打印机。

---

## Comments

**2026-10-14 · 建票（agent）。** 来源：用户2026-10-14确认审计第2至7项修复并测试个人技能｜不做会怎样：打印机已接收作业却显示未投递｜落点：backend/app/mod03_notice/print/ipp.py｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：已隔离复现；有明确错误结果；按原出口最小修复；现有测试边界可复用

**2026-10-14 · 开工。** 共同范围、采用记录、固定评审起点、分派与隔离约定见 .codebuddy/work/50-tickets/TAIL-325-付款批次按唯一通知书登记.md 的共同实施输入；本票无阻塞，按本票验收实施。

**2026-10-14 · 实现与隔离验证。** IPP成功类别0x00xx按已接收处理，非零成功提示属性调整；原连接失败、明确错误及畸形短响应拒绝保持。新增0x0001/0x0002回归修复前2失败5通过（rc=1），修复后打印相关4件38项通过（rc=0）。真实网络完全替身，证据 artifacts/audit-fixes-main-print-red.log、artifacts/audit-fixes-main-print-green.log；协议依据 RFC 8011 B.1.2（https://www.rfc-editor.org/rfc/rfc8011.html#appendix-B.1.2）。

**2026-10-14 · 统一验收与收尾。** 逐条验收已满足；累计Standards/Spec均无发现，统一证据、旧失败归因与个人技能实跑结论见 .codebuddy/work/50-tickets/TAIL-325-付款批次按唯一通知书登记.md Comments。生产服务未重启；按本批最终Git回执提交推送。
