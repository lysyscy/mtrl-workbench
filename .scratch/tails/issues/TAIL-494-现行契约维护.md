# TAIL-494: 同步已核实的文档与验证契约

**What to build:** 同步已核实的文档与验证契约

**Blocked by:** TAIL-490

**Status:** done

**Labels:** wayfinder:task

**Parent:** [材料工作台工程质量达标路线](TAIL-483-工程质量达标路线.md)

**Assignee:** codex/01a1af77-36ae-7cb0-9ae8-65fa971d389b

**Mode:** AFK

- [x] 修正已证实的字体路径和过期注释指针及跳钩子建议；旧机械导出断言沿批准增列同步；只改当前主人不改业务或全仓规则，引用和最小检查通过

## 批次目标与边界

沿基线T-6/B3和492实际过期断言，仅同步已存在的现行契约，不发明新规范或清理未知内容。

- README与workflow的字体目录指向实际`backend/app/web/fonts`，模板仍在resources/templates。
- report_export/resources旧模板说明/哈希表指针改成现行主人；report_export/service库存导出“HTTP现导”旧注释改为真实缓存出口。
- mod15_user/api解绑i8的旧fallback注释依当前identity拒绝语义改正；不改账号/密码或外呼行为。
- ops/install_hooks的跳钩子建议与CONTRIBUTING现行规则冲突，改为修复失败后正常提交，不更新本机hook安装或变更安全配置。
- 492已将机械年度导出10列旧断言同步已批准11列并核新列公式/缓存，保其失败与复测证据；不改导出结果。

验证仅语义、实际引用、变更范围与真实钩子；复用492失败单例的红绿。不运行应用/业务测试来验证纯注释。回退为本批文本/测试变更，无运行资源和数据变更。未知旧工具/原件/其他dirty保留。

## Comments

2026-11-06 · Created.

2026-11-06 · done: Resolution：实际字体/模板主人和过期注释已同步，3份Python去文档AST不变；旧机械增列断言沿批准11列、公式和缓存修正，失败单例复测通过。独立双轴审查无实质发现；详见 ../../quality-wayfinding-20261106/implementation.md。未更新本机hook或业务。
