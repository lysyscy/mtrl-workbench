"""壳真机自检 · **㉔ 报错人话化**（`TAIL-117` 批次 1 · 2026-09-27 用户裁定"按推荐执行"）。

**它验什么**（只有真机看得见的那一半）：
  ① ⭐ **真造一个 500**：`page.route` 把 `m01` 的导出端点拦成 500 ⇒ 点「导出 Excel（R1）」⇒
     屏幕上那些提示里**不许出现**内部串（`HTTP` / `/api/` / `Error:` / `500`）—— 那是给排查看的
     （守则 §3.1 技术细节不上屏 · §3.7 报错处理硬规则）；
  ② 提示必须**给下一步**（含「重试」或「管理员」）（守则 §2.2 结果可解释）；
  ③ ⭐ **原始串没被丢**：`console.warn` 里必须留下 `→ HTTP 500`
     （守则 §5.8：内部信息要**换地方**——折进 console / 技术明细，⛔ 不是删掉）。

⚠️ **为什么不能只靠离线判据**：`backend/tests/test_ux_errors.py` 钉的是**形态**（出口唯一 / 那一行的写法）；
   "用户屏幕上到底有没有 `HTTP 500`"——**只有真造一次失败**才看得见（本批次之前，屏幕上就是它）。

⚠️ 本机坑（`_shell_smoke.py` 文件头那两条）同样适用；⚠️ 本件**不改数据**（只读 ＋ 拦一个 GET 形态的导出）。
"""

from __future__ import annotations

#: 拦成 500 的端点 = `m01`「项目档案」的导出（`EXP_ROUTES['项目档案']`）
EXPORT = "**/api/m01/projects/export*"
#: 屏幕上**不许**出现的内部串（用户看不懂 / 或会误导）
FORBIDDEN = ("HTTP", "/api/", "Error:", "500", "GET ", "POST ")
#: 提示里**应当**有的"下一步"字样（守则 §2.2）—— ⚠️ 它是**取样**（"有没有给下一步"），
#:   ⛔ 不是"必须出现某个词"：措辞换了（如 `管理员 ⇒ 维护人`）就把新词补进来，⛔ 别为此改文案。
NEXT_HINTS = ("重试", "管理员", "维护人")


def check(page, errors: list[str]) -> None:
    """把导出端点拦成 500 ⇒ 看屏幕上的提示是不是人话、技术串有没有留痕。"""
    from _shell_common import goto

    warns: list[str] = []
    page.on("console", lambda m: warns.append(m.text) if m.type == "warning" else None)

    goto(page, "m01")
    # ⚠️ 先把筛选**重置**回默认（"在建"）：否则别的段改过筛选 ⇒ 行集为空 ⇒
    #    点导出会走"没什么可导的"那条兜底提示 ⇒ 判据**假红**（且看起来像真缺陷）。
    rst = page.locator('#view [data-act="fPjReset"]')
    if rst.count():
        rst.first.click()
        page.wait_for_timeout(300)

    hit_api: list[str] = []

    def _boom(route):
        hit_api.append(route.request.url)
        route.fulfill(status=500, content_type="text/plain", body="Internal Server Error")

    page.route(EXPORT, _boom)
    try:
        btn = page.locator('#view [data-act="exp"][data-t="项目档案"]')
        if btn.count() == 0:
            errors.append("㉔ m01 找不到「导出 Excel」按钮（`data-act=exp` `data-t=项目档案`）"
                          "—— 判据的前提没了（页面改了入口就同批改本件）")
            return
        page.evaluate("() => document.querySelectorAll('.toast').forEach(x => x.remove())")
        before = len(errors)                 # ← 认领"我造的噪音"时只准动这一段（见下方）
        btn.first.click()
        page.wait_for_timeout(1500)          # 等失败提示落地（`dlExport` 会先给一句"正在准备文件"）

        texts = page.evaluate("() => [...document.querySelectorAll('.toast')].map(x => x.innerText)")
        joined = " ⏎ ".join(t for t in texts if t.strip())
        print(f"㉔ 失败提示（真造 500）= {joined[:200]!r}")

        if not hit_api:
            errors.append("㉔ 点了「导出 Excel（R1）」但**没发出**导出请求 —— 判据没走到被测路径"
                          "（多半是行集为空走了兜底提示）⇒ 先修本件的前提，⛔ 别让它静默变绿")
            return
        if not joined:
            errors.append("㉔ 后端返回 500 之后**屏幕上一条提示都没有** —— 用户只会以为「点了没反应」")
            return
        bad = [w for w in FORBIDDEN if w in joined]
        if bad:
            errors.append(f"㉔ 提示里出现**内部串** {bad}（守则 §3.1/§3.7 禁止）—— 原文：{joined[:160]}")
        if not any(k in joined for k in NEXT_HINTS):
            errors.append(f"㉔ 提示没给**下一步**（守则 §2.2：要说清「怎么办」）—— 原文：{joined[:160]}")
        tech = [w for w in warns if "→ HTTP 500" in w]
        if not tech:
            errors.append("㉔ `console.warn` 里没看到技术串（`→ HTTP 500`）—— 排障线索被**删掉**了"
                          "（守则 §5.8：要换地方，不是删掉）")
        else:
            print(f"㉔ 技术明细已留痕（console，不上屏）= {tech[0][:120]!r}")
    finally:
        page.unroute(EXPORT)
        # ⚠️⭐ **这次 500 是本件自己造的** ⇒ 浏览器必然为它打一条
        #    `[console.error] Failed to load resource: … 500`。本件**认领**它 ——
        #    ⛔ 不认领的话，真机裁决永远红（闸门失效：明明是我们自己造的错，却当壳的缺陷报）。
        #    ⚠️ **只认领本件触发之后新增的、且形状对得上的那一条**：
        #       别的 `console.error` 一律照旧上报（⛔ 别写成"把 500 全滤掉"，那会把真缺陷一起藏了）。
        if hit_api:
            for e in list(errors[before:]):
                if e.startswith("[console.error]") and "Failed to load resource" in e and "500" in e:
                    errors.remove(e)
                    print("㉔ 已认领本件自造的 500 噪音（浏览器必然会打的那一条 console.error）")
