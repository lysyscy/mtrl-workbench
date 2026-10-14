# 材料报表自动化工作台 · Agent 读取入口

接手从 `README.md` §〇定位当前状态与任务；实施或按票接续再读 `.codebuddy/plans/开发计划-主文档.md` §0、§13.6 当前交接与 §15 相关票。`.codebuddy/memory/MEMORY.md` 的凭据与操作边界宿主未注入时手动读；其余资料按下表取当前动作命中章节，只读调查不展开实施收尾。

目录职责、分层和命名由 `README.md` 持有；本件只维护读取指针。

首次使用个人方法时，读 `docs/agents/workflow.md` §一定位实际来源和本次需要的资源，按当前授权区分只读与维护；不因新会话自动同步。复盘个人方法或获准维护个人包时使用所列 improve-workflow。运行中任务沿用固定规则与授权基线。

实施、核验、保存或按票接续时，读 `docs/agents/workflow.md`：§一是输入和个人 execution 参考，§二是提交推送，§四是验证接线，§五是既有采用与接续限制。跨批统筹仅在明确采用时读取 coordination，创建子代理前读取 delegation；实际参考定位回该页 §一。

生成或修改文档时，按 workflow §一定位个人 document-maintenance；选择目录或专项迁移时分别读取 document-layout、document-migration。项目迁移决定见 `docs/adr/0033-document-layout.md`；未迁部分按 `docs/guides/document-governance.md` 与 `.codebuddy/work/README.md` 的既有落点操作。


| 当前动作 / 要判断的事 | 读取位置 |
|---|---|
| 查本仓输入、核验绑定、拆批记录、提交推送 | `docs/agents/workflow.md`；运行命令见 `docs/guides/development-and-verification.md` §十一 |
| 开票、领票、销号、判断依赖或状态 | `docs/agents/issue-tracker.md`；活跃索引见主计划 §15；标签见 `docs/agents/triage-labels.md` |
| 改业务行为、字段含义 | `delivery/材料科业务全流程说明书.md`、`delivery/PRD/` 对应 `MOD-*`；领域资料用法见 `docs/agents/domain.md` |
| 改界面或处理显示、交互报障 | `docs/guides/frontend-design.md` §0 → §9 |
| 写上屏文字 | `.codebuddy/work/40-decisions/D29-文案审计口径-以熟手为准.md` |
| 改壳适配、监听、重画或共享调用 | `docs/guides/development-and-verification.md` §十 / §十五 / §十六 |
| 涉及打印、主题、历史数据、配置出口、模块搬运或判据 | 先取 `docs/guides/implementation-constraints.md` 标题，再读命中小节；业务含义回 `delivery/` |
| 改工具脚本、处理编码或文件操作 | `docs/guides/implementation-constraints.md` §廿三、`tools/README.md` 对应项 |
| 碰环境、起停、部署、架构或模块分工 | `ops/README.md` 索引 |
| 查硬数字的依据 | `docs/reference/thresholds.md` |
| 推翻既有决定、追溯当初原因 | `.codebuddy/work/40-decisions/` 对应 D 件 |
| 找资料、检查读取范围或历史位置 | `README.md` §三 → `ops/README.md`、`.codebuddy/work/README.md` §六 |
| 建文档、归档、删件或调整文档结构 | `docs/guides/document-governance.md` |
| 整理重复、过期或难以定位的文档 | `.codebuddy/skills/docs-audit/SKILL.md`；写 Agent 文档时使用实际安装的 writing-for-agents，定位见 workflow §五 |

凭据与生产数据边界见 `.codebuddy/memory/MEMORY.md`；真实 `.env` 不提交，钩子见 `ops/hooks/pre-commit`。
