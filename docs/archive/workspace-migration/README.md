# 工作区统一迁移（2026-10-19）

用户确认整体方案并授权受控停启，起点55649bbd304ec496538716202d6333656ad45c22；规则来源为My-Skills aab574c。只迁目录与修消费者，不写业务数据、不推送本仓远端。现行目录回README，生命周期与运行绑定回docs/guides/work-records.md。

## 已实际完成

- 根artifacts、logs、.scratch/local和旧.artifacts/recovery均已退出，实际旧目录不存在。
- 7,153个运行与恢复文件逐一核SHA后迁移；服务重新启动，GET /app=200。Python日志和NSSM stdout/stderr共用var/log。日备份任务调用脚本默认值，随ops/backup_databases.py切到var/backups/databases；无需另建任务。
- 2份i8凭据、7,009份无自动失效契约的导入预览、导入映射和i8源Excel均保留原字节；本轮不修改token保留语义。i8源文件包含透视对象，归var/data而非可丢弃缓存。
- 用户历史付款原表在data/source/payment-plan-history；现场诊断输入在data/source/i8-diagnostics；其余待保留工作簿在data/source/legacy-workspace。付款历史参考数据归data/reference/payment-history，现有用户导出归exports。明细及SHA见moved-files.tsv和本机runtime-moves.json。
- 活动前端审计保持原报告包及字节，归.artifacts/active/frontend-visual-audit/imported-20261019/reports；只改原任务中的路径，票内容、状态和采用基线未改。该effort仍在途，不能因本次迁移结束清掉。
- 持续核验状态归var/state/verification；权威四态未被局部测试刷新。5份壳基线原字节迁入shell-baselines，不重新盖章。新旧壳仍有1,603行差异；迁移前后15个前端文件及5份基线字节一致，属于已有差异。
- 付款skill本仓脚本的备份路径改为var/backups/payment-plan-audit；分发包重建到dist/payment-plan-audit.skill。9个成员与本仓源一致，临时解包独立启动通过；未因此宣布现场核对或付款能力验收。

## 清理与最小恢复材料

69份完整源码快照原容器共1,631,669,609字节，改为Git对象引用与去重后的独有字节；恢复包约24MB（按Git对象及原行尾重建，逐文件SHA不变）。旧目录其他重复内容按Git对象/内容摘要归并；重建性测试输出、已停隔离PG集群、隔离Git元数据、过期整树行为夹具及安装全量日志不再保留。旧业务dump仍在var/backups/manual，三份均通过pg_restore目录读取；本轮未做完整数据库恢复。

开发证据仅在.artifacts/archive/workspace-migration/20261019-01选留，retention.json限定至2026-11-18。两个恢复包保留独有字节与来源清单，不保留整棵旧工作区。发现的4组含凭据字节已退出证据包；其中2组由已有Git对象及行尾恢复，不重复留存。剩余2组旧本机配置/历史差异原字节仅在var/state/legacy-credential-recovery保留迁移回滚用途，保留窗口至2026-11-18，窗口提前关闭或凭据失效时立即处置；不得提交或复制进报告。释放562个旧链接入口，Python环境及共享Node目标未删除。

恢复时只取清单指定的单项到单独临时目录并核SHA，不覆盖当前工作区。包内manifest.json为权威：git_blob用git cat-file blob取字节，restore_eol=crlf时仅把LF还原CRLF后核原SHA；recovery_blob/blob取blobs/<sha>；private_state_blob从所列私有状态取；digest_only没有原文字节。快照容器自身可重新序列化，真正保全的是其逐文件原字节与元数据，不承诺中间JSON的空格布局。恢复包过期后不再承诺这些中间版本可恢复；原件、运行数据和必要业务dump不受此证据期限支配。

## 机器接线与实际验证

- 工具共享workspace_paths按effort/run/kind生成输出；父进程结束释放work，实际核验输出归有限本机证据，子进程沿父轮。T24拒绝旧混合根，即使.gitignore仍作防泄漏保护；T14检查未退出run、归档理由与期限。7项隔离反例通过，临时目录实际退出。
- 诊断原件进入pytest选测和输入签名；样本变化让旧证明失效，局部结果文件不反向触发pytest。项目skills源变化带出机械费回归；补齐插件和依赖源测试登记，选集覆盖检查通过。
- 全量1,853项：1,852通过，唯一失败是新增配置项未补示例；固定目录不需新增可配项，已移除该项。此后100项定向回归和31项消费者回归通过；新收尾/样本签名反例也覆盖在后续选集中。没有重复声明一次完整全绿。
- 文档审计必须修0；目录签名、选测、引用查询与生命周期反例按实际日志保存。分发包成员、原件、迁移文件、凭据与预览SHA均核对；仅运行日志、重建分发包与生成台账按预期变化。

## 保存与边界

既有dirty、未跟踪附件、四份原先已删除的任务资料及并行任务均保护。本轮不整仓暂存、重置或清理；共享文件只保存本轮可分离差异。共享未跟踪资料的路径修复继续留在原工作区，必要补丁单独保存，避免把其他任务全文纳入本轮提交。

服务加载、隔离测试、包启动及实际业务验收分别记载；未做新一轮真实i8登录/抓取、付款写入、实体打印或跨机现场验收。个人方法源及安装副本本轮未修改，沿此前已发布安装的aab574c。
