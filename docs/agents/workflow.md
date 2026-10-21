# 项目执行绑定

> 读者：实施、核验或保存本仓改动的 Agent。回答：个人方法来源、本项目输入、权限、隔离与保存接线。只读调查按当次范围读取，不展开实施收尾。

## 一、来源与项目输入

本次目录标准固定于 lysyscy/My-Skills 已发布提交 `aab574c26cae00fe2c5d1f6c114e41edb929792d`。来源为 setup-solo-workflow 所属的 references/document-layout.md、document-maintenance.md 与 document-migration.md；完整目录标准读原件，本页只保留项目绑定。调用前沿当前宿主或 Skills Manager 登记定位实际入口，核本次需要的资源；维护源与已安装版本不一致时区分来源，不因新会话自动同步。

| 动作 | 同来源参考 |
|---|---|
| 普通实施与唯一收尾 | implement-solo-spec → references/execution.md；涉及共享契约、失败归因等风险时读 references/verification.md |
| 明确采用跨批统筹；创建子 Agent | 分别读 implement-solo-spec → references/coordination.md、references/delegation.md；既有采用记录与任务限制优先 |
| 日常文档维护；选择目录；专项迁移 | 分别读 setup-solo-workflow → references/document-maintenance.md、references/document-layout.md、references/document-migration.md |
| 个人方法复盘、能力缺口或获准包维护 | improve-workflow 及其按条件参考；本轮专项迁移不授权技能更新 |

`[用户·2026-10-13]` 本仓接入 setup-solo-workflow 与 implement-solo-spec。普通任务、输入接续、子代理配置、资料维护与明确采用后的 effort 调度按 AGENTS.md 的条件入口读取个人维护源；本节保留本项目的输入、状态、验证能力和授权。已有Matt票源、标签、业务资料与D件布局直接复用。

| 需要绑定的内容 | 本仓主人与落点 |
|---|---|
| 现行需求与字段口径 | `docs/requirements/材料科业务全流程说明书.md` / `docs/requirements/PRD/`；按AGENTS.md定位对应MOD与原句 |
| effort规格、采用记录及累计范围 | 已有设计件或所属票；新独立方案放 `.scratch/<effort>/`；已结束旧方案从docs/archive/index.md追溯，单票目标与验收放票面。明确采用时记录用户确认、固定起点、累计范围与当次授权；不为接入新建空规格或第二份状态表 |
| 票源与阶段 | `docs/agents/issue-tracker.md` §一～§四；主计划§15是活跃索引，§14.3为排期，已销号姊妹件是历史短索引；开销票使用 `_tail_open.py` / `_tail_close.py` |
| 资料目录与历史 | README.md §二/三/四/七、docs/guides/document-governance.md、docs/guides/work-records.md；术语及D件消费回 docs/agents/domain.md |
| 验证程序与选择 | 按实际行为、风险及调用者选择现有 pytest 文件/节点和必要静态工具；命令、隔离及浏览器分工回 `docs/guides/development-and-verification.md` §十一 |
| 结果与接续 | 当前票Comments留命令、退出码、关键数、未验边界与必要复现；跨会话且无合适票时才用当日日志；当前交接回主计划§13.6 |
| 运行与数据权限 | docs/agents/project-rules.md的凭据边界；服务与恢复操作回 docs/guides/deployment.md。测试使用隔离数据；生产服务重启、迁移及真实业务写入按当前明确授权执行 |

金额或日期出口变化仍先按业务样例核对字段目的、实际事实与统计调整；已确认规格沿用，不重新访谈。未知使用者继续调查并留下缺口；验收、证据和票状态须一致。资料同步及最终输入核验按AGENTS.md指向的个人方法执行。

## 二、提交与推送

`[用户·2026-10-12]` 运行 agent 自行决定是否及何时提交、推送本仓改动，无需另征用户同意；当前任务明确要求不提交或不推送时遵守该要求。

决定提交前完成相关核验，明确列举本次范围内的文件暂存，保留无关已有修改，遵守 docs/agents/project-rules.md 的凭据与 Git 操作纪律，运行真实提交钩子。推送后读取远端分支SHA与本地提交核对；交付报告SHA及实际结果。源码提交、运行加载和现场验收分别记载。

## 三、取舍：本项目够用即止

`[用户·2026-10-12]` 一人开发练手，优先速度和token成本；金额、身份权限、写入、回滚与已修复缺陷的有效覆盖保留。普通小改不为假设情况扩测试，不强制每条新增测试配独立变异。
`[用户·2026-10-09]` 建检查前判断“本项目是否真会发生、后果是否值得维护成本”；按已证缺陷选择保障，不为不存在的风险增加代码或承诺。

## 四、按影响核验：项目能力与边界

交付前由Agent按implement-solo-spec → execution.md「自查、独立审查、关闭发现」主动选择自查、定向独立审查或完整双轴，并在原票或回执说明理由与实际覆盖范围；不等待用户另开对话或提醒。核累计未审改动，不能只看最后一笔提交。本仓跨模块金额口径、写入/撤销/事务及共享壳的组合改动重点核集成风险；简单局部样式或文字修正仍按实际影响裁剪。来源版本和本次读取基线分别记录，源码更新不等于已安装。

- 测试维护取舍沿个人verification.md：保留当前业务后果的保障；已确认退出的行为同步移除断言和登记，写法变化则保留原缺陷检测能力。
- 从实际行为、失败后果和调用者选择已有 pytest 文件/节点；已有保障足够就复用。共享计算、身份、存储/事务、配置/启动或影响不明时扩大；提交、新删件及已有 dirty 本身不触发全量。
- 金额、身份权限、写入、回滚、迁移、共享出口及严重缺陷保留有效回归。先确认专用测试目标与实际 engine；无法确认时停止对应写入验证，继续不依赖它的工作。模拟接口浏览器只证明交互，不证明数据库写入。
- 原始 pytest 退出码、实际选集、失败节点和未验边界是运行证据。默认不生成四态、不自动选集、不扫描广泛输入哈希或复用跨运行通过缓存；历史判据报告仅按需追溯，不能证明当前完整通过。
- 证据只在内容、输入、环境、选择和预期仍相同且足够时复用；变化则复验受影响范围。未执行、未知、超时、空选择和非零结果不能报通过；保留首次失败并区分产品、测试和环境问题。
- 语法/字节钩子保持；文档审计、链路/覆盖提示及变异只在对应调查或风险需要时显式使用，不维护日常变异登记。39段真机与壳快照仍仅用于现场、部署验收或明确需要，不访问未经授权的业务目标。

## 五、重构与跨会话接续

`[用户·2026-10-12]` 已按原约定启动的重构保持原仓串行、不建clone/worktree、不派子代理及原批次授权；历史可从本文件Git追溯。
`[用户·2026-10-13]` 本次接入将通用执行方法归个人维护源；新明确采用的effort按技能判断自做或动态分派，不自动更改既有任务。用户对某任务的具体串行或隔离限制优先，创建子代理仍先读取个人模型规则。

新effort沿用Matt的澄清、规格和拆票方法，具体输入读个人“输入与分批接续”；规格和票记录累计评审起点及授权批次。批次交付与整个effort完成按各自验收判断；普通改动仅引用对应章节，不自动进入effort循环或最终双轴。

**技能定位**：按当前宿主提供的真实入口或 Skills Manager 登记来源定位技能，核来源、所属资源与固定版本；同名技能分别按用途定位，不在本仓复制正文。个人方法来自 lysyscy/My-Skills，Skills Manager 管理中央库与已选择的 Agent 部署。源发布与实际安装分别核验；只读检查不更新或部署，维护与同步按当前明确授权执行。Matt 原版、票字段、业务口径和项目配置保持各自主人。

## 六、专项迁移与项目例外

[用户·2026-10-15] 整体清单确认后要求推进至完成；现行协议、工程正文、产品需求与状态已实际迁入标准位置，旧薄入口退役。目录决定与来源清单见docs/adr/0033-document-layout.md；历史原文与SHA从docs/archive/index.md追溯。

| 保留范围 | 实际契约与读取方式 | 退出条件 |
|---|---|---|
| 现有TAIL票仓 | 已采用的本地tracker权威；原票状态与Comments保持，索引在docs/status.md §15，历史短索引在docs/archive/tickets/index.md | 保持tracker协议，实际票仓已迁至.scratch/tails/issues；切换tracker另行处理；新任务规格使用.scratch，不另造票状态 |
| 已有D件 | 长期来源与编号在docs/adr保持；现行消费指针在既有索引更新，新决定使用docs/adr | 来源继续保存，按具体冲突读取，不默认加载全部旧裁定 |
| 项目约束与文档审计 | 用户已确认退出CodeBuddy项目接入；约束在docs/agents/project-rules.md，审计在docs/guides/document-audit.md与tools/audit | 已撤销两份宿主指针；本次不更新已安装技能 |
| delivery第三方原件与实际运行资源 | 检查、历史对账和运行模块的真实输入；现行产品Markdown在docs/requirements | 真实程序或来源契约完成切换后再单独处置，不因文档统一搬动正在运行服务的资源 |
| 运行数据与开发输出 | var按data/state/cache/log/tmp/backups分工；用户原件data/source、成品exports、分发包dist；实际绑定和恢复见docs/guides/work-records.md | 当前消费者已切换；历史旧路径按迁移清单查新地址，不保留双写入口 |

普通任务只搜索现行资料、当前effort和直接依赖；历史只有明确追溯才读。恢复仅还原本批拥有的路径，遇到后续新内容保护双方。当前目录与命名回README.md，资料生命周期回docs/guides/work-records.md。

本仓沿用Python组件契约backend/app、backend/tests、backend/alembic及backend/app/resources，不为统一改包路径；第三方素材delivery沿其来源契约。历史判据结果、旧回执和壳基线仍在var/state/verification；本轮仅退役其生成/复用义务，不清理旧证据、原件或壳基线。壳基线只迁字节，不重新盖章；现存差异按原结论处理。

开发工具共享tools/audit/workspace_paths.py：默认effort为checks-当天、run为时间与PID，子进程沿用MTRL_RUN_ID；只由创建轮次的父进程收尾。输出按kind生成；进程退出释放work，保留实际核验输出至同effort本机归档（首次创建的期限不随新运行延长）。Agent手动运行使用MTRL_EFFORT/MTRL_RUN_ID指定本轮身份时由Agent自己结束run，并从实际安装的setup-solo-workflow/scripts/workspace_check.py运行run-closed/closed；检查本身不会代替删除。凭据和原件不得进入工具输出。

Codex宿主提供的用户附件固定在.codex-attachments/，作为本机原始输入忽略Git；不覆盖、不在任务收尾自动删除，正式采纳为长期数据时再按data/source的原件契约处理。
