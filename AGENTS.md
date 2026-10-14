# 材料报表自动化工作台 · Agent 读取入口

接手从 `README.md` §〇定位当前状态与任务；实施或按票接续再读 `.codebuddy/plans/开发计划-主文档.md` §0、§13.6 当前交接与 §15 相关票。`.codebuddy/memory/MEMORY.md` 的凭据与操作边界宿主未注入时手动读；其余资料按下表取当前动作命中章节，只读调查不展开实施收尾。

目录职责、分层和命名由 `README.md` 持有；本件只维护读取指针。

新会话首次使用个人方法时，先按只读检查或已授权维护分流，再按[包操作](C:/Users/Administrator/.skills-manager/skills/improve-workflow/references/package-operations.md)“新会话同步”核本机源与安装一次；本机维护源与部署绑定回 `ops/agents/issue-tracker.md` §四。用户要求复盘并优化个人工作流时使用 [improve-workflow](C:/Users/Administrator/.skills-manager/skills/improve-workflow/SKILL.md)。运行中任务沿用已采用的规则基线。

个人执行方法为 [implement-solo-spec](C:/Users/Administrator/.skills-manager/skills/implement-solo-spec/SKILL.md)：普通改动读“普通改动”与“验证与失败处理”，外部方法消费边界和当次能力发现也由该处持有；拆票或按票接续读“输入与分批接续”；创建子代理前读“模型与推理强度”，需要分派时再读“动态分派与隔离”。整个 effort 的实施循环与最终评审仅在用户明确采用时启用；采用记录和本仓绑定见 `ops/agents/issue-tracker.md` §四。

生成或修改文档、以及任务收尾时，读[个人文档维护约定](C:/Users/Administrator/.skills-manager/skills/setup-solo-workflow/references/document-maintenance.md)，按 `ops/docs-governance.md` 与 `.codebuddy/work/README.md` 的本仓落点操作。[setup-solo-workflow](C:/Users/Administrator/.skills-manager/skills/setup-solo-workflow/SKILL.md) 仅在首次接入或用户要求重新配置时使用。


| 当前动作 / 要判断的事 | 读取位置 |
|---|---|
| 查本仓输入、核验绑定、拆批记录、提交推送 | `ops/agents/issue-tracker.md` §四；运行命令见 `ops/development/开发与核验.md` §十一 |
| 开票、领票、销号、判断依赖或状态 | `ops/agents/issue-tracker.md`；活跃索引见主计划 §15；标签见 `ops/agents/triage-labels.md` |
| 改业务行为、字段含义 | `delivery/材料科业务全流程说明书.md`、`delivery/PRD/` 对应 `MOD-*`；领域资料用法见 `ops/agents/domain.md` |
| 改界面或处理显示、交互报障 | `ops/前端设计守则-以使用用户为中心.md` §0 → §9 |
| 写上屏文字 | `.codebuddy/work/40-decisions/D29-文案审计口径-以熟手为准.md` |
| 改壳适配、监听、重画或共享调用 | `ops/development/开发与核验.md` §十 / §十五 / §十六 |
| 涉及打印、主题、历史数据、配置出口、模块搬运或判据 | 先取 `ops/development/实现约束.md` 标题，再读命中小节；业务含义回 `delivery/` |
| 改工具脚本、处理编码或文件操作 | `ops/development/实现约束.md` §廿三、`tools/README.md` 对应项 |
| 碰环境、起停、部署、架构或模块分工 | `ops/README.md` 索引 |
| 查硬数字的依据 | `ops/阈值表.md` |
| 推翻既有决定、追溯当初原因 | `.codebuddy/work/40-decisions/` 对应 D 件 |
| 找资料、检查读取范围或历史位置 | `README.md` §三 → `ops/README.md`、`.codebuddy/work/README.md` §六 |
| 建文档、归档、删件或调整文档结构 | `ops/docs-governance.md` |
| 整理重复、过期或难以定位的文档 | `.codebuddy/skills/docs-audit/SKILL.md`；写 Agent 文档时使用 Matt `writing-for-agents`，技能定位见票协议 §四 |

凭据与生产数据边界见 `.codebuddy/memory/MEMORY.md`；真实 `.env` 不提交，钩子见 `ops/hooks/pre-commit`。
