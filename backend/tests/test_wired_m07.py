"""`MOD-07` 收发结存与活动大表 —— **前端壳接线的离线断言**。

真机验证在 `tools/_shell_smoke.py`（第 ⑩ 段：连服务 + 连库），本文件只做**静态接线断言**。

⚠️ 这里钉的是**接线本身**，不是"页面好不好看"：
1. **演示数据必须已清** —— 留着就永远渲染演示值（`ui_parity` 的 `U2b` 也查 `m07→WHM`）。
2. **适配层必须把金额转成数字** —— 后端金额出**字符串**（`numeric(18,2)` 精度保护），
   不过 `N0()` 的话壳里的求和会变成**字符串拼接**（`'100.00'+'1.00'`）—— **合计那栏安静地错掉**。
   ⚠️ 更隐蔽的一处：大表**手填列**的合计走 `typeof v === 'number' ? v : 0`
   ⇒ 手填值若是字符串，**那一列合计恒 0**（2026-09-18 接线时核实）。
3. **判据不得在前端复写**（`D18`）—— 防出**第二份口径**（金额非负 / 开工时间格式 / 选题校验）。
4. **不许本地赋值冒充落库**（假成功）。
5. ⛔ **不许给 `BIGSET` 兜底「空了就填全部候选」** —— 后端选题有**标记行**区分
   「从未选题」（⇒ 后端已给全部候选）与「选了空」（⇒ 0 个项目）；前端兜底会把「清空」悄悄改回去。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
SHELL = (ROOT / "backend" / "app" / "web" / "index.html").read_text(encoding="utf-8")
ROUTER = (ROOT / "backend" / "app" / "mod07_setl" / "router.py").read_text(encoding="utf-8")
API = (ROOT / "backend" / "app" / "mod07_setl" / "api.py").read_text(encoding="utf-8")


def _body(name: str) -> str:
    """取壳里 `function <name>(…){…}` 的函数体（**花括号配平**，不靠"下一个函数"）。"""
    i = SHELL.find(f"function {name}(")
    assert i >= 0, f"壳里找不到 `function {name}(`"
    j = SHELL.find("{", i)
    depth, k = 0, j
    while k < len(SHELL):
        if SHELL[k] == "{":
            depth += 1
        elif SHELL[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    body = SHELL[i:k + 1]
    assert len(body) < 6000, f"`{name}` 取到 {len(body)} 字符 —— 配平可能跑偏"
    return body


def _slice(name: str, limit: int = 12000) -> str:
    """取壳里 `V.<name>=()=>{…}` 的切片（花括号配平）。"""
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


# ============== `ACC-SETL-001` / `ACC-SETL-EXT-001` 的**形态**半边（`§19` 批 2 搬家）
#
# 原先钉在**旧服务端页**（`render_setl_page` / `render_extract_page`）渲染出的 HTML 上；
# 旧页删除（授权 `D18`）⇒ 形态**改指新壳**（⛔ 判据不删）。


@acc("ACC-SETL-001", "001-04")
def test_壳里重置回默认月且不串页():
    """「重置」= 核算年月回**默认月**（上月）；且本页**不得**带上别模块的筛选状态（跨页污染防线）。"""
    assert "whReset:()=>{ fWhYm=bjMonth(-1);" in SHELL, "重置没回到默认月"
    s = _slice("m07")
    assert 'name="pj"' not in s and "invWh" not in s, "本页串进了别模块的筛选状态"


@acc("ACC-SETL-EXT-001", "001-05")
def test_壳里提取页重置回在建与上月():
    """「重置」= 项目状态回**默认**（在建）＋ 金额月份回**默认**（上月）。"""
    assert "fExtReset:()=>{ fExt.status='在建'; fExt.ym=bjMonth(-1);" in SHELL, "提取页重置没回默认"


@acc("ACC-SETL-EXT-001", "001-03")
def test_壳里提取表两类按序且合计行紧贴():
    """两类按 `extBlock('焊材')` → `extBlock('气体')` 渲染；**每块的合计行在该块之内**（紧贴本类数据行）；
    该表**刻意不可排**（⛔ 不带 `data-sort`）。"""
    s = _slice("m07")
    assert "${extBlock('焊材')}${extBlock('气体')}" in s, "两类的渲染顺序变了"
    # ⚠️ 合计行在 **`extBlock` 的体内**（不在 `V.m07` 切片里 ⇒ 要取函数体）
    b = _body("extBlock")
    assert "sumRowOf(EXT_THEAD, list, {3:" in b and "lead:kind+'合计'" in b, \
        "块的合计行不在本块内 / 不是由共用出口出的"
    assert '<table class="dt cond" data-sort-key="m07:kinds">' in s, \
        "提取表带了 `data-sort`（它必须**刻意不可排**）"


@acc("ACC-SETL-EXT-001", "001-04")
def test_壳里按项目状态过滤且空态跨列派生():
    """① 可见行按**项目状态**过滤（`extVisible`）；③ 该状态下没有数据 ⇒ 空态提示行，
    `colspan` **由表头派生**，并点名是哪一类。"""
    assert "const extVisible = kind => extWhs(kind).filter(w => fExt.status === '全部'" in SHELL, \
        "可见行不再按项目状态过滤"
    assert 'colspan="${thCount(EXT_THEAD)}"' in SHELL, "空态行的跨列数不再由表头派生"
    assert "当前筛选条件下没有" in SHELL and "数据 —— 换个「项目状态」或月份" in SHELL, "空态提示丢了"


@acc("ACC-SETL-EXT-001", "001-06")
def test_壳里导出走真下载且带当前筛选():
    """导出矩阵走 `saveExt` → `/api/m07/extract/export?status=…&period=…`（带上**当前筛选**）。"""
    # ⚠️ 「保存到本地」按钮在 **`ACT`**（不在 `V.m07` 切片里）⇒ 查全文
    assert 'data-act="saveExt"' in SHELL, "导出弹窗没有真保存按钮"
    assert "'/api/m07/extract/export?status='+encodeURIComponent(fExt.status)" in SHELL, \
        "导出端点没带上当前筛选"


# ---- `ACC-RPT-BIG-001`（活动大表）的形态半边


# ============== `ACC-RPT-BIG-001`（活动大表）的**形态**半边（`§19` 批 2 搬家）
#
# 原先钉在**旧服务端页**（`big_view.render_big_page` / `render_export_page` / `_cell_html` / `_thead`）
# 渲染出的 HTML 上；旧页删除（授权 `D18`）⇒ 形态改指新壳（⛔ 判据不删）。

# ⚠️ `BIG_THEAD` 在壳里是**多段反引号拼接**（`const BIG_THEAD=`…`` ` `` ＋ `` +`…` ``），
#    所以取到第一处 `` `; `` 为止（非贪婪）；取出来的是**两行表头的全部标记**。
_BIG_THEAD_RE = re.compile(r"const BIG_THEAD=(.*?)`;", re.S)


def _big_thead() -> str:
    m = _BIG_THEAD_RE.search(SHELL)
    assert m, "壳里找不到 `const BIG_THEAD=`"
    return m.group(1)


@acc("ACC-RPT-BIG-001", "001-02")
def test_壳里表头不含已裁掉的列():
    """拿**域内核那把尺子**（`boundary_violations`）扫壳的表头 ⇒ 不得含已裁掉的列（如「材料费」数据项）。"""
    from app.mod07_setl import big_domain as B

    assert B.boundary_violations(html=_big_thead()) == [], "壳表头里出现了不得有的列"


@acc("ACC-RPT-BIG-001", "001-03")
def test_壳里输入框只出现在手填列():
    """手填列**恰好 6 个**：表体只经一个 `cell()` 生成输入框（`cell(0)…cell(5)`），⛔ 没有第 7 个。"""
    s = _slice("m07")
    assert s.count('data-act="bigEdit"') == 1, "输入框渲染点不止一处（应只有一个 `cell()` 生成器）"
    for i in range(6):
        assert f"${{cell({i})}}" in s, f"手填列 `cell({i})` 没了"
    assert "${cell(6)}" not in s, "出现了第 7 个手填列（手填列应恰好 6 个）"


@acc("ACC-RPT-BIG-001", "001-04")
def test_壳里派生列是纯文本格():
    """派生列（合计 / 使用率 / 产值完成率）在壳里是**纯文本格**（走 `M(...)` / `pct(...)`），⛔ 无输入框。"""
    s = _slice("m07")
    for expr in ("M(r.totC)", "pct(r.use)", "pct(r.done)"):
        assert expr in s, f"派生列的渲染点变了：{expr}"


@acc("ACC-RPT-BIG-001", "001-05")
def test_壳里主材累计走金额出口且取数口未接入():
    """⚠️ 集采台账取数口**未接入**（M5 未落地，`MAIN_MATERIAL_PORT is None`）⇒ 主材累计在本表是**派生文本格**
    （`M(r.matC)`，⛔ 不是手填输入框）；`0.00` 与「取数口没接」两件事不许混（⛔ 不写 0 冒充"确实没有"）。"""
    from app.mod07_setl import big_service as BS

    assert BS.MAIN_MATERIAL_PORT is None, "取数口已接入 ⇒ 本断言要跟着改（显「—」的前提就是取数口为空）"
    s = _slice("m07")
    assert "M(r.matC)" in s, "主材累计的渲染点变了（它必须是派生文本格，不能变成手填）"


@acc("ACC-RPT-BIG-001", "001-09")
def test_壳里零与未录入在输入框上分得开():
    """零是**合法录入值**（不得被误判成未录入）：输入框的值走 `bigDisp(c.v,i)`，而它的空值判定是
    **严格 `==null`** —— ⛔ 不用 `||`/`?` 之类的真值判断（那会把 `0` 吞掉、显示成未录入）。"""
    assert "const bigDisp=(v,i)=>v==null?'':String(v);" in SHELL, \
        "`bigDisp` 对空值的判定变了（用真值判断会把合法的 0 吞掉）"
    s = _slice("m07")
    assert "bigDisp(c.v,i)" in s, "输入框的值没走 `bigDisp` 出口"


@acc("ACC-RPT-BIG-001", "001-12")
def test_壳里带入格可辨且带来源月():
    """带入格**仍是可编辑输入框**（`class="inp…ed"`）＋ 带**来源月**标记（`↺MM月`）。"""
    s = _slice("m07")
    assert "c.from?' ed':''" in s, "带入格没有带入态样式（不再是可辨的输入框）"
    assert "↺${c.from.slice(5)}月" in s, "带入格没有来源月标记"


@acc("ACC-RPT-BIG-001", "001-13")
def test_壳里行只由一份装配出():
    """「页面行序 = 导出页行序」在壳里的等价形态：**行只从 `bigRows(...)` 这一处装配**（表体 ＋ 合计行），
    ⛔ 没有第二份行序；导出走 `/api/m07/big/export`（复用同一个 `big_service`，另有断言）。"""
    s = _slice("m07")
    assert s.count("bigRows(") == 2, f"`bigRows(` 出现了 {s.count('bigRows(')} 次（应只用于表体与合计行）"
    assert "bigRows(bjMonth(-1)).map((r,ri)=>" in s, "表体不是由 `bigRows` 装配的"
    assert "/api/m07/big/export?period=" in SHELL, "导出没走 API（那一份才是与页面同源的）"


@acc("ACC-RPT-BIG-001", "001-15")
def test_壳里出纸走按模板导出且没有打印通道():
    """出纸 = **按模板导出 → Excel 打印**（壳的 `bigExport` → `/api/m07/big/export?period=`）；
    ⛔ 没有打印通道 / A3 入口（连标题里都不许出现）。"""
    s = _slice("m07")
    assert 'data-act="bigExport"' in s, "壳里没有「按模板导出」入口"
    assert "Excel 打印" in s, "没写明出纸方式（按模板导出后在 Excel 打印）"
    assert "A3" not in s, "壳里还留着 A3 打印通道"
    # 导航里有本页（新壳的侧栏菜单）
    assert "'m07','收发结存与活动大表'" in SHELL, "新壳侧栏里没有本页入口"
    # 路由层面：大表**没有**任何打印 / A3 入口（API 侧；旧页路由随本批删除）
    from app.main import create_app

    paths = [p for p in create_app().openapi()["paths"] if "big" in p]
    assert paths and not any(("print" in p or "a3" in p.lower()) for p in paths), paths


@acc("ACC-SETL-001", "001-01")
def test_壳里表体每仓一行且合计行由共用出口出():
    """表体 = **每仓一行**（逐行算校验）；合计行由 `sumRowOf(WH_THEAD, rows, …)` 出 —— 行数与
    四个金额列的合计都**按行派生**（⭐ 校验格另算，见 001-09）。"""
    s = _slice("m07")
    assert "sumRowOf(WH_THEAD, rows," in s, "合计行不是由共用出口按行派生的"
    assert "balOf(w)" in s, "表体没逐行渲染"


@acc("ACC-SETL-001", "001-02")
def test_壳里核算年月默认上月且可切():
    """默认 = **北京时间上月**（§9.2）；并由 `whMonth` 控件承载（切了重取数，另有断言）。"""
    assert "let fWhYm = bjMonth(-1);" in SHELL, "默认没落成上月"
    assert "tmBtn('whMonth',{scope:'wh',val:fWhYm" in SHELL, "没有核算年月控件（或没绑到本页状态）"


@acc("ACC-SETL-001", "001-05")
def test_壳里空态跨列数由表头派生():
    """空月 ⇒ 空态提示行，`colspan` **由表头列数派生**，且提示里点名是哪个年月。"""
    assert 'colspan="${thCount(WH_THEAD)}"' in SHELL, "空态行跨列数不再由表头派生"
    assert "没有收发结存数据" in SHELL, "空月没有提示"


@acc("ACC-SETL-001", "001-06")
def test_壳里抓取弹窗默认取本页年月且讲清强踢():
    """抓取弹窗默认月 = **本页当前所选核算年月**（可改）；且须讲清**会登录 i8 强踢**（`D9`）。"""
    assert "fetchWh:()=>{ fetchKind='wh'; fetchM=fWhYm;" in SHELL, "抓取弹窗没取本页当前年月"
    assert "强踢" in SHELL, "D9（会强踢在线用户）没告知"


@acc("ACC-SETL-001", "001-07")
def test_壳里文件数恒为仓数加一():
    """「分仓库工作簿 ＋ **1 个总表**」⇒ 文件数恒 = 仓数 ＋ 1（回执里两个数同源算出，⛔ 不写死）。"""
    assert "个分仓库 xlsx ＋ 1 个总表（zip）" in SHELL, "回执没按「仓数 ＋ 1」说清产出物"


@acc("ACC-SETL-001", "001-08")
def test_壳里产出物清单按仓数加总表且真导出():
    """「分仓库工作簿 ＋ 1 个总表」：产出物清单**逐项**列出（分仓库那份按仓数、总表一份），
    且导出走**真端点**（⛔ 不是死按钮）。"""
    assert "个分仓库 xlsx（每仓一个）" in SHELL, "产出物清单没按仓数列出分仓库工作簿"
    assert "收发结存表.xlsx" in SHELL, "产出物清单没列总表"
    assert "zipSfjc" in SHELL and "/api/m07/settlement/export?period=" in SHELL, "导出没走真端点"


@acc("ACC-SETL-001", "001-09")
def test_壳里对平显示与合计行校验():
    """校验列按两位小数归一判等：对平写「已对平」、不平写「差 X」；且**合计行的校验格**
    是对**合计值本身**再判一次（`tagOf(totBal)`），⛔ 不是抄某一行。"""
    assert '已对平' in SHELL and "tagOf(balOf(w))" in SHELL, "逐行的对平/差额显示出口没了"
    assert "tagOf(totBal)" in SHELL, "合计行的校验格不是对合计值本身判定的"


# ============================================================== 1 · 演示数据已清

@acc()
def test_m07演示块已删():
    """四个演示容器必须**物理删除**（留着就永远渲染演示数据 —— `ui_parity` 的 `U2b` 也查）。"""
    assert "const WHM = {" not in SHELL, "收发结存演示块 `const WHM = {` 还在"
    assert "const EXTM = {}" not in SHELL, "提取演示块 `const EXTM = {}` 还在"
    assert "const BIGVAL = {}" not in SHELL, "大表手填演示块 `const BIGVAL = {}` 还在"
    assert "const EXTRACT = EXTM[" not in SHELL, "已失效的 `EXTRACT` 别名还在（它指向演示数据）"
    assert "WHM['2026-08']" not in SHELL, "切片仍在引用演示基线 `WHM['2026-08']`"


@acc()
def test_m07数据源改为后端填充():
    assert "let WHM = {};" in SHELL, "`WHM` 没改成「空容器 + 后端填充」"
    assert "let EXTM = {};" in SHELL, "`EXTM` 没改成「空容器 + 后端填充」"
    assert "let BIGVAL = {};" in SHELL, "`BIGVAL` 没改成「空容器 + 后端填充」"
    assert "let BIGSET = [];" in SHELL, "`BIGSET` 没改成「空数组 + 后端填充」"
    body = _body("reloadM07")
    for call in ("API.m07Settlement(", "API.m07Extract(", "API.m07Big("):
        assert call in body, f"`reloadM07()` 没读 `{call.rstrip('(')}`"


@acc()
def test_未选题不得被前端兜底填满():
    """⛔ 反向：`BIGSET` 空了**不代表**「未选题」—— 后端有**标记行**区分两种情况。

    若在重拉里写「空了就填全部候选」，用户点「清空」会被**悄悄改回全部候选**（假成功、不报错）。
    """
    body = _body("reloadM07")
    assert "bigCands()" not in body, "`reloadM07()` 里给 `BIGSET` 兜底填了全部候选（会吃掉用户的「清空」）"


# ============================================================== 2 · 适配层

@acc()
def test_适配层覆盖大表手填列():
    """⭐ 手填 6 列的 key 必须与**后端**一致（`big_domain.BIG_MANUAL_KEYS`）——

    漏一个 / 顺序错 ⇒ 壳里读该格恒 `undefined`（**静默失配**），而且 `bigEdit` 会把**别的列**写到后端。
    """
    from app.mod07_setl.big_domain import BIG_MANUAL_KEYS

    m = re.search(r"const BIG_MKEYS = \[([^\]]*)\];", SHELL)
    assert m, "壳里找不到 `const BIG_MKEYS = [...]`"
    shell_keys = [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
    assert shell_keys == list(BIG_MANUAL_KEYS), (
        f"BIG_MKEYS 与后端不一致：壳 {shell_keys} vs 后端 {list(BIG_MANUAL_KEYS)}"
    )


@acc()
def test_适配层把金额转成数字():
    """⛔ **后端金额出的是字符串** ⇒ 适配层必须过 `N0()`。

    两处硬伤（都"不报错"）：
    ① 收发结存的 `begin/in/out/end` 是字符串 ⇒ 表内求和变**字符串拼接**；
    ② 大表**手填列**的合计走 `typeof v === 'number' ? v : 0` ⇒ 手填值若是字符串，**那一列合计恒 0**。
    """
    wh = SHELL[SHELL.find("const adaptWh = r =>"):][:300]
    assert "const adaptWh" in wh, "壳里找不到 `const adaptWh`"
    # ⚠️ 正则**必须带前缀边界**：不加的话 `in:\s*N0\(` 会被 `begin:` 里的子串 `in:` 喂饱
    #    （反向灵敏度实测：不加边界时，把 `in: N0(r.in)` 改回 `in: r.in` **照样绿** —— 假绿）。
    for k in ("begin", "in", "out", "end", "rows"):
        assert re.search(rf"(?:^|[\s,(]){k}:\s*N0\(", wh), f"`adaptWh` 的 `{k}` 没过 `N0()`"
    man = _body("adaptManual")
    assert "N0(v)" in man, "`adaptManual` 的金额列没过 `N0()`（手填列合计会恒 0）"
    ext = _body("adaptExtract")
    assert "N0(" in ext, "`adaptExtract` 的金额没过 `N0()`（提取金额求和会变字符串拼接）"


@acc()
def test_适配层按后端格式判断金额列():
    """⚠️ 哪几列是金额**由后端 `manual_fmts` 决定** —— ⛔ 前端不硬编码"下标 1..4 是金额"。"""
    man = _body("adaptManual")
    assert "fmts" in man and "'money'" in man, "`adaptManual` 没按后端格式判断金额列（硬编码了下标）"


# ============================================================== 3 · 写动作走后端（含反向）

@acc()
def test_大表手填走后端且不在前端复写判据():
    """⭐ 反向：**不许**再有前端判据（`badMoney` / `bigStore`）+ 本地改 `BIGVAL` 冒充落库。"""
    i = SHELL.find("bigEdit:async t=>{")
    assert i > 0, "`bigEdit` 没改成 async（异步走后端）"
    j = SHELL.find("bigPick:t=>{", i)
    body = SHELL[i:j if j > i else i + 1800]
    assert "API.m07BigCell(" in body, "`bigEdit` 没走 `/api/m07/big/cell`"
    assert "badMoney(" not in body, "`bigEdit` 还在前端复写判据（⇒ 第二份口径）"
    assert "bigStore(" not in body, "`bigEdit` 还在用前端的 `bigStore` 解析（该由后端 `parse_manual` 一把管）"
    assert "BIGVAL[" not in body, "`bigEdit` 还在本地改 `BIGVAL` 冒充落库（假成功）"
    assert "reloadM07()" in body, "`bigEdit` 成功后没「以后端为准重拉」"


@acc()
def test_选题落库走后端():
    """⭐ 反向：不许只在本地 `BIGSET.push` 冒充落库。"""
    i = SHELL.find("bigPickOk:async")
    assert i > 0, "`bigPickOk` 没改成 async"
    body = SHELL[i:i + 900]
    assert "API.m07BigSelection(" in body, "`bigPickOk` 没走 `/api/m07/big/selection`"
    assert "reloadM07()" in body, "`bigPickOk` 成功后没「以后端为准重拉」"


@acc()
def test_m07抓取分支接后端():
    assert "if(k==='wh') return whFetchBackend(m);" in SHELL, "抓取弹窗的收发结存分支没接后端"
    body = _body("whFetchBackend")
    assert "API.m07Fetch(" in body, "`whFetchBackend` 没调 `/api/m07/fetch`"
    assert "r.ok === false" in body, "抓取降级（i8 失败 ⇒ 手动导入）没处理"


@acc()
def test_导出已落地为真下载():
    """`TAIL-04` 落地后：`zipSfjc` 不再是「如实标注未落地」，而是**真的产出并下载文件**。

    ⚠️ 这条断言**换过一次方向**：
      · 接线前它钉的是「必须如实说未落地」（当时 `TAIL-04` 没做，报"已生成"就是**假成功**）；
      · `TAIL-04` 落地后，同一处必须改成「真的产出文件」——
        **钉临时状态的断言要跟着状态走**，否则它会把"已经做好的功能"判成红
        （本轮实测：它当场变红，正是提示"该改断言了"的信号，不是实现错）。
    """
    i = SHELL.find("zipSfjc:")
    assert i > 0, "壳里找不到 `zipSfjc`"
    j = SHELL.find("whReset:()", i)
    body = SHELL[i:j if j > i else i + 1600]
    assert "/api/m07/settlement/export?period=" in body, "`zipSfjc` 没打导出端点"
    assert "尚未落地" not in body, "`TAIL-04` 已落地，还在说「尚未落地」"
    assert "createObjectURL" in body and ".download" in body, "没真的触发下载"
    assert "已生成 <b>第四工程公司" not in body, "还在报「已生成 .zip」的假成功"


# ============================================================== 4 · 后端端点 + 接线自洽

# ============================================================== 5 · 「结余」录入（2026-09-18 用户裁定「甲」）

@acc("ACC-SETL-EXT-001", "001-09")
def test_结余录入走后端且不在前端复写判据():
    """⭐ 反向：`extBal` 不许在前端复写「金额非负 / 空 = 清空」判据，也不许本地改 `BAL_EX` 冒充落库。"""
    i = SHELL.find("extBal:async t=>{")
    assert i > 0, "`extBal` 没改成 async（异步走后端）"
    j = SHELL.find("\n expExt:", i)
    body = SHELL[i:j if j > i else i + 1600]
    assert "API.m07BalCell(" in body, "`extBal` 没走 `/api/m07/extract/balance`"
    assert "raw:" in body, "没把**原始输入**交给后端（前端先转数字 ⇒ 非法输入变成 NaN、看不出错）"
    assert "badMoney(" not in body and "numOf(" not in body, \
        "`extBal` 还在前端复写金额判据（⇒ 第二份口径）"
    # ⚠️ 判据只认**代码形态**（`BAL_EX[`）—— 别写成「不含『不本地改』这句话」：
    #    那段说明文字**本身**就写在函数上方，用文案判会**被自己的注释喂饱**（假绿）。
    assert "BAL_EX[" not in body, "`extBal` 还在本地改 `BAL_EX` 冒充落库（假成功）"
    assert "reloadM07()" in body, "`extBal` 成功后没「以后端为准重拉」"


@acc("ACC-SETL-EXT-001", "001-09")
def test_结余是表单类动作已登记CHG():
    """⛔ 漏登记 `CHG` ⇒ `change` 事件被静默丢弃（输入框「点了没反应」）。"""
    m = re.search(r"const CHG=\[([^\]]*)\]", SHELL)
    assert m, "壳里找不到 `CHG` 数组"
    assert "'extBal'" in m.group(1), "`extBal` 没登记进 `CHG`"


@acc("ACC-SETL-EXT-001", "001-09")
def test_结余演示容器已清成空容器():
    assert "const BAL_EX = {" not in SHELL, "结余演示块 `const BAL_EX = {` 还在"
    assert "let BAL_EX = {};" in SHELL, "`BAL_EX` 没改成「空容器 + 后端填充」"


@acc("ACC-SETL-EXT-001", "001-07")
def test_结余适配层过N0且不给未录入补值():
    """⚠️ 后端金额出**字符串**（不过 `N0()` 会显示成带引号的串）；
    ⛔ **不给未录入补 0** —— 一补，「没填」与「填了 0」就再也分不开。"""
    body = _body("adaptBalances")
    assert "N0(v)" in body, "结余没过 `N0()`"
    assert re.search(r"if \(v == null \|\| v === ''\) return;", body), \
        "空值（未录入）没被跳过 ⇒ 会给未录入补一个值（0 与「未录入」就分不开了）"


@acc("ACC-SETL-EXT-001", "001-11")
def test_reloadM07填充结余():
    """⭐ 重拉是**唯一出口**：`BAL_EX` 必须由 `reloadM07()` 从后端 `balances` 原地填。"""
    body = _body("reloadM07")
    assert "adaptBalances(ex && ex.balances)" in body, "没读 `/api/m07/extract` 的 `balances`"
    assert "Object.keys(BAL_EX).forEach(k => delete BAL_EX[k]);" in body, \
        "`BAL_EX` 没「原地清空再填」（外部持有的引用会指向旧对象）"


@acc("ACC-SETL-EXT-001", "001-09")
def test_结余列渲染成可编辑输入且合计下标跟着移():
    """「点格即改」的形态判据 ＋ ⚠️ **加列后合计行的列下标必须跟着移**（否则合计算到「结余」列上）。"""
    body = _body("extBlock")
    assert 'data-act="extBal"' in body, "「结余」列没渲染成可编辑输入"
    assert "extBalOf(" in body, "结余格没走取数出口"
    assert "v == null ? ''" in body, "未录入没给空值（⛔ 不写 0）"
    assert "{3:rs=>" in body and "4:rs=>" in body, "合计行的列下标没跟着移（列 +1 之后仍按旧下标）"
    assert "{2:rs=>" not in body, "合计行还在按旧下标取列"


@acc("ACC-SETL-EXT-001", "001-09")
def test_表头含结余列且列序照模板():
    m = re.search(r"const EXT_THEAD=`([^`]*)`", SHELL)
    assert m, "找不到 `EXT_THEAD`"
    head = m.group(1)
    assert head.count("<th") == 5, f"提取表表头应为 5 列（加「结余」），实得 {head.count('<th')}"
    assert head.index("仓库") < head.index("结余") < head.index("总金额"), \
        f"「结余」列的位置不对（应照成品模板：仓库之后、金额之前）：{head}"


@acc("ACC-SETL-EXT-001", "001-09")
def test_后端结余端点读写都在():
    assert '@router.post("/api/m07/extract/balance")' in API, "后端缺写端点"
    assert "S.save_balance_cell(" in API, "写端点没走服务层出口（判定会散到路由里）"
    assert "load_balances(s)" in API, "读端点没带上结余（壳里永远空）"


@acc()
def test_后端关键端点都在():
    for path, verb in (
        ("/api/m07/settlement", "get"), ("/api/m07/extract", "get"), ("/api/m07/big", "get"),
        ("/api/m07/big/cell", "post"), ("/api/m07/big/selection", "post"),
        ("/api/m07/extract/balance", "post"),
        ("/api/m07/fetch", "post"),
    ):
        assert f'@router.{verb}("{path}")' in API, f"后端缺端点 {verb.upper()} {path}"
    assert "router.include_router(api_router)" in ROUTER, "`mod07_setl/router.py` 没汇总 API 路由"


@acc()
def test_抓取端点必须显式确认():
    """⛔ 防"直接 POST 打进来"的静默抓取（**会顶号**）。"""
    assert "confirmed=req.confirm" in API, "抓取端点没把 `confirm` 交给 `run_fetch`（D9 二次确认形同虚设）"


@acc()
def test_大表手填校验走服务层出口():
    """⭐ 金额非负 / 开工时间格式的判定**唯一出口 = `big_service.save_manual_cell`**（不在路由里另写）。"""
    assert "BS.save_manual_cell(" in API, "手填端点没走 `big_service.save_manual_cell`"
    assert "month=req.month, warehouse=req.warehouse" in API, "手填端点的参数形态不对"


@acc()
def test_boot含m07且逐路容错():
    i = SHELL.find("async function boot() {")
    body = SHELL[i:SHELL.find("function bootErrorBanner()", i)]
    assert "soft('收发结存与大表'" in body, "`boot()` 里「收发结存与大表」没走 `soft()`"
    # ⚠️ 顺序有依赖：大表的机械 / 焊材·气体列取 `reloadMech` / `reloadInv`。
    # ⚠️ 必须用**完整调用语句**比较位置 —— 用 `body.index("reloadMech")` 会被**注释里**那句
    #    「顺序有依赖：`reloadMech`、`reloadInv` 都在 `reloadM05` 之前」喂饱
    #    （反向灵敏度实测：那样写时，把 `reloadM07` 挪到 `reloadMech` 之前**照样绿** —— 假绿）。
    # ⭐ 2026-09-19（性能 `P2`）：`boot()` 改成**两组并行** ⇒ 形态从「一路一等」搬成「组内并发」。
    #    判据**一字未变**（`reloadM07` 必须等 `reloadMech` / `reloadInv`），只是改成按**组**证：
    #    ① 两条调用语句还都在；② 文本次序不变；③ ⭐ `reloadM07` 必须落在**第二组**里
    #    （放进第一组 = 与 mech/inv 并行 ⇒ 大表机械列取空，正是这条要挡的）。
    i_mech = body.find("soft('机械 6 列', reloadMech)")
    i_m07 = body.find("soft('收发结存与大表', reloadM07)")
    assert i_mech >= 0, "`boot()` 里没有 `reloadMech` 那一路"
    assert i_m07 >= 0, "`boot()` 里没有 `reloadM07` 那一路"
    assert i_mech < i_m07, "`reloadM07` 排在 `reloadMech` 之前（大表的机械列会取到空值）"
    i_g2 = body.find("await Promise.all(", body.find("await Promise.all(") + 1)
    assert i_g2 > 0, "`boot()` 不是**两组** `await Promise.all([...])`（第二组没了 ⇒ 依赖屏障也丢了）"
    assert i_g2 < i_m07, "`reloadM07` 没放进第二组 ⇒ 与 `reloadMech`/`reloadInv` 并行（大表机械列会取空）"
    assert i_mech < i_g2, "`reloadMech` 不在第一组（它不该等 m07）"


@acc()
def test_WIRED含m07():
    m = re.search(r"const WIRED=new Set\(\[([^\]]*)\]\);", SHELL)
    assert m and "'m07'" in m.group(1), "`WIRED` 里没有 `m07`（侧栏会仍标「原型态」）"


@acc()
def test_月份切换会重新取数():
    """⚠️ `WHM[月]` 现在来自后端 ⇒ 切月只 `render()` 会看到**空表**（且不报错）。"""
    assert "if(sc==='wh'){ fWhYm=v; mp.open=null; reloadM07();" in SHELL, (
        "切换核算年月后没有重新取数（只 render ⇒ 空表）"
    )


@acc()
def test_视图切片未被改动():
    """⭐ 反向：`V.m07` 里**不得**出现任何 `API.` 调用 —— 原型的渲染逻辑必须一行不改（`D18`）。

    ⚠️ 已知并**已登记**的例外只有 1 行（「已验收基线」文案引用了演示块 `WHM['2026-08']`，
       演示块删掉后不改会 `TypeError` 整页崩）—— 见 `tools/ui_parity_expected.txt` 的 `m07` 行。
    """
    body = _slice("m07")
    assert "API." not in body, "`V.m07` 里出现了 API 调用 ⇒ 原型渲染逻辑被改（该走适配层）"
    assert "WHM['2026-08']" not in body, "`V.m07` 仍引用演示基线（演示块已删 ⇒ 会崩）"


@acc()
def test_金额格式化认null():
    """「主材累计」取数口未接入 ⇒ 后端给 `null` ⇒ 页面显「—」。

    ⚠️ `M()` 原本 `Number(null) || 0` ⇒ 会显示「0.00」= **冒充"确实没有"**（`TAIL-25` 明确禁止）。
       ⭐ 对**数字入参**行为必须**完全不变**（这条是反向灵敏度要盯的）。
    """
    i = SHELL.find("const M=n=>{")
    assert i > 0, "壳里找不到 `const M=n=>{`"
    line = SHELL[i:SHELL.find("\n", i)]
    assert "n==null" in line and "'—'" in line, "`M()` 没处理 `null`（不可得会显示 0.00）"
    assert "Number(n)||0" in line, "`M()` 的数字分支被改动了（数字入参行为必须不变）"


@acc()
def test_主材累计不可得时不写0():
    body = SHELL[SHELL.find("const bigMatCum = wh =>"):][:400]
    assert "MAT_OK ?" in body and ": null" in body, "`bigMatCum` 取数口未接入时没给 `null`（会写 0）"


# --------------------------------------------------------------- 活动大表导出（`TAIL-04` 片 4b）


@acc("ACC-RPT-BIG-001", "001-19")
def test_活动大表导出走真下载而不是假成功():
    """⭐ `TAIL-04` **片 4b**：大表成品由后端模板填充生成 ⇒ 壳侧必须是**真下载**。

    ⚠️ 原型那个按钮是 `data-act="exp"`（诚实占位：**没有文件产生**）—— 接线后必须换成大表自己的动作。
    """
    assert "bigExport:async ()=>{" in SHELL, "缺真下载动作 `bigExport`"
    assert "/api/m07/big/export?period=" in SHELL, "没走活动大表导出端点"
    assert "encodeURIComponent(bjMonth(-1))" in SHELL, \
        "月份没原样带给后端（§9.2 材料报表类默认 = 上月；⛔ 前端不另算）"
    assert "x-export-filename" in SHELL, "文件名没从 `X-Export-Filename` 带出（命名规则的主人在后端）"
    # ⛔ 旧的**假成功**按钮必须消失（大表卡头那一个）
    assert 'data-act="exp" data-t="经济活动分析大表（按模板）"' not in SHELL, "大表卡头还留着假成功的 `exp`"
    assert 'data-act="bigExport"' in SHELL, "大表卡头的按钮没接到 `bigExport`"


@acc("ACC-RPT-BIG-001", "001-19")
def test_活动大表导出失败必须给人原因不静默():
    """后端失败回 **JSON 200 ＋ `ok:false` ＋ 中文原因**（一行都没有 / 模板坏 / **显示区对账不过**）
    ⇒ 壳必须**弹原因**，⛔ 不能静默、也不能当文件下载。"""
    i = SHELL.index("bigExport:async ()=>{")
    body = SHELL[i:SHELL.index("\n /* —— MOD-12 —— */", i)]     # 终点锚用**下一段注释头**（纯 ASCII）
    assert 400 < len(body) < 2200, f"取体越界（{len(body)} 字符）—— 锚点可能切歪了"
    assert "ct.includes('application/json')" in body, "没按 content-type 分流"
    assert "d.message||'后端没给原因'" in body, "失败时没把后端的中文原因给用户"
    assert "if(!r.ok) return toast(`<b>导出没能完成</b>：HTTP ${r.status}`" in body, \
        "非 2xx 没显式报错（会静默产出空文件）"
