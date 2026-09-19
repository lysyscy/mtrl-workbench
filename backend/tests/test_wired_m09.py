"""`MOD-09` 特殊费用月报表 —— **前端壳接线的离线断言**。

真机验证在 `tools/_shell_smoke.py`（第 ⑪ / ⑪b 段：连服务 + 连库，含**写路径往返**），
本文件只做**静态接线断言**。

⚠️ 这里钉的是**接线本身**，不是"页面好不好看"：
1. **演示容器必须已清** —— 留着就永远渲染演示值（`ui_parity` 的 `U2b` 也查 `m09→AWF`）。
2. **适配层必须把金额转成数字** —— 后端金额出**字符串**（`numeric(18,2)` 精度保护），
   而原型切片里写着 `r[1].toFixed(2)` ⇒ 不过 `N0()` 会 **TypeError 整页崩**（不报错地坏）。
3. **候选 / 默认项目必须由 `reloadM09()` 落定** —— `PJs` 是**异步填充**的，
   写成加载时求值（`const x = f(异步变量)`）会在取数回来时**早已定死成空**（静默失去候选）。
4. **判据不得在前端复写**（`D18`）—— §5.5 的金额判据唯一出口是后端 `domain.amount_problem`。
5. **不许本地改数据冒充落库**（假成功）。
6. **失败也要看回执** —— 后端对「金额不合法」回 **HTTP 200 ＋ `ok:false`**
   ⇒ 只判 `!r` 不判 `ok === false` 的话，那句"金额不合法…"会被当成成功**吞掉**。
7. ⭐ **自动项取数改用核算年月**（`inv_detail.ym`）：原实现按 `iv.dd`（**单据日期**）前缀算 ——
   口径要的是核算年月（`domain` 顶部已注明），两者在"单据日期跨月"时**不一致**且**不报错**。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛
API = (ROOT / "backend" / "app" / "mod09_fee" / "api.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "backend" / "app" / "mod09_fee" / "router.py").read_text(encoding="utf-8")


def _body(name: str) -> str:
    """取壳里 `function <name>(…){…}` 的函数体（**花括号配平**，不靠"下一个函数"）。"""
    i = SHELL.find(f"function {name}(")
    assert i >= 0, f"壳里找不到 `function {name}(`"
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


def _act(name: str) -> str:
    """取壳里 `ACT` 的**某一条动作**（从 `  <name>:` 起，按括号配平扫到该条语句结束）。

    ⚠️ 必须**只取这一条** —— 只写「文件里含 `API.m09Add(`」是**假绿**：
       同名调用在两处出现（API 客户端定义里、动作里），把动作那处变异掉照样能通过。
    """
    i = SHELL.find(f"\n  {name}:")
    assert i >= 0, f"壳里找不到 `ACT.{name}`"
    i += 1
    depth, k = 0, i
    while k < len(SHELL):
        c = SHELL[k]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "\n" and depth == 0 and k > i:
            break
        k += 1
    body = SHELL[i:k]
    assert 20 < len(body) < 3000, f"`{name}` 取到 {len(body)} 字符 —— 配平可能跑偏"
    return body


# ================================ `ACC-FEE-MON-001` 的**形态**半边（`§19` 批 2 搬家）
#
# 原先钉在**旧服务端页** `render_fee_page` 渲染出的 HTML 上；旧页删除（授权 `D18`）⇒ 形态改指新壳
# （⛔ 判据不删）。实质（取数 / 判定 / 独立复算）仍留在 `tests/test_acc_fee_mon.py`。

_AWF_THEAD_RE = re.compile(r"const AWF_THEAD=`([^`]*)`;")


def _awf_heads() -> list[str]:
    """壳里本表表头（`AWF_THEAD`）的**列标签**（去掉标签里的 HTML）。"""
    m = _AWF_THEAD_RE.search(SHELL)
    assert m, "壳里找不到 `const AWF_THEAD=`"
    return [re.sub(r"<[^>]*>", "", h).strip()
            for h in re.findall(r"<th[^>]*>([\s\S]*?)</th>", m.group(1))]


@acc("ACC-FEE-MON-001", "001-01")
def test_壳里自动项与手填项同桌():
    """§5.5：**1 个固定自动项行 ＋ N 个手填项行**，同一张表（`data-sort-key="m09:awf"`）。"""
    s = _slice("m09")
    assert 'data-sort-key="m09:awf"' in s, "壳里这张表不是「特殊费用月报表」"
    assert "安全文明施工费</b>（按 CBS 分类）" in s, "自动项那一行没了"
    assert "${list.length?list.map(" in s, "手填项没有由后端 `list` 渲染"


@acc("ACC-FEE-MON-001", "001-02")
def test_壳里合计行由共用出口出():
    """合计行的**金额格**由 `sumRowOf(AWF_THEAD, …)` 的 `{2:…}` 给出 —— 走全站唯一金额出口
    （**千分位**由它统一出，页面不再自己拼字符串）。"""
    assert "sumRowOf(AWF_THEAD, list, {2:()=>total" in SHELL, "合计行不是由共用出口出的"


@acc("ACC-FEE-MON-001", "001-04")
def test_壳里重置回默认月与默认项目():
    """「重置」= 核算年月回**默认月**（上月）＋ 项目回**默认项目**（候选第一个）。"""
    assert "awfReset:()=>{ awfYm=bjMonth(-1); awfPj=AWF_PJS[0]||'';" in SHELL, "重置没回默认"


@acc("ACC-FEE-MON-001", "001-05")
def test_壳里空态行跨列数由表头派生():
    """未录的那一份 ⇒ 空态提示行，`colspan` **由表头列数派生**（⛔ 不写死数字）。"""
    assert 'colspan="${thCount(AWF_THEAD)}"' in SHELL, "空态行的跨列数不再由表头派生"
    assert "还没有手填项" in SHELL, "未录的月没有提示"


@acc("ACC-FEE-MON-001", "001-06")
def test_壳里项目面板是单选且候选键来自后端():
    """§2.7.4：候选**键 = 仓库名**（后端 `projects` 的 `key`）；面板**单选**（`single:true` ⇒ 无全选/清空）；
    ⚠️ 传进 `projPanel` 的必须是**候选键**（`AWF_PJS`）而不是档案行对象（否则 `data-pj="[object Object]"`）。"""
    assert "const awfPjPanel=()=>projPanel({list:()=>AWF_PJS" in SHELL and "single:true})" in SHELL, \
        "项目面板不是单选、或候选不是那份键清单"
    assert "AWF_PJS = (d.projects || []).map(p => p.key)" in SHELL, "候选不是由后端落定（键 = 仓库名）"


@acc("ACC-FEE-MON-001", "001-09")
def test_壳里本页不设导出入口且写明随台账导出():
    """§7.1 / §5.5：本表**随「逐月欠款台账」导出**、**本页不设单独导出按钮**。"""
    s = _slice("m09")
    assert "逐月欠款台账" in s, "没写明它随台账导出"
    assert "export" not in s.lower(), "壳的 m09 视图里出现了导出入口（本页不该有）"


@acc("ACC-FEE-MON-001", "001-10")
def test_壳里表头是本表自己的列而非库存单据透视形态():
    """`DEV-R-04`：本表 = **独立新报表**。壳的表头 = `AWF_THEAD`（自家列出口）：含库存单据没有的
    **数据项 / 来源 / 占合计**，且**列数比库存单据少** —— 透视表不可能长这样。"""
    from app.mod08_inv.domain import INV_TABLE_COLUMNS
    from app.mod09_fee import domain as D

    mine = _awf_heads()
    assert mine == [c["label"] for c in D.AWF_COLUMNS], f"壳表头 ≠ 本表列出口：{mine}"
    assert set(mine) - {c["label"] for c in INV_TABLE_COLUMNS} == {"数据项", "来源", "占合计"}
    assert len(mine) < len(INV_TABLE_COLUMNS)


# ============================================================== 1 · 演示数据已清

@acc()
def test_m09演示容器已删():
    """演示容器与其 3 个月演示值必须**物理删除**（留着就永远渲染演示数据 —— `U2b` 也查）。"""
    assert "let AWF = {" not in SHELL, "特殊费用演示容器 `let AWF = {` 还在"
    assert "'华能德州热电联产项目仓库': [['油卡使用'" not in SHELL, "3 个月演示手填值还在"
    for dead in ("awfMut", "awfMonth()"):
        assert dead not in SHELL, f"已失效的 `{dead}` 还在（它只服务于已删的演示容器）"


@acc()
def test_m09数据源改为后端填充():
    assert "let AWF_ROWS = [];" in SHELL, "`AWF_ROWS` 没改成「空数组 + 后端填充」"
    assert "let AWF_PJS = [];" in SHELL, "`AWF_PJS` 没改成「空数组 + 后端填充」"
    body = _body("reloadM09")
    assert "API.m09Fee(" in body, "`reloadM09()` 没读 `/api/m09/fee`"
    for v in ("AWF_PJS = (d.projects", "AWF_ROWS = (d.manuals", "AWF_AUTO = N0(",
              "AWF_TOTAL = N0("):
        assert v in body, f"`reloadM09()` 没落定 `{v}…`"


# ============================================================== 2 · 适配层

@acc()
def test_m09适配层把金额转成数字():
    """⛔ 后端金额出**字符串**，切片里却是 `r[1].toFixed(2)` ⇒ 不过 `N0()` **整页崩**。

    ⚠️ 断言必须**钉在 `awfList` 那一行本身**（它才是喂给切片的那一处），
       不能只写「文件里出现过 `N0(r.amount)`」—— 别处也可能有一模一样的子串。
    """
    m = re.search(r"const awfList = \(\) => AWF_ROWS\.map\(([^;]*)\);", SHELL)
    assert m, "壳里找不到 `const awfList = () => AWF_ROWS.map(...)`"
    assert "N0(r.amount)" in m.group(1), f"`awfList` 的金额没过 `N0()`：{m.group(1)[:80]}"


@acc()
def test_m09自动项不再由前端按单据日期算():
    """⭐ 口径：自动项取数用**核算年月**（`inv_detail.ym`）。

    原实现 `awfAuto` 按 `iv.dd`（**单据日期**）前缀从壳里的 `IVs` 自算 —— 与后端口径不同，
    且**不报错**（金额只是悄悄对不上）。接线后必须读后端落定的值。
    """
    i = SHELL.find("const awfAuto =")
    assert i > 0, "壳里找不到 `const awfAuto =`"
    line = SHELL[i:i + 130]
    assert "AWF_AUTO" in line, "`awfAuto` 没改成读后端落定的 `AWF_AUTO`"
    assert "IVs" not in line, "`awfAuto` 还在前端按 `IVs` 自算（口径应以后端 `inv_detail.ym` 为准）"


@acc()
def test_m09合计不再由前端自算():
    """⭐ 合计 = 自动项 ＋ Σ手填项 —— 算法主人是后端 `domain.total_amount`，前端只读结果。"""
    i = SHELL.find("const awfTotal =")
    assert i > 0, "壳里找不到 `const awfTotal =`"
    line = SHELL[i:i + 130]
    assert "AWF_TOTAL" in line, "`awfTotal` 没改成读后端落定的 `AWF_TOTAL`"
    assert "reduce(" not in line, "`awfTotal` 还在前端自算求和（= 第二份口径）"


# ============================================================== 3 · 候选与默认值

@acc()
def test_m09候选与默认项目由重拉落定():
    """⚠️ 原先 `awfPj = (pjSort(ntPjList())[0]||{name:''}).name` 是**加载时求值** ⇒ 静默空。

    接线后两件事都必须在 `reloadM09()` 里做（`awfPj` 按后端回包的 `project` 落定）。
    ⚠️ 断言必须落在这个函数**自己的作用域**里（`awfPj = d.project` 只此一处），
       只写「文件里含 `AWF_PJS`」会被别处的同名子串喂饱。
    """
    assert "awfPj = (pjSort(ntPjList())[0]" not in SHELL, "默认项目又变回「加载时求值」了"
    assert "awfPj = d.project" in _body("reloadM09"), \
        "`reloadM09()` 没按后端回包的 `project` 落定默认项目"


@acc()
def test_m09面板候选用后端清单():
    """⭐ 候选必须与写路径**同源**：后端 `build_candidates` ⇒ 键 = 仓库名 ⇒ `project_by_key` 认。

    ⚠️ 断言只看 `awfPjPanel` **这一段**（拿 `ntPjList()` 的地方不止一处，查全文会误判）。
    """
    i = SHELL.find("const awfPjPanel=")
    assert i > 0, "壳里找不到 `const awfPjPanel=`"
    seg = SHELL[i:SHELL.find("\n", i)]          # ⚠️ 只取**这一行**（多取会把下面的注释一起圈进来）
    assert "list:()=>AWF_PJS" in seg, "候选面板没改读后端清单 `AWF_PJS`"
    assert "ntPjList()" not in seg, "候选面板还在读 `ntPjList()`（档案表全部 —— 与后端候选未必同源）"


# ============================================================== 4 · 写动作走后端

@acc()
def test_m09四个写动作都走后端():
    for name, call in (("awfAdd", "API.m09Add("), ("awfDel", "API.m09Delete("),
                       ("awfName", "API.m09Name("), ("awfAmt", "API.m09Amount(")):
        body = _act(name)
        assert call in body, f"`ACT.{name}` 没调 `{call.rstrip('(')}`"
        assert "awfAct(" in body, f"`ACT.{name}` 没走 `awfAct`（失败路径会吞掉后端原因）"


@acc()
def test_m09不得本地改数据冒充落库():
    """⛔ 反向：写动作里不得再出现 `AWF_ROWS` 的本地增删 —— 那是"假成功"（库没变、页面变了）。"""
    for name in ("awfAdd", "awfDel", "awfName", "awfAmt"):
        body = _act(name)
        for bad in ("AWF_ROWS.push", "AWF_ROWS.splice", "awfMut", "AWF_TOTAL ="):
            assert bad not in body, f"`ACT.{name}` 里出现 `{bad}` —— 本地改数据冒充落库"


@acc()
def test_m09金额判据不在前端复写():
    """§5.5 的金额判据唯一出口 = 后端 `domain.amount_problem`（只拦非数字、**允许 0 与负数**）。"""
    body = _act("awfAmt")
    for bad in ("isNaN(", "numOf(", "badMoneyMsg(", "amount_problem("):
        assert bad not in body, f"`ACT.awfAmt` 复写了金额判据（`{bad}`）⇒ 第二份口径"


@acc()
def test_m09失败也要看回执():
    """后端对「金额不合法」回 **HTTP 200 ＋ `ok:false`** ⇒ 只判 `!r` 会把那句原因**吞掉**。"""
    body = _body("awfAct")
    assert "r.ok === false" in body, "`awfAct()` 没判 `ok === false`（后端那句拒绝原因会被当成成功吞掉）"
    assert "reloadM09()" in body, "`awfAct()` 事后没重拉（失败也得以后端为准）"


@acc()
def test_m09切月份切项目都重取数():
    """手填项**按「核算年月 ＋ 项目」各存一份** ⇒ 两个筛选一变都得重新取那一份（只 `render()` 会看到旧那一份）。"""
    assert "if(sc==='awf'){ awfYm=v; mp.open=null; reloadM09();" in SHELL, \
        "月份切换没重新取数（会看到上一月那一份）"
    body = _act("awfPjPick")
    assert "reloadM09()" in body, "切项目没重新取数（会看到上一个项目那一份）"


# ============================================================== 5 · 切片与纳管

@acc()
def test_m09切片不得直连后端():
    """⛔ `V.m09` 是**原型的渲染逻辑** ⇒ 一行不改（`ui_parity` 的 `U1` 也查）。"""
    body = _slice("m09")
    for bad in ("API.", "reloadM09(", "fetch("):
        assert bad not in body, f"`V.m09` 里出现 `{bad}` —— 原型渲染逻辑被改（该走适配层）"


@acc()
def test_m09已进WIRED与boot():
    m = re.search(r"const WIRED=new Set\(\[([^\]]*)\]\)", SHELL)
    assert m, "壳里找不到 `const WIRED=new Set([...])`"
    assert "'m09'" in m.group(1), "`WIRED` 里没有 m09（侧栏仍标「原型态」）"
    # ⚠️ 2026-09-19（`P3` 主体）：`boot()` 不再逐路拉 ⇒ 判据搬到**取数表**（⛔ 判据不变：m09 得有取数出口）
    from tests.shell_load_helpers import loaders as _loaders   # noqa: PLC0415
    assert "特殊费用月报表" in _loaders(), "「特殊费用月报表」这一路取数不见了"


# ============================================================== 6 · 后端端点

@acc()
def test_后端m09端点存在且复用service出口():
    """⚠️ 读端点走 `_payload` ⇒ `build_page_data`，写端点**各自**直接调 `SV.act_*`。

    ⚠️ 断言必须**进各自函数体**取切片 —— 只写「文件里含 `SV.act_add(`」是**假绿**：
       同名调用在别处出现时，把端点里那处变异掉**只查全文照样通过**。
    """
    for ep in ('@router.get("/api/m09/fee")', '@router.post("/api/m09/fee/add")',
               '@router.post("/api/m09/fee/name")', '@router.post("/api/m09/fee/amount")',
               '@router.post("/api/m09/fee/delete")'):
        assert ep in API, f"后端缺 `{ep}`"
    for fn, needle in (("def _payload(", "SV.build_page_data("),
                       ("def _payload(", "SV.parse_state("),
                       ("def api_fee(", "_payload("),
                       ("def api_add(", "SV.act_add("),
                       ("def api_rename(", "SV.act_rename("),
                       ("def api_amount(", "SV.act_set_amount("),
                       ("def api_delete(", "SV.act_delete(")):
        i = API.find(fn)
        assert i > 0, f"找不到 `{fn}`"
        j = API.find("\ndef ", i)
        seg = API[i:j if j > i else i + 900]
        assert needle in seg, f"`{fn}` 没走 `{needle}`（判定该与 PRG 端点**同一出口**，不另写一套）"


@acc()
def test_后端m09端点剔除页面专用列():
    """⚠️ 「操作」列（`ops`）是**页面专用 HTML 占位** ⇒ `/api/*` 必须剔除（`domain.PAGE_ONLY_KEYS`）。

    ⚠️ 断言必须钉在 `_row()` **自己的作用域**里：只写「文件里含 `D.PAGE_ONLY_KEYS`」是**假绿**
       —— 文档注释里那句 `domain.PAGE_ONLY_KEYS` **含 `D.PAGE_ONLY_KEYS` 这个子串**
       （反向灵敏度实测：把实现那行改成 `if False:` **照样绿** —— 子串喂饱，同族坑第二次踩到）。
    """
    from app.mod09_fee import domain as D

    assert D.PAGE_ONLY_KEYS == ("ops",)
    i = API.find("def _row(")
    assert i > 0, "`api.py` 里找不到 `def _row(`"
    j = API.find("\ndef ", i)
    seg = API[i:j if j > i else i + 600]
    assert "if k in D.PAGE_ONLY_KEYS:" in seg, "`_row()` 没剔除 `PAGE_ONLY_KEYS`（操作列会漏进 API）"


@acc()
def test_后端m09路由已汇总():
    """`main.py` 不用改 —— `mod09` 的页面路由文件负责汇总（同 `mod07` 的做法）。"""
    assert "from app.mod09_fee.api import router as api_router" in ROUTER, \
        "`mod09_fee/router.py` 没汇总 JSON API 路由"
    assert "router.include_router(api_router)" in ROUTER, "没把 api 路由挂上去"
