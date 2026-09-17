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
