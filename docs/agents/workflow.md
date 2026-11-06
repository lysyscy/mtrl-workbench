# 项目执行绑定

本页保存本项目已采用规则的来源、按动作入口、目录与运行例外及共享记忆身份。个人方法来自lysyscy/My-Skills，按宿主真实入口或Skills Manager登记定位实际安装资源；维护源发布不代表本机已经安装，读取不授权更新个人包。

## 已采用的项目规则

采用来源：lysyscy/My-Skills `9fda2b149097cac1d7b6ab20e8b520f69b37e445`（2026-10-31）。本项目普通实施与收尾直接按 [CONTRIBUTING](../../CONTRIBUTING.md)，资金、权限、写入/恢复等验证直接按[隔离验证](../guides/development-and-verification.md)，界面取舍按[前端设计](../guides/frontend-design.md)，预览按[预览指南](../guides/frontend-preview.md)。不再把 implement 的旧 execution、verification 或 human-collaboration 手册作为普通任务前置。

跨票统筹明确采用时才读已安装 implement-solo-spec 的 coordination 参考；委派模型、强度、上下文与实参核对由宿主已采用规则持有。setup 仅在接入、获准更新或专项迁移时运行；写 Agent 消费资料仍用实际安装的 writing-for-agents。文档日常维护同步唯一正文、必要引用与消费者，新增/加强长期规则先展示内容与影响并获批；维护指南不再通过外部技能多级跳转。

2026-11-04增量采用 My-Skills `af51f214dd06a3cc66c443f21f9481d2c120b1fa` 的 implement-solo-spec/coordination 第5步（发现证据、原始意图与处置条件）。本机Manager安装及Codex独立子Agent上下文的显式读取已核，未推定其他宿主自动加载。仅适用于此后新采用跨票统筹的任务；在途任务的切换仍按下段办理。

在途任务沿原规格的业务、验收和授权基线；必要的规则切换在原记录写明来源及采用点。主预览只在原计划的验收点提供，记录实际版本和待用户判断事项；仍供验收时保留，资源按本项目指南退出。

React 重写已签收，现行业务和界面约束归 requirements 与 frontend-design，原任务材料按 Git 追溯。开发、隔离验证、人工验收、正式切换和旧版退役分别判定；主线状态不能覆盖独立工作树进度。跨任务文档在安全批次边界整合，遇修改/删除冲突先将独有有效知识迁到现行主人，保护双方内容。

## 目录与退出

本项目沿用 `backend/app`、`backend/tests`、`backend/alembic`、`backend/app/resources` 的 Python 组件契约，React 组件沿 `apps/frontend/{src,tests}` 及组件根依赖/锁/构建契约；网页字体、模板按运行消费者保留。`.scratch/<effort>`只放活动Markdown/票；默认开发输出由`tools/audit/workspace_paths.py`自动登记到项目`.artifacts/runs`，短命计算文件用系统TEMP。成功释放已结束消费者的work，必要证据及已核纯开发失败保留30天；未知、在用与恢复资料继续保护。setup负责随仓固定版本部署，实际路径、显式任务和失败分支见[实际接入](../guides/artifact-lifecycle.md#本项目实际接入)。旧AgentArtifacts登记区和显式`.artifacts/active`运行沿原入口与期限；未迁移旧运行才执行旧workspace_check，不扩扫历史目录。无相关产物的简单任务不造effort/run；仍供验收的主预览按原用途保留，不能因回复结束停服。

历史有效独有知识先归现行正文；可达Git提交及原路径足够追溯且无活动用途时，旧正文退出。本项目仍保活动依赖、验收和范围裁决所需最小集合，终态不推定缺票已完成。恢复用可达提交及原路径，核后续修改后只取所需内容。

`.env`、`var`、`.codex-attachments`、原始输入、成品、在用构建、非 Git/忽略资料及他人未提交内容由各自用途决定生命周期。本次处理直接相关且已无用途的产物，包含前序会话遗留；他人修改与在用原件保持受保护，专项清理逐文件核 Git 可恢复性。

### 任务文件退出

采用 My-Skills `709a9001f3c8c1e67fa0e28f45d000d032308a4e` 的独立只读检查；原生命周期登记和固定旧运行保持。收尾范围从现有任务记录取得，不新建清理台账。使用实际安装的脚本，重复`--path`列本任务目录及散置票，先固定已保存的完整提交：

```text
backend/.venv/Scripts/python.exe -B -X utf8 C:/Users/Administrator/.skills-manager/skills/setup-solo-workflow/scripts/task_files.py --root D:/dev/mtrl-workbench --path .scratch/<effort> --path .scratch/tails/issues/<本任务票>.md --revision <已保存提交>
```

首查核在场文件、未保存增量和仓内内联Markdown链接/代码字面路径。负责人确认现行知识归位、Git可恢复性及活动消费者后，按授权处置；处置后用同一范围/提交加`--closed`，仍有路径或本地引用时非零。另运行`tools/oneoff/_list_tails.py --all`核余下票的实际依赖。动态路径、外部脚本及历史聊天等消费者不由文本扫描证明，具名保留的材料在原记录说明用途与解除条件。检查不删除、不判业务结项、不按年龄清理、不接每次提交钩子，也不替代运行组/预览/schema/工作树的各自退出核验。

## 共享记忆

共同记忆政策由宿主已部署指令直接提供；setup 模板只用于布置，不是日常回读入口。本项目固定 bank ID 为 `project-3379fef93fbada35`；子目录和同项目其他工作树沿用此身份，分支相关记录保留来源分支、必要版本及合并/部署状态。无有效内容不建空库。

普通业务按已有业务入口和显式技能执行，记忆使用不触发工程实施、票务或额外收尾；开发代码、辅助工具或技能才读取本页实施方法。现行规则、关键理由与活动状态仍由项目文件持有，偏好、决定背景及验证经验按共同政策留存。首次完整接入和专项内容迁移才读取同源 `references/memory-adoption.md`，平常任务不重跑筛选。

本仓历史React重写分支沿用同一记忆库。2026-10-28用户已签收正式React入口并批准旧版退役，原React与切换候选两棵冻结工作树在必要本机资料保全后均已退出；分支提交仍可达。源码退役、现场加载和资源退出分别记录，当前状态回status；[退役回执](https://github.com/lysyscy/mtrl-workbench/blob/040bbdc2b9462a264490de2e9fd5add19ba96ffe/.scratch/tails/issues/TAIL-424-旧前端退役与清理.md)按Git追溯，后续任务的预览按实际登记由对应owner持有。

## 已接入的个人产物生命周期

2026-11-06按[ADR](../adr/0001-development-artifact-ownership.md)采用个人包`2e0e153c0b434da03a2b1363b45945599a76b0c9`的项目内默认与setup固定版本部署。实际CLI、保留分支、调度验收和旧运行边界统一见[产物生命周期](../guides/artifact-lifecycle.md)，其他项目不因此切换。
