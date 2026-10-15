# TAIL-314: 库存与报表读取只取所需字段，减少完整ORM及原始JSON的重复物化

**What to build:** 库存与报表读取只取所需字段，减少完整ORM及原始JSON的重复物化

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 库存页面与过程资料的规范行、行序、count/projects、金额精度与调整单字段和现实现等价；原始JSON留存及确需ORM的调用者保持可用。
- [x] 焊材/气体只查原单入库所需字段，分类/年度历史/结余沿用领域出口；原单与调整后、入库与出库、空与零反例在隔离库通过。
- [x] 瘦读SQL不取未用raw，不因访问延迟字段引入逐行查询；库存调整映射在请求内复用，实际查询计数有证据。
- [x] 在同条件本机页面与直接读入口复测耗时/载荷，记录收益或剩余瓶颈；保留完整响应语义对照，不承诺固定提速倍数。

---

## Comments

**2026-10-12 · 开工（agent）。** HEAD019263e；原仓串行仅314，已有7份本批规划文档保留并纳入本地提交。开工差异摘要在00-scratch；不推送、不重启、不写业务库。保留完整ORM入口，规范行改明确列投影，提取经mod08服务读取原单入库四字段。

**2026-10-12 · 规划交接（agent）。** 本轮仅开票未实施。设计第一切片；推荐首个新执行对话只办本票。原型只在诊断进程替换读函数，四入口规范化JSON摘要相等；不是业务写/导出已验收。不得改业务库、TAIL-313日期保护或擅自加载服务；产品变更的定向反例用mtrl_workbench_test隔离。技术入口与复现条件见设计及性能基线，实施时重核当前HEAD。

**2026-10-12 · 建票（agent）。** 来源：用户2026-10-12性能诊断委派；本机只读测量｜不做会怎样：首次进入仍受库存全量读取或无关依赖拖慢｜落点：.codebuddy/work/10-designs/设计-首次载入最小优化-20261012.md｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：一 同一库存全量被四读入口消费；二 首次约1–3秒且18198行；三 明确投影比缓存维护便宜；四 字段金额与行序等价且同条件复测

**2026-10-12 · 实施与定向核验（agent）。** `backend/app/mod08_inv/repository.py` 的规范行明确SELECT消费列，保留完整ORM的list_details与原单服务出口；新增原单入库四字段投影，经service供焊材/气体提取，分类与年度/结余函数未改。库存API请求内复用调整映射，SELECT由3降2；matrix/big/extract为6/11/4，提取库存子查询固定1次。SQL不取raw/created_at，不产生InvDetail实体或逐行延迟查询。

使用 `backend/.venv/Scripts/python.exe -X utf8`，测试由conftest切至mtrl_workbench_test，真实库用例全部rollback：

- `-m pytest backend/tests/test_inventory_projection.py backend/tests/test_acc_inv.py backend/tests/test_acc_inv_fetch.py backend/tests/test_tail266_inventory.py backend/tests/test_acc_setl_ext_001.py -q --tb=short`：36项，rc=0；含完整ORM/规范行/API等价、金额分位、调整到0、未调整字段缺省、月份过滤、raw可读、写调整/重抓/撤销及原单入出库反例。
- `-m pytest backend/tests/test_acc_proc_001.py backend/tests/test_acc_proc_002.py backend/tests/test_proc_report_data.py backend/tests/test_process_export.py backend/tests/test_path1_weldgas.py backend/tests/test_acc_rpt_big.py backend/tests/test_big_export.py backend/tests/test_acc_fee_mon.py backend/tests/test_tail300_sources.py::test_fee_original_excludes_adjustment backend/tests/test_layering.py -q --tb=short --junitxml=artifacts/_partial_tail314_reports.xml`：113项，rc=0，12.77s；覆盖材料来源优先级、原始/调整/差异、过程ZIP、焊材/气体与大表导出、年度历史/独立结余空与0、特殊费用完整原单消费者和服务委托。
- 自动影响说明选到105件测试（共享桩及静态分层读取面较宽）；按本票已查明实际消费者执行上述149项，未运行全量pytest、变异或39段。py_compile及syntax_audit通过；syntax首次因沙箱TEMP写入失败，局部TEMP改到00-scratch后原检查复验rc=0。终轮doc_audit、chain_audit与claim_audit均必须修0/rc=0；既有黄色提示保留。暂存字节由已安装真实提交钩子核验，实际提交记录以本轮Git为准，不推送。

**2026-10-12 · 同口径只读复测（agent）。** 现有8000服务未加载修改。独立直接读探针复用基线脚本与实际FastAPI响应序列化，所有事务READ ONLY；初次独立进程前后函数ms为inventory763.4→560.3、matrix1005.6→796.3、big741.7→124.6、extract622.6→318.0。为说明调度波动，另在同进程交替旧/新读函数三组，第二组调换顺序，各组清理监听；函数中位数如下（非P95，不能视为生产服务剖析）：

| 入口 | 旧读ms | 新读ms | SELECT旧→新 | 响应字节 |
|---|---:|---:|---:|---:|
| inventory | 871.6 | 554.2 | 3→2 | 11,361,071 |
| matrix | 1156.1 | 834.7 | 6→6 | 172,921 |
| big | 751.2 | 110.0 | 11→11 | 6,383 |
| extract | 578.0 | 89.9 | 4→4 | 9,227 |

初次前后及三组四入口完整响应规范化SHA256均相等（保持数组顺序，仅排序JSON对象键）；库存原始响应字节与gzip长度相同，仍18,198行/11.36MB，gzip9为662,366字节。extract仅对象键序可能变化，gzip长度有1字节波动。证据：`.codebuddy/work/00-scratch/tmp-20261012-tail314-before.json`、`.codebuddy/work/00-scratch/tmp-20261012-tail314-after.json`、`.codebuddy/work/00-scratch/tmp-20261012-tail314-paired.json`；复现脚本 `.codebuddy/work/00-scratch/tmp-20261012-tail314-paired.py`，`--direct-only`只测直接入口。scratch为14天临时证据，不作后续永久依赖。

页面复用原浏览器探针，在随机本机端口的临时同一FastAPI实例交替旧/新读入口，沿用中间件/GZip/壳/业务库；lifespan禁用、HTTP写方法拒绝、数据库READ ONLY，测完实例退出。Chromium151.0.7922.34、1440×900、新上下文先等home加载后进页；首次/重复/刷新与基线相同定义，每格仅1样本：

| 页 | 首次旧→新ms | 重复旧→新ms | 刷新后旧→新ms | 首次GET旧→新 |
|---|---:|---:|---:|---:|
| m05 | 586.3→601.9 | 30.6→31.5 | 517.2→658.5 | 7→7 |
| m06 | 3804.4→1996.8 | 31.9→31.8 | 3937.8→2044.3 | 6→6 |
| m07 | 3052.4→1446.0 | 32.3→31.0 | 2650.1→1226.4 | 5→5 |
| m08 | 1366.0→1142.9 | 43.9→39.8 | 1282.8→1226.6 | 1→1 |

全部失败列表为空、重复均0GET、页面DOM计数与载荷不变；临时实例显示6/7页等待下降、8页收益较小、5页无收益，不能据此保证运行服务或日常浏览器同倍数。页面证据 `.codebuddy/work/00-scratch/tmp-20261012-tail314-browser-before.json` / `.codebuddy/work/00-scratch/tmp-20261012-tail314-browser-after.json`。

**2026-10-12 · 接续与边界（agent）。** 仅314实施；315/316仍待做，依赖已解除。下一轮315可直接复用service.load_rows投影，仍需独立做矩阵分桶/差异同源与解除库存/大表依赖；316仍只摘大表无消费者库存依赖。未推送、未重启现有服务、未迁移或写业务库，TAIL-313日期代码/90条保护未动；正式运行服务/已有登录浏览器/冷服务及未来规模未验。后端投影不能减少当前库存浏览器11.36MB，相关传输/解压/序列化仍在。
