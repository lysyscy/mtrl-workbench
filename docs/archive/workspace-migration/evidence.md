# 迁移交付证据（2026-10-20）

开始于2026-10-19，完成于2026-10-20。范围及分类回本目录README和spec；现行职责仍由仓根README、workflow和work-records持有。

- 实施提交：ea2b65bc5c2c931816d8e471155c771ef51404f4，135个明确路径/可分离差异，真实pre-commit语法、字节及凭据检查通过。既有dirty和未跟踪资料保留；共享路径窄补丁基于修改前工作区，仅供逐项核对，不直接对新HEAD整包应用。
- 7,153个运行/恢复文件逐项核SHA；2份Cookie、7,009份无到期契约的预览、映射及i8源文件保持原字节。两份临时测试冲突XLSX已确认只差docProps/core.xml，删除测试副本，原运行字节保持。
- 原artifacts、logs、.scratch/local及.artifacts/recovery均实际退出；本次effort与run也已退出活动目录。已安装workspace_check的run-closed、closed均返回0，回执在本机有限归档。
- 69份原源码快照1.63GB压缩为约24MB的Git/原行尾引用及独有字节；其他重复/可重建中间物清除后，独有恢复包约74MB。两包的逐项清单、SHA、恢复方法及凭据边界回README和本机manifest；不是保留整树现场。
- 活动前端审计仍保留原报告包，在.artifacts/active/frontend-visual-audit/imported-20261019/reports。用户原件在data/source、历史参考数据在data/reference、成品在exports、业务dump在var/backups；不套开发证据到期删除。
- 服务Running，GET /app和/healthz均200；NSSM及Python日志在var/log。最新已迁备份通过SHA及pg_restore目录验证；未做完整恢复。定时备份任务沿原调用，脚本默认输出var/backups/databases。
- 全量1,853项中1,852通过，唯一配置示例失败已通过删除不需要的可配项修复；未重报一次全量全绿。后续100项定向、31项消费者和34项付款技能回归全部通过，7项生命周期隔离反例通过；目录签名、选测、引用查询、语法/字节和文档审计按原始回执核实。
- 5份壳基线与15个前端源文件相对迁移前字节不变，仍有已有1,603行差异。未重新盖章消除该红项。
- 付款技能真实本地维护源为skills/payment-plan-audit；原Manager ID 877236e1-3546-485f-a2be-2114add22a3d通过官方update刷新，中央库与原codex/codebuddy/workbuddy/opencode/doubao五端的13个维护文件一致，来源、预设、标签和部署范围不变。共享未提交维护资料仍由原工作区持有，不把安装同步表述为源整树已提交。
- dist/payment-plan-audit.skill重建，9个运行成员与源一致，脱仓临时解包启动通过。未进行真实i8请求、原表现场核对、付款回写或实体打印，不宣称现场能力验收。
- 本仓未推送远端；Manager备份当前有本机变化、ahead=0，未提交或推送本次变化。此前三个个人技能的备份推送授权不扩大到本轮新增的项目技能变化。个人方法源码与安装副本本轮未修改。

本机选留48份原始回执及两份去重恢复包位于.artifacts/archive/workspace-migration/20261019-01，保留至2026-11-18。当前有效原件、运行数据、活动任务和私有配置恢复材料按各自主人及退出条件管理。
