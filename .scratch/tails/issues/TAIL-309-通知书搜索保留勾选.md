# TAIL-309: 付款通知书搜索保留勾选

**What to build:** 勾选付款通知书后，搜索、改关键词及清空搜索不取消已选通知书；隐藏选择数量真实可见，批量操作范围清楚，删除或失效项不会误操作。

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 先用隔离假数据复现旧实现搜索取消勾选，再验证修复后搜索、改词、清空仍保留选择。
- [x] 多轮加选、取消和全选只作用于当前可见候选；显示隐藏已选数量与全部已选金额。
- [x] 付款弹窗列出全部有效选择，按对应通知书提交金额；直接批量动作遇隐藏选择须先展示核对。
- [x] 重拉清理已删除及不再可勾选记录；付款窗口打开后批次变化须重新核对，不能串金额。
- [x] 重复渲染、同页导航不清选择；离页及整页刷新按现有约定清空；项目等业务筛选范围保持原语义。

---

## Comments

**2026-10-12 · 开工（Codex）。** 用户来源：付款通知书勾选一项后搜索取消勾选。独立 clone：`D:/UserData/Documents/Codex/2026-10-12/task-2/mtrl-workbench-notice`；分支 `codex/notice-search-selection`；基点 `f6e13b018501a8aba9d0ba4debd059759209f050`。`git clone --no-local --no-checkout` 建立，未使用硬链接或 alternates；未复制源工作区、.env、凭据、未跟踪或生产数据。该提交票仓未发现 TAIL-309；编号由委派预留，公共计划/索引由集成人统一处理。

**2026-10-12 · 范围与依据。** 已读 AGENTS、README 当前交接、主计划 §13.6/§15、issue-tracker §四、MEMORY、IDE-细节 §十/十一、前端守则 §0、D29、MOD-03 及相关壳/浏览器夹具。所需 code-review 技能未提供，按已有规则定点复核；docs-audit 与本次交互修复无关。`ntSearch → prunePick → ntHit(fNt)` 按带搜索条件的可见集删除已选 ID，为直接根因。现有项目/时间/分类筛选仍裁剪，搜索保留；离页/整页刷新不持久化。付款本来有逐行核对弹窗，可包含搜索隐藏的选择；改分类/剔除/恢复/打印/PDF 是直接执行，隐藏选择存在时先清空搜索查看再执行。全选范围保持当前 `ntHit(fNt).filter(ntSelectable)`。

**2026-10-12 · 完成待复核（Codex）。** 正式改动仅六个壳文件（45 行新增 / 13 行删除）、一个 11 项浏览器回归文件及本票。未改 index.html、后端、主计划、公共索引；无提交、暂存、推送、部署或服务启动。`ntSearch` 不再裁剪；`prunePick` 排除搜索条件且维持业务范围；`reconcilePick` 在普通重绘与批量入口清实际失效项。隐藏提示显示「当前列表外 N 条」、全部已选金额，并提供清空搜索核对 / 清空勾选。直接批量动作的按钮和入口均按隐藏选择核对，付款弹窗含全部已选候选。另补 `payBatchIds` 核对窗口与提交行序：删除/撤单导致批次变化时先重建窗口，避免上一行金额错用到剩余行。保持同页导航选择，真实离页与整页刷新清空。

**2026-10-12 · 运行证据。** 本任务独立 `.venv` 使用 Python 3.14.7（系统可用版本；源仓约定为 3.13，未借用其环境），依照 requirements.txt 安装锁定依赖，Playwright 1.62.0 使用 `C:/ProgramData/ms-playwright`。首次沙箱内浏览器未返回，停止后经正常审批运行隔离浏览器。所有页面由原有 `ui_page` 拦截器提供 clone 文件；接口回包为假通知书，写出口捕获参数，未访问真实服务或数据库。

- 旧壳：`.venv/Scripts/python.exe -X utf8 -u -m pytest tests/test_tail309_notice_selection.py -x --tb=short`，搜索后选择 `['101'] → []`，1 failed，3.32s；隔离 HEAD web 再验同一判据仍红。
- 新回归首轮：9 passed，20.86s；既有触达回归首轮：67 passed，69.63s；补充读取失败/陈旧 ID 后终轮为 **190 passed，96.95s，rc=0**。
- 终轮（backend 为 cwd）：`.venv/Scripts/python.exe -X utf8 -u -m pytest tests/test_tail309_notice_selection.py tests/test_shell_bind.py tests/test_tail282_pay_draft.py tests/test_shell_ui_workflow.py tests/test_wired_m03_pay.py tests/test_wired_m03_pick.py tests/test_wired_m03_print.py tests/test_tail292_nav.py tests/test_shell_render.py tests/test_ux_states.py tests/test_wired_m03_action.py tests/test_wired_m03_list.py tests/test_wiring_guards.py tests/test_ux_buttons.py tests/test_ux_text.py tests/test_ux_colors.py tests/test_ux_feedback.py tests/test_ux_pages.py tests/test_ux_numbers.py tests/test_theme.py tests/test_ui_scale.py --tb=short --junitxml=../.codebuddy/work/00-scratch/tail309-final-regression.xml`。
- 反向灵敏度：`.codebuddy/work/00-scratch/tail309_sensitivity.py` 在隔离副本串行运行；HEAD 搜索、绕开隐藏核对、移除付款行序核对、绕开失效清理 **4/4 抓到预期 AssertionError**（各子测试 rc=1，驱动 rc=0）；正式代码未变异。证据：`00-scratch/tail309-sensitivity/results.json` 及四份 log。
- 默认主题的隔离实屏：`00-scratch/notice-selection-visual/hidden-1440.png`、`hidden-1024.png`、`payment-preview.png`。已看图，隐藏数量/金额/清空入口及付款窗口完整；选择条 scrollWidth=clientWidth（1164/748），付款按钮在视口内。首次窄屏溢出已局部修正。
- 离线审计：syntax_audit（3.36s）、本次八文件 bytes_guard（0.13s）、ui_parity（0.22s）、prg_form_audit（0.17s）均 rc=0 / 必须修 0；`git diff --check` rc=0。证据在 `00-scratch/tail309-audits/`。

**2026-10-12 · 既有审计边界与交接。** `wiring_audit` rc=1：W1=0、W1b=12、W2=81；与本 clone HEAD 的独立全量 Git archive 比较，规范化根路径后报告完全相同（非本轮引入）。`asset_audit` rc=1 是直接读取 `.env` 时 FileNotFoundError；HEAD 隔离副本同样失败。本任务明确禁止复制凭据，未为该审计借用或补入真实配置。对照证据：`00-scratch/tail309-audits/baseline-comparison.json`。自动影响入口 `--explain` 已查明推荐消费者；实际按上述触达范围验证，没有执行会访问运行服务/数据库的完整 `_shell_smoke.py`，也未运行 shell_verify `--snapshot` 或刷新完整权威四态。没有功能修复阻塞；真实服务集成、全壳现场验收与公共票索引收尾留给集成人。ready-for-human 表示未提交待复核，不表示部署或现场验收已完成。

**2026-10-12 · 独立复核后授权本地提交。** 集成人反馈「TAIL309独立复核无阻断」，明确授权仅八文件本地提交；禁止推送、部署、改公共索引或复制真实 `.env`。据此进入提交收尾，票仍为 ready-for-human，等待主仓整合与目标 Python 3.13 复验；本 clone 不重复建环境。新 clone 未配置作者身份，沿用基点 `s-cy <s.cy@local>`，仅对提交进程提供身份环境变量，不修改 Git 配置。

**2026-10-12 · pre-commit 实际结果与边界。** 通过 `ops/install_hooks.ps1` 安装仓库原钩子，真实 `git commit` 触发后未提交：`syntax_audit --staged`、`audit_work`、`bytes_guard --staged` 通过；`doc_audit` 与 `audit_meta` 各 rc=2（缺少 PRD_ACCEPTANCE_BASELINE 判据基线配置），`mut_cover --check` rc=1（生成台账不一致）。在完整 HEAD archive 内分别重跑，三项退出码及规范化报告均与当前一致，证据 `00-scratch/tail309-audits/precommit-baseline-comparison.json` 及对应日志；没有修补公共台账或借入环境配置。按本轮允许准确记录隔离跳过项及限定八文件的授权，仅本次采用临时钩子执行前三项适用检查，明确打印其余三项未完成 / 既有非绿原因；提交后恢复 `ops/hooks/pre-commit` 原字节。不使用 `--no-verify`，不声称完整原钩子全绿；190 项行为/界面回归、4 项反向检查及 wiring / asset 原有边界保持不变。实际提交 SHA 与父提交以 Git 和交付回复为准。

**2026-10-12 · 主目录最终整合与收口。** 源clone干净、codex/notice-search-selection、8件提交41088fcfbe95cb9d2a0641ebdc07ff8467adbd6e/父f6e13b0已核对，从本地无冲突取入01e22581c85ae63c71b953b02b369978b30f3081，接在a5be5d7→551174a→a8ccd00之后。六件壳JS保持源实现；只补本票已有测试中的550行虚拟表/最大字号两个最小用例、仓内可重复四反例及治理登记，不追加优化。主原钩子SHA256=b31e6015c7ce2702b3294736259814c8ac3b859468841566dcf7ecf46461bd12，始终未替换或削减；clone临时钩子记录是源阶段历史，不能作为主仓绿证据。

**单次真实最终代码结果。** 主仓Python3.13.14：`backend/.venv/Scripts/python.exe -B -X utf8 .codebuddy/work/00-scratch/tmp-20261012-tail309-combined.py`，原306–308组合130件完整包含，加共享壳实际消费者及源21件触达回归，共158文件；单次pytest1320通过、0失败/错误/跳过，240.99s，rc=0。测试HEAD=01e22581c85ae63c71b953b02b369978b30f3081，额外测试差异和全部输入SHA已保存；正式app/tests和临时副本逐字节一致，前后未变，没有还原登录逻辑。完整输出/JUnit/源码快照与diff：`artifacts/tail309-integration/pytest-output.txt`、`artifacts/tail309-integration/junit.xml`、`artifacts/tail309-integration/result.json`及input-snapshot.json/input-diff.patch。假i8、假会话/用户、实际测试库严格限定127.0.0.1:5432/mtrl_workbench_test；生产凭据不复制，真实付款接口不调用，浏览器全用假回包捕获写出口。

**必要风险证据。** 搜索/改词/清空保留、当前可见全选、隐藏数量及全部已选金额、直接批量动作先核对、付款窗口全体与对应金额、删除/撤单行序变化须重核、陈旧ID清理、业务筛选与离页清空全部通过。正常13通过26.06s，四靶明确AssertionError（恢复旧含搜索裁剪、绕过隐藏核对、移除付款行序、防失效清理），复原13通过27.10s；正式壳字节未变，完整反向回执`artifacts/tail309-integration/mutations.json`。首次反例只恢复搜索调用却被新裁剪规则保护，不算命中；改为完整还原旧缺陷两处后重跑4/4。新增两个用例同时检验550行实际虚拟表、标准1440与最大字号1024，已看四张真实截图：隐藏范围/总额清楚，核对与付款按钮完整，弹窗包含两条不同选择。截图在`artifacts/tail309-integration/visual/`，未重设计既有付款弹窗。

**原仓检查与真实边界。** 主素材审计实际rc=0（原全部规则和主路径，仅提供原.env中唯一所需非秘密PRD_ACCEPTANCE_BASELINE键，未打印凭据）；主装配审计及a8基线均rc=0，完整JSON完全一致，不能沿用clone的非绿结论。回执`artifacts/tail309-integration/boundary-audits.json`。索引由原_tail_open在隔离副本干跑/应用/T6核验后转入，原票Comments保留；四反例登记并生成132件覆盖台账。实际最终适用检查及shell_verify结果保留在final-checks.json；正常主仓最终提交的完整原钩子输出另存commit-hook-output.txt/commit-receipt.json，不能拿审计结果代替。

**未验与交接。** shell_verify只读检查与旧壳基线差58行（本次有意13删/45增），rc=1；没有--snapshot盖章。全站39段_shell_smoke需要运行中服务，当前授权禁止真实服务/付款操作，因此未执行，不伪称现场全绿；隔离浏览器并不替代此边界。没有部署、重启、推送或刷新完整权威四态，运行服务仍旧版本。原284/287及其余B2/B3/B4/B5未动；用户明确本批之后停用dot开发、改为自行串行修改，完成本批即停，不另开工作。306–308既有8/7/9反向输入未改，可沿用已核验回执；本次组合已含相关行为。最终本地提交及源码绑定在final-commit-binding.json。
