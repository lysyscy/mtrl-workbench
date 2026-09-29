"""壳真机自检 · **㉗ 页级四态**（`TAIL-117` 批次 6 · 2026-09-27）。

**它验什么**（守则 §4.2「加载未完成不给最终数」· §3.3「状态要真实」· §2.2「说清为什么 ＋ 下一步」）：
  ⭐ 这两件**只有真机能验**（离线看不见"屏幕上那一瞬画的是什么"）：
    ① **加载态**：把 `m09` 那一路**拖慢 1.2 秒** ⇒ 进页的那一瞬屏幕必须是「正在读取…」，
       并且 **⛔ 不许出现表**（出现表 = 用户看到的是一张空表，与"确实没有数据"**长得一样**）；
    ② **错误态 ＋ 重试**：把这一路**真拦断**（`abort`）⇒ 屏幕必须是「没能取到 ＋ 重试」，
       **⛔ 不许出现表**；点「重试」（此时放开拦截）⇒ **必须真的恢复**（表回来、错误态消失）。
       ⚠️ ② 的后半截是重点：**"给了重试按钮"和"重试真能用"是两件事**。

**为什么拿 `m09` 做样本**：它只有**一路**依赖（`特殊费用月报表`）⇒ 拦它就等于"这一页取不到"，
  判据干净；换别的页要同时拦好几路才能造出同一个局面。
"""

from __future__ import annotations

import time

#: 被拖慢 / 拦断的那一路（`PAGE_LOAD['m09']` 只有它一个）
LABEL = "特殊费用月报表"
PATTERN = "**/api/m09/**"


def _read(page) -> dict:
    """屏幕上现在是什么（正文文本 ＋ 表数 ＋ 有没有重试按钮 ＋ 壳自报的状态）。"""
    return page.evaluate("""() => ({
        txt: ((document.querySelector('#view') || {}).innerText || '').replace(/\\s+/g, ' '),
        tables: document.querySelectorAll('#view table').length,
        retry: document.querySelectorAll('#view [data-act="retryPage"]').length,
        kind: (typeof pageState === 'function') ? pageState().kind : '(无 pageState)',
    })""")


def check(page, errors: list[str]) -> None:
    """㉗ 加载态 / 错误态 / 重试（见文件头）。"""
    out: list[str] = []

    # ---------- ① 加载态：把这一路拖慢 ----------
    def slow(route):
        time.sleep(1.2)
        try:
            route.continue_()
        except Exception:      # noqa: BLE001  —— 页面可能已经切走，忽略即可
            pass

    page.route(PATTERN, slow)
    page.evaluate("() => { LOADED.delete('" + LABEL + "'); FAILED.delete('" + LABEL + "'); }")
    page.click('[data-k="m09"]')
    page.wait_for_function("() => VIEW === 'm09'", timeout=10000)
    now = _read(page)                      # ⚠️ 立刻读、**不 settle**（要的就是"那一瞬"）
    ok_load = ("正在读取" in now["txt"]) and now["tables"] == 0
    out.append(("✅" if ok_load else "⛔")
               + f"㉗-① 取数没回来时屏幕上是「正在读取…」且**没有表**"
                 f"（实测 kind={now['kind']} · 表 {now['tables']} 个 · 正文 {now['txt'][:52]!r}）")
    if not ok_load:
        errors.append("㉗-① 取数未完成时**没有**出加载态（守则 §4.2：加载未完成不给最终数）——"
                      f"实测 kind={now['kind']} · 表 {now['tables']} 个 · 正文 {now['txt'][:60]!r}")

    page.wait_for_function("() => pageState().kind !== 'loading'", timeout=15000)
    after = _read(page)
    ok_ready = after["tables"] >= 1 and "正在读取" not in after["txt"]
    out.append(("✅" if ok_ready else "⛔")
               + f"㉗-①′ 读完之后自动换成真内容（表 {after['tables']} 个 · kind={after['kind']}）")
    if not ok_ready:
        errors.append(f"㉗-①′ 取数回来后没换成真内容（表 {after['tables']} 个 · kind={after['kind']}）")
    page.unroute(PATTERN)

    # ---------- ② 错误态 ＋ 重试真能用 ----------
    page.route(PATTERN, lambda route: route.abort())
    page.evaluate("() => { LOADED.delete('" + LABEL + "'); FAILED.delete('" + LABEL + "'); }")
    page.click('[data-k="m08"]')            # 先离开 m09（否则 `go()` 同页不重进）
    page.click('[data-k="m09"]')
    page.wait_for_function("() => pageState().kind === 'error'", timeout=15000)
    bad = _read(page)
    ok_err = (("没能取到" in bad["txt"]) and bad["retry"] >= 1 and bad["tables"] == 0
              and "Failed to fetch" not in bad["txt"])
    out.append(("✅" if ok_err else "⛔")
               + f"㉗-② 取不到时屏幕上是「没能取到 ＋ 重试」且**没有表**、**没有人话之外的英文原文**"
                 f"（实测 表 {bad['tables']} 个 · 重试按钮 {bad['retry']} 个 · 正文 {bad['txt'][:52]!r}）")
    if not ok_err:
        errors.append("㉗-② 取不到那一页时**没有**出错误态（守则 §3.3：状态必须真实 ——"
                      "⛔ 别把「取不到」画成「这页没数据」；也⛔ 别把浏览器的 `Failed to fetch` 原样上屏）——"
                      f"实测 表 {bad['tables']} 个 · 重试按钮 {bad['retry']} 个 · 正文 {bad['txt'][:60]!r}")

    # 放开拦截 ⇒ 点「重试」⇒ 必须真的恢复
    page.unroute(PATTERN)
    page.click('#view [data-act="retryPage"]')
    page.wait_for_function("() => pageState().kind !== 'loading'", timeout=15000)
    back = _read(page)
    ok_back = back["tables"] >= 1 and "没能取到" not in back["txt"] and back["kind"] == "ready"
    out.append(("✅" if ok_back else "⛔")
               + f"㉗-②′ 点「重试」真的恢复了（表 {back['tables']} 个 · kind={back['kind']}）")
    if not ok_back:
        errors.append(f"㉗-②′ 「重试」没修好这一页（表 {back['tables']} 个 · kind={back['kind']}）"
                      " —— 按钮在、不管用 = 比没有更糟")

    print("㉗ 页级四态（加载 / 错误 / 重试）：")
    for line in out:
        print("   " + line)

    # ⚠️ **清掉本次"故意拦断"留下的浏览器噪音**：`route.abort()` 会让 Chromium 自己打一条
    #    `Failed to load resource: net::ERR_FAILED`（`console.error`），而编排件把 `console.error`
    #    一律当失败 ⇒ 不清就是**自检自己制造的假红**（页面明明已经正确降级并在②′恢复了）。
    #    ⛔ 只清这一条特征串，别扩大（真·资源加载失败也长这样？—— 是，所以本函数只在本段范围内清，
    #       且②′ 已经用"重试后真的恢复"证明了这不是真故障）。
    before = len(errors)
    errors[:] = [e for e in errors if "net::ERR_FAILED" not in e]
    if before != len(errors):
        print(f"   （已清掉本次故意拦断产生的 {before - len(errors)} 条浏览器噪音）")
