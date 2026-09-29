#!/usr/bin/env python
"""`TAIL-190` · **真机**复验（2026-09-29 · 一次性 · ⛔ 不碰 i8 · ⛔ 只读）。

**为什么要有这一遍**：`TAIL-190` 的病是「同步回执说有 2 条待人工、而 `m01` 那张卡是空的」——
离线判据只能钉**源码形态**（`if (ARCP.length || ARCP_ERR || ARCP_DROP.length)` 这种），
⭐ 而"**卡片到底画没画出来、上面写了什么**"只有真机说了算。

**怎么造状态**（⛔ 不碰 i8 —— 同步会**登录并顶号**（`D9`）⇒ 一律走桩）：
  · `GET /api/m01/archive-pending` 喂 `dropped_items`（清单空 ＋ 有丢掉条目）⇒ 看**卡片还出不出**；
  · `POST /api/m02/sync/common-projects` 喂 `SyncOut`（`待人工 2 条（多仓库 0 · 壳下小微 2）`）
    ⇒ 点一遍**二次确认**（真的走那条 UI 路）⇒ 看**回执有没有把两类分开说**。

**五条断言**：
  ① 清单空 ＋ 有丢掉条目 ⇒ **卡片必须出现**（改前：整张卡都不出现 = 报障现场 ✗）；
  ② 丢掉的那几条**逐条列出来** ＋ 说清**为什么**与**该去哪**（建单向导）＋ 写明"不是报错"；
  ③ **真实数据**（放开拦截）⇒ 卡片出现且写出"另有 2 条不属本卡"（＝用户现在能看到的东西）；
  ④ 回执里「多仓库 0 条」时 ⛔ **不许**再冒出「一个全名挂多个仓库…去 m01」那句（改前就是这么写的 ✗）；
  ⑤ 回执里**壳下小微那类要指去建单向导**（`m03`）。

用法（工程根 · 默认打 8000）：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail190_arch_card.py`
   换端口 / 换库：`… _tail190_arch_card.py --base http://127.0.0.1:8001`
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from playwright.sync_api import Error as PWError
from playwright.sync_api import sync_playwright

REPO = pathlib.Path(__file__).resolve().parents[2]
ARCH = re.compile(r".*/api/m01/archive-pending.*")
SYNC = re.compile(r".*/api/m02/sync/common-projects.*")

#: 卡片那一路的桩：**清单空** ＋ 两条丢掉（＝报障时后端真会回的形状，见 `_b_diag_archive_pending.py`）
STUB_ARCH = {
    "found": True, "items": [], "dropped": 1,
    "dropped_items": [{
        "full_name": "第四工程公司2026年小微项目(TBLX2026070003)",
        "why": "shell_small",
        "why_text": "它是「壳下具体小微」（壳已在档，但它名下的仓库还没建行）—— 要的是「出现在单据名里」的"
                    "**关键词**，出路是**建档向导**（m03 里遇到该壳时选小微／补词），⛔ 不是在这里选仓库"
                    " ⇒ **不属本卡**",
        "reason": "壳已在档，但壳下具体小微（1 个仓库：兰考金不换前置车间项目）需配关键词 —— 走建档向导人工建",
    }],
    "source": {"target": "常用项目列表", "at": "2026-09-29 15:13:02", "run_record_id": 2},
}
#: 回执那一路的桩：`counts` 带**拆数**（多仓库 0 · 壳下小微 2 ⇒ 正是用户那次同步的数）
STUB_SYNC = {
    "table": "common_project", "count": 5, "sample": [], "degraded": False,
    "message": "建档 5 条 · 已在档案 11 条 · 待人工 2 条（多仓库 0 · 壳下小微 2） · 缺 phid 0 条",
    "counts": {"create": 5, "exists": 11, "manual": 2, "no_phid": 0,
               "manual_multi": 0, "manual_shell": 2},
}


def check(errors: list[str], tag: str, ok: bool, what: str, extra: str = "") -> None:
    """一条断言一行 —— ⚠️ 实参顺序 `(errors, tag, ok, what, extra)`：`ok` 是布尔、`what` 是那句话。"""
    print(("  ✅ " if ok else "  ⛔ ") + f"{tag} {what}" + (f"：{extra}" if extra else ""))
    if not ok:
        errors.append(f"{tag} {what}" + (f"（{extra}）" if extra else ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="已起好的实例（默认 8000）")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    sys.path.insert(0, str(REPO / "backend"))
    from app.core import session as SESS                     # noqa: PLC0415
    from app.core.db import session_scope                    # noqa: PLC0415
    from app.mod15_user import domain as UD                  # noqa: PLC0415
    from app.mod15_user import repository as UR              # noqa: PLC0415

    with session_scope() as s:
        admin = UD.active_admins(UR.all_users(s))[0]
        cname, cval = SESS.COOKIE_NAME, SESS.make(admin.name or admin.account)

    errors: list[str] = []

    def stub(pg, pattern, payload) -> None:
        pg.route(pattern, lambda r: r.fulfill(status=200, content_type="application/json",
                                              body=json.dumps(payload, ensure_ascii=False)))

    def goto_m01(pg) -> None:
        pg.click('[data-k="m01"]')
        pg.wait_for_function("() => VIEW === 'm01'", timeout=15000)
        # ⚠️ 卡片是**取数回来之后**注入的（`reloadArchPend` ⇒ `BIND.m01`）⇒ 等它出现；
        #    改前这里**等不到**（清单空 ⇒ 不画）——那正是本脚本①要抓的事，所以**不抛异常**、交断言报。
        try:
            pg.wait_for_selector("#archBox", timeout=8000)
        except PWError:
            pass

    def arch_text(pg) -> str:
        return pg.evaluate("() => { const b = document.getElementById('archBox');"
                           " return b ? (b.innerText || '').replace(/\\s+/g, ' ') : ''; }")

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.context.add_cookies([{"name": cname, "value": cval, "url": base}])
        pg.goto(f"{base}/app", wait_until="load")
        pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)

        try:
            # ── ①② 清单空 ＋ 有丢掉条目 ⇒ 卡片必须出现并把话说清 ──────────────────
            print("\n①② 清单空但「有丢掉的那几条」（＝报障现场）：卡片必须出现 ＋ 逐条说清")
            stub(pg, ARCH, STUB_ARCH)
            goto_m01(pg)
            txt = arch_text(pg)
            check(errors, "①", bool(txt), "卡片**出现**了（改前：清单空 ⇒ 连卡片都不画 ＝ 用户看到的「空」）",
                  (txt[:90] or "（`#archBox` 不存在）"))
            check(errors, "②", ("不属这张卡" in txt or "不属本卡" in txt), "写明了「有几条不属本卡」")
            check(errors, "②", "建档向导" in txt, "丢掉的理由指了**真出路**（建单向导）")
            check(errors, "②", "第四工程公司2026年小微项目" in txt, "把丢掉的那一条**名字**也列出来了")
            check(errors, "②", "不是" in txt and "报错" in txt, "写明「卡里没有它们 ≠ 报错」（否则用户以为系统坏了）")

            # ── ③ 真实数据（放开拦截）⇒ 现在这条库上应有的样子 ──────────────────
            print("\n③ 真实数据（放开拦截）：用户现在刷新 `m01` 应看到的样子")
            pg.unroute(ARCH)
            pg.reload(wait_until="load")
            pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)
            goto_m01(pg)
            rtxt = arch_text(pg)
            check(errors, "③", bool(rtxt) and "不属本卡" in rtxt,
                  "真实数据下卡片出现且写出「另有 N 条不属本卡」", (rtxt[:110] or "（卡片不存在）"))

            # ── ④⑤ 回执：多仓库 0 时不许再指 m01；壳下小微要指建单向导 ──────────
            print("\n④⑤ 同步回执（走桩 ＋ 真的点一遍二次确认）：两类要分开说")
            stub(pg, SYNC, STUB_SYNC)
            pg.evaluate("() => ACT.syncPj()")                     # 打开二次确认弹窗（⛔ 不确认不发请求）
            pg.wait_for_selector('[data-act="m02SyncOk"]', timeout=8000)
            pg.click('[data-act="m02SyncOk"][data-which="common-projects"]')
            pg.wait_for_function("""() => { const r = document.querySelector('#modalRoot');
                return !!(r && /多仓库|待人工/.test(r.innerText || '')); }""", timeout=15000)
            mtxt = pg.evaluate("() => { const r = document.querySelector('#modalRoot');"
                               " return r ? (r.innerText || '').replace(/\\s+/g, ' ') : ''; }")
            print(f"   · 回执实测：{mtxt[:160]}")
            check(errors, "④", "一个全名挂多个仓库" not in mtxt,
                  "「多仓库 0 条」时⛔ 不再冒出「一个全名挂多个仓库…去 m01」那句（改前就是这么写的）")
            check(errors, "⑤", ("壳下小微" in mtxt and "建档向导" in mtxt),
                  "「壳下小微」那类**指去了建单向导**（而不是 m01 那张卡）")
        except PWError as exc:
            errors.append(f"真机复验中途失败：{type(exc).__name__}: {str(exc)[:200]}")
            print(f"  ⛔ 中途失败：{type(exc).__name__}: {str(exc)[:200]}")
        finally:
            pg.unroute(ARCH)
            pg.unroute(SYNC)
            b.close()

    print("\n" + ("=== `TAIL-190` 真机复验：全部通过 ===" if not errors
                  else f"=== `TAIL-190` 真机复验：{len(errors)} 项未通过 ==="))
    for e in errors:
        print(f"  ⛔ {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
