# 接口取数版本 · 2026-10-15

用户确认：skill主线认可；同金额付款提示简写“已付同金额”；改为系统接口取数，局域网另一台电脑无需数据库连接配置。系统付款计划继续保留。

当前已实现：GET /api/m03/plan-audit/snapshot，正常系统登录且账号在用才能获取全部月份通知书、全部项目、全部有效付款及日期；服务器使用REPEATABLE READ只读事务，不访问i8。POST /api/m03/plan-audit/methods保留已确认预览SHA、源SHA、系统指纹、单据唯一性、归属、原拟方式、审批及生效已付校验；先整批校验再更新通知书planned_pay_method，不登记实际付款。客户端通过系统会话调用接口，不能直连数据库；不保存密码、不自动跟随携带凭据的跳转、不自动重试不确定写入。

客户端：只需完整skill、Python/openpyxl、系统网址及正常登录；纯规则随resources/audit-runtime.zip分发，从工作台真源生成并检查manifest，不引入SQLAlchemy、core.db或.env。--repo仅为开发规则入口；不能恢复本机数据库取数。首次remote.py隐藏输入密码保存会话，后续audit.py自动使用；原表及备份在本机处理，离线snapshot需明确旧快照。付款方式回写仍须逐单预览获用户确认，本轮未执行。

原表：桌面原文件第4、77、78、79行已改“10/12已付同金额”或“10/13已付同金额”；沿用此前系统快照，没有声称新核对事实。117通过、4本月已付、22待核、2汇总差异；264公式及缓存、原业务单元格XML、打印区域、其他4张业务表保持。写后SHAb4185b9b62497f562ca67d1a753f9dfcb250b24ddfdb5c2c7a707d2a80f04274；写前完整备份20261015-182643-b78ee1a04e26，见same-amount-original-20261015/verification.json。

验证：97项定向pytest通过，覆盖规则/格式保护、HTTP登录与Cookie、会话失效、账号停用/删除、伪造会话拒绝、无凭据重定向、预览及金额拒写、批次原子性、Windows预览字节SHA和回执、既有付款默认及会话行为；remote-acc.json及remote-pytest.log。真实表副本通过模拟HTTP接口跑完prepare、AI映射复用、核对标注，客户端未提供仓库参数或数据库配置，见portable-http-smoke/verification.json；这不是实体第二台电脑验收。

实际服务器只读取数函数验证：2026-10-15T18:30:39+08:00捕获1178通知书、20项目，快照完整，未写数据库；server-api-read-verification.json。已部署Codex脚本用该快照和随包规则执行prepare成功，未传--repo、未改原表。加载前正式服务/app=200、接口404、列不存在；后续已按用户同意完成加载，现状见下段。

安装：Skills Manager保持ID877236e1-3546-485f-a2be-2114add22a3d和Codex部署，已update；源、中央库、真实部署10个md/py/zip文件逐项SHA相同，见remote-install-verification.json。package/payment-plan-audit.skill为完整可携带压缩包，无数据库连接、会话、密码或本次业务快照。

检查：syntax、bytes、wiring、chain及git diff --check退出0。doc_audit仍由既有T18仓外归档根D:/dev/.归档-mtrl不存在和_doccheck素材包1103/1104计数差阻断，没有修无关归档或报全绿。代码已落盘，未提交/推送；已有并行dirty保留。

用户后续明确回复“同意同意”，授权备份、字段迁移和服务重启。本轮已完成：

- 备份两库到.artifacts/recovery/databases/20261015-184346-28232c22；两份custom归档均校验SHA、非空TOC，未做本次新归档恢复演练。
- 停止正式服务后取得业务基线，通过Alembic将业务库迁移至c350261015，再启动服务。34张业务表23621行（不含版本表）原有列逐表行数与内容SHA一致，新planned_pay_method为VARCHAR(32)、NOT NULL、默认空，非空值0。
- 隔离测试库同步同一迁移，34张业务表10663行原有列摘要一致，新拟方式非空值0；两库原有付款流水和金额未改变。
- 正式服务Running，新服务进程9828，/app=200；用Edge已有正常登录打开GET /api/m03/plan-audit/snapshot，2026-10-15T18:45:24+08:00返回完整1178通知书/20项目，新字段可用。没有提取浏览器Cookie、读取账号密码或签造生产会话。匿名与无效Cookie的GET及匿名POST /methods均401；真实通知书列表接口200且拟方式字段全部为空。

记录见production-load-20261015/backup.json、migration-verification.json、test-migration-verification.json、live-http-verification.json、notice-list-verification.json。skill和原表本轮未再次改动，源码未提交/推送；未执行拟方式回写、实际付款、打印或i8，未在实体第二台电脑验收。
