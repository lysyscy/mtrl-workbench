# TAIL-450: 已识别架构差额的后续实证与有界深化

**What to build:** 已识别架构差额的后续实证与有界深化

**Blocked by:** None

**Status:** needs-triage

- [ ] 启用研究后逐项裁定采用、保留或暂缓，明确证据和首批范围，不把已否决替换强作欠账
- [ ] 采用项先以现有隔离入口证明问题与收益，再复用成熟能力最小实施、退出旧职责并完成相关回归
- [ ] 保金额、归属、未知回执、草稿、撤销与权限契约，真实外部调用及正式切换另守授权
- [ ] 本票候选均有处理结论、真实验证与未验边界，现行文档和干净工作区同步，本地保存不自动推送

## Comments

2026-10-28 · 用户已签收原React重写并授权424退役。旧壳、读壳/语义检查及其专属反例随实际消费者退出，jslex最后的旧壳自检消费者也已退出；下列旧工具/lexer候选不再作为待实施工作。其余事务、请求内读取、读模型与纯工具隔离候选仍待本票原范围裁定，未因本次收尾启动或签成完成。

2026-10-28 · Created.


## 接续边界

用户2026-10-27要求：本轮收完后先研究新前端启用/旧端退役，把已查未做项保存为一张票。此票仅收敛架构候选，不自动开工或要求全部换库；needs-triage是等待启用研究后排序，不是所有候选已确认必须改。正式入口/退役已有TAIL-423/424主人，不在此票复制或代签。源扫描为0f169606以前本夜固定快照；接续先核最新分支/状态与本票定位。

本夜已完成的页面就绪/视觉/费用滚条/机械renderer28→0、Node/tsx、合同与Flow schema、Git index审计、付款行锁、项目history刷新不再列为待改；完整实际覆盖与独审/用户未验边界见本轮研究底稿第25节。若活动底稿退出，可从本票保存提交及原路径.scratch/frontend-architecture/research.md追溯，不另造长期报告。

## 候选与最小批次

| 优先/性质 | 精确证据与成熟能力 | 有界验收/停止条件 |
|---|---|---|
| P1：事务所有权，代码风险确证、动态收益待实证 | mod11_jc/fetch_service.py约223–230对借入Session直接rollback后继续落库；mod07_setl/api.py约319、mod08_inv/router.py约179、mod11_jc/api.py约182把外部抓取包在session_scope，core/history.py账号事务锁可能跨网络持有。复用现有mod06_proc/workbench_api.py约68–90短DB→外部获取→短DB应用；局部失败候选为SQLAlchemy begin_nested保存点，先核预flush与tracker所有权 | 只用合成隔离DB和模拟外部callback：局部同步失败不回滚调用者已有改动，账号锁/历史一致；外部等待期间不占写事务，应用阶段仍重读保护；重抓幂等/人工和调整保留/空报表不清旧值。先集采局部所有权，跨三域阶段拆分另一个子批；不能完整证明就保持明确待实证，不真实i8试错 |
| P2：同请求读事实复用，静态重复确证、收益待量化 | mod05_flow/router.py约48–64、service.py opening_views/build_debt_live/total_debt_rows：调用展开5次notice_debt_views、2次机械有效值、2次集采build_list；这是调用数，非实测SQL轮次/性能。复用本请求一次组装与SQLAlchemy现有查询，不加全局缓存/DataLoader | 同一输入原JSON逐值相等，含负/零/空、历史覆盖、待归属、集采标签和跳过、机械来源；查询/装配次数证明净收益，不声称跨表严格快照。导出与页面仍同口径；差异不清即停止 |
| P3：剩余读模型边界，弱形状静态确证 | apps/frontend/src/flow.tsx约40–44 Debt把缺金额转String；约57–60 Stats只验外壳后强转，金额/数组可能到render才报错。合同/Flow已用Valibot1.5.0纯schema+v.is，可按端点复用，不扩付款/撤销写命令 | 每次仅一个读端点，先正常实际形状及独立坏输入反例；保金额字符串/null/0/日期/额外字段、错误可重试与原输入。类型由schema推导并退出旧强转；真实形状未核或需修改业务含义则停止 |
| P4：纯工具装配，维护收益待实证 | backend/tests/test_bytes_guard.py、test_syntax_audit_exit.py、test_tail_tools.py、test_backend_verify.py前段为离线工具，但父conftest先装应用/DB。复用pytest目录作用域，仅收窄已确认四件的装配；新C1已有独立stdlib unittest，不混同其已完成 | 无配置/无数据库子进程可跑纯工具，证明不import app.main/不建engine或迁移；保原业务guard拒错库与rollback集成保护。test_workspace_paths含真实app分支，不按文件名全移；无净收益则保留 |
| P4：旧工具退役，已失效声明、执行前复核消费者 | tools/probe/_m14_parity.py、tools/oneoff/_prune_ghosts.py、_prune_ui_expected.py仍引用已退出U1/U5/expected接口，共255行；已知有效引用为backend/tests/shell_scissors.py约47自引用ALLOW，test_shell_api.py约332验证其不过期。复用Git历史恢复，退出死职责 | 先核当前tracked/真实消费者；只删除这三件与准确ALLOW，跑相关剪刀/引用检查，不执行失效脚本或新建历史归档；ui_parity/shell_verify/jslex仍有消费者不顺带删 |
| 低优先：所选付款预览范围下推，量级收益未测 | mod03_notice/notice_api_router.py约501传selected IDs，list_view.py约187–195/246–278仍载全流水/关联/留痕；现有flows_of_notices、links_by_notice可复用，但前者升序而旧全量倒序 | 先以实际量级证明收益；保None=全量、[]=空、已撤销流水及旧行序。不能只换函数造成排序/遗漏；非前端启用前置 |

## 保留/暂缓不是必改欠账

- OpenAPI生成：openapi-typescript7.13.0+隔离TS5.9.3生成、应用TS7消费技术可行已实证；本夜优先现有端点schema的净收益，未接入完整生成链。未来端点覆盖/维护收益或兼容版本有实据才重开，不把peer边界改成强制降TS/忽略peer。HeyAPI当时同有TS7启动问题，不按营销或main manifest推发布支持。
- jslex仍服务旧/app、shell_api与60个测试消费者；合法if后regex的内存反例被截断，但未发现当前壳真实使用。若424直接退役旧壳及其消费者，随责任退出比新上AST便宜；若仍长期维护且真实语法缺口触发，再核现有/成熟parser差额，不盲搬TS7不稳定compiler API。
- 六声明patch保留。picker1.14.0虽有相应上游修正，但AntD6.6.7只接受~1.12.2且有ESM变化；没有兼容证据不override或大升依赖来换“零patch”。
- 既有ReactRouter/Query、保存队列、草稿/unknown、业务撤销/金额/归属、字体/富控件测量、账号隔离、i8协议、Excel模板/透视缓存是已审视保留差额；Activity、全站ErrorBoundary、认证格式替换或统一平台没有当前净收益/兼容依据，不重新塞成待办。

## 执行与恢复

按采用子批独立本地提交；仅现有受保护测试库/可丢弃副本写测，原库只读。先确认输入/版本，复用backend_verify/唯一预览和真实失败反例，不降守卫/跳审批。业务意义、认证/权限、外部i8/打印、正式切换/迁移/合并/推送仍按当次授权，不由此票自动扩大。

每个采用项交实现/旧职责退出/验证与回退；未采用项保具体理由。P1/P2可在本票内分批，无需拆成多个无消费者规格；若确需复杂阶段规格，只建一份最小共同来源并在此引用。原扫描证据保本机task-4/backend-architecture-review、task-5/architecture-b、task-6/architecture-c.md；事实摘要已在本票，外部任务产物缺失也不要求重新全仓盘点。官方能力参考：[SQLAlchemy Session](https://docs.sqlalchemy.org/en/21/orm/session_basics.html)、[Valibot v.is](https://valibot.dev/api/is/)、[pytest conftest作用域](https://docs.pytest.org/en/stable/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files)。
