"""`MOD-06` 过程资料的**机械源**接线 —— 离线断言。

⭐ 本轮的性质是「**只换来源、不改结构**」：`MACH6` 仍是 `{仓库名: {核算月: [6 列]}}`，
   所以壳里十几处引用（过程资料 17 列的机械 6 列 / 活动大表 / 机械结算 / 台账候选）**一行未改**。
   断言要钉住的正是这件事：**来源变了、引用面没变、且不许留取零出口**。

⚠️ 反向三条：
1. 不许再往壳里塞演示 `MACH6`（页面会显示演示值，与后端 KPI **打架**）。
2. 不许留 `m05MechSettle` 那种**取零出口**（它是"未接线"的临时态 ⇒ 接线后必须消失）。
3. `V.m06` 切片内不得出现 `API.`（原型渲染逻辑一行不改 —— `D18`）。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL, act_entry, page_slice, with_kernel, with_tbl  # noqa: F401  ← `P4`① 读取点收敛（`with_kernel`：`TAIL-67` · `with_tbl`：`TAIL-64`）
ROUTER = (ROOT / "backend" / "app" / "mod06_proc" / "router.py").read_text(encoding="utf-8")


# ── ⭐ 2026-10-04（`TAIL-219` 批 2b 余下 ②）：本件两把自造剪刀已换成语义窗口子 ──────────
#   · `page_slice("m06")` ⇒ `page_slice("m06")`：**页切片的唯一算法**（原先本件自写"花括号配平"，
#     与 `ui_parity`/`shell_src` 那套**并存** = 同一件事两套算法 —— 正是本要治的病）。
#     实测：`page_slice("m06")` 比旧切片**多**页尾那段横幅注释，而本件三条断言（无 `API.` / 无 `mechOpen` /
#     有 `TBL({head:DIFF_THEAD,`）**换后仍成立** ⇒ 换得了（量测件 `.scratch/local/_tail219_batch2b_rest.py`）。
#   · `_act_body(name)` ⇒ `act_entry(name)`：⭐ 逐字节一致（`procExpToggle` 789 / `mechOpen` 2577 都对上）。


@acc()
def test_机械演示数组已删():
    """⛔ 演示值会让本页机械数与后端 KPI **打架**（真假混用比不接更糟）。"""
    assert "const MACH6 = {" not in SHELL, "机械演示数组 `MACH6` 还在壳里"
    assert "let MACH6 = {};" in SHELL, "`MACH6` 没改成「空对象起手 + 后端填充」"


@acc()
def test_机械值来自后端且boot会拉():
    assert "m06Mech: () => API.get('/api/m06/mech')" in SHELL, "API 层没有 `m06Mech`"
    assert "async function reloadMech()" in SHELL, "没有 `reloadMech()`"
    assert "MACH6 = d.mech || {};" in SHELL, "`reloadMech()` 没把后端结果写进 `MACH6`"
    # ⚠️ 2026-09-19（`P3` 主体）：`boot()` 不再逐路拉（改成「进哪页拉哪页」）⇒ 判据**搬到取数表**上
    #    （⛔ 判据一字未改：机械值必须有取数出口；且**吃它的那几路必须等它**）。
    from tests.shell_load_helpers import (  # noqa: PLC0415
        DEP_BEFORE as _DEP, loaders as _loaders, page_load as _pl,
    )
    assert "机械 6 列" in _loaders(), "机械值没有取数出口"
    for page in ("m05", "m06", "m07"):
        assert "机械 6 列" in _pl()[page], f"`PAGE_LOAD['{page}']` 没拉机械值"
    assert "机械 6 列" in _DEP["付款域"], "`付款域` 不再等机械值（m05 的机械欠款会取到空）"


@acc()
def test_机械结构未变_引用面一行未改():
    """⭐ 本轮的全部好处就在这：**只换来源**，所以这些派生函数仍是原型写法。"""
    for frag in (
        "const mach6Arr=(wh,ym)=>(MACH6[wh]||{})[ym]||MACH6_Z;",
        "const machSettleOf=wh=>N2(Object.keys(MACH6[wh]||{}).reduce((a,k)=>a+machExtRent(wh,k),0));",
    ):
        assert frag in SHELL, f"机械派生函数被改动了（本轮只该换来源）：{frag[:46]}…"


@acc()
def test_m05的机械结算改用真源_且不再是取零出口():
    """接线后 `m05` 的机械欠款必须读真源 —— 那条「机械源未接线 ⇒ 取 0」的临时态要消失。"""
    assert "N2(machSettleOf(k)" in SHELL, "`V.m05` 的机械结算项没接真源"
    assert "m05MechSettle" not in SHELL, "取零出口 `m05MechSettle` 还有残留（临时态没清）"


@acc()
def test_后端机械读数端点存在且形状对齐原型():
    assert '@router.get("/api/m06/mech")' in ROUTER, "后端缺 `GET /api/m06/mech`"
    assert "MECH_COLUMNS" in ROUTER, "端点没按 `MECH_COLUMNS` 出 6 列"
    assert '"mech": out' in ROUTER, "端点没出 `mech` 键（壳按它填 `MACH6`）"


@acc()
def test_WIRED含m06():
    m = re.search(r"const WIRED=new Set\(\[([^\]]*)\]\);", SHELL)
    assert m and "'m06'" in m.group(1), "`WIRED` 里没有 `m06`"


@acc()
def test_视图切片未被改动():
    """⭐ 反向：`V.m06` 里不得出现 `API.` —— 渲染逻辑必须一行不改（`D18`）。"""
    body = page_slice("m06")
    assert 3000 < len(body) < 12000, f"`V.m06` 切片长度 {len(body)} 可疑 —— 配平可能跑偏"
    assert "API." not in body, "`V.m06` 里出现了 API 调用 ⇒ 原型渲染逻辑被改（该走适配层）"


# ============================================================== `TAIL-38` · 录机械费入口



@acc()
def test_录机械费走后端且不在前端复写判据():
    """⭐ 反向：不许本地改 `MACH6` 冒充落库（假成功）；校验（负数 / 非数字）也不在前端复写。"""
    body = act_entry("procMechSave")
    assert "API.m06MechSave(" in body
    assert "MACH6[" not in body
    assert "reloadMech()" in body
    assert "MECH_SECTIONS" not in body



# --------------------------------------- `ACC-RPT-PROC-001` 的**形态**半边（搬家 · §19 批 2）
#
# 这 9 条判据原先有 6 条带"页面形态"观测（`tab=` / 筛选栏 radio / 合计行 `colspan` 之和 /
# `tot` 行 …）。旧页删除（`D18`）⇒ 形态那半边**改指新壳**（⛔ 判据不删）。
# ⭐ 新壳把这些做成了**结构**（格数由表头派生 / 单选面板 / 选中即收起）—— 比逐格数更硬。


@acc("ACC-RPT-EXP-001", "001-03")
def test_导出展开区是独立出口_全壳恰好一处():
    """TAIL-265：项目与确认在独立弹窗，取消关闭；不再依赖表内浮层或镜像开关。"""
    assert SHELL.count("const procExpDlg=()=>") == 1, "导出弹窗必须有唯一构造出口"
    body = SHELL[SHELL.index("const procExpDlg=()=>"):SHELL.index("const procExpSelection=()=>")]
    assert "modal({" in body and 'id="procExportProjects"' in body
    assert 'data-act="procExpSave"' in body and 'data-act="procExpCancel"' in body
    assert "procExpStrip" not in page_slice("m06"), "页面仍渲染旧展开区"

@acc("ACC-RPT-EXP-001", "001-01")
def test_导出展开区是多选_每项目一份_多项目打zip():
    """TAIL-265：同窗复选框、全选/清空，保留每项目一份与多项目ZIP出口。"""
    body = SHELL[SHELL.index("const procExpDlg=()=>"):SHELL.index("const procExpSelection=()=>")]
    assert 'type="checkbox"' in body and 'type="radio"' not in body
    assert 'data-act="procExpPjPick"' in body
    assert 'data-act="procExpPjAll"' in body and 'data-act="procExpPjNone"' in body
    assert "每项目一份" in body and "ZIP" in body
    assert "const pjs=procExpPjs.slice();" in act_entry("procExpSave")

@acc("ACC-RPT-EXP-001", "001-01")
def test_一个项目都没选时导出按钮禁用():
    """清空后禁用导出且处理器防空；不静默回退当前项目。"""
    body = SHELL[SHELL.index("const procExpDlg=()=>"):SHELL.index("const bigCands =")]
    assert re.search(r"\$\{selected\.size\?'':'\s*disabled'\}", body), "初始空选择没有禁用导出"
    assert re.search(r"\w+\.disabled\s*=\s*!selected\.size", body), "全选/清空后没有同步禁用状态"
    assert "if(!pjs.length) return toast(" in act_entry("procExpSave")

@acc("ACC-RPT-EXP-001", "001-04")
def test_导出取数跟随当前所显示的表():
    """旧页：切表后「导出取数」提示逐一对上（`data-exp-tab`）。新壳对应：**导出 URL 带上当前表签**
    ⇒ 取数跟着用户眼前那张表走（⛔ 不许固定成表②）。"""
    assert "'&tab='+encodeURIComponent(procTab)" in SHELL, \
        "导出请求没带当前表签 ⇒ 会导出与眼前不一致的表"


@acc("ACC-RPT-EXP-001", "001-02")
def test_导出展开区默认选中本页当前项目():
    """弹窗没有选择时默认当前项目；不修改页面单选，也不取首个候选。"""
    body = act_entry("procExpToggle")
    assert "if(!procExpPjs.length&&procPj) procExpPjs=[procPj];" in body
    assert "procPj=" not in body and "PROC_PJS[0]" not in body
    assert "procExpDlg();" in body

@acc()
def test_导出面板一键开合_开合判据只认面板自身状态():
    """TAIL-265：点击直接开同一弹窗，取消后单次点击重开，取消不下载。"""
    body = act_entry("procExpToggle")
    assert "procExpDlg();" in body and "procExpOn" not in body
    assert "pjClose('procPj');pjClose('procExpPj');" in body
    cancel = act_entry("procExpCancel")
    assert "closeModal();" in cancel and "procExpPjs=[]" in cancel
    assert "dlExport" not in cancel and "procExpSave" not in cancel

@acc()
def test_过程资料机械手录不按截止月拦截():
    """导入截止月不再作为机械手录挡板。"""
    assert "MECH_SECTIONS = d.sections || {};" in SHELL, "后端机械段标记未落定"
    assert "API.m06MechSave(" in act_entry("procMechSave")
    assert "MECH_SECTIONS[wh]" not in act_entry("procMechSave"), "仍按历史段拒绝机械手录"


@acc("ACC-RPT-PROC-001", "001-01")
def test_默认停在调整后表():
    """旧页断言：不带参数 ⇒ `tab=1`（**表② 调整后**）。新壳对应 `procTab` 的**初值 = 1**
    ⇒ ⛔ 不许改成 0（原始）或 2（差异）。"""
    assert "let procPj='', procTab=1" in SHELL, "壳里 `procTab` 初值不是 1（表② 调整后）"


@acc("ACC-RPT-PROC-001", "001-04")
def test_项目筛选单选且选中即收起():
    """旧页：`type="radio"` ＋ `onchange` 提交 ＋ 收起态 `<details>`（且不给「全选 / 清空」）。
    新壳换成**单选面板** ⇒ claim 不变：**只单选** ＋ **选中即收起**。"""
    panel = SHELL[SHELL.index("const procPjPanel="):]
    panel = panel[:panel.index("\n")]
    assert "pickAct:'procPjPick'" in panel and "single:true" in panel, \
        "m06 的项目面板不是单选（`single:true`）—— 「不给多选」这条保证没了"
    assert "procPjPick:t=>{ procPj=t.dataset.pj; pjClose('procPj'); render(); }" in SHELL, \
        "选完项目没有收起面板"


@acc("ACC-RPT-PROC-001", "001-03")
def test_筛选栏不设只读年月框():
    """旧页断言筛选栏没有 `name="period"` / `readonly`。新壳同理：**核算月只作表内列**
    （§5.2.2）⇒ ⛔ 不给一个只读的年月框当摆设。"""
    assert 'name="period"' not in SHELL, "壳里出现了名为 `period` 的年月框"


@acc("ACC-RPT-PROC-001", "001-05")
def test_合计行格数由表头派生():
    """⭐ **三条判据点的共同形态**（`001-05` 逐列合计 · `001-06` 总求和各段 · `001-07` 差异表合计）：
    「**跨列数 = 表头列数**」。旧页靠"数 `colspan` 之和"验证；新壳把这条**做成了结构** ——
    `sumRowOf` 的格数 `n` **由 `thCols(thead)` 派生** ⇒ ⛔ 不可能与表头不一致（比逐格数更硬）。"""
    assert "const sumRowOf=(thead,rows,sums,opt={})=>" in SHELL
    assert "const n=thCols(thead)" in SHELL, \
        "合计行的格数不再由表头派生 ⇒「跨列数 = 表头列数」这条保证没了"
    # ⭐ 2026-09-29（`TAIL-64` P2②）：这两张表（**差异表** / **主表 表①·表②**）的**表外壳**也走统一出口
    #   `TBL`。钉**意图**（⛔ 不钉"切片里必须有 `<table`" —— 通用件一抽就假红，同 P0/P1b 那两次教训）：
    #   ① 切片**两处**都委托 `TBL`；② `TBL` 内核真把 rows 拼进 `tbody`（两段拼起来看）。
    #   自证 = `tools/mut/_mut_tbl.py` 的 M3/M4（去掉任一处委托 ⇒ 必须红）。
    body = page_slice("m06")
    assert "TBL({head:DIFF_THEAD," in body, "差异表的表外壳没走统一出口 `TBL`（`TAIL-64` P2②）"
    assert "TBL({head,rows:body" in body, "主表（表①/表②）的表外壳没走统一出口 `TBL`（`TAIL-64` P2②）"
    assert "rows.join('')" in with_tbl(body), \
        "`TBL` 内核没有把 rows 拼进 `tbody` ⇒ 表被掏空了（判据两段拼接：切片委托 ＋ 内核真做事）"


@acc("ACC-RPT-PROC-002", "001-08")
def test_正式段空态在壳里渲染成破折号而不是零():
    """⭐ 判据点**搬家**（`§19` 批 2）：原先钉在**旧服务端页**那一格（`render_proc_page` 的输出里
    空态渲染成「—」而不是 `0.00`）。旧页整体删除（授权 `D18`）⇒ 改指**新壳**（⛔ 判据不删）。

    ⚠️ 认法：壳的金额格式器 `M()` **对 `null` 直接回「—」** —— 这就是「**不臆造 0**」（`001-08`）
       在界面上唯一的落点；把它的 `null` 分支钉住（⛔ 不许退化成 `Number(null)||0`）。
    """
    assert "const M=n=>{if(n==null) return '—'" in SHELL, \
        "壳的金额格式器没有「null ⇒ —」这一支 ⇒ 空态会被渲染成 0（正是 001-08 要防的「臆造 0」）"


@acc("ACC-RPT-PROC-002", "001-03")
def test_机械录入口只送mech键_材料列没有输入面():
    """机械提交不产生材料列写入。"""
    assert "'mech_'+" in act_entry("procMechSave")
    for bad in ("values['in_", "values['out_", 'id="in_', 'id="out_'):
        assert bad not in SHELL


@acc()
def test_机械列名由后端给():
    """⚠️ 列名的**唯一主人 = 后端** `domain.MECH_COLUMNS` ⇒ 壳里的 `MECH_LABELS` 只是兜底。

    ⚠️ 断言必须**钉在 `reloadMech` 体内、且要求覆盖动作有前置条件**（= 条件来自后端响应）——
       只写「壳里含 `d.columns`」是**假绿**：同一函数里 `d.columns.forEach(...)` 也在，
       把前置条件改成 `false`（覆盖永不生效）照样能过。
    """
    i = SHELL.find("async function reloadMech()")
    assert i > 0, "壳里找不到 `async function reloadMech()`"
    body = SHELL[i:][:700]
    assert "MECH_LABELS" in body, "`reloadMech()` 里没有列名覆盖"
    assert re.search(r"if\s*\(\s*d\.columns", body), (
        "列名覆盖的前置条件不是来自后端响应（可能整个不生效 ⇒ 前端硬编码列名）"
    )


@acc()
def test_后端机械写端点存在():
    assert '@router.post("/api/m06/mech")' in ROUTER, "后端缺 `POST /api/m06/mech`（`TAIL-38` 的写入口）"
    # ⚠️ 必须**看 API 端点自己的函数体** —— 只写「文件里含 `mech_ui.parse_mech_values(`」是**假绿**：
    #    PRG 端点（`POST /m06/mech`）里也有一处 ⇒ 变异掉 API 端点那一处照样能过。
    i = ROUTER.find("def api_mech_save(")
    assert i > 0, "后端缺 `def api_mech_save(`"
    body = ROUTER[i:i + 2000]
    assert "mech_ui.parse_mech_values(" in body, (
        "写端点没走 `mech_ui.parse_mech_values`（判定该与 PRG 端点复用**同一出口**，不另写一套）"
    )


# --------------------------------------------------------------- 按模板导出（`TAIL-04` 片 4a）


@acc("ACC-RPT-EXP-001", "001-08")
def test_按模板导出走真下载而不是假成功():
    """⭐ `TAIL-04` **片 4a**：过程资料成品由后端模板填充生成 ⇒ 壳侧必须是**真下载**。

    ⚠️ 原型那个「保存到本地」是 `data-act="exp"`（诚实占位：**没有文件产生**）——
       接线后必须换成过程资料自己的动作，否则又变成"点了像成功、其实没文件"。
    """
    assert "procExpSave:async ()=>{" in SHELL, "缺真下载动作 `procExpSave`"
    assert "/api/m06/export?projects=" in SHELL, "没走过程资料导出端点"
    assert "'&tab='+encodeURIComponent(procTab)" in SHELL, \
        "没把**当前所显示的那张表**带给后端（001-04：取数跟随当前表，⛔ 不在前端另算）"
    assert "x-export-filename" in SHELL, "文件名没从 `X-Export-Filename` 带出（命名规则的主人在后端）"
    # ⛔ 旧的**假成功**必须消失
    assert 'data-act="exp" data-t="过程资料（按模板）"' not in SHELL, "预览弹窗还留着假成功的 `exp`"
    assert 'data-act="procExpSave"' in SHELL, "预览弹窗的「保存到本地」没接到 `procExpSave`"


@acc("ACC-RPT-EXP-001", "001-08")
def test_按模板导出失败必须给人原因不静默():
    """后端失败回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（没选项目 / 项目没数据 / 取不到展示名 /
    模板坏 / **显示区对账不过**）⇒ 壳必须**弹原因**，⛔ 不能静默、也不能当文件下载。"""
    i = SHELL.index("procExpSave:async ()=>{")
    body = SHELL[i:SHELL.index("\n procTab:t=>{", i)]        # 终点锚用**下一个动作名**（纯 ASCII）
    assert 100 < len(body) < 2500, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"
    _b = with_kernel(body)         # ⭐ `TAIL-67`：错误分类已抽到 `dlExport` 通用件
    assert "ct.includes('application/json')" in _b, "没按 content-type 分流"
    assert "后端没给原因" in _b, "失败时没把后端的中文原因给用户"
    assert "r.ok" in _b and "HTTP ${r.status}" in _b, \
        "非 2xx 没显式报错（会静默产出空文件）"


# ------------- ⭐ `TAIL-173`（2026-09-29 · 用户裁定 `A`）：`A4` 顺手报的两件，本批落地


@acc("ACC-RPT-EXP-001", "001-09")
def test_卡头不再出现那枚永不出结果的导出按钮():
    """⭐ `TAIL-173`-①（用户裁定 `A`）：`m06` 卡头原先**并排两枚导出** —— 真入口
    「批量导出（先选项目）…」（按 17 列模板导出）＋ 一枚**永远只会说「这一页还没有导出功能」**的
    「导出 Excel」（`EXP_ROUTES` 里没有「过程资料」）⇒ 点了必然空转，用户会以为坏了
    （守则 §4.4：相似元素不制造歧义）。

    ⚠️ **做法 = 渲染后摘除**（`BIND.m06`），⛔ **不改 `V.m06` 那一行**，两个原因：
       ① 切片是**逐行对位**核对的 ⇒ 删一行会让它后面**所有行**报漂移（`A4` 那次 101 条的教训）；
       ② `tests/test_tail04_pages.py` 把 `data-act="exp" data-t=…` 的**名单钉在源码上** ⇒ 删源码必红。
    ⚠️ **兜底那句不许顺手删**（`EXP_ROUTES` 上面的分支）：`m08` 朴素那份 / 已取消的差异清单仍在用它。
    ⚠️ **能证伪**：把 `BIND.m06` 里那两行摘除代码删掉 ⇒ 本件必红。
    """
    i = SHELL.find("addBind('m06', function")
    assert i >= 0, "找不到 `BIND.m06`"
    seg = SHELL[i:i + 3000]
    assert '[data-act="exp"][data-t="过程资料"]' in seg, \
        "`m06` 卡头那枚「永不出结果」的导出按钮**没有被摘掉**（用户点了会以为坏了）"
    assert ".remove();" in seg, "定位到了没删（摘除要真的 `remove()`）"
    # ⚠️ 兜底那句必须还在（别的页还在它上面）：这是"别顺手扩大改动面"的守卫
    assert "还没有导出功能" in SHELL, \
        "兜底说明被顺手删了 —— `m08` 朴素那份 / 已取消的差异清单还在用它"


@acc("ACC-RPT-PROC-001", "001-10")
def test_差异表的差额列只标方向不整列标红():
    """⭐ `TAIL-173`-②（用户裁定 `A`）：差异表**每一行本来就是差异** ⇒ 差额列整列标红
    **没有区分度**（守则 §4.5：颜色只承担语义），而方向本来就在值里
    （`const SIG=n=>(n>0?'+':'')+M(n)` ⇒ 正数带 `+`、负数带 `-`）⇒ 改成**只靠符号**，
    并给该列一句说明（悬停：正 = 上调 / 负 = 下调）。

    ⚠️ **只在 `V.m06` 切片里判**：同写 `style="color:var(--dg)">${SIG(a.newAmt-iv.amt)}` 在**别的页**
        （库存单据那条链路）也有 ⇒ 拿全文撞就是**假红**（本判据第一版正是这么红的，别拆这道收窄）。
    ⚠️ **能证伪**：把 `style="color:var(--dg)"` 加回**本页**差额格 ⇒ 本件必红。
    """
    i = SHELL.find("V.m06=()=>{")
    assert i >= 0, "找不到 `V.m06` 切片"
    j = SHELL.find("V.m07", i)
    slab = SHELL[i:j if j > i else i + 9000]
    assert 'style="color:var(--dg)"' not in slab, \
        "差异表的差额列又整列标红了（每行都是差异 ⇒ 红色没有区分度）"
    assert "正 = 上调 / 负 = 下调" in slab, "差额列没告诉用户方向怎么读"
