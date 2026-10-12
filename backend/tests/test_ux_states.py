"""`TAIL-117` 批次 6：**页级四态**（加载 / 空 / 错误 / 部分成功）的离线判据（守则 §4.2 · §3.3 · §2.2 · §5.9）。

**本批治的是什么**（开工时的实测）：壳是「进哪页拉哪页」，而 `render()` **不看取数回来了没有**
⇒ 数据没到的那一瞬，屏幕上画的是**空表 / 0 / 空图**，与"确实没有数据"**长得一模一样**。
用户看到"这月没有付款"时分不清**真的没有**还是**还没取回来** —— 守则 §4.2 把这条列为最高优先级
（「宁可少给，不能给错」）。

**判据分工**：
  · **本件（离线）**：出口唯一性 ＋ 结构在位（状态页必须给下一步 ＋ 空态必须说清为什么与下一步）
    ＋ ⭐「所有取数都必须过"连不上"的人话包装」（本批 ㉗ 当场抓到的第二条缺口）
  · **真机 ㉗**（`tools/probe/_shell_states.py`）：把一路拖慢 ⇒ 屏幕上必须是「正在读取…」且**没有表**；
    把一路拦断 ⇒ 必须是「没能取到 ＋ 重试」，且点「重试」**真的能恢复**。

⚠️ 本件**不测行为**（"屏幕上那一瞬画的是什么"离线看不见）—— 那是 ㉗ 的活。
"""

from __future__ import annotations

import pathlib

from tests.acc_plugin import acc
from tests.shell_src import SHELL

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _seg(marker: str, stop: str = "\n}") -> str:
    """从 `SHELL` 里取一段源码（**起止都是唯一整串** ⇒ ⛔ 别用"下一个某级标题"那种找法）。"""
    i = SHELL.find(marker)
    if i < 0:
        return ""
    j = SHELL.find(stop, i)
    return SHELL[i:j + 2] if j > i else SHELL[i:]


@acc("ACC-UI-SHELL-001", "001-17")
def test_页级状态只有一个出口():
    """⭐「这一页现在该显示什么」只能由 `pageState()` 说了算（⛔ 别在各页 `V.*` 里各判一次）。

    ⚠️ **能证伪**：在某个 `V.*` 切片里另写一段"没数据就画空表"的判断 ⇒ 严格说本件抓不到；
       但把 `pageState` / `pageGate` 复制出第二份、或把 `render()` 的拦截拆掉 ⇒ 本件必红。
    """
    for fn in ("function pageState(", "function pageGate(", "async function retryPage(",
               "function markPending("):
        assert SHELL.count(fn) == 1, f"{fn}) 在壳里出现 {SHELL.count(fn)} 次（应当**只有一处**出口）"


@acc("ACC-UI-SHELL-001", "001-18")
def test_渲染必须先过页级状态():
    """⭐ `render()` 必须先问 `pageState()`：不 `ready` 就画状态页，⛔ 不许画空页。

    ⚠️ 判法 = 钉**结构在位**（`const st=pageState();` ＋ `if(st.kind!=='ready')`）——
       ⛔ 不判它内部怎么写（那是实现细节）；把拦截删掉 ⇒ 本件必红。
    """
    assert "const st=pageState();" in SHELL, \
        "`render()` 里没有取页级状态（`const st=pageState();`）—— 数据没回来时又会画空页"
    assert "if(st.kind!=='ready')" in SHELL, \
        "`render()` 没有按页级状态分流（`if(st.kind!=='ready')`）—— 加载 / 错误态会被跳过"


@acc("ACC-UI-SHELL-001", "001-19")
def test_状态页必须给下一步():
    """⭐ 状态页不是"一片空白"：**加载态**要说"正在读**哪几项**、读完会自己出来"；
    **错误态**要说"哪一块没取到 ＋ 别的页照常可用 ＋ 重试"（守则 §2.2「为什么 ＋ 下一步」）。"""
    gate = _seg("function pageGate(")
    assert gate, "找不到 `pageGate()`"
    for need, why in (("正在读取", "加载态必须说清「在读」"),
                      ("读完自动显示", "加载态必须说清「不用刷新」"),
                      ("没能取到", "错误态必须说清「没取到」"),
                      ("别的页照常可用", "错误态必须说清「影响范围」"),
                      ('data-act="retryPage"', "错误态必须给「重试」按钮")):
        assert need in gate, f"页级状态页缺「{need}」（{why}）"


@acc("ACC-UI-SHELL-001", "001-20")
def test_空态只有一个出口且要说清为什么与下一步():
    """⭐ 表内空态一律走 `EMPTYROW`、块级一律走 `EMPTYBOX`（守则 §2.2 / §5.9）——
    ⛔ 不许再手写 `<tr><td colspan=… class="ctr mut">`（那种写法多半只写"无数据"，没有下一步）。

    ⚠️ 墓碑用**带上下文的整串**（`class="ctr mut" style=`）—— 光搜 `class="ctr mut"`
       会把注释里那句"⛔ 别再手写…"也算上（假红）。
    """
    assert 'class="ctr mut" style=' not in SHELL, \
        "又出现手写的空态了（`class=\"ctr mut\" style=`）—— 空态必须走 `EMPTYROW` / `EMPTYBOX`"
    n_row = SHELL.count("EMPTYROW(")
    assert n_row >= 11, f"表内空态走 `EMPTYROW` 的只有 {n_row} 处（应 ≥ 11：11 张表各一处）"
    assert "EMPTYBOX(" in SHELL, "块级空态出口 `EMPTYBOX` 不见了（图表 / 卡内空区要用它）"


@acc("ACC-UI-SHELL-001", "001-21")
def test_取数一律过连不上的人话包装():
    """⭐⭐ 本批 ㉗ 当场抓到的第二条缺口：**`fetch` 自己被拒**那条路（服务没起 / 断网 / 被拦）
    漏出了浏览器的英文原文 —— 页级错误态上写着 `Failed to fetch`。

    ⇒ 契约：**壳里所有 `fetch` 都必须过 `rawFetch`**（它把网络失败翻成"连不上服务器 ＋ 下一步"）。
    ⚠️ 判法：裸 `await fetch(` **只允许两处** —— ① `api.js` 的 `rawFetch` 自己；
       ② `core.js` 的 `dlExport`（导出下载，它**自己**有一份人话 catch，见批次 1）。
       ⛔ 出现第三处就是"某条路上用户又会看到浏览器英文"。
    """
    bare = SHELL.count("await fetch(")
    assert bare <= 2, (
        f"壳里有 {bare} 处裸 `await fetch(`（只允许 2 处：`api.js::rawFetch` 与 `core.js::dlExport`）"
        " —— 新加的那处必须改走 `rawFetch`，否则网络失败时用户会看到浏览器的英文原文")
    # ⚠️ 数的是 `await rawFetch(`（5 处：通用 send / 表单 / 文件 / 两条抓取）；
    #    `getSafe` / `postSafe` 是箭头函数**直接返回**那个承诺（不带 `await`）⇒ 不算在内。
    assert SHELL.count("await rawFetch(") >= 5, \
        f"过 `rawFetch` 的取数只有 {SHELL.count('await rawFetch(')} 处（应 ≥ 5：通用写 / 表单 / 文件 / 两条抓取）"
    for need in ("const netErr =", "const rawFetch ="):
        assert need in SHELL, f"「连不上」的人话包装缺件：{need!r}"


@acc("ACC-UI-SHELL-001", "001-22")
def test_逐路容错要按路记名():
    """⭐ 页级状态的数据源 = `soft()` 按**路名**记的失败表（`FAILED`）——
    ⛔ 别把它退回"只往 `fails` 里 push 一句话"（那样判不出"是**哪一页的哪一路**坏了"）。

    ⚠️ 还有一条**防卡死**：`loadPaths` 必须在 `finally` 里摘 `PENDING`
       （中途抛异常还挂着 ⇒ 整页永久"正在读取"，用户连重试的机会都没有）。
    """
    assert "FAILED.set(label" in SHELL, "`soft()` 没按路名记失败（`FAILED.set(label, …)`）"
    assert "FAILED.delete(label)" in SHELL, "`soft()` 成功时没摘掉失败名 ⇒ 重试成功也仍显示错误态"
    assert "FAILED_TECH.set(label" in SHELL and "FAILED_TECH.delete(label)" in SHELL, "技术错误须随同路替换与恢复"
    assert "FAILED_TECH.delete(l)" in SHELL, "页级重试须同步清除该路技术错误"
    assert "fresh.forEach(l => PENDING.delete(l));" in SHELL, \
        "`loadPaths` 没在 `finally` 里摘 `PENDING` ⇒ 中途抛异常会让整页永久卡在「正在读取」"


@acc("ACC-UI-SHELL-001", "001-23")
def test_真机27号的判据还在():
    """⭐ 本批最要紧的三件（那一瞬画的是什么 / 取不到时画什么 / 重试真管用吗）**只有真机能验**
    ⇒ 判据本身也要有人守着（⛔ 别哪天被顺手删掉，文档还写着"已挂判据"）。"""
    src = (ROOT / "tools" / "probe" / "_shell_states.py").read_text(encoding="utf-8")
    for need in ("def check(", "retryPage", "正在读取", "kind === 'error'"):
        assert need in src, f"真机 ㉗ 里缺 {need!r} —— 页级四态的真机判据被拆了？"
    # ⭐ 2026-10-02（`TAIL-215` 批 1）：编排改成「遍历注册表」⇒ 锚点改指**注册表**（意图一字未改）。
    smoke = (ROOT / "tools" / "probe" / "_shell_segments.py").read_text(encoding="utf-8")
    assert "_shell_states:check" in smoke, "真机 ㉗ 没进注册表（`_shell_segments.py`）⇒ 等于没跑"


@acc("ACC-UI-SHELL-001", "001-53")
def test_真机31号的空态判据还在():
    """⭐ `TAIL-171`-①（2026-09-29 · 用户裁定「按推荐做」）：**全站此前没有任何真机探针验过「空态」**
    （`_shell_states.py` 只管 加载 / 错 / 重试）⇒ 空态此前**只有离线判据**，而"0 行那一刻屏幕上
    到底画了什么"**只有真机能验**（离线只能证明源码里写了 `EMPTYROW(...)`）。
    ⇒ 新增 `tools/probe/_shell_empty.py`（挑 `m04`：筛到没数据的月 ⇒ 必须给空态；再筛回当月 ⇒
    **正常路没被改坏**），本判据守"它还在、还挂着"（⛔ 别哪天被顺手删掉、文档还写着"已挂判据"）。"""
    src = (ROOT / "tools" / "probe" / "_shell_empty.py").read_text(encoding="utf-8")
    for need in ("def check(", "当前筛选条件下没有付款计划", "ok_empty", "正常路"):
        assert need in src, f"真机 ㉛（空态）里缺 {need!r} —— 空态的真机判据被拆了？"
    # ⭐ 2026-10-02（`TAIL-215` 批 1）：同上，锚点改指**注册表**。
    smoke = (ROOT / "tools" / "probe" / "_shell_segments.py").read_text(encoding="utf-8")
    assert "_shell_empty:check" in smoke, "真机 ㉛ 没进注册表（`_shell_segments.py`）⇒ 等于没跑"
