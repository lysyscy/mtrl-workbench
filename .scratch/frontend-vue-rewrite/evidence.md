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

## 2026-10-23 TAIL-401项目维护

授权与旧UI对照只回[本规格](spec.md#tail-401-单票接续)，逐项技术完成、审查及未验边界回[TAIL-401](../tails/issues/TAIL-401-项目维护与人工归属.md)。基点 `f667be4bdf25d34d51999b328d4caf6a1b40a4ef`，分支 `codex/react-frontend-rewrite`，开工clean；未clone/push/部署或调用真实外部系统。

- `node apps/frontend/node_modules/typescript/bin/tsc --noEmit --project apps/frontend/tsconfig.json` 最终退出0。首次未使用导入/类型收窄及本地模板拼写检查失败已修正；一次Vite误传`--root`被CLI拒绝，未产出构建，改回项目cwd命令后成功。
- 在 `apps/frontend` 执行 `node node_modules/vite/bin/vite.js build` 最终退出0，152模块；theme.css保持运行时路径，既有grid大chunk提示保留。构建仅供预览，未部署正式服务。
- 临时 `tail401-20261023/work/verify_preview.py` 实际8组检查通过，连接身份逐次断言 `mtrl_workbench_test / mtrl / 唯一schema`，search_path不回落public。仅从正式配置读取测试DSN，不传正式DSN给迁移或测试子进程，未读取生产业务数据。外部HTTP和打印均阻断，i8来源固定替身；首次缺测试地址使前端正确禁用同步，后续仅补 `http://fixed-i8.invalid` 并重启自己的合成预览。首次与修正后两次schema均由同一finally清理，不借pytest回滚覆盖浏览器写入。
- 浏览器使用CUA内置浏览器，实际旧/app只读观察＋新页真实交互；两个Excel均用openpyxl读取。API指定序导出「待指认乙、待指认甲」，浏览器筛选＋表头序导出「待指认甲、待指认乙」，均2行/9列。浏览器文件已移入本run证据，原下载清除。变更后的选择器实际显示「改后选择项」；原项目ID保持，公共台账继续读取。没有新增长期测试、外部替身或脚本。

本机原始报告和必要日志/两份合成XLSX归 `.artifacts/archive/frontend-vue-rewrite/tail401-20261023/`，沿既有retention保留至2026-11-21。8038本票合成预览结束后停止，专属schema、端口、临时work和下载均清理，run-closed结果见本回执后续落账。8037用户i8副本PID24988/session35463及其schema/数据保持，仍按原preview-handoff停止方式；新build可供父任务整合项目页预览，但该8037路由白名单仍会将项目页转到i8，不能把它报成401可验收入口。401人工预览需父任务在接续中按原边界另开或调整，未扩大现有副本写权限。

本票ready-for-human；用户睡眠授权只延后人工关口，不等于接受本页。没有未决新增业务规则；真实外部联调和人验收均未完成。自查范围及理由回原票；422最终累计审查保持。

收尾实测：两次自有schema及其数据库会话均为0，8038无监听，两个执行会话均退出0；PID24988创建时间未变。临时work和本票浏览器下载已删除，必要产物已归档，workspace_check.py run-closed退出0。最后自查补回包ord回写，使后端夹紧位置后输入显示实际保存值；最终type/build仍退出0，没有为此重复旧后端或全仓测试。

## 2026-10-23 TAIL-402付款通知基础处理

基点8f9837af8824436a98d8fef6c3d84eb6c4354b98、codex/react-frontend-rewrite、开工clean。范围/旧UI依据/未做票/自查及晨验收边界回[402原票](../tails/issues/TAIL-402-付款通知查询与基础处理.md)。旧合成`/app`已实际打开并看图，新页默认及抓取结果弹窗也已目视，未冒称生产画面或真实外部联调。沿当前安装的implement-solo-spec执行参考及writing-for-agents维护原票/规格；不更新个人技能。

- `node apps/frontend/node_modules/typescript/bin/tsc --noEmit --project apps/frontend/tsconfig.json`最终退出0；`apps/frontend`内`node node_modules/vite/bin/vite.js build`最终退出0，156模块；既有theme.css运行时路径及grid大chunk提示保留。首次可空表头TS错误已修；未安装依赖、未部署。
- 临时`verify_api.py`最终退出0，5组真实隔离后端/Excel代表核对通过，结果为`api-check.json`及`api-final.log`；金额和权限等未变后端保障复用既有400/401证据，不复跑全仓。新页面不包含金额写入；试制过的金额输入已裁出最终差异，后续维护/付款批次承接，不将试制时的成功保存计作本票交付能力。
- CUA内置浏览器操作与真实隔离后端组合验证，结果为`browser-check.json`。250行合成长表上先后勾选窗口外两行，共300.25元；返回保留勾选与底部位置；分类、撤销重做、剔除和仅所选恢复均经真实列表再读核对。搜索隐藏的勾选仍在汇总，直接批量动作禁用；普通剔除视图禁选撤单、可勾剔除行。抓取弹窗只由确认提交，固定在线冲突停止，重新勾选允许强踢后成功；挂载不发起抓取。
- 浏览器真实下载`browser-export.xlsx`以openpyxl读取，10数据行/16列、单据0240至0249与显示排序一致；API单独指定序导出为2行16列。原下载已移入本run证据。新页只读金额按分计算合计，不另造金额规则；分类/剔除/恢复及历史回放仍由原接口决定。
- 首轮夹具把app_settings.effective误当dict，导致绑定读取500；首次api.log和preview.log保留，已修为隔离进程固定I8_BASE_URL后重建自有环境通过。读后脚本首次把账号误期待为展示名，改为实际接口账号preview-admin后通过；不改产品规则。CUA月份fill只改原生显示而未提交React变更，改用原生月份键盘选择并核状态后完成冲突路径；实际发起的多一次固定2026-10抓取如实在调用记录中。

两次隔离均明确`mtrl_workbench_test`及唯一schema，search_path无public；只从正式配置读测试DSN，正式DSN未传子进程、未复制生产业务数据。8038归本run，真实外部HTTP/打印由既有固定替身阻断；两个schema及对应连接均为0、8038无监听、两执行会话退出0，`resource-check.json`记录精确schema。必要日志/报告/合成Excel已归`.artifacts/archive/frontend-vue-rewrite/tail402-20261023/`，沿effort既定2026-11-21到期，不续期；临时work、预览标签页及下载已清理，workspace_check.py run-closed退出0。8037用户i8副本PID24988创建时间2026-10-22 23:56:50未变，schema/数据/停止方式仍归原preview-handoff。

402状态ready-for-human，四项勾选只指技术覆盖；401同样待晨验收。403/404/405/406未实施或代签，金额维护/付款/打印全页能力未完成；后续由父统筹按原授权安排，本子任务停止。最终保存运行真实提交钩子，不push/正式部署；自查足够的理由回原票，422累计独立审查保持。

收尾静态：syntax_audit --staged退出0、必须修0。bytes_guard首次检出本次追加使evidence.md混行尾，已恢复该件原LF；最终字节与真实提交钩子结果见提交回执。


## 2026-10-23 TAIL-404批量付款

固定起点23319d408ad68ef7a02e954ad9a896168fc622b0、codex/react-frontend-rewrite、开工clean。完成范围、旧实际UI/事件依据、技术验收与晨间人工边界回[404原票](../tails/issues/TAIL-404-付款通知批量付款.md)。只做本票，未clone或推进405；原后端付款判定、事务与历史边界不变，API增补同源限制/方式及真实逐项流水凭据，旧客户端兼容。

- 最终TS7 `node apps/frontend/node_modules/typescript/bin/tsc --noEmit --project apps/frontend/tsconfig.json`及组件cwd `node node_modules/vite/bin/vite.js build`退出0；最终构建已在浏览器重载，既有theme.css与chunk提示不变。
- 临时verify_api.py最终退出0，4组真实隔离API检查见本机reports/api-check.json；首次登录路径错误导致匿名拒绝，未产生付款，api.log保留非零；api-final.log记录纠正后通过。第二条流水固定抛错的500是预期事务反例，全部回滚与统计原值已实查，未隐藏该日志。
- CUA内置浏览器实际旧/app弹窗及新页面/结果截图已在工具回显目视；代表交互与一次请求证据见reports/browser-check.json。双击仅1POST，实际流水FL202610230648334108、125.25元、方式其他、批次备注与请求号均由SQL核对。付款成功后固定阻断列表请求，成功回执和刷新故障区分；撤除阻断并重读成功，没有重付。表内拟付60.25跨页保留，取消后SQL为0流水。最终SQL全schema仅3条（API2+浏览器1），失败/移出目标无流水，见reports/final-db.json。
- 所有schema由既有isolated_database建立，mtrl_workbench_test/mtrl、唯一search_path且无public；最初导入错误/观察旧页/最终验证共3个自有schema，精确名字及清理回resource-check.json。I8Client构造和所有httpx出站被固定阻断，无真实i8、强踢、抓取、同步或打印；未复制生产业务数据。

自查基点与范围、审批工具后续已执行的准确状态、首次错误和未验边界只回原票。未新增持久测试、不跑矩阵或全仓、422累计独立审查保持。8037未被本任务操作；末次只读健康ReadTimeout且PID24988未查到，需要父任务核实用户预览，未擅自重启/重建。必要日志/报告归本机 `.artifacts/archive/frontend-vue-rewrite/tail404-20261023/`，沿既有2026-11-21期限，不延长；自有资源清理与run-closed结果后附。


**2026-10-23 · 本次收尾实测。** 3个精确自有schema及其应用连接均为0，8038无监听、会话81795退出0；临时work/脚本/故障开关和浏览器页已清，Network临时阻断已撤除。必要日志/报告已归上述本机archive，run-closed退出0。8037未操作，末查超时/PID24988未见的问题交父核实；不擅自重建或删除其数据。源码提交及真实钩子结果见最终回执，不push或部署。


### 2026-10-23 TAIL-406打印PDF与设置

本轮固定起点59197066390f700bdb8e57492bdf57c653eb36f3，串行技术交付和验证/首次失败/浏览器策略拒绝/资源收尾只回[406原票](../tails/issues/TAIL-406-付款通知PDF打印与设置.md)。必要原始日志及合成PDF/PNG在本机`.artifacts/archive/frontend-vue-rewrite/tail406/`，沿既有2026-11-21期限。当前停在406，待父架构检查和完整人工验收，不推进407。


### 2026-10-23 TAIL-407机械明细与有效月值

串行实现与技术证据、首次非零、13项现有检查、真实浏览器/SQL/四页文件和自有资源收尾只回[407原票](../tails/issues/TAIL-407-机械零租与月度明细编辑.md)。必要logs/reports/screenshots在本机`.artifacts/archive/frontend-vue-rewrite/tail407-20261023/`，沿既有2026-11-21期限；临时构建/脚本/下载和8038独立schema已清。ready-for-human，未代人工验收；8037 PID19956及其共享构建13文件保持，未开放机械页。407停下交父统筹408，本轮未推进408。


### 2026-10-23 TAIL-408 JSON明细录入

仅现行JSON路线的实现、旧实际UI依据、9项现有检查、真实预览/冲突/拒绝/独立月值/四页文件、首次非零及资源收尾只回[408原票](../tails/issues/TAIL-408-机械报表文件导入.md)。必要logs/reports/screenshots在本机`.artifacts/archive/frontend-vue-rewrite/tail408-20261023/`，沿既有2026-11-21期限；ready-for-human未代人工验收。8037原PID19956/schema/构建受保护，未开放407/408；不重启通用导入、不推进409，仅本地提交，未push/部署。


### 2026-10-23 合同关联弹窗人工反馈实施

本次仅按用户明确授权调整合同关联弹窗。用户于2026-10-23明确“OK，这里验收通过”，仅确认本小节合同关联弹窗（实现提交 `5f1f9caa68ff6a9f2cc9068f84c8332425e40300`）局部人工验收通过；不代表付款通知书整页、TAIL-403或整个前端重构通过，其余反馈及409未混入。局部组件以业务材料名为合同名称，合同号辅助；默认展开合同金额、发票总金额与供应商／贸易公司明细。推荐仍来自原后端，打开不选定；新增没有当前合同，修改分别显示当前关联与拟换合同。X、点外、取消统一退出，改过选择时同层确认放弃。保留未开／超开票、关联前欠款、统计付款及不一致可关联，关联未接付款登记。

验证：实际观察旧/app弹窗；独立HEAD bb199c49e63813c8b214b4c64e2c5014420446c9快照只叠加本次4个源码文件，未完成409源码未进入；typecheck/build最终退出0，保留既有theme.css/大chunk提示。CUA在自有8038专属test schema实际观察新增／修改、推荐不自动选、发票默认展开、X/取消弃选保留、点外关闭，各完成一次新增/修改关联；SQL两关系、0付款流水，金额不一致不拦截。未新增持久测试、不跑矩阵。必要日志/报告在本机`.artifacts/archive/frontend-vue-rewrite/contract-dialog-20261023/`，沿2026-11-21期限；浏览器截图在CUA回显目视，未导出本地截图文件。

审查：按workflow§四及本轮用户明确要求，使用code-review独立Standards／Spec双轴（各独立上下文，gpt-6.1-sol/high），固定基点与范围同上四文件，包含新文件全文。Standards初审0；Spec找出三处旧版提示/贸易发票保留遗漏，已修，原审查者定向复核关闭；最终两轴实质未决均0。金额计算及既有后端写入沿403已验证实现，不以构建/自查替代独立审查；不替代422累计评审和人工验收。

8037仅更新已验独立构建13文件，先资源后index并保留旧13资源供已打开页面使用，不重启，PID19956及原schema数据保留，健康/页面/资源哈希核对通过。用户刷新页面后可查看新增/修改效果，旧已打开页面不被强制刷新。自有8038两精确schema已清、浏览器页已关；临时构建/依赖/脚本随本轮run收尾，具体资源结果见resource-check.json。未执行真实i8、强踢、抓取、同步、打印、生产写入、push或部署。


## 阶段5A候选公共接线

原候选 `43c1da19bd4a971891fd359551210e662d410dd3` 已串行接入费用、收发结存及库存：`main.tsx` 持有懒加载、路由、材料与报表分组及账号树保活，临时补丁已退出。后台页沿hidden/inert及active/blocked暂停；换号由原账号树和QueryClient清理。机械挂载与history隔离未改。415最简整改 `05c30b86` 已包含，费用后端与 `3561c5f` 一致，无expected/锁行新协议。

当时实际类型/独立构建及定向Standards/Spec均通过；领域证据回412/414/415原票。普通IAB公共导航当时因临时服务首次失败及错误页data URL策略拦截未验，未重试该被拒动作或切换CDP；真实DB缺获准DSN仍未验。原始日志留候选 `.artifacts/archive/phase5a-wiring/verify`，原全文可从候选 `808c17e6` 的 `.scratch/frontend-vue-rewrite/phase5a-wiring.md` 取回。该旧过程资料不另建历史档案；当前接合及验证以下节为准。

## 阶段5AB串行整合

本批固定活动基点 `73ed77eaf0aab17d47dd985a0eca5cd3d70fbea9`，选择吸收干净候选 `808c17e6af6df9f9afeb7d032d89d6eb5b7fc859` 相对 `3561c5f` 的最终累计差异，未逐个cherry-pick。纳入415费用、412月报/提取、414库存、413大表、410过程资料五页；大表已有合计API透传随页面采用。公共main及库存定位接缝按活动73ed核对，原机械收口保留；本批没有组件替换。

415/414的独立候选内容分别归原票Comments，412/413/410继续由各自原票持有。三份非标准5A文件不复制到活动目录，其现行事实、有效验证与必要来源在本节及原票闭合；不另设治理或历史档案。五票原状态和未勾验收保留，真实DB及完整人工验收未通过。

开工原13项dirty已逐文件SHA256及逐hunk冻结于本机本轮recovery；本证据追加本批内容，机械源码补共享历史保护，均对HEAD与工作副本作相同变换；其余11件字节保持，两个受影响文件的原增删内容逐项一致，原13项全部留在未暂存区。最终保护、最小集成验证、独立双轴、成品和资源清理依据见本机 `.artifacts/archive/frontend-vue-rewrite/integrate-5ab/reports/delivery.md`。无push、主线合并、部署或8037/8047资源更新；真实DB无安全DSN，未读取主线.env，未执行已拒生产来源恢复夹具、真实i8/强踢/生产写入或物理打印。


本批最终验证：活动工作副本严格typecheck通过；不含.env及原dirty的精确暂存快照typecheck/build通过，保留既有theme.css运行时与大chunk提示。最小后端API合计透传1项、既有大表合计及过程差异成品2项离线通过，实际生成XLSX逐格核对，领域其余证据复用原票。独立Standards发现旧账号POST迟到401、Spec发现新页待核实状态可经机械旧历史入口绕过；分别补所属组件卸载AbortSignal、复用同一guards查询并在机械历史读取前/提交前双查，原审查者均定向关闭，无未决必要发现。普通IAB工具本轮不可用；合成交互结果、首次夹具错误和真正覆盖范围以本机delivery/browser-check为准，不冒称IAB或真实DB通过。无安全DSN的真实保存、权限、事务/回滚、真实业务文件、实体IME、本机200%缩放及完整人工验收保持未验。


## 组件库覆盖补齐（活动批）

基点 `2acab1de241d8410ff53c46ad6464fd2d2b14040`。用户已批准补齐真实漏项；不以标签替换率验收，409及原13项dirty继续保护。逐文件字节及原hunk保护在本机task-13本轮recovery，索引原为空。

| 位置 | 本批选择与理由 |
|---|---|
| contract-dialog 日期/截至日/寄回日，contract-subtables 三类日期，contract-tools 起点 | 换 BusinessDate，复用现有AntD日期面板；保空串及YYYY-MM-DD、禁用及草稿处理。 |
| projects 筛选/搜索/档案编辑/类型/指认/仓库/排序 | 换 Input、Select、Checkbox；排序仍用字符串和原离焦提交，不加Form或InputNumber。状态选择保在建蓝/归档灰。 |
| flow、notices 筛选及搜索，notice-payment 方式/备注，i8 记录筛选 | 换 Input/Select；保原筛选状态、金额字符串、手改方式与付款流程。共享项目选择和TimePicker不重写。 |
| mechanical 407/408 工具条/普通动作/明细增删/录入冲突选择 | 换 Button/Checkbox/Select/TextArea；冻结MechanicalWork、取数/采用/忽略逻辑不动。 |
| flow 生效/撤销，notices/付款弹窗审批与付款状态，i8 执行状态 | 换AntD Tag并复用现有语义色；撤销中性、完成绿、待处理/部分黄、失败红。 |
| projects 普通成功、flow 导出成功 | 接AntD App消息上下文，仅短暂成功用message；错误留原对象旁。 |
| 子表保存/抓取/批付/机械写入反馈及待核实/部分结果 | 留页内role=status/alert：有需处理清单、未保存输入或重读核对动作，toast会丢失持续上下文。 |
| 金额/IME/Tab/离焦草稿编辑器，AG Grid，必要文件input，静态/矩阵表 | 保留既有实现，现成替代不能减少业务自维护且可能损失已确认行为。通知书草稿混合字段和阶段6打印设置本批不重构。 |

实际视觉、交互、检查和独立双轴结果待本批结束补录；8047旧资源不能作为本批验证。


### 通知书与合同关联样板（待确认）

组件库覆盖其余草稿继续暂停。本次仅形成通知书页、合同关联弹窗及必要时间入口/外壳的独立候选；合成实例入口和固定源摘要见本机 task-14 唯一样板回执。类型、独立构建、IAB代表交互和定向独立设计/业务审查已完成，未连接真实数据库或代签业务验收。候选尺寸与视觉取向待用户确认，确认后再决定推广；409、原性能dirty和其余暂停稿保持原边界。
