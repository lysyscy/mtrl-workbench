# TAIL-382: 人工推荐不依赖全台账装配，批量预览不逐条查询通知书和关联

**What to build:** 人工推荐不依赖全台账装配，批量预览不逐条查询通知书和关联

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 推荐只读候选发票一次，批量预览查询次数不随通知书条数增长，候选范围共享读取。
- [x] 全项目序号、跨项目当前关联、推荐金额、原关系保护及确认重新读取和锁定保持。
- [x] 在已确认专用测试库验证并回滚，完成分层检查、资料同步与本地保存，不写生产或i8。

---

## Comments

**2026-10-20 · 建票（agent）。** 来源：用户2026-10-20明确要求完成架构候选B和C｜不做会怎样：编排知识与事实读取散在调用者，后续修正容易漏路径｜落点：backend/app/mod11_jc、mod03_notice/service.py及推荐与批量预览回归｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：范围已授权；复用既有实现；分项验证；不改业务规则

**2026-10-20 · 实施范围。** 用户明确要求剩余B/C均实施，固定起点5d65aff、工作区干净；本票限定原报告对应区域，技术选择由Agent完成，不改业务口径、不扩为前端框架或通用数据层，不部署、不重启、不写生产。推送沿TAIL-380的自动审批受阻状态，当前没有向具体origin/master推送的新确认，不重试或绕过。

**2026-10-20 · C实施与验证完成。** `_link_candidates`按请求批量取得通知书、项目、合同与既有关联，全项目合同集派生序号，再逐条产出每份通知书的候选，避免把整批候选同时复制。人工推荐只读所选候选的发票和付款一次，关联通知书也按id批量读取；移除对build_list全台账装配和全量通知书的依赖。通知书批量出口复用mod03既有repository，经service暴露，不跨包查表；无新增依赖、配置或通用数据层。推荐证据和唯一匹配仍各自判断，确认重读应付及锁定重读通知书的流程未改。

- 写入验证前按Settings与TestDatabaseGuard确认专用目标127.0.0.1:5432/mtrl_workbench_test，运行时夹具再次核engine；rollback_db包住测试写入并在结束回滚，无生产或i8请求。
- 旧实现先红：`tests/test_candidate_reads.py -o addopts= -q --tb=short`退出1，两项均暴露问题；候选发票读取2次，批量从1条增到24条时SELECT从5增至51。最终测试分别断言候选发票只读一次、只带候选合同id，且24条与1条查询次数相同。
- 第一轮与最终逐条产出版本分别运行 `tests/test_candidate_reads.py tests/test_jc_link_recommendations.py tests/test_jc_auto_link.py tests/test_acc_jc_pay_link.py tests/test_layering.py -o addopts= -q --tb=short` 均退出0、37项通过。再补跨项目当前关联、缺失/重复/空输入回归单独退出0；最终C共38项。
- 与B的最终累计命令/完整选集见TAIL-381 Comments，同一最终输入91项退出0（78.70秒）。涵盖无预选、全项目稳定序号、发票证据/日期排序、统计付款0与其他通知书及手工付款保留、换合同前金额基准、只补空缺、预览后来源变化跳过、重复确认和分层。
- 现行结构同步docs/architecture.md；B已本地提交41a5eac且真实提交钩子通过，临时缺pin副本已释放，原始失败日志按既有output器限期归档。未跑全量pytest、真实业务写入、真实i8或服务重启；推送仍沿TAIL-380自动审批限制，未尝试重推。资料按writing-for-agents与现有主人维护，未新建第二份术语表或ADR。

**2026-10-21 · 收尾。** 两票已按工具销号，doc_audit退出0且必须修0；全部改动字节检查和git diff --check通过；workspace_check closed退出0。临时副本已退出，必要日志/截图由现有输出器限期归档，无活动effort遗留。最终累计91项通过证据有效，以下本地提交执行真实钩子；推送及运行加载仍未执行。

**2026-10-21 · 获准推送与重启完成。** 用户明确授权本次所有提交推送到本人GitHub私库lysyscy/mtrl-workbench的master后重启服务，替代此前待具体目的地确认的状态。

- `git push origin master`退出0，普通快进a47a652..bad703d，含6bf8291、5d65aff、41a5eac、bad703d四个提交；`git ls-remote origin refs/heads/master`与本地HEAD同为bad703ddbad24ce538bfce05202adc8150882bff。
- 重启前核NSSM指向本仓backend/.venv/Scripts/python.exe，工作目录backend，启动参数为uvicorn app.main:app、8000端口；lifespan仅装配日志，无启动迁移。本轮无依赖、配置或数据库结构变更。
- 使用现有`ops/server_ctl.ps1 -Action restart -WaitSec 30`，退出0。00:05:09新应用启动完成，服务Running；NSSM进程31040→32656，应用进程28668→14684，正式虚拟环境入口仍在本仓。
- 重启后只读核验：`/healthz`和`/app`均200，health状态ok；/app包含本次layoutTables调用。`/static/shell/`的core.js、actions.js、proj.js、view.js均200且响应字节与仓库对应文件完全相同；最新启动日志Application startup complete，无本轮启动错误。
- 源码未变化，复用最终累计91项通过的证据；本次只追加部署记录，不重跑全量pytest。未执行真实i8抓取、实体打印或业务写入，不将服务健康核对当作真实业务验收。当前状态和历史短索引同步，最终文档提交随后沿同一授权保存并推送。
