"""壳 `render()` 的两条**渲染纪律**（2026-09-21 用户报障后立的守卫）。

① **本页内刷新不得跳滚动** —— m03 勾选一行 ⇒ 列表跳回顶部（`pick` 走 `render()`，
   innerHTML 替换把 `.view` 的 scrollTop 归零）。⇒ `render()` 必须**先记后还**。
② **大表渐进渲染的安全边界** —— 库存明细 1900+ 行一次 parse 卡顿 ⇒ 分帧写入；
   三条红线：切点必须落在行边界（`</tr>`，退而求其次 `>`）、渲染途中切页必须**丢弃剩余块**、
   `BIND[VIEW]` 必须等最后一块写完（注入按钮依赖完整 DOM）。

⚠️ 读源码文本的断言：**先把注释剥掉**（本仓铁律 —— 别惩罚"把坑写进注释的人"）。
   ⚠️ 它们是**静态守卫**：真实行为由 `tools/probe/_shell_smoke.py` 的真机段兜（勾选后滚动不跳）。
"""

from __future__ import annotations

import re

from tests.acc_plugin import acc
from tests.shell_src import read_shell, tbl_kernel           # ⭐ 壳源的**唯一读取出口**（P4①立的规矩）


def _render_body() -> str:
    """取 `render()` ＋ 虚拟滚动那组函数（到 `const V=` 为止，已剥注释）。"""
    html = re.sub(r"/\*.*?\*/", "", read_shell(), flags=re.S)
    html = re.sub(r"//[^\n]*", "", html)
    i = html.find("function render(){")
    assert i > 0, "壳里找不到 render()（改名了？本守卫要跟着改）"
    j = html.find("\nconst V=", i)                  # 虚拟滚动一组函数紧跟 render 之后
    return html[i:j if j > 0 else i + 12000]


@acc()
def test_本页内刷新不得跳滚动():
    body = _render_body()
    assert "scrollTop" in body and "keep" in body, (
        "render() 丢掉了「先记后还」滚动 —— m03 勾选一行会跳回顶部（用户 2026-09-21 报障）")
    # 记与还必须成对：先取 keep，写完才还原（还原出现在 keep 之后）
    assert body.index("keep") < body.rindex("keep"), "`keep` 只出现一次 ⇒ 没有还原"
    # ⛔ 切页回顶是**故意的**：`go()` 里的显式置 0 不许被人"顺手修掉"
    # ⚠️ 2026-09-27（批次 6）：`go()` 从**一行**变成**多行**了（进页前要多做一件"标出要拉哪几路"）
    #    ⇒ 判法从"取那一行"改成"取这一段的**窗口**"（⛔ 不是放宽 —— 仍要求函数体里真有这句）。
    go = re.sub(r"/\*.*?\*/", "", read_shell(), flags=re.S)
    body_go = go[go.index("function go(k){"):][:700]
    assert "scrollTop=0" in body_go, "go() 的切页回顶没了（那是故意的设计）"


@acc()
def test_虚拟滚动的设计红线():
    """⭐ 2026-09-21 用户裁定「走虚拟滚动」（m08 库存明细 1374 行 ≈ 2.75 万节点，一次 parse 卡几百毫秒）。

    ⚠️⚠️ 设计红线（同日**两连败换来的**，本断言把它们钉死）：
    ① 每帧写**完整片段**（pre ＋ 垫高 ＋ 窗口行 ＋ post，一次 innerHTML）—— ⛔ 绝不 `insertAdjacentHTML`
       追加表格片段（div 上下文里 `<tr>` 会被解析器整段吞掉，实测 211/1374 行）；
    ② ⛔ 绝不把一张表拆成多个 `<table>`（列宽/吸顶错位）；
    ③ 行高**实测回填**（本表 27~91px 共 6 档、会换行 ⇒ 不能假定等高）＋ base 自校正。
    """
    body = _render_body()
    assert "startVirtual" in body and "VSCROLL" in body, "虚拟滚动入口没了（m08 又会整表渲染卡顿）"
    assert "insertAdjacentHTML" not in body, "红线①破了：虚拟路径里出现了片段追加（<tr> 会被解析器吞掉）"
    # ⭐ `P5-c`（2026-09-30）后落点变了（页级那条路已删）：红线①仍钉「**首帧一次整页写**」，
    #    红线②另钉「**滚动重画只换 `tbody` 的行**」（原来是"写完整片段"那句，落点已随页级一起消失）。
    assert "$('#view').innerHTML=out;" in body, \
        "红线①破了：首帧不是**整页一次写**（拼片段追加的话 `<tr>` 会被解析器整段吞掉）"
    assert "tb.innerHTML = SP(topH0) + winRows.join('') + SP(botH0);" in body, \
        "红线②破了：滚动重画不是**只换 `tbody` 的行**（动 `#view`／`.tw` ⇒ 打断滚轮手势、`scrollTop` 归零）"
    assert "getBoundingClientRect().height" in body, "红线③破了：没有行高实测回填（行高 27~91px 不等高，估算会漂移）"
    assert "inTbody" in body, (
        "红线④破了：splitRows 不认 tbody —— 截到 thead 的表头行会把整段窗口写进 thead 上下文"
        "（2026-09-21 真机抓到：tbody 空、页面没行）")
    assert "VS_MIN=400" in read_shell(), "虚拟化阈值没了（小页也被虚拟化 = 固定开销不值）"
    # 红线③：BIND（注入按钮/钩子）必须在最后一块之后才调 —— 两个分支各调一次
    assert body.count("BIND[VIEW]") >= 2, "`BIND[VIEW]` 只调一处 ⇒ 另一条路径渲染完没有注入钩子"


@acc()
def test_表级虚拟滚动_挂载点与分派顺序():
    """⭐ `TAIL-64` **P5-a**（2026-09-30）＋ **P5-c**（同日）：表级虚拟滚动的三条**结构性**保证。

    ⚠️ **为什么要有它**：`m08` 试点把"**谁在滚 / 谁被重画**"从**整页**换成**那张表自己** ⇒
      ① **滚动监听的挂载点只能有一处、且必须排在 `startVirtual` 里任何 `return` 之前** ——
         真机当场抓到过：写在页级那半里，表级那条从函数顶部就 `return` ⇒ **一个监听都挂不上**
         （滚动条能拖、内容一动不动），而离线判据 / `node --check` / `U1` **全绿** ⇒ 只能靠这条把结构钉住；
         ⚠️ `P5-c` 删掉页级那条路之后，`startVirtual` 里**还剩三处**提前退出（逃生阀 / 没有标记的表 / 分派）
         ⇒ 这条规矩不变；
      ② **两条路必须归一**（`startVirtual(` 全壳只许"定义 ＋ 调用"两处）—— 另开第三条路 = 第三条要各自
         记得调 `placePops` / `applyPjFilters` / `BIND`（本仓"漏一条"的经典病）；
      ③ **`TBL` 内核真的出 `data-vs`**（⚠️ `P5-b` 起**一律带**：⛔ 别改成逐表开关 —— 那会退化成名单式）
         ＋ **`startVirtual` 里真有「本页有没有带标记的表」那一步** —— 否则"表级接管"**悄悄不生效**
         （那一页 1000+ 行照旧整表 parse）；
      ④ **分派前先清空实例表、逃生阀接在唯一那条路上**（`P5-c`）：⛔ 顺序错了 = 上一页认领过的表留到下页
         （滚动时认错对象、画到不在页上的表）；`off` 若没人读 = `VSCROLL` 变成一条**没人管的配置**。
    自证 = `tools/mut/_mut_p5a.py`：改名标记 / 摘掉挂载点 / 摘掉分派 / 摘掉清空 ⇒ 本件必须红。
    """
    body = _render_body()
    assert "vsBindScroll();" in body, \
        "虚拟滚动的滚动监听没有统一挂载点（`vsBindScroll()` 不见了）—— 表级那条路会没人挂监听"
    #: ⚠️ 顺序只在 `startVirtual` **函数体里**量 —— `let VS_TS=[];`（声明）里也含 `VS_TS=[];`，
    #:    在整段里量会量到声明那一处（首版就栽在这：量出"清空在挂监听之前"的**假红**）。
    sv = body[body.index("function startVirtual(html"):]
    for need in ("vsBindScroll();", "VS_TS=[];", "if(!vsOn(VIEW)) return false;",
                 "return startVirtualTables("):
        assert need in sv, f"`startVirtual` 里少了这一步：{need}"
    order = [sv.index("vsBindScroll();"), sv.index("VS_TS=[];"),
             sv.index("if(!vsOn(VIEW)) return false;"), sv.index("return startVirtualTables(")]
    assert order == sorted(order), (
        "`startVirtual` 的四步顺序错了 —— 必须是「**挂监听 → 清空 → 逃生阀 → 分派**」："
        "监听排后面 ⇒ 一 `return` 就跳过它（真机症状：滚动条能拖、内容一动不动；而离线全绿）；"
        "清空排分派后 / 只在某一支里清 ⇒ 上一页的实例留到下页")
    src = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", read_shell(), flags=re.S))
    n = src.count("startVirtual(")
    assert n == 2, (
        f"`startVirtual(` 全壳出现 {n} 次（应为 **2**：定义 ＋ `render()` 里那一次调用）—— "
        "另开第三条渲染通道 = 那条要各自记得调 `placePops` / `applyPjFilters` / `BIND`")
    #: ⚠️ **必须剥块注释再判**：`TBL` 内核那段注释里**引述**了 `data-vs="<key>"` 这个写法
    #:    ⇒ 不剥的话"内核不再拼标记"这个变异**照样绿**（本仓"判据撞注释"第 4 次）。
    kern = re.sub(r"/\*.*?\*/", "", tbl_kernel(), flags=re.S)
    assert "'<tbody data-vs=\"'+(key||'1')+'\">'" in kern, \
        "`TBL` 内核不再在 `tbody` 上出 `data-vs` ⇒ 表级虚拟滚动认领不到任何表"\
        "（⚠️ `P5-b` 起**一律带**：⛔ 别改成「逐表开关」—— 那会退化成名单式）"
    #: ⚠️ 钉的是**调用**那一句（`=vsTableHits(html)`）—— 光写 `vsTableHits(html)` 会被**函数定义**满足（假绿）。
    assert "=vsTableHits(html)" in body, \
        "`startVirtual` 里没有「本页有没有带标记的表」这一步 ⇒ 表级那条路**永远不会接管**"


@acc()
def test_页级虚拟滚动那条死路已删():
    """⭐ `TAIL-64` **P5-c**（2026-09-30）：页级那条路（"整页一张大表自己滚"）**已删**，只剩**表级**。

    ⚠️ **为什么删**（真机逐页量测见 `tools/oneoff/_p5c_survey.py`）：`P5-b` 起 `TBL` **每一张表**都带
       `data-vs` ⇒ 只要带标记的表够行数就由表级接管，**页级那半已经走不到**；而 17 页里"够阈值却**不带**
       标记的 `tbody`" = **0 个** ⇒ 没有任何页指望它。两条路并存 = 同一件事**写两遍**（`TAIL-64` 整条主线
       就是从"多份口径"收成一个）⇒ 删掉它，`VSCROLL` 的 `off` 也**恢复 `TAIL-66` 的原意**（＝本页不虚拟化）。
    ⚠️ **墓碑那半**：壳里不许再出现**整页窗口写**的形态 —— 记号就是那个整页实例 `VS`（`let VS=` / `VS.pre` /
       `VS.post`）。⛔ 加回来 = 红线① 的老毛病跟着回来（"窗口换错了不报错"）。
    ⚠️ **堵漏那半**（`P5-c` 同批，三处都是"接管时认错了对象"，⛔ 全都不报错，只会画错 / 画空 / 花屏）：
      ① **没有自带滚动容器（`.tw`）的表不许接管** ⇒ 行**原样写回**（硬画 ⇒ 整张表只剩一个垫高行，
         看起来就是「表是空的」）。⚠️ 这不是假想：实测 17 页里有 **9 张**带标记的表不在 `.tw` 里；
      ② **认领表体按刚打上的 `data-vs-i` 标记对位**，⛔ **不按 `data-vs` 的值查**（`TBL` 的 `key` 缺省是
         `'1'` ⇒ 一页多表同键（`m14` 实测 5 张全叫 `1`）⇒ 按值查会把窗口画到**别人**那张表上）；
      ③ **每页先清空实例表**（顺序见上一条判据）。
    自证 = `tools/mut/_mut_p5a.py`：`M4`–`M7`（清空 / 写回 / 对位 / 退回整页写）各自必须红。
    """
    body = _render_body()
    src = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", read_shell(), flags=re.S))
    for mark in ("let VS=", "VS.pre", "VS.post"):
        assert mark not in src, (
            f"页级那条路**又长回来了**（壳里出现 `{mark}`）—— 虚拟滚动只许有**表级**这一条："
            "另一条得各自记得调 `placePops` / `applyPjFilters` / `BIND`，窗口口径也会分叉")
    # ① 没 `.tw` ⇒ 行原样写回（⛔ 别硬画成"整张表只剩一个垫高行"）
    assert "inst.pre+inst.rows.join('')+inst.post" in body, \
        "认领时没看「这张表有没有自带滚动容器（`.tw`）」⇒ 没有容器的表会被画成**只剩一个垫高行**（像张空表）"
    # ② 认领按 `data-vs-i` 对位（⛔ 不按值查：一页里多张表会同键）
    assert "querySelector('tbody[data-vs-i=\"'+inst.hit+'\"]')" in body, \
        "认领表体不是按 `data-vs-i` 标记**对位**"
    assert "querySelector('tbody[data-vs=\"'+inst.key+'\"]')" not in body, \
        "认领表体又按 `data-vs` 的**值**查了 —— 一页里多张表同键（`key` 缺省 `'1'`）⇒ 窗口会画到别人那张表上"
    # ③ 每页先清空（顺序由「挂载点与分派顺序」那条判据钉）
    assert "VS_TS=[];" in body, "分派前没清空实例表 ⇒ 上一页认领过的表会留到下页"


@acc()
def test_通用浮层要逃出卡片裁剪_机制只有一处():
    """⭐⭐ 2026-09-26：`TAIL-109`（用户报障「**通用导入的项目选择控件，行数显示不全**」）＋
    `TAIL-110`（同类风险收口）。

    **病根**：`.card{...overflow:hidden}`（给表格圆角用的）会剪掉**卡片矩形之外**的部分，而浮层是
      `position:absolute` ⇒ 真机量到：卡片下沿 504、浮层伸到 567 ⇒ **裁掉 63px ＝ 最下面 2~3 行**，
      那几行**既看不见也滚不到**（浮层自身 `scrollH≈clientH`）。
    **药**：渲染后把浮层提升为 `fixed`（包含块 = 视口 ⇒ 不受非 transform 祖先的 `overflow` 裁剪）。

    **判词**（五半，缺一半都不算）：
      ① 机制**只有一处实现**（`placePops`）—— ⛔ 别按"项目面板一套、时间选择器一套"各写一份；
      ② **两类浮层都挂了两个钩子**：锚 `pjwrap` ／ 盒 `pjpop`（项目面板 ＋ **时间选择器**）；
      ③ `render()` **两条路径都要调**（虚拟滚动那条**提前 `return`** ⇒ 漏了它，大表页上照旧被裁）；
      ④ 滚 / 缩窗口要**重新定位**（浮层是 `fixed`，不重新定位就"粘"在原地像浮在空中）；
      ⑤ ⛔ **不许再出现裸浮层**：壳里每个 `z-index:80` 的浮层盒**必须**带 `pjpop`
         （新加浮层忘了挂钩子 ⇒ 它的后半截又会被裁，而人**不会记得**这件事 —— 所以由机器记）。

    ⚠️ 能证伪：删 `placePops` 的任一调用 / 摘掉某一类的 `pjpop` / 新加一个不带钩子的浮层 ⇒ 本件必红。
    ⚠️ 静态判词的**行为**那半边由真机段 `tools/probe/_shell_pops.py` 兜（量 `fixed` ＋ 点命中）。
    """
    raw = read_shell()
    src = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", raw, flags=re.S))

    # ① 机制只有一处
    assert src.count("function placePops()") == 1, "通用浮层机制**应当只有一处**（`placePops`）"

    # ② 两类浮层都挂两个钩子
    assert 'class="mpwrap pjwrap"' in src, (
        "时间选择器的**锚**没挂 `pjwrap` —— 它就不会被 `placePops` 提升为 `fixed`（`TAIL-110`）")
    assert src.count('class="fi pjwrap"') >= 5, "项目面板的锚不见了（`.fi pjwrap` 那十几处）"
    pops = re.findall(r"<div[^>]*z-index:80[^>]*>", src)
    assert len(pops) == 2, (
        f"壳里的浮层盒数变了（{len(pops)} 个）—— 增删浮层必须同批过本件（并挂好钩子）：{pops}")
    for tag in pops:
        assert 'class="pjpop"' in tag, (
            f"有浮层**没挂 `pjpop`** ⇒ 它的后半截会被卡片裁掉（`TAIL-109`/`TAIL-110`）：{tag}")

    # ③ 两条渲染路径都调（`placePops()` 全壳出现 3 次 = 1 处定义 ＋ 2 处调用）
    assert src.count("placePops()") == 3, (
        f"`placePops()` 的调用点不是两处（全壳 {src.count('placePops()')} 次）—— "
        "虚拟滚动那条提前 `return`，漏了它大表页上照旧被裁")

    # ④ 滚 / 缩窗口要重新定位
    assert "document.addEventListener('scroll', placePops, true)" in src, (
        "浮层是 `fixed` ⇒ 外层一滚必须重新定位（⚠️ 要**捕获阶段**：`scroll` 不冒泡）")
    assert "addEventListener('resize', placePops)" in src, "缩窗口后浮层没重新定位"


@acc()
def test_项目面板的过滤与折叠_两条渲染路径都要重涂():
    """⭐⭐ 2026-09-27（用户裁定 ①②）：项目面板的**搜索词与归档折叠**是"渲染后重涂"的。

    ⚠️ 为什么必须重涂：过滤是**纯 DOM** 的（打字**不重绘** —— 重绘重建输入框会把焦点与光标一起丢掉，
      壳里踩过）⇒ 可面板一重绘（勾选 / 展开归档），那点 DOM 改动**就没了** ⇒ `render()` 收尾要照
      `PJ_TXT` 再涂一遍、按 `PJ_OPEN[pk+'Arc']` 复位折叠块。

    ⚠️ **两条渲染路径都要调**（同 `placePops` 那条教训）：虚拟滚动那条**提前 `return`** ⇒ 漏了它，
       大表页上「勾一个候选搜索词就没了 / 归档又自己展开」。

    能证伪：去掉任一处的 `applyPjFilters()` ⇒ 本件必红（计数断言）。
    """
    src = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", read_shell(), flags=re.S))
    assert "function applyPjFilters(){" in src, "没有过滤/折叠重涂的唯一出口"
    # ⚠️ 数**带分号的调用**（定义那行没有分号）⇒ 算术干净：**2 处渲染收尾 ＋ 1 处输入委托**。
    calls = src.count("applyPjFilters();")
    assert calls == 3, (
        f"`applyPjFilters();` 全壳调用 {calls} 次 —— 应为 **3**"
        "（`render()` 的**两条**路径各一处〔虚拟滚动那条提前 `return`，漏了它大表页上照样出问题〕"
        " ＋ `input` 委托一处〔打字时只切 DOM、不重绘〕）")
