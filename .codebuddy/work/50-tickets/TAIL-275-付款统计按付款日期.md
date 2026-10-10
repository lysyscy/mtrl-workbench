# TAIL-275: 周月付款统计改按付款日期，台账表头写明按单据日期

**What to build:** 付款统计按有效流水实际金额和付款日期；欠款台账保留统计金额与单据日期

**Blocked by:** 无

**Status:** done

- [x] 付款统计（按周/按月）**取有效流水实际金额、按付款日期归桶**，欠款手调不改变付款统计；同一张卡上左栏、右栏、窗口合计与「本桶合计/N 笔」**用的是同一个时间**
- [x] 逐月欠款台账**保持按单据日期**，⛔ 不跟着改
- [x] 台账的**表头/说明写明「按单据日期」**，并写清目的：**为了监控拖了很久的付款**（单据日期越早 ⇒ 拖得越久 ⇒ 越该被看见）
- [x] 付款统计侧**不加**时间口径说明（按付款时间符合常识）

---

## Comments


**2026-10-09 · 建票（agent）。** 来源：用户2026-10-09定案（设计件3.6b）｜不做会怎样：同一张付款统计卡上两个数用的是两个时间，且看不出区别｜落点：MOD-05付款统计卡（后端bucket_of的实参、壳侧本桶合计）、MOD-05台账表头｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①统计按pay_date、台账按doc_date，故意不一样②现状同卡内已经两套时间打架，改完即统一③统计侧不写说明（符合常识）④台账侧要写表头加说明，因为目的是监控拖很久的付款

**2026-10-10 · 开工（agent）。** HEAD=c31cd8a，初始dirty为空；字节基点 `.codebuddy/work/00-scratch/tail275-start.json`。只实施275，按影响核验，不提交、不推送。付款统计独立投影，台账日期出口保持；跨桶调整金额的分摊未定，须报告样例。

**2026-10-10 · 实施与验收（agent）。** 付款统计独立付款日期投影，一次取流水按通知书关联；剔除/撤销/无关联不纳入。单桶内整单统计额只计一次；跨桶仅在统计额等于有效流水合计时按笔归期，金额为Decimal。跨桶手调或缺付款日期不回退单据日期/今日，也不臆造比例；API给具体流水样例，异常状态页内警告，不冒充完整合计。台账共享视图/月度出口未改；壳按后端right/cells/counts显示，有效选桶消费pst.ym，窗口合计取right之和。台账两栏表头与简短说明同批更新，付款统计旧错误文案纠正。说明书仅改§4.5.5时间分桶，§4.5.4保持；核实ACC-FLOW-PST-001六条未写死单据日期，JSON/MOD-05/引用索引无需重复定义。

实际修改：domain.py、service.py、index.html、pages-a.js、proj.js、test_acc_flow_pst.py、新增test_tail275_stats.py及_mut_tail275.py、说明书、当前票与协议销号索引。未触达数据库结构、_current_bucket、268/276及pack.ps1。

实际命令（仓根；pytest首组在backend工作目录；下文python指backend/.venv/Scripts/python.exe，--since的省略项均为.codebuddy/work/00-scratch/tail275-start.json）：
- `_run_rulers.py --start .codebuddy/work/00-scratch/tail275-start.json` rc=0；HEAD c31cd8a、dirty空；`--since ... --explain` rc=0，使用_pytestscope实际消费者选测。
- `python -m py_compile` 运行修改及新判据/变异件 rc=0；首次误用backend工作目录下的backend/.venv路径rc=1，改正路径后执行成功。
- `.venv/Scripts/python.exe -X utf8 -m pytest tests/test_acc_flow_pst.py tests/test_page_m05.py -q` rc=0（20项）；新壳行为`pytest backend/tests/test_tail275_stats.py -q` rc=0（2项）。
- `ops/server_ctl.ps1 -Action restart` rc=0，/app=200。
- `python -X utf8 tools/mut/_mut_tail275.py` rc=0，8/8：日期错取、实际金额替换、撤销、剔除、多笔重复、选桶丢失、窗口误用全量、笔数脱离后端均正常绿/隔离红；正式源码及产品资料未作临时变异靶。
- `python -X utf8 tools/audit/mut_cover.py` rc=0（生成忽略产物）；`python -X utf8 tools/audit/shell_verify.py`盖章前rc=1，26行均为本票预期差异，逐条确认，无变异残留。
- 初轮`python -X utf8 tools/oneoff/_run_rulers.py --since ...` rc=1，198.64s，唯一相关失败是test_ux_brief普通说明块；改为现有警告状态样式后`pytest backend/tests/test_ux_brief.py backend/tests/test_tail275_stats.py -q` rc=0（6项）。不将初轮失败报绿。
- `.codebuddy/work/00-scratch/tail275-data.py`现场只读rc=0（首次漏register_all rc=1，补装配后成功）；month/week均未发现无法归期数据。
- `.codebuddy/work/00-scratch/tail275-live.py`真机只读rc=0。实际页面9月左栏合计=右侧9月=本桶合计=1,965,483.03，51笔，窗口合计同后端right之和；通知书167单据2026-08-23、付款2026-09-21、统计8,270元，统计归9月，安徽国风台账8月付款仍87,770元。两栏按单据日期表头/说明正常；截图已目视检查。周跨月、周一标签、月6/周8窗口、窗口外全量金额差、选桶与异常状态另由真实组装/浏览器隔离样例验证。

最终影响入口、完整壳自检与盖章的实际rc/耗时：
```text
tools/audit/doc_audit.py rc=0 1.88s
tools/audit/audit_drift.py rc=0 1.06s
tools/audit/audit_meta.py rc=0 0.56s
tools/audit/audit_work.py rc=0 0.38s
tools/audit/syntax_audit.py rc=0 5.19s
tools/audit/bytes_guard.py rc=0 0.13s
tools/audit/ui_parity.py rc=0 0.23s
⚠️ 「壳变了没有 / 变在哪」**不归本件**（`U1`/`U5` 已于 2026-09-30 `TAIL-201` 退场）⇒ 那一层看 `python tools/audit/shell_verify.py`（差异 ⇒ rc=1 ⇒ 复核后 `--snapshot` 盖章）。
tools/audit/wiring_audit.py rc=0 3.43s
tools/audit/chain_audit.py rc=0 0.25s
tools/audit/asset_audit.py rc=0 0.17s
tools/audit/claim_audit.py rc=0 0.13s
tools/audit/prg_form_audit.py rc=0 0.25s
pytest（隔离结果） rc=0 161.88s
真机壳自检 rc=0 138.34s
壳基线盖章 rc=0 0.29s
总墙钟 330.28s BAD: []
```
完整真机输出位置以final log的“真机证据”行为准；本票scratch保留selection、rulers初/终、mutations、live、shell-diff日志及两张截图。初轮各成功项输入未变可复用；最终相关pytest独立结果隔离，未刷新权威四态。无关治理黄项保持，不纳入275。

**一轮双轴code-review（基点c31cd8a工作区差异）。** Standards 0硬违反/0有意义smell；Spec 0；不再双轴复审。之后只修复上述已知警告样式失败，局部与最终壳复验。

**未定与未验边界。** 尚未定义跨不同桶的多笔付款遇统计金额手调时如何分摊；隔离样例统计150、实际40（9月）+60（10月）会明确报未归期，而非各笔重复150或擅分60/90。缺付款日期亦待补事实。现场目前均无此类未归期行，因此不阻挡当前明确范围交付；将来出现须用户确认规则。未做真实付款写入、撤销或生产数据调整；无数据库/备份恢复/全量业务套件重跑，无提交、无推送。

本轮截至收尾约17.2分钟（含读取、实现、失败修补、检查、真机及一轮复审）；可交付明确范围。

**2026-10-10 · 协议销号。** `_tail_close.py --id 275 --apply` rc=0，票done、§15销号行和计数同步；销号后`doc_audit.py` rc=0，`shell_verify.py` rc=0（差0），`git diff --check` rc=0。完整壳39段rc=0，无console/page错误，盖章完成。后续只有当前票留痕变更，运行代码/现场数据未变，前述有效核验证据继续可用；未提交、未推送。

**2026-10-10 · 用户最终裁定与补修开工。** 人工修改统计结算/统计付款只修正欠款；实际付款错误撤回重付。用户授权按该目的实施，原275同源金额约束及前次分摊待定结论作废；历史Comments保留，当前交付结论以本次补修结果为准。开工差异基点tail275-revision-start.json，保留已有dirty，不提交不推送。同步落实整轮retro：定点读取、先便宜回归、复用有效结果、少量长等待、精简证据，删除无业务依据的分摊/归期异常逻辑，不新建检测闸门。

**2026-10-10 · 补修交付（取代此前交付结论）。** 付款统计一次读取有效流水，以实际金额和pay_date独立投影；项目取通知书归属，剔除/撤销/无关联流水不纳入。人工统计金额调整只影响欠款及按doc_date的台账，无须分摊到付款日期。删除未归期警告及无调用旧求和/前端辅助函数。窗口合计取右桶之和，选桶、项目金额和笔数同源。业务说明§4.5.5、MOD-05及验收基线3处文字同步，§4.5.4不改。retro已落入issue-tracker§四：先核实字段设计目的，定点读取，先低成本验证，复用未变成功项，不新增猜测性检测。

实际命令及退出码（日志均在00-scratch/tail275-revision-*）：
- `python -X utf8 -m pytest backend/tests/test_acc_flow_pst.py backend/tests/test_page_m05.py backend/tests/test_tail275_stats.py backend/tests/test_wired_m05.py backend/tests/test_ux_brief.py -q`：rc=0，40项。
- `python -X utf8 tools/mut/_mut_tail275.py`：rc=0，6/6正常绿、隔离变异红。
- `_run_rulers.py --since tail275-revision-start.json --explain`：rc=2，验收JSON路径待定；已核实实际消费者，单独执行`pytest backend/tests/test_acc_suite_selftest.py -q`及`tools/probe/_audit_face.py`均rc=0，并断言JSON只变3处文字、所有ID及其他值不变。
- `python -X utf8 -u .codebuddy/work/00-scratch/tail275-revision-run.py`：rc=1，157.68秒；相关pytest rc=0（129.77秒），仅wiring发现无调用旧sum_pay_stat。删除后`tools/audit/wiring_audit.py`局部复验rc=0，其他成功结果复用，无重复全轮。
- `python -X utf8 .codebuddy/work/00-scratch/tail275-live.py`：rc=0；现场9月统计1,965,483.03、51笔，跨月样本付款归9月、台账仍归8月；安徽国风8月台账付款87,770。浏览器只读，未写生产数据。
- `powershell -NoProfile -File ops/server_ctl.ps1 -Action restart`：rc=0，10.48秒；`tools/probe/_shell_smoke.py`：rc=0，39段、109.83秒、无console/page错误；预期壳差异已复核，`tools/audit/shell_verify.py --snapshot`及随后`tools/audit/shell_verify.py`均rc=0。

未验边界：未进行生产付款/撤销写入，未刷新权威四态，未重跑无关全量业务套件。没有仍需确认的金额分摊规则；此前“跨桶手调分摊未定义”结论失效。一轮双轴复审已用，不追加。补修核验编排157.68秒、最终壳编排约120.56秒，其余阅读/实现/局部核验另计；可交付，票保持done，无提交、无推送。

收尾仅更新本票与§15原销号行；`python -X utf8 tools/audit/doc_audit.py` rc=0（必须修0），`git diff --check` rc=0。运行代码未再变化，沿用上述有效结果。

**2026-10-10 · 空周窗口显示修复及提交授权。** 用户截图反馈“没有付款数据”，授权修复并提交推送。开工基点`tail275-empty-start.json`。现场Q4周窗口left=0、buckets=2，但全年实际付款1,965,483.03；上一轮用left非空决定整卡展示，误隐藏选桶/时间范围入口。改为按窗口桶存在决定展示，空窗口保留选择器、零合计及空桶提示，无改金额或日期口径。

核验：`_run_rulers.py --since tail275-empty-start.json --explain` rc=0，使用既有_pytestscope选择并核对实际影响；仅付款统计显示分支新增变化，其他运行输入及此前成功证据复用。`pytest backend/tests/test_tail275_stats.py backend/tests/test_page_m05.py -q` rc=0（13项）；新增空窗口测试在隔离旧实现中rc=1，修复后rc=0（首次测试选择器误写data-act，纠正为真实data-id后重做隔离红验）。`tail275-empty-live.py` rc=0，默认空周仍可选时间，切9月显示1,965,483.03、51笔。syntax_audit、wiring_audit、bytes_guard、ui_parity均rc=0；完整`_shell_smoke.py` rc=0，39段、无console/page错误；shell_verify仅预期2行差异，复核后--snapshot及再验均rc=0。无生产数据写入，无新一轮双轴复审，无权威四态刷新。此次现场与回归验证约数分钟，完整壳为主要耗时；票保持done，可交付。本次提交包含275与已授权retro全部修改。

**2026-10-10 · 周选择无反应补修。** 用户授权修复并提交推送；基点`tail275-week-start.json`。选择器列整季度，但统计仅取最近8周，窗口外选择被pstData退回旧桶；pstb原来只改本地ym，未驱动跨季度或窗口取数。新增stats查询bucket作为窗口截止桶；选周同步轴年/季度及请求参数，自动补拉；改轴清除旧选桶。本周快捷键按实际周所属季度，季度首个跨月周保留面板季度。默认窗口、8周上限、周一标签、_current_bucket、金额及台账口径不变。

核验：`_run_rulers.py --since tail275-week-start.json --explain`选择影响，沿既有_pytestscope核对相关消费者；`pytest backend/tests/test_tail275_stats.py backend/tests/test_acc_flow_pst.py backend/tests/test_page_m05.py -q` rc=0（23项）；`pytest backend/tests/test_tail275_stats.py backend/tests/test_wired_m05.py backend/tests/test_shell_api.py -q` rc=0（41项）。隔离旧actions调用新增测试rc=1，修复实现rc=0。`tail275-week-live.py` rc=0：06-29、07-06、08-03、09-28均选中正确周，历史季度面板本周快捷键可返回当前周。`ops/server_ctl.ps1 -Action restart` rc=0；syntax_audit、wiring_audit、bytes_guard、ui_parity均rc=0。只读现场，无生产付款调整；无新增双轴复审或权威四态刷新。

最终完整`_shell_smoke.py` rc=0（39段、无console/page错误）；壳差异15行均为本次选桶参数及联动，复核后`shell_verify.py --snapshot`及再验rc=0。此前在完整壳执行期间补修了本周快捷键的季度选择，因此最后对冻结代码重新完成完整壳核验，没有沿用旧输入结果。主要耗时为完整壳约两分钟/次，其余定点验证；可交付，票保持done。此前空窗口修复及275/retro已提交推送`69b3ca2`；本次按授权提交周选择补修。
