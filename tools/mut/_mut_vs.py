#!/usr/bin/env python
"""`TAIL-66` **反向灵敏度**（真机变异）：证明"虚拟滚动阈值 ＋ 焦点护栏"这两条**真有区分力**。

⭐ 为什么必须有本件：新做的机制若不证明"改坏了会被抓住"，它跟没做一样
   （本仓 2026-09-21 的教训：`_mut_boot.py` / `_mut_m03pay.py` 曾**静默崩掉**、无人知道）。

**两个靶**（真机量，改完**逐字节复原** ＋ MD5 校验）：
| 变异 | 怎么改 | 期望 |
|---|---|---|
| A · 摘掉**焦点护栏** | 删掉 `if(!inst.force && vsEditing()){ inst.pending=true; return; }` | 滚动重画 ⇒ **焦点与输入值都被蒸发**（断言失败） |
| B · 把阈值调到 10 万 | `const VS_MIN=400` ⇒ `100000` | m08 **不再虚拟化** ⇒ DOM 行变回全量（>1000） |

⛔⛔ **2026-09-30 实测补记：本件此前是一支「僵尸」** —— 它的靶写在 `index.html` 上，而壳拆件
   （`P4`②）之后那三串（`VS_MIN` / 焦点护栏 / `drawVirtual`）**早就搬进 `shell/view.js` 了**
   ⇒ 一跑就停在"❌ 找不到 `const VS_MIN=400`"，**而它不在任何闸门清单里** ⇒ 没人发现
   （`mut_cover.py` 只查"目标**文件**在不在"，查不出"**靶串**还在不在"）。
   ⇒ 本轮 `P5-c` 正好重写了护栏那一行，一并修好三处：
     ① 靶改到 `shell/view.js`；
     ② 切页改用真机探针那套（裸 `wait_until="networkidle"` 在本壳**永远等不到** ⇒ **静默挂死**，
        见 `_shell_smoke.py` 文件头坑 1）；
     ③ 探针里那句 `drawVirtual(false)` 改成"挑**焦点所在那张表**的实例"（`P5-c` 起 `drawVirtual` 只收实例）。

跑法：`backend/.venv/Scripts/python.exe tools/mut/_mut_vs.py`（rc=0 = 两处都抓到且**逐字节复原**）。
⚠️ 需要壳在跑（`http://localhost:8000/app`）＋ Playwright。⚠️ 同 `_mut_*` 纪律：**独占跑**（别与别的闸门并行）。
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import sys
import time

sys.path.insert(0, str(pathlib.Path(r"D:\dev\mtrl-workbench\backend")))
sys.stdout.reconfigure(encoding="utf-8")

from playwright.sync_api import sync_playwright               # noqa: E402
from app.core.db import session_scope                         # noqa: E402
import app.core.session as SESS                               # noqa: E402
from app.mod15_user.repository import all_users               # noqa: E402

ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
#: ⭐ 靶在**件**里（壳拆件后那三串都搬进了 `shell/view.js` —— 见文件头那条"僵尸"补记）
SHELL_JS = ROOT / "backend" / "app" / "web" / "shell" / "view.js"
GUARD = "  if(!inst.force && vsEditing()){ inst.pending=true; return; }"
MIN400 = "const VS_MIN=400;"
#: ⚠️ 2026-10-01（`TAIL-204` 第 7 步）换落点：原 `.workbuddy/scratch` 是**搬家遗留的旧落点**（盘上一直在、
#:   被 `.gitignore` 藏着），第 7 步已整棵清掉 ⇒ 换到唯一的临时区 `work/00-scratch/`（`T14` 管 TTL）。
BAK = ROOT / ".scratch" / "local" / "view.js.bak-mutvs"
#: ⭐ 切页 / 等这一屏画完**复用真机探针那两件**（⛔ 别在这里再写一份 sleep 版切换：那正是"假绿"的老病）
sys.path.insert(0, str(ROOT / "tools" / "probe"))
from _shell_common import goto as _goto  # noqa: E402


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def run_checks(pg) -> dict:
    """真机量两件事：m08 的 DOM 行数 · m07 的焦点护栏。"""
    # ⚠️⭐ **必须绕开浏览器缓存**：第一版没绕 ⇒ 改了源文件、浏览器还在用**旧的** ⇒ 两处变异"都没抓到"
    #    （**假绿** —— 变异测试最危险的失败方式）。
    # ⚠️ 但⛔ **别用 `wait_until="networkidle"`**：本壳有持续请求 ⇒ 它**永远等不到**（静默挂死，
    #    见 `_shell_smoke.py` 文件头坑 1）⇒ 改成真机探针那套"等到这一屏画完"（`_shell_common.goto`）。
    pg.goto(f"http://localhost:8000/app?_={int(time.time() * 1000)}", wait_until="load", timeout=45000)
    pg.wait_for_function("() => (PJs.length > 0) || (NO.length > 0) || BOOT_ERROR", timeout=20000)
    _goto(pg, "m08")
    rows = pg.evaluate("document.querySelectorAll('#view tbody tr').length")
    #: ⭐ **必须挑对表**：`m07`/`m11` 这类"表里有手填控件"的页要过 `min` 才被认领（它们的行数在阈值下）。
    #: ⚠️⚠️ **`m07` 那张表太小 ⇒ 窗口一帧就把全表装下** ⇒ 第二次 `drawVirtual` 会走"窗口没变 ⇒ 一个字节
    #:    都不动"的早退 ⇒ 护栏**压根没被走到**（2026-09-30 实测：摘掉护栏照样"绿" = **假绿**）。
    #:    ⇒ 改挑「**表体里有可编辑控件 ＋ `.tw` 真能滚**」的那张表，并**先把窗口挪开**（见下面那段）。
    _goto(pg, "m11")
    pg.evaluate("VSCROLL.m11={min:5}; render();"); pg.wait_for_timeout(500)
    guard = pg.evaluate("""() => {
        const cand=VS_TS.filter(x=> x.tb && x.tw
            && (x.tw.scrollHeight - x.tw.clientHeight) > 50
            && x.tb.querySelector('input,select,textarea'));
        if(!cand.length) return {ok:false, why:'这一页没有「表体里有可编辑控件、且自带滚动」的表 —— '
            + '本段**验不了**（⛔ 别静默通过：换个页/调 `min` 再来）', n:VS_TS.length};
        const inst=cand[0];
        const i=inst.tb.querySelector('input,select,textarea');
        i.focus(); if(i.tagName==='INPUT') i.value='12345';
        /* ⚠️ **先把窗口挪开**：不挪 ⇒ 窗口没变 ⇒ `drawVirtual` 早退 ⇒ 这条永远绿（假绿）。
           ⭐ 且这正是**真实路径**：用户就是在表内编辑时往下滚的。 */
        inst.tw.scrollTop=Math.round((inst.tw.scrollHeight - inst.tw.clientHeight) * 0.5);
        drawVirtual(inst);
        const a=document.activeElement;
        return {ok: !!(a && i.isConnected && a===i && String(i.value).includes('12345')),
                tag: a?a.tagName:null, connected:!!i.isConnected,
                v:(a&&a.value!==undefined)?a.value:null, key:inst.key, n:VS_TS.length,
                mid:Math.round(inst.tw.scrollTop)};
    }""")
    pg.evaluate("VSCROLL.m11={off:true}; render();")
    return {"m08_rows": rows, "guard": guard}


def main() -> int:
    orig = SHELL_JS.read_bytes()
    BAK.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SHELL_JS, BAK)
    h0 = md5(orig)
    with session_scope() as s:
        u = all_users(s)[0]
    token = SESS.make(u.account)
    rc = 0
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            pg = b.new_page(extra_http_headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
            pg.context.add_cookies([{"name": getattr(SESS, "COOKIE_NAME", "mw_session"),
                                     "value": token, "url": "http://localhost:8000"}])
            base = run_checks(pg)
            print(f"基线：m08 DOM 行 {base['m08_rows']} · 护栏 {base['guard']}")
            if base["m08_rows"] > 200:
                print("❌ 基线就不对：m08 没被虚拟化（窗口应 <200 行）"); rc = 1
            if not base["guard"].get("ok"):
                print("❌ 基线就不对：护栏没保住焦点"); rc = 1

            # ── 变异 A：摘掉焦点护栏
            t = orig.decode("utf-8")
            if GUARD not in t:
                print("❌ 找不到护栏那一行（代码改过 ⇒ 本变异脚本要同步改）"); return 1
            SHELL_JS.write_text(t.replace(GUARD, "  /* 变异A：护栏已摘掉 */", 1), encoding="utf-8", newline="")
            a = run_checks(pg)
            ok_a = not a["guard"].get("ok")
            print(f"变异A（摘护栏）：护栏 {a['guard']} ⇒ {'✅ 抓到（焦点/值丢了）' if ok_a else '❌ 没抓到'}")
            rc = rc if ok_a else 1
            SHELL_JS.write_bytes(orig)

            # ── 变异 B：阈值调到 10 万
            t = orig.decode("utf-8")
            if MIN400 not in t:
                print("❌ 找不到 `const VS_MIN=400`"); return 1
            SHELL_JS.write_text(t.replace(MIN400, "const VS_MIN=100000;", 1), encoding="utf-8", newline="")
            bb = run_checks(pg)
            ok_b = bb["m08_rows"] > 1000
            print(f"变异B（阈值 10 万）：m08 DOM 行 {bb['m08_rows']} ⇒ "
                  f"{'✅ 抓到（退回全量渲染）' if ok_b else '❌ 没抓到'}")
            rc = rc if ok_b else 1
            SHELL_JS.write_bytes(orig)
            b.close()
    finally:
        SHELL_JS.write_bytes(orig)
    h1 = md5(SHELL_JS.read_bytes())
    same = h1 == h0
    print(f"复原：MD5 {'一致 ✅' if same else '❌ 不一致（' + h0 + ' vs ' + h1 + '）'}")
    if same:
        BAK.unlink(missing_ok=True)
    return rc if same else 1


if __name__ == "__main__":
    sys.exit(main())
