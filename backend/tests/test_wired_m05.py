"""`m05`（付款流水与欠款）**前端壳接线**断言（离线 · 静态）。

配套：运行时端到端 = `tools/probe/_e2e_m05_wired.py`（真机 ＋ 真库，跑完清理）·
结构一致性 = `tools/audit/ui_parity.py`（⭐ 2026-09-30 `TAIL-201`：`U1` 已退场 ⇒ 现只剩 **U2/U2b/U3/U4**；「壳变了没有」看 `shell_verify` ＋ **U2b 已接线页不得留演示数组**；
⚠️ `m05` 在 U1 里**有 1 条已登记漂移** —— `V.m05` 的机械结算项换数据源，理由写在登记簿里）。

⚠️ **本文件测不了什么**：静态检查（壳里有没有那些接线点），**不证明运行时真调通**。两把都要。

⭐ 反向断言是重点：**欠款 / 台账 / 付款统计不许再由前端自算**（那是第二份口径），
   写动作不许再用本地赋值冒充落库。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc

from tests.shell_src import SHELL, with_kernel  # noqa: F401  ← `P4`① 读取点收敛（`with_kernel`：`TAIL-67`）


def _slice(name: str, limit: int = 18000) -> str:
    """取壳里 `V.<name>=()=>{…}` 的切片（花括号配平）。

    ⚠️ `limit` 是"配平跑偏"的**哨兵**（配平歪了会一路吃到下一个函数 ⇒ 长度暴涨），⛔ 不是预算线：
       `V.m05` 2026-09-28 两次重设计（`TAIL-141` 显示层 ＋ `TAIL-142` 卡头按钮）后 **16.5k** ⇒
       旧哨兵 16000 当场误报（"配平可能跑偏"），实测**配平是对的**。字长本身归 `T5`（>400 行文件）管，
       ⛔ 别在这里再立一条预算。
    """
    i = SHELL.find(f"\nV.{name}=()=>{{")
    assert i > 0, f"壳里找不到 `V.{name}=()=>{{`"
    i += 1
    depth, k = 0, SHELL.find("{", i)
    while k < len(SHELL):
        if SHELL[k] == "{":
            depth += 1
        elif SHELL[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    body = SHELL[i:k + 1]
    assert 2000 < len(body) < limit, f"`V.{name}` 切片长度 {len(body)} 可疑 —— 配平可能跑偏"
    return body


# ------------------------------- `§19` 批 3：旧页删除后，几条**形态** claim 由新壳接管
# 原先在 `tests/test_page_m05.py` 里借**旧服务端页**观测（该文件已改守数据出口 ✓）。


@acc("ACC-FLOW-LED-001", "001-05")
def test_台账两侧共用同一个项目选择器且无切换口径():
    """§4.5.4：台账两侧**共用同一个**项目选择器（切一次两边都换）；⛔ 没有「切换口径」按钮。"""
    assert "const ledPjPanel=()=>projPanel({list:ledProjs,selected:()=>[ledCur()],pickAct:'ledPjPick'" in SHELL, \
        "两侧没有共用同一个项目选择器"
    assert "切换口径" not in _slice("m05"), "壳里出现了「切换口径」按钮"


@acc("ACC-FLOW-LIST-001", "001-04")
def test_撤销入口只在生效行且必须填原因():
    """§4.4.5：撤销按钮**只在生效行**出（已撤销那行给「—」）；撤销**必须填原因**（后端把关）。"""
    s = _slice("m05")
    assert 'data-act="revDlg"' in s, "流水行没有撤销入口"
    assert """${f.voided?'<span class="mut sm">—</span>':`<button class="btn sm dg" data-act="revDlg\"""" in s, \
        "撤销入口不是「只在生效行」出的"
    assert "撤销原因必填" in SHELL, "没写明撤销必须填原因"


@acc("ACC-FLOW-LIST-001", "001-06")
def test_流水空态跨列由表头派生且不分页():
    """空态行的 `colspan` **由表头派生**（⛔ 不写死）；该表**不做分页**（一次给全）。"""
    s = _slice("m05")
    assert "EMPTYROW(thCount(FL_THEAD)" in s, "空态行的跨列数不再由表头派生"
    assert "没有付款流水" in s, "空态提示丢了"
    assert "不做分页" in s, "没写明「不做分页」"


# --------------------------------------------------------------- 接线点（正向）


@acc()
def test_壳把m05标为已接后端并指向四个端点():
    assert "'m05'" in SHELL and "const WIRED=new Set(" in SHELL
    for fn in ("API.flows()", "API.debt()", "API.stats(", "API.ledger(", "API.flowRevoke("):
        assert fn in SHELL, f"缺接线点：{fn}"
    assert "/api/m05/flows?year_month=" in SHELL
    assert "/api/m05/ledger?project_id=" in SHELL


@acc()
def test_流水行与期初行在适配层完成转形():
    assert "function adaptFlow(x)" in SHELL and "function adaptOpening(x)" in SHELL
    # ⭐ 仓库名（归并键）与展示名分开 —— 拿展示名当键会静默失配
    assert "projKey: x.project_key || ''" in SHELL
    assert "proj: x.project_key || x.project_label || ''" in SHELL
    assert "proj: x.project_display || ''" in SHELL


@acc()
def test_读写都走统一的出口与外壳():
    assert "async function reloadM05()" in SHELL
    assert "async function m05Act(fn, okMsg, ms)" in SHELL
    # 期初 / 备注目前只有 PRG 表单端点 ⇒ 必须用表单编码发（不是 JSON）
    assert "postForm: async (url, obj) => {" in SHELL
    assert "URLSearchParams(obj || {})" in SHELL
    # ⭐ 2026-09-29（`TAIL-64` P2④）：本页**两张表的表外壳**也走统一出口 `TBL`（⛔ 别退回裸
    #   `<table class="dt" data-sort …>`）。⚠️ `m05:ledger-*` 的 key 是**拼出来**的（三栏台账共用一处渲染）。
    #   自证 = `tools/mut/_mut_tbl.py` 的 M9（台账去委托）/ M10（流水去委托）⇒ 各自必须红。
    s = _slice("m05")
    assert "TBL({head:LED_THEAD,key:'m05:ledger-'+sc," in s, \
        "逐月欠款台账没走统一出口 `TBL`（`TAIL-64` P2④）"
    assert "TBL({head:FL_THEAD,key:'m05:flows'," in s, \
        "付款流水表没走统一出口 `TBL`（`TAIL-64` P2④）"


# --------------------------------------------------------------- 反向（不许再出现）


@acc()
def test_欠款台账统计不再由前端自算():
    """⭐ 三块的**唯一出口 = 后端**（§4.5.1 / §4.5.4 / §4.5.5）。

    原型在浏览器里按 `NO` / `MACH6` / `JCs` / `LGs` 现算 —— 那是第二份口径，
    而且**机械会读到演示数据**（与后端 KPI 打架）。
    """
    # `debts()` 只读后端
    assert "const d = M05.debt || {};" in SHELL
    assert "d.by_category || []).find(x => x.category === c" in SHELL
    # 台账行只读后端
    assert "const ledOpen=(sc,proj)=>{ const side=m05Side(sc)" in SHELL
    assert "const ledRows=(sc,proj)=>{ const side=m05Side(sc)" in SHELL
    # 付款统计只读后端
    assert "const pstData=()=>{ const st=M05.stats||{};" in SHELL
    # ⛔ 旧的**前端自算**必须消失
    assert "const 辅材=N2(F-FP+lgF)" not in SHELL, "欠款还在前端算"
    assert "const ms=NO.filter(n=>ntLive(n)&&n.cat===sc&&ntProjKey(n)===proj).map(ntYm);" not in SHELL, \
        "台账还在前端按月拼行"
    assert "const axes=pstMonthsOfYear" not in SHELL, "付款统计还在前端拼时间轴"


@acc()
def test_写动作不許用本地赋值冒充落库():
    assert "f.voided=true; f.reason=rs;" not in SHELL, "撤销还在改内存"
    assert "LGs.push(O(['LG'" not in SHELL, "期初还在前端 push"
    assert "LGs.splice(i,1); closeModal()" not in SHELL, "期初删除还在改内存"
    assert "LEDNOTE[k]=v" not in SHELL, "台账备注还在写前端缓存"


@acc()
def test_机械结算源已接线_读真源():
    """⭐ **本轮改动**（`TAIL-27` 第 6 页 · `MOD-06` 机械源接线）：机械结算源 = 过程资料机械 6 列，
    现已接后端（`/api/m06/mech` ⇒ 壳里 `MACH6`）⇒ `V.m05` 的机械结算项**恢复原型写法**
    `machSettleOf(k)`，与原型**逐字一致**（那条 `ui_parity` 登记漂移已消号）。

    ⚠️ 本条断言**原先钉的是「未接线 ⇒ 取 0」的临时态**（那时取演示 `MACH6` 会让本页机械数
       与后端 KPI 打架）—— 接线完成后**按事实反转**：必须读真源，且取零出口必须消失。
    """
    assert "m05MechSettle" not in SHELL, "取零出口 `m05MechSettle` 还在（临时态没清）"
    assert "N2(machSettleOf(k)" in SHELL, "`V.m05` 的机械结算项没接真源"
    # ⚠️ 不要用「从 `V.m05=` 扫到 `V.m06=`」这种切片 —— 中间夹着 MOD-06 的**顶层助手函数**
    #    （本文件第一次就是这么切歪的）。**钉具体串**更准。


@acc()
def test_已接线页的演示数组必须已删():
    assert "const LG = [" not in SHELL
    assert "LG.map(r=>O(r,LG_COLS))" not in SHELL


# --------------------------------------------------------------- 台账**显示层**重设计（`TAIL-141` · 方案 `B`）
# ⭐ 2026-09-28（用户「逐月欠款台账的交互和显示重新设计吧」⇒ 选 `B`）：**只改显示层** ——
#    口径一个字没动，⛔ 表头 `LED_THEAD` 一字未改（⚠️ 2026-09-30 `TAIL-201`：`U5` 已**退场** ⇒ 这条理由作废；真理由 = 它是**界面口径**，改了要跑 `acc_*` ＋ 真机）。


@acc("ACC-FLOW-LED-001", "001-12")
def test_台账的现状数_截至行与入口名都钉住():
    """守四件（守则 §2.6 §2.7 先给结论 · §4.7 数字口径透明 · §4.4 相似元素不歧义 · §5.9 优先级）。

    ⚠️ 这四条**都是"下一个人顺手改回去"的高危处** —— 尤其表尾那个「合计：」是**旧形态的原话**，
       谁重排版式都可能把它抄回来（那时"当前欠多少"又重新变成一个没人读得懂的格子）。
    """
    # ① 每栏标题行**先给"现状"**（§2.6 能算出来的别让人自己数 · §2.7 结论贴在对象上）
    assert "本项目当前欠款（含期初）" in SHELL, "标题行没给「本项目当前欠款」⇒ 用户又得自己把「欠款」列加一遍"
    assert "${esc(mLast.ym)} 新增" in SHELL, "标题行没给「最近一月新增」（那是台账里唯一属于「当月」的那个数）"
    # ⭐ 它必须与**表尾那一格同源**（同一处算出来）—— 两处各算一份 ⇒ 迟早打架（§4.7）
    assert "const cur=N2(rows.reduce((a,r)=>a+(r.s-r.p),0));" in SHELL, \
        "标题行那个数不是从表尾同一个出口算出来的（各算一份 ⇒ 迟早打架）"
    # ② 表尾正名（§4.7）：原来叫「合计：」⇒ 会被读成"各月数字相加"
    assert "lead:'<b>合计：</b>'" not in SHELL, "表尾又退回「合计：」（那会被读成各月数字相加）"
    assert "截至 ${esc(upto)}" in SHELL and "自期初起累计" in SHELL, "表尾没写明「截至哪个月 · 自期初起累计」"
    assert "当前欠款</span>" in SHELL, "表尾「欠款」那格没标出它就是「现在还欠多少」"
    # ③ 两个期初录入入口**不许同名并排**（§4.4；旧的「＋ 录入期初占位行」两栏各一个）
    assert ">＋ 录入${sc}期初</button>" in SHELL, "期初录入按钮文案没带分类名（两栏认错就录错池子）"
    assert "＋ 录入期初占位行</button>" not in SHELL, "同名并排的旧按钮文案又回来了"
    # ④ 空月压暗（§5.9）—— ⚠️ 台账**空月也出行**，不压暗则"哪个月真发生过事"看不出来
    assert "const z=!r.open&&!N2(r.s)&&!N2(r.p)" in SHELL, "空月压暗没了（每个月看起来一样重）"
    # 备注可编辑性要**提前说**（§2.4：不给提示，用户不知道点一下就改）
    assert "点这一格就能改" in SHELL, "备注可编辑没提前说"
    # ⑤ ⭐ 2026-09-29（`A1` 逐页）：**引用了已经删掉的东西 = 页面在讲一件不存在的事**（守则 §4.2 状态必须真实）。
    #    本页 4 条 KPI 已于 2026-09-28 **全删**（用户判「无用」），而标题行与卡内说明里还写着
    #    「与上方 KPI 不是同一个数」⇒ 用户会**抬头去找一排已经不存在的 KPI**（`TAIL-161` 同族教训：
    #    删掉一块东西时，同一批必须扫一遍"还在说它的那些话"）。
    assert "与上方 KPI 不是同一个数" not in SHELL, \
        "又说「与上方 KPI 不是同一个数」—— 那排 KPI 2026-09-28 已全删，页面在讲一件不存在的事"
    assert "与上方全部项目的 KPI" not in SHELL, "同上（另一处措辞）"
    assert SHELL.count("与上方那三栏不是同一个数") >= 2, \
        "没写明「与上方那三栏不是同一个数」（那三栏**按项目分列**、台账这两栏只算选中的那一个）"
    # ⛔ 墓碑：`V.m05` 里那句 `const d=debts();` 随 KPI 删除一起消失（§5.1「答不出为什么需要它，就删」）
    assert "const d=debts();" not in _slice("m05"), "`V.m05` 里又出现没有读者的 `const d=debts();`"


@acc("ACC-FLOW-LED-001", "001-13")
def test_台账卡头按钮分组与点开有反馈都钉住():
    """`TAIL-142` ＋ `TAIL-144`（用户：①「上面几个按钮的显示和交互优化一下」② 截图报障
    「我要选辅材机械表的项目，要在右上角选离那么远；我要统一导出，点按钮后又要跑到最左边选项目」）。

    守则：§2.7（**控件贴在它管的对象上**）· §4.4（相似元素不歧义）· §5.5（点开必须有反馈）·
    §3.4（说明贴在对象旁，别拿长 toast 顶替）· §5.9（优先级）。
    """
    s = _slice("m05")
    # ① ⭐ 控件贴对象：「看哪个项目」必须在**两栏台账之前**（它管的就是下面那两张表）。
    #    ⚠️ 这条是 `TAIL-144` 的核心：它原来挂在卡头右上角 ⇒ 用户"要在右上角选，离那么远"。
    #    ⚠️⚠️ 一律钉**标记串**（`<span class="mut sm">…</span>`），⛔ 别钉裸文案 —— 源码注释里也出现过
    #       「看哪个项目（两侧共用）」这句 ⇒ 钉裸文案时"把控件删掉"仍会**假绿**（反向灵敏度 M10 实测抓到）。
    _PICK = '<span class="mut sm">看哪个项目（两侧共用）</span>'
    assert _PICK in s, "「看哪个项目」那条标签没了"
    assert s.index(_PICK) < s.index("${ledHalf('辅材')}"), \
        "「看哪个项目」又跑到表格后面/卡头右上角去了（守则 §2.7：控件要贴着它管的那两张表）"
    # ② ⭐ 卡头**只留一个**导出入口（用户 2026-09-13 裁定「卡头一个导出入口」；上一版挤了三个）
    _h = s.index("<h4>逐月欠款台账")
    head = s[_h:s.index("</h4>", _h)]
    assert head.count("data-act=") == 1 and 'data-act="ledExpToggle"' in head, \
        f"卡头上了不止一个入口（实测 {head.count('data-act=')} 个）—— ⛔ 别再把导出件塞回卡头"
    # ⭐ 2026-09-28：按钮名由孤零零的「导出…」改成「**批量导出（先选项目）…**」—— 用户报
    #    「点掉筛选后**不知道去哪里找**」（守则 §10「按钮怎么起名」：动词在前 ＋ 名字里能看出下一步 ＋ 有下文带 `…`）。
    assert ">批量导出（先选项目）…</button>" in head, "卡头那个唯一入口的按钮名没说明「要先选项目」"
    # ③ ⭐ 两个导出在同一条面板里，**各自的项目范围挨着自己的动作**（治"点按钮后跑到最左边选项目"）
    strip = SHELL[SHELL.index("const ledExpStrip=()=>"):SHELL.index("const lgPjPanel=()=>")]
    assert "① 逐月台账" in strip and "② 总欠款汇总" in strip, "两个导出没在同一条面板里（分两处又会让人来回跑）"
    # ⚠️ 2026-09-30（`TAIL-64` `P4-d-b`）：那枚项目按钮**改走统一出口 `PJB`** ⇒ 它的落点改成**委托形式**
    #    （**判词不变**：面板里这几件都在）；余下四枚是普通按钮，照旧钉 `data-act`。
    for act in ("PJB({act:'ledExpPjToggle'", 'data-act="ledExpOk"', 'data-act="ledExpCancel"',
                'data-act="debtPick"', 'data-act="debtExpAll"'):
        assert act in strip, f"面板里缺 {act}（导出件跑到别处去了）"
    assert "选择项目（" in strip, "「导出总欠款」的范围按钮不在它旁边"
    assert ">导出台账</button>" in strip and ">导出总欠款</button>" in strip, "两个导出的动作名不清楚"
    # ④ 两个 toggle 点开**必须自己带 `on`**（由展开态决定，⛔ 不是写死）
    # ⚠️ `P4-d-b`：那串动态类改由 `PJB` 的 `cls` 参**传进去**（判词不变：按钮仍看展开态、点开自己变样）。
    assert """cls:`btn${pjIsOpen('ledPj')?' on':''}`""" in s, "项目选择器按钮不看展开态（点开自己不变样）"
    assert """class="btn pri${ledExpOn?' on':''}\"""" in s, "导出入口不看展开态（点开自己不变样）"
    assert ".btn.on{background:var(--pri-l);border-color:var(--pri-bd);color:var(--pri-d)}" in SHELL, \
        "缺 `.on` 按钮态（且必须复用 `--pri*` token，⛔ 不另造视觉语言 —— 守则 §4.5）"
    # ⑤ ⛔ DOM 注入那条老路已撤（`TAIL-138` 当年为了"零切片漂移"把按钮注入进卡头 ⇒ 就是它把卡头挤成三个）
    assert "anchor.dataset.debtExp" not in SHELL, "`BIND.m05` 的注入又回来了（导出件会被塞进卡头）"
    # ⑥ 参数按钮按「设没设」分主次（与 `pjTypePick` / `uiScaleSet` 同一套写法）
    assert """class="btn sm${DEBTPICK.length?' pri':' gost'}\"""" in SHELL, \
        "「选择项目」没按「已设 / 未设」分主次（未设 = 全部 ⇒ 该是次要态）"
    # ⑦ 说明要贴在面板里；⛔ 别再用长 toast 顶替（墓碑：所有「已展开…」回执都不许挂 6200ms）
    for line in SHELL.splitlines():
        if "toast('已展开" in line:
            assert ",6200)" not in line, \
                f"「已展开」回执又变回 6200ms 的长机制说明：{line.strip()[:70]}"
    assert "toast('已展开「导出台账」：默认选中<b>本页当前项目</b>（可多选）')" in SHELL, \
        "台账导出面板的回执不是短句（应只剩「点上了」这一件）"
    assert "每次打开<b>默认选中本页当前项目</b>" in SHELL, "面板里没写「默认选中本页当前项目」"
    # ⑧ 真机段在位（本批的新覆盖：**点开自己变样** ＋ 不开长 toast —— 离线看不见）
    probe = Path(__file__).resolve().parents[2] / "tools" / "probe" / "_shell_m05head.py"
    assert probe.exists(), "真机段 `_shell_m05head.py`（㉚）不在位"
    assert "check_m05head(page, errors)" in (probe.parent / "_shell_smoke.py").read_text(encoding="utf-8"), \
        "真机段 ㉚ 没被编排件 `_shell_smoke.py` 调用"


# --------------------------------------------------------------- 台账导出（`TAIL-04` 片 2＋3）


@acc("ACC-FLOW-LED-001", "001-11")
def test_台账导出走真下载而不是假成功():
    """⭐ `TAIL-04` **片 2＋3**：台账成品由后端模板填充生成 ⇒ 壳侧必须是**真下载**。

    ⚠️ 原型那个「保存到本地」是 `data-act="exp"`（诚实占位：**没有文件产生**）——
       接线后**必须换成**本页自己的动作，否则又变成"点了像成功、其实没文件"。
    """
    assert "ledExpSave:async ()=>{" in SHELL, "缺真下载动作 `ledExpSave`"
    assert "/api/m05/ledger/export?projects=" in SHELL, "没走台账导出端点"
    assert "'&ym='+encodeURIComponent(bjMonth(-1))" in SHELL, \
        "报告月没原样带给后端（§9.2 材料报表类默认 = 上月；⛔ 前端不另算一份期间）"
    assert "x-export-filename" in SHELL, "文件名没从 `X-Export-Filename` 带出（命名规则的主人在后端）"
    # ⛔ 旧的**假成功**必须消失
    assert 'data-act="exp" data-t="逐月欠款台账"' not in SHELL, "预览弹窗还留着假成功的 `exp`"
    assert 'data-act="ledExpSave"' in SHELL, "预览弹窗的「保存到本地」没接到 `ledExpSave`"


@acc("ACC-FLOW-LED-001", "001-11")
def test_台账导出失败必须给人原因不静默():
    """后端失败回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（没选项目 / 项目不在档案 / 模板坏 /
    **显示区对账不过**）⇒ 壳必须**弹原因**，⛔ 不能静默、也不能当文件下载。"""
    # ⚠️ 取体的**终点锚**用**下一个动作名**（`ledNote`，纯 ASCII）—— 别用中文注释当锚：
    #    中文注释里哪怕一个标点不同就找不到（本文件实测踩到一次），而动作名是代码结构。
    i = SHELL.index("ledExpSave:async ()=>{")
    body = SHELL[i:SHELL.index("\n ledNote:t=>{", i)]
    assert 100 < len(body) < 2500, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"
    _b = with_kernel(body)         # ⭐ `TAIL-67`：错误分类已抽到 `dlExport` 通用件
    assert "ct.includes('application/json')" in _b, "没按 content-type 分流"
    assert "后端没给原因" in _b, "失败时没把后端的中文原因给用户"
    assert "r.ok" in _b and "HTTP ${r.status}" in _b, \
        "非 2xx 没显式报错（会静默产出空文件）"


@acc("ACC-FLOW-LED-001", "001-14")
def test_总欠款导出与期初删除都不许静默失败():
    """⭐ 2026-09-28（用户走查两条「点了没反应」）—— 两条**同源**缺陷，各钉一条静态断言。

    ① **「导出总欠款」**：壳里曾写 `dlExport(url, …)` —— `url` 是**未声明的标识符** ⇒ `ReferenceError`；
       而该动作是 `async` ⇒ 异常变成**未捕获的 promise rejection** ⇒ 界面**毫无反应**（连报错都不给）。
    ② **「删除期初行」**：`delLg` 用 `LGs.find(x=>x.id===t.dataset.id)`，而 `adaptOpening` 曾把 id 写成
       **假值 `''`**（后端那时不返回 id）＋ `dataset.id` 恒是**字符串** ⇒ 恒不匹配 ＋ 静默 `return`。

    ⚠️ 这两处**离线判据原先 0 覆盖**（全仓搜 `debtExpAll` / `delLg` 无断言）⇒ 坏了没人知道 ——
       本条与 `tests/test_page_m05.py` 的「两侧同 id」合起来才算闭环（壳侧 ＋ 后端侧）。
    """
    # ① 总欠款导出：先看**本动作体**（⛔ 别全仓扫 `dlExport(url` —— `procExpSave` 那种
    #    「先 `const url=…` 再传进去」的写法是**对的**，一刀切会把好写法也判红，实测踩到一次）
    i = SHELL.index("debtExpAll:async ()=>{")
    act = SHELL[i:i + 2000]
    assert "/api/m05/debt/export" in act, "「导出总欠款」的动作体里没有后端端点 `/api/m05/debt/export`"
    # ⭐ 2026-09-28（同日第二批 · 用户口径）：它现在带 `projects=`（选择项目 · 顺序即行序）
    assert "projects=" in act, "「导出总欠款」没把「选择项目」的选择带给后端（`projects=`）"
    # ⭐ 老缺陷的**根因形态**：`url` 必须在**本动作体内声明**（⛔ 别用外层/不存在的标识符 ⇒ 点击静默失败）
    assert "const url=" in act, "「导出总欠款」的 `url` 必须在本动作体里**声明**（否则 async ⇒ 未捕获 rejection ⇒ 点了没反应）"
    assert "dlExport(url," in act, "「导出总欠款」必须真走统一下载出口 `dlExport`"
    # ①′ **选择项目**那套必须齐（多选 + 顺序 + 不落库）
    assert "debtPick:t=>{" in SHELL and "debtPickUp:t=>{" in SHELL and "debtPickOk:()=>{" in SHELL, \
        "缺「导出总欠款 · 选择项目」那一套动作（多选 / 调顺序 / 确定）"
    # ⭐ 2026-09-29（`TAIL-64` A′）：那张「选择项目」弹窗的表也走统一出口 `TBL` —— 且**刻意不可排**
    #   （`sort:false`：它的行序是**用户手工调的**，⛔ 给它排序入口会把用户调好的顺序搞乱）。
    #   自证 = `tools/mut/_mut_tbl.py` 的 M19（去掉委托）/ M21（`sort:false` 改回 `true`）都必须红。
    assert "TBL({cls:'cond',key:'modal:debtPick',sort:false," in SHELL, \
        "「选择项目」的表没走统一出口 `TBL`，或没声明「刻意不可排」（`sort:false`）"
    assert "选择项目（" in SHELL, "「选择项目」按钮文案没了（用户 2026-09-28 明确要求：叫得让人一眼明白）"
    assert "选题" not in SHELL, "壳里又出现「选题」这个说法（用户说看不懂，已统一改成「选择项目」）"
    # ② 期初行 id：不许写死假值，且比较必须归一成字符串（`dataset.id` 恒是字符串、`x.id` 是数字）
    assert "id: '', proj:" not in SHELL, \
        "`adaptOpening` 又把期初行 id 写死成假值 `''` ⇒ 「删除期初行」必然匹配不上、静默无反应"
    assert "id: x.id == null ? '' : String(x.id)" in SHELL, "`adaptOpening` 没把真 id 带出来（归一成字符串）"
    i = SHELL.index("delLg:t=>{")
    body = SHELL[i:SHELL.index("delLgOk:t=>{", i)]
    assert 100 < len(body) < 3000, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"
    assert "String(" in body, "`delLg` 没做 `String()` 归一（`dataset.id` 是字符串、`x.id` 是数字）"
    assert "toast(" in body, "`delLg` 找不到数据时必须给**可见反馈** —— 「点了没反应」正是本条的老毛病"
