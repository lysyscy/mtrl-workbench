# 开发产物管理实施

## 范围与固定基线

- 用户2026-11-06确认[ADR](../../docs/adr/0001-development-artifact-ownership.md)全部六项取舍，setup负责部署升级，并明确要求开始实施。
- 先修改唯一维护源 D:/dev/My-Skills 的 setup，再将固定版本部署到材料工作台；其余项目不切换。可弃旧文件按ADR分类退出，业务原件、恢复点、在用资源、未知归属与无关未提交内容保持保护。
- My-Skills main基点：709a9001f3c8c1e67fa0e28f45d000d032308a4e；来源为 https://github.com/lysyscy/My-Skills.git。该仓仅有既存未跟踪 .artifacts/.scratch/exports，保持不动。
- Manager setup ID e34116bd-0a65-4a0e-a178-d45af8836aae，来源 https://github.com/lysyscy/My-Skills/tree/main/skills；原部署 codebuddy/codex/deepseek_harness/minimax_code/workbuddy/zcode，保持集合与Preset。
- 材料工作台已有无关修改：docs/guides/frontend-design.md、docs/status.md，以及.impeccable、PRODUCT.md、DESIGN.md等未跟踪资料。根.tmp-fees-width.py、debug.log等仅按本任务明确核过的分类处置，不混入其他提交。
- Hindsight倡议：kp-354d303817ae49168c1096c30fb7371f。正式规则和授权以本任务及ADR为准。

## 执行状态

1. 已完成：确认维护源、安装身份、现有实现与项目调用链；普通沙箱不能查询My-Skills工作树/Manager锁，宿主权限下只读核对成功，未修改Git配置。
2. 已实现并源端验证：项目布局、可弃开发声明、进程创建身份及消费者登记、异常退出有限保留，旧格式兼容；setup固定版本部署入口及独有修改保护。
3. 源提交2e0e153c0b434da03a2b1363b45945599a76b0c9已推送main。全套224项、4条件跳过，其余通过；系统结构验证通过（临时uv+PyYAML，未装业务venv）；CI [42216806182](https://github.com/lysyscy/My-Skills/actions/runs/42216806182)成功。
4. 已完成Manager preflight/update/confirm-install/check/confirm-distribution，结果distribution_verified，六宿主部署集合与Preset保持。Manager自动备份已推送42994acec2ea85a05bbc64d96ac703a12df96da5；其他实体设备尚未核验。
5. 已由实际安装的setup将该固定版本部署到tools/_vendor/setup_solo_workflow及项目登记区，校验清单随仓保存。workspace_paths、backend_verify、frontend preview/release已接入；前端候选跨进程消费仍受保护。
6. 已验证：生产者15项、backend_verify工具24项、路径新旧格式10项、发布操作28项通过。发布操作初次两项失败为旧假实现缺少configuration接口，补齐后28项通过。真实backend_verify执行workspace_paths/preview_runtime，pytest=0、隔离schema与系统TEMP均退出；报告在.artifacts/runs/204153-913712-13120/reports/backend-verify.json。
7. 每日任务保留原六根，仅增加mtrl-workbench-project。首次启动被自动审批拒绝后先只读核七根无到期/自动封存候选，未绕过保护；提供该证据后同一任务入口于北京时间20:58–20:59成功执行，七项exit=0、LastTaskResult=0、未新增删除。通知机制沿既有已验证入口，本轮未另触发失败通知。
8. 旧文件分类已完成本轮处置：1个失效脚本和9个旧构建候选，共353文件、24,396,656字节。删除前复核绝对边界、无链接、完整散列、正式/回退指针、成功发布回执及当前引用；执行回执见旧基线证据组reports/legacy-cleanup-{plan,result}.json。
9. 项目实现提交9c4f4f08d4a4a430ed2618533bade5735f58bca2已推送并核对远端；真实pre-commit语法、字节与凭据文件检查通过。固定运行时增加.gitattributes的LF约束，暂存与工作区字节均匹配setup清单，避免Windows检出转换损坏来源校验。
10. 真实publish -CheckOnly通过，报告为.artifacts/runs/211113-713600-37196/reports/preflight.json；消费者退出后work已释放，证据closed、operation_result=success，2026-12-06T13:11:22.867200Z到期。正式前端指针仍为040bbdc2b946；本轮未重启或操作真实业务数据。
11. 实施与验收已完成；本记录完成保存后按task_files核退出，历史提交保留完整回执，ADR与现行指南继续持有规则。旧基线证据组已close，必要证据保留到2026-12-06T13:14:04.144982Z，不将证据结项当作任务Markdown退出。

## 本轮运行现场

- 旧基线证据组：C:/Users/Administrator/AppData/Local/AgentArtifacts/projects/mtrl-workbench/groups/development-artifact-ownership-20261106/files；已closed、operation_result=success、无hold，必要日志和回执保留30天。
- 全套源测试日志：上述logs/my-skills-full-tests.log。
- 发布用干净固定检出C:/Users/Administrator/AppData/Local/Temp/mtrl-setup-243yux5e已退出：核远端保存、无未提交/未跟踪/忽略内容与消费者后通过git worktree remove移除，Git登记及原目录均不存在。
- 首次在证据组work/setup-source建检出因Windows长路径失败；Git无登记、原目录不存在，不涉及其他工作树。
- 源提交作者沿本仓最近记录Codex Agent/codex-agent@localhost，用单次-c参数，未改持久Git配置。

## 关键实现约束

- 现有legacy groups/<id>/files与closed清单保护保留；新项目目标为.artifacts/runs/<id>/run.json及类型目录。
- 系统TEMP只放允许丢失的中间件；跨进程候选和预览build仍留受归属校验的work，并由消费者决定退出。
- 仅生产者事先声明且可核实的纯开发运行允许失败或异常退出进入30天保留；默认未知/业务运行继续保护。
- 正常操作结果与清理结果分开；显式清理仍非零报告未完成，生产者入口保留原退出码。
- 共享工具只改维护源，项目接入由setup部署固定版本；不直接编辑中央库或Agent副本。

## 本轮具名保留

- .artifacts/active/oilcard-interaction/20261030-dsh/work：原型node_modules仍链接到此处，README保留Univer研究用途；由原型任务核试用/恢复用途后退出，不能顺带删未跟踪源码。
- var/state/import_preview：历史业务确认JSON，现有运行消费者与原业务退出条件未完整确认；由导入业务核实后单独处置。
- debug.log：仍在近期写入，写入者未核实；保留到来源与占用解除。
- .artifacts/archive：93组仍在既有期限内（11月18日至12月2日），不搬家或续期；旧AgentArtifacts活动/保护组沿原主人。
- 原有.scratch中的TAIL-474及share-feasibility研究，和他人PRODUCT/DESIGN/.impeccable材料继续由原任务持有。
- data、exports、var/backups、正式及回退frontend releases、业务原件保持原保护。删除旧候选构建不删除对应reports/logs。
