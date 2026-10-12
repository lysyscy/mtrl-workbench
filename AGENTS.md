# 材料报表自动化工作台 · Agent 读取入口

接手先读 `README.md` §〇、`.codebuddy/plans/开发计划-主文档.md` §13.6 最新行与 §15 相关票，以及 `.codebuddy/memory/MEMORY.md`（宿主未注入时手动读）。然后按下表取当前动作需要的章节。

目录职责、分层和命名由 `README.md` 持有；本件只维护读取指针。

| 当前动作 / 要判断的事 | 读取位置 |
|---|---|
| 开始改动、选技能或核验范围、拆批接续、提交推送 | `ops/agents/issue-tracker.md` §四；运行命令见 `.codebuddy/memory/IDE-细节.md` §十一 |
| 开票、领票、销号、判断依赖或状态 | `ops/agents/issue-tracker.md`；活跃索引见主计划 §15；标签见 `ops/agents/triage-labels.md` |
| 改业务行为、字段含义 | `delivery/材料科业务全流程说明书.md`、`delivery/PRD/` 对应 `MOD-*`；领域资料用法见 `ops/agents/domain.md` |
| 改界面或处理显示、交互报障 | `ops/前端设计守则-以使用用户为中心.md` §0 → §9 |
| 写上屏文字 | `.codebuddy/work/40-decisions/D29-文案审计口径-以熟手为准.md` |
| 改壳适配、监听、重画或共享调用 | `.codebuddy/memory/IDE-细节.md` §十 / §十五 / §十六 |
| 涉及打印、主题、历史数据、配置出口、模块搬运或判据 | 先取 `.codebuddy/memory/细则.md` 标题，再读命中小节；业务含义回 `delivery/` |
| 改工具脚本、处理编码或文件操作 | `.codebuddy/memory/细则.md` §廿三、`tools/README.md` 对应项 |
| 碰环境、起停、部署、架构或模块分工 | `ops/README.md` 索引 |
| 查硬数字的依据 | `ops/阈值表.md` |
| 推翻既有决定、追溯当初原因 | `.codebuddy/work/40-decisions/` 对应 D 件 |
| 找资料、检查读取范围或历史位置 | `README.md` §三 → `ops/README.md`、`.codebuddy/work/README.md` §六 |
| 建文档、归档、删件或调整文档结构 | `ops/docs-governance.md` |
| 整理重复、过期或难以定位的文档 | `.codebuddy/skills/docs-audit/SKILL.md`；写 Agent 文档时使用 Matt `writing-for-agents`，技能定位见票协议 §四 |

凭据与生产数据边界见 `.codebuddy/memory/MEMORY.md`；真实 `.env` 不提交，钩子见 `ops/hooks/pre-commit`。
