# payment-plan-audit 独立审查（修复后）

What this change does: 新 skill 只读原始材机计划和系统事实，按原行生成并排核对报告，并生成拟付款方式预览。独立命令只在用户确认后写通知书拟方式；本审查没有运行该写入命令。

审查对象：`skills/payment-plan-audit/SKILL.md`、`scripts/audit.py`、`snapshot.py`、`methods.py`、新增`test_audit.py`及直接使用的金额、项目匹配、六类审查规则和通知书拟方式消费者。按单人本机、普通月表规模判断。审查者未改源码，只写此调查报告和独立离线复跑目录。

## 结论

初审发现的三项必须修问题已由主 Agent 修改，并完成独立复核。修复后未发现新的阻断项。真实文件无漏行；143明细、9项目、计划19,099,428.50元。最终状态为69行核对通过、74行待人工核对，69条拟方式候选；金额规则中的120行“完全匹配”与最终状态已明确分开。

## 三项修复复核

1. **预览生成后金额事实变化仍可回写**，已补保护。
   - 初始`methods.py:43-52`只检查ID、归属、旧拟方式、剔除/撤单，未检查生成资格依赖的审批/有效已付。真实原表40行、通知书82，把离线快照的审批改1元或有效已付改82500元，重新compare均失去资格，而旧代码检查项全部不变；该复现没有执行methods。
   - 修复后预览携带approved/paid/flow_amount/planned_amount；load_approved校验金额资格。事务内先锁`payment_notice, payment_flow`，再查询审批和有效流水汇总，任何变化整批拒绝。独立静态复核`methods.py:34-37,47-62`确认这条路径；最终真实69条预览均包含四金额且满足资格。
   - 新增测试源码覆盖approved/paid变化及整批不写；审查者按“不运行methods.py”的边界没有执行该测试中的方法函数。PostgreSQL真实锁与回滚仍未现场验收。

2. **离线快照缺失剔除/撤单状态仍产生合格预览**，已补保护。
   - 初审删除真实快照通知书82的excluded/i8_revoked字段，validate仍通过且该单进入候选，原因是`.get()`把未知当False。
   - 修复后snapshot.validate要求归属、项目、收款单位、两个状态等资格字段，并要求excluded/i8_revoked为明确bool。独立内存变异验证：逐一删除excluded或i8_revoked，均抛“快照缺少字段”拒绝；未触库。

3. **“完全匹配120”包含未对应项目及剔除/撤单行**，已明确结果层次。
   - 初审真实120行“完全匹配”中51行项目未唯一对应，107/110/115还已剔除撤单；虽然已正确挡住回写，摘要容易误读。
   - 修复后保留旧六类金额规则，Excel列标题改为“金额规则结论”，增加“本行状态”；任何输入/归属/剔除撤单问题都成为待人工核对。最终离线复跑验证所有带问题或金额非完全匹配的行均待人工核对；summary.row_status=69通过/74待核对。

## 报告复核与余项

- 离线复核现已在JSON和Excel“数据说明”明确标注“离线复核，沿用旧快照”，保留原采集时间2026-10-15T16:42:17.988834+08:00。
- 尚有一条非阻断噪声：原件末行只有G196总计，E196从无公式或值，但当前汇总报告仍称E196“全表总计包含缺失金额，无法独立验证”。最小修正是该总计字段既无原值也无公式时跳过；有公式但无缓存仍应保留报警。E153缺金额和E154/E157不能独立核验的真实问题不受影响。
- 报告核对明细144行×22列、待处理75行×22列、行分类197行（均含表头）。原报/系统项目、收款单位、金额在同一行并排；L4/L77:L79四条附注准确保留；报告内零可执行公式。只验证结构和单元格值，没有做Excel视觉渲染。

## 独立执行证据

1. 初版离线复跑输出：`.scratch/payment-plan-workflow/skill-review-replay`。audit.json、snapshot.json、method-preview.json与audit-first逐字相同。
2. 修复后离线复跑输出：`.scratch/payment-plan-workflow/skill-review-final`。执行`backend/.venv/Scripts/python.exe -B -X utf8 skills/payment-plan-audit/scripts/audit.py --repo D:/dev/mtrl-workbench --source <桌面真实原件> --month 2026-10 --snapshot .scratch/payment-plan-workflow/audit-first/snapshot.json --output-dir .scratch/payment-plan-workflow/skill-review-final`，退出码0。
3. 不是依据重复运行相同就判正确：逐项核对此前独立原表调查的143个精确行号序列全部相同；196个非空行全有分类且无重号。
4. 9段行数30/14/20/13/11/33/19/1/2全部相符；G66/G80零值、7个无可用号候选、155行“设备”11,193,840元、E153缺金额、四组重复号均保留。E81/E82各少259,250元已准确报告。
5. 相对这份快照，69个预览候选均满足项目对应、金额、正计划、可识别方式、非重复及非剔除撤单等条件；59行项目未唯一对应被挡住，没有猜项目凑命中。
6. 静态复核snapshot.capture使用PostgreSQL REPEATABLE READ和SET TRANSACTION READ ONLY；系统已付仅汇总status=effective，不调用i8。methods具备预览SHA、源SHA、数据库指纹、字段存在、唯一号、归属、旧值、剔除撤单和审批/已付事实复查，整批事务更新并先保留回执。
7. 原件始终SHA=`97753b7f7f1a61cb016d0f0f1bd02a244c5ee5301f3181efc9135e007799b051`；未保存/重算原件，未访问实时数据库或i8，没有执行methods.py、迁移或生产回写。

Verdict: Ship，限已验证的只读核对和预览；生产写入须沿用户确认和项目生产验收边界执行。

Not checked: 生产回写、PostgreSQL锁/回滚、Excel现算与视觉效果；静态代码复核不代替这些验收。
