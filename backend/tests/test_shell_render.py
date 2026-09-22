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
