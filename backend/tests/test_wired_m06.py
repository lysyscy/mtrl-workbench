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
SHELL = (ROOT / "backend" / "app" / "web" / "index.html").read_text(encoding="utf-8")
ROUTER = (ROOT / "backend" / "app" / "mod06_proc" / "router.py").read_text(encoding="utf-8")


def _view_body(tag: str) -> str:
    """取 `V.<tag>` 切片（**花括号配平**，不靠"下一个 V." —— 中间夹着顶层函数）。"""
    i = SHELL.find(f"\n{tag}=()=>{{")
    assert i > 0, f"壳里找不到 `{tag}=()=>{{`"
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
    return SHELL[i:k + 1]


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
    boot = SHELL[SHELL.find("async function boot() {"):][:2600]
    assert "soft('机械 6 列', reloadMech)" in boot, "`boot()` 没拉机械值"
    # ⚠️ 顺序：m05 的机械欠款由它派生 ⇒ 必须先于付款域那一路
    assert boot.find("soft('机械 6 列', reloadMech)") < boot.find("soft('付款域', reloadM05)"), \
        "`reloadMech` 必须在 `reloadM05` **之前**（m05 的机械欠款由它派生）"


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
    body = _view_body("V.m06")
    assert 3000 < len(body) < 12000, f"`V.m06` 切片长度 {len(body)} 可疑 —— 配平可能跑偏"
    assert "API." not in body, "`V.m06` 里出现了 API 调用 ⇒ 原型渲染逻辑被改（该走适配层）"


# ============================================================== `TAIL-38` · 录机械费入口


@acc()
def test_录机械费入口挂在BIND钩子且不改切片():
    """⭐ 原型 `V.m06` **没画**「录机械费」入口（机械 6 列在原型里是只读的）⇒ 按 §5.2.5 ③ 自行设计。

    ⛔ **不改 `V.m06` 一行**：走原型自己的 `BIND` 钩子（渲染后往页首注入一条工具栏）。
    """
    assert "BIND.m06 = function ()" in SHELL, "壳里没有 `BIND.m06`（录机械费入口没挂上）"
    assert 'data-act="mechOpen"' in SHELL, "入口按钮没挂 `mechOpen` 动作"
    body = _view_body("V.m06")
    assert "mechOpen" not in body, "入口被塞进了 `V.m06` 切片（应走**切片外**的 `BIND` 钩子）"


@acc()
def test_录机械费走后端且不在前端复写判据():
    """⭐ 反向：不许本地改 `MACH6` 冒充落库（假成功）；校验（负数 / 非数字）也不在前端复写。"""
    i = SHELL.find("mechOk:async ()=>{")
    assert i > 0, "`mechOk` 没改成 async（异步走后端）"
    body = SHELL[i:i + 900]
    assert "API.m06MechSave(" in body, "`mechOk` 没走 `/api/m06/mech`"
    assert "MACH6[" not in body, "`mechOk` 还在本地改 `MACH6` 冒充落库（假成功）"
    assert "reloadMech()" in body, "`mechOk` 成功后没「以后端为准重拉」"


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
    """⭐ 判据点**搬家**（`§19` 批 2）：原先钉在旧页 html（`name="mech_i"` 有、`name="in_/out_"` 没有）。
    改指**新壳**的「录机械费」弹窗：它**只**由 `MECH_LABELS`（**后端**给的列名）生成 `mech_` 键，
    ⛔ 不产生任何**材料列**的输入面（机械列可录 ≠ 材料列可录 —— §5.2）。
    """
    assert "values['mech_'+i]" in SHELL, "机械值没按 `mech_` 键组装"
    assert 'id="mechIn' in SHELL, "机械列没有输入框"
    for bad in ("values['in_", "values['out_", 'id="in_', 'id="out_'):
        assert bad not in SHELL, f"壳里出现了材料列的输入面：{bad}（材料列只读是铁律）"


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
    assert 400 < len(body) < 2500, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"
    assert "ct.includes('application/json')" in body, "没按 content-type 分流"
    assert "d.message||'后端没给原因'" in body, "失败时没把后端的中文原因给用户"
    assert "if(!r.ok) return toast(`<b>导出没能完成</b>：HTTP ${r.status}`" in body, \
        "非 2xx 没显式报错（会静默产出空文件）"
