"""`MOD-08` 库存单据 / 调整单 —— **前端壳接线的离线断言**。

真机验证在 `tools/probe/_e2e_m08_wired.py`（连库 + 连服务），本文件只做**静态接线断言**。

⚠️ 这里钉的是**接线本身**，不是"页面好不好看"：
1. **适配层必须覆盖全部列键** —— 漏一个键 ⇒ `iv.<键>` 恒 `undefined`（**静默失配、不报错**），
   `m01` 的状态枚举就踩过同一个坑。
2. **判据不得在前端复写**（`D18`：判定与落库一律后端）—— 防出**第二份口径**。
3. **不许本地赋值冒充落库** —— 防**假成功**。
4. **不许把"加载时求值"留在接后端的数据上** —— `IVs` 变异步填充后，加载时算出来的
   `PROC_PJS` / `procPj` 会**永远停在空值**上（页面没候选、不报错）。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL, const_items, func_body  # noqa: F401  ← `P4`① 读取点收敛
ROUTER = (ROOT / "backend" / "app" / "mod08_inv" / "router.py").read_text(encoding="utf-8")

# ⭐ 2026-10-03（`TAIL-219` 批 2b）：本件原先自带两把剪刀（`_body` / `_shell_list`）——
#    已**整把删掉**，取段改走壳的语义口径（函数 ⇒ `func_body` · 常量项 ⇒ `const_items`）。⛔ 别写回来。


# ============================================================== 1 · 数据源已换后端


# ----------------------------------- `ACC-INV-001` 的**形态**半边（搬家 · `§19` 批 2）
#
# 原先钉在**旧服务端页** `render_inv_page` 渲染出的 HTML 上；旧页删除（授权 `D18`）⇒
# 形态那半边**改指新壳**（⛔ 判据不删）。实质（判定/取数/口径）仍留在 `tests/test_acc_inv.py`。


@acc("ACC-INV-001", "001-01")
def test_表头出口在且可筛列数由列元数据派生():
    """旧页：断言渲染出的表头逐列 = **后端** `INV_TABLE_COLUMNS`（列结构的唯一主人）。
    新壳：表头出口 `ivThead()`（**逐列插筛选入口**）＋ 可筛列数 `IV_COLN = IV_FCOL.length`
    —— `IV_FCOL` 是列元数据的**唯一出处**（末列「操作」不参与筛选）。"""
    assert "const ivThead=()=>{" in SHELL, "表头渲染出口没了"
    assert "const IV_COLN=IV_FCOL.length;" in SHELL, "可筛列数不是由列元数据派生的"


@acc("ACC-INV-001", "001-02")
def test_重置回默认年月():
    """旧页：`href="/m08"`（不带参数）就是「重置」。新壳：`fIvReset` 把核算年月重置回**默认月**（上月）。"""
    assert "fIvReset:()=>{" in SHELL and "fIvYm=bjMonth(-1)" in SHELL, "重置没回到默认年月"


@acc("ACC-INV-001", "001-05")
def test_每列筛选由后端列键驱动():
    """旧页：每个可筛列都有 `name="f_<key>"`，末列「操作」没有。新壳：列筛选由 `IV_FCOL`（**后端给的列键**）
    驱动 ⇒ ⛔ 前端不另立一份列清单（列清单的主人 = 后端 `domain.INV_TABLE_COLUMNS`）。"""
    assert "IV_FCOL" in SHELL and "ivColPass" in SHELL, "壳里没有列筛选通道"


@acc("ACC-INV-001", "001-06")
def test_数值列既给区间也给值清单():
    """旧页：数值列同时给「区间」与「值清单」。新壳：`ivColMin`/`ivColMax`（区间）＋ `ivColVal`（值清单）并存。"""
    for k in ("ivColMin", "ivColMax", "ivColVal"):
        assert k in SHELL, f"壳里没有 {k}（数值列的区间 / 值清单少了一条）"


@acc("ACC-INV-001", "001-07")
def test_合计行由表头派生且单价列不求和():
    """旧页：合计行在 `<tbody>` 内、格数 = 表头列数（**派生**）、两个单价列留空。
    新壳：`sumRowOf(INV_THEAD, …)` ⇒ 格数**由表头派生**（结构性保证 ✓）＋ 说明里点明两个单价列不求和。"""
    assert "sumRowOf(INV_THEAD,list,invSums,{tip:'" in SHELL, "合计行不是由表头派生的"
    assert "两个单价列不求和" in SHELL, "「单价列不求和」这条没说清"
    # ⭐ 2026-09-29（`TAIL-64` P2⑤）：**表外壳**也走统一出口 `TBL`（⛔ 别退回裸 `<table class="dt" data-sort …>`）。
    #   自证 = `tools/mut/_mut_tbl.py` 的 M11 去掉这处委托 ⇒ 必须红。
    assert "TBL({head:ivThead(),key:'m08:invoices'," in SHELL, \
        "库存单据明细表没走统一出口 `TBL`（`TAIL-64` P2⑤）"


@acc("ACC-INV-001", "001-08")
def test_空态行跨列数由表头派生():
    """旧页：空态提示行的 `colspan` 由表头列数派生。
    新壳同款：走**空态唯一出口** `EMPTYROW(thCount(INV_THEAD), …)`（跨列数仍由表头派生）。"""
    assert "EMPTYROW(thCount(INV_THEAD)" in SHELL, "空态行的跨列数不再由表头派生"
    assert "没有库存单据明细" in SHELL, "空态文案丢了"


@acc("ACC-INV-001", "001-11")
def test_抓取弹窗默认取本页核算年月且讲清强踢():
    """旧页：`id="fetchMonth"` 的默认值 = 本页当前所选核算年月；且弹窗里必须讲清**会登录 i8 强踢**（`D9`）。"""
    assert "fetchIv:()=>{ fetchKind='iv'; fetchM=fIvYm;" in SHELL, "抓取弹窗没取本页当前年月"
    assert "强踢" in SHELL, "D9（会强踢在线用户）没告知"


@acc("ACC-INV-001", "001-12")
def test_两种导出并存且透视那份写明独立通道():
    """旧页：`data-act="exp"` 与 `data-act="expPivot"` **并存**，后者写明工作簿形态与「主表那份不受影响」。"""
    assert 'data-act="expPivot"' in SHELL, "透视导出没接"
    # ⚠️ 2026-09-27（守则 §3.1 · `TAIL-117` 批次 2/3）：悬停里那句实现话术（「脚本改 i8 导出源文件」）
    #    与「朴素导出」这种内部叫法换成人话 ⇒ token 同步，**口径一字未改**（仍要求写明"是独立通道"）。
    assert "单独的一条通道" in SHELL and "不影响主表那份" in SHELL, "没写明透视是**独立通道**"
    assert 'data-t="库存单据明细总表"' in SHELL, "朴素导出没接"


@acc("ACC-INV-001", "001-13")
def test_壳里不出现删除入口与是否作废():
    """旧页：拿 `boundary_violations` 扫 HTML ＋ 页面上不得出现删除入口 /「是否作废」列。
    新壳同理 —— 直接拿**域内核那把尺子**去扫**壳全文**（同一把尺子、更难糊弄的对象）。"""
    from app.mod08_inv.domain import FORBIDDEN_ACTIONS

    for act in FORBIDDEN_ACTIONS:
        assert f'data-act="{act}"' not in SHELL, f"壳里出现了删除入口：{act}"
    assert "是否作废" not in SHELL, "壳里出现了「是否作废」（不许建这个字段/列）"


@acc()
def test_演示数组已删():
    """两张演示数组必须**物理删除**（留着就永远渲染演示数据 —— `ui_parity` 的 `U2b` 也查）。"""
    assert "const IV = [" not in SHELL, "库存单据演示数组 `IV` 还在"
    assert "const AD = [" not in SHELL, "调整单演示数组 `AD` 还在"


@acc()
def test_数据源改为后端填充():
    assert "let IVs=[], ADs=[];" in SHELL, "`IVs`/`ADs` 没改成「空数组起手 + 后端填充」"
    assert "IVs=IV.map(" not in SHELL, "`IVs` 还在从演示数组生成"
    assert "await API.m08Inventory()" in SHELL, "`reloadInv()` 没读 `/api/m08/inventory`"


@acc()
def test_加载时求值的两处已改为重算():
    """`PROC_PJS` / `procPj` 不能停在"加载时算出来的空值"上（**静默失去候选**）。"""
    assert "const PROC_PJS=uniqBy(IVs" not in SHELL, "`PROC_PJS` 仍是加载时一次性求值"
    assert "let PROC_PJS=[];" in SHELL, "`PROC_PJS` 没有改成可重算的空数组"
    body = func_body("reloadProc")
    assert "PROC_PJS = d.projects" in body, "过程资料候选须包含后端历史项目"
    assert "procPj = PROC_PJS[0]" in body, "过程资料首次读取须落定当前项目"
    assert "let procPj=PROC_PJS[0]" not in SHELL, "`procPj` 仍是加载时求值"


@acc()
def test_仓库候选与数据源同源():
    """⚠️ 候选用演示主数据 `WHs` ⇒ 与 i8 真名对不上，**选了也筛不出行**（静默失配）。"""
    assert "pjSort(uniqBy(IVs,iv=>iv.wh))" in SHELL, "库存候选须只取真实库存仓库"
    assert "pjSort(WHs.map(w=>w.name))" not in SHELL, "「项目」候选还在用演示 `WHs`"
    assert "WHs.map(w=>w.name).forEach" not in SHELL, "「全选项目」还在用演示 `WHs`"


# ============================================================== 2 · 适配层覆盖全部列键


@acc()
def test_适配层覆盖全部列键():
    """⭐ 最关键的一条：`IV_COLS` / `AD_COLS` 里**每一个键**都要在适配层里有落点。

    漏一个 ⇒ 壳里读 `iv.<键>` 恒 `undefined`（合计恒 0 / 状态列恒空），**而且不报错**。
    """
    inv_body = func_body("adaptInv")
    adj_body = func_body("adaptAdj")
    miss_i = [k for k in const_items("IV_COLS") if f"{k}:" not in inv_body]
    miss_a = [k for k in const_items("AD_COLS") if f"{k}:" not in adj_body]
    assert not miss_i, f"`adaptInv` 漏了列键 {miss_i} ⇒ 壳里读它们是 undefined（静默失配）"
    assert not miss_a, f"`adaptAdj` 漏了列键 {miss_a} ⇒ 同理"


@acc()
def test_适配层把id转成字符串():
    """原型的 `data-*` 是字符串、`===` 比较不转会**静默找不到行**（`m03` 的教训）。"""
    inv_body, adj_body = func_body("adaptInv"), func_body("adaptAdj")
    assert "id: String(r.id)" in inv_body, "`adaptInv` 的 `id` 没转成字符串"
    assert "ivid: String(a.row_id)" in adj_body, "`adaptAdj` 的 `ivid` 没转成字符串"


@acc()
def test_留痕转成对象数组():
    """`adjDlg` 里按 `x.field / x.before / x.after` 取值 ⇒ 必须是**对象数组**
    （原型演示数据给的是数组数组 ⇒ 那张卡会渲染出一排 `undefined`）。"""
    body = func_body("adaptAdj")
    assert re.search(r"trail:\s*\[\{[^}]*field:", body), "`trail` 不是对象数组 ⇒ 留痕卡会显示 undefined"


@acc()
def test_适配层把金额转成数字():
    """⛔ **后端金额出的是字符串**（`numeric(18,2)` 精度保护，与 `m05` 同款 —— 用 JSON number 会在
    浮点上抖）。所以适配层**必须**过 `N0()`：不过的话，壳里的求和会变成**字符串拼接**
    （`'82920.00' + '1.00'` ⇒ `'82920.001.00'`）—— 合计那一栏会安静地错掉，**不报错**。

    ⚠️ 这条是**真发现**（首次真机验证时 e2e 报出来的），不是照抄的检查项。
    """
    body = func_body("adaptInv")
    for k in ("qty", "px", "pi", "amt", "tax"):
        assert re.search(rf"{k}:\s*N0\(", body), f"`adaptInv` 的 `{k}` 没过 `N0()`（字符串会拼进求和）"
    assert "newAmt: N0(" in func_body("adaptAdj"), "`adaptAdj` 的 `newAmt` 没过 `N0()`"


# ============================================================== 3 · 写动作走后端（含反向）


@acc()
def test_打调整单走后端且不在前端复写判据():
    """⭐ 反向：**不许**再有前端判据（`badMoney`）+ 本地 `ADs.push` 冒充落库。"""
    i = SHELL.find("adjOk:async t=>{")
    assert i > 0, "`adjOk` 没改成 async（异步走后端）"
    j = SHELL.find("adjDel:async t=>{", i)
    body = SHELL[i:j if j > i else i + 1200]
    assert "API.m08Adjust(" in body, "`adjOk` 没走 `/api/m08/adjust`"
    assert "ADs.push(" not in body, "`adjOk` 还在本地 push 调整单（假成功）"
    assert "badMoney(" not in body, "`adjOk` 还在前端复写判据（⇒ 第二份口径）"
    assert "!rs" not in body, "`adjOk` 还在前端判「备注必填」（该由后端 `adjustment_problem` 一把管）"


@acc()
def test_撤销调整单走后端():
    """⭐ 反向：不许再 `ADs.splice` 本地删（原实现只改内存、刷新就回来 —— 假成功）。"""
    i = SHELL.find("adjDel:async t=>{")
    assert i > 0, "`adjDel` 没改成 async"
    body = SHELL[i:i + 700]
    assert "API.m08AdjustClear(" in body, "`adjDel` 没走 `/api/m08/adjust/clear`"
    assert "ADs.splice(" not in body, "`adjDel` 还在本地 splice（假成功）"


@acc()
def test_抓取分支接后端():
    assert "if(k==='iv') return ivFetchBackend(m);" in SHELL, "抓取弹窗的库存单据分支没接后端"
    body = SHELL[SHELL.find("async function ivFetchBackend("):][:1400]
    assert "API.m08Fetch(" in body, "`ivFetchBackend` 没调 `/api/m08/fetch`"
    assert "r.ok === false" in body, "抓取降级（i8 失败 ⇒ 手动导入）没处理"


# ============================================================== 4 · 后端端点 + 接线自洽


@acc()
def test_后端四个端点都在():
    for path, verb in (("/api/m08/inventory", "get"), ("/api/m08/adjust", "post"),
                       ("/api/m08/adjust/clear", "post"), ("/api/m08/fetch", "post")):
        assert f'@router.{verb}("{path}")' in ROUTER, f"后端缺端点 {verb.upper()} {path}"


@acc()
def test_抓取端点必须显式确认():
    """⛔ 防"直接 POST 打进来"的静默抓取（**会顶号**）。"""
    assert "confirmed=req.confirm" in ROUTER, "抓取端点没把 `confirm` 交给 `run_fetch`（D9 二次确认形同虚设）"


@acc()
def test_boot逐路容错():
    """⛔ **一个端点失败不得拖垮全站**。

    ⭐ 实测踩到（本轮）：后端新加了 `/api/m06/mech` 但**服务没重启** ⇒ 该端点 404 ⇒
    原来的单个 `try` 把后面**全部**跳过 ⇒ `m08`/`m05` 明明已接线却**显示空表**，
    **看起来像功能没做**（假故障，最难查的那类）。

    ⇒ 现在每路走 `soft()`：坏的那路在顶部横幅里点名，其余页照常可用。
    """
    i = SHELL.find("async function boot() {")
    body = SHELL[i:SHELL.find("function bootErrorBanner()", i)]
    # ⚠️ 2026-09-19（`P3` 主体）：`boot()` 不再逐路拉（改成「进哪页拉哪页」）⇒ 判据搬到**取数表**上
    #    （⛔ 判据一字未改：**每一路都得有取数出口、且都走 `soft()`** —— 一路失败不许拖垮全站）。
    from tests.shell_load_helpers import loaders as _loaders   # noqa: PLC0415
    assert "const soft = async (label, fn) =>" in SHELL, "壳里没有逐路容错出口 `soft()`"
    ls = _loaders()
    for label in ("付款通知书", "项目档案", "修改留痕", "付款计划", "机械 6 列", "库存单据", "付款域"):
        assert label in ls, f"「{label}」这一路取数不见了"
    assert len(ls) >= 13, f"取数路只剩 {len(ls)} 条 —— 逐路覆盖不全"


@acc()
def test_WIRED含m08():
    m = re.search(r"const WIRED=new Set\(\[([^\]]*)\]\);", SHELL)
    assert m and "'m08'" in m.group(1), "`WIRED` 里没有 `m08`（侧栏会仍标「原型态」）"


@acc()
def test_视图切片未被改动():
    """⭐ 反向：`V.m08` 里**不得**出现任何 `API.` 调用 —— 原型的渲染逻辑必须一行不改（`D18`）。

    ⚠️ 切片必须用**花括号配平**：早先写成"从 `V.m08=` 到下一个 `async function`"，
       而这两者之间夹着一大段顶层函数（ACT 条目等）⇒ **断言看的是别人的代码**（假红/假绿都出过）。
    """
    i = SHELL.find("\nV.m08=()=>{")
    assert i > 0, "壳里找不到 `V.m08=()=>{`"
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
    assert 2000 < len(body) < 12000, f"`V.m08` 切片长度 {len(body)} 可疑 —— 配平可能跑偏"
    assert "API." not in body, "`V.m08` 里出现了 API 调用 ⇒ 原型渲染逻辑被改（该走适配层）"
