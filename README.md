# 材料报表自动化工作台

材料科内部使用的付款、材料报表、机械费与集采工作台。i8 是外部业务来源，本系统承载科室核对、统计、人工调整和报送，不替代 i8 审批。

## 从这里开始

- 改业务或查字段含义：[当前需求](docs/requirements.md)。
- 理解结构与跨域关系：[架构](docs/architecture.md)。
- 开发和核验：[开发指南](docs/guides/development-and-verification.md)；部署、服务身份和配置：[部署指南](docs/guides/deployment.md)；恢复：[数据库备份](docs/guides/database-backup.md)。
- 查在途项目：[当前状态](docs/status.md)。Agent 按 [AGENTS](AGENTS.md) 的动作入口读取。

## 仓库地图

`backend/app`、`backend/tests`、`backend/alembic` 是现有 Python 组件；运行模板与字体在 `backend/app/resources`。`ops` 放部署/服务/备份与提交钩子，`tools` 放仍有用途的开发工具，`skills` 放业务技能。实际依赖以 `backend/pyproject.toml`、`backend/uv.lock` 为准。

`docs` 只保当前知识；`.scratch` 保活动规格和票。已结束且无活动消费者的历史材料通过 Git 读取，例如 `git log --all -- <原路径>`、`git show <提交>:<原路径>`。不复制另一套历史目录。

用户原件在 `data/source`，成品在 `exports`，构建在 `dist`；`var` 下 data/state/cache/log/tmp/backups 各按运行职责保存。`.codex-attachments` 是本机用户附件。它们和忽略文件不因文档清理退出，实际模板、字体授权与 `delivery` 第三方原件保留原有消费者契约。开发产物生命周期见[项目工作流](docs/agents/workflow.md)。
