# TAIL-299: 分层门禁补上「把别包模型当查询目标」这一形态：收掉指向 mod01 的 12 处直查，其余 16 处进待清名单（只许变短），并按本仓纪律配一条活的证伪靶

**What to build:** 分层门禁补上「把别包模型当查询目标」这一形态：收掉指向 mod01 的 12 处直查，其余 16 处进待清名单（只许变短），并按本仓纪律配一条活的证伪靶

**Blocked by:** None（可立即开工；先做 TAIL-298）

**Status:** done

- [x] **门禁新形态**：`backend/tests/test_layering.py` 新增一条规则（形态 = 「把**别包**模型当**查询目标**」），判据覆盖五种写法：`select(X)` · `select(X.列)` · `session.get(X,…)` · `session.query(X)` · `select(...).select_from(X)`（X = 别包 `models` 的类）⇒ 可证伪：隔离副本里把任一处改回直查 ⇒ **必红**；`domain` / typing / join 条件那类**正当引用**喂进去 ⇒ **必须放行**（防误伤，名单不许被撑爆）。
- [x] **扫面与防空扫**：只扫 `app/mod*/**`（与规则 C 同面；`app/` 顶层、`home`、`report_export` 在面外 —— 写进 docstring）；断言 = 包数下限 ＋ 件数下限 ＋ ⭐ **「名单里的每一条都必须被扫出来」**（名单被扫空 = 判据自己坏了）。
- [x] **两张名单**：`_ALLOW_C2_PENDING`（起步 **16** 条 · 只许变短 · 逐条指向 `TAIL-300`）＋ `_ALLOW_C2_BY_DESIGN`（起步 **1** 条 = `mod05_flow/router.py` 的付款临界区锁，理由写"为什么必须在这一侧锁"）；`_C2_PENDING_START` 记起始条数。
- [x] **mod01 实际12处收口**（逐处清单见 Comments）：一律走 `mod01_projects.service` 出口。`select(Project)` 的几处走 `all_projects(s)`（＋ `domain.ordered/build_candidates`，跨包用 domain 本来就允许）；「仓库名 ↔ id」的 3 处走**同一个新出口**（多件共用 ⇒ 值得开，见施工图 §3.2 取舍表；⛔ 不为单调用者单开转手层）。
- [x] **反向灵敏度（活的）**：⭐ 先核归档件 `tools/mut/_归档-20261009/_mut_layering.py` 能否移回复用（README 要求先比较现行活件、复核路径与锚点），不能就新写一支；至少覆盖「改回直查 ⇒ 必红」＋「正当引用 ⇒ 放行」。登记进 `_run_muts.KEY`（或 `KEEP_OUT` 带理由）＋ `mut_cover` 台账。⭐ **顺手补上老缺口**：规则 A/B/B2/C/D 现在**没有活的靶**（只有归档件 ⇒ 规则烂掉没人喊）。
- [x] **工程档**：`ops/architecture.md` §一 那句规矩后补一句——由判据守「⛔ 跨包把对方模型当**查询目标**」（import 用于 typing / domain / join 条件**不受限**）。
- [x] **收尾**：按 `_impactscope` 实选集跑（预计 = `syntax_audit` ＋ pytest 选集（含 `test_layering` 与 10 处所在模块的判据）；动了 `tools/mut` 加 `mut_cover`、动了 `_run_muts` 加 `_gatescope --selftest`）；⭐ **不动页面 ⇒ 不需要真机、不需要盖章**；票 Comments 记证据与未验边界。

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：2026-10-11 架构体检 B 案（用户按推荐）；清单与出口形状由只读子代理逐处核实｜不做会怎样：不做：规矩与尺子不同形 ⇒ 同类继续从 models 绕（实测 21 处）；且分层守卫当前无活的证伪靶（_mut_layering 已归档，architecture.md 自己写历史自证）｜落点：落点：backend/tests/test_layering.py（新规则 C2 ＋ 待清与按设计两张名单 ＋ 防空扫断言）· tools/mut 新增活靶 ＋ mut_cover 台账 · 10 处读点所在文件（mod03_notice sup_match 与 notice_api_router · mod04_plan project_views · mod06_proc service · mod09_fee service 与 repository · mod11_jc repository）· ops/architecture.md 一节（补尺子形态一句）｜阶段 / 时机：随时（排 TAIL-298 之后）｜**排期四问**（`§14.3` 同源）：四问：一 会真发生（同一族已漏到 21 处）；二 真发生很难受且静默（口径改了漏一处不报错）；三 不做也能活，但每次口径变更都要满仓搜谁翻过那张表；四 有更省的：先收最便宜的 10 处，门禁带待清名单只许变短，其余另票

**2026-10-11 · 建票时随票的施工清单（只读核实：子代理逐处给了文件:行与用途）。**

要收的 10 处（全是「import mod01 的 models ＋ 自己 select」）：

| 文件:行 | 现在要什么 | 改法（出口） |
|---|---|---|
| `mod03_notice/sup_match.py:95` | 仓库名映射（id → warehouse_name） | ⭐「仓库名 ↔ id」新出口 |
| `mod09_fee/repository.py:34` | 仓库名 → 项目 id | 同上（同一件事第二处） |
| `mod11_jc/repository.py:171` | 仓库名 → id | 同上（同一件事第三处） |
| `mod11_jc/repository.py:56` | 合同行 ＋ 仓库名（现在 join 别包表） | 同上 ＋ 本包合同查询分开做（⛔ 不再 join 别包表） |
| `mod03_notice/notice_api_router.py:355` | 归属档案行的仓库名（单条） | `all_projects(s)` 过滤取一条（或走上面那个出口） |
| `mod04_plan/project_views.py:28` · `:34` | 项目候选（键 ＋ 展示名） | `service.all_projects(s)` ＋ `domain.ordered/build_candidates`（跨包用 domain 本来就允许） |
| `mod06_proc/service.py:144` | 键 → 展示名 | 同上 |
| `mod09_fee/service.py:41` | 项目候选 | 同上（本处已在用 `PJ.build_candidates`，只换取数口） |
| `mod11_jc/repository.py:176` | 项目候选 | 同上 |

出口取舍依据：`all_projects(session)` **已存在**（`mod01_projects/service.py:24`，2026-10-02 那批建的），覆盖其中多数处；「仓库名 ↔ id」**一处要开三家共用** ⇒ 按施工图 §3.2 取舍表**值得开**（⛔ 不为单调用者单开转手层）。

预判的核验面（以 `_run_rulers --explain` 的**实选集**为准）：`syntax_audit` ＋ pytest 选集（`test_layering` ＋ 这 10 处所在模块的判据）；若动了 `tools/mut` ⇒ 加 `mut_cover`；若动了 `_run_muts` ⇒ 加 `_gatescope --selftest`。⚠️ 不动页面 ⇒ **不需要真机、不需要盖章**。

**2026-10-12 · 领票。** 已核TAIL-298/301为done；按用户授权实施299，保留已有修改，不实施300、不提交推送。基点：`.codebuddy/work/00-scratch/tmp-20261012-tail299-start.json`。

**2026-10-12 · 清单订正（用户裁定按实际清单）。** 原票10处Project漏列`mod11_jc/repository.py::_project_key`、`mod05_flow/service.py::build_ledger`的get，共12处，均在299收口。新C2五形态完整实扫（包含数字包名mod02_i8）改前29处，改后17处＝16待清＋1按设计锁；原「21／10待清」仅为建票预估。补入300的是mod05的revoke/revoke_info/sync_stat_paid，以及mod01的pending/archive_pending和mod03的latest_unresolved。300本轮只订正清单，未实施；不以遗漏扫描维持原预估。

**2026-10-12 · 落账。** 12处Project查询全走mod01 service；仓库名↔档案id由warehouse_index一处、多家共用，其他复用all_projects；项目候选和标签仍由原domain或原视图形状构建。合同主表改为本包查询＋项目索引装配，保留筛选/原序/空仓库语义。13包147件实扫后17查询＝16待清＋1付款锁，extra/stale均空；300未实施，最新Comments保留完整接续清单和锁/原单/批量边界。

**2026-10-12 · 唯一一次双轴评审。** 基点为开工快照（HEAD 2df035b0a1376351c64f95a18f82aa2ed64665d9，无新提交），只审本轮diff。Standards：1项P2（普通get误伤＋get关键字漏扫）；Spec：2项P2（相对导入绕过、domain映射get误伤），后者与Standards重叠。同批修正：查询接收者识别、entity关键字、绝对/相对导入解析；扩展隔离靶证明每例先前漏/误报现已正确。未再开第二轮，业务形状/排序无其他发现。

**2026-10-12 · 核验。** 新C2对改前直查先红（rc=1），收口后绿；五件相关pytest39项通过。按基点执行_run_rulers首轮rc=0/BAD: []：124件pytest选集100.32s，总154.06s；syntax/bytes/chain/claim/doc与mut_cover、_run_muts/_gatescope自测均rc=0。链路仍全站11条已接，子集结果隔离，未刷新权威四态。

活靶比较归档入口后新建：原入口写正式靶且归档路径无效，保留其9条现行import靶并改成临时副本；A/B/B2/C/D/C2真实断言共62次检查（基线、五形态＋get关键字、多引用别名/相对导入、typing/domain/join正常放行、同处新增查询、名单幽灵/增长/漏扫、包数/件数防空扫）。_run_muts --cases _mut_layering.py最终rc=0/BAD: []，25.8s；依实测列SLOW_KEY并留KEY。正式app/tests逐字节hash未变；mut_cover已重生成。服务已restart，/app=200；最终重启与收尾检查结果以下补记。

**未验边界。** 本轮源码门禁覆盖票面静态import可解析模型的五种查询，动态getattr/运行期ORM别名或原始SQL不在此静态规则内；app顶层/home/report_export在明确扫面外。未执行300的16处取数迁移，付款锁例外仍按原行为保留；无页面行为改变，未跑本轮真机、未盖壳章；未全套刷新权威四态，既有黄档和部署/恢复未验事项保持。不提交、不推送。

**2026-10-12 · 终轮与销号回执。** _tail_close.py --id 299干跑核对后--apply，票done、活动行移出、排期原行入历史、真源计数活跃3/已销号301；README及最新交接同步。最终再次restart成功，/app=200。

_run_rulers.py --since .codebuddy/work/00-scratch/tmp-20261012-tail299-start.json终轮rc=0/BAD: []，pytest选集88.08s，总115.07s；语法、字节、链路、文档、mut_cover与_run_muts/_gatescope自测均通过。此前首轮154.06s、扩展隔离入口25.8s；本轮未跑无关全套KEY和真机，不刷新权威四态。已有10件与本轮无关的dirty按开工快照逐字节复核未变，共享文档/登记件只追加本票影响；HEAD仍2df035b0a1376351c64f95a18f82aa2ed64665d9。完整源码最终检查日志在scratch临时证据，永久核验摘要以本Comments为准。

**2026-10-12 · 联合提交授权与合并核验。** 用户已明确授权301一轮双轴评审并修复后提交、推送299与301；取代此前不提交边界。299原唯一双轴评审及补修结果不变，本次没有另开评审或改代码。合并工作区相关pytest实跑73项/12.32s、rc=0；39段本机真机自检rc=0（服务/磁盘列清单一致，console/page错误无），壳基线20261012-0741，均为本次新增证据。命令与日志见301本日Comments。本票、300票及新变异件行尾统一CRLF；变异件仅换行字节改动，已再跑 `_run_muts.py --cases _mut_layering.py`，rc=0、25.4s、BAD: []，62次隔离检查通过，未重复无关靶。最终文书检查回执为scratch `tmp-20261012-301-review-final.log`；提交前检查、真实hook与推送结果以实际命令输出及Git记录为准。300未实施，其他未验边界沿用原记录。
