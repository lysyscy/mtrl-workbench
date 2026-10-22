# 重构增量测试清理 · 2026-10-22

本批已完成用户批准的测试清理及项目级持久约束。清理起点 `46c5ff72e65386e0823f696a2768421cb3c18af2`、开工clean；范围用 `02a29b2^ = 290d1e54064bf21641af0f5f2f193cc29f2cb46d`（首个397实现的父提交）到46c5ff7确定。仅处理397/398及A/B、399、400、419地址切片新增或改写测试及直接夹具，没有扫描或删除更早历史业务测试、改产品代码、推进401或修改个人技能。

## 数量与取舍

函数数只计 `test_*`；用例数按pytest参数化行展开相乘，普通函数计1，函数内循环不另计。后端只计上述Git区间新增/AST变化的函数，不把整文件历史测试混入分母，也不叠加运行次数。此前已删的超长账号2函数/3例不重复计入。

| 同一范围 | 函数：清理前 → 后 | 用例：清理前 → 后 |
|---|---:|---:|
| 前端9个测试模块 | 73 → 48 | 98 → 49 |
| 后端增量（6文件内） | 13 → 12 | 15 → 12 |
| 合计 | 86 → 60 | 113 → 61 |

- 删除旧新界面三尺寸对照、主题/颜色/展示名文案与像素结构断言；删除跨页重复的账号暂停/迟到下载组合、台账同范围旧响应及复杂并发格值、鼠标事件时序探针。保留共享壳换号与实际HTTP权限、跨项目保存和草稿归属等必要代表。
- 台账身份恢复4例裁为同账号断网恢复1例；不确定撤销只留真实丢回执后读回1例，移除undo/redo×坏JSON形状4例。保存、中文输入、真实撤销重做、冲突/归属、金额空/零和真实文件导出继续保留。
- 地址丢回执3形状裁为缺ok的1例；保留正常/拒绝保存、取消、权限、清空回退、留痕及保存后读回失败。移除在途POST顺序/同值/缺行版本矩阵及专用线程池、4个控制端点和1个中间件所在的55行 `i8_settings_backend.py`，直接复用现有外部I/O封锁夹具；不撤销已完成的产品修复。
- 删除真实Vite StrictMode专用测试及服务夹具（端口探测、脚本/缓存、子进程等待与清理）；挂载不执行外部动作由保留的浏览器入口和较便宜后端保护验证。未新建测试或把多例拼成长脚本。
- 机械报表明细定位4组合裁为同名项目1条必要交互，删除同文备注专用项目及两类明细种子；网格/文件代表所需长表保留。移除浏览器遍历所有文件单元格的重复比较，保留独立金额、项目顺序、四页、公式与快照保护；既有后端文件/金额检查未动。
- 删除本次新增的0/22/126额外项目×两月份精确4次SQL矩阵（1函数3例），原有批量读取及开工月业务保障保留。后端其余增量是实际权限/外部误操作、时长/操作人、文件内容或隔离出口保障，保持原样。

## 实际验证与收尾

- `pytest apps/frontend/tests --collect-only -q -p no:cacheprovider`：退出0，49项/0.74秒，仅证明可收集。
- 只执行改写测试/夹具影响的9项：`test_i8_settings.py`全部5项、台账身份草稿恢复1项、机械网格/四页实际文件/同名定位各1项；`-q -s --tb=short -p no:cacheprovider`及JUnit输出，退出0，9通过/36.71秒。没有全页、全仓、计时对比或独立审查循环；其余未改保留测试复用原有效证据。
- 运行器仅从配置选取TEST_DATABASE_URL，先核 `mtrl_workbench_test/mtrl/pg_catalog`，再通过现有夹具创建3个独占schema；实际后端验证search_path等于各自schema，无public回退。正式DSN未进入子进程，真实i8/打印均封锁。结束只读确认3 schema已不存在、所属会话0、3 PID不存在、3端口关闭，未终止他人进程。
- 本批选择定向自查：累计变更限测试删减与项目文档、可逆，9项覆盖改写接缝；不改变生产行为，语法/字节由真实提交钩子验证。没有新增测试平台/门禁、依赖或发布动作；不push/部署/正式DB写入/外部i8/同步/打印。
- 长期取舍唯一正文：[workflow.md §三](../../docs/agents/workflow.md#三取舍本项目够用即止)，[AGENTS](../../AGENTS.md)明确实施开工先读；project-rules与本spec用短指针消费，已收敛历史“所有修复永久回归”、多轮计时及后端默认全量要求。writing-for-agents用于指针和单一正文，未更新个人技能。
- 原始收集/选集/JUnit/数量/资源核验及提交钩子日志选留 `.artifacts/archive/frontend-vue-rewrite/test-cleanup-20261022/`，沿原retention至2026-11-21；本轮截图/测试导出/work和一次性脚本释放，旧归档证据不动。最终提交、clean与run-closed结果回交付回执；整个重构仍活动，不执行effort closed。

未跑全部保留测试、未重建未变化的前端产物；不宣称完整新前端或人工验收通过。398/400仍待整页人工验收，419整票未完成，401未推进。

---

以下保留先前小批次的当时证据；其中测试数量、选集和“全部断言保留”不代表清理后的当前覆盖。

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


## 2026-10-23 i8人工反馈有界修正

旧可见渲染依据：`backend/app/web/shell/view.js:17-18,34,64-76` 区分m02/m03导航并将页标题与身份放公共顶栏；`backend/app/web/index.html:1040-1046` 的 `V.m02` 顺序为引导、抓取结果回显、执行记录，`:764` 的 `fetchNt` 位于 `V.m03`。`backend/app/web/shell/core.js:1322-1338` 在回显卡h4存在且尚未注入时添加“i8 连接设置”；这证明旧代码有入口，不证明用户当前需要它，也不足以断言注释过时。本轮只核旧源码渲染条件，隔离预览不开放旧/app，未冒称一比一看过旧运行画面。

删除i8页付款抓取和配置整区；清理i8-settings/i8-execution、仅它们使用的前端解析/错误标志/CSS，以及5个地址测试＋7个失去页面入口的抓取测试（共12函数）；固定响应夹具退出长期测试树，现有8037预览仅在自有run/work保留临时副本直至用户结束。未新增永久测试。共享后端和迁移不变，旧测试结果保留为历史、不冒称当前保留覆盖。

`npm run typecheck`、`npm run build`退出0。复用现有8037与真实业务副本，单次只读Playwright冒烟通过：两区无入口、结果/记录保留、标题身份同排、禁用撤销重做位于身份左侧、动作筛选可用、页面错误0、业务POST 0；本机修正版截图已目视。原图Library返回云端路径本机不可见，未看到原图。产物归现有`.artifacts/active/frontend-vue-rewrite/i8-human-preview-20261022/reports/smoke-correction.json`与`i8-corrected.png`，进程/schema/停止方式归同目录preview-handoff。未重启、重复制或删除用户预览数据；运行中不执行run-closed。当前差异局部可逆且无后端/资金写入，定向自查足够；按用户要求不追加独立审查循环。未push/部署，400待用户复看、419地址取消/其他待做、402未实施、401未推进。
