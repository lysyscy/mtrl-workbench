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
from tests.shell_src import read_shell                       # ⭐ 壳源的**唯一读取出口**（P4①立的规矩）


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
    go = re.sub(r"/\*.*?\*/", "", read_shell(), flags=re.S)
    m = re.search(r"function go\(k\)\{[^\n]*", go)
    assert m and "scrollTop=0" in m.group(0), "go() 的切页回顶没了（那是故意的设计）"


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
    assert "VS.pre" in body and "VS.post" in body, "红线①破了：虚拟帧没有写完整片段（pre＋窗口＋post）"
    assert "getBoundingClientRect().height" in body, "红线③破了：没有行高实测回填（行高 27~91px 不等高，估算会漂移）"
    assert "inTbody" in body, (
        "红线④破了：splitRows 不认 tbody —— 截到 thead 的表头行会把整段窗口写进 thead 上下文"
        "（2026-09-21 真机抓到：tbody 空、页面没行）")
    assert "VS_MIN=400" in read_shell(), "虚拟化阈值没了（小页也被虚拟化 = 固定开销不值）"
    # 红线③：BIND（注入按钮/钩子）必须在最后一块之后才调 —— 两个分支各调一次
    assert body.count("BIND[VIEW]") >= 2, "`BIND[VIEW]` 只调一处 ⇒ 另一条路径渲染完没有注入钩子"


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
