# Agent 读取入口

共享记忆按宿主统一自定义指令执行；本项目固定库为 `project-3379fef93fbada35`，逻辑身份和普通业务/开发分流见 [工作流绑定](docs/agents/workflow.md#共享记忆)。记忆不能替代当前规则或授权。

按当前动作读取下列主人及其必要源码。接手活动工作先从 [status](docs/status.md) 到原规格/票，核所在分支、工作树及实际进度。

| 当前动作 | 先读 |
|---|---|
| 开发实施、工程验证、提交或开发环境操作 | [项目工作流](docs/agents/workflow.md)，实施开工先读“够用即止” |
| 开票、领票、改状态或依赖 | [票协议](docs/agents/issue-tracker.md) |
| 改业务、金额、归属或权限 | [当前需求](docs/requirements.md)中的相应主题 |
| 改共享结构、写入/撤销或刷新链 | [架构](docs/architecture.md) |
| 改界面与文案 | [前端设计](docs/guides/frontend-design.md)；旧壳机制再读 [旧前端参考](docs/reference/legacy-frontend.md) |
| React 构建、启动、更新、核验或退出预览 | [预览指南](docs/guides/frontend-preview.md)与活动规格；先核在用资源与目标 schema |
| 运行开发工具、选择检查或排查隔离 | [开发与验证](docs/guides/development-and-verification.md) |
| 配置、启停、部署或服务加载 | [部署](docs/guides/deployment.md)；恢复再读 [备份](docs/guides/database-backup.md) |
| i8 调用、探测或解析 | [i8 契约](docs/reference/i8-contract.md)与既有封装 |
| 集采付款方式/账期接口 | [共享契约](docs/reference/jc-payment-contract.md) |
| 模板生成、字段映射与导出 | [模板导出](docs/reference/template-export.md) |
| 文档维护或专项迁移 | workflow 的个人方法入口；实际安装的 writing-for-agents |

凭据和真实业务原件保持受保护；真实服务、外部写入与业务数据操作按当次授权。独立 React 工作树的改动及索引由其任务持有，公共票号由指定整合者串行分配。
