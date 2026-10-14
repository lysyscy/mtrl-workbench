# 既有方法接入记录

源：旧README的开发入口段，基线 `7c37f89b3787a053e87debfa70dac768c2ffe846`。按当时发布与接入情况解释；当前方法来源回docs/agents/workflow.md。

### ①之补 开发入口

TAIL-330–334已完成内部方法消费、按需能力选择、只读分流、依赖定位与重启授权接合。个人包1bc23a4已发布且Skills Manager同步完成，Codex/CodeBuddy/WorkBuddy实际资源核对通过；累计验证、一次双轴审查及未验边界回TAIL-334 Comments。全局只保留能力发现触发原则，外部原版与生产服务保持。

个人工作流已通过AGENTS.md接入：普通改动、按票接续、子代理配置和资料维护按条件读取个人技能，本仓继续持有业务、票源、目录、测试与授权绑定。现由Skills Manager统一部署到Codex、CodeBuddy、WorkBuddy，完整维护源与部署绑定回docs/agents/workflow.md；安装衔接和真实发布同步证据回TAIL-324，首次接入证据回TAIL-320。既有业务待办和运行版本分别按本页与主计划判断。

开发与核验按 `docs/agents/workflow.md`，命令见 `docs/guides/development-and-verification.md` §十一。当前能力见主计划 §0.3；运行服务和本地代码的差别见本节开头。资料迁移与历史治理演练的证据从已销号票索引按需追溯。

