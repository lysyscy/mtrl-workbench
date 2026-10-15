# TAIL-301: 集采台账的行模板与合计下标也改成按列身份定位：加列/调序不再静默错位或错算

**What to build:** 集采台账的行模板与合计下标也改成按列身份定位：加列/调序不再静默错位或错算

**Blocked by:** None（可立即开工；与 TAIL-299/300 无耦合，先做哪张都行）

**Status:** done

- [x] 行单元格由列清单按 id 排列；隔离加列/调序后与表头逐格对齐，无需同步行串。
- [x] 合计列来自 domain.SUM_KEYS，按 id 查位；隔离加列/调序后金额与空格仍落在对应列。
- [x] 原列数/列序/单元格文字、交互和七列合计算法不变；相关回归及真机39段（含㉜/㉝）通过。
- [x] 新改判据同批隔离反向灵敏度、登记及覆盖台账一致；不写正式件或产品资料作靶。
- [x] 实际检查、未验边界落票；状态/架构/交接回写并销号，终轮影响入口 BAD: []；不提交不推送。

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：2026-10-11 TAIL-298 收尾双轴评审判断项（Standards 轴）；用户 2026-10-11 拍「可以另立票」｜不做会怎样：不做：加列/调序正是这张表下一次改动的形态 —— 表头、隐藏/钉列、导出都跟着列清单走，只有行模板的单元格串与合计行的列下标留在原地 ⇒ 行与表头错位、合计把别的列加起来，界面不报错（298 治的就是这一类静默错位）｜落点：backend/app/web/index.html（V.m11 行模板单元格串）· backend/app/web/shell/*（sumRowOf 调用处的下标映射 ↔ domain.SUM_KEYS）· backend/app/web/shell/pages-b.js（列身份出口）· backend/app/mod11_jc/domain.py（SUM_KEYS）· backend/tests（判据：行序与表头同源、合计按 id 查位）· ops/architecture.md 三节（列身份段补一句）｜阶段 / 时机：随时（调试期；A 案补口 —— 紧接 TAIL-298 做最省）｜**排期四问**（`§14.3` 同源）：四问：一 会真发生（加列/调序就是下一次改动）；二 真发生很难受且静默（行比表头少或多一格、合计加错列，界面不报错）；三 不做也能活，但每次改列要人肉数格子；四 更省的做法：行模板与合计都改成按列清单派生（或至少把列下标换成按 SUM_KEYS 查位），一次到位、无第二处口径

**2026-10-11 · 领票与取舍（agent）。** 选甲（真派生）：现有单元格按 id 绑定，排列仅由 JC_COLUMNS 决定；普通新增列按同名行字段生成，特殊控件仍按 id 定义其显示。SUM_KEYS 经列表 API 带到壳，合计按 id 查位，保留原七列取值与 N2/reduce 算法。相较乙，不新增一份需要人工同步的行序清单；加列/调序的隔离浏览器用例验证真实排列，故障由对应判据报红。范围只收 m11 两个遗留面，不改业务、文案、排序或产品资料。

**2026-10-11 · 办完与逐条证据（agent）。** ① `V.m11` 的原单元格改为 id 映射，按 `JC_COLUMNS` 排列；新增普通列由 `jcDefaultCell` 读 `adaptJc.columnValues` 的同名字段，不需改行串。② `service.build_list` / `api_list` 带出 `sum_keys = domain.SUM_KEYS`，`reloadM11` 原地接收，`jcSumColumns` 按 id 查位（控件列 +1）；原七列取值、N2/reduce、筛选含不纳入行的算法不变。③ `test_tail301_columns.py` 三条判据：域→API转发、真实行格、真实合计；浏览器演练调序与插入文本/金额列，逐格核 HTML/金额/空格。④ `_mut_tail301_columns.py` 临时后端副本内五靶独立命中：API转发漏键、装配漏键、行序固定、控件偏移错、付款误加发票；基线全绿、rc=1＋断言消息、MD5复原；已进 KEY/SLOW_KEY/隔离入口，台账一致。⑤ 已按协议追加已销号索引，README §〇/架构 §三/计划 §13.6 同批回写；销号由脚本完成，不提交不推送。

**实际命令与结果**：以下 `$PY` = `D:/dev/mtrl-workbench/backend/.venv/Scripts/python.exe`，Python均加 `-X utf8`；pytest工作目录 = `D:/dev/mtrl-workbench/backend`，其余 = 仓根。开工快照 `tools/oneoff/_run_rulers.py --start .codebuddy/work/00-scratch/tmp-20261011-301-entry.json` rc=0，只记开工字节。

| 实跑命令（Python命令由 `$PY` 执行） | 退出码与关键数 |
|---|---|
| `-m py_compile` 本轮改过的运行Python/测试/变异/登记件 | rc=0；含中文件编译通过 |
| `-m pytest tests/test_acc_jc_shell.py tests/test_ux_pages.py tests/test_tail04_pages.py tests/test_tail298_columns.py tests/test_tail290_jc.py tests/test_tail301_columns.py -q --tb=short -o "addopts=-p tests.acc_plugin"` | rc=0，58 passed，9.08s；日志 `.codebuddy/work/00-scratch/tmp-20261011-301-pytest.log` |
| `tools/oneoff/_run_muts.py --cases _mut_tail301_columns.py` | rc=0，5/5命中，27.9s，BAD: []；日志 `.codebuddy/work/00-scratch/tmp-20261011-301-mut.log` |
| `tools/audit/mut_cover.py` / 同命令 `--check` | 均rc=0，123件台账一致；生成物不手改 |
| `powershell -NoProfile -ExecutionPolicy Bypass -File D:/dev/mtrl-workbench/ops/server_ctl.ps1 -Action restart` | 两次rc=0；运行Python改后已重启，/app=200 |
| `tools/probe/_shell_smoke.py`（子进程设Playwright缓存路径） | 修复后rc=0，39段，㉜/㉝绿、console/page错误无；日志 `.codebuddy/work/00-scratch/tmp-20261011-301-smoke-final.log` |
| `tools/audit/shell_verify.py --snapshot` / 默认复核 | rc=0，逐行差0；后续影响入口再盖最新章 `20261011-2339` |
| `tools/audit/syntax_audit.py` / `tools/audit/bytes_guard.py --paths` 本轮11件实现/测试/登记/票 | 均rc=0，必须修0；B1–B4通过；收尾文档字节由终轮再验 |
| `tools/oneoff/_run_rulers.py --since .codebuddy/work/00-scratch/tmp-20261011-301-entry.json --explain` / 去掉 `--explain` 实跑 | 均rc=0；129个测试文件，隔离pytest rc=0（131.54s）；完整39段真机rc=0（86.44s）；总墙钟253.10s，BAD: []；日志 `.codebuddy/work/00-scratch/tmp-20261011-301-rulers.log` |

影响入口实际检查：doc_audit / audit_drift / audit_meta / audit_work / syntax_audit / bytes_guard / ui_parity / wiring_audit / chain_audit / asset_audit / claim_audit / prg_form_audit / mut_cover；均必须修0或一致。登记入口与gatescope自测rc=0；自测中「陈旧名单/未知参数」是隔离拒绝反例，不是生产失败。黄档如实保留：doc疑似49、drift43、meta54、work4；不称零提示。入口真机完整证据 `.codebuddy/work/00-scratch/tmp-20261011-233928-shell-smoke.log`。原有21格 `<td>` 源码与HEAD按多重集比对一致，文字/class/style/控件没改；`git diff --check` rc=0。

**失败与补修**：首跑真机rc=1，㉓五项合计为空；原因是我只加了装配层字段，漏了API显式转发。新增端点断言在修复前rc=1（`API must forward sum_keys`），补转发、重启后相关58项/变异5靶/完整真机均复绿。另一次从仓根错误指定 `tests/...` 的调用没有收集测试，已在backend正确复跑，未计作通过。

**未验边界**：本轮没有运行整套pytest刷新权威四态；使用隔离选集出口。真机使用本机当时现场数据，其他规模未验；Excel已由既有290回归核到实书值/列序/格式/合计，没有额外做人眼版式比对。未动其他页面、排序内核、业务规则或 `delivery/`，无越界改动；无新特殊控件或新编辑功能。相关读取按AGENTS指针：四份指定资料、MEMORY、IDE §十/十一/十五/十六、细则判据/工具节与前端守则；文档收尾查治理与README格式，不满仓搜索。

**终轮回执落点**：全部收尾文书一次写完后再执行同一影响入口；完整输出保存在 `.codebuddy/work/00-scratch/tmp-20261011-301-final-rulers.log`，以实际退出码和 `BAD: []` 为准；最终汇报不把待执行命令报绿。

**2026-10-12 · 一轮双轴评审与两票合并核验。** 用户授权：301做一轮双轴评审并修复，然后提交、推送299与301。基点HEAD `2df035b0a1376351c64f95a18f82aa2ed64665d9`；只审301增量（含两件新文件），299独立评审结果不混入。按code-review技能并行只读：Standards 0条（无硬违规或值得处理的启发式问题）；Spec 0条（五项验收已实现，无行为改变或越界）。无代码修复项，未开第二轮。既有选甲理由仍成立：行格与合计都真派生，列身份只有一个主人。

实际新跑：绝对venv解释器加 `-X utf8`，backend目录下 `-m pytest tests/test_acc_jc_shell.py tests/test_ux_pages.py tests/test_tail04_pages.py tests/test_tail298_columns.py tests/test_tail290_jc.py tests/test_tail301_columns.py tests/test_layering.py -q --tb=short -o "addopts=-p tests.acc_plugin"`，rc=0，73 passed/12.32s。仓根 `tools/probe/_shell_smoke.py` rc=0，实际39段（含㉜/㉝）、console/page错误无，服务与磁盘20列一致；`tools/audit/shell_verify.py --snapshot` rc=0，基线20261012-0741。`tools/audit/syntax_audit.py` rc=0/必须修0；`tools/audit/mut_cover.py --check` rc=0/124件一致。完整输出见scratch `tmp-20261012-301-review-related.log`、`tmp-20261012-301-review-smoke.log`、`tmp-20261012-301-review-syntax.log`。

本轮只回写评审/授权/交接记录，统一299/300票及新变异件 `_mut_layering.py` 的CRLF；未改运行代码或判据语义。301隔离5靶相关输入未变，复用已实跑自证；新变异件行尾统一后再实跑 `tools/oneoff/_run_muts.py --cases _mut_layering.py`，rc=0、25.4s、BAD: []，仍覆盖62次隔离检查（日志 `tmp-20261012-301-review-mut.log`）。未全套刷新权威四态，未验边界沿用两票原记录；300仅清单订正及行尾统一，未实施。文书一次写完后，以 `tools/oneoff/_run_rulers.py --since .codebuddy/work/00-scratch/tmp-20261012-301-review-entry.json --explain` 选范围、去掉 `--explain` 实跑；最终回执落在scratch `tmp-20261012-301-review-final.log`，以实跑rc/BAD为准。提交前便宜检查及真实pre-commit仍须通过；提交/推送的SHA以Git记录和最终汇报为准，原先“不提交”是当时授权边界，本次用户已明确变更。
