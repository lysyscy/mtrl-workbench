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
def test_导出如实标注未落地():
    """⛔ 原型这里报「已生成 .zip」却拿不到文件 —— 接线后必须**如实说**（属 `TAIL-04`）。"""
    i = SHELL.find("zipSfjc:")
    assert i > 0, "壳里找不到 `zipSfjc`"
    body = SHELL[i:i + 900]
    assert "TAIL-04" in body, "`zipSfjc` 没标注「属 TAIL-04 尚未落地」"
    assert "已生成 <b>第四工程公司" not in body, "`zipSfjc` 还在报「已生成 .zip」的假成功"


# ============================================================== 4 · 后端端点 + 接线自洽

@acc()
def test_后端七个端点都在():
    for path, verb in (
        ("/api/m07/settlement", "get"), ("/api/m07/extract", "get"), ("/api/m07/big", "get"),
        ("/api/m07/big/cell", "post"), ("/api/m07/big/selection", "post"),
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
    i_mech = body.find("await soft('机械 6 列', reloadMech);")
    i_m07 = body.find("await soft('收发结存与大表', reloadM07);")
    assert i_mech >= 0, "`boot()` 里没有 `reloadMech` 那一路"
    assert i_m07 >= 0, "`boot()` 里没有 `reloadM07` 那一路"
    assert i_mech < i_m07, "`reloadM07` 排在 `reloadMech` 之前（大表的机械列会取到空值）"


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
