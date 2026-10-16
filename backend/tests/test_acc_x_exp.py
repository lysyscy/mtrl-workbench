"""`ACC-X-EXP-001` —— 导出（跨域）12 点。

⚠️ 这 12 点里 **7 点早已有主**（`test_tail04_export.py` 钉 `001-02`/`001-05`；
   `test_path1_weldgas.py` 等钉路径①的 `001-08`~`001-12`）⇒ ⛔ 本文件**不复述**它们，
   只补**还没人验过**的那几点（`001-01` · `001-03` · `001-04` · `001-06` · `001-07`）。
"""

from __future__ import annotations

import pathlib
import re

import app
from tests.acc_plugin import acc
from tests.shell_src import SHELL, tbl_kernel  # noqa: F401  ← `P4`① 读取点收敛


def _shell_dir() -> pathlib.Path:
    return pathlib.Path(app.__file__).resolve().parent / "web"


def _index() -> str:
    return (_shell_dir() / "index.html").read_text(encoding="utf-8")


def _view_slices(html: str) -> dict[str, str]:
    """`V.mXX = …` → 该视图的渲染切片（到下一个视图起点为止）。

    ⚠️ 「页」在这里 = 导航里的视图（`NAV` 的第二列）—— ⛔ 不是"文件"也不是"卡片"，
       否则"逐页都有导出入口"这句话就没法核（页的粒度不定 ⇒ 断言必然写成橡皮尺）。
    """
    starts = [(m.group(1), m.start()) for m in re.finditer(r"^V\.(m\d+)\s*=", html, re.M)]
    out: dict[str, str] = {}
    for i, (k, s) in enumerate(starts):
        e = starts[i + 1][1] if i + 1 < len(starts) else len(html)
        out[k] = html[s:e]
    return out


#: **非数据页** —— 本就不设导出。
#: ⚠️⚠️ 依据 = **用户 2026-09-20 亲口补的原意**：
#:    > 「我当时说所有页面都能导出的**原意，就是所有有数据的页面**，
#:    >   一些非数据页面根本不算在内的」
#: ⛔ **「非数据」≠「页上没有表」** —— `m15` 页上就有 `m15:users` 那张表，它是**系统/账号数据**、
#:   不是**业务台账**；`m14` 是**配置类**（§9.4）；`m10` 是**暂缓**（页都没做）。
#:    ⇒ ⛔ 所以**不许**拿"页上有没有 `data-sort-key`"当真值来源（那会得出"m15 是数据页"）。
#: TAIL-263 已撤掉无自有数据源的说明页 m13；各业务页的真实导出入口保留。
NON_DATA_VIEWS = {"m10", "m14", "m15"}
#: 不单独导出的数据页仍须有真实出口；TAIL-263 删除默认说明，去处在导出确认中呈现。
EXPORT_EXEMPT = {
    "m09": "m05",
}


@acc("ACC-X-EXP-001", "001-01")
def test_有数据的页面都有导出入口():
    """数据页保留真实导出；特殊费用随逐月欠款台账导出，在导出确认中显示去处。

    ⚠️⚠️ **这句 claim 的字面有歧义，执行形态是「三段」而不是「字面上的每一个视图」**：
      ① **数据页** ⇒ 必须有导出入口；
      ② **数据页、但不单独导出** ⇒ 核对共用导出入口及导出确认中的去处（`m09`）；
      ③ **非数据页** ⇒ **不在范围内**（`m10` 暂缓 / `m14` 配置类 / `m15` 系统账号）。
    ⚠️ 本断言**第一版按字面执行**，把 ③ 判成了"3 个缺口" —— **那是误判**（用户当场纠正）。
       误判换来的一样东西是：**证明这句 claim 的字面本身不可执行** ⇒
       已提议把它改写成上面三段（⛔ 否则下一个按字面做的人／模型还会重蹈覆辙）。
    ⚠️ `NON_DATA_VIEWS` 用**双向**钉住：冒出新的／不再成立，**都红** ——
       ⛔ 它是"这份名单已核对过"的意思，不是"允许少做"的意思。
    """
    # ⚠️ 2026-09-28（`TAIL-164` · `P2-a` 拆件）：`NAV` 已随拆件搬进 `web/shell/*.js` ⇒ 导航要从
    #    **合并后的壳**（`SHELL`）解析；而**视图切片 `V.*` 按计划 §23 留在 `index.html`** ⇒ 切片仍读单件。
    views = dict(sorted(set(re.findall(r"\['(m\d+)','([^']+)','[^']+'\]", SHELL))))
    assert len(views) >= 12, f"导航只解析出 {len(views)} 个视图 —— 解析大概失效了"
    slices = _view_slices(_index())

    no_entry, missing_note, exempt_ok, wrongly_listed = [], [], [], []
    for k in views:
        has_entry = bool(re.search(r'data-act="exp\w*"', slices.get(k, "")))
        if k in NON_DATA_VIEWS:
            if has_entry:
                wrongly_listed.append(k)     # 非数据页**忽然有了导出入口** ⇒ 口径变了，要同步名单
            continue
        if has_entry:
            continue                          # ① 数据页有入口 ⇒ 闭合
        if k in EXPORT_EXEMPT:
            assert 'data-act="ledExpToggle"' in slices.get(EXPORT_EXEMPT[k], ""), "特殊费用随台账导出的真实入口丢失"
            preview = _fn_body(_actions(), "ledExpOk:()=>", "ledExpSave")
            assert "特殊费用月报表" in preview, "导出确认未显示特殊费用工作表"
            exempt_ok.append(k)
            continue
        if re.search(r"不单独[^\"<]{0,40}导出[^\"<]{0,60}", slices.get(k, "")):
            exempt_ok.append(k)               # ② 有「说明去处」⇒ 按除外条件闭合
        else:
            no_entry.append(k)                # ⇒ **新缺口**（数据页、既没入口也没说明）

    assert not no_entry, (
        "这些**数据页既没有导出入口、也没有『不单独导出』的说明**（且不在非数据页名单里）⇒ 新缺口：\n  "
        + "\n  ".join(sorted(no_entry))
        + "\n  ⇒ 要么加导出入口，要么在页面上写明去处（claim 的除外条件要求「说明去处」）。")
    assert not wrongly_listed, (
        f"{sorted(wrongly_listed)} 在**非数据页**名单里，却有了导出入口 ⇒ 口径变了："
        "要么把它从名单里撤下来（那就是数据页，按 ① 走），要么说明为什么非数据页也要导出。")

    # ⭐ 豁免须已核对真实共用出口及导出确认，不能空挂名单
    for k in EXPORT_EXEMPT:
        assert k in exempt_ok, f"{k} 声明了豁免，但真实共用导出出口未闭合"


def _actions() -> str:
    return (_shell_dir() / "shell" / "actions.js").read_text(encoding="utf-8")


def _fn_body(src: str, name: str, end: str) -> str:
    """抽 `name:` 起、到 `end` 止的一段（段内断言用，避免全文件宽松命中）。"""
    i = src.index(name)
    return src[i:src.index(end, i)]


def _strip_js_comments(seg: str) -> str:
    """去掉 JS 注释（`/* … */` 与 `// …`）——

    ⚠️ 必须去：渲染面的**源码**里到处是 `**加粗**` 之类的**注释写法**（本仓中文注释的习惯），
       不去掉的话"无 Markdown 泄漏"这条断言会被自己的注释判红（**假红**）。
    ⚠️ 第二条 `sub` 是**兜未闭合的块注释**：截段窗口若正好切在一个 `/* …` 中间，
       第一条（要求有 `*/`）就匹配不上、注释会留在段里 ⇒ **又会假红**。
       （我第一版正是死在这：按固定字符数截段，截进了下一个注释块。）
    """
    seg = re.sub(r"/\*.*?\*/", "", seg, flags=re.S)
    seg = re.sub(r"/\*.*$", "", seg, flags=re.S)
    return re.sub(r"//[^\n]*", "", seg)


#: 渲染面：`name → (定义锚点, 终止标记)`。
#: ⚠️⚠️ 必须用**定义锚点**找人，⛔ 不能按"哪个文件包含这个名字"选文件 ——
#:   `ledExpOk` 这个名字在 `index.html` 里**也**出现（`data-act="ledExpOk"` 那个按钮）⇒
#:   按包含关系会选到 `index.html`，然后在里面找 `ledExpSave` **找不到**（我第二版就栽在这）。
#: ⚠️ 也⛔ 别用"固定字符数"截段：会截进后面的注释块，而那段注释若没闭合，
#:   去注释的正则匹配不上 ⇒ 注释里的 `**` 会被当成泄漏（我第一版栽在这）。
RENDER_SEGMENTS = {
    "ledExpStrip": ("ledExpStrip=()=>", "\n/*"),
    "procExpDlg": ("procExpDlg=()=>", "const procExpSelection"),
    "ledExpOk": ("ledExpOk:()=>", "ledExpSave"),
    "procExpOk": ("procExpOk:()=>", "procExpSave"),
}


#: 导出相关的**渲染面**（001-07 要核的就是这几段产出的字符串）
EXPORT_RENDERERS = tuple(RENDER_SEGMENTS)


@acc("ACC-X-EXP-001", "001-04")
def test_导出展开区在滚动容器之外且全页恰好一处():
    """claim：「导出展开区**渲染在滚动容器之外**，且**全页恰好一处**」。

    ⚠️ 「滚动容器」在这个壳里是**具体的**：`.tw{overflow:auto;max-height:…}`（表格包裹层）。
       代码自己的注释就写着（`index.html` L2048 / L2055）：
       > 「面板必须渲染在 `.tw` **之外**（浮层才不被滚动容器裁）」
       ⇒ 所以判据 = **展开区的渲染点在同一个卡片里第一个 `<div class="tw">` 之前**。
       ⭐ 这不是我发明的标准，是**代码注释里已经写着的意图** —— 判据只是把它变成可执行的。
    ⚠️ 「恰好一处」= 每个展开区**全页只被渲染一次**（`${ledExpOn?…}` 出现 1 次）——
       ⛔ 两处渲染会让同一份状态画两份，点一个另一个不动。
    """
    html = _index()
    slices = _view_slices(html)
    for strip, flag in (("ledExpStrip", "ledExpOn"),):
        call = f"${{{flag}?{strip}():''}}"
        assert html.count(call) == 1, (
            f"`{strip}` 的渲染点在**全页出现 {html.count(call)} 次** —— claim 要求**恰好一处**"
            "（两处渲染 = 同一份状态画两份，点一个另一个不动）")

        site = html.index(call)
        view = next((k for k, seg in slices.items()
                     if seg.find(call) >= 0), None)
        assert view, f"`{strip}` 的渲染点不在任何视图切片里 —— 解析大概失效了"
        seg = slices[view]
        idx = seg.index(call)
        near = seg[max(0, idx - 400):idx]
        assert '<div class="tw"' not in near, (
            f"`{strip}` 的渲染点前面就是 `.tw`（滚动容器）开标签 ⇒ 展开区**被塞进了表格容器**，"
            "会被滚动容器裁掉（浮层面板会被切断）—— 代码注释里写着它必须渲染在 `.tw` 之外。"
            f"\n  ⚠️ 注意：**不能**用「该片里第一个 `.tw` 在不在前面」来判 —— `{view}` 里"
            "前面还有别的卡片（也带 `.tw`），那样会**假红**。")


@acc("ACC-X-EXP-001", "001-03")
def test_多项目导出的清单预览有单多两条形态():
    """claim：「多项目导出的**清单预览**：**单项目 = 一个工作簿（多工作表）**，
    **多项目 = zip ＋ 每项目一行清单**」。

    ⚠️ 落点 = 两个导出确认弹窗 `ledExpOk`（逐月欠款台账）/ `procExpOk`（过程资料）的 `body`
       —— 它们都是 `pjs.length===1 ? 单 : 多` 的**两条形态**。
    ⚠️ 「每项目一行清单」**必须真的是"一行一项目"**（分支自己 `pjs.map`，或交给 `TBL` 的列定义式
       `list:` ⇒ 那时由**内核**逐项一行；见下面那句的两段式判法）——
       ⛔ 只写一句"内含 N 个"（数字）**不算清单**：用户要看的是**哪几个项目**在里面。
    """
    for key, end, unit in (("ledExpOk:", "ledExpSave", "工作表"),):
        seg = _fn_body(_actions(), key, end)
        assert "pjs.length===1" in seg, f"`{key}` 没有**单/多**两条形态（claim 要求两条都在）"
        # ⚠️ 切三元分支要认**行首那个 `:`** —— 按"第一个 `:`"切会在 `style="margin:0"` 上断开
        parts = re.split(r"\n\s*:\s*", seg.split("pjs.length===1", 1)[1], maxsplit=1)
        assert len(parts) == 2, f"`{key}` 的单/多两条形态切不开（三元的 `:` 大概换写法了）"
        single, multi = parts
        assert "1 " in single and ("工作簿" in single or "文件" in single), \
            f"`{key}` 的**单项目**分支没说清生成什么（应是「1 个工作簿/文件」）"
        assert unit in single, f"`{key}` 的单项目分支没说明**内含多张工作表**（应出现 `{unit}`）"
        # ⭐ 2026-09-29（`TAIL-64` A′）：表外壳走统一出口 `TBL` ⇒ 原先钉 `<table` 字面就假红了
        #   （那串搬进 `TBL` 内核后分支里不再出现）。改钉**两段式**（照 P0 范式）：
        #   ① 分支**委托** `TBL` 并交出表的身份（`key:'modal:…'`）；② 内核里**真的**渲染 `<table>`。
        #   自证 = `tools/mut/_mut_tbl.py` 的 M16/M17 去掉这两处委托 ⇒ 必须红。
        assert "TBL({cls:'cond',key:'modal:" in multi, (
            f"`{key}` 的**多项目**分支没有清单表 ⇒ 用户看不到「哪几个项目」进了 zip"
            "（claim 明确要求「**每项目一行清单**」）")
        assert "<table" in tbl_kernel(), "`TBL` 内核不再渲染 `<table>`（表外壳出口坏了）"
        # ⭐ 2026-09-30（`TAIL-64` **`P5-d-a`**）：**「逐项目一行」也改成两段式** —— 判词不变（清单要一行一项目），
        #   落点允许两种：① 分支**自己** `pjs.map`（旧形态）；② 分支把**数据**交给 `list:`（列定义式
        #   `cols:[{t,r}]` ＋ `list:pjs`）⇒ 那时"逐项目一行"由**内核**做 ⇒ ②那半钉内核（下一句）。
        #   ⛔ 别退回"必须有 `pjs.map`"字面 —— 那等于宣布以后不许用列定义式（与 `P5-d` 的方向相反）。
        assert ("pjs.map" in multi) or ("list:pjs" in multi), \
            f"`{key}` 的清单表不是**逐项目一行**（既没有 `pjs.map`，也没有把数据交给 `list:`）"
        assert "rows=list.map((x,i)=>'<tr>'+cols.map(c=>c.r(x,i)).join('')+'</tr>')" in tbl_kernel(), \
            "`TBL` 内核不再**逐项一行**（列定义式的行派生坏了 ⇒ 用 `cols:` 的清单表会**一行都不出**）"
        assert "zip" in multi.lower(), f"`{key}` 的多项目分支没说明**打成 zip**"


@acc("ACC-X-EXP-001", "001-07")
def test_导出相关渲染面无Markdown泄漏():
    """claim：「导出相关**渲染面无 Markdown 泄漏**」。

    ⚠️ "泄漏" = 本该渲染成**格式**的写法（`**粗体**` / `| 表格 |` / `## 标题`）被当成**字面文本**吐到界面上。
       落点 = 导出相关的那几段**渲染面**（`ledExpStrip` / `procExpStrip` / `ledExpOk` / `procExpOk`）。
    ⚠️⚠️ 必须先**去掉 JS 注释**再查 —— 本仓中文注释里 `**加粗**` 是习惯写法，
       不去注释这条断言会被**自己的注释**判红（假红，而且极难查）。
    ⚠️ **覆盖面的诚实交代**：这是**静态**检查（核模板串），
       ⛔ **不等于**真机 DOM 上没有泄漏 —— 真机那层由 `tools/probe/_shell_smoke.py` 兜（它读 console/page 错误）。
    """
    # ⚠️ 渲染面**不在同一个文件**：两个展开区在壳的公共件里、两个确认弹窗在 `actions.js`；
    #    2026-09-28（`TAIL-164` · `P2-a` 拆件）后展开区又搬进了 `web/shell/pages-a.js`/`pages-b.js`
    #    ⇒ 取源一律用**合并后的壳**（`SHELL`），⛔ 别再列举单件（列举必漏，漏了还静默）。
    for name, (anchor, end) in RENDER_SEGMENTS.items():
        src = next((s for s in (SHELL, _actions()) if anchor in s), None)
        assert src, f"找不到 `{name}` 的定义（锚点 `{anchor}`）—— 落点变了，先核对再改断言"
        seg = _strip_js_comments(_fn_body(src, anchor, end))
        assert "**" not in seg, f"`{name}` 的渲染面出现 `**`（Markdown 粗体泄漏到界面）"
        assert not re.search(r"(?m)^\s*\|\s*\S", seg), f"`{name}` 的渲染面出现 Markdown 表格行（`| … |`）"
        assert not re.search(r"(?m)^\s*#{1,4}\s", seg), f"`{name}` 的渲染面出现 Markdown 标题（`## …`）"


#: 导出清单弹窗里的表（`001-06`）：`弹窗名 → (标题片段, 排序键)`
EXPORT_MODAL_TABLES = {
    "ledExpOk": ("导出 · 逐月欠款台账", "modal:ledExp"),
}
#: ⚠️ **刻意不可排**的表 —— `index.html` 注释里点名的（`MOD-07` 焊材/气体提取的**分组表**）：
#:   它只写 `data-sort-key`，是因为**合计行要 pin 在表尾**，注入了排序入口反而会坏。
NOT_SORTABLE_BY_DESIGN = ("modal:expExt",)


@acc("ACC-X-EXP-001", "001-06")
def test_导出清单弹窗里的表可排序():
    """claim：「导出**清单弹窗**里的表**可排序**」。

    ⚠️⚠️ **这条判据的命门是那个开关叫 `data-sort`，⛔ 不是 `data-sort-key`** ——
       壳里注入排序入口的逻辑**精确匹配 `data-sort` 属性本身**（`index.html` 里那段正则，
       还专门为此改过一版：老的 `\\bdata-sort\\b` 会把 `data-sort-key` 也算成「可排」，
       `-` 是词边界）。`data-sort-key` 只是**排序状态的键（表的身份）**。
    ⇒ 所以断言**两头都要**：① 表上有 **`data-sort`**（真开关）；② 有 `data-sort-key`（身份 · 本仓「新表一律声明」）。
       ⛔ 只钉 `data-sort-key` = 盯着一堆**不生效**的属性看 —— 典型的「看着改了、其实没生效」。
       ⚠️ 这条我是**踩过**的：第一版找"同类里能排的那张"去对齐，认错了对象
       （`modal:expExt` 有 key 但**没** `data-sort`，它是**刻意不可排**的）——
       所以反面也一并钉住。
    """
    acts = _actions()
    kern = tbl_kernel()
    for name, (title, key) in EXPORT_MODAL_TABLES.items():
        assert title in acts, f"找不到导出弹窗「{title}」（{name}）—— 落点变了"
        # ⭐ 2026-09-29（`TAIL-64` A′）：表外壳走统一出口 `TBL` ⇒ 字面标签在源码里查不到了。
        #   改钉**委托时那三件事**（判据的命门不变：真开关 `data-sort` ＋ 身份 `key`）：
        #   ① 交出身份 `key:'modal:…'`；② **不**写 `sort:false`（= 走默认的可排分支）；
        #   ③ 内核里「可排」那条分支**真的**出 ` data-sort data-sort-key="…"`。
        #   自证 = `tools/mut/_mut_tbl.py` 的 M16（去掉委托）/ M18（把 `sort:false` 塞进去）都必须红。
        i = acts.find("key:'" + key + "'")
        assert i >= 0, f"「{title}」的清单表没声明身份 `key:'{key}'`（本仓约定新表一律声明）"
        win = acts[max(0, i - 200): i + 220]
        assert "TBL({" in acts[max(0, i - 200): i], (
            f"「{title}」的清单表没用统一出口 `TBL`（`TAIL-64` A′）")
        assert "sort:false" not in win, (
            f"「{title}」的清单表被标成**刻意不可排**（`sort:false`）⇒ 表头点了不动。\n"
            "  ⚠️⚠️ 刻意不可排只许给「合计行要 pin 在表尾」那类表（`modal:expExt`）。")
        assert "' data-sort data-sort-key=\"'+key+'\"'" in kern, (
            "`TBL` 内核里「可排」那条分支不再出 ` data-sort data-sort-key`（排序开关坏了）")

    # ⭐ 把**机制**也钉住：⛔ 别把"认 `data-sort`"放宽成"认 `data-sort-key` 也行"
    # ⚠️ 2026-09-28（`TAIL-164` · `P2-a` 拆件）：这段机制住在**壳的公共件**里（原先在 `index.html` 的内联脚本，
    #    现随 `P2-a` 搬进 `web/shell/*.js`）⇒ 必须读**合并后的壳**（`SHELL`），⛔ 不是 `index.html` 单件。
    #    ⭐ 判据内容**一个字没改**（还是钉那个字面），只换读取出口（本仓既有做法，同 `shell_src.dl_kernel`）。
    assert "\\sdata-sort[\\s>]" in SHELL, (
        "注入排序入口的逻辑不再精确匹配 `data-sort` —— ⚠️ 一旦放宽成「有 `data-sort-key` 也算可排」，"
        "**刻意不可排**的表（分组表：合计行要 pin 在表尾）会被**误注入**排序入口 ⇒ 那是**有意的设计**，别动。")

    # ⭐ 反面：刻意不可排的表 **不许**被"顺手对齐"加上 `data-sort`
    # ⚠️ 2026-09-29（`TAIL-64` A′）：表外壳走统一出口 `TBL` ⇒ **字面标签查不到了**，改钉**委托时的两件事**：
    #   ① 交出身份（⚠️ 它是**拼出来**的：`key:'modal:expExt-'+kind` ⇒ 查**不带收尾引号**的那半段）；
    #   ② **显式** `sort:false`（= 走"只出 `data-sort-key`、不出 `data-sort`"那条分支）。
    #   ⛔ 别改回钉字面标签（那等于宣布"以后不许抽通用件"）。
    #   自证 = `tools/mut/_mut_tbl.py` 的 M36（去掉委托）/ M37（`sort:false` 去掉）都必须红。
    for key in NOT_SORTABLE_BY_DESIGN:
        needle = "key:'" + key
        assert needle in acts, (
            f"找不到 `{key}` 那张刻意不可排的表 —— 落点变了（或它没走统一出口 `TBL`）")
        i = acts.index(needle)
        assert "TBL({" in acts[max(0, i - 200): i], f"`{key}` 那张表没走统一出口 `TBL`"
        assert "sort:false" in acts[i: i + 260], (
            f"`{key}` 那张表**没显式声明 `sort:false`** —— ⛔ 它是**刻意不可排**的"
            "（分组表：合计行要 pin 在表尾 ⇒ 注入排序入口会坏）")


__all__ = ["NON_DATA_VIEWS", "EXPORT_EXEMPT", "EXPORT_RENDERERS",
           "EXPORT_MODAL_TABLES", "NOT_SORTABLE_BY_DESIGN"]
