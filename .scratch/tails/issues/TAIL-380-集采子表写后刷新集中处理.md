# TAIL-380: 集采子表写后刷新集中处理

**What to build:** 集采子表写后刷新集中处理

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 新增和三种删除动作共用子表刷新，调用者不再保管跨刷新的行对象或重复拉取明细。
- [x] 保留真实列表重载的浏览器回归验证新行对象、金额、明细、删除身份及标题焦点；拒绝或异常不清空草稿。
- [x] 保持日期金额校验、取消不写入、付款引用和合同编号口径；相关检查通过，资料与源码保存状态据实记录。

---

## Comments

**2026-10-20 · 建票（agent）。** 来源：用户2026-10-20授权按架构检查首选直接开工｜不做会怎样：新增及三种删除动作重复处理行对象替换，测试未覆盖真实重载后明细与焦点｜落点：backend/app/web/shell/core.js、actions.js、proj.js及相关浏览器回归｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：四个调用者同一收尾；范围局部；复用现有金额和刷新规则；无其他业务前置

**2026-10-20 · 开工。** 基点a47a652；工作区干净。用户授权无需无关裁决直接实施；本票仅集中集采子表写后刷新，不扩展表格布局或合同候选读取。沿现有jcAct、列表重载及子表弹窗，不改业务规则、后端或生产服务；公共动作与浏览器回归按现有规则执行。

**2026-10-20 · 完成与验证。** `jcSubAct` 接管新增和三种删除的写后收尾；沿用 `jcAct` 权威重载，再按合同id找到新对象，`jcSubDlg` 返回并等待对应弹窗，明细只读一次。移除4处重复重找对象、重复明细请求和多余重画。新增成功清草稿，删除及失败保留草稿；原金额、日期、引用规则不变。现行架构说明同步至docs/architecture.md。原源码形态断言由真实行替换后的明细、金额回执、删除身份及焦点保障接替。

- 旧实现反例：`backend/.venv/Scripts/python.exe -X utf8 -m pytest tests/test_jc_subtable_refresh.py -q --tb=short`（backend目录）退出1；3种保存均多读一次明细（4次，预期本轮2+1），2种失败草稿场景通过。
- 修复后定向：同解释器运行 `tests/test_jc_subtable_refresh.py tests/test_modal_focus.py::test_子表删除中间行后回标题避免连续回车误删 tests/test_wired_m11.py -q --tb=short`，退出0，16项通过。
- 扩大验证：`tests/test_jc_subtable_refresh.py tests/test_modal_focus.py tests/test_shell_ui_workflow.py::test_发票子表新增草稿默认北京时间当日且可改 tests/test_shell_ui_workflow.py::test_集采保存后不被重画锚定向上拉动 tests/test_shell_render.py tests/test_tail301_columns.py tests/test_shell_api.py tests/test_wired_m11.py -q --tb=short`，退出1，65项中64项通过；仅列顺序旧断言失败，见下一条。
- 既有失败已独立复现，未改预期或跳过换绿：① `test_acc_jc_shell.py::test_触发方式写明且不许把人工说成自动` 仍要求已移除的“抓取一律要人点 / 本系统没有任何定时任务”，在内存拼接的HEAD全文上原用例同样退出1。该文件9项中其余8项通过。② `test_tail301_columns.py::test_rows_follow_columns` 比较outerHTML含实测left，28px与27.9844px不等；从HEAD导出独立web副本、通过MTRL_UI_FIXTURE_WEB跑同一节点，退出1并复现相同差异。它们均非本次改动造成，未纳入本票产品修复。
- 最终输入复验：新测试加默认主题、金额回执断言后，`tests/test_jc_subtable_refresh.py -o addopts= -q --tb=short` 退出0，5项通过；随后补的 `::test_删除已有行保留未保存的草稿` 单独退出0，1项通过。最终共75项不同检查中73项通过、2项上述HEAD既有失败；不宣称整组全绿。
- 默认主题的付款草稿、保存结果已实际看图：弹窗日期/金额/按钮清楚，无新遮挡；保存后主表付款12.34、欠款-12.34与子表一致，草稿消失且焦点安全。截图在本机 `.artifacts/archive/checks-20261020/233618-518403-8748/screenshots/` 的 `jc-payment-draft.png`、`jc-payment-after-save.png`，按该effort的retention.json到期处置。
- 沙箱内Python socketpair停在accept，尚未进入Playwright动作；停止两次挂起运行，受控诊断退出1后自动审查允许沙箱外假请求回归，测试可执行。诊断无业务请求。中间一次括号整合错误已由node --check定位修正，随后相关用例通过。
- 未执行全量pytest、真实i8/业务写入、数据库迁移、生产重启或真实用户操作验收；两个其他架构候选不在本票范围。保存授权沿项目workflow，提交与远端结果另记，不以测试替代部署。

**2026-10-20 · 收尾检查。** doc_audit与10件文本bytes_guard均退出0、必须修0；git diff --check通过。HEAD网页临时副本已删除，沙箱诊断按30天期限转入本机.artifacts/archive/jc-subtable-refresh/diagnosis；workspace_check closed退出0。截图由现有输出器自动限期归档，无活动effort输出遗留。

**2026-10-20 · 本地保存与推送受阻。** 主改动已提交6bf8291，真实pre-commit语法/字节/凭据检查通过。git push origin master两次均在执行前被自动审批拒绝，未发生远端写入；第一次因目的地未核实，随后GitHub连接器确认当前认证用户lysyscy及仓库owner同为83298716、私有仓库且有admin/push权限，再次审查仍要求人类明确确认该具体仓库master目的地。保留本地提交，等待用户对lysyscy/mtrl-workbench的master推送明确授权，不换工具绕过。生产重启与真实业务验收未做。
