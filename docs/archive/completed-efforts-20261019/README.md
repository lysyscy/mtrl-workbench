# 2026-10-19 过程资料归档

本批按用户明确授权处置；原始文件保持字节，原文中的“当前”“未结项”和路径均属于当时语境。迁移前仓库HEAD为2da4c94，存在其他未提交修改，本批没有整仓保存。逐文件旧路径、新路径与SHA-256见[manifest.json](manifest.json)。恢复只处理清单内路径，原位置有新内容时先保护双方。

| 来源 | 处置及现行主人 |
|---|---|
| 六项问题只读审查 | [原文](legacy-six-issues/review-20261010.md)；R1/R2/R5已由4ddcfd5实施，R3/R4/R6分别由TAIL-282/284/283落实。真实规则归说明书、MOD-01/03/05/07/11及对应实现；本件只保留问题和原建议的证据链 |
| business-skill-deployment | [原文](business-skill-deployment/spec.md)；长期维护入口已在各技能references/maintenance.md，运行源在本项目skills及各业务项目，不再依赖本effort。部署数字是当时快照，当前集合向Manager查询 |
| payment-plan-workflow | [原规格](payment-plan-workflow/spec.md)及交付调查原文；2026-10-19新授权允许退出活动资料区，不代表实体第二台电脑或真实业务写入已验收。现行业务归说明书§4.3、MOD-04及skills/payment-plan-audit，运行资源和交付包保持原位 |

共42项旧路径：14份Markdown保留在此，28项JSON输入/快照/回执映射至本机.artifacts/recovery/effort-archive-20261019/payment-plan-workflow；其中before.json与preflight.json完全相同，只存一份并保留两个恢复映射。未把业务快照、25MB开工字节基点或本机恢复输入提交Git。JSON不是运行依赖，保留用于恢复既有清理、验证和发布依据。额外生成的重复保护ZIP已在逐件核SHA后移除。

原表、skills源码、resources/audit-runtime.zip、artifacts/payment-plan-audit.skill、业务流程tools和仍在使用的.skill-releases均保留。未重跑机械费旧目录删除，未重启、迁移数据库、访问i8、付款或打印。

依赖检查覆盖源码、维护说明、测试、打包器、同步器、随包ZIP及5个真实安装目标，共206个文件/压缩成员，无两个effort路径引用；归档后再次运行相同扫描及34项隔离测试。具体测试结果、归档原因审计与尚保留旧设计的逐项判断见docs/archive/handoff-reminder-repair-20261019.md。
