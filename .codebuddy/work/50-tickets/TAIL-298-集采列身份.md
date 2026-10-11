# TAIL-298: 集采台账的列改成有身份：表头由后端列清单生成，隐列与钉列按 id 现算，导出列由域内核派生（屏幕与导出不再各抄一份）

**What to build:** 集采台账的列改成有身份：表头由后端列清单生成，隐列与钉列按 id 现算，导出列由域内核派生（屏幕与导出不再各抄一份）

**Blocked by:** None（可立即开工）

**Status:** done

- [x] **列清单只有一个主人**：m11 的列文字面量从壳里退场（壳不再写 `JC_THEAD` 那种 20 列字面量），表头由 `/api/m11/list` 的 `columns` 生成 ⇒ 可证伪：壳源码里扫不到该字面量；渲染出的表头列数 = 1 个控件列 ＋ `columns` 长度。
- [x] **隐列与钉列按 id 定位**：屏幕行为表引用的每个 id 都在后端 `domain.JC_COLUMNS` 里（写错 id ⇒ 判据红）；表现与改前一致 —— 隐藏贸易公司三列后其余列自动变宽、行身份区四格是连续前缀且不透明、合计行首格仍钉、`render()` 每次重建后重新落（真机 ＋ 现有 `_shell_jcpin` 探针）。
- [x] **导出列由域内核派生**：`jc_export.COLUMNS` 不再自写字面量（列集 = `JC_COLUMNS − PAGE_ONLY_KEYS`、合计列 = `SUM_KEYS`）；导出的 19 列与屏幕列同序 —— 把 m11 补进 `tests/test_tail04_pages.py` 那条「页面表头 ↔ 导出列」的名单。
- [x] **导出表头的字与键名对齐**：加可选 `export_label`（缺省 = `label`）⇒ 屏幕带「（自动）」「（自由文本）」、Excel 不带；序号列键名统一为 `project_seq`（元数据 / 行字典 / 导出三者同名；子表 `INV_COLUMNS` / `PAY_COLUMNS` 同批核对）。
- [x] **值级缺口堵上**：`naive_export` 的调用页各加一条「COLUMNS 的每个 key 都出现在样例行里」的断言（堵 `r.get(key)` 那类静默空列）；若暴露既有键名错 ⇒ 如实报，当轮修或另立票，⛔ 不为求绿改断言。
- [x] **反向灵敏度**：新增一条变异（列清单里删一列 / 行为表里写错一个 id ⇒ 覆盖或引用判据必红），在 `mut_cover` 台账登记并自证能红。
- [x] **要搬的断言搬完**：`tests/test_ux_pages.py:459-494`（钉 jcApplyPin 实现形状那条）改钉「钉列 id 集合来自规格 ＋ 渲染后重量」；`tests/test_acc_jc_shell.py` 的空态跨列改指规格；`tools/probe/_shell_jcpin.py` 与 `tools/mut/_mut_probe_jcpin.py` 同批跟上。
- [x] **收尾**：真机跑过 m11（表头 / 隐 / 钉 / 导出）＋ `shell_verify --snapshot` 重盖章 ＋ 按 `_impactscope` 实选集跑相关判据与依赖自测；票 Comments 记证据与未验边界。

---

## Comments

**2026-10-11 · 建票（agent）。** 来源：2026-10-11 架构体检 A 案；用户逐轮「按推荐」并确认「共识」｜不做会怎样：不做：改一次列序要人肉同步五处（表头常量、导出字面量、两处位置常量、切片行），漏一处不报错（隐藏错列、钉错列、导出列名漂）｜落点：落点：backend/app/mod11_jc/domain.py（列清单键名与派生口）· backend/app/report_export/jc_export.py（由 domain 派生）· backend/app/web/shell/pages-b.js（屏幕行为表）· shell/actions.js 的 jcApplyHide 与 jcApplyPin · shell/core.js 的 BIND.m11 · web/index.html 的 TBL 调用 · backend/tests 与 tools/probe、tools/mut · ops/architecture.md 三节｜阶段 / 时机：随时（调试期；A 案第一票）｜**排期四问**（`§14.3` 同源）：四问：一 会真发生，加列与改列序就是下一次改动；二 真发生很难受且静默；三 不做也能活，但每加一列跨六处；四 有更省的做法规避重活：v1 只做 m11，不动切片、不动排序内核、不改行为

**2026-10-11 · 办完（agent）。** 列身份落地：`domain.JC_COLUMNS` 成列的**唯一主人** —— 壳表头由它现生成、隐藏/钉列按 id 现算、Excel 导出由它派生（落点与「以使用用户为中心」一致；术语已回写 `ops/architecture.md` §三）。

**逐条验收（票面 8 条）**

① **列清单一个主人** ✅ 壳里那个 20 列字面量退场（`proj.js` 留一句指向），表头 = `pages-b.js::jcThead()`（控件列 ＋ `columns` 逐列生成，屏内注解「（自动）」按尾部全角括号染灰）。可证伪两半：壳源码扫不到 `const JC_THEAD` 与旧表头片段（`tests/test_tail04_pages.py`）；**渲染出的表头列数 = 1 ＋ 列清单长度**（真机 ㉝-⑦ 实测「表头 21 格 · 后端列清单 20 列」）。
② **隐列与钉列按 id** ✅ `JC_HIDE_IDS` / `JC_PIN_IDS`（`pages-b.js`）＋ `jcColIndex` 现算列位；真机 ㉝ ①–⑤ 全绿（连续前缀链 0/29 → 29/76 → 76/161 → 161/229、行与表头逐格同款 0px、四格不透明、合计行首格仍钉、隐藏三列后**重量**），㉝-⑦ 另证「隐藏的正是偏好那三列」。⚠️ **真机第一跑抓到一处真错**：`nth-child` 少算一格（写 `i+1`，DOM 里 #1 是控件列 ⇒ 应 `i+2`）—— 当场把「发票金额」当贸易公司名藏掉，界面看着只是"少了三列"；已修并复跑绿。
③ **导出列由域内核派生** ✅ `jc_export.COLUMNS` = `D.JC_COLUMNS − PAGE_ONLY_KEYS`（19 列同序）、`MONEY_KEYS = SUM_KEYS`；m11 已补进 `test_tail04_pages.py` 的「页面表头 ↔ 导出列」名单（屏幕那份 = 域内核列清单）。
④ **表头字与键名对齐** ✅ 新增可选 `export_label`（缺省 `label`）：屏幕「结算金额（自动）/ 欠款金额（自动）/ 付款方式（自由文本）」↔ Excel「结算金额 / 欠款金额 / 付款方式」，其余列两边**逐字相同**（`test_tail298_columns.py::test_导出表头的字与键名对齐_屏幕注解只许那三列` 把注解白名单写死 ⇒ 多一列带注解就红）。序号列统一 `project_seq`（元数据 / 行字典 / 导出三者同名）。**子表同批核对**：`INV_COLUMNS` / `PAY_COLUMNS` 的「序号」是弹窗里按**行序**生成的行号（壳 `i+1`），行字典里没有这个键、也没有导出 ⇒ **不是**「三者同名」那一类，已在域内注明（⛔ 别拿它 `r.get()`）。
⑤ **值级缺口** ✅ 两条新判据：`m11` 走**真库真产行**（打桩内核，截 `service.export_xlsx` 真正交出去的那批行，逐列核 key）＋其余四页各一条（`nt`/`pl` 直调 `_export_row`；`fl` 走注入的 `load`；`pj` 只替 `session_scope` 一层）。**没有暴露既有键名错** —— 两条首跑即绿，如实记（本仓这一族的键目前是对齐的）。
⑥ **反向灵敏度** ✅ `tools/mut/_mut_tail298_columns.py`：4 靶 **4/4 命中**（列清单删一列 ⇒ 列数覆盖那条红；键名漂 ⇒ **值级**那条**独立**红；行为表写错 id ⇒ 引用判据红；钉列不连续 ⇒ 前缀判据红），靶在 `_isolated.isolated_backend` 临时副本、MD5 逐字节复原。已进 `_run_muts.KEY` ＋ 放行其隔离入口（实测紧贴快集线 ⇒ 同批归 `SLOW_KEY`：`--fast` 跳过、全套仍跑）；`mut_cover` 台账重生成（121 件 · `--check` 绿）。壳件在真机首跑修过一处（见 ②）⇒ 该变异**在修好后重跑过**（rc=0 · 23.7 s）。
⑦ **要搬的断言搬完** ✅ `test_ux_pages.py` 001-61 改钉「行为表 id ∈ 规格 ＋ 钉列 = 列清单连续前缀 ＋ 偏移仍是**量出来的**」；`test_acc_jc_shell.py` 空态跨列改指 `jcThead()`；`_mut_tbl.py` M15 锚点同批跟上；`_shell_jcpin.py` 加 ⑦。
⑧ **收尾** ✅ 见下。

**核验（按影响入口 · 基点 `.codebuddy/work/00-scratch/tmp-20261011-298-entry.json`）**：`_run_rulers --since …` **rc=0 · BAD: []** —— 首轮 **341.26 s**（含真机 39 段**重跑**）⇒ 修好隐藏列号后复跑 **225.35 s**（复用真机证据）⇒ **双轴评审的注释漂修完后终轮 313.49 s**（真机**再重跑** rc=0，证据 `.codebuddy/work/00-scratch/tmp-20261011-225552-shell-smoke.log`）。登记检查 11 把（doc_audit / audit_drift / audit_meta / audit_work / syntax_audit / bytes_guard / ui_parity / wiring_audit / chain_audit / asset_audit / claim_audit / prg_form_audit / `mut_cover --check` / `_run_muts --selftest` / `_gatescope`，各「必须修 0」）＋ pytest 选集 **133 件**（隔离结果 rc=0）＋ **真机壳自检 39 段 rc=0**（console/page 错误「无」）；壳章 `20261011-2255`，`shell_verify.py` 复核「与最新基线逐行一致」rc=0。改到运行中后端模块 ⇒ 已 `ops/server_ctl.ps1 -Action restart`（⚠️ 首跑真机整片红正是因为服务仍在跑**旧模块**：`columns[0].key` 还是 `idx` —— 列清单对不上 ⇒ 钉列按设计**不瞎设偏移**、隐藏也落空；重启后全绿）。
**反向灵敏度**：新变异 4/4（⑥）；`tools/mut/_mut_probe_jcpin.py` rc=0（基线绿 ＋ 去掉切换 ⇒ 判据红）；`tools/mut/_mut_tbl.py` rc=0（M15 新锚点唯一命中 · 21.1 s）。
**双轴评审（Standards ＋ Spec · 2026-10-11）**：Spec 轴逐条 **8/8 达成 · 越界 0**；Standards 轴报 **3 条硬违规**（全是**注释漂**、无行为错）：① `core.js` 那句仍写 `:nth-child(i+1)`（实为 `i+2` —— 正是真机首跑抓到的错法，照它改会**重犯**）② `core.js` / `domain.py` 两处点名了不存在的 `JC_VIEW`（真名 = `JC_HIDE_IDS`/`JC_PIN_IDS`）③ 新变异件 docstring 第一段不是「守什么」（`mut_cover` 台账抓错列）⇒ **三条已同批修**（③ 修后重生成台账 ＋ 复跑该变异 rc=0）。判断项 3 条见下（未验边界④）。
**未验边界（如实）**：① `tools/mut/_mut_m11cost.py` **未跑** —— 它仍**直接写正式壳件**（工具纪律：旧入口未隔离不跑）；其靶行 `el.classList.add('fl'); el.style.left=OFF[i]+'px';` 未被本轮改动（实测仍唯一命中）、㊲ 真机段绿 ⇒ 原证明按「代码未变」复用。② 导出 xlsx 只核到「列集 / 表头字 / 键覆盖」三层，**没做人眼比对**（真书复核见 `test_tail290_jc.py` 既有断言）。③ 真机跑的是本机开发库（254 行合同），其它数据规模未扫。④ **列身份只收到四个面**（表头 / 隐藏 / 钉列 / 导出）：`V.m11` 的行模板（手写 `<td>` 串）与 `sumRowOf` 的**列下标**（`{6:…,13:…}` ↔ `SUM_KEYS`）**仍是位置口径** ⇒ 加列 / 调序若落在它们左边，那两处仍会**静默错位 / 错算**；本轮按 A 案「v1 只做 m11、不动切片」**明确不做**，已在 `proj.js` 就地写明（评审建议另立一票，等用户定）。
**顺手记**：`_run_muts` 的快集超时提醒点名 `_mut_tbl.py`（20.8s > 20s）—— 属治理项（`SLOW_KEY` 分层，`_run_muts` 单一出口），未随本票改。
