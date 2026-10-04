"""`MOD-07` 收发结存与活动大表 —— **前端壳接线的离线断言**。

真机验证在 `tools/probe/_shell_smoke.py`（第 ⑩ 段：连服务 + 连库），本文件只做**静态接线断言**。

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

from tests.m07_shell_helpers import API, ROUTER, SHELL  # noqa: F401

# ⚠️ 2026-09-19（`P3` 主体）：`boot()` 不再逐路拉 ⇒ 下面那条判据改在**取数表**上证（判据不变）。
from tests.shell_load_helpers import DEP_BEFORE, loaders, page_load  # noqa: F401
# ⭐ 2026-10-03（`TAIL-219` 批 2／2b）：取片改走壳的语义口径（⛔ 别在本件自造剪刀）
from tests.shell_src import const_items, func_body, page_slice, tbl_kernel, with_kernel  # ⭐ `TAIL-67`：判据要连通用件一起看（`tbl_kernel`：`TAIL-64`）

# ============== `ACC-SETL-001` / `ACC-SETL-EXT-001` 的**形态**半边（`§19` 批 2 搬家）
#
# 原先钉在**旧服务端页**（`render_setl_page` / `render_extract_page`）渲染出的 HTML 上；
# 旧页删除（授权 `D18`）⇒ 形态**改指新壳**（⛔ 判据不删）。


@acc("ACC-SETL-001", "001-04")
def test_壳里重置回默认月且不串页():
    """「重置」= 核算年月回**默认月**（上月）；且本页**不得**带上别模块的筛选状态（跨页污染防线）。"""
    assert "whReset:()=>{ fWhYm=bjMonth(-1);" in SHELL, "重置没回到默认月"
    s = page_slice("m07")
    assert 'name="pj"' not in s and "invWh" not in s, "本页串进了别模块的筛选状态"


@acc("ACC-SETL-EXT-001", "001-05")
def test_壳里提取页重置回在建与上月():
    """「重置」= 项目状态回**默认**（在建）＋ 金额月份回**默认**（上月）。"""
    assert "fExtReset:()=>{ fExt.status='在建'; fExt.ym=bjMonth(-1);" in SHELL, "提取页重置没回默认"


@acc("ACC-SETL-EXT-001", "001-03")
def test_壳里提取表两类按序且合计行紧贴():
    """两类按 `extBlock('焊材')` → `extBlock('气体')` 渲染；**每块的合计行在该块之内**（紧贴本类数据行）；
    该表**刻意不可排**（⛔ 不带 `data-sort`）。"""
    s = page_slice("m07")
    # ⭐ 2026-09-29（`TAIL-64` P2③）：判据改成**与结构无关**的「**顺序**」钉法 —— ⛔ 别退回钉整串
    #   `${extBlock('焊材')}${extBlock('气体')}`：表外壳抽进 `TBL` 之后两个块进了 `rows` 数组，写法一变就假红。
    i_solder, i_gas = s.find("extBlock('焊材')"), s.find("extBlock('气体')")
    assert 0 <= i_solder < i_gas, "两类的渲染顺序变了（焊材必须排在气体前面）"
    # ⚠️ 合计行在 **`extBlock` 的体内**（不在 `V.m07` 切片里 ⇒ 要取函数体）
    b = func_body("extBlock")
    assert "sumRowOf(EXT_THEAD, list, {3:" in b and "lead:kind+'合计'" in b, \
        "块的合计行不在本块内 / 不是由共用出口出的"
    # ⭐ 2026-09-29（`TAIL-64` P2③）：判据从「钉字面」改成「钉意图」——
    #   原写法钉整串 `<table class="dt cond" data-sort-key="m07:kinds">`；表外壳抽进统一件 `TBL` 之后**当场假红**。
    #   ⛔ 别退回钉字面（那等于宣布"以后不许抽通用件"）。现在断三件事：
    #   ① 切片**委托** `TBL` 并交出表的身份（`key:'m07:kinds'`）；② **显式** `sort:false`（刻意不可排）；
    #   ③ `TBL` 内核里「不可排」那条分支**真的只出 `data-sort-key`**、不出 `data-sort`。
    #   ⚠️ 渲染形态那半由**原型侧真机**守：`demo/_smoke.js` 的分组表那条（表开标签不许含 `data-sort`）。
    #   自证 = `tools/mut/_mut_tbl.py` 的 M5（去掉委托）／M7（`sort:false` 改回 `true`）都必须红。
    assert "TBL({cls:'cond',key:'m07:kinds',sort:false," in s, \
        "提取表没走统一出口 `TBL`，或没显式声明「刻意不可排」（`sort:false`）"
    kern = tbl_kernel()
    assert "' data-sort data-sort-key=\"'" in kern and "' data-sort-key=\"'" in kern, \
        "`TBL` 内核里「可排 / 不可排」两条分支不齐 ⇒ `sort:false` 那条保证（⛔ 不出 `data-sort`）没了"


@acc("ACC-SETL-EXT-001", "001-04")
def test_壳里按项目状态过滤且空态跨列派生():
    """① 可见行按**项目状态**过滤（`extVisible`）；③ 该状态下没有数据 ⇒ 空态提示行，
    `colspan` **由表头派生**，并点名是哪一类。"""
    assert "const extVisible = kind => extWhs(kind).filter(w => fExt.status === '全部'" in SHELL, \
        "可见行不再按项目状态过滤"
    assert "EMPTYROW(thCount(EXT_THEAD)" in SHELL, "空态行的跨列数不再由表头派生"
    assert "当前筛选条件下没有" in SHELL and "换个「项目状态」或月份" in SHELL, "空态提示丢了"


@acc("ACC-SETL-EXT-001", "001-06")
def test_壳里导出走真下载且带当前筛选():
    """导出矩阵走 `saveExt` → `/api/m07/extract/export?status=…&period=…`（带上**当前筛选**）。"""
    # ⚠️ 「保存到本地」按钮在 **`ACT`**（不在 `V.m07` 切片里）⇒ 查全文
    assert 'data-act="saveExt"' in SHELL, "导出弹窗没有真保存按钮"
    assert "'/api/m07/extract/export?status='+encodeURIComponent(fExt.status)" in SHELL, \
        "导出端点没带上当前筛选"


@acc("ACC-SETL-001", "001-01")
def test_壳里表体每仓一行且合计行由共用出口出():
    """表体 = **每仓一行**（逐行算校验）；合计行由 `sumRowOf(WH_THEAD, rows, …)` 出 —— 行数与
    四个金额列的合计都**按行派生**（⭐ 校验格另算，见 001-09）。"""
    s = page_slice("m07")
    assert "sumRowOf(WH_THEAD, rows," in s, "合计行不是由共用出口按行派生的"
    assert "balOf(w)" in s, "表体没逐行渲染"
    # ⭐ 2026-09-29（`TAIL-64` P2③）：**表外壳**也走统一出口 `TBL`（⛔ 别退回裸 `<table class="dt" …>`）。
    #   自证 = `tools/mut/_mut_tbl.py` 的 M6 去掉这处委托 ⇒ 必须红。
    assert "TBL({head:WH_THEAD,key:'m07:warehouses'," in s, \
        "收发结存表没走统一出口 `TBL`（`TAIL-64` P2③）"


@acc("ACC-SETL-001", "001-02")
def test_壳里核算年月默认上月且可切():
    """默认 = **北京时间上月**（§9.2）；并由 `whMonth` 控件承载（切了重取数，另有断言）。"""
    assert "let fWhYm = bjMonth(-1);" in SHELL, "默认没落成上月"
    assert "tmBtn('whMonth',{scope:'wh',val:fWhYm" in SHELL, "没有核算年月控件（或没绑到本页状态）"


@acc("ACC-SETL-001", "001-05")
def test_壳里空态跨列数由表头派生():
    """空月 ⇒ 空态提示行，`colspan` **由表头列数派生**，且提示里点名是哪个年月。"""
    assert "EMPTYROW(thCount(WH_THEAD)" in SHELL, "空态行跨列数不再由表头派生"
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
    body = func_body("reloadM07")
    for call in ("API.m07Settlement(", "API.m07Extract(", "API.m07Big("):
        assert call in body, f"`reloadM07()` 没读 `{call.rstrip('(')}`"


@acc()
def test_未选题不得被前端兜底填满():
    """⛔ 反向：`BIGSET` 空了**不代表**「未选题」—— 后端有**标记行**区分两种情况。

    若在重拉里写「空了就填全部候选」，用户点「清空」会被**悄悄改回全部候选**（假成功、不报错）。
    """
    body = func_body("reloadM07")
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
    man = func_body("adaptManual")
    assert "N0(v)" in man, "`adaptManual` 的金额列没过 `N0()`（手填列合计会恒 0）"
    ext = func_body("adaptExtract")
    assert "N0(" in ext, "`adaptExtract` 的金额没过 `N0()`（提取金额求和会变字符串拼接）"


@acc()
def test_适配层按后端格式判断金额列():
    """⚠️ 哪几列是金额**由后端 `manual_fmts` 决定** —— ⛔ 前端不硬编码"下标 1..4 是金额"。"""
    man = func_body("adaptManual")
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
    body = func_body("whFetchBackend")
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
    _a = with_kernel(body)         # ⭐ `TAIL-67`：下载代码已抽到 `dlExport` 通用件
    assert "dlExport" in body and "createObjectURL" in _a and ".download" in _a, "没真的触发下载"
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
def test_结余是表单类动作由change委托承接():
    """⛔ 判词（不变）：**「结余」这个表单类动作必须真的能被 `change` 触发**（否则输入框「点了没反应」）。

    ⭐ `#2`（2026-09-26）**换落点**：原先钉的是「`extBal` 必须登记进 `CHG`」——
      名单已拆 ⇒ 同一件事的新落点 = **`change` 委托「看见 `data-act` 就跑」**（不再需要任何登记）。
    """
    assert "extBal" in SHELL, "壳里找不到「结余」那个动作"
    assert "if(ACT[a]) ACT[a](t,e);" in SHELL, (
        "`change` 委托不是「不看名单直接跑」⇒ 表单类动作（含 `extBal`）会被**静默丢弃**")


@acc("ACC-SETL-EXT-001", "001-09")
def test_结余演示容器已清成空容器():
    assert "const BAL_EX = {" not in SHELL, "结余演示块 `const BAL_EX = {` 还在"
    assert "let BAL_EX = {};" in SHELL, "`BAL_EX` 没改成「空容器 + 后端填充」"


@acc("ACC-SETL-EXT-001", "001-07")
def test_结余适配层过N0且不给未录入补值():
    """⚠️ 后端金额出**字符串**（不过 `N0()` 会显示成带引号的串）；
    ⛔ **不给未录入补 0** —— 一补，「没填」与「填了 0」就再也分不开。"""
    body = func_body("adaptBalances")
    assert "N0(v)" in body, "结余没过 `N0()`"
    assert re.search(r"if \(v == null \|\| v === ''\) return;", body), \
        "空值（未录入）没被跳过 ⇒ 会给未录入补一个值（0 与「未录入」就分不开了）"


@acc("ACC-SETL-EXT-001", "001-11")
def test_reloadM07填充结余():
    """⭐ 重拉是**唯一出口**：`BAL_EX` 必须由 `reloadM07()` 从后端 `balances` 原地填。"""
    body = func_body("reloadM07")
    assert "adaptBalances(ex && ex.balances)" in body, "没读 `/api/m07/extract` 的 `balances`"
    assert "Object.keys(BAL_EX).forEach(k => delete BAL_EX[k]);" in body, \
        "`BAL_EX` 没「原地清空再填」（外部持有的引用会指向旧对象）"


@acc("ACC-SETL-EXT-001", "001-09")
def test_结余列渲染成可编辑输入且合计下标跟着移():
    """「点格即改」的形态判据 ＋ ⚠️ **加列后合计行的列下标必须跟着移**（否则合计算到「结余」列上）。"""
    body = func_body("extBlock")
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
    """⚠️ 2026-09-19（性能 `P3` 主体）：`boot()` 不再**逐路拉**（改成「进哪页拉哪页」）
    ⇒ 判据**一字未变地搬到取数表上**（原来证的是「`reloadM07` 必须等在 `reloadMech`/`reloadInv` 之后」）：
    ① `收发结存与大表` 这一路在 `LOADERS` 里；② 它在 `LOAD_DEP`（＝必须等前置路）；
    ③ ⭐ **凡吃到它的页，清单里必须同时列前置两路**（`机械 6 列` ＋ `库存单据`）—— 这是**行为级**断言，
       比原来的"文本次序"更强：次序写反 / 清单漏项 / 依赖组被拆掉，它都会红。
    """
    assert "收发结存与大表" in loaders(), "没有「收发结存与大表」这一路取数"
    assert "收发结存与大表" in const_items("LOAD_DEP"), "它不在 `LOAD_DEP` 里（依赖屏障丢了）"
    for page, labels in page_load().items():
        if "收发结存与大表" in labels:
            for need in DEP_BEFORE["收发结存与大表"]:
                assert need in labels, \
                    f"`PAGE_LOAD['{page}']` 吃了大表却没列前置的「{need}」（机械列 / 焊材气体列会取空）"


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
    body = page_slice("m07")
    assert "API." not in body, "`V.m07` 里出现了 API 调用 ⇒ 原型渲染逻辑被改（该走适配层）"
    assert "WHM['2026-08']" not in body, "`V.m07` 仍引用演示基线（演示块已删 ⇒ 会崩）"


@acc()
def test_金额格式化认null():
    """后端给 `null`（不可得）⇒ 页面显「—」—— 现在主要发生在「取数口被显式摘除」时
    （`TAIL-25` 已接入 ⇒ 正常态有真数；⚠️ 这条守卫**必须留着**：兜底路一坏，"不可得"就会显示 0.00）。

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
    """⚠️ `TAIL-25` 接入后正常态有真数；这条守的是**兜底路**（取数口被显式摘除 ⇒ `null` ⇒ 「—」，
    ⛔ 不写 0 冒充"确实没有"）—— 壳里那个 `MAT_OK ?` 三元**必须留着**，⛔ 别当死代码清掉。"""
    body = SHELL[SHELL.find("const bigMatCum = wh =>"):][:400]
    assert "MAT_OK ?" in body and ": null" in body, "`bigMatCum` 取数口不可得时没给 `null`（会写 0）"
