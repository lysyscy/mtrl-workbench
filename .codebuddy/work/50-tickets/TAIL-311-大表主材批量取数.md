# TAIL-311: 活动大表主材同会话批量取数

**What to build:** 活动大表与导出保持金额、选题和顺序，每次组装只在同一会话批量读取一次主材结算事实。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 多项目/合同、有无贸易公司、两类发票及 TAG_IN/非 TAG_IN 的结果符合独立手写 Decimal 期望；有贸易公司只取贸易发票，无贸易公司只取供应商发票；项目键仍为仓库名、结算不按月切。
- [x] owner 输出与既有 MOD11 结算行及 build_big_data 的 mat_cum 对齐；使用调用者同一 Session，flush 未提交发票后大表即可读取新额，不另开 session_scope，不调 build_list/payments_of_many。
- [x] 1个与多个项目的主材查询次数固定，不随项目数增长；空项目集合不读取合同/发票。显式端口 None 对应值 None/mat_available=false；正常无纳入合同对应0.00；读取异常继续失败，不伪装0。
- [x] 选题、行序、手填带入、合计、API响应及导出映射保持；当前壳 reloadM07/bigRows 保持，不顺带改用 bg.rows。迁移后只剩测试使用者的 main_material_total 删除，口径断言迁到 owner，不维持死 helper 或重复算法测试。
- [x] owner/build_big_data 的定向隔离金额与会话场景、相关已有大表/导出及分层检查通过，结果写局部出口；不改壳、模板、公共 workbook 或通用测试架构。

## 执行落点与最小方案

设计及取舍主人 = `.codebuddy/work/10-designs/设计-剩余重构最小方案-20261012.md` §3.2；业务规则回 `delivery/材料科业务全流程说明书.md` §5.7.1 / §6.4.2–6.4.4，以及 `delivery/PRD/02-功能规格/MOD-07.md`、`delivery/PRD/02-功能规格/MOD-11.md`。

- `backend/app/mod11_jc/service.py`：增加 settlement_totals_by_project(s, warehouse_keys)，一次 list_contracts(tags=[TAG_IN]) + 一次 invoices_of_many，复用 `backend/app/mod11_jc/domain.py` 的 settle_amount 逐合同归并；所请求键回 Decimal，两位精度，不读付款/展示事实。复用 `backend/app/mod11_jc/repository.py`，不新增查询框架、缓存或预计算表。
- `backend/app/mod07_setl/big_service.py`：MAIN_MATERIAL_PORT 回调改 (Session, 仓库键集合)→映射，setter 仍可显式 None；默认回调延迟委托 owner，_amounts 在项目循环前调用一次。定向符号核实未发现本件以外的生产单仓回调调用者，无需双签名兼容层。
- `backend/app/mod07_setl/big_domain.py`：仅处理迁移后死 helper；build_big_data 与 `backend/app/mod07_setl/api.py` 响应契约保持。当前前端忽略 bg.rows 的证据见设计§1，优化后端取数不扩大为前端权威改造。

最低验证：复用 `backend/tests/test_acc_rpt_big.py`、`backend/tests/test_wired_m07_big.py`、`backend/tests/test_big_export.py` 的相关断言；在 owner/build_big_data seam 补一组真实测试库回滚场景，验证独立金额预期、未提交可见、固定读取次数及 None/0区别。对应 FakeSession 若需调整只改原夹具。必要反例按实际风险选择，核验范围按 `ops/agents/issue-tracker.md` §四。

本票与 TAIL-310 同属第一批，推荐紧随其后串行（共用 MOD11 service；无技术前置）。整批修错/测试/落账/提交在同一执行会话结束；不扩为真实39段、旧壳差58行或其它候选验收。

---

## Comments

**2026-10-12 · 建票（agent）。** 来源：用户2026-10-12确认三票两批；设计-剩余重构最小方案-20261012.md｜不做会怎样：逐项目新开会话并组装全量集采列表，重复读取无关付款事实｜落点：backend/app/mod07_setl/big_service.py；backend/app/mod11_jc/service.py｜阶段 / 时机：随时（第一批，建议TAIL-310后串行）｜**排期四问**（`§14.3` 同源）：①无技术前置②每多项目重复全量读取③与310共用MOD11 service④独立Decimal期望、同Session未提交可见与固定读取次数可核验

**2026-10-12 · 落账（agent）。** 紧接TAIL-310/543e519原仓串行；MOD11新增 settlement_totals_by_project(s, warehouse_keys)，一次纳入合同读取+一次所选合同发票批读，复用 settle_amount。同Session主材端口在项目循环前调用一次；不读build_list或付款事实、不新开会话，保留TAG_IN、贸易/供应商、Decimal两位、无合同0/不可得None和异常失败。前端、HTTP契约、模板和公共workbook未改。

**实际消费者补齐。** 定向符号核实发现历史只读工具 tools/probe/_probe_tail97_impact.py 仍调用main_material_total；同票迁到owner（调用保持在其已有会话内），历史待确认的假设迁移增量保留。随后删除旧helper与导出名，原001-05断言迁到owner interface，不保留第二套算法。该工具只跑内存隔离校验，未查询真实业务库。

**定向证据。** `cd backend; .venv/Scripts/python.exe -X utf8 -m pytest tests/test_tail311_bulk_materials.py tests/test_acc_rpt_big.py tests/test_wired_m07_big.py tests/test_big_export.py tests/test_layering.py -o "addopts=-p tests.acc_plugin" -q --tb=short`：59 passed、rc=0。新增4项真实隔离事务覆盖手写132.00/7.25/0.00、多合同/两类发票/两态、MOD11既有结算行对齐、flush未提交且未来日期发票后132.01、顺序/手填0带入/合计139.26、同Session仅一次端口、固定查询1项目=3/多项目=3（项目键/合同/发票）、空集合0查询、None/0与异常继续失败、API原derived金额字符串契约。首次API断言误以为扁平字段，已修正并复验；产品API未改。原大表/壳接入与成品导出断言保留。

**终轮与隔离。** 两票组合命令为上述311选集再加 tests/test_tail310_selected_pay.py tests/test_notice_action_api.py tests/test_acc_pay_verify.py，并加 `--junitxml=../artifacts/_partial_tail310_311.xml`：97 passed、8.33s、rc=0。结果局部出口 artifacts/_partial_acc_results.json 与 artifacts/_partial_tail310_311.xml，未刷新权威四态；新增夹具写前核实current_database=mtrl_workbench_test并finally回滚，应用业务库未写、无建库/迁移。源码py_compile、历史探针内存校验与git diff --check均rc=0。实际读取依据为AGENTS最小指针、定稿设计§3.1/3.2、两票、业务说明书§4.2.5/4.4.2–4.4.4/5.7.1/6.4.2–6.4.4、MOD03/07/11 PRD、Matt codebase-design/DEEPENING与writing-for-agents；主要工作在金额/会话定向场景，未做完整implement-spec或独立复核。

**提交与接续。** 本票正常钩子本地提交，实际SHA见Git与批次交付；未推送/部署/重启。下一批只做TAIL-312，沿用定稿设计§3.3与312票面，在新对话核实最新master/HEAD/工作区；不进入TAIL-284/287、统计写owner封装或请求并发治理。真实39段、旧壳差58行及现场样表边界继续未验；本批通过不代表发布通过，未测现场耗时。
