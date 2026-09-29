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
from tests.shell_src import SHELL, with_kernel  # noqa: F401  ← `P4`① 读取点收敛（`with_kernel`：`TAIL-67`）
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


def _act_body(name: str) -> str:
    """取 `ACT.<name>` 的函数体（**花括号配平** —— 体里嵌着模板串与 `.map()`，⛔ 不能靠"下一个动作名"切）。

    ⚠️ 认法用**行首**（`^[ \\t]*name:`）—— ⛔ 不能拿 `f"\\n{name}:"`：动作是**缩进**在 `ACT = {…}` 里的
       （实测踩到：缩进后那个写法一处都匹配不上）；也不能裸匹配 `name:`（`data-act="mechOpen"` 里也有）。
    """
    m = re.search(rf"(?m)^[ \t]*{name}:", SHELL)
    assert m, f"壳里找不到 `ACT.{name}` 的定义"
    i = m.start()
    k, depth = SHELL.find("{", i), 0
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
    # ⚠️ 2026-09-19（`P3` 主体）：`boot()` 不再逐路拉（改成「进哪页拉哪页」）⇒ 判据**搬到取数表**上
    #    （⛔ 判据一字未改：机械值必须有取数出口；且**吃它的那几路必须等它**）。
    from tests.shell_load_helpers import (  # noqa: PLC0415
        DEP_BEFORE as _DEP, loaders as _loaders, page_load as _pl,
    )
    assert "机械 6 列" in _loaders(), "机械值没有取数出口"
    for page in ("m04", "m05", "m06", "m07"):
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
    # ⚠️ 2026-09-26：原先这里切**固定 900 字符** —— 往 `mechOk` 里加几行注释/兜底就把
    #    `reloadMech()` 挤出窗口 ⇒ **假红**（本次就是这么红的）。改成切到**本动作结束**
    #    （下一个段头块注释为止），不再靠魔法数字。
    seg = SHELL[i:]
    nxt = seg.find("\n/*", 1)
    body = seg[:nxt] if nxt > 0 else seg[:4000]
    assert len(body) > 200, "切出来的 `mechOk` 太短 —— 本页形态变了就同批改本件"
    assert "API.m06MechSave(" in body, "`mechOk` 没走 `/api/m06/mech`"
    assert "MACH6[" not in body, "`mechOk` 还在本地改 `MACH6` 冒充落库（假成功）"
    assert "reloadMech()" in body, "`mechOk` 成功后没「以后端为准重拉」"
    # ⭐ 2026-09-26（`TAIL-107`）：往历史段手录要**在本地就拦住并说清**（别等后端拒、那时人已填完 6 格）
    assert "MECH_SECTIONS" in body and "history" in body, \
        "`mechOk` 没有拦「往历史段手录」这一档 —— 用户会填完 6 格才被拒（守则 §5.5：要提前说清）"


# --------------------------------------- `ACC-RPT-PROC-001` 的**形态**半边（搬家 · §19 批 2）
#
# 这 9 条判据原先有 6 条带"页面形态"观测（`tab=` / 筛选栏 radio / 合计行 `colspan` 之和 /
# `tot` 行 …）。旧页删除（`D18`）⇒ 形态那半边**改指新壳**（⛔ 判据不删）。
# ⭐ 新壳把这些做成了**结构**（格数由表头派生 / 单选面板 / 选中即收起）—— 比逐格数更硬。


@acc("ACC-RPT-EXP-001", "001-03")
def test_导出展开区是独立出口_全壳恰好一处():
    """⭐ 判据点**搬家**（`§19` 批 2）：旧页断言展开区渲染在 `.tw`（**滚动容器**）**之外**、
    全页**恰好一处** —— 否则浮层面板会被裁掉。新壳对应：展开区是**独立渲染出口**
    `procExpStrip`，且在壳里**只被调用一次**（⛔ 不是表体模板里的一段）。"""
    assert "const procExpStrip=()=>" in SHELL, "展开区没有独立出口"
    assert SHELL.count("procExpStrip()") == 1, "展开区不是恰好一处（会被裁 / 会重复）"
    assert "procExpOn?procExpStrip()" in SHELL, "展开区不是按开关独立渲染的一段"


@acc("ACC-RPT-EXP-001", "001-01")
def test_导出展开区是多选_每项目一份_多项目打zip():
    """⭐ 判据点**搬家**（`§19` 批 2）：旧页的展开区是 checkbox ＋ 全选/清空（**区域内不得出现 radio**）
    ＋ 每项目一份、≥2 个打成 zip。新壳对应：`procExpPjs` **数组 ＋ 多选面板**
    （`selected:()=>procExpPjs`、**不带 `single:true`**、`allAct`/`noneAct` 给全选/清空）＋ 面板写明口径。"""
    panel = SHELL[SHELL.index("const procExpPjPanel="):]
    panel = panel[:panel.index("\n")]
    assert "selected:()=>procExpPjs" in panel and "single:true" not in panel, \
        "导出项目面板不是多选（或混进了单选 `single:true`）"
    assert "allAct:'procExpPjAll'" in panel and "noneAct:'procExpPjNone'" in panel, \
        "多选面板缺「全选 / 清空」"
    assert "每项目一份" in SHELL and "zip" in SHELL, "面板没写清「每项目一份 / ≥2 打成 zip」"


@acc("ACC-RPT-EXP-001", "001-01")
def test_一个项目都没选时导出按钮禁用():
    """旧页：清空后导出按钮 **disabled** —— ⛔ 不静默退回"当前项目"（那是一次用户没要求的导出）。"""
    assert "${procExpPjs.length?'':'disabled'}" in SHELL, "0 个项目时导出按钮没有禁用"


@acc("ACC-RPT-EXP-001", "001-04")
def test_导出取数跟随当前所显示的表():
    """旧页：切表后「导出取数」提示逐一对上（`data-exp-tab`）。新壳对应：**导出 URL 带上当前表签**
    ⇒ 取数跟着用户眼前那张表走（⛔ 不许固定成表②）。"""
    assert "'&tab='+encodeURIComponent(procTab)" in SHELL, \
        "导出请求没带当前表签 ⇒ 会导出与眼前不一致的表"


@acc("ACC-RPT-EXP-001", "001-02")
def test_导出展开区默认选中本页当前项目():
    """⭐ 判据点**搬家**（`§19` 批 2）：原先钉在旧页的导出展开区（未动过 ⇒ 勾选 = 本页当前项目；
    且**不改动**页面那个单选项目）。新壳对应一句：**展开区没选过东西时，默认取当前项目** ⇒
    ⛔ 不许默认取"第一个候选"或空（那会导出用户没选的项目）。"""
    assert ("if(procExpOn&&!procExpPjs.length&&procPj) procExpPjs=[procPj];" in SHELL), \
        "导出展开区没默认选中本页当前项目"


@acc()
def test_导出面板一键开合_开合判据只认面板自身状态():
    """⭐ 2026-09-28（用户报障原话「弹出的选择项目控件**点没了的话，还要再点两下按钮才能出来**」）：
    开关按钮的判据**只能是面板自己的开合态**（`pjIsOpen`），⛔ 不能用另一个镜像变量 ——
    镜像**不会**跟着「点浮层外面收起」一起合 ⇒ 状态走散后，下一次点按钮就变成
    "**关一个已经关了的**" ⇒ 要点**两下**才出来。这正是那条报障的根。

    ⚠️ **能证伪**：把 `const open=!pjIsOpen('procExpPj');` 换回 `procExpOn=!procExpOn;` ⇒ 本件必红。
    """
    seg = _act_body("procExpToggle")
    assert "const open=!pjIsOpen('procExpPj');" in seg, \
        "开 / 关判据不是面板自身的开合态 ⇒ 点浮层外面收起后会与镜像变量走散（要点两下才出来）"
    assert "procExpOn=open;" in seg, "镜像变量没跟这一次开 / 关同步写（展开区会与面板不同步）"


@acc()
def test_过程资料页标出机械历史段的截止月():
    """⭐ 2026-09-28（用户口径：「想知道的话，在过程资料页给历史段加一个标记就好了」）：
    机械 6 列按核算月分**两段** —— **历史段**（≤ 截止核算月）= 过程资料导入的快照值、界面不许手改；
    **手录段**（截止月之后）= 「录机械费」处手填（旁路表）。页面要**说清分界在哪个月**，
    否则用户看不出"这一个月是快照值还是手填值"、也看不出手录会不会被拒（守则 §5.5）。

    ⚠️ 能证伪：把 `mechCutLabel(procPj)` 那半句摘掉 ⇒ 本件必红。
    ⚠️ 判段的**唯一出口** = 后端给的 `MECH_SECTIONS`（`domain.section_of`）——
       ⛔ 壳里不许拿截止月自己比大小（那是第二份口径）。
    """
    assert "const mechCutLabel=wh=>" in SHELL, "「历史段截止月」没有唯一出口"
    assert "filter(k=>s[k]==='history')" in SHELL, \
        "截止月不是从后端给的段（`MECH_SECTIONS`）里取的 —— 壳里自判段就是第二份口径"
    assert "mechCutLabel(procPj)" in SHELL, "过程资料页没有按**当前所选项目**取该项目的分界月"
    assert "历史段截至" in SHELL and "此后为手录段" in SHELL, \
        "过程资料页没把分界月说给用户看（用户看不出这月是快照值还是手填值）"
    assert "暂无导入快照" in SHELL, \
        "没有快照的项目＝机械 6 列全部可手录，也该说清（⛔ 不能显示成空白让人猜）"


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

    ⭐ 2026-09-23（`TAIL-76` ②）：补**结构护栏** —— 原先只断言"壳里没有 `id="in_`"（全壳字面扫），
       钉不住"**机械区块里**恰好只有那 6 个输入面"。原靶 `mech_ui.block_html` 随旧页 2026-09-18 删除
       ⇒ 那半条 claim 一度**改坏了也没人知道**。现在按**弹窗体内**数：除「核算月」那一个输入框外，
       ⛔ 不许再有任何输入面。
    """
    # ⭐ 2026-09-28（用户口径：改成"按核算月一屏手填"）：键仍是 `mech_<列序号>`，⛔ claim 一字未变。
    assert "'mech_'+" in SHELL, "机械值没按 `mech_` 键组装"
    assert 'data-act="mechCell"' in SHELL, "机械列没有可手填的格子"
    for bad in ("values['in_", "values['out_", 'id="in_', 'id="out_'):
        assert bad not in SHELL, f"壳里出现了材料列的输入面：{bad}（材料列只读是铁律）"

    body = _act_body("mechOpen")
    # ⭐ 结构护栏（claim 不变：**机械区块里只有机械 6 列的输入面**）——
    #   2026-09-28 改成"表头一行 ＋ 每月一行"后：`MECH_LABELS` 派生 **2 处**（表头 / 数据行），
    #   而输入面的**模板只有 1 处**（每行复用同一段）⇒ ⛔ 别在这里长出材料列的格子。
    assert body.count("MECH_LABELS.map(") == 2, "机械列没由 `MECH_LABELS` 派生（表头 ＋ 数据行各一处）"
    assert body.count("<input") == 2, \
        f"机械区块的输入面不是「核算期 1 ＋ 6 列 1 处模板」（实测 {body.count('<input')}）—— 多出来的就是材料列的输入面"
    assert 'data-i="${j}"' in body, "机械列格子没按列序号派生（`mech_` 键就对不上了）"
    m = re.search(r"const MECH_LABELS = \[(.*?)\];", SHELL, re.S)
    assert m and len(re.findall(r"'[^']+'", m.group(1))) == 6, \
        "`MECH_LABELS` 兜底不是 6 列（§5.2.5 ③「机械 6 列」）"


@acc()
def test_录机械费第二次打开要回填该月现值():
    """⭐ `TAIL-76` ①：**录第二次**要能看见**现值**（原靶 `mech_ui._value_of` 随旧页 2026-09-18 删除）。

    ⚠️ 2026-09-28：形态改成"**按核算月一屏手填**"（用户口径）—— 这条**更要紧**（整屏都是现值才敢改一格），
       ⛔ 别因为改了形态就把回填丢了：丢了 ⇒ 打开是**空盒**，而保存是"空 ⇒ 0"（§4.4 旁路载体的口径）
       ⇒ 用户只改其中一格、点保存，**其余列会被清成 0** —— 而且界面上全程看不出这件事。

    现法：每一行按自己的 `ym` 从 `MACH6`（= 后端 `mech`）取那一月的 6 列 ⇒ 填进该行格子；
       `null` / `0` 显示**空**（⛔ 不显示 0 —— `001-08`「不臆造 0」）。
    """
    body = _act_body("mechOpen")
    assert "mach6Arr(wh,ym)" in body, "弹窗没有从 `MACH6` 取**该月现值**（第二次打开会是空盒）"
    assert "const a=mach6Arr(wh,ym)" in body, "取现值的写法变了"
    assert "Number(a[j])!==0" in body, "`0` 没按空显示（会把没填过的月份渲染成 0）"
    assert 'value="${esc(v)}"' in body, "现值没写进格子的 `value` ⇒ 界面上看不见现值"


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
    i = SHELL.find("BIND.m06 = function")
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
