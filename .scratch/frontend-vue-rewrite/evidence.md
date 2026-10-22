# 测试脚本小批次 · 2026-10-22

本批技术完成，待父任务审查；TAIL-400未启动，398仍待完整流水欠款页人工验收。固定基点为 `cfd74c4373cf33b271cdeb3b570150d4be0327b6`，开工 clean；仅在既有 `codex/react-frontend-rewrite` worktree 实施，无工具链更新、push、部署、正式重启或真实业务写入。

## 改动与取舍

- 同一测试模块复用一个 Playwright/Chromium，仍为每例创建并在 finally 关闭独立 context。模块结束关闭浏览器，避免同步事件循环跨模块常驻。pageerror断言保留，出错也释放context。
- 预览后端的日志、临时数据改为本轮run下按schema分目录；服务stdout日志也按schema命名，避免后模块覆盖前模块故障证据。EXPORT_ROOT仍只在本批exports内。
- 测试数量不变，下沉0、删除0。所有原 `test_*` 函数正文AST与基点一致；身份、金额、草稿、撤销、IME/焦点及真实XLSX断言均保留。纯HTTP权限例原本就不启动浏览器，无需再搬层。
- 未发现值得在本批改写的等待/定位；补充IME防抖例的400/850ms等待用于证明时间窗内没有请求，保留。未换TS runner、引入框架或建设通用计时平台；临时计时脚本已释放。

## 同组选集与测量

仓根项目Python `backend/.venv/Scripts/python.exe -X utf8 -m pytest`，向其传入以下10节点及 `-q --tb=short --durations=0`。本批另用临时pytest hook记录report.duration、夹具时间、context身份及捕获输出；比较六轮使用相同探针。

```text
apps/frontend/tests/test_preview.py::test_switch_account_drops_old_scope_and_late_response
apps/frontend/tests/test_preview.py::test_actual_permission_rejection_and_invalid_cookie
apps/frontend/tests/test_ledger.py::test_continuous_edit_real_save_and_readback
apps/frontend/tests/test_ledger.py::test_mouse_and_chinese_composition_survive_prior_receipt
apps/frontend/tests/test_ledger.py::test_saved_but_refresh_failed_does_not_resubmit
apps/frontend/tests/test_ledger.py::test_real_undo_redo_conflict_and_account_ownership
apps/frontend/tests/test_ledger.py::test_duplicate_add_stale_token_and_real_export
apps/frontend/tests/test_export_dialogs.py::test_two_independent_dialogs_preserve_scope_and_real_debt_file
apps/frontend/tests/test_mechanical_reports.py::test_grid_freeze_virtualization_scroll_locate_and_ime
apps/frontend/tests/test_mechanical_reports.py::test_four_real_sheets_file_order_money_formulas_and_snapshot
```

Python 3.15.1、pytest 9.1.1；复用原构建，六轮dist聚合字节SHA256均为 `989ee813430aee3f675c8c0b93152eaed0d6b22fa7e65dc529a03cca4db3eec8`。每轮独立pytest进程，每模块新schema/种子/FastAPI服务；未清空OS或数据库缓存，属于重复热运行，但包含每轮进程启动成本。

单位为秒。setup/call/teardown为各节点阶段求和；总计为pytest子进程墙钟，包含启动/收集，故不等于三阶段之和。

| 轮次 | setup | call | teardown | 总计 | 原始退出码 / 结果 |
|---|---:|---:|---:|---:|---|
| baseline-3 | 22.21 | 18.56 | 2.99 | 45.01 | 0 / 10通过 |
| baseline-4 | 22.26 | 19.21 | 3.19 | 46.12 | 0 / 10通过 |
| baseline-5 | 23.34 | 19.17 | 3.24 | 47.31 | 0 / 10通过 |
| optimized-1 | 18.52 | 18.55 | 1.53 | 39.86 | 0 / 10通过 |
| optimized-2 | 18.06 | 18.46 | 1.58 | 39.35 | 0 / 10通过 |
| optimized-3 | 18.46 | 18.09 | 1.57 | 39.39 | 0 / 10通过 |

总计中位数 **46.12 → 39.39秒**，减少 **6.73秒（14.6%）**。前波动45.01–47.31秒，后39.35–39.86秒，仅适用于本组本机输入。浏览器由9次启动减为4次，每轮仍为9个独立context、4个独占schema；初始Cookie/storage均空，同时存活context均为1。call阶段接近，收益主要来自启动与退出，不外推全套提速或runner优劣。

## 失败、补充验证与输出成本

- 断连前首轮 `baseline-1`：10通过，退出0，总94.53秒（setup52.67/call32.06/teardown6.54）。运行条件与恢复后明显不同，不纳入收益计算，也不称为清空缓存后的冷机测量。
- `baseline-2`：仅留下 `F.......`，执行连接断开，未生成终态报告；不作通过或计时样本。恢复后先核原PID18436/20216与服务已退、schema无会话，再按准确名字清理遗留 `frontend_rewrite_397_15dd1f7de7a943c9bec26f75bc8964fa`，确认消失。首次失败的内存捕获已丢失，原因仍不明；单节点诊断 `diagnose-switch` 退出0，恢复后的前后六完整轮也均未复现，未删改该断言或声称修复。后续探针已逐阶段落盘。
- 同一个受控pageerror探针前后都为预期退出1：2个call通过，首例teardown准确报 `batch context cleanup probe`。后例验证Cookie、storage、route及视口无污染；优化后 `shared_browser=True`、存活context=1。错误没有被吞掉，下一例仍可用。
- 受控失败定位都只需首次输出即可定位到browser_page的teardown，无额外归因重跑；原始日志均7586字节，没有定位轮次或输出量改善证据。未量测真实Token或缓存命中，不从字节数推算Token收益。
- `affected-extra`：退出0，8通过（30.23秒pytest/31.20秒墙钟），含初始身份失败、preview opt-in、身份草稿4种恢复、不确定撤销读回、中文防抖；至此六个受影响UI测试模块均有代表验证。1条Starlette/httpx弃用warning保留，未安装其建议依赖。
- Python编译已通过；最终暂存语法/字节由真实提交钩子核验，输出保留于上述本机归档的logs/commit.log。不以已有测试或本回执代替父任务审查。

## 隔离、收尾与未验边界

每次实际连接均为 `mtrl_workbench_test / mtrl`；唯一schema search_path不回落public，实际后端启动有核验。浏览器服务写入由独占schema保护，未借用pytest回滚。每个完整比较轮的schema ready/cleaned集合一致；原始报告记录所属进程与schema。

最终schema和预览数据库会话均0；历史PID有被AMD、Windows服务及Codex运行时复用的情况，按创建时间和执行路径排除并保留，未终止其他线程进程。早期原夹具对共享 `var/log/frontend-397` 的既有日志保留；优化后其字节摘要和mtime未变。14份重复导出和本批work（含临时脚本/后端临时数据）已删除，只留最后完整轮校验过的4份XLSX及必要日志、阶段报告、截图。

原始证据位于本机 `.artifacts/archive/frontend-vue-rewrite/test-opt-20261022/`，沿既有retention.json保留至 **2026-11-21**；未延长其他轮期限。`run-closed`退出0，active中的本轮已退出。整个前端effort仍在进行，保留本规格与证据，不执行整个effort的closed。

未跑全量、所有布局/缩放参数、真实业务数据、外部i8/打印、生产服务及TAIL-400；未重建前端，构建字节未变。模块内浏览器崩溃可能连带该模块剩余用例，未新增重启/重试机制。首次中断轮失败未归因是残余风险。

本批选择定向自查：三处小型夹具/工具改动、不变的业务断言、同组重复测量及异常隔离探针足以核局部风险；自查不冒充独立审查。父任务审查本批累计差异后决定后续，未新增技术大票或改变业务票状态。
