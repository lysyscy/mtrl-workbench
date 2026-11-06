# 任务文件退出、导航与计划任务实施回执

2026-11-06，用户批准复盘建议1、2落地，并要求实现既有清理计划任务。执行范围为独立任务文件检查、当前项目导航与已结束材料退出，以及原六个AgentArtifacts登记区的调度修复；不修改业务、服务或正式数据。原油卡交接、前端设计/油卡需求、未跟踪审计资料及status原额外空行保持保护。

## 独立退出检查与技能分发

唯一维护源为`D:/dev/My-Skills`，起点`1d0d09a0d163ccb7f1af831d5e4c713796bba187`。新增`setup-solo-workflow/scripts/task_files.py`，不接每次提交钩子、不使用登记组closed推导任务文档已退出。显式范围限定`.scratch`内目录/散置票；固定Git提交，报告当前文件、未保存增量和仓内内联Markdown链接/代码字面路径。`--closed`对残留和引用返回非零；越界/链接/读取失败不冒充成功。工具只读，不判断业务结项、外部消费者或删除授权。

7项隔离回归覆盖运行组结项但文件仍在、脏/未跟踪原件保护、删除后引用、不可读来源、非法/错误范围、外部链接及真实CLI非零。个人包清单全套运行213项，209项通过，4项需要专用Windows夹具的原有环境检查按原条件跳过；结构验证通过。首次结构验证因既有业务venv无yaml而阻塞，随后沿规范在临时uv环境使用PyYAML，通过后退出，未向业务环境安装依赖。

源提交`709a9001f3c8c1e67fa0e28f45d000d032308a4e`已正常推送main，[对应CI](https://github.com/lysyscy/My-Skills/actions/runs/42193839404)成功。首次推送被自动审批以未明确授权该外部默认分支拒绝；用户随后明确授权推送及原部署更新，正常推送成功，未绕过。

Manager预检、安装后验、`skills check --force`的`up_to_date`及分发后验均通过；setup技能原ID、coding Preset和codebuddy/codex/deepseek_harness/minimax_code/workbuddy/zcode六个部署保持。Manager自动备份`77e784fa002415614e25259822bb1fe152ab0876`已核远端与完整内容。跨设备恢复仍有官方`needs_calibration_after_restore`边界：恢复后须官方update/check校准，未实测另一台设备。用于后验的本任务干净发布工作树已退出，My-Skills旧工作树与未跟踪材料保持。

项目CONTRIBUTING已把任务文件、运行产物、工作树退出分别接线，实际命令归[工作流绑定](../../docs/agents/workflow.md#任务文件退出)。真实坏现场的首查返回非零：质量路线26份材料与4个外部引用仍在，证明新检查能在本轮原遗漏上给出反馈，不只靠夹具通过。

## 当前导航与历史材料

`status`收敛为当前运行、当前维护、油卡旧接续、具名保留与Git追溯。正式当前仍为`b3ba025f`、回退`7156a5ae`，本次不再部署。i8现行契约/扩展说明保真实17条代表与未验范围，原验收链接改为固定Git对象；路由仅改设计注释指向现行契约，运行AST不变。质量路线的当前机制已在代码/验证指南/业务规则持有，完整判据和具名覆盖限制按退出前Git原路径追溯，不把未验场景升级为通过或操作授权。

初查7组71个已跟踪候选，发现未跟踪审计报告仍消费`audit-remediation-20261105`的两份文档；这两份具名保留，不修改他人的报告。因此实际退出范围为其余6个effort目录、TAIL-450及475–496，保留油卡452–463/474依赖链与423/424切换回执。新增本回执先保存，再与本轮材料一起按Git追溯退出，不再留下永久effort。

删除前逐文件核HEAD保存一致、无链接、绝对边界与所有权；余下票用原`_list_tails.py --all`检查，正文引用用实际安装的独立检查器核验。阶段提交先固定本回执和新导航，随后执行退出；最终删除数量、关闭检查及保存SHA在收尾提交/当前status记录。用户原件、试用schema/恢复点、未跟踪资料及无关修改不在删除范围。

## 每日计划任务

保留原`PersonalSkillArtifactCleanup`为实际执行者；原Codex同名自动化继续PAUSED，避免重复清理。范围仍是mtrl-workbench、my-skills、project-workflow、inquiry、approval、metrology六个已登记根，执行原`artifact_lifecycle.py sweep`，不扫描仓库`.scratch`或旧现场。

实际对照确认：普通Windows任务无包身份，探针当时只能看到一个登记根；同一探针进入`OpenAI.Codex`包上下文后六个均可见。使用[微软包内执行命令](https://learn.microsoft.com/en-us/powershell/module/appx/invoke-commandindesktoppackage?view=windowsserver2025-ps)的`-PreventBreakaway`保持子进程视图，不搬迁登记根、不改登记身份。最终包装器等待本次新完成回执、核六根集合及总体返回，启动成功不能代替清理成功。

前两轮实际调度5区通过、询价区报无路径的errno13权限拒绝；后续在同一上下文中只读检查、非阻塞锁和通知状态写入均成功，符合瞬时锁竞争。原执行器只对该无路径错误增加最多3次、间隔5秒的有界重试；路径权限错误和未知失败不重试。纯替身验证临时占锁后成功、持续占锁仍失败、带路径权限错误只尝试一次。最终真实轮六区均首次尝试返回0，不能把这轮成功归因于重试。

17:31真实调度完成，`LastTaskResult=0`、Ready/Enabled，下一次为2026-11-07 09:00（北京时间），此后每天9点；保留当前用户Interactive身份、错过后补跑和IgnoreNew禁止重叠。需要该用户登录、设备运行且应用包/解释器可用，未验证关机或注销状态下执行。失败按Windows会话消息通知并去重，前次真实失败已成功调用消息发送并写通知标记；未宣称用户已阅读。成功后清除通知去重标记。运行源为`C:/Users/Administrator/.codex/automations/automation/windows_cleanup.py`及`windows_cleanup_task.ps1`，实际回执为同目录`windows-task-result.json`与`windows-last-run.json`。

所有active/hold保护保持，调度不解除保护、不改保留期限、不强抢锁。原任务XML、原/新脚本、失败和成功回执及包上下文探针证据保留于本机登记组`workflow-close-20261106/files/reports`；临时探针、修复脚本已退出原目录。该组在本轮最后退出检查保存后按30天结项，不将启用调度当作现在就应删除未到期证据。
