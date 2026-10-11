"""前端壳**运行时自检**（真机加载 `/app`，抓 console / page 错误，断言导航 ＋ `m03` ＋ `m01` 渲染）。

⚠️ 这条自检**不进 `pytest`**（它要浏览器 + 活服务）⇒ 属工程自检（`tools/`），
   与 `tools/_verify_auto.py` 同款定位：**真机才能发现的那类问题**用它抓。

⚠️⚠️ **本机两个必踩的坑（2026-09-17 实测，脚本已规避 —— 别改回去）**：
   1. **`wait_until="networkidle"` 永远等不到**（壳里有持续请求）⇒ 脚本会**静默挂死**。
      改用 `load` ＋ **显式的 `wait_for_function`**（等数据到位）。
   2. **`browser.close()` / `sync_playwright()` 退出时会挂在驱动连接上**
      （`Connection closed while reading from the driver`）⇒ 跑完必须 `os._exit()`，
      **不要**走正常关闭路径。⚠️ 症状极像"脚本没输出"：**空输出 ≠ 通过**。

⭐ `TAIL-215` 批 2 起：**本件只留「引导 ＋ 遍历注册表 ＋ 汇总」** —— 段的代码在 `tools/probe/_shell_*.py`（每段一件），段的**位置与理由**在 `tools/probe/_shell_segments.py`。
⇒ ⛔ 加一段别再改本件（加一个段件 ＋ 注册表加一行即可）。

用法：先起服务，再 `python -u tools/probe/_shell_smoke.py`。
"""

from __future__ import annotations

import os
import pathlib
import sys

from playwright.sync_api import sync_playwright

# ⭐⭐ 段的注册表（`TAIL-215` 批 1）：**哪几段 / 按什么顺序 / 为什么是这个顺序** —— 只有那一处。
#     ⛔ 别在本件再列一份段清单（那会长出第二套顺序 —— 本仓最恨的病）。
from _shell_segments import BASE, SEGMENTS        # noqa: E402
errors: list[str] = []



def _freshness_error(got: list, want: list) -> str | None:
    """比「页面拿到的列清单」与「磁盘上的列清单」—— 不一致就给出那句**指名道姓**的话，一致给 `None`。

    ⭐ `TAIL-298` 实测（2026-10-11）：改了 `domain.JC_COLUMNS` 而**没重启服务** ⇒ `/api/m11/list`
       还是旧列清单 ⇒ 钉列/隐藏按 id 找不到列 ⇒ 症状**全在界面上**（列错位、钉列不落），
       看着像界面 bug，白跑一整轮 39 段真机。⇒ 把这类噪声压成一句"去重启"。
    ⚠️ 抽成**纯函数**是为了让它**能被单独证伪**（`tools/mut/_mut_smoke_fresh.py` 就喂两对列表打它）；
       ⛔ 取数（页面 `fetch` ／ 磁盘 `import`）别挪进来 —— 那样它就又要真机才能验。
    """
    if got == want:
        return None
    return (f"⛔ 服务在跑**旧模块**（改后端没重启）：`/api/m11/list` 的列清单前 3 个 = {got[:3]}，"
            f"磁盘上 = {want[:3]}。先跑 `ops\\server_ctl.ps1 -Action restart` 再复核真机 —— "
            "⛔ 别把这轮的红当界面 bug 查，那整片都是假象")


def _freshness(page, errors: list[str]) -> None:
    """真机**前置**：服务在跑的是不是**磁盘上这一份**代码（对不上 ⇒ 后面每段的结论都不可信）。"""
    root = pathlib.Path(__file__).resolve().parents[2]
    try:
        sys.path.insert(0, str(root / "backend"))
        from app.mod11_jc import domain as D                        # noqa: PLC0415
        want = [c["key"] for c in D.JC_COLUMNS]
    except Exception as exc:                                        # ⛔ 读不到就**明说**，别静默当通过
        errors.append(f"真机前置跑不动：磁盘上的 `app.mod11_jc.domain` 读不到（{exc!r}）"
                      " ⇒ 「服务新旧」这一项没核对上")
        return
    got = page.evaluate("async () => ((await (await fetch('/api/m11/list')).json()).columns || [])"
                        ".map(c => c.key)")
    msg = _freshness_error(list(got), want)
    if msg:
        errors.append(msg)
    else:
        print(f"   ✅ 真机前置：服务与磁盘同一份列清单（{len(want)} 列）", flush=True)


def _boot(page) -> None:
    """把壳带起来并等**开屏那一屏**画完 —— `phase != "pre"` 的段都依赖它（见 `_shell_segments.py`）。"""
    page.goto(BASE + "/app", wait_until="load", timeout=45000)
    # ⭐ 等数据到位（⛔ 不用 networkidle，见文件头坑 1）
    page.wait_for_function("() => PJs.length > 0 || NO.length > 0 || BOOT_ERROR", timeout=20000)
    # ⚠️ 等侧栏真的渲染出来再量（`#nav` 初始是空 div、`#ttl` 初始是「—」）——
    #    此前这里**量早了**，打印出的「侧栏项数 = 0 / 顶栏 = —」是**误导**（会把"真没渲染"淹没）。
    page.wait_for_function("() => document.querySelectorAll('#nav .sb-i').length > 0", timeout=20000)
    # ⭐⭐ **先排掉"服务比代码旧"**（`TAIL-298` 收尾加的）：不先排掉，后面整片红都是假象。
    _freshness(page, errors)


def _run_segment(seg, page, errors) -> None:
    """跑一段 —— `entry` 两种形态：**可调用** / `"模块:函数"`（每段一件，见 `_shell_segments.py`）。

    ⚠️ `TAIL-215` 批 2 起**没有**「段函数放在编排件里」这一支 —— ⛔ 别加回来
       （那等于把段代码塞回主件，正是本轮要治的病）。
    """
    entry = seg.entry
    if callable(entry):
        fn = entry
    else:
        mod, _, fname = entry.partition(":")
        fn = getattr(__import__(mod), fname)
    fn(page, errors)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.on("console", lambda m: errors.append(f"[console.{m.type}] {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        # ⭐⭐ 编排 = **遍历 `_shell_segments.SEGMENTS`**（`TAIL-215` 批 1）——
        #    「哪几段 / 什么顺序 / 为什么」**只有那一张表**一处；⛔ 别在这里再写"第几段做什么"。
        #    · `phase="pre"` 的段跑在**开页之前**；第一次遇到非 `pre` ⇒ 先把页面带起来。
        booted = False
        ran: list[str] = []
        for seg in SEGMENTS:
            if seg.phase != "pre" and not booted:
                _boot(page)
                booted = True
            ran.append(seg.id)
            _run_segment(seg, page, errors)

        # ⭐⭐ 把**实际跑过哪几段、什么次序**照实打出来（`TAIL-215` 批 1）——
        #    「少跑了一段 / 顺序被换了」从此**在输出里看得见**（此前只能靠人读全篇）。
        #    ⛔ 别把这行删掉：它是"段数守恒"唯一看得见的证据。
        print(f"\n══ 本跑编排：实际跑了 {len(ran)} 段（注册表 {len(SEGMENTS)} 段）——"
              f"{' · '.join(ran)}")

    print("\n=== console / page 错误 ===")
    if errors:
        for e in errors[:20]:
            print("  ❌", e)
        return 1
    print("  （无）✅")
    return 0


if __name__ == "__main__":
    # ⚠️ **故意不关浏览器**（见文件头坑 2）：`close()` 会挂在驱动连接上 ⇒ 只 flush 后硬退出。
    rc = main()
    sys.stdout.flush()
    os._exit(rc)
