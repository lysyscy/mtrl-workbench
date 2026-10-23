# 开发工具入口

按实际任务使用对应命令，先读源码/--help确认输入、输出和副作用。脚本在场不构成真实业务写入或删除授权。

| 用途 | 入口与边界 |
|---|---|
| 暂存语法、字节与凭据保护 | audit/syntax_audit.py、bytes_guard.py，由真实pre-commit调用 |
| 旧壳源码与语义读取 | audit/shell_source.py、shell_api.py；共享读取不因index拆件失效 |
| 运行输出与生命周期 | audit/workspace_paths.py、audit_work.py；只处理本任务拥有产物 |
| 开、关、列票 | oneoff/_tail_open.py、_tail_close.py、_list_tails.py；协议见docs/agents/issue-tracker.md，默认干跑 |
| 疑似未调用公共定义 | audit/wiring_audit.py，只保W2候选提示，不自动判缺陷或删代码 |
| 已有业务反例 | mut对应当前靶；先核隔离，再按实际风险显式运行，不作日常全量义务 |
| 浏览器/i8专项探测 | probe对应入口；真实登录、抓取、打印按当前明确授权 |

oneoff保留仍有迁移/诊断/分发用途的入口，例如_jc_payment_terms.py默认只读，真实回写另需确认摘要与授权；不能为证明历史结束而执行迁移。历史工具通过Git取回，不保归档目录或变异覆盖账。新的一次性脚本放本轮.artifacts的work，结束释放；不为同义检查建通用治理平台。

命令、隔离及产物路径见docs/guides/development-and-verification.md，服务/备份脚本在ops。
