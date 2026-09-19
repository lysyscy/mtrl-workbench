"""`m04`（付款计划）**前端壳接线**断言（离线 · 静态）。

配套：
- 运行时端到端 = `tools/_e2e_m04_wired.py`（真机 ＋ **真库**，跑完清理）
- 结构一致性 = `tools/ui_parity.py`（U1 视图逐行一致 / U2b 已接线页不得留演示数组）

⚠️ **本文件测不了什么**：它是**静态检查**（壳里有没有那些接线点），**不证明运行时真调通**。
   两把都要 —— 这正是「判据绿 ≠ 链路对」的教训。

⭐ 其中四条是**反向**断言：审查结果不许前端自算 · 不许用本地赋值冒充落库 ·
   不许对没接的动作说成功 · 已接线页的**演示数组必须已删**。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc

from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛


def _act(name: str, limit: int = 6000) -> str:
    """取 `ACT` 里 `<name>:async ()=>{…}` 的**函数体**（⚠️ 必须**花括号配平**）。

    ⚠️ 别用「起点 + 固定字符数」—— 那是**假绿/假红的温床**：截短了断言看不到要查的代码，
       截长了会**吃进下一个动作**（反向灵敏度实测踩到：`plRowSave` 的 2400 字符窗口
       把后面的 `plRowCancel` 吃了进来 ⇒ 「失败时不许清草稿」这条**误判**）。
    """
    i = SHELL.find(f"{name}:async ()=>{{")
    assert i > 0, f"找不到 `{name}:async ()=>{{`"
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
    assert len(body) < limit, f"`{name}` 取到 {len(body)} 字符 —— 配平可能跑偏"
    return body


# --------------------------------------------------------------- 接线点（正向）


@acc()
def test_壳把m04标为已接后端并指向真实端点():
    assert "'m04'" in SHELL and "const WIRED=new Set(" in SHELL
    assert "/api/m04/plans?year_month=" in SHELL
    for fn in ("API.plCell", "API.plRematch", "API.plForce", "API.plForceCancel",
               "API.plDelete", "API.plDeleteImpact"):
        assert fn in SHELL, f"缺写动作接线点：{fn}"


@acc()
def test_付款计划字段在适配层完成转形():
    """后端 `audit_result` / `forced_through` / `is_manual` / 派生两列 → 原型 `PL_COLS` 字段名。"""
    assert "function adaptPlan(x)" in SHELL
    assert "result: x.audit_result" in SHELL
    assert "forced: !!x.forced_through" in SHELL and "manual: !!x.is_manual" in SHELL
    assert "pay_date: 'pay_date'" in SHELL or "PL_COL_API" in SHELL
    # 「项目」列必须保留**用户填报原值**（换成展示名会把「未匹配」这一档抹掉）
    assert "proj: x.project_input || ''" in SHELL


@acc()
def test_写动作统一走后端并以后端为准重拉():
    assert "async function reloadPlans()" in SHELL
    assert "async function plAct(fn, okMsg, ms)" in SHELL
    # 删除走 §4.3.6 两步：先取**后端**影响范围
    assert "await API.plDeleteImpact(ids)" in SHELL


# --------------------------------------------------------------- 反向（不许再出现）


@acc()
def test_审查结果不再由前端自算():
    """唯一出口 = 后端 `domain.audit_rows`（§4.3.4 的 6 种判定）。

    原型原先在浏览器里实时派生（查通知书 ＋ 重复检测）⇒ 那是**第二份口径**。
    """
    assert "const plRev=(p)=>String((p&&p.result)" in SHELL, "`plRev` 没改成读后端"
    assert "if(Number(p.monthAmt)>Number(n.approve)-paidOf(n.id)) return '超过未付';" not in SHELL, \
        "旧的**前端判定**还在 ⇒ 口径有两份"


@acc()
def test_写动作不許用本地赋值冒充落库():
    assert "p[f]=String(t.value" not in SHELL, "行内改列还在改内存"
    assert "p.forced=true" not in SHELL, "强制通过还在改内存"
    assert "PLs.splice(i,1)" not in SHELL, "删除还在改内存"
    assert "plAlert" not in SHELL and "plNextIds('PL',3)" not in SHELL, "旧的造演示行还在"


@acc()
def test_已接线页的演示数组必须已删():
    """`m04` 标了「已接后端」⇒ 演示数组 `PL` 不得残留（产品化红线①）。"""
    assert "const PL = [" not in SHELL
    assert "let PLs=[];" in SHELL


@acc()
def test_导入与手动行已接通():
    """⭐ `TAIL-35` 接线后**改写的断言** —— 旧断言钉的是「**未接通**」这个**临时状态**。

    ⚠️ 改写理由（不是「把绿改红」，是**守的状态变了**）：`TAIL-35` 的定义就是「随 `TAIL-27` 其余页接」，
       现在接了 ⇒ 「必须如实说未接通」这条使命完成。**反向内核保留**：
       ⛔ 不许留任何「说了未接通、却在别处假装成功」的入口（旧的造演示行也仍在禁列）。
    """
    assert "导入尚未接通壳" not in SHELL, "导入还挂着「未接通」提示（已接线）"
    assert "手动行尚未接通壳" not in SHELL, "手动行还挂着「未接通」提示（已接线）"
    # 反向内核（照旧）：不许造演示行冒充成功
    assert "plAlert" not in SHELL and "plNextIds('PL',3)" not in SHELL, "旧的造演示行还在"


@acc()
def test_导入与手动行走后端():
    """⭐ 接线点：导入 = **multipart** → `/api/m04/import`；手动行 = JSON → `/api/m04/plans`。"""
    assert "m04Import: async (year_month, file) =>" in SHELL, "导入没写 multipart 客户端"
    assert "new FormData()" in SHELL, "导入没用 `FormData`（multipart 只能这么传）"
    assert "plImportOk:async ()=>" in SHELL, "`plImportOk` 没改成 async（那还是假导入）"
    assert "API.m04Import(" in SHELL, "`plImportOk` 没走 `/api/m04/import`"
    assert "m04PlanSave: body => API.post('/api/m04/plans', body)" in SHELL, (
        "手动行没走 `/api/m04/plans`"
    )
    assert "plRowSave:async ()=>" in SHELL, "`plRowSave` 没改成 async"


@acc()
def test_手动行判据不得在前端复写():
    """⭐ 反向：手动行的校验（年月 / 项目 / 金额）**一律后端**（`plan_manual.manual_row_payload`）。

    前端只把**原值**送上去 —— 复写任何一道 = **第二份口径**（`D18`：判定一律后端）。
    """
    body = _act("plRowSave")
    assert "API.m04PlanSave(" in body, "`plRowSave` 没调后端"
    for bad, why in (
        ("badMoney(", "还在前端复写**金额**校验"),
        ("pjRowOf(d.proj)", "还在前端复写「**项目必选**」"),
    ):
        assert bad not in body, f"`plRowSave` {why}（⇒ 第二份口径）"


@acc()
def test_手动行失败时保留已填内容():
    """§4.3.3.1：**校验失败 ⇒ 保留已填内容**（不清空重填）⇒ 失败分支**不许**清草稿层。"""
    body = _act("plRowSave")
    assert "plRowEditId=''; plD={};" in body, "成功后没清草稿（行已落库，该清）"
    j = body.find("}catch(e){")
    assert j > 0, "`plRowSave` 没有 catch 分支"
    assert "plD={}" not in body[j:], "失败时把草稿清空了（§4.3.3.1 要求**保留已填内容**）"


@acc("ACC-PLAN-MANUAL-001", "001-06")
def test_手动行有徽标_导入行没有():
    """⭐ 判据点**搬家**（`§19` 批 2）：原先钉在**旧服务端页**的 HTML 上（`render_m04` 输出的
    「手动」徽标 ＋ 「编辑」入口只对手动行出现）。旧页整体删除（授权 `D18`）⇒ 改指**新壳**
    （⛔ 判据不删 —— `§19` 铁律：形态变了搬断言）。

    ⚠️ 认法要能**分别看住两种行**：徽标与「编辑」入口**都由 `p.manual` 分支**给出 ——
       ⛔ 不许无条件渲染（那样**导入行也会挂上「手动」**，正是原判据要防的）。
    """
    assert "${p.manual?' <span class=\"tag t-in\"" in SHELL, \
        "手动行徽标没按 `p.manual` 分支渲染 ⇒ 导入行会一起挂上「手动」"
    assert ">手动</span>':''}" in SHELL, "徽标分支没闭合（要么无条件渲染、要么文案与判据对不上了）"
    assert "${p.manual?`<button class=\"btn sm\" data-act=\"plRowEdit\"" in SHELL, \
        "「编辑」入口没按 `p.manual` 分支（§4.3.3.1：只有手动行可编辑）"


@acc()
def test_手动行三个本地动作已恢复原型():
    """⭐ `plRowAdd` / `plRowEdit` 是**本地草稿层**（**不落库**）⇒ 接线后恢复原型实现即可、无需改。"""
    assert "plRowEditId=PL_NEW_ID; plD=plBlank(); render();" in SHELL, "`plRowAdd` 没恢复原型"
    assert "plD={ym:p.ym, proj:plProjKey(p.proj)" in SHELL, "`plRowEdit` 没恢复原型"
    assert "编辑只对「手动行」开放" in SHELL, "「只有手动行可编辑」的提示丢了（§4.3.3.1）"


@acc()
def test_后端两个新端点存在():
    """`TAIL-35` 的后端落点：手动行 JSON 端点 ＋ 导入 multipart 端点。

    ⚠️ 端点**已搬到 `plan_api_router.py`** —— `router.py` 加了这两段后涨到 **668 行 > 600**（禁合入硬线）
       ⇒ 按本仓纪律**拆件**（`router.py` 只留页面端点，用 `include_router` 汇总）。
    ⚠️ 断言必须**进各自函数体**取切片 —— 只写「文件里含 `manual_row_payload(`」是**假绿**
       （反向灵敏度实测：改成 `_` 前缀后照样通过 —— **子串喂饱**）。
    """
    base = Path(__file__).resolve().parents[1] / "app" / "mod04_plan"
    api = (base / "plan_api_router.py").read_text(encoding="utf-8")
    router = (base / "router.py").read_text(encoding="utf-8")
    assert '@router.post("/api/m04/plans")' in api, "后端缺 `POST /api/m04/plans`"
    assert '@router.post("/api/m04/import")' in api, "后端缺 `POST /api/m04/import`"
    assert "router.include_router(plan_api_router)" in router, "`router.py` 没汇总 API 路由（端点会 404）"
    for fn, needle, why in (
        ("def api_plan_row_save(", r"(?<![A-Za-z_])manual_row_payload\(",
         "手动行端点没走 `manual_row_payload`（判定该与 PRG 端点复用**同一出口**）"),
        ("def api_plan_import(", r"(?<![A-Za-z_])repo\.merge_month\(",
         "导入端点没走 `repo.merge_month`（§9.5 幂等就没了）"),
    ):
        i = api.find(fn)
        assert i > 0, f"`plan_api_router.py` 里找不到 `{fn}`"
        j = api.find("\n@router.", i)                     # 到下一个路由为止（函数体边界）
        body = api[i:j if j > i else i + 2500]
        assert re.search(needle, body), why
