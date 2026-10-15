# TAIL-337: Python315PG18及依赖升级

**What to build:** Python315PG18及依赖升级

**Blocked by:** 备份及候选环境核验通过再切换

**Status:** done

- [x] uv管理的Python3.15、PG18.6、Node24.21、Git2.56及全部最新稳定兼容依赖实际加载；旧项目环境清理，保留有效数据备份。
- [x] 两库逐表数据、序列和迁移版本核验，真实服务探活及隔离回归通过；部署入口与精确/哈希锁一致。

---

## Comments

**2026-10-14 · 建票（agent）。** 来源：用户2026-10-14明确要求升级全部运行环境和依赖并清理旧版本｜不做会怎样：继续运行旧依赖和PG16，无法达到指定升级目标｜落点：backend/requirements.txt与ops部署入口及本机环境｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：目标明确；跨大版本必须验证恢复与兼容；单批集成；不扩大业务功能

**2026-10-14 · 升级、备份与加载。** 用户本轮明确授权Python3.15（复用已有uv管理解释器）、PG18.6、Node24.21、Git2.56及全部最新依赖，按单批普通模式实施并扩大实际共享风险验证。正式venv为Python3.15.0，uv0.13.1；PG18.6/Node24.21.0/Git2.56.0.windows.2已加载。77包精确锁及哈希锁一致，uv同步干跑无变化，官方PyPI查询outdated=[]。既有镜像缺FastAPI0.143.1与pydantic-settings2.16.0，按最新版本目标改为单一官方源；仍保留HTTPS、单源、venv副本及哈希保障。

两库逻辑备份及角色保存在`D:/backups/mtrl-workbench/runtime-20261014`（限制访问）。pg_upgrade检查先遇Windows受限目录权限，补当前用户权限后仍在本地连接阶段停顿；限时停止，未作生产数据迁移，原失败日志保留。改用PG18临时50433端口恢复两库和角色，逐表行数/内容SHA256/序列一致后切到5432。业务35表23591行，测试35表10553行，两库各31序列；原SCRAM规则、角色口令和排序保留。全量回归后生产表及序列仍一致，已重建统计。PG16旧服务及旧安装/数据、项目旧venv和候选venv已清理；WorkBuddy正在使用的共享Python保留，不清其他项目运行时。回执=`.codebuddy/work/00-scratch/tmp-20261014-runtime-upgrade/runtime-receipt.json`。

**2026-10-14 · 验证。** 新环境完整pytest1760项：1755通过、5失败，原非零完整日志=`.codebuddy/work/00-scratch/tmp-20261014-runtime-upgrade/full-pytest.log`，原结果=`full-acc.json`。失败为旧“禁止官方源”规则1项及新版CORS合法合并Origin导致的Vary字符串断言4项；保持实际保障调整测试后，相关两文件10项通过（含新增安装源缺失/HTTP/多源拒绝），结果=`compatibility-acc.json`。复用其余同环境/代码未变的1755项，不把原全量非零改称全绿。PDFRenderer真实新版浏览器156.0.8078.4生成19886字节样张=`render-smoke.pdf`；未出纸、未登录i8或做真实业务写入。pip check通过；77包pip-audit无已知漏洞，报告=`pip-audit.json`。服务自检Running/Automatic、GET /app200、35表、模板指纹及端点通过；真实人工导入仍跳过。PS语法及路径、部署DryRun、doc/syntax/bytes/claim通过。

`_run_rulers --explain`对版本文件、哈希锁和运维入口仍报待查，未冒称入口通过：实际消费者分别为uv版本发现、uv哈希同步、pip/uv单源及副本、NSSM服务依赖、server_ctl PG18状态、deploy_restore首次安装。已按这些消费者核真实加载、拒绝保护、锁无差异、PS解析和DryRun；不是修改选择器以消除提示。新机真实安装、实体打印、日常备份链/异盘校验及现场日志访问限制未验；本次两库真实逻辑恢复已证明。
