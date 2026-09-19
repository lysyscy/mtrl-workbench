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
                 "pay_sum: N0(x.pay_sum)", "debt: N0(x.debt)"):
        assert frag in s, f"适配层漏了 `{frag}`"
    # ⚠️⚠️ 键名以 `domain.DERIVED_MONEY_KEYS` 为准：**是 `pay_sum`，⛔ 不是 `pay`**。
    #    写成 `x.pay` ⇒ 拿到 `undefined` ⇒ `N0()` 变 0 ⇒ **页面金额恒 0、且不报错**（实测踩到过）。
    #    （⚠️ 断言要**写精确**：别处 `adaptNotice` 里有个 `pay: numOr0(x.pay_amount)` 也含 `x.pay`。）
    assert "pay: N0(x.pay)" not in s, "⛔ 别把付款合计的键名写成 `pay`（后端叫 `pay_sum`）"
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
    assert "const jcPay=j=>N2(j.pay_sum);" in s, "付款合计的键名是 `pay_sum`（后端 `DERIVED_MONEY_KEYS`）"
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
def test_子表弹窗按需拉明细_增删走_api():
    """⭐ 子表半片：`/api/m11/list` **不给子表明细** ⇒ 弹窗开前必须拉 `/api/m11/detail`。

    ⚠️ 另钉一条**最容易静默失效**的：`jcAct` 内部会 `reloadM11()` ⇒ `JCs` 是**原地换内容**、
      行对象被**重建** ⇒ 之后必须**重取**那一行，否则 `jcLoadSub` 写到一个已不在表里的旧对象上
      （弹窗看着"没变化"，且**不报错**）。
    """
    s = _sh()
    assert "async function jcLoadSub" in s, "要有子表按需载入器（唯一数据来源）"
    assert s.count("await jcLoadSub(") >= 4, "三个弹窗 ＋ 增删之后都要重拉明细"
    for frag in ("API.m11InvAdd({id:j.id,", "API.m11PayAdd({id:j.id,",
                 "API.m11InvDel({row_id:Number(rid)})", "API.m11PayDel({row_id:Number(rid)})"):
        assert frag in s, f"子表动作没接上 API：{frag}"
    assert "const j2=JCs.find(x=>x.id===j.id)" in s, \
        "⛔ `jcAct` 重建行对象后必须**重取**（否则静默写到废弃对象上）"
    for bad in ("j.invoices.push(", "j.payments.push(", "j.invoices.splice(", "j.payments.splice("):
        assert bad not in s, f"⛔ 不许再本地改子表冒充落库：{bad}"


@acc()
def test_演示数组已清干净():
    s = _sh()
    assert "const JC = [" not in s, "演示数组 `JC` 必须删（一份内容只许一个主人）"
    assert "const JC_COLS = [" not in s, "列序表 `JC_COLS` 随演示数据一起删"


@acc()
def test_写动作接上了_api_且抓取要二次确认():
    """⭐ 写动作半片：标记 / 批量 / 存档 / 付款方式 / 手工新增 都走 API（⛔ 不许本地改数组）。

    ⚠️ 抓取另加两条：**必须先二次确认**（会顶号，`D9`）· 且走真端点（原先是假 toast）。
    ⚠️ 手工新增的项目键 = **仓库名**（§2.7.4），⛔ 不是 `project_id`（列表接口也不给 id）。
    """
    s = _sh()
    assert "async function jcAct" in s, "写动作要有统一外壳（照 `awfAct`：成败都回后端真实状态）"
    for frag in ("API.m11Tag({id:j.id, tag:t.dataset.v})",     # 单条标记
                 "API.m11Tag({ids, tag:v})",                    # 批量标记
                 "API.m11Fields({id:j.id, fields:{method:t.value}})",   # 付款方式（自由文本）
                 "fields:{arch:next}",                          # 存档推进
                 "API.m11Add({"):                               # 手工新增
        assert frag in s, f"动作没接上 API：{frag}"
    assert "project_key:jcND.pj" in s, "手工新增要传 `project_key`（仓库名），⛔ 不是 project_id"
    assert "API.m11Fetch(" in s and "jcFetchOk" in s, "抓取要走 `POST /api/m11/fetch`"
    # ⭐ `M5-6`（2026-09-20）：抓取弹窗要能设「**开始日期**」（增量）——
    #    实测全量 40.4 秒 vs 增量 1~5 秒（i8 的耗时与命中条数成正比）⇒ ⛔ 不能只剩"全量"一条路。
    assert "jcFetchSince" in s, "抓取要能设「开始日期」（增量），⛔ 不能只支持全量"
    assert "这一步会登录 i8" in s, "抓取前必须讲清会顶号（D9）"
    assert "jcFetchPreview" in s, "抓取回执要展示**匹配预览**（否则漏匹配会被静默埋掉）"
