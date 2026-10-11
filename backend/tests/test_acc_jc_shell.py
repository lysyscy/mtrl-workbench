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
from functools import lru_cache

import app
from tests.acc_plugin import acc
from tests.shell_src import SHELL   # ⚠️ 壳源码的唯一出口（⛔ 别直接读 index.html）
# ⚠️ 抹注释（`_fn` 用）：`tools.audit.jslex` 是**同长**那一支（换行/偏移不变）；⛔ 别改成删字符那支
from tools.audit.jslex import blank_comments


def _index() -> str:
    """⚠️ 2026-09-28（`TAIL-164` · `P2-a` 拆件）：本函数**不再"只看 `index.html`"** —— 壳已是多件
    （`base/view/ui/proj/pages-a/pages-b.js` ＋ 原有 5 件），本件各用例干的事都是"**在整支壳里找某一段**"，
    拆件后那些段可能住在 `shell/*.js` ⇒ 一律返回**合并后的壳**（判据内容一字未改，只换取材方式）。
    ⭐ 本仓纪律：壳源码只从 `tests.shell_src` 取，⛔ 别绕过它读单件（那也是 `P4`① 收敛读取点的本意）。
    """
    return SHELL


def _actions() -> str:
    return (pathlib.Path(app.__file__).resolve().parent / "web" / "shell" / "actions.js").read_text(encoding="utf-8")


def _all_shell() -> str:
    """**整支壳**拼起来（＝ `shell_src.SHELL`：`index.html` ＋ 全部 `web/shell/*.js`，顺序 = `<script src>` 顺序）。

    ⚠️ 判"某个函数有没有被调用"必须用**整支** —— 定义在一件、调用却散在另几件里
       （`pruneJcPick` 就是：定义 1 处、调用 8 处）。
       ⛔ 只搜一个文件会得出"定义了没调用"的**假结论**（我第一版就这么误判了）。
    ⚠️ 2026-09-28（`P2-a` 拆件）：原先这里**手拼 3 件**（`index.html`＋`core.js`＋`actions.js`），
       拆件后那 3 件之外还有 7 件 ⇒ 手拼表**必然漏**（漏了还会静默得出"没调用"）⇒ 改走唯一出口。
    """
    return SHELL


@lru_cache(maxsize=8)
def _blanked(src: str) -> str:
    """整篇抹注释（**从文档开头**跑 lexer ⇒ 字符串/注释状态才是对的）。

    ⚠️ 2026-10-11（`TAIL-298` 收尾）实测：**拿半截源码**去抹会炸 —— 切片起点若落在标签/属性中间
       （如 `data-…="…"` 之后再没有配对的引号），lexer 会抛「字符串没闭合」。
       ⇒ 一条铁律：**整篇抹一次，再按原文下标切片**（`blank_comments` 等长 ⇒ 两边下标通用）。
    """
    return blank_comments(src, html=True)


def _fn(src: str, anchor: str, end: str) -> str:
    """切出 `[anchor, end)` 那一段 —— ⚠️ 段里的**注释已抹成空格**（等长，行号/偏移不变）。

    ⚠️ 为什么必须抹掉注释：本件好几条断言是**计数式**的（`row.count("<td") == row.count("</td>")` 那类），
       而段原本是**原文**（含注释）⇒ 谁在注释里写一句「手写 `<td>` 串」就会让判据**假红**
       （2026-10-11 真实发生：白跑一整轮按影响入口，见 `TAIL-298` Comments）。
    ⚠️ 下标一律取自**原文**（`src`），取完再回 `_blanked(src)` 上切 —— 因为本件有 `end` 锚点**本身长在
       注释里**（`"/* MOD-09 特殊费用月报表的表头"`）⇒ 抹完就找不到了。
    """
    i = src.index(anchor)
    j = src.index(end, i)
    return _blanked(src)[i:j]


@acc("ACC-JC-UI-001", "001-03")
def test_空态行跨列数派生且全选框回显三态():
    """claim：「**筛选无结果时必须给空态提示行**（跨列数 = 表头列数）；
    **表头全选框必须回显状态**（全选 → 勾选，取消一行 → 半选）」。

    ⚠️ 两半都要钉，而且都有"最容易偷懒"的写法：
       ① 空态行的 `colspan` **必须由表头派生**（`thCount(…)`）—— ⛔ 写死一个数字，
          表头一改列就错位（多一块/少一块），而且**空态时才看得见** ⇒ 平时测不出来；
       ② 全选框**要有三种态**：全选中 → `checked`；部分选中 → `indeterminate`（半选）；
          一个没选 → 都不是。⛔ 只做 `checked` 的话，用户筛了一半勾选时看不出"还差几条"。
    ⭐ 2026-10-11（`TAIL-298`）：跨列数取自**后端列清单现生成的表头**（`jcThead()`）——
       `m11` 那 20 列字面量已从壳里退场（列的唯一主人 = `domain.JC_COLUMNS`）。
    """
    html = _index()
    empty = [ln for ln in html.splitlines() if "当前筛选条件下没有集采合同" in ln]
    assert empty, "找不到集采台账的空态提示行 —— 落点变了"
    assert "EMPTYROW(thCount(jcThead())" in empty[0], (
        "空态行的跨列数**没有由表头派生** —— ⛔ 写死的数字在表头改列后会错位，"
        "而且只有「筛到空」时才看得见：\n  " + empty[0].strip()[:160])
    # ⭐ 2026-09-29（`TAIL-64` P3 余量）：表外壳走统一出口 `TBL`（⛔ 别退回裸 `<table class="dt" …>`）。
    #   ⭐ 2026-10-11（`TAIL-298`）：表头那一项由 `JC_THEAD` 字面量改成 `jcThead()`（按列清单现生成）。
    #   自证 = `tools/mut/_mut_tbl.py` 的 M15 去掉这处委托 ⇒ 必须红。
    assert "TBL({head:jcThead(),key:'m11:jc'," in html, \
        "集采台账表没走统一出口 `TBL`（`TAIL-64` P3 余量），或表头没按列清单现生成（`TAIL-298`）"

    bind = _fn(html, "BIND.m11=", "/* ====")
    assert "box.checked" in bind and "hit===vis.length" in bind, (
        "全选框的 `checked` 不是「全中」才勾 —— 那会出现「勾着的其实没全选」")
    assert "box.indeterminate" in bind and "hit>0" in bind, (
        "全选框**没有半选态**（`indeterminate`）—— 取消一行后它会显示成「完全没选」，"
        "用户看不出「其实还选中了别的」")


@acc("ACC-JC-UI-001", "001-07")
def test_三张子表日期默认系统当日且草稿可改():
    """claim：「**三张子表**（供应商发票 / 贸易公司发票 / 付款）录入日期默认取**系统当日**，且**草稿可改**」。

    ⚠️ 三条容易做错的地方，一条一条钉：
       ① 默认值**与子表种类无关** —— ⛔ 不许再有「只有 pay 给当日、发票侧留空」那种分叉
          （2026-10-10 用户裁定：三张同款；真机那条 `test_发票子表新增草稿默认北京时间当日且可改`
          逐张开弹窗验过，并额外钉住「历史未结金额」仍按**核对截至日**那个例外）；
       ② 默认值**不许写死日期字面量** —— 必须取"今天"那个变量（正式实现换系统日期即可）；
       ③ 草稿**可改**：改了要进**草稿层**（`jcSubD`），⛔ 不是改完就当落库。
    ⚠️ 校验口径**一条没动**：日期仍必填、金额仍须 > 0（`test_acc_jc_write.py` 的落库侧同款判据仍绿）。
    """
    acts = _actions()
    add = _fn(acts, "jcSubAdd:", "jcSubSet:")
    assert "jcSubD={date:SYS_TODAY,amt:''}" in add.replace(" ", ""), (
        "三张子表的默认日期不是同一个「系统当日」—— 发票侧也必须起步当天。\n"
        "  ⚠️ 例外只有一个：「历史未结金额」按**核对截至日**（下一行覆盖），⛔ 别把它也改成当天。\n"
        f"  实际：{add.strip()[:180]}")
    assert "SYS_TODAY" in add and "'2026-" not in add, (
        "默认日期里出现了**写死的日期字面量** —— 必须取「今天」那个变量"
        "（正式实现只换它的取值，⛔ 不许在业务代码里埋死日期）")
    assert "if(kind==='inv'&&jcHistoryDate(j)) jcSubD.date=jcHistoryDate(j);" in add, (
        "「历史未结金额」的核对截至日覆盖没了 —— 那一行的日期含义是结转核对日，不是今天")
    # ⛔ 校验不变：日期必填、金额 > 0 的判据不许顺手放宽
    # ⛔ 校验不变：日期必填、金额 > 0 的判据不许顺手放宽（两条都是全壳唯一的串）
    assert "if(!/^\\d{4}-\\d{2}-\\d{2}$/.test(dt)) return toast(" in acts, "日期必填校验不见了"
    assert "if(badMoney(v,{positive:1})) return toast(" in acts, "金额「必须 > 0」的校验不见了"

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
        i_rows = seg.index("rows:")
        i_draft = seg.index("jcSubRow()")
        i_sum = seg.index("sumRowOf(")
        # ⭐ 2026-09-29（`TAIL-64` A′）：三张子表的**表外壳**也走统一出口 `TBL`（⛔ 别退回裸 `<table …>`）。
        #   ⚠️ 换成 `TBL` 之后，**上面那三段的源码先后顺序一字未变**（`rows:` ⇒ `empty:` ⇒ `sum:` 仍在同一序上，
        #      只是从「模板里的 `${…}` 三段」变成「一次调用里的三个参数」）—— 所以顺序那条判据照旧成立。
        #   自证 = `tools/mut/_mut_tbl.py` 的 M31／M32／M33 去掉这三处委托 ⇒ 必须红。
        assert "TBL({cls:'cond',key:'" + table + "',head:" in seg, (
            f"`{dlg}`（`{table}`）的表没走统一出口 `TBL`（`TAIL-64` A′）")
        assert i_rows < i_draft < i_sum, (
            f"`{dlg}`（{table}）里三段的顺序不对 ⇒ 草稿行没有钉在「**数据行之后、合计行之前**」。"
            f"\n  实际位置：数据行 {i_rows} / 草稿行 {i_draft} / 合计行 {i_sum}")

    row = _fn(html, "const jcSubRow=", "/* MOD-09 特殊费用月报表的表头")
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
    # ⭐ 2026-09-30（`TAIL-64` P4-b）：原先拿 `<div class="fbar">` 当**切片起点**——而筛选栏的**外壳**
    #   已收进统一出口 `FBAR`（全站都走 `${FBAR({body:`）⇒ 那个字面**只在内核里**，会切到**别处**去。
    #   ⇒ 换成**本页稳定且唯一**的锚点（卡头那枚导出的 `data-t`）—— 它在本页筛选栏**之前**，
    #     所以下面那五件控件与「可多选」都仍在切片内（断的意图一字未改）。
    bar = _fn(html, 'data-t="集采台账"', '${jcNewOn?jcNewStrip()')
    order = [k for k in ("jcPjToggle", "id=\"fTag\"", "id=\"fArch\"", "id=\"fSup\"", "jcReset")
             if k in bar]
    assert len(order) == 5, f"筛选栏控件不全（缺 {set(['jcPjToggle','fTag','fArch','fSup','jcReset']) - set(order)}）"
    assert order == ["jcPjToggle", "id=\"fTag\"", "id=\"fArch\"", "id=\"fSup\"", "jcReset"], (
        "筛选栏控件顺序变了 —— 「**项目**」必须是**第一个**（它定的是业务范围）；实际顺序：" + str(order))
    assert "jcPjPanel()" in bar, "「项目」没有走**多选面板**（`jcPjPanel`）—— 与本页「项目可多选」的口径不符"
    assert "可多选" in bar, "「项目」控件的标签没写明「可多选」"


@acc("ACC-JC-FETCH-001", "001-01")
def test_触发方式写明且不许把人工说成自动():
    """claim（**2026-09-27 按后端真相改写**，见下方原委）：「**触发方式要写明**，且界面口径必须与后端一致
    —— 抓取**一律人工点击**（`D9` 本工程无任何定时任务）」。

    ⚠️⚠️ **原委（必读，⛔ 别把这条改回去）**：本点原来的 claim 是
      「触发方式写明『人工点击 ＋ **定时自动（一期启用）**』，且执行记录含**定时自动触发**那一条」，
      观测点是壳里那张**接口清单表 `TASK`**（`index.html`）。三件事在 2026-09-27（`TAIL-117` 批次 7）同时暴露：
        ① 那张表**零引用**（`m02` 的两张卡 2026-09-20 起改读**执行记录**真数据）⇒ 它**从不上屏**
           ⇒ 这条 claim 过去是**假绿**（钉在一段没人渲染的代码上）；
        ② 后端口径是**用户 2026-09-19 的裁定**：「抓取**只做人工点击**（**无定时**；与 `D9` 一致）」
           （`app/mod11_jc/fetch_service.py` 文件头 ＋ `app/mod02_i8/fetch_task.py::MANUAL_ONLY`）；
        ③ 而界面上却写着「一期启用『定时自动』· 系统每天自动跑一次」⇒ **说了不做的话**（守则 §4 最高优先级）。
      ⇒ 本批：删掉那张不上屏的死码表、把界面文案订正成后端的真相，判据改成钉**这两件**。
    ⭐ **用户 2026-09-27 就 `TAIL-125` 拍板选 ①（改契约面文字）⇒ 已同批改齐**：
       `PRD/验收/验收基线.json` 的 `criterion` 与 `001-01` 的 claim 都改成人工口径（改前备份在
       `.codebuddy/backups/交付面-*/`）＋ `PRD/验收/用例索引.md` 补了变更说明 ＋
       `PRD/02-功能规格/MOD-11.md` 的同一句话同批订正。
       ⚠️ 所以本条判据现在与**基线文字一致**（不再有"判据改了、基线没改"那种悬空）。
    """
    html = _index()
    # ① 界面**必须**写明"抓取一律要人点 / 没有定时任务"（这条口径在 `V.m02` 的口径说明里，真的上屏）
    assert "抓取一律要人点" in html and "本系统没有任何定时任务" in html, (
        "界面没有写明「抓取一律人工、无定时任务」—— 用户会把该抓的活放着不管（以为系统会自己跑）")
    # ② ⛔ 不许再把"定时自动"说成已启用（后端没有定时任务 ⇒ 那是假话）
    assert "一期启用「定时自动」" not in html, "界面又写回「一期启用定时自动」—— 与后端 `D9` 口径矛盾"
    assert "定时自动触发" not in html, "界面又出现「定时自动触发」这条记录 —— 后端不会定时触发"
    # ③ 集采那一处"自动"只允许是「抓完自动同步常用项目列表」（真实存在的那一件）
    assert "自动同步一次常用项目列表" in html, "「抓完自动同步常用项目列表」这句口径丢了"


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


@acc()
def test_甲方单位分类弹窗的表也走统一出口_TBL():
    """`TAIL-64` A′：`modal:jcParty`（甲方单位分类）的表走统一出口 `TBL`。

    ⚠️ 它的**表头原本跨两行**（`<thead><tr>` 与 `<th>…</th>` 分成两行写）⇒ 换 `TBL` 时把表头**并成一串**
       —— 这是「表头跨多行的表别硬搬」那条的一个**例外**：它**没有逐列插值**、只是排版断行，
       并起来**无损**（对照：`mechYm`/`awfTbl` 那种逐列插值的才真属于 `P5` 行模板的活）。
    ⚠️ 空态仍是那个**写死的 3**（`EMPTYROW(3, …)`），本次**不顺手改**它（⛔ 一码归一码）。
    自证 = `tools/mut/_mut_tbl.py` 的 M20 去掉这处委托 ⇒ 必须红。
    """
    acts = _all_shell()
    assert "TBL({cls:'cond',key:'modal:jcParty'," in acts, \
        "甲方单位分类弹窗的表没走统一出口 `TBL`（`TAIL-64` A′）"
    assert "EMPTYROW(3, '还没有甲方记录'" in acts, \
        "那张表的空态行丢了（⚠️ 它的跨列数是写死的 3，不是由表头派生的）"
