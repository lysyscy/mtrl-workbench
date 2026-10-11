# TAIL-299: 分层门禁补上「把别包模型当查询目标」这一形态：收掉指向 mod01 的 10 处直查，其余 11 处进待清名单（只许变短），并按本仓纪律配一条活的证伪靶

**What to build:** 分层门禁补上「把别包模型当查询目标」这一形态：收掉指向 mod01 的 10 处直查，其余 11 处进待清名单（只许变短），并按本仓纪律配一条活的证伪靶

**Blocked by:** None（可立即开工；先做 TAIL-298）

**Status:** ready-for-agent

- [ ] **门禁新形态**：`backend/tests/test_layering.py` 新增一条规则（形态 = 「把**别包**模型当**查询目标**」），判据覆盖五种写法：`select(X)` · `select(X.列)` · `session.get(X,…)` · `session.query(X)` · `select(...).select_from(X)`（X = 别包 `models` 的类）⇒ 可证伪：隔离副本里把任一处改回直查 ⇒ **必红**；`domain` / typing / join 条件那类**正当引用**喂进去 ⇒ **必须放行**（防误伤，名单不许被撑爆）。
- [ ] **扫面与防空扫**：只扫 `app/mod*/**`（与规则 C 同面；`app/` 顶层、`home`、`report_export` 在面外 —— 写进 docstring）；断言 = 包数下限 ＋ 件数下限 ＋ ⭐ **「名单里的每一条都必须被扫出来」**（名单被扫空 = 判据自己坏了）。
- [ ] **两张名单**：`_ALLOW_C2_PENDING`（起步 **10** 条 · 只许变短 · 逐条指向 `TAIL-300`）＋ `_ALLOW_C2_BY_DESIGN`（起步 **1** 条 = `mod05_flow/router.py` 的付款临界区锁，理由写"为什么必须在这一侧锁"）；`_C2_PENDING_START` 记起始条数。
- [ ] **mod01 那 10 处收口**（逐处清单见 Comments）：一律走 `mod01_projects.service` 出口。`select(Project)` 的几处走 `all_projects(s)`（＋ `domain.ordered/build_candidates`，跨包用 domain 本来就允许）；「仓库名 ↔ id」的 3 处走**同一个新出口**（多件共用 ⇒ 值得开，见施工图 §3.2 取舍表；⛔ 不为单调用者单开转手层）。
- [ ] **反向灵敏度（活的）**：⭐ 先核归档件 `tools/mut/_归档-20261009/_mut_layering.py` 能否移回复用（README 要求先比较现行活件、复核路径与锚点），不能就新写一支；至少覆盖「改回直查 ⇒ 必红」＋「正当引用 ⇒ 放行」。登记进 `_run_muts.KEY`（或 `KEEP_OUT` 带理由）＋ `mut_cover` 台账。⭐ **顺手补上老缺口**：规则 A/B/B2/C/D 现在**没有活的靶**（只有归档件 ⇒ 规则烂掉没人喊）。
- [ ] **工程档**：`ops/architecture.md` §一 那句规矩后补一句——由判据守「⛔ 跨包把对方模型当**查询目标**」（import 用于 typing / domain / join 条件**不受限**）。
- [ ] **收尾**：按 `_impactscope` 实选集跑（预计 = `syntax_audit` ＋ pytest 选集（含 `test_layering` 与 10 处所在模块的判据）；动了 `tools/mut` 加 `mut_cover`、动了 `_run_muts` 加 `_gatescope --selftest`）；⭐ **不动页面 ⇒ 不需要真机、不需要盖章**；票 Comments 记证据与未验边界。

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
