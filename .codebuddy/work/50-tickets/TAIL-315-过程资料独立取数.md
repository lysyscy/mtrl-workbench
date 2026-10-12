# TAIL-315: 过程资料直接读矩阵与单据差异，解除库存全量及大表预加载

**What to build:** 过程资料直接读矩阵与单据差异，解除库存全量及大表预加载

**Blocked by:** TAIL-314

**Status:** done

- [x] 一次报表读取按仓库分桶来源，原始/调整矩阵、全部有效项目候选、合计及导出金额与现实现等价；覆盖库存优先、历史来源、机械、空/零反例。
- [x] 页面直接读取同源单据差异与合计，保留数据库id、原值/调整值/差额、留痕与精确跳转原始行；没有调整时真实显示空态。
- [x] 第6页首次不预拉库存全量或收发结存/大表/提取；仍需的机械标签/录入及项目显示来源保留，没有未加载假零。
- [x] 机械及库存调整等跨页写后标脏/reload、失败点名、重试、加载/空/错误状态和批量导出保持；定向验证在隔离测试库。
- [x] 同条件复测首次/重复/刷新后、GET数/载荷，证明原始与调整/差异页面语义相等并记录实测改善或缺口。

---

## Comments

**2026-10-12 · 规划交接（agent）。** 本轮仅开票未实施。设计第二切片，Blocked by仅314；推荐第二个串行新对话。本次实测3587ms；去依赖与分桶收益为推断，尚未运行产品实现。现有机械轻量路不一并砍，差异必须先接领域diff_rows/diff_totals再解除库存依赖；屏幕单据差异与导出逐月差额不可混用。TAIL-313与实际业务库写入不在范围；服务加载由父对话另行安排。

**2026-10-12 · 建票（agent）。** 来源：用户2026-10-12性能诊断委派；本机只读测量｜不做会怎样：首次进入仍受库存全量读取或无关依赖拖慢｜落点：.codebuddy/work/10-designs/设计-首次载入最小优化-20261012.md｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：一 差异来源需先有瘦读出口；二 6页首访3587ms并等大表；三 请求内分桶及同源差异成本可控；四 三表金额导航导出等价且不拉无关接口


**2026-10-12 · 实施与隔离核验（agent）。** 开工HEAD `3f2a70c`、工作区干净；串行仅315。请求内按仓库分桶，原始/调整矩阵沿用domain；矩阵增加同源单据 `diffs/diff_totals`，页面不再读IVs/ADs，数据库id、原值/调整值/差额、备注/操作人/时间及精确跳转保持。第6页只拉过程资料与机械；机械保存只重拉这两源，其他页仍由API写出口全标脏、下次进入再取。未改业务金额/资格/导出规则及313保护。

`backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_acc_proc_001.py backend/tests/test_acc_proc_002.py backend/tests/test_proc_report_data.py backend/tests/test_process_export.py backend/tests/test_proc_split_shell.py backend/tests/test_tail315_proc.py backend/tests/test_wired_m06.py backend/tests/test_wired_boot.py backend/tests/test_ux_states.py backend/tests/test_tail292_nav.py::test_inventory_original_id_virtual_and_return backend/tests/test_layering.py -q --tb=short --junitxml=artifacts/_partial_tail315.xml`：107项/0失败/0错误，19.98s。再补库存调整撤销后真实API写出口标脏→进入m06仅重读两路及脱敏样例截图，`test_tail315_proc.py -q --tb=short --junitxml=artifacts/_partial_tail315_refresh.xml`：3项通过（2项重跑、1项新增），合计108项不同测试。数据库测试由conftest指向mtrl_workbench_test、外层事务回滚；浏览器写出口截获，未写业务库。沙箱内首次失败/中断及误写导航节点名的收集失败均不计通过；上述为放行本机隔离环境后的完成结果。

覆盖：同月库存优先、历史/机械独有项目、空≠零、未知类别、全候选/所选输出、来源单次读取、原始/调整及逐月差额xlsx/ZIP、页面单据差异顺序/三列合计/留痕、失败点名/重试恢复、机械保存与库存撤销跨页刷新、550行虚拟表精确id跳转和返回筛选。默认表与有调整差异在隔离样例截图已查看，布局/列值/入口保持；截图 `00-scratch/tmp-20261012-tail315-fixture-{default,diff}.png`。未运行全量回归、变异、额外review或正式服务39段；原壳历史58行未核实边界保留。

**2026-10-12 · 相对314的同条件测量（agent）。** 探针 `00-scratch/tmp-20261012-tail315-paired.py`，汇总JSON同名；同进程切换314原函数/壳与315、同FastAPI中间件/GZip/业务库，每事务READ ONLY；临时随机端口，拒绝HTTP写入、lifespan关闭，现有服务未动。Chromium151.0.7922.34、1440×900；先home启动再首访m06，重复返回，刷新壳再进入。每种模式3样本，交替顺序，第2组反转；以下为中位数，无P95承诺。

| 指标 | 314（本轮前） | 315（本轮后） |
|---|---:|---:|
| matrix函数ms | 1024.8 | 808.0 |
| FastAPI序列化ms | 24.7 | 22.9 |
| matrix完整HTTP请求ms | 1175.6 | 785.9 |
| matrix JSON字节 | 172,921 | 175,561 |
| matrix gzip字节 | 8,913 | 9,045 |
| m06首访ms | 2290.9 | 931.5 |
| m06重复ms | 30.6 | 32.1 |
| m06刷新后ms | 2328.1 | 706.2 |
| 首访/刷新GET | 6 | 2 |
| 首访/刷新解压载荷字节 | 11,564,878 | 189,340 |
| 首访/刷新传输字节（含resource固定开销） | 679,892 | 12,390 |

首访3样本范围：前2239–2769ms、后904–1514ms，存在热身/系统波动；重复均0GET、0载荷。新增差异字段令matrix增加2,640字节，但整页省掉库存11.36MB和结存/大表/提取三GET。所有旧matrix字段完整规范化哈希一致；全部项目原始/调整/差异页面文本与跳转id哈希一致；新增单据差异/合计与旧domain全量来源输出一致，全部失败列表/浏览器错误为空。差异有值留痕与跳转另由隔离样例核验。

原始未优化基线（019263e）曾测m06首访3587ms（单样）、314同进程原函数matrix1156ms；314曾测m06首访1997ms（单样）。这些是上一轮不同样本的参考，不能与本轮中位数相减或相加来宣称稳定累计收益。本票可证明的增量是上述314→315配对结果，尚不能保证正式服务/其他设备收益。

**2026-10-12 · 接续与交付边界（agent）。** 仅315完成，316仍待串行：第7页PAGE_LOAD与LOAD_DEP未动，可继续解除其库存预拉；315新增matrix差异出口可复用，机械轻量路保留。无推送、重启、迁移或业务写入，313的90条日期/防覆盖未触碰。正式运行后端仍未加载314/315；加载需由父对话另行安排。本地提交含本票代码、必要测试及销号文档，SHA以Git实际记录为准。


**2026-10-12 · 轻量收口（agent）。** py_compile、实际改动字节哨，以及doc_audit --ui、syntax_audit、ui_parity、wiring_audit、chain_audit、asset_audit、claim_audit、prg_form_audit均rc=0/必须修0；doc疑似52、wiring W2待清理1为黄档，未据此扩大本票。日志/命令与耗时见 `00-scratch/tmp-20261012-tail315-checks.py` 及分项log；剩余8项合计约14s。销号工具干跑/真跑后，修正已销号表的空行并经同一audit_meta.ledger_counts/audit_common.write_counts重算，活动3、编号总数316与T6一致；315为done，316状态未动。git diff --check通过。回写后再验文档及真实提交钩子，本地提交以Git为准，未推送。
