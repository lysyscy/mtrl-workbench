# TAIL-276: 无仓库历史项目：手动建档、一行集采合同、通知书配套降级

**What to build:** 无仓库历史项目：手动建档、一行集采合同、通知书配套降级

**Blocked by:** TAIL-274（无仓库项目也要能出逐月欠款台账）

**Status:** claimed

- [ ] 能**手动建**一个无仓库历史项目：仓库名沿用 `未建仓-N` 占位文本（⛔ 不置空 —— 它是唯一识别键）
- [ ] 它**能挂逐月欠款台账**（依赖 `TAIL-274`）
- [ ] 它的集采合同表**只有一行**：材料名 ＝ 项目全名、合同日期/供应商/合同金额留空，**发票金额在子表里录一条** ⇒ 结算金额与欠款金额**自动算出**
- [ ] 付款通知书里「集采实际供应商自动匹配」与「单据关联」对这类项目**显式降级**（⛔ 不静默匹配错）；子表弹窗标题写明「本项目的全部集采合同（1 行汇总）」
- [ ] 项目档案页给这类档案一个**可见标记「无仓库（历史项目）」**；⛔ 不新增项目类型

---

## Comments

**2026-10-09 · 建票（agent）。** 来源：用户2026-10-09定案（设计件3.7）｜不做会怎样：宜昌、许昌安彩这类只有i6欠款的项目在系统里没法挂单据｜落点：MOD-01项目档案、MOD-11那一行合同、MOD-03通知书的供应商自动匹配与单据关联｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①统一手动建、仓库名沿用未建仓-N占位文本（它是唯一识别键不能置空）②集采合同只有一行、材料名填项目全名、发票金额走子表、结算与欠款自动算③不关联供应商④通知书的供应商自动匹配与单据关联要显式降级不能静默匹配错⑤档案页给可见标记「无仓库（历史项目）」

**2026-10-10 · 精简实施与验证（agent，未销号）。** 初始HEAD `58766573079b6c2e0eb986b39fde904643626fd5`、dirty为空。按用户本轮提示词及后续最终裁定实施；本轮最终口径：关联金额动态取通知书统计付款金额，手改统计金额同步改变集采欠款，零值不回退审批金额。这替代提示词中的“只取有效流水、手改统计不影响集采”要求。关联只存关系，日期显示最近生效流水日；旧关联金额不再参与计算，手工付款保持既有行为。未改付款流水权威出口、金额公式及MOD-05集采注入。

- 实现：项目档案手工建档沿用POST /api/m01/projects与reloadProjects，普通项目不传仓库名、展示名默认全名，后端生成未建仓-N。手工合同新增可勾选历史汇总，项目全名默认材料名、日期/供应商/贸易公司空、金额沿用空转零；每项目历史汇总重复新增提示修改原行。截至日记现有备注，供应商发票子表明确历史未结金额/核对截至日、提醒已扣除此前付款。只在人主动选择时建一行，不批量生成或改造现有合同。日期回显改适配层读取date；引用累计行明确统计付款累计，解绑保留真实流水。供应商自动匹配与候选规则不变，依用户本轮E节取代旧票面的专用降级/固定1行候选标题要求。
- 存量只读核查（READ ONLY事务）：15条关联存储总额3,374,868.39，统计付款总额1,096,781.17；8条差异共2,278,087.22。兰考通知书57：52,378.00→49,730.60；太康通知书10/7/6/3/4/8/9旧值合计2,275,439.82→0。用户已解释并确认纠正；无生产数据清洗。许昌安彩与宜昌邦普已有多条普通合同，项目归属流水0条，合同备注无历史汇总截至日，保留原记录。未替用户录入历史基数。重启后真实GET明细已核实兰考49,730.60、日期2026-09-22；太康上述7条均0且日期空，其他已付款关联仍保留。
- 验证命令均以 `backend/.venv/Scripts/python.exe -X utf8` 运行。`-m pytest backend/tests/test_tail276_jc.py backend/tests/test_tail274_ledger.py backend/tests/test_tail275_stats.py backend/tests/test_acc_jc_domain.py backend/tests/test_acc_jc_list.py backend/tests/test_acc_jc_write.py backend/tests/test_acc_jc_pay_link.py backend/tests/test_acc_jc_shell.py backend/tests/test_acc_sup_match.py backend/tests/test_wired_m01.py backend/tests/test_wired_m11.py -q` 初跑rc1（普通日期初始化源码形态断言）；保留普通初始化、单独应用历史截至日后，`-m pytest backend/tests/test_tail276_jc.py backend/tests/test_acc_jc_shell.py -q` 11项rc0。先前旧回退审批金额用例的rc1已按最终口径修正。相关原输入未变化的通过结果复用。
- `tools/oneoff/_run_rulers.py`：按影响选择124件测试，pytest rc0（150.41秒）；语法/字节/壳规则/接线/链路/资产/PRG检查均rc0，入口rc1仅因新增反例后覆盖台账未生成。`tools/audit/mut_cover.py`及`--check`生成并复核rc0，未变化检查复用，不重跑无关项。总墙钟171.41秒；完整日志 `.codebuddy/work/00-scratch/tmp-20261010-tail276-rulers.txt`。
- `tools/mut/_mut_tail276.py` 最终rc0：隔离正常绿，旧金额误用/关联复制审批额/日期错误映射3项红，正式源码不作变异靶、测试库事务回滚。中途隔离导入路径与日期断言误取说明文字已修；最新测试同时覆盖真实项目建档路由、候选与项目导出、MOD-11导出、MOD-05注入、0→30000→50000→撤销回30000、统计手改45000而真实流水仍30000、改关联/解绑保留流水、手工付款与单查询批量取数。最新 `-m pytest backend/tests/test_tail276_jc.py -q` rc0；py_compile及node --check rc0。
- `ops/server_ctl.ps1 -Action restart` rc0。`tools/probe/_shell_smoke.py` 完整39段rc0、console/page错误0；证据 `.codebuddy/work/00-scratch/tmp-20261010-tail276-shell.txt`。随后 `tools/audit/shell_verify.py --snapshot`及普通核对均rc0。未再修改运行壳。真实CSS下检查手工建档弹窗、历史录入标准/最大字号；截图 `artifacts/_diag/tail276/project-live.png`、`artifacts/_diag/tail276/history-live.png`、`artifacts/_diag/tail276/history-largest-live.png`，未发现场数据写请求。隔离浏览器完成建档保存及历史合同保存、子表日期/来源/解绑显示操作。
- 边界：初始只读SQL因项目列名写错rc1，修正后rc0。未运行全185件pytest，按用户必要探索/按影响要求选测；未做双轴审查、未提交/推送/开分支或PR/自动销号。历史基数及截至日仍由人核对录入；有此前已扣付款时不要再次引用。无发票合同仍可能显示负欠款，待真实发票金额导入。本轮停在审查之前，由用户决定是否开启审查。

**2026-10-10 · 追加：历史汇总向所有项目开放。** 按用户要求（沭阳等有仓库项目也可使用）去掉新增合同勾选与默认值的仓库限制；默认不勾选，普通合同行为不变。新增有仓库项目浏览器回归覆盖勾选、取消及真实保存请求载荷；`-m pytest backend/tests/test_tail276_jc.py backend/tests/test_acc_jc_shell.py -q` 12项rc0，node --check rc0。隔离恢复旧仓库限制后新增用例红，反例脚本rc0；现场有仓库项目勾选/截至日显示通过，未发写请求，截图artifacts/_diag/tail276/history-warehouse-live.png。原dirty保留，未提交、未销号、未启动双轴审查。

**2026-10-10 · 追加核验收尾。** 本次完整壳自检39段rc0，console/page错误0，日志 `.codebuddy/work/00-scratch/tmp-20261010-tail276-all-projects-shell.txt`；随后壳基线快照rc0。字节/壳规则/接线/票结构检查均rc0。仅改开放勾选的两处限制及针对性用例，其他旧输入不重复核验。
