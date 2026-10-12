# TAIL-307: 过程资料页面与导出共用有效数据组装

**What to build:** 过程资料页面与导出共用有效数据组装

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 库存独有、有效历史独有和有效机械独有项目均可按原始/调整后/差额导出；独立金额与None/0预期成立。
- [x] 页面与导出共用来源、仓库资格、材料cutoff和矩阵组装；多项目导出每个来源/cutoff只读取一次，不用导入候选替代报表候选。
- [x] 截止仅筛导入，已存材料/机械金额及历史回滚行为保持；页面响应shape、逐单差异与工作簿月度差额不同含义保持。
- [x] 无数据、未登记展示名与未选项目错误保持；多项目ZIP内容、标题及文件名正确。
- [x] 隔离回归、反向灵敏度及适用检查通过，记录收益与边界；不提交推送、部署或重启服务，不动D、284/287。

---

## Comments

**2026-10-12 · 建票（agent）。** 来源：2026-10-12用户自主开发授权及父任务B1委托｜不做会怎样：只有机械费的项目页面可选但导出被拒，多处资格和矩阵规则会漂移｜落点：mod06_proc/service.py、report_export/service.py及隔离回归｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①机械独有漏导出已静态核实②合法报表无法交付③现成owner矩阵出口可复用④独立金额预期、回滚、ZIP和加载次数及隔离反例验证

**2026-10-12 · 调查与暂停交接。** 基线f6e13b018501a8aba9d0ba4debd059759209f050（TAIL306已本地提交，未推送）。说明书§5.2.5明确候选含机械独有，双截止只筛导入不遮挡已存金额。新增test_proc_report_data.py在旧实现上6失败/7通过（2.58s），覆盖机械三表、ZIP、缺展示名、回滚后仅手录仍可导出；已写最小实现，尚未复验。MOD06私有来源快照和单仓库矩阵供页面/build_matrices共用；导出调用build_matrices的所选仓库参数，命名/模板/错误仍归导出，逐单和月度差异不合并。

**2026-10-12 · 分线边界。** 按父任务当前委托暂停B1写入，转当前工作区独占长期登录；父任务另安排报表隔离线，恢复B1先等协调。本批6个未提交文件为主计划、本票、backend/app/mod06_proc/service.py、backend/app/report_export/service.py、backend/tests/test_process_export.py、backend/tests/test_proc_report_data.py。Git只登记D:/dev/mtrl-workbench一个worktree；无已登记且获授权的独立目录。仓库要求保留dirty、共享文件重读串行；技能未规定自动分支/worktree。代码与长期登录预计不交叉，主计划/销号索引/tools README/覆盖台账/结果文件交叉需协调。没有reset、stash、覆盖、提交B1或改D/284/287。

**2026-10-12 · B1恢复与实现完成，未提交待复核。** 按最新委托恢复当前工作区B1；此前分线说明保留为历史。MOD06来源快照、候选资格和单仓库矩阵由页面/build_matrices共用，导出只取所选仓库矩阵并负责展示名、格式与交付；多项目来源/材料截止/展示名各读一次。有效机械独有项目进入三表/ZIP，导入候选仍含全部档案，不与报表混用。材料/机械截止仍仅筛导入；原始/调整、逐单/逐月差额、None/0、仓库键和回滚语义保持。新接口只增加可选warehouses，不建通用框架。

首轮26项有5项发现机械独有尾块的材料小计遗漏，模板公式未被覆盖而拒产；在过程资料格式适配process_export.body_spec用现有引擎的空串约定显式清空小计，明细与小计均留空，不造0。公共tpl_fill/save/workbook和D的共享Excel读取机制均未改。修补后26项通过；新增尾块独立断言也纳入最终选集及反向验证。

**运行证据。** 开工基点tmp-20261012-b1-entry.json；HEAD=f6e13b018501a8aba9d0ba4debd059759209f050。按影响入口--explain，仅列本批5个运行/测试路径，选择111件，排除长期登录新测试后执行110件。`backend/.venv/Scripts/python.exe -X utf8 .codebuddy/work/00-scratch/tmp-20261012-b1-verify.py related`：859通过/2跳过/3失败，93.41s；3失败为副本缺requirements.txt与迁移文件，补齐后repair同3项通过，1.33s。2跳过为副本未带.env的测试库守卫；仅在临时副本给假开发库地址，guard的正常/错指/同地址3项全部通过，0.06s。因此110件所选864个独立用例全部取得通过结果，未重复整套93s回归；环境修补未改正式代码或既有859项输入。

`...tmp-20261012-b1-verify.py mutations`调用tools/mut/_mut_proc_report_data.py：正常14通过（2.64s），8/8明确行为断言造红，复原14通过（2.46s），正式源码字节未变。靶含漏机械候选、共用首仓库截止、交换原始/调整、月差额代替逐单、每项目重读、恢复已回滚历史、截止遮挡已存机械、漏空小计。测试库为127.0.0.1:5432/mtrl_workbench_test，真实回滚用例外层事务/SAVEPOINT整体回滚；假来源/展示名和进程假i8配置，不连i8。

**适用检查与收益。** syntax_audit、chain_audit、claim_audit、bytes_guard实际7个代码/测试/工具文本、mut_cover生成及--check、doc_audit --ui、audit_drift/meta/work均rc=0；链路102/102，文档必须修0，交付面四检607/31/472/121通过。mut_cover现130件，原未覆盖登记保持。票和索引回写后再核文档与字节，最终完整回执在scratch的tmp-20261012-b1-final-checks.json。收益是资格/来源/矩阵规则一处修改，两端同源；批量导出不再按项目重复取数。

**范围和未验边界。** 本批10个未提交文件：主计划、本票、已销号索引、MOD06 service、report_export service/process_export、test_process_export/test_proc_report_data、反向脚本、tools README。原有长期登录4个草稿保留，不改写、不复原，不认作已验；仅临时副本的3个已跟踪登录文件换为HEAD且移除副本新登录测试。没有生产库/真实i8调用、部署、重启、推送或提交；不动TAIL-284/287及D公共workbook机制，不刷新完整权威四态，不声称运行中服务已应用本次代码。交给父任务独立复核。
