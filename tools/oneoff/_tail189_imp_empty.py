#!/usr/bin/env python
"""`TAIL-189` · **真机**复验（2026-09-29 · 一次性 · ⛔ 只读不开写 · ⛔ 不动任何库数据）。

**为什么要这一遍**：`TAIL-189` 的用户报障是「④ 确认落库**是亮的**、点下去**没反应**；刷新后才是灰的」，
根因是 `needPj` 把「要不要选项目」绑在**候选列表**上 ⇒ 候选为空时闸门整条失灵。
离线判据（`tests/test_imp_shell.py`）只能钉**源码形态**（`const needPj = IMP.hasPj && !IMP.wrap;`），
⭐ 而"**屏幕上那枚按钮到底拦没拦住**"只有真机能证 —— 这正是本脚本要补的那半。

**怎么造出那个状态**（不求人、不改库）：把 `GET /api/imp/*/options` 拦断、**直接喂一个候选为空的回包**
（`{"ok": true, "projects": []}` —— 与 `m06_proc` 在空库上的真实回包同形）。⚠️ 之所以走桩而不去建空库：
① 用户那份测试库里有 13 个项目（是他在跑预演要用的）⇒ ⛔ 不能清；② 起第二个库要多一份 `.env` 与端口，
代价远大于收益；③ 这条链的**唯一变量**就是那一个回包 ✓。

**四个断言**（每条各证一件事）：
  ① **候选为空** ⇒ 那一格**照样画**（⛔ 不静默少一格）＋ **没有可点的空面板**（按钮要么不在、要么置灰）
     ＋ 提示给**真出路**（去「i8 接入层」同步 i8「常用项目列表」）；
  ② 同上状态再真走到 ③ ⇒ **④ 必须置灰** ＋ 提示说清「库里还没有项目档案」
     ⭐ **这是本次报障的正面复现**（改前：④ 亮着、点下去静默）；
  ③ **`ok:false`** ⇒ 页首必须**把原因写出来**（改前：静默当作"这个域没有上下文"
     ⇒ `hasPj` 取不到 ⇒ 闸门**整条失灵**，与本次报障同一族）；
  ④ **放开拦截刷新** ⇒ 正常路（候选非空 ⇒ 按钮可用）**没被改坏**。

⚠️ 本脚本**第一次跑就自曝过两处自己的错**（留痕，别重犯）：① `check()` 的实参顺序写反了
   （把"描述"当成了"结果" ⇒ **失败也印成 ✅** —— 假绿）；② 按"按钮存在"去查"置灰"，
   而空候选那格**本来就不给** `data-act="impPjToggle"`（那正是"没有可点的空面板"）⇒ 查的是错东西。
   ⇒ 真机脚本也必须**先证明自己量的是对的东西**。

用法（工程根 · 默认打 8000）：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail189_imp_empty.py`
   换端口 / 换库：`… _tail189_imp_empty.py --base http://127.0.0.1:8001`
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
OPTIONS = re.compile(r".*/api/imp/[^/]+/options$")

#: 域上下文桩：**候选为空**（`m06_proc` 在空库上的真实回包同形 —— `projects: []` 而非缺键）
STUB_EMPTY = {"ok": True, "projects": [], "warehouse": "", "cutoff_ym": "", "cutoffs": {}}
#: 域上下文桩：取不到（后端 `api_options` 的 `ok:false` 形态）
STUB_FAIL = {"ok": False, "message": "取本域选项失败：本脚本的桩"}

READ_CTX = r"""() => {
  const v = document.querySelector('#view');
  const t = (v.innerText || '');
  const btn = v.querySelector('[data-act="impPjToggle"]');
  const c = v.querySelector('[data-act="impCommit"]');
  return {txt: t,
          hasField: t.includes('这批数据进哪个项目'),
          toggle: !!btn,
          toggleDisabled: !!(btn && btn.disabled),
          toggleLabel: btn ? (btn.innerText || '').trim() : '',
          commit: !!c,
          commitDisabled: !!(c && c.disabled)};
}"""


def check(errors: list[str], tag: str, ok: bool, what: str, extra: str = "") -> None:
    """一条断言一行（✅ / ⛔）—— 与别的探针同一形态。

    ⚠️ 实参顺序 = `(errors, tag, ok, what, extra)`：**`ok` 是布尔、`what` 是那句话**。
    本脚本第一版把两者写反 ⇒ **失败也印成 ✅**（假绿）—— 真机脚本自己也得先证明量的是对的东西。
    """
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

    sys.path.insert(0, str(REPO / "tools" / "probe"))
    from _shell_legacy import _imp_pick, _mk_xlsx            # noqa: PLC0415 —— ⛔ 不复制第二份造表器

    with session_scope() as s:
        admin = UD.active_admins(UR.all_users(s))[0]
        cname, cval = SESS.COOKIE_NAME, SESS.make(admin.name or admin.account)

    scratch = REPO / ".workbuddy" / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    fx = scratch / "tail189_imp_empty.xlsx"
    _mk_xlsx(fx, "m06_proc")

    errors: list[str] = []

    def stub(pg, payload: dict) -> None:
        pg.route(OPTIONS, lambda r: r.fulfill(status=200, content_type="application/json",
                                              body=json.dumps(payload, ensure_ascii=False)))

    def goto_imp(pg) -> None:
        pg.click('[data-k="imp"]')
        pg.wait_for_function("() => VIEW === 'imp'", timeout=15000)
        pg.wait_for_function(
            """() => { const s = document.querySelector('[data-act="impDomain"]');
                       return !!(s && s.options.length && s.value); }""", timeout=15000)

    def pick_domain(pg) -> None:
        """切到 `m06_proc`（它是要项目的域）—— 域上下文是**异步**取的（桩也走这一路）⇒ 条件等。"""
        pg.select_option('[data-act="impDomain"]', "m06_proc")
        pg.wait_for_function(
            """() => { const s = document.querySelector('[data-act="impDomain"]');
                       return s && s.value === 'm06_proc'; }""", timeout=10000)
        pg.wait_for_function("() => (document.querySelector('#view').innerText || '')"
                             ".includes('这批数据进哪个项目')", timeout=10000)

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.context.add_cookies([{"name": cname, "value": cval, "url": base}])
        pg.goto(f"{base}/app", wait_until="load")
        pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)

        try:
            # ── ③ `ok:false` ⇒ 原因必须上屏（改前静默）────────────────────────────
            print("\n③ `ok:false`：取不到域上下文时，页首必须把原因写出来（⛔ 不静默）")
            stub(pg, STUB_FAIL)
            goto_imp(pg)
            pg.select_option('[data-act="impDomain"]', "m06_proc")
            pg.wait_for_timeout(900)
            got_fail = pg.evaluate(READ_CTX)
            check(errors, "③", ("取本域选项失败" in got_fail["txt"]),
                  "取不到时**把原因写在页首**（⛔ 不静默 —— 静默 ⇒ `hasPj` 取不到 ⇒ 闸门整条失灵）",
                  (got_fail["txt"].strip().splitlines() or [""])[0][:90])
            pg.unroute(OPTIONS)

            # ── ①② 候选为空 ⇒ 那一格要画 / 不许有可点空面板 / 给真出路 ⇒ ④ 要拦住 ──
            print("\n①② 候选为空（＝用户报障的那个状态）：一格要画 · 不许有可点空面板 · 给真出路 · ④ 要拦住")
            stub(pg, STUB_EMPTY)
            pg.reload(wait_until="load")
            pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)
            goto_imp(pg)
            pick_domain(pg)
            got1 = pg.evaluate(READ_CTX)
            print(f"   · ① 步实测：有该格 = {got1['hasField']} · `impPjToggle` 在 = {got1['toggle']} "
                  f"· 它的置灰 = {got1['toggleDisabled']}")
            check(errors, "①", got1["hasField"],
                  "「这批数据进哪个项目」那一格**照样画出来**（⛔ 不静默少一格 —— 少了用户以为不用选）")
            m_hint = re.search(r"这个域要先有项目档案[^\n]{0,70}", got1["txt"])
            check(errors, "①", not (got1["toggle"] and not got1["toggleDisabled"]),
                  "**没有「可以点的空面板」**（候选为空时那枚按钮要么不渲染、要么置灰 —— 点开是空的 = 假控件）",
                  f"toggle 在 = {got1['toggle']} · 置灰 = {got1['toggleDisabled']}")
            check(errors, "①", ("i8 接入层" in got1["txt"] and "常用项目列表" in got1["txt"]),
                  "提示给的是**真出路**（去「i8 接入层」同步 i8「常用项目列表」—— 只说「没项目」等于把人堵死）",
                  m_hint.group(0) if m_hint else "（没找到那句指路）")

            # ① → ③：真上传真解析（既有 helper），再看 ④
            _imp_pick(pg, "m06_proc", fx)                # 选域 → 上传 → 解析（② 出来）
            pg.click('[data-act="impPreview"]')          # ② → ③（只读，不写库）
            pg.wait_for_selector('[data-act="impCommit"]', timeout=20000)
            got3 = pg.evaluate(READ_CTX)
            m3 = re.search(r"库里还没有项目档案[^\n]{0,60}", got3["txt"])
            print(f"   · ③ 步实测：④ 在 = {got3['commit']} · 置灰 = {got3['commitDisabled']}")
            check(errors, "②", got3["commitDisabled"],
                  "**④ 确认落库真的置灰**（＝本次报障的正面复现：改前它亮着、点下去没反应）",
                  f"disabled={got3['commitDisabled']}")
            check(errors, "②", m3 is not None,
                  "④ 那侧的提示说清是「库里还没有项目档案」（不是「还没选」—— 两种状态给两条出路）",
                  m3.group(0) if m3 else "（没找到那句话）")

            # ── ④ 放开拦截 ⇒ 正常路没被改坏 ────────────────────────────────────
            print("\n④ 放开拦截后（候选非空）：正常路必须照旧（按钮可用）")
            pg.unroute(OPTIONS)
            pg.reload(wait_until="load")
            pg.wait_for_function("() => typeof VIEW !== 'undefined' && VIEW", timeout=20000)
            goto_imp(pg)
            pick_domain(pg)
            got_ok = pg.evaluate(READ_CTX)
            n_pj = pg.evaluate("async () => ((await (await fetch('/api/imp/m06_proc/options'))"
                               ".json()).projects || []).length")
            print(f"   · 真实候选 {n_pj} 个 · `impPjToggle` 在 = {got_ok['toggle']} "
                  f"· 置灰 = {got_ok['toggleDisabled']}")
            check(errors, "④", bool(n_pj) and got_ok["toggle"] and not got_ok["toggleDisabled"],
                  "候选非空时那枚按钮**可用**（⛔ 改动没把正常路拦死）",
                  f"候选 {n_pj} 个 · 置灰 = {got_ok['toggleDisabled']}")
        except PWError as exc:
            errors.append(f"真机复验中途失败：{type(exc).__name__}: {str(exc)[:200]}")
            print(f"  ⛔ 中途失败：{type(exc).__name__}: {str(exc)[:200]}")
        finally:
            pg.unroute(OPTIONS)
            b.close()
            if fx.exists():
                fx.unlink()                                      # ⛔ 不给 `.workbuddy/scratch` 留垃圾

    print("\n" + ("=== `TAIL-189` 真机复验：全部通过 ===" if not errors
                  else f"=== `TAIL-189` 真机复验：{len(errors)} 项未通过 ==="))
    for e in errors:
        print(f"  ⛔ {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
