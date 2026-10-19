# 当前工作区固定目录迁移

用户2026-10-19授权：按My-Skills已发布aab574c固定目录契约整理当前mtrl-workbench，重点是artifacts、.artifacts、.scratch/local。先核真实依赖，修改实际消费者与规则，已结束材料选留归档或清理；保护运行数据、用户原件、活动工作和已有dirty。不推送材料工作台，不维护或同步个人技能。

范围包括运行路径、验证结果/回执/基线、一次性文件与恢复现场的分类及必要迁移；票仓、业务定义、有效技能与运行模板不因目录统一重排。涉及运行服务切换时先核现场及权限。

验收：旧位置无未说明活消费者；新入口实际读写正确；原件与运行数据指纹守恒；原有修改被保留；相关正反测试、规则/工具引用检查和正常提交检查通过；剩余例外写具体内容与退出条件。迁移工具只处理本批清单，拒绝覆盖和越界；完成后归档必要结论并退出本活动目录。

## 已确认迁移清单（2026-10-19）
用户确认整体方案并授权受控停启 mtrl-workbench-server；不写业务数据、不推送本仓。

| 原位置 | 类型及真实消费者 | 目标及处置 |
|---|---|---|
| artifacts/i8_cookie | cookie_store 动态凭据 | var/state/i8_cookie；原字节迁移，不复制进证据 |
| artifacts/import_preview | preview_store token 状态，无自动过期 | var/state/import_preview；全部保留 |
| artifacts/import_profiles.json | ProfileStore 导入映射记忆 | var/data/import_profiles.json；唯一实例保留 |
| artifacts/i8_source | source_cache 离线含透视导出的源 Excel | var/data/i8_source；全部保留 |
| artifacts/i8_warehouse、.sigcache | 可重建运行缓存 | var/cache/{i8_warehouse,signatures}；本轮先保留 |
| artifacts/exports、pdf | 业务导出 | exports；保留现有成品，不覆盖 |
| artifacts/hist_supplement/source、_diag | 用户原件和现场输入 | data/source；核消费者后迁移 |
| artifacts/acc_results、回执、pytest输入、变异台账 | 验证持久状态 | var/state/verification；不刷新成功证明 |
| .artifacts/recovery/backups/*壳单文件基线 | shell_verify 真基线 | var/state/verification/shell-baselines；字节不变 |
| 数据库日备份 | backup_databases 与计划任务 | var/backups/databases；同批修实际任务和默认值 |
| artifacts/payment-plan-audit.skill | 在用分发包 | dist/payment-plan-audit.skill；核维护脚本及说明 |
| logs | Python 日志与 NSSM stdout/stderr | var/log；停服务后迁移并改宿主配置 |
| 活动前端证据 | 并行前端任务 | 保持其固定输入与工作基线，具名暂缓 |
| .scratch/local 源码快照 | 旧 impactscope 字节基点 | 逐份核 Git 可恢复内容，独有差量压缩留恢复依据；可恢复的重复正文删除 |
| 旧验证目录 | 测试输出、一次性代码及恢复副本 | 核完成证据后选留最小有限原始证据，释放可重建临时物；未知项不擅删 |

新开发验证输出按 .artifacts/active/<effort>/<run>/<kind> 生成，运行结束退出 active；临时 API 自动释放。必要证据按有限期限选留；现行文档与机器扫描、签名、选测、忽略策略同行。
