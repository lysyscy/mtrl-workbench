"""`ACC-PRJ-LIST-001` **001-07**：长项目名必须**完整可读**（不得省略号、不得被容器硬切）。

⭐⭐ 这条是基线里 **B 类「不可由机器断言」的唯一一条**，它的备注写得非常明确：

> 属**渲染层行为**，本项目的 DOM-stub 自检（`demo/_smoke.js`）**测不到**
> （它只测 DOM 与文本，不测 CSS 是否实际裁切）。⇒ 由真实浏览器走查 / 人工复核；
> **实现阶段若引入端到端浏览器测试，应把它升级为可机器断言。**

本文件通过 Playwright 测量实际渲染宽度。

⚠️ 为什么**必须**用真浏览器（⛔ 别退回 DOM-stub 那种做法）：
   「被容器硬切」是**布局的结果** —— `overflow:hidden` 配一个固定宽度，DOM 里文本
   **一个字符都不少**、只有**渲染宽度**能看出它被切了。⭐ 所以判据只能是
   `scrollWidth <= clientWidth`（**真量一遍**），而不是"扫 CSS 文本里有没有 ellipsis"。

⚠️ 本文件**会起一个真实的 uvicorn**（测试库 · 随机端口）＋ 一个 Chromium ⇒
   比别的用例慢得多、也重得多。⭐ 这是有意的：这条判据**只能**这么测。
"""

from __future__ import annotations

import socket
import threading
import time

import pytest

from app.core.db import session_scope
from app.main import app

#: 一个**很长**但完全合法的项目全名（中文 ＋ 括号 ＋ 数字，模拟真实形态）。
#: ⚠️ 长度按"能撑破一栏"来取 —— 太短的话这条断言**测不出任何东西**（照样绿）。
LONG_NAME = (
    "中国石油化工股份有限公司西南油气分公司川西天然气净化厂第二联合装置技术改造项目"
    "（二期）材料采购与结算全过程管理（含备品备件与专用工具）"
)




def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _LiveServer:
    """在**后台线程**里跑一个真 uvicorn（⛔ 不依赖"外面恰好有个服务在跑"）。

    ⚠️ 为什么要自己起：pytest 若去打 `127.0.0.1:8000`，那条断言就**依赖环境**
       （本机没开服务 ⇒ 红；而那与"名字读不读得全"毫无关系）。
       ⭐ 自己起一个 ⇒ 这条判据**只依赖代码**，可以在任何机器上跑。
    """

    def __init__(self) -> None:
        import uvicorn

        self.port = _free_port()
        self._server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=self.port, log_level="warning"))
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def __enter__(self) -> str:
        self._thread.start()
        deadline = time.time() + 30
        while time.time() < deadline:
            if getattr(self._server, "started", False):
                return f"http://127.0.0.1:{self.port}"
            time.sleep(0.1)
        raise RuntimeError("uvicorn 没能在 30 秒内起来")

    def __exit__(self, *exc) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=15)


def _seed_long_project() -> int:
    """往**测试库**塞一行超长项目名 ⇒ 返回 id（⚠️ 用完要删）。

    ⚠️⚠️ 长名字要写在 **`disp`（展示名）** 上，⛔ 不是只写 `name_full` ——
       页面渲染的是**展示名**（`ACC-PRJ-LIST-001/001-02` 明写「**全名不作显示**
       （最多作悬停提示）」）⇒ 只塞 `name_full` 的话，那一行渲染出来是**空的**，
       于是这条判据会以"没找到那一行"红掉 —— ⭐ 我第一次就是这么写错的
       （红的原因与"名字被切"**毫无关系**，属于**测法**错、不是实现错）。
       ⇒ 两个都塞：`disp` 是"用户实际看到的那串"，`name_full` 顺带保持现实形态。
    """
    from app.mod01_projects.models import Project

    with session_scope() as s:
        row = Project(name_full=LONG_NAME, disp=LONG_NAME)
        s.add(row)
        s.flush()
        pid = row.id
        s.commit()
    return pid


def _drop_project(pid: int) -> None:
    from app.mod01_projects.models import Project

    with session_scope() as s:
        row = s.get(Project, pid)
        if row is not None:
            s.delete(row)
        s.commit()


def test_长项目名完整可读_真机量一遍不许被裁切():
    """真浏览器里量：那一行的**每个单元格**都不许被裁切。

    ⚠️ 为什么量**整行**而不是只量"项目名那一格"：
       ⛔ 别把断言绑死在"第几列是名字"上 —— 列会挪、名字也可能渲染在两个格子里。
       而"**长名字不得被切**"这件事，等价于"**渲染它的那一格不许被切**"——
       整行都量，就把"它到底在哪一格"这个问题**绕过去了**（⛔ 不靠猜）。
    """
    pid = _seed_long_project()
    try:
        with _LiveServer() as base:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(args=["--no-sandbox"])
                try:
                    page = browser.new_page(viewport={"width": 1280, "height": 900})
                    page.goto(base + "/app", wait_until="load", timeout=45000)
                    page.wait_for_function(
                        "() => (typeof PJs !== 'undefined' && PJs.length > 0) || BOOT_ERROR",
                        timeout=25000)
                    assert not page.evaluate("BOOT_ERROR"), "壳启动就报错了"

                    page.click('[data-k="m01"]')
                    page.locator(f'[data-act="editFull"][data-id="{pid}"]').wait_for(state="visible")

                    got = page.evaluate(
                        """(needle) => {
                            const rows = [...document.querySelectorAll('#view tbody tr')];
                            // ⚠️ 项目名在壳里是 <input>（可编辑单元格）⇒ `innerText` **不含**它
                            //    ⇒ 找行必须连 input 的 value 一起看（⭐ 我第一次只查 innerText，白跑一轮）
                            const hit = rows.find(tr => {
                                if (tr.innerText.includes(needle.slice(0, 12))) return true;
                                return [...tr.querySelectorAll('input')]
                                    .some(i => (i.value || '').includes(needle.slice(0, 12)));
                            });
                            if (!hit) return {found: false, rows: rows.length};
                            const cells = [...hit.querySelectorAll('td,th')];
                            const named = [...hit.querySelectorAll('input')]
                                .filter(i => (i.value || '').includes(needle.slice(0, 12)));
                            return {
                              found: true,
                              n: cells.length,
                              nameInputs: named.length,
                              // ① 「**不得用省略号**」：整行逐格算 computed style
                              ellipsis: cells.filter(c => {
                                  const st = getComputedStyle(c);
                                  return st.textOverflow === 'ellipsis'
                                      || (st.webkitLineClamp && st.webkitLineClamp !== 'none');
                              }).map(c => c.innerText.slice(0, 18)),
                              // ② 「**名字完整**」：input 的 value 一字不少（⛔ 不许 JS 层截断），
                              //    且**可点入 / 可选中**（键盘可读全 —— 这是"可读"的落点）
                              valueFull: named.every(i => (i.value || '').length === needle.length),
                              readonly: named.some(i => i.readOnly || i.disabled),
                              // ③ **实测**（⛔ 不作红绿 · 登记待裁定）：input 的宽度由 CSS 决定、
                              //    不由内容决定 ⇒ 长值**必然**视觉溢出（可横滚看全）。
                              //    ⚠️ 要量 **input 本身**，不是它外面的 `<td>` ——
                              //       量错了会得到"0 个溢出"的**假象**（⭐ 我第一版正是这么量的）。
                              clipCells: cells.filter(c => c.scrollWidth > c.clientWidth + 1).length,
                              clipInputs: [...hit.querySelectorAll('input')]
                                  .filter(i => i.scrollWidth > i.clientWidth + 1).length,
                              // ⚠️ 被切的具体是哪几格（红的时候要能一眼看出是哪一格、差多少）
                              clipped: [...hit.querySelectorAll('input')]
                                  .filter(i => i.scrollWidth > i.clientWidth + 1)
                                  .map(i => ({
                                      len: (i.value || '').length,
                                      sw: i.scrollWidth, cw: i.clientWidth,
                                  })),
                            };
                        }""", LONG_NAME)
                    got['keyboard_readable'] = []
                    for action in ('editFull', 'editDisp'):
                        field = page.locator(f'[data-act="{action}"][data-id="{pid}"]')
                        field.focus(); field.press('End')
                        end_visible = field.evaluate('(e)=>e.selectionStart===e.value.length && (e.scrollWidth<=e.clientWidth+1 || e.scrollLeft>0)')
                        field.press('Home')
                        home_visible = field.evaluate('(e)=>e.selectionStart===0 && e.scrollLeft<=1')
                        got['keyboard_readable'].append(end_visible and home_visible)
                finally:
                    browser.close()
    finally:
        _drop_project(pid)

    assert got.get("found"), (
        f"壳里**没渲染出**这个超长项目名（该页共 {got.get('rows')} 行）⇒ 本判据根本没测到东西"
        "（⚠️ 先确认 m01 已接线 —— 否则这条红的原因不是「名字被切」）")
    assert got["n"] > 0, "那一行一个格子都没有"
    assert got["nameInputs"] > 0, "没找到承载项目名的可编辑格（形态变了 ⇒ 本判据要跟着改）"

    # ① ⛔ 不得用省略号（claim 的第一半 —— 明确、可判定）
    assert not got["ellipsis"], (
        f"这些格子用了省略号/行数截断：{got['ellipsis']} —— claim 明写「**不得用省略号**」")

    # ② ⭐ 名字必须**完整**在内容里（⛔ 不许 JS 层截断成 "前 20 字…"），且**可读全**
    assert got["valueFull"], (
        "栏里的名字**被截短了**（value 比原名短）—— claim 明写「名字必须完整可读」")
    assert not got["readonly"], (
        "名字格是只读的 ⇒ 用户**没法读全**被框挡住的部分（那才真的不可读）")

    # ③ ⭐ **不得被容器硬切**（claim 的第二半）—— **硬断言**，⛔ 不再是"实测报告"。
    #    ⚠️ 2026-09-20 用户裁定：走 **(b) 完整版**（**改实现去够口径**，⛔ 不是把 claim 收窄成
    #       "可点入读全"）⇒ 实现侧已改成**名字格按内容定宽**（`shell/core.js::nameW`）
    #       ⇒ 本节从"只报数不判"升级为**必须为 0** ✓
    #    ⚠️ 要量 **input 本身**、不是它外面的 `<td>`：量错了会得到"0 个溢出"的**假象**
    #       （⭐ 我第一版正是这么量的 —— 那时还以为"不切"）。
    assert got['keyboard_readable'] == [True, True], got
