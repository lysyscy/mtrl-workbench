# TAIL-312: 加载恢复清除当前错误并维护唯一横幅

**What to build:** 串行重试成功后清除该路过期错误，其它失败仍可见；提示横幅只有一个，技术明细留在折叠区。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 同路连续失败只保留最新的人话与技术两半，串行失败→成功后两半都消失，另一失败仍保留；boot 的“当前登录用户”soft 路径也能进入/退出当前横幅。BOOT_ERROR 仍为字符串。
- [x] 重复同步后横幅节点最多1个，全部恢复后为0；当前 Map 为真源，fails/failsTech 只由当前错误派生，不再累计历史。移除横幅不能被 if(BOOT_ERROR) 空值分支跳过。
- [x] pageState/retryPage 的逐页隔离与现有 loading/ready/error 行为保持，失败页不拖垮无关页。LOADED缓存、PENDING、LOAD_DEP两组次序、ALWAYS_FRESH的m02以及写后reload/markCrossPageStale保持。
- [x] 隔离浏览器走查有错/重试/恢复：横幅在 main 内 #view 前的布局流里，按钮可点击，技术明细默认折叠，人话与下一步沿用既有出口；业务面不显示原始技术串。
- [x] 相关定向壳回归与受影响语义断言通过，结果写局部出口；本票不实现/不宣称 inflight 请求所有权或旧响应保护，不据此销号并发风险，不新建加载框架。

## 执行落点与最小方案

设计及取舍主人 = `.codebuddy/work/10-designs/设计-剩余重构最小方案-20261012.md` §3.3；状态与提示规则回 `ops/前端设计守则-以使用用户为中心.md` §0 / §9 命中的条款，上屏文字回 `.codebuddy/work/40-decisions/D29-文案审计口径-以熟手为准.md`。

`backend/app/web/shell/core.js` 的 soft 以 FAILED 路名→人话为当前真源，技术 Map 同步替换/删除；loadPaths/boot 收尾用当前快照重建 BOOT_ERROR 并同步横幅。bootErrorBanner 使用稳定节点标识 upsert，无错时移除，保留现有布局位置。使用局部函数/Map，不增加新脚本或错误中心。`backend/app/web/shell/view.js`、pageState、retryPage 的对外契约保持。

最低验证：复用 `backend/tests/test_shell_ui_workflow.py` 的隔离 ui_page 做失败→重试恢复、同路替换、保留其它失败与唯一节点回归；核对上述可见状态及点击。调整 `backend/tests/test_ux_errors.py`、`backend/tests/test_ux_states.py`、`backend/tests/test_wired_boot.py` 的受影响形态断言并保留原语义，定向核验 `backend/tests/test_wired_m02.py` 的 ALWAYS_FRESH、LOAD_DEP次序及写后刷新；不为旧字符串留住历史错误。必要反例按实际风险选，范围按 `ops/agents/issue-tracker.md` §四。

第二批在新对话独立执行；无技术前置。请求并发治理仍暂缓：实际 reloadM05 已隔离复现旧年份覆写新年份，不能只修改 LOADED/PENDING 收尾而宣称数据发布安全。真实39段与旧壳差58行不进入本票默认验收。

---

## Comments

**2026-10-12 · 建票（agent）。** 来源：用户2026-10-12确认三票两批；设计-剩余重构最小方案-20261012.md｜不做会怎样：重试成功仍显示历史错误，横幅重复占位｜落点：backend/app/web/shell/core.js｜阶段 / 时机：随时（第二批独立执行）｜**排期四问**（`§14.3` 同源）：①无技术前置②错误残留与重复横幅已隔离复现③前端独立批次④串行恢复、逐路隔离、唯一节点与相关加载规则可核验

**2026-10-12 · 开工（agent）。** 原仓单执行者，HEAD=5d2bd675bd736f19ba671cf9492738a1f7c5bbd1，工作区干净；只实施设计§3.3及本票，不派子代理、不建worktree。

**2026-10-12 · 落账（agent）。** FAILED按路名持有当前人话，FAILED_TECH同步替换/清除；syncBootErrors从当前Map派生fails/failsTech与字符串BOOT_ERROR。loadPaths及boot收尾都同步，身份失败晚到亦不遗漏；retryPage只清本页两半与缓存。bootErrorBanner以稳定节点更新，无错移除；既有布局流位置、转义、默认折叠与文案出口保持。历史执行记录/API排障原文未删改，不把历史技术串继续当当前故障。

逐条证据：①②新增隔离浏览器回归覆盖同路连续失败替换两半、串行恢复保留另一失败、重复同步最多1节点/全恢复0节点、字符串BOOT_ERROR、启动“当前登录用户”晚到及恢复。③既有pageState/pageGate/重试隔离及loading→ready断言通过，LOADED/PENDING/LOAD_DEP/ALWAYS_FRESH和写后刷新/markCrossPageStale相关断言通过。④默认主题下有错/展开/恢复截图已查看：main内#view前占位、重试与summary真点击、原始串只在折叠明细、HTML错误文本安全转义；截图为artifacts/_tail312-error.png、artifacts/_tail312-details.png、artifacts/_tail312-recovered.png。⑤最终五件定向文件加两条直接消费者断言共51项通过（rc=0）；局部出口artifacts/_partial_tail312.json及artifacts/_partial_tail312.xml。

命令：backend/.venv/Scripts/python.exe -X utf8 -m pytest backend/tests/test_shell_ui_workflow.py backend/tests/test_ux_errors.py backend/tests/test_ux_states.py backend/tests/test_wired_boot.py backend/tests/test_wired_m02.py backend/tests/test_ux_pages.py::test_启动失败横幅不许盖住内容 backend/tests/test_wired_m08.py::test_boot逐路容错 -q --tb=short --junitxml=artifacts/_partial_tail312.xml；仅子进程指定局部ACC_RESULTS_PATH、Playwright路径及内存数据库占位，浏览器请求由ui_page隔离，未连接真实业务库。沙箱Chromium未启动的两次进程已停止，不算通过；允许启动浏览器后首轮48/49，一条新增测试误把现有loading状态等同立即重画DOM，按既有渲染出口调整断言后49/49，再补两条真实消费者完成51/51。

核验范围：_run_rulers.py --explain（rc=0）保守列出88个壳使用者文件；按本票实际修改符号缩为上述定向组合，未把88件或全库报为通过。固定8项均通过：doc_audit、syntax_audit、bytes_guard、ui_parity、wiring_audit、asset_audit、claim_audit、prg_form_audit（各rc=0）；syntax初次因沙箱临时目录权限失败，换正常执行环境复验通过，未算假绿。文档必须修0/疑似51/豁免33，接线W1/W1b均0、W2一项为未改动mod06 available_months；未扩大本票清理。diff --check通过。新增浏览器回归使test_shell_ui_workflow出现行数黄提示；按本票要求复用既有ui_page，不在本批另扩拆件，黄提示未冒充已清理。实际读取设计§3.3、票、AGENTS触发入口、Matt codebase-design/DEEPENING与writing-for-agents；未调用完整implement-spec或独立复核。

边界：未改310/311、合同日期、i8匹配、view.js与历史诊断出口；未实现inflight所有权/旧响应保护，不销号并发风险，统计写owner和其它暂缓项不启动。真实39段与原壳差58行仍未验。未触碰真实数据库或付款，未推送、部署、重启；本轮三票到此收尾。

**2026-10-12 · 提交与推送。** 本票实现、测试和文档收尾同次本地提交，SHA见Git；真实钩子保留，未推送。
