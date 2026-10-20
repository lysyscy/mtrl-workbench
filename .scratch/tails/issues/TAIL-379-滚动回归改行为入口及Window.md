# TAIL-379: 滚动回归改行为入口及Windows脚本模板

**What to build:** 滚动回归改行为入口及Windows脚本模板

**Blocked by:** None

**Status:** done

- [x] 源码字样不再充当滚动行为保障，既有浏览器场景明确产生两轴滚动并保持通过。
- [x] 共享渲染修改有定向运行入口，保留切页回顶结构保护。
- [x] 全局入口已有的Windows运行说明补可复制模板，成功与失败分支实测。

---

## Comments

**2026-10-20 · 建票（agent）。** 来源：用户批准复盘2和4｜不做会怎样：不扩全量测试或新增技能规则｜落点：现有测试与运行说明｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：弱静态断言漏检及命令嵌套引号重跑

**2026-10-20 · 实施核验。** 删除scrollTop/keep字样弱断言，保留切页回顶结构检查；强化通知书夹具横向前置，文档补既有16项两轴选集。`pytest tests/test_shell_render.py tests/test_shell_ui_workflow.py -k "切页显式回顶 or 通知书勾选后改付款金额 or 集采保存后不被重画 or 集采推进后保留" -q --tb=short -o addopts=`：17通过，exit0；原缺陷失败证据复用378。全局AGENTS已指向的C:/Users/Administrator/.codex/local-hooks/README.md补PowerShell7 here-string模板；中文/引号/$/反引号实测及Python异常非零分支通过。PS5.1试验中文损坏，模板限PS7并指向UTF-8脚本文件。个人execution/verification已有行为验收和实际失败保护要求，无需重复加规则；未改My-Skills或Manager副本，不触发技能发布。仅本机运行说明更新，不宣称多端同步。未全量测试、未改生产业务或重启。
