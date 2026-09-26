"""`ACC-JC-FETCH-001` · **壳侧**（抓取入口 / 三态批量勾选）的验收断言。

⚠️ 与 `test_acc_jc_fetch.py`（**库级**：落库 / 幂等 / 不覆盖）分工：本文件只钉**页面形态**。
⚠️ 逐条对应（claim 原文见验收基线）：
   - `001-01` 触发方式写明「人工点击 + 定时自动（一期启用）」，且执行记录含**定时自动**那一条
   - `001-02` 抓取入口打开「**按月抓取**」弹窗（与其它接口入口行为一致）；**无抓取交互的接口**仍走提示
   - `001-04` 未勾选时批量按钮**先禁用**（⛔ 不是点了才拦）
   - `001-06` 全选范围 = **当前筛选结果**；筛选收紧后勾选**被裁剪**
"""

from __future__ import annotations

import pathlib
import re

import app
from tests.acc_plugin import acc


def _index() -> str:
    return (pathlib.Path(app.__file__).resolve().parent / "web" / "index.html").read_text(encoding="utf-8")


def _actions() -> str:
    return (pathlib.Path(app.__file__).resolve().parent / "web" / "shell" / "actions.js").read_text(encoding="utf-8")


def _all_shell() -> str:
    """**整支壳**（`index.html` ＋ `core.js` ＋ `actions.js`）拼起来。

    ⚠️ 判"某个函数有没有被调用"必须用**整支** —— 定义在 `index.html`、调用却散在
       `actions.js` 与 `core.js` 里（`pruneJcPick` 就是：定义 1 处、调用 8 处）。
       ⛔ 只搜一个文件会得出"定义了没调用"的**假结论**（我第一版就这么误判了）。
    """
    d = pathlib.Path(app.__file__).resolve().parent / "web"
    return "\n".join([
        (d / "index.html").read_text(encoding="utf-8"),
        (d / "shell" / "core.js").read_text(encoding="utf-8"),
        (d / "shell" / "actions.js").read_text(encoding="utf-8"),
    ])


def _fn(src: str, anchor: str, end: str) -> str:
    i = src.index(anchor)
    return src[i:src.index(end, i)]


@acc("ACC-JC-UI-001", "001-03")
def test_空态行跨列数派生且全选框回显三态():
    """claim：「**筛选无结果时必须给空态提示行**（跨列数 = 表头列数）；
    **表头全选框必须回显状态**（全选 → 勾选，取消一行 → 半选）」。

    ⚠️ 两半都要钉，而且都有"最容易偷懒"的写法：
       ① 空态行的 `colspan` **必须由表头派生**（`thCount(JC_THEAD)`）—— ⛔ 写死一个数字，
          表头一改列就错位（多一块/少一块），而且**空态时才看得见** ⇒ 平时测不出来；
       ② 全选框**要有三种态**：全选中 → `checked`；部分选中 → `indeterminate`（半选）；
          一个没选 → 都不是。⛔ 只做 `checked` 的话，用户筛了一半勾选时看不出"还差几条"。
    """
    html = _index()
    empty = [ln for ln in html.splitlines() if "当前筛选条件下没有集采合同" in ln]
    assert empty, "找不到集采台账的空态提示行 —— 落点变了"
    assert "colspan=\"${thCount(JC_THEAD)}\"" in empty[0], (
        "空态行的跨列数**没有由表头派生** —— ⛔ 写死的数字在表头改列后会错位，"
        "而且只有「筛到空」时才看得见：\n  " + empty[0].strip()[:160])

    bind = _fn(html, "BIND.m11=", "/* ====")
    assert "box.checked" in bind and "hit===vis.length" in bind, (
        "全选框的 `checked` 不是「全中」才勾 —— 那会出现「勾着的其实没全选」")
    assert "box.indeterminate" in bind and "hit>0" in bind, (
        "全选框**没有半选态**（`indeterminate`）—— 取消一行后它会显示成「完全没选」，"
        "用户看不出「其实还选中了别的」")


@acc("ACC-JC-UI-001", "001-07")
def test_付款子表日期默认系统当日且草稿可改():
    """claim：「**付款子表**录入日期默认取**系统当日**，且**草稿可改**」。

    ⚠️ 三条容易做错的地方，一条一条钉：
       ① **只有付款子表**默认当日 —— 发票侧（`inv`/`tinv`）**必须留空**：
          「发票日期必填」是有意的（⛔ 替用户填一个默认值等于**帮他做了一个该他自己做的判断**）；
       ② 默认值**不许写死日期字面量** —— 必须取"今天"那个变量（正式实现换系统日期即可）；
       ③ 草稿**可改**：改了要进**草稿层**（`jcSubD`），⛔ 不是改完就当落库。
    """
    acts = _actions()
    add = _fn(acts, "jcSubAdd:", "jcSubSet:")
    assert "kind==='pay'?SYS_TODAY:''" in add.replace(" ", ""), (
        "付款子表的默认日期不是「只有 pay 才给当日、发票侧留空」这个形态 ——\n"
        "  ⚠️ 发票日期是**必填**（该用户自己判断归哪个月），⛔ 别替他填默认值。\n"
        f"  实际：{add.strip()[:180]}")
    assert "SYS_TODAY" in add and "'2026-" not in add, (
        "默认日期里出现了**写死的日期字面量** —— 必须取「今天」那个变量"
        "（正式实现只换它的取值，⛔ 不许在业务代码里埋死日期）")

    # ⚠️ `jcSubSet` 是 `ACT` 上的**动作**（`jcSubSet:t=>{…}`），⛔ 不是 `const jcSubSet=`
    m = re.search(r"jcSubSet:t=>[^\n]*", acts)
    assert m, "找不到 `jcSubSet`（写草稿层的动作）—— 落点变了"
    assert "jcSubD" in m.group(0), (
        "`jcSubSet` 没有写**草稿层** `jcSubD` —— 那用户改的那一格要么丢了、要么直接落库了，"
        "两种都不对（草稿就该只在草稿层）")


@acc("ACC-JC-UI-001", "001-08")
def test_子表草稿行列对齐且钉在合计行之前取消不入库():
    """claim：「子表草稿行**列对齐**并**钉在「数据行之后、合计行之前」**；
    **取消 = 草稿丢弃不入库、增行态复位**」。

    ⚠️ 「钉在…之前」这句在本壳里是**两层**保证（缺一层，排序一开就乱）：
       ① **渲染顺序**：草稿行就写在数据行与合计行**之间**；
       ② **行级 `draftrow`**：它并入排序的 pin 通道（钉表尾、不参与排序）——
          ⚠️ 没有②的话，用户一点表头排序，草稿行就会被排走、合计行窜到它前面。
    ⚠️ 「取消不入库」要**反向**钉：`jcSubCancel` 那段里**不许出现任何落库调用**。
    """
    html = _index()
    for dlg, table in (("jcInvDlg:", "modal:jcInv"), ("jcTInvDlg:", "modal:jcTInv"),
                       ("jcPayDlg:", "modal:jcPay")):
        seg = _fn(_all_shell(), dlg, "jcSubAdd" if dlg == "jcPayDlg:" else "＋ 增加一张发票</button>")
        i_rows = seg.index(".map((v,i)") if ".map((v,i)" in seg else seg.index(".map((p,i)")
        i_draft = seg.index("jcSubRow()")
        i_sum = seg.index("sumRowOf(")
        assert i_rows < i_draft < i_sum, (
            f"`{dlg}`（{table}）里三段的顺序不对 ⇒ 草稿行没有钉在「**数据行之后、合计行之前**」。"
            f"\n  实际位置：数据行 {i_rows} / 草稿行 {i_draft} / 合计行 {i_sum}")

    row = _fn(html, "const jcSubRow=", "/* MOD-11 集采台账的表头")
    assert 'class="draftrow"' in row, (
        "草稿行没有 `draftrow` 这个类 ⇒ 它**不会被 pin 到表尾**：用户一点表头排序，"
        "草稿行就会被排走、合计行窜到它前面（「钉在合计行之前」就破了）")
    assert row.count("<td") == row.count("</td>"), "草稿行的 `<td>` 没有闭合（列会错位）"
    for branch, want in (("jcSubKind==='pay'", 4), ("return `<tr class=\"draftrow\"><td class=\"fc\">新增</td>", 4)):
        assert branch in row, f"找不到草稿行的这个分支：{branch[:40]!r}"
    assert "jcSubD" in row, "草稿行的输入框没有接到草稿层 `jcSubD`"

    cancel = _fn(_actions(), "jcSubCancel:", "/* 子表增行")
    assert "jcSubReset()" in cancel, "取消后**没有复位增行态**（`jcSubReset`）⇒ 草稿行会一直挂着"
    assert "API." not in cancel and "jcAct(" not in cancel, (
        "`jcSubCancel` 里出现了落库调用 —— **取消 = 草稿丢弃、不入库**，⛔ 一个字节都不该写进去")
    assert "未写入任何数据" in cancel, "取消的提示没有明说「未写入任何数据」（用户得知道确实没落库）"


@acc("ACC-JC-UI-001", "001-14")
def test_筛选栏控件齐备且项目是第一个():
    """claim：「筛选栏控件齐备（**项目 / 三态 / 存档 / 供应商 + 重置**），
    且「**项目**」是**本页第一个控件**、走**多选面板**」。

    ⚠️ 「项目是第一个控件」不是排版喜好：项目是**业务范围**（先定范围再看别的），
       而且它在这一页是**多选**（与别的页的单选项目控件**不是一个形态**）⇒ 两件都要钉。
    """
    html = _index()
    bar = _fn(html, '<div class="fbar">', '${jcNewOn?jcNewStrip()')
    order = [k for k in ("jcPjToggle", "id=\"fTag\"", "id=\"fArch\"", "id=\"fSup\"", "jcReset")
             if k in bar]
    assert len(order) == 5, f"筛选栏控件不全（缺 {set(['jcPjToggle','fTag','fArch','fSup','jcReset']) - set(order)}）"
    assert order == ["jcPjToggle", "id=\"fTag\"", "id=\"fArch\"", "id=\"fSup\"", "jcReset"], (
        "筛选栏控件顺序变了 —— 「**项目**」必须是**第一个**（它定的是业务范围）；实际顺序：" + str(order))
    assert "jcPjPanel()" in bar, "「项目」没有走**多选面板**（`jcPjPanel`）—— 与本页「项目可多选」的口径不符"
    assert "可多选" in bar, "「项目」控件的标签没写明「可多选」"


@acc("ACC-JC-FETCH-001", "001-01")
def test_触发方式写明且执行记录含定时自动那条():
    """claim：「**触发方式写明**「人工点击 + 定时自动（一期启用）」，且**执行记录含定时自动触发那一条**」。

    ⚠️ 两半都要钉，而且**要钉在对的接口上**：
       ① 「定时自动」这句是**集采合同（`API-04`）**的口径（§6.4 / 技术栈 `OPEN-T9`）——
          ⛔ 不能"随便哪个接口写了就算"，否则别的接口写一句同一句话就能骗过断言；
       ② 执行记录里要**真的有一条**「定时自动触发」的记录行（⛔ 只有说明文字、没有记录行不算）。
    """
    html = _index()
    api04 = next((ln for ln in html.splitlines() if "'API-04'" in ln), None)
    assert api04, "API 清单里找不到 `API-04`（采购合同信息）这一行 —— 落点变了"
    assert "人工点击 + 定时自动（一期启用）" in api04, (
        "`API-04` 那一行没写明触发方式「人工点击 + 定时自动（一期启用）」——\n"
        f"  实际那一行是：{api04.strip()[:160]}")
    assert "定时自动触发" in html, (
        "执行记录里没有**定时自动触发**那条记录 ⇒ 页面只说了「会定时」，却拿不出跑过的凭据"
        "（claim 后半句要求「执行记录**含**定时自动触发那一条」）")


@acc("ACC-JC-FETCH-001", "001-02")
def test_抓取入口统一走按月抓取_没有落点的如实提示():
    """claim：「抓取入口打开「**按月抓取**」弹窗（**与其它接口入口行为一致**）；
    **无抓取交互的接口**仍走模拟提示」。

    ⚠️ 「行为一致」在这个壳里 = 三个真入口（`API-01`/`02`/`03`）**都**走到各自那个
       「按月抓取」弹窗，⛔ 不许有谁落回一句 toast 就完事（那样同一个"触发"按钮点下去行为不同）。
    ⚠️ 兜底那句**必须如实**（"尚未接通 / ⛔ 不假装成功"）——
       ⛔ 兜底里出现"模拟成功"这类字样就等于**在骗用户**（claim 里"模拟提示"指的是
       **没有抓取交互**的接口，不是"假装抓成功"）。
    """
    body = _fn(_actions(), "fetchOne:", "manualUp:")
    for api, handler in (("API-01", "fetchNt"), ("API-02", "fetchWh"), ("API-03", "fetchIv")):
        assert api in body and handler in body, (
            f"`fetchOne` 没有把 `{api}` 分派到 `{handler}` —— 三个真入口的行为会不一致")
    for api, handler in (("API-05", "m02Sync"), ("API-06", "m02Sync")):
        assert api in body and handler in body, f"`fetchOne` 没有把 `{api}` 分派到真同步 `{handler}`"
    assert "尚未接通" in body, (
        "`fetchOne` 的兜底没写「尚未接通」这类如实提示 —— 无抓取交互的接口会被静默吞掉")
    assert "不假装成功" in body or "⛔" in body, "兜底提示要**如实**（明说没接通），⛔ 不许含糊过去"


@acc("ACC-JC-FETCH-001", "001-04")
def test_批量标记按钮未勾选时先禁用():
    """claim：「**未勾选时批量按钮先禁用**（⛔ **不是点了才拦**）」。

    ⚠️ 「先禁用」和「点了再拦」是**两件不同的事**：后者用户会先点一下、被拒一次，才知道要勾选。
       ⇒ 判据必须钉在**按钮标签本身**（`disabled`）上，⛔ 不能只看 handler 里有没有那句拦截
       （handler 里的拦截是**第二道**保险，两者**都要有**，但**只有前者**满足 claim）。
    """
    html = _index()
    tags = re.findall(r"<button[^>]*data-act=\"jcBatchTag\"[^>]*>", html)
    assert tags, "找不到批量标记按钮（`data-act=\"jcBatchTag\"`）—— 落点变了"
    for tag in tags:
        assert "disabled" in tag, (
            "这个批量标记按钮**没有「先禁用」**（标签里没有 `disabled`）⇒ 用户会先点一下被拒，"
            f"才知道要先勾选：\n  {tag[:150]}")
        assert "jcPick.size?" in tag, (
            "批量按钮的 `disabled` 不是跟着**勾选数**走的 ⇒ 禁用条件大概接错了对象：\n"
            f"  {tag[:150]}")
    # ⚠️ `#2`（2026-09-26）起 `CHG=` 那个结束标记**已不存在**（名单拆了）⇒ 改用紧随其后的「事件委托」段注释。
    body = _fn(_actions(), "jcBatchTag:", "/* 事件委托")
    assert "if(!jcPick.size)" in body, (
        "handler 里少了第二道保险（点了也要拦）—— 按钮禁用是「先禁用」，"
        "但**状态可能被外部改动**，两道都要在")


@acc("ACC-JC-FETCH-001", "001-06")
def test_全选只作用于当前筛选结果且收紧后被裁剪():
    """claim：「**全选范围 = 当前筛选结果**；**筛选收紧后勾选被裁剪，不越界**」。

    ⚠️ 两半：
       ① 全选**只**勾"当前可见"（= 筛选结果）—— ⛔ 不是全量：否则用户筛了"甲仓"再点全选，
          会把**看不见的**行也勾上，之后批量标记就**越界**改了没看见的行；
       ② 筛选**收紧**（可见集变小）后，已经勾上、但现在看不见的行必须**被裁掉**。
       ⚠️ ②尤其要紧：不裁的话"全选 → 改筛选 → 批量标记"会改到**屏幕上根本不存在**的行。
    """
    html = _index()
    acts = _actions()

    # ① 全选 = 当前可见（筛选结果），⛔ 不是全量
    assert "jcVisible()" in _fn(acts, "jcPickAll:", "jcBatchTag"), (
        "全选没有走 `jcVisible()`（= 当前筛选结果）—— 那它勾的就是**全量**，"
        "筛了「甲仓」再点全选会连看不见的行一起勾上，之后批量标记就改了屏幕上没有的行")

    # ② 筛选收紧后裁剪：`pruneJcPick` 拿 `jcVisible()` 做差集，且**真的被调用**
    i = html.index("const pruneJcPick=")
    pruned = html[i:i + 420]                     # ⚠️ 按固定窗口取本行即可：
    assert "jcVisible()" in pruned, (            #    ⛔ 别拿"后面的某个声明"当终止标记 ——
        "`pruneJcPick` 没有拿 `jcVisible()` 做差集 —— 筛选收紧后勾选不会被裁剪，"  # 那可能在它**前面**
        "批量标记会越界改到屏幕上看不见的行")
    assert _all_shell().count("pruneJcPick()") >= 4, (
        "`pruneJcPick()` 的调用点太少 ⇒ 有些筛选变化后根本不会裁剪"
        "（⚠️ 必须搜**整支壳**：定义在 `index.html`、调用散在 `actions.js`/`core.js`）")
