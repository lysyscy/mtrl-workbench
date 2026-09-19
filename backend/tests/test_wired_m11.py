"""`M5-7` 壳接线（集采台账）的自检 —— 离线 · 只读**壳源码** · 不连库 · 不起浏览器。

⚠️ 它守的是**接线本身**（数据源换没换 · 动作有没有假装成功 · 演示数组清没清），
   ⛔ **不是**业务口径（那些在 `test_acc_jc_*.py`）。
   "页面到底跑不跑得起来"另由真机自检 `tools/_shell_smoke.py` 管（`node --check` 绿 ≠ 能跑）。

⭐ 其中三条是技能明令**照抄**的反向断言：不许再自己算不变式 · 不许用本地赋值冒充落库 ·
   不许对没接的动作说成功。它们才是真正抓 bug 的那三条。
"""

from __future__ import annotations

from tests.acc_plugin import acc
from tests.shell_src import read_shell


def _sh() -> str:
    return read_shell()


# ---------------------------------------------------------------- 结构：接线接上了

@acc()
def test_数据源接到后端_四处注册齐():
    s = _sh()
    assert "API.m11List" in s and "/api/m11/list" in s, "取数要走 `/api/m11/list`"
    assert "async function reloadM11" in s, "要有 `reloadM11`"
    assert "'集采台账': reloadM11" in s, "`LOADERS` 要认这一路（否则进页面不拉）"
    assert "m11: ['集采台账']" in s, "`PAGE_LOAD` 要登记（`P3` 的按需取数靠它）"
    assert "'m11'" in s, "`WIRED` 要加 `m11`（侧栏与顶栏据此不标「原型态」）"


@acc()
def test_适配层把后端字符串金额转成数字():
    """⚠️ 后端金额出**字符串**（`numeric(18,2)` 精度保护）⇒ 适配层必须过 `N0()`
    （漏了会让壳里求和变**字符串拼接**、合计安静地错）。"""
    s = _sh()
    assert "function adaptJc" in s, "要有适配层（⛔ 不许把转形散落到 `V.m11` 里）"
    for frag in ("contractAmt: N0(x.contract_amt)", "settle: N0(x.settle)",
                 "pay: N0(x.pay)", "debt: N0(x.debt)"):
        assert frag in s, f"适配层漏了 `{frag}`"
    assert "id: String(x.id)" in s, "⛔ id 必须转字符串（原型到处 `x.id===t.dataset.id`）"
    assert "proj: x.project_key" in s, "「项目」的键必须是**仓库名**（§2.7.4）"
    assert "notice_ids: (x.notice_ids || []).map(String)" in s, \
        "要带出通知书 id（`m03` 的集采关联靠它反查，⛔ 不补会静默变空）"


# ---------------------------------------------------------------- 三条反向断言

@acc()
def test_反向_判定搬家_金额读后端不再前端现算():
    """⭐ 反向断言①：**不许再自己算不变式**（那是第二份口径，早晚与后端分叉）。"""
    s = _sh()
    assert "const jcSettle=j=>N2(j.settle);" in s, "结算必须读后端字段"
    assert "const jcPay=j=>N2(j.pay);" in s
    assert "const jcDebt=j=>N2(j.debt);" in s
    assert "jcTradeInvSum(j):jcInvSum(j)" not in s, \
        "⛔ 不许再按子表现算结算（原实现 = 第二份口径）"
    assert "const jcDebt=j=>N2(jcSettle(j)-jcPay(j))" not in s, "⛔ 欠款不许再前端现算"


@acc()
def test_反向_动作不再本地赋值冒充落库():
    """⭐ 反向断言②：**不许用本地赋值冒充落库**。"""
    s = _sh()
    assert "JCs.forEach(j=>{ if(jcPick.has(j.id)){ j.tag=v; n++; } })" not in s, \
        "⛔ 批量标记不许再本地改数组（改完只是这一屏变了，刷新就没）"
    assert "j.tag=t.dataset.v" not in s, "⛔ 单条标记不许再本地改数组"
    assert "JCs.push(j)" not in s, "⛔ 手工新增不许再本地 push（演示数组 `JC_COLS` 也已删，那句本就跑不通）"
    assert "cur.payments.length=0" not in s, "⛔ 取消关联不许再本地改付款子表"


@acc()
def test_反向_没接的动作不假装成功():
    """⭐ 反向断言③：**不许对没接的动作说成功**，要如实说"尚未接通 ＋ 归哪条"。"""
    s = _sh()
    assert "已抓取采购合同信息（API-04）：新增" not in s, "⛔ 抓取按钮不许再报假的「已抓取」"
    assert "尚未接通" in s, "没接的动作必须**如实**说明（技能第 4 步：不得假装成功）"
    assert "M5-5" in s, "取消关联要说明它归 `M5-5`（⛔ 不留给用户一个沉默的按钮）"


@acc()
def test_演示数组已清干净():
    s = _sh()
    assert "const JC = [" not in s, "演示数组 `JC` 必须删（一份内容只许一个主人）"
    assert "const JC_COLS = [" not in s, "列序表 `JC_COLS` 随演示数据一起删"


@acc()
def test_注册齐了但没有半截函数():
    """⚠️ `jcAct` 这种"写了却没人调"的写动作外壳**本片故意不加** —— 加了会被 `wiring_audit` 报红。"""
    s = _sh()
    assert "async function jcAct" not in s, "本片（只读接线）不写动作用不到的写外壳"
