"""按受影响机制选择隔离自证。

--cases明确选件；无参数不跑全套。KEY与KEEP_OUT仍双向检查登记覆盖。
原生隔离入口按已检查的实现明确放行；其余旧入口拒绝对正式工作文件写靶，
未来涉及对应判据时先隔离再验证。历史原因按需查Git与原票。
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
MUT = ROOT / "tools" / "mut"
sys.path.insert(0, str(ROOT / "tools" / "oneoff"))
import _gatescope as _gate  # noqa: E402
import _pytestscope as _scope  # noqa: E402

#: ⭐⭐ 慢集 = **每支实测超 `FAST_BUDGET`**的那些（`TAIL-237`）——⭐ **秒数看每次运行自己打的那行**（⛔ 别抄进代码/文档，
#:   它随机器与靶件变化；2026-10-06 首次分层时抄了 6 处，同日 `/code-review` 判它违规并已全部撤掉）。
#: ⭐ **为什么按秒数分、而不是按"我以为它重要吗"**：本件**每轮都打印每支秒数** ⇒ 分层依据是**量出来的**，
#:   不靠谁记得住 ⇒ 别人接手也复现得出。
#: ⛔ **单一出口**：别在别处再写一份"哪些是慢的"（本仓规矩：同一条口径只许有一处）。
#: ⚠️ **漂移怎么办**：`FAST_BUDGET` ＋ `SLOW_BUDGET` 那两道提醒会自动喊（见 `main`）—— ⛔ 不靠人记得回来改。
FAST_BUDGET = 20.0
SLOW_BUDGET = 60.0

#: 慢集（`--fast` 跳过它们；跑全套时照跑）
SLOW_KEY: frozenset[str] = frozenset({
    "_mut_docaudit.py", "_mut_shellapi.py", "_mut_segments.py",
    # ⚠️ `_mut_syntax.py`（`TAIL-244` 定档）：靶＝`syntax_audit`（内建 `--selftest` ＋ 活树五靶），
    #   **每处靶都要 `node --check`、且有两处真去动壳件**（`print-export.js` / `index.html`）
    #   ⇒ 秒数紧贴快集线、余量太小 ⇒ 归慢集（⛔ 别为消提醒改 `FAST_BUDGET`，票面已明写）。
    #   ⭐ 它**同时留在 `KEY`**：慢集只表示"`--fast` 跳过"，而动了 `tools/mut/` 的那轮闸门仍跑全套。
    "_mut_syntax.py",
})

#: ⭐⭐ **刻意留在快集、且超预算也不提醒挪走**的那几支（`/code-review` 2026-10-06 抓出后才补上，
#:   否则第一轮就出现"提醒说该挪、而它挪了就会出事故"的自相矛盾 ⇒ **提醒变成噪音**）：
#:   `_mut_uicheck` —— 靶在**仓外交付面**，`git diff` 看不见 ⇒ 挪进慢集等于"**外部被回退也不验**"
#:   （`TAIL-234` 记的正是交付面被云同步回退过一次、41 处差异尺子只看见 2 处）。
#:   它实测在 `FAST_BUDGET` 上下 ⇒ **这一条是"按理由豁免超时提醒"，不是"免检"**。
KEEP_FAST: dict[str, str] = {
    "_mut_uicheck.py": "靶在仓外交付面，git 看不见 ⇒ 必须每轮验（挪进慢集＝外部回退不验）",
}

#: ⭐ 关键集：靶是**尺子自身 / 结构守卫 / 文档面**的那几支（⇒ 它们烂掉 = 一整片守卫静默失效）
KEY: tuple[tuple[str, str], ...] = (
    # ⚠️ 说明里**不抄条数**（2026-10-05 `/code-review` 指出：那与本件 docstring 的"共 N 条"是
    #    同一件事两处写 —— 而 docstring 自己就写着"条数看本件输出、⛔ 别在别处抄"）。
    ("_mut_docaudit.py", "doc_audit 的 T1–T19 ＋ T24/T25 ＋ T4 计数锚点（条数看本件输出）"),
    # ⭐ 2026-10-06（`TAIL-238`）：`T3` **叙述豁免收窄**的两个方向（真幽灵仍红 · 叙述句豁免）
    #   ＋「票仓不放水」「距离闸仍承重」—— ⛔ 不接进来 = 收了判据却没人跑它，烂掉无人知。
    ("_mut_t3_narr.py", "T3 幽灵路径的叙述豁免（真幽灵仍红 · 叙述句豁免 · 票仓不放水 · 距离闸承重）"),
    ("_mut_injectsplice.py", "T22 注入档「两行粘成一行」（+ 正常排版不许误伤）"),
    ("_mut_linewalls.py", "T21 文档「字墙」（单行 >800 字 · 基线只许变短）"),
    ("_mut_countanchors.py", "T4 的四类计数锚点"),
    ("_mut_claim.py", "claim_audit（裁定必须同行写日期＋出处）"),
    ("_mut_uicheck.py", "doc_audit --ui 的交付面四检"),
    ("_mut_covergap.py", "cover_gap（口径覆盖缺口登记册）"),
    ("_mut_t12.py", "T12 分层与命名"),
    ("_mut_t14t15.py", "T14/T15（scratch TTL · work 区文头 · artifacts 白名单）"),
    ("_mut_t20.py", "T20 保留期与容量（backups 上限 · oneoff 件数容量）"),
    ("_mut_segments.py", "真机自检**段注册表**的顺序守卫（`TAIL-215` 批 1 · 离线 · 秒级）"),
    ("_mut_shellapi.py", "壳的**语义口径**（`TAIL-219` 批 1：认结构 / 找不到必抛 · 离线 · 秒级）"),
    ("_mut_livemachine.py", "T23 活机器口径（`TAIL-236` 批 2：缺一路/空命中/复述/接线 ＋ 正常不误报）"),
    # ⚠️ 这一支的**方向与众不同**：票面要的是「抽掉一个信号 ⇒ 必须**不再**报」——
    #    `_mut_docaudit` 的框架只会断言"报了" ⇒ 表达不出这个方向（见该件 docstring）。
    ("_mut_downgrade.py", "T26 降档判据（`TAIL-236` 批 3：两个信号各撤一次必须不再报）"),
    # ⭐ 2026-10-06（`TAIL-234`）：`T27` 页脚尾部＋ `T28` `PRD` 规格件基线。
    #   ⚠️ **靶同样在仓外交付面** ⇒ 与 `_mut_uicheck` 同理：不接进来 = 收了判据却没人跑它。
    #   ⭐ 里面有一靶用的是**旧根那份真实退化件**（本机被云同步盖回过的快照）⇒ 不是"造出来的假红"。
    ("_mut_facedoc.py", "T27/T28 交付面尾部两张网（页脚后内容、缺件/能力编号损失及篇幅提示）"),
    # ══════════════════════════════════════════════════════════════════
    # ⭐⭐ 2026-10-06（`TAIL-239`）：下面这一段是**量出来的**，不是"我觉得它重要"。
    #   做法 = 逐支读 `_mut_*.py` 的 docstring 第一段（`tools/mut/` 全集）＋ 归类：
    #     ① 靶＝`CMDS` 里那把**尺子本身** ＋ **离线**（不起服务、不开浏览器）＋ 秒级 ⇒ 进关键集；
    #     ② 实测秒数紧贴快集线 ⇒ `SLOW_KEY`（⛔ 秒数看每次运行自己打的那行，别抄）；
    #     ③ 有意不跑 ⇒ `KEEP_OUT`（**逐支带理由**，见下）。
    #   ⚠️ 前两支（`_mut_chain` / `_mut_uicheck` 那类）已经栽过 5 次「加了反向灵敏度却没人跑」，
    #   所以这次不只加行，还装了**选集自己的机器眼**（`cover_gap()` ＋ `_mut_keycover.py`）。
    ("_mut_chain.py", "chain_audit 的反向灵敏度（靶＝链路对账尺子本身 · 离线）"),
    ("_mut_asset.py", "asset_audit 的 A1/A2/A4（靶＝尺子本身 · 离线）"),
    ("_mut_shell.py", "ui_parity 的 U2/U2b/U3（靶＝尺子本身 · 离线）"),
    ("_mut_u4.py", "ui_parity 的 U4「标了已接后端就要真有 /api/mNN」（靶＝尺子本身 · 离线）"),
    ("_mut_prg_form.py", "prg_form_audit「PRG 端点不许拿 Query 收必填」（靶＝尺子本身 · 离线）"),
    ("_mut_shellverify.py", "shell_verify 盖章式闸门（加行/改行/删行三形态都得让它红）"),
    ("_mut_t8_m08imp.py", "audit_drift 的 T8「m08 撤项不许复活」（靶＝尺子本身 · 离线）"),
    ("_mut_wiring.py", "wiring_audit「口径说了要做的事，代码里接上了吗」（靶＝尺子本身 · 离线）"),
    # ⚠️⭐ 本票第 3 步新建的守卫**自己也得进关键集** —— 它要是没进，下一个 239 就是它。
    ("_mut_keycover.py", "**选集机器眼**：`KEY` ∪ `KEEP_OUT` 有缺口就报红（治「没人跑」这件事本身）"),
    # ⚠️ 2026-10-06（`TAIL-241` 第 4 步）：pytest 选测范围的反向灵敏度
    #   —— 守的是「按改动范围跑」那条判据（漏跑比慢跑严重得多 ⇒ 它必须自己有牙）。
    #   ⛔ 没进 `SLOW_KEY`：它只真跑**一支见证件**（不是整套选测集）⇒ 实测在快集预算内。
    ("_mut_pytestscope.py", "选测范围的判据（漏跑/跳过/缺口三个方向都造得出红）"),
    # ⚠️ 2026-10-07（`TAIL-244`）：靶＝`syntax_audit` 的**内建 `--selftest`** —— 它那段自证
    #   一直"写了、当时能过、此后没人碰" ⇒ 尺子腐化了没人知；⛔ 而这把尺子本身就在闸门 `CMDS` 里。
    #   ⭐ 已归 `SLOW_KEY`（要 node ＋ 动壳件）；⛔ 理由里不钉条数（尺子加规则就成假话）。
    # ⚠️ 2026-10-07（`/retro` 候选1）：新尺子 `bytes_guard`（行尾 / 坏字符 / BOM / 编码）的反向灵敏度
    #   —— 四条规则各造一次红 ＋ **正常件必须放行**（防"永远红"那个方向）。靶件落 `tools/audit/` 下、用完即删。
    #   ⚠️ 它是**当场被 `cover_gap()` 报红抓出来的**（新写的一支忘了登记）—— 那道自检第一次真派上用场。
    ("_mut_gatescope.py", "相关核验通过回执：漏跑/清单外、输入变更、失败失效、权威档隔离"),
    ("_mut_bytesguard.py", "bytes_guard 的 B1–B4（混行尾 / U+FFFD / ps1 缺 BOM / 非 UTF-8 ＋ 正常件放行）"),
    # ⚠️ 2026-10-07（`TAIL-244`）：靶＝`syntax_audit` 的**内建 `--selftest`** —— 它那段自证
    #   一直"写了、当时能过、此后没人碰" ⇒ 尺子腐化了没人知；⛔ 而这把尺子本身就在闸门 `CMDS` 里。
    #   ⭐ 已归 `SLOW_KEY`（要 node ＋ 动壳件）；⛔ 理由里不钉条数（尺子加规则就成假话）。
    ("_mut_syntax.py", "syntax_audit 的各条规则靶 ＋ 内建 `--selftest`（靶＝尺子本身 · 要 node --check · 动壳件 ⇒ 慢集）"),
)

#: ⭐⭐ **有意不跑名单**（`TAIL-239` 第 3 步 · 治复发）—— **逐支带理由**。
#:
#: **为什么需要它**：本件原来只有"进/不进"两档 ⇒ 新写一支 `_mut_*.py` 的人**默认它会被跑**，
#:   实际不会 ⇒ 「加了反向灵敏度却没人跑」（本族已 5 次：`TAIL-205` / `TAIL-233` / `TAIL-236` /
#:   `TAIL-237` / 本票）。有了这份名单，"不跑"就从**默认的沉默**变成**必须写下来的判断**。
#:
#: ⛔ **单一出口**：哪支在跑、哪支有意不跑，只在本件说了算；⛔ 别在别处再写一份清单。
#: ⛔ **理由不许写"不重要"/"以后再说"** —— 那等于没写（本仓吃过"靠回忆 ⇒ 静默失效"的亏）。
#:   下面每条都落到**可复核的事实**（靶是什么 · 跑起来要什么 · 谁在守）。
#:
#: ⭐ 三类理由的**速查**（细节逐支写在行尾）：
#:   · **靶是业务面断言**（`backend/tests/test_*.py` 里的业务/接线用例）⇒ 闸门只收"尺子/结构/文档面"
#:     （本件题头那条选集标准），业务面由各自域**自己的 pytest** 守；且每处变异都要拉起一次
#:     pytest ⇒ 分钟级 ⇒ 进闸门等于把闸门时长拉爆（按需 `--all` 仍能全跑）。
#:   · **靶要真机**（浏览器 / 起服务 / `tools/probe/`）⇒ 收工闸门是真机**另一档**的活。
#:   · **当前红 / 靶假设过期** ⇒ ⛔ 塞进闸门＝每轮假红（那比不跑更坏：假红会让人学会忽略闸门）。
KEEP_OUT: dict[str, str] = {
    "_mut_design_rules.py": "现行前端守则结构的原生隔离自证；仅守则/判据变化按需",
    "_mut_proc_split.py": "分域截止与机械覆盖的原生隔离自证；仅相关业务或判据变化按需",
    "_mut_proc_split_shell.py": "分域截止/月编辑壳判据的原生隔离自证；仅对应壳或判据变化按需",
    "_mut_tail262.py": "历史替换/i8优先/批量拒写的原生隔离自证；仅对应机制变化按需",
    "_mut_tail264_266.py": "候选/合同键/批录/年度汇总的隔离覆盖输入；仅对应机制变化按需",
    "_mut_tail274.py": "期初三行与台账累计的原生隔离自证；仅对应金额/判据变化按需",
    "_mut_ui_workflow.py": "供应商确认及导入范围的原生隔离自证；仅对应流程/判据变化按需",
    # ---- 靶要真机（浏览器 / 起服务 / `tools/probe/`）----
    "_mut_sticky.py": "靶＝`sticky_probe`（合计行视口吸附的真机探针）· 靶在闸门里但**要真机** ⇒ 属真机那一档",
    "_mut_vs.py": "靶＝`tools/probe/` 的虚拟滚动阈值 ＋ 焦点护栏 · **要 playwright 真机**",
    "_mut_vsrisk.py": "靶＝`tools/probe/_shell_smoke.py`（㊱ 接管缺口）· **要真机**",
    "_mut_m11cost.py": "靶＝`tools/probe/_shell_smoke.py`（㊲ m11 打开不卡）· **要真机**",

    # ---- 当前红 / 靶假设过期（⛔ 修好前塞进闸门＝每轮假红；已在当日日志留痕）----

    # ---- 靶是业务面断言（由各自域 pytest 守；分钟级 ⇒ 按需 `--all`）----
    "_mut_acct.py": "靶＝收款账号字段（`TAIL-60/61` 修法）· 业务面",
    "_mut_amount.py": "靶＝`tests/test_amount_text_parity.py`（金额文本）· 业务面",
    "_mut_archive_chain.py": "靶＝`TAIL-29`-③ 抓取链路接自动建档 · 业务面",
    "_mut_archpick.py": "靶＝`ACC-PRJ-SYNC-001`（档案取数口径）· 业务面",
    "_mut_auth.py": "靶＝`ACC-USR-MGMT-001/001-01`（未登录 ⇒ 无身份）· 业务面",
    "_mut_b4.py": "靶＝m11 接入建议/校验/记忆三条边界（纪律）· 业务面",
    "_mut_big.py": "靶＝`ACC-RPT-BIG-001`（活动大表）· 业务面",
    "_mut_core_bindings.py": "靶＝`tests/test_core_bindings.py`（core 取数口 ＋ 装配层接线）· 接线断言 pytest",
    "_mut_core_projects.py": "靶＝`TAIL-36` 项目三小件唯一实现 · 业务面",
    "_mut_d25.py": "靶＝`D25` 四条用户裁定（负数照收 / 非数据行跳过 / 标段行认月）· 业务面",
    "_mut_deps.py": "靶＝`tests/test_deps_declared.py`（依赖清单不许漏登记）· 接线断言 pytest",
    "_mut_excl_overpay.py": "靶＝『剔除行可勾选』＋『超付挂提醒』· 业务面",
    "_mut_i8cookie.py": "靶＝`§7.8` i8 凭据（cookie 缓存复用 / 未绑即拒）· 业务面",
    "_mut_impkit.py": "靶＝`TAIL-69`『预览不写库』· 业务面",
    "_mut_impstale.py": "靶＝`TAIL-78`『导入/回滚 ⇒ 取数缓存全标脏』· 业务面",
    "_mut_ledger.py": "靶＝`ACC-RPT-EXP-001`（台账导出）· 业务面",
    "_mut_m01wired.py": "靶＝`tests/test_wired_m01.py` · 业务面",
    "_mut_m02wired.py": "靶＝`tests/test_wired_m02.py`（`TAIL-27` 壳接线）· 业务面",
    "_mut_m03act.py": "靶＝`tests/test_wired_m03_action.py` · 业务面",
    "_mut_m03list.py": "靶＝`tests/test_wired_m03_list.py` · 业务面",
    "_mut_m03pay.py": "靶＝`tests/test_wired_m03_pay.py` · 业务面",
    "_mut_m03pick.py": "靶＝`tests/test_wired_m03_pick.py` · 业务面",
    "_mut_m04forms.py": "靶＝m04 强制通过 · 业务面",
    "_mut_m04wired.py": "靶＝`tests/test_wired_m04.py` · 业务面",
    "_mut_m05wired.py": "靶＝`tests/test_wired_m05.py` · 业务面",
    "_mut_m06wired.py": "靶＝`tests/test_wired_m06.py`（`MOD-06` 机械源接线）· 业务面",
    "_mut_m07bal.py": "靶＝结余录入片 · 业务面",
    "_mut_m08wired.py": "靶＝`tests/test_wired_m08.py` · 业务面",
    "_mut_m09.py": "靶＝`MOD-09` 壳接线 · 业务面",
    "_mut_m14.py": "靶＝`MOD-14` 壳接线（`ACC-CFG-RULE-001`）· 业务面",
    "_mut_m4.py": "靶＝`ACC-RPT-EXP-001`（过程资料导出）· 业务面",
    "_mut_m4b.py": "靶＝`ACC-RPT-BIG-001`（活动大表）· 业务面",
    "_mut_m4c.py": "靶＝`TAIL-03/02/01`（机械手录 / 历史导入 / 手动导入 Excel）· 业务面",
    "_mut_m4d.py": "靶＝真机抓取暴露的两处修复 · 业务面",
    "_mut_m4e.py": "靶＝`ACC-PRJ-SYNC-001/001-06` · 业务面",
    "_mut_m4f.py": "靶＝链路 B（`ACC-PRJ-AUTO-001` 7 点 ＋ `ACC-SETL-FETCH-001/001-10`）· 业务面",
    "_mut_m4g.py": "靶＝导出项目参数保序去重 · 业务面",
    "_mut_m6.py": "靶＝`ACC-INIT-001` / `ACC-ODDVAL-001` · 业务面",
    "_mut_m7w.py": "靶＝`MOD-07` 壳接线 · 业务面",
    "_mut_m9.py": "靶＝`ACC-FEE-MON-001`（11 个判据点）· 业务面",
    "_mut_mapping.py": "靶＝`import_kit.mapping` / `profile_store`（`TAIL-75` B1）· 业务面",
    "_mut_own_109.py": "靶＝`ACC-PRJ-OWN-001/001-09` · 业务面",
    "_mut_own_dialog.py": "靶＝`TAIL-29`-②④ 链路 C 弹窗 · 业务面",
    "_mut_owncfg.py": "靶＝`ACC-PRJ-OWN-001` ＋ `ACC-CFG-RULE-001` · 业务面",
    "_mut_ownwh.py": "靶＝`TAIL-39`『兜底前先查 i8 仓库名单』· 业务面",
    "_mut_p1.py": "靶＝路径①（模板填充）片 1 · 业务面",
    "_mut_p5a.py": "靶＝表级虚拟滚动（`TAIL-64` `P5-a`/`P5-c`）· 接线断言 pytest",
    "_mut_print.py": "靶＝打印链路（`TAIL-46` ②③）· 业务面",
    "_mut_prjtype.py": "靶＝`TAIL-42`『人工覆盖三类判定』· 业务面",
    "_mut_proc.py": "靶＝`ACC-RPT-EXP-001`（过程资料成品）· 业务面",
    "_mut_promote.py": "靶＝`TAIL-30`-③ 人工指认（链路 B）· 业务面",
    "_mut_rules.py": "靶＝`TAIL-40` 剔除规则落库 · 业务面",
    "_mut_stale.py": "靶＝`tests/test_wired_boot.py::跨页写动作后全标脏` · 业务面",
    "_mut_tail04.py": "靶＝`TAIL-04` 导出切片 · 业务面",
    "_mut_tail04_pages.py": "靶＝`TAIL-04` 最后两页 ＋ `exp` 真分发 · 业务面",
    "_mut_tail35.py": "靶＝`TAIL-35`（m04 导入 ＋ 手动行）· 业务面",
    "_mut_tail43.py": "靶＝`TAIL-43` 六处断言 · 业务面",
    "_mut_tbl.py": "靶＝`TBL` 统一表外壳（`TAIL-64`）· 接线断言 pytest",
    "_mut_time.py": "靶＝`tests/test_acc_i8_time.py`（壳的业务时钟取自北京时间）· 业务面",
    "_mut_trailscope.py": "靶＝`tests/test_trail_scope.py`（留痕范围判据）· 接线断言 pytest",
    "_mut_trash.py": "靶＝`ACC-USR-MGMT-001/001-09`（回收站）· 业务面",
    "_mut_unresolved.py": "靶＝`TAIL-41`（未命中清单的新鲜度）· 业务面",
    "_mut_uxnum.py": "靶＝`tests/test_ux_numbers.py`（金额大数带单位 / 不可得金额不许冒充 0）· 接线断言 pytest",

    # ---- 一次性靶（脚本自称"用完即删"，留着只为可复核 ⇒ 不进闸门）----
    "_mut_jc.py": "靶＝`M5` 集采域内核 11 条断言 · 件自己的 docstring 写着**「用完即删」**（一次性靶类）· 业务面",
}


def cover_gap() -> tuple[list[str], list[str]]:
    """**选集的机器眼**（`TAIL-239` 第 3 步）→ `(缺口件名, 名单里已不在盘的件名)`。

    ⭐ **为什么必须有它**：本件原来只回答"哪些要跑"，**没人回答"那没跑的那些呢"** ——
    而"没跑且没人说为什么"正是本族 5 次静默失效的根（`TAIL-205`/`233`/`236`/`237`/本票）。
    ⇒ 现在**每一支 `_mut_*.py` 必须落在 `KEY` 或 `KEEP_OUT` 之一**，否则当场报红并列出它。
    ⚠️ **两侧都查**：缺口（新件忘了登记）· 陈旧（改名/删件后名单没跟改）—— 后者同样让选集失真。
    ⛔ 本函数**只读**：不跑任何变异件。

    ⚠️⚠️ **`SLOW_KEY` 为什么不在这份名单里**（`TAIL-244` 实测才弄清、此前没人说得清）：
    `SLOW_KEY` **不是第三档**，它是 `KEY` 的**子集语义** —— 它只回答"`--fast`（收工闸门默认那条）
    跳过它"，跑全套时照跑（`main()` 的用例一律从 `KEY` 取，`SLOW_KEY` 只做过滤）。
    ⇒ **只登记在 `SLOW_KEY`、没登记在 `KEY`** 的件名会被**静默忽略**（没人跑、也没人写为什么）
    —— 那是本族同款的静默失效 ⇒ 这条子集关系由 `report_cover()` 单独断言（`orphan_slow`）。
    """
    on_disk = {p.name for p in MUT.glob("_mut_*.py")}
    listed = {n for n, _ in KEY} | set(KEEP_OUT)
    return sorted(on_disk - listed), sorted(listed - on_disk)


def report_cover() -> int:
    """打印选集自检结果并给 rc（`0`＝名单盖住全集 ＋ 慢集没有孤儿）。"""
    gap, stale = cover_gap()
    # ⭐ `TAIL-244`：`SLOW_KEY` 里**不在 `KEY`** 的名字 = 没有任何一轮会跑它（见 `cover_gap` 说明）
    orphan_slow = sorted(SLOW_KEY - {n for n, _ in KEY})
    if gap:
        print(f"⛔ **选集有缺口**：{len(gap)} 支 `_mut_*.py` 既不在 `KEY` 也不在 `KEEP_OUT`")
        print("   ⇒ 它们**不会被任何一轮跑**（`TAIL-239`：加了反向灵敏度却没人跑，本族已 5 次）")
        for n in gap:
            print(f"     · {n}")
        print("   ⇒ 两选一：**① 该跑** ⇒ 加进 `KEY`（并想清快集/慢集）"
              "　**② 有意不跑** ⇒ 进 `KEEP_OUT` 并**写下为什么**（⛔ 不许写「不重要」）")
    if stale:
        print(f"⛔ **名单陈旧**：{len(stale)} 支已不在盘上（改名/删件 ⇒ 本件要跟改）："
              f"{', '.join(stale)}")
    if orphan_slow:
        print(f"⛔ **慢集有孤儿**：{len(orphan_slow)} 支在 `SLOW_KEY` 里却**不在 `KEY`** ⇒ "
              f"**没有任何一轮会跑它们**（`--fast` 的用例从 `KEY` 取，慢集只做过滤）："
              f"{', '.join(orphan_slow)}")
        print("   ⇒ 修法：把它也加进 `KEY`（`SLOW_KEY` 只是给 `KEY` 打上「`--fast` 跳过」的标记）")
    if not gap and not stale and not orphan_slow:
        print(f"✅ 选集一致：`KEY` {len(KEY)} 支 ∪ `KEEP_OUT` {len(KEEP_OUT)} 支 "
              f"＝ 盘上 {len(list(MUT.glob('_mut_*.py')))} 支（⛔ 条数别抄在别处）")
    return 1 if (gap or stale or orphan_slow) else 0


def run_one(p: pathlib.Path, timeout: int) -> tuple[int, float]:
    if p.name not in {'_mut_gatescope.py', '_mut_bytesguard.py', '_mut_facedoc.py', '_mut_tbl.py',
                       '_mut_design_rules.py', '_mut_proc_split.py', '_mut_proc_split_shell.py',
                       '_mut_tail262.py', '_mut_tail264_266.py', '_mut_tail274.py', '_mut_ui_workflow.py'}:
        print('未执行：旧脚本尚未提供隔离入口，须先为本轮对应判据准备隔离输入：', p.name)
        return 2, 0.0
    t = time.time()
    try:
        r = subprocess.run([PY, "-X", "utf8", str(p)], cwd=str(ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        rc = r.returncode
        if rc:
            tail = [x for x in ((r.stdout or "") + (r.stderr or "")).strip().splitlines() if x.strip()][-3:]
            for x in tail:
                # ⚠️⭐ 2026-10-05（`/retro`）：**带上件名** —— 子进程的尾巴行是**先于**下面那行
                #   "结果行"打印的 ⇒ 不加归属时，读者会把它当成**上一支**的失败原因
                #   （当天实测误读一次：把 `_mut_linewalls` 的自检当成 `_mut_injectsplice` 的）。
                print(f"        [{p.name}] {x[:170]}")
    except subprocess.TimeoutExpired:
        print(f"        [{p.name}] ⚠️ 超过 {timeout}s 未结束 ⇒ **算未验证**（⛔ 不当通过）")
        rc = 124
    return rc, time.time() - t


def main() -> int:
    args = sys.argv[1:]
    if '--selftest' in args:
        return selftest()
    if not args:
        print('按影响明确选择 --cases <变异件名...>；普通改动不默认执行全部KEY')
        return 2
    timeout = 900
    if "--timeout" in args:
        timeout = int(args[args.index("--timeout") + 1])
    fast_only = "--fast" in args
    # ⚠️⭐ 2026-10-06（`TAIL-239` 第 3 步）：**选集自检在最前面跑，且各档都跑** ——
    #   缺口件在 `--fast` / 全套 / `--all` 三条路上都"不会被跑" ⇒ 哪条路都得先报出来。
    #   （原先只查 `KEY` 里有没有件消失的那段并进来了 —— 覆盖面更大：缺口 + 名单陈旧都归它。）
    if "--cover-only" in args:
        return report_cover()
    if report_cover():
        return 1
    if "--all" in args:
        cases = [(p.name, "（按需全跑）") for p in sorted(MUT.glob("_mut_*.py"))]
    else:
        cases = [(n, why) for n, why in KEY if (MUT / n).exists()]
        if fast_only:
            skipped = [n for n, _ in cases if n in SLOW_KEY]
            cases = [(n, w) for n, w in cases if n not in SLOW_KEY]
    if '--cases' in args:
        requested = []
        for name in args[args.index('--cases')+1:]:
            if name.startswith('--'): break
            requested.append(name)
        registry = dict(KEY) | KEEP_OUT
        if not requested or set(requested)-set(registry):
            print('变异选择为空或不在活件登记中，未执行')
            return 2
        cases = [(n, registry[n]) for n in dict.fromkeys(requested)]

    bad: list[str] = []
    fast_hit: list[str] = []
    slow_hit: list[str] = []
    spent = 0.0
    mode = "快集（--fast）" if fast_only and not ("--all" in args) else "关键集"
    print(f"── 变异自证（{len(cases)} 支 · {mode} · timeout {timeout}s/支）")
    if fast_only and not ("--all" in args):
        print(f"   ⏭ 已按需跳过慢集 {len(SLOW_KEY)} 支 —— ⛔ 本次**没验**它们；"
              f"只补验受影响判据/机制的对应隔离自证")
    import os
    os.environ.pop("ACC_RESULTS_PATH", None)
    related = "--related" in args
    if related and ("--fast" in args or "--all" in args):
        print("相关集不能与 --fast / --all 混用")
        return 1
    receipt = _gate.open_receipts(related=related, git_ok=_scope.changed_paths() is not None)
    required = {name for name, _ in cases if receipt is None or
                receipt.required("tools/mut/" + name, [])}
    selected = [(name, why) for name, why in cases if name in required]
    _gate.validate_selection({name for name, _ in selected}, {name for name, _ in cases}, required)
    for name, _ in cases:
        if name not in required:
            print("   ⏭", name, "检查、输入、环境未变，复用已有通过证明")
    cases = selected
    for name, why in cases:
        rc, sec = run_one(MUT / name, timeout)
        if receipt is not None:
            receipt.record("tools/mut/" + name, [], rc)
        spent += sec
        flag = "✅" if rc == 0 else "⛔"
        print(f"  {flag} {name:32s} rc={rc:<3d} {sec:6.1f}s   {why}")
        if rc:
            bad.append(name)
        if name not in SLOW_KEY and name not in KEEP_FAST and sec > FAST_BUDGET:
            fast_hit.append(f"{name}（{sec:.1f}s）")
        if name in SLOW_KEY and sec > SLOW_BUDGET:
            slow_hit.append(f"{name}（{sec:.1f}s）")
    # ⚠️⭐ 2026-10-06（`TAIL-237`）：**秒数只在这里算** —— 上面每行都是当次实测值。
    #   ⛔ 别把它抄进代码注释/文档/票名（首次分层时抄了 6 处，同日 `/code-review` 判违规并已撤掉）。
    print(f"── 本次合计 {spent:.1f} 秒（{len(cases)} 支）")
    print("BAD:", bad)
    if bad:
        print("  ⚠️ 上面这些 = **反向灵敏度没跑过**（要么判据变了、要么靶烂了）—— ⛔ 别当它是「环境问题」，去看那一支。")
    # ⚠️⭐ **分层漂移的机器提醒** —— 快集里长出慢支 / 慢集里长出超长支时自动喊，
    #   ⛔ 不靠"谁记得回来看一眼"（那正是本仓反复吃的那类静默漂移）。
    if fast_hit:
        print(f"  ⚠️ **快集超时提醒**：{'、'.join(fast_hit)} 已超 {FAST_BUDGET:.0f}s "
              f"⇒ 该挪进 `SLOW_KEY`（本件单一出口），否则每轮都在吃它的秒数。")
    if slow_hit:
        print(f"  ⚠️ **慢集过长提醒**：{'、'.join(slow_hit)} 已超 {SLOW_BUDGET:.0f}s "
              f"⇒ 该看它为什么变慢（靶件变大？多跑了一次真机？）。")
    if receipt is not None:
        receipt.save(1 if bad else 0)
    return 1 if bad else 0


def selftest():
    """覆盖登记与隔离拒绝在临时名字空间验证，正式文件不作靶。"""
    import tempfile
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as temp:
        folder = pathlib.Path(temp)
        for name in {n for n, _ in KEY} | set(KEEP_OUT):
            (folder/name).write_text('"""fixture"""\n', encoding='utf-8')
        with patch.dict(globals(), MUT=folder):
            assert cover_gap() == ([], []), '正常登记不能误伤'
            extra=folder/'_mut_unregistered.py'; extra.write_text('pass\n',encoding='utf-8')
            assert cover_gap()[0], '未登记不能静默漏选'
            extra.unlink()
            (folder/KEY[0][0]).unlink()
            assert cover_gap()[1], '陈旧登记不能静默放行'
        with patch.object(subprocess,'run',side_effect=AssertionError('不得启动正式写靶脚本')):
            assert run_one(folder/'_mut_docaudit.py', 1)[0] != 0
        from types import SimpleNamespace
        with patch.object(subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='fixture', stderr='')) as dispatch:
            for name in ('_mut_tbl.py', '_mut_design_rules.py', '_mut_proc_split.py',
                         '_mut_proc_split_shell.py', '_mut_tail262.py', '_mut_tail264_266.py', '_mut_ui_workflow.py'):
                assert run_one(folder/name, 1)[0] == 0, '已确认隔离入口不得被拒绝'
            assert dispatch.call_count == 7
    print('自测 变异登记缺口、陈旧项、正常放行及非隔离脚本拒绝通过')
    return 0


if __name__ == "__main__":
    sys.exit(main())
