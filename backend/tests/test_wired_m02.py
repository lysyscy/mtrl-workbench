"""`m02`（i8 接入层）**前端壳接线**断言（离线 · 静态）。

**这一页接的是什么**：原型里两张卡都是假的 —— 「抓取结果回显」读的是**演示数组**
（`WHs`/`JCs` 本身就是演示数据 ⇒ 显示出来是假话）、「抓取任务日志」是**8 行硬编码**。
接线后两张卡的**唯一数据源 = 执行记录**（`/api/m02/fetch/records`）。
另外两个「同步」按钮（`API-05`/`API-06`）原先只弹「尚未接通」⇒ 现在真发请求，
但**必须**先过 `D9` 那道闸（会强踢在线用户 ⇒ 二次确认之后才允许 `allow_kick=true`）。

⚠️ **本文件测不了什么**：这些是**静态检查**（壳里有没有那些接线点），**不证明运行时真的调通**；
   运行时那一段由壳真机自检（`tools/probe/_shell_smoke.py` 的 `m02` 段）覆盖。
   ⚠️ 两个同步**永远不会**进自动自检 —— 它们会**真登录 i8 并顶号**（`D9`）⇒ 只许人工点击。

⭐ 其中三条是**反向**断言：不许再拿演示数组当回显 · 不许对没落点的接口假装成功 ·
   不许绕开二次确认把 `allow_kick=true` 发出去。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

from tests.shell_src import (  # noqa: F401  ← `P4`① 读取点收敛
    SHELL, act_entry, bind_block, const_src, func_body,
)

# ⭐ 2026-10-03（`TAIL-219` 批 2b）：本件原先自带剪刀 `_fn`（"标记 A → 标记 B"）——
#    已**整把删掉**，取段改走壳的语义口径（函数 ⇒ `func_body` · 动作条 ⇒ `act_entry` ·
#    `BIND` 块 ⇒ `bind_block` · 常量整句 ⇒ `const_src`）。⛔ 别写回来。


# --------------------------------------------------------------- 接线点（正向）


@acc()
def test_壳把m02标为已接后端并指向真实端点():
    """`WIRED` 含 `m02`，且壳里真的出现该模块的端点。"""
    assert "'m02'" in SHELL[SHELL.index("const WIRED=new Set("):][:120], "`WIRED` 没含 m02"
    assert "/api/m02/fetch/records" in SHELL, "执行记录端点没接"
    # ⚠️ 2026-09-19（性能 `P2`）：`boot()` 分组并行 ⇒ 形态从 `await soft(...)` → 组内 `soft(...)`（判据不变）
    from tests.shell_load_helpers import loaders as _loaders   # noqa: PLC0415
    assert "async function reloadM02()" in SHELL and "i8 执行记录" in _loaders(), \
        "`boot` 里要独立一路（一路失败不许拖垮别页）"


@acc("ACC-I8-FETCH-001", "001-09")
def test_执行记录写完就刷且进页不被缓存住():
    """⚠️⚠️ 用户 2026-09-20 实测：「**执行记录并不会自动刷新**」。

    真因**两条叠加**（只修一条仍有缝）：

    ① `P3` 的 `LOADED` 缓存口径是「同一页反复进出**不重复拉**」—— 对**台账页**正好是错的：
       「i8 执行记录」的内容**由别的动作产生**（抓取 / 同步 / 批量打印 / 只导出 PDF
       都往 `run_record` 写一条），用户看这一页**就是要看"刚刚那次跑完没"**
       ⇒ 缓存住的必然是**旧**的（在用户眼里就是假话）。
       ⇒ 它进 `ALWAYS_FRESH`：**每次进页都重拉**（一次 50 条的 GET，代价可忽略）。
    ② 人**已经站在 `m02` 上**、从这页点「触发」抓完 ⇒ 不会有人再 `go('m02')`
       ⇒ 得**写完就地刷**（`reloadM02IfOn()`；不在 m02 页时**不发请求**，切回来由 ① 兜住）。

    ⚠️ 三个抓取入口的**成功 / 降级 / 抛异常**三条路**都要刷** —— 它们**都写了**一条执行记录
       （后两条尤其容易漏：界面上一句"没能完成"很容易被当成"什么都没发生"）。
    """
    fresh = const_src("ALWAYS_FRESH")
    assert "'i8 执行记录'" in fresh, \
        "「i8 执行记录」没进 `ALWAYS_FRESH` ⇒ 切回 m02 看到的还是旧记录（缓存住了）"
    assert "ALWAYS_FRESH.has(l)" in func_body("loadPaths"), \
        "`loadPaths` 没认 `ALWAYS_FRESH`（那它就只是个摆设）"

    for fn in ("ntFetchBackend", "whFetchBackend", "ivFetchBackend"):
        body = func_body(fn)
        n = body.count("reloadM02IfOn()")
        assert n >= 3, (
            f"`{fn}` 只在 {n} 处刷了执行记录 —— 成功 / 降级 / 抛异常**三条路都要刷**"
            "（它们都往 `run_record` 写了一条）")


@acc("ACC-I8-FETCH-001", "001-07")
def test_回显与任务日志同源于执行记录():
    """⭐ 001-07：**执行记录**是这两张卡的唯一数据源（原型是演示值 / 硬编码行）。

    - 「抓取结果回显」= 每类接口在记录里**最近一次**的结果（6 行都走同一个出口）；
    - 「抓取任务日志」= 记录本身（时间 / 接口 / 结果 / 耗时 —— 后两项由适配层算，⛔ 后端不为它加字段）；
    - 两者都读 `M02_RECS`（同一次取数），⛔ 不各自去要一次（防两份快照打架）。
    """
    assert "let M02_RECS = [];" in SHELL and "M02_RECS = (recs || []).map(" in SHELL
    assert "function m02EchoKv()" in SHELL and "function m02LogRows()" in SHELL
    echo = func_body("m02EchoKv")
    log = func_body("m02LogRows")
    latest = func_body("m02Latest")
    assert "m02Latest(" in echo, "回显卡要走「按接口取最近一次」那个出口"
    assert "M02_RECS" in latest and "M02_RECS" in log, "两张卡必须读同一份记录（`M02_RECS`）"
    assert SHELL.count("API.m02Records") == 1, "只许一处取数（⛔ 别两张卡各取一次）"


@acc("ACC-I8-FETCH-001", "001-07")
def test_两张卡由渲染后注入且切片一行未改():
    """⭐ 为什么走 `BIND.m02`：切片是**逐行对位**核对的，删一行就会让后面全部报漂移
    ⇒ 结构化替换一律放「渲染后注入」（`BIND.m01` 那两张卡同款）。

    ⚠️ 卡片里那句「（模拟）」在切片里**已改准并登记**（`ui_parity_expected.txt` 的 `m02` 行）——
       那是**唯一**一处显式偏离（`ui_parity` 的 `U1` 当场看得见）。
    """
    bind = bind_block("m02")
    assert "kv.innerHTML = m02EchoKv();" in bind, "回显卡没接真数据"
    assert "tb.innerHTML = m02LogRows();" in bind, "日志卡没接真数据"


# --------------------------------------------------------------- 同步（D9 那道闸）


@acc("ACC-PRJ-SYNC-001", "001-10")
def test_同步先二次确认才允许强踢():
    """⭐ `D9`：两个同步都会**登录 i8 并强踢该账号在线用户** ⇒ `allow_kick=true` **只许**在
    用户二次确认之后发出去（先把闸摆好，再谈调用）。

    ⚠️ 三层看住：① 端点 URL 里带 `allow_kick=true`（后端也要求显式授权）；
       ② 那个 URL **只在** `m02SyncOk`（＝确认按钮的处理函数）里被引用；
       ③ 确认弹窗里**必须写明会顶号**（⛔ 不许悄悄踢人）。
    """
    assert "m02SyncWh: () => API.post('/api/m02/sync/warehouses?allow_kick=true'" in SHELL
    assert "m02SyncPj: () => API.post('/api/m02/sync/common-projects?allow_kick=true'" in SHELL
    # ⚠️ 段的**起止**：`m02SyncOk` 在后面（`syncWh` 在前）⇒ 终点要用它之后那节的开头，⛔ 不能拿 `syncWh` 当终点
    confirm = act_entry("m02SyncOk")
    assert "API.m02SyncWh()" in confirm or "API.m02SyncPj()" in confirm, \
        "确认之后才发请求（⛔ 别在弹窗打开时就发）"
    dlg = func_body("m02Sync")
    assert "强制踢掉" in dlg and "data-act=\"m02SyncOk\"" in dlg, "确认弹窗没讲清会顶号"
    # ⛔ 反面：不许在别处直接打这两个端点（绕开确认弹窗）
    assert SHELL.count("API.m02SyncWh()") + SHELL.count("API.m02SyncPj()") == 2, \
        "两个同步端点各只许有一处调用方（且必须在确认处理函数里）"


@acc("ACC-PRJ-SYNC-001", "001-10")
def test_同步回执与降级一律原样转述且刷新相关页():
    """⭐ 001-10（回执给计数 · 禁静默）＋ §3.6（降级必须显式说明）：

    - 成功 ⇒ 把后端那句中文回执**原样**转给用户（⛔ 不换句话、不吞）；多仓库待人工还要指路 `m01`；
    - 降级 ⇒ 明说「i8 侧不可用、**未改动本地档案**」；
    - 「常用项目列表」会**真的建档** ⇒ 顺手刷新档案与「待人工建档」卡（`TAIL-45`）。
    """
    confirm = act_entry("m02SyncOk")
    assert "r.degraded" in confirm and "未改动本地档案" in confirm, "降级没说清（会让人以为同步过了）"
    assert "esc((r&&r.message)" in confirm, "回执要原样转（⛔ 不换句话）"
    assert "reloadM02()" in confirm, "同步完要刷新执行记录（回显与日志跟着变）"
    assert "reloadProjects()" in confirm, "常用项目列表会建档 ⇒ 档案与待人工建档卡要跟着刷"
    assert "待人工建档" in confirm, "有待人工的要去 m01 处理 —— 回执里要指路"
    # ⭐⭐ 2026-09-29（`TAIL-190` 用户真机报障）：「待人工」里**混着两类、出路不同** ⇒
    #    回执必须**按类别把「去哪」说清**：多仓库 ⇒ `m01` 那张卡；壳下小微 ⇒ **建档向导**
    #    （它按设计**根本不在卡上**）。⚠️ 报障形态 = 回执一句"去 m01 的卡"，而用户到那儿看到的是**空卡**。
    assert "ct.manual_multi" in confirm and "ct.manual_shell" in confirm, \
        "回执没按出路分两类 —— 用户会照着一句话跑去 m01 看空卡（报障就是这个）"
    assert "建档向导" in confirm, "「壳下具体小微」那类没指去建单向导（它不进 m01 那张卡）"
    assert "一个全名挂多个仓库" in confirm, "多仓库那类照旧要指 m01（这一半本来就对，⛔ 别改坏）"
    assert "需人工选定 —— 去" not in confirm, \
        "老的「一律指 m01」那句写法又回来了（它正是让用户看空卡的原因）"


# --------------------------------------------------------------- 反向（三条）


@acc("ACC-I8-FETCH-001", "001-07")
def test_纯年月的执行记录也算付款通知书():
    """⭐ 真机实测踩到的**假话**（2026-09-18）：付款通知书那条链路的记录 `target` **只写年月**
    （`mod03_notice/router.py` 里 `target=year_month`）⇒ 映射若只认「付款通知书」四个字，
    回显卡就会对**已经抓过**的付款通知书说「还没有执行记录」。

    ⚠️ 反过来也要看住：**认不出的一律不猜**（走原文），⛔ 别把别的记录硬塞给某一类。
    """
    isif = func_body("m02IsIf")
    assert "bare_month" in isif and "/^\\d{4}-\\d{2}$/" in isif, "纯年月那条判据没写"
    assert "付款通知书" in SHELL and "bare_month: true" in SHELL
    label = func_body("m02LabelOf")
    # ⚠️ 2026-09-20：断言从"钉旧写法的字面"（原先是 `it ? … : r.target`）改成**钉意图** ——
    #    用户要求「里面显示的**接口名不直观**，换成直观的」⇒ 抓取接口改成「名字（型号）」，
    #    并且要给**打印 / 只导出 PDF** 那两类也补一层人话映射。
    assert "M02_IFACES.find" in label, "抓取接口仍要认得出（走正常映射）"
    assert "return r.target" in label, "认不出的要走原文（⛔ 不猜成某一类）"
    # ⭐ 打印 / 导出**不在 `M02_IFACES` 里**（那是"抓取接口"清单）⇒ 必须另给人话，
    #    否则 fallback 成 `r.target` = **一长串单号**、界面上看不出这是什么（用户实测反馈）。
    assert "print" in label and "export_pdf" in label, \
        "打印 / 只导出 PDF 的记录要给人话标签（⛔ 别把一长串单号直接摆在格子里）"


@acc()
def test_反向_不再拿演示数组当回显():
    """⛔ 原型那 6 行读的是 `NO`/`WHs`/`IVs`/`JCs`/`PJs` —— 其中 `WHs`/`JCs` **本身就是演示数组**
    （`WHs` 归 m07 的演示、`JCs` 归集采域的原型页）⇒ 接线后**必须**由 `BIND.m02` 就地换成真数据，
    否则页面上写的就是假话（"抓过 675 行"而库里的数由用户在别页看）。
    """
    bind = bind_block("m02")
    assert "kv.innerHTML = m02EchoKv();" in bind, "回显卡没被真数据覆盖 ⇒ 演示值会露给用户"


@acc()
def test_反向_没落点的接口不许假装成功():
    """⛔ `API-04 采购合同信息` 属**集采域（M5，未开工）** ⇒ 壳里必须**如实说未接通**，
    并且**不得**出现它的抓取端点调用（原型那句「已触发抓取（模拟）→ 成功」正是要删的假话）。
    """
    act = act_entry("fetchOne")
    # ⚠️ 按**代码**认，⛔ 不按整段文本认 —— 上面那句解释里就写着 `API-04`（本仓实测踩过：
    #    「断言被自己的文档注释喂饱」）。
    assert "api==='API-04'" not in act and "tt==='采购合同信息'" not in act, \
        "别给没落点的接口编一条抓取分支"
    assert "集采域" in act and "尚未接通" in act, "没落点的接口要说清为什么，⛔ 不许假装成功"
    assert "（模拟）" not in act, "原型的「（模拟）→ 成功」是最典型的假话，必须删干净"


@acc()
def test_反向_降级路径指向真入口而不是假上传():
    """⛔ 「手动导入」不许演一个不存在的上传控件：有对应导入页的（`m07`/`m08`/`m06`）
    **把人送过去**（真入口，与抓取同一套管线）；没有的**如实说未接通**。
    """
    up = act_entry("manualUp")
    assert "go(k)" in up, "有入口的要真跳过去（⛔ 只弹一句话等于没接）"
    assert "'m07':'m08'" in up or ("'收发结存表':'m07'" in up and "'库存单据明细表':'m08'" in up)
    assert "尚未接通" in up, "没有入口的要如实说（⛔ 不演示假上传）"
