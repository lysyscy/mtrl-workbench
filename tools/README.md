# 开发工具入口

按实际任务使用对应命令，先读源码/--help确认输入、输出和副作用。脚本在场不构成真实业务写入或删除授权。

| 用途 | 入口与边界 |
|---|---|
| React 性能测量/原件口径检查 | dev/frontend_measure.py；小样筛查后完整84组，复用在用只读预览；见docs/guides/frontend-preview.md的性能测量入口 |
| 后端隔离pytest | dev/backend_verify.py；明确来源配置及backend内测试节点，独占临时schema、退出码/清理日志；见开发与验证指南 |
| React 验看与失败截图 | dev/frontend_capture.py；对已存在预览页采集截图和身份JSON；React失败自动截图与按需截图fixture共用，不创建服务或写业务数据。 |
| React 真实副本预览/复制及历史冻结样本 | dev/frontend_preview.py（运行与排他实现在同目录server/runtime模块）、frontend_preview_copy.py；操作与目标保护见docs/guides/frontend-preview.md |
| 暂存语法、字节与凭据保护 | audit/syntax_audit.py、bytes_guard.py，由真实pre-commit调用；--staged只检查Git index，显式无参数保全量模式，Git失败非零 |
| 旧壳源码与语义读取 | audit/shell_source.py、shell_api.py；共享读取不因index拆件失效 |
| 运行输出与生命周期 | audit/workspace_paths.py、audit_work.py；只处理本任务拥有产物 |
| 开、关、列票 | oneoff/_tail_open.py、_tail_close.py、_list_tails.py；协议见docs/agents/issue-tracker.md，默认干跑 |
| 疑似未调用公共定义 | audit/wiring_audit.py，只保W2候选提示，不自动判缺陷或删代码 |
| 已有业务反例 | mut对应当前靶；先核隔离，再按实际风险显式运行，不作日常全量义务 |
| 浏览器/i8专项探测 | probe对应入口；真实登录、抓取、打印按当前明确授权 |

oneoff保留仍有迁移/诊断/分发用途的实际入口，副作用以各脚本为准；真实回写另需确认摘要与授权，不能为证明历史结束而执行迁移。历史工具通过Git取回，不保归档目录或变异覆盖账。新的一次性脚本放本轮.artifacts的work，结束释放；不为同义检查建通用治理平台。

命令、隔离及产物路径见docs/guides/development-and-verification.md，服务/备份脚本在ops。
