# TAIL-381: 普通表、虚拟行、显隐与缩放由同一布局收尾维持列宽、冻结及滚动

**What to build:** 普通表、虚拟行、显隐与缩放由同一布局收尾维持列宽、冻结及滚动

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 普通重画、虚拟窗口、显隐及resize共用隐藏→量宽→冻结收尾，页面BIND次数不增加。
- [x] 普通30行和虚拟450行的列几何、两轴滚动、列身份以及A项子表焦点草稿回归保持。
- [x] 用隔离副本确认去掉冻结收尾会被检出，资料同步、临时输出收口并本地保存。

---

## Comments

**2026-10-20 · 建票（agent）。** 来源：用户2026-10-20明确要求完成架构候选B和C｜不做会怎样：编排知识与事实读取散在调用者，后续修正容易漏路径｜落点：backend/app/web/shell/view.js、actions.js、core.js、index.html及布局行为回归｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：范围已授权；复用既有实现；分项验证；不改业务规则

**2026-10-20 · 实施范围。** 用户明确要求剩余B/C均实施，固定起点5d65aff、工作区干净；本票限定原报告对应区域，技术选择由Agent完成，不改业务口径、不扩为前端框架或通用数据层，不部署、不重启、不写生产。推送沿TAIL-380的自动审批受阻状态，当前没有向具体origin/master推送的新确认，不重试或绕过。

**2026-10-20 · B实施与验证完成。** `view.js::layoutTable` 持有hide→fit→pin次序，页面BIND之后及虚拟窗口更新均调用；`layoutTables`持有当前页及唯一120ms防抖缩放收尾。移除BIND、列显隐和另一个resize监听中的重复hide/pin。`saveTableScroll`接管m03/m11两轴快照，保留整表重画后恢复、滚动仅换tbody且不写回scrollTop的已有规则；脚本次序和页面BIND注册数不变。

- 首轮13项（新布局2项、test_shell_bind.py、test_shell_render.py）退出0；扩大到两轴滚动、金额编辑、A项子表与modal焦点50项退出0；30/450行夹具更正后两项复验退出0。
- 替代脆弱静态断言：列id/连续前缀仍静态核对；hide/resize/virtual窗口中的实测偏移与首列0由test_table_layout.py行为断言守护。临时网页副本仅删除layoutTable中的pin调用，同两场景均在真实几何断言失败（退出1）；母脚本确认命中后退出0，副本已自动释放，日志限期归档在本机.artifacts/archive/architecture-bc。
- 既有test_tail301_columns.py的列内容比较不再包含浮点left（此前HEAD的28/27.9844px误报）；只移除clone中的left属性，其余列内容与控件不变；冻结几何另有实测保障。该文件4项全部通过。
- 最终B/C累计命令：在backend目录用项目`.venv/Scripts/python.exe -X utf8 -m pytest`执行 `tests/test_table_layout.py tests/test_shell_bind.py tests/test_shell_render.py tests/test_shell_ui_workflow.py::test_通知书勾选后改付款金额保留两轴位置 tests/test_shell_ui_workflow.py::test_集采推进后保留横向位置_普通表与虚拟表 tests/test_shell_ui_workflow.py::test_集采推进后保留纵向位置_有无横向溢出 tests/test_shell_ui_workflow.py::test_集采保存后不被重画锚定向上拉动 tests/test_tail301_columns.py tests/test_ux_pages.py::test_集采台账行身份区钉列与隐藏列都按id定位_偏移必须量出来 tests/test_jc_subtable_refresh.py tests/test_modal_focus.py tests/test_candidate_reads.py tests/test_jc_link_recommendations.py tests/test_jc_auto_link.py tests/test_acc_jc_pay_link.py tests/test_layering.py -o addopts= -q --tb=short`，退出0，91 passed in 78.70s。其中B相关53项、C相关38项。C另见TAIL-382。
- 已看默认主题显隐、1120视口及450行虚拟窗口截图，表头与冻结区完整，合同号未被覆盖；截图由既有output器自动限期归档在本机.artifacts/archive/checks-20261020，各次retention.json管理；最终累计场景也含A项子表与焦点，不替代生产验收。
- 现行结构同步docs/architecture.md；未跑全量pytest、生产操作/重启、真实i8或实体打印；原抓取说明文字的旧断言不在本次改动和选集内。本次不推送，沿TAIL-380待具体远端目的地确认，不重复触发被拒绝动作。
