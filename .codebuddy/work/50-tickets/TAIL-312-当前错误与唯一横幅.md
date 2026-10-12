# TAIL-312: 加载恢复清除当前错误并维护唯一横幅

**What to build:** 串行重试成功后清除该路过期错误，其它失败仍可见；提示横幅只有一个，技术明细留在折叠区。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 同路连续失败只保留最新的人话与技术两半，串行失败→成功后两半都消失，另一失败仍保留；boot 的“当前登录用户”soft 路径也能进入/退出当前横幅。BOOT_ERROR 仍为字符串。
- [ ] 重复同步后横幅节点最多1个，全部恢复后为0；当前 Map 为真源，fails/failsTech 只由当前错误派生，不再累计历史。移除横幅不能被 if(BOOT_ERROR) 空值分支跳过。
- [ ] pageState/retryPage 的逐页隔离与现有 loading/ready/error 行为保持，失败页不拖垮无关页。LOADED缓存、PENDING、LOAD_DEP两组次序、ALWAYS_FRESH的m02以及写后reload/markCrossPageStale保持。
- [ ] 隔离浏览器走查有错/重试/恢复：横幅在 main 内 #view 前的布局流里，按钮可点击，技术明细默认折叠，人话与下一步沿用既有出口；业务面不显示原始技术串。
- [ ] 相关定向壳回归与受影响语义断言通过，结果写局部出口；本票不实现/不宣称 inflight 请求所有权或旧响应保护，不据此销号并发风险，不新建加载框架。

## 执行落点与最小方案

设计及取舍主人 = `.codebuddy/work/10-designs/设计-剩余重构最小方案-20261012.md` §3.3；状态与提示规则回 `ops/前端设计守则-以使用用户为中心.md` §0 / §9 命中的条款，上屏文字回 `.codebuddy/work/40-decisions/D29-文案审计口径-以熟手为准.md`。

`backend/app/web/shell/core.js` 的 soft 以 FAILED 路名→人话为当前真源，技术 Map 同步替换/删除；loadPaths/boot 收尾用当前快照重建 BOOT_ERROR 并同步横幅。bootErrorBanner 使用稳定节点标识 upsert，无错时移除，保留现有布局位置。使用局部函数/Map，不增加新脚本或错误中心。`backend/app/web/shell/view.js`、pageState、retryPage 的对外契约保持。

最低验证：复用 `backend/tests/test_shell_ui_workflow.py` 的隔离 ui_page 做失败→重试恢复、同路替换、保留其它失败与唯一节点回归；核对上述可见状态及点击。调整 `backend/tests/test_ux_errors.py`、`backend/tests/test_ux_states.py`、`backend/tests/test_wired_boot.py` 的受影响形态断言并保留原语义，定向核验 `backend/tests/test_wired_m02.py` 的 ALWAYS_FRESH、LOAD_DEP次序及写后刷新；不为旧字符串留住历史错误。必要反例按实际风险选，范围按 `ops/agents/issue-tracker.md` §四。

第二批在新对话独立执行；无技术前置。请求并发治理仍暂缓：实际 reloadM05 已隔离复现旧年份覆写新年份，不能只修改 LOADED/PENDING 收尾而宣称数据发布安全。真实39段与旧壳差58行不进入本票默认验收。

---

## Comments

**2026-10-12 · 建票（agent）。** 来源：用户2026-10-12确认三票两批；设计-剩余重构最小方案-20261012.md｜不做会怎样：重试成功仍显示历史错误，横幅重复占位｜落点：backend/app/web/shell/core.js｜阶段 / 时机：随时（第二批独立执行）｜**排期四问**（`§14.3` 同源）：①无技术前置②错误残留与重复横幅已隔离复现③前端独立批次④串行恢复、逐路隔离、唯一节点与相关加载规则可核验
