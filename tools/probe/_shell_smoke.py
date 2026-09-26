"""前端壳**运行时自检**（真机加载 `/app`，抓 console / page 错误，断言导航 ＋ `m03` ＋ `m01` 渲染）。

⚠️ 这条自检**不进 `pytest`**（它要浏览器 + 活服务）⇒ 属工程自检（`tools/`），
   与 `tools/_verify_auto.py` 同款定位：**真机才能发现的那类问题**用它抓。

⚠️⚠️ **本机两个必踩的坑（2026-09-17 实测，脚本已规避 —— 别改回去）**：
   1. **`wait_until="networkidle"` 永远等不到**（壳里有持续请求）⇒ 脚本会**静默挂死**。
      改用 `load` ＋ **显式的 `wait_for_function`**（等数据到位）。
   2. **`browser.close()` / `sync_playwright()` 退出时会挂在驱动连接上**
      （`Connection closed while reading from the driver`）⇒ 跑完必须 `os._exit()`，
      **不要**走正常关闭路径。⚠️ 症状极像"脚本没输出"：**空输出 ≠ 通过**。

用法：先起服务，再 `python -u tools/probe/_shell_smoke.py`。
"""

from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

from _shell_pend import check as check_pend   # noqa: E402  ← ⑭ 链路 B「待人工指认」（`TAIL-30`-③）
from _shell_arch import check as check_arch   # noqa: E402  ← ⑮ 链路 A「多仓库选一个」（`TAIL-45`）
from _shell_m02 import check as check_m02     # noqa: E402  ← ⑯ i8 接入层回显/日志（`TAIL-27`）
from _shell_m01type import check as check_type  # noqa: E402  ← ⑰ m01 类型列人工覆盖（`TAIL-42`）
from _shell_ownwh import check as check_ownwh  # noqa: E402  ← ⑱ 链路 C 兜底前查 i8 名单（`TAIL-39`）
from _shell_home import check as check_home    # noqa: E402  ← ⑲ 看板接真数据（`§19` 批 5）

from _shell_exp import check as check_exp        # noqa: E402  ← ⑬ m07 导出（`TAIL-04`）—— 2026-09-21 外移（本文件逼近 600 行红线）
from _shell_legacy import check as check_legacy  # noqa: E402  ← ⑳ 四个暂留件收口的壳内四页（`§19`）
from _shell_m09 import check as check_m09    # noqa: E402  ← ⑪/⑪b m09 特殊费用（2026-09-25 外移：`TAIL-99`）
from _shell_m14 import check as check_m14    # noqa: E402  ← ⑫/⑫b/⑫c m14 规则配置 ＋ 剔除名单卡（同上）

BASE = "http://127.0.0.1:8000"
errors: list[str] = []


def _goto(page, key: str, timeout: int = 15000) -> None:
    """切页并等**这一屏画完**（⛔ 不是睡固定毫秒）—— 实现搬进 `_shell_common.goto`（各件共用一份）。

    ⚠️ 2026-09-26：本函数原先在这里实现，现**移到 `_shell_common.py`** —— 因为 `_shell_m09` /
       `_shell_m14` 也有同样的"切页睡 800 ms"，三处共用一份（⛔ 不再各写一遍，那正是本仓的老病）。
    """
    from _shell_common import goto

    goto(page, key, timeout=timeout)


def _session_cookie() -> tuple[str, str]:
    """造一张「以**在用管理员**身份登录」的会话票 —— 返回 `(cookie 名, 票)`。

    ⭐ 2026-09-21（③ 收紧「未登录不回落首个管理员」之后**必须**补的一步）：
       壳不再"没登录也算管理员"⇒ 不带会话跑本自检，所有**写动作**都会被后端**正当地**拒掉
       （那是我们要的行为）⇒ 那几条链路就没法验了。⇒ 先给浏览器播一张会话票。

    ⚠️ 用**壳自己的** `core/session.make`（⛔ 不硬编码账号/密码，⛔ 不绕开自己的签名）——
       票的载荷 = 那个管理员的**姓名**（与登录页写进 cookie 的东西一致，见 `api_do_login`）。
    ⚠️ 这里**不走登录页**是有意的：登录页 / 验签 / 会话隔离是 `test_acc_usr_login.py` 的事，
       本件只关心**壳的运行时**。
    """
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))
    from app.core import session as SESS
    from app.core.db import session_scope
    from app.mod15_user import domain as D
    from app.mod15_user import repository as R

    with session_scope() as s:
        admin = D.active_admins(R.all_users(s))[0]
        return SESS.COOKIE_NAME, SESS.make(admin.name or admin.account)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.on("console", lambda m: errors.append(f"[console.{m.type}] {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        # ⭐ 先播会话票（见 `_session_cookie` 的注释）—— ⛔ 别删：删了本自检就跑在"未登录"态
        _ck_name, _ck_val = _session_cookie()
        page.context.add_cookies([{"name": _ck_name, "value": _ck_val, "url": BASE}])
        print(f"⓪ 已播种会话票（以在用管理员身份）· cookie={_ck_name}")

        page.goto(BASE + "/app", wait_until="load", timeout=45000)
        # ⭐ 等数据到位（⛔ 不用 networkidle，见文件头坑 1）
        page.wait_for_function(
            "() => PJs.length > 0 || NO.length > 0 || BOOT_ERROR", timeout=20000
        )

        # ⚠️ 等侧栏真的渲染出来再量（`#nav` 初始是空 div、`#ttl` 初始是「—」）——
        #    此前这里**量早了**，打印出的「侧栏项数 = 0 / 顶栏 = —」是**误导**（会把"真没渲染"淹没）。
        page.wait_for_function("() => document.querySelectorAll('#nav .sb-i').length > 0", timeout=20000)
        nav = page.locator("#nav .sb-i").count()
        print(f"① 侧栏项数 = {nav}")
        print(f"② 顶栏 = {page.locator('#ttl').inner_text()[:70]}")

        # 数据层：证明真拉到后端（空库 ⇒ 0 条也是"真的拉到"）
        print(f"③ NO={page.evaluate('NO.length')} 条 · PJs={page.evaluate('PJs.length')} 条"
              f" · BOOT_ERROR={page.evaluate('BOOT_ERROR')!r}")

        # 切到 m03 并断言结构件（对照 ui_parity 的口径）
        _goto(page, "m03")
        dims = page.evaluate("""() => ({
            tables: document.querySelectorAll('#view table').length,
            fbar:   document.querySelectorAll('#view .fbar').length,
            tip:    document.querySelectorAll('#view details.tip').length,
            sum:    document.querySelectorAll('#view tr.sumrow').length,
            pjwrap: document.querySelectorAll('#view .pjwrap').length,
            sortcol:document.querySelectorAll('#view [data-sort-col]').length,
            rows:   document.querySelectorAll('#view tbody tr').length,
            head:   (document.querySelector('#view .card h4')||{}).innerText||'',
        })""")
        print("④ m03 结构件 =", dims)

        # ---- m01 项目档案：接线后应**渲染真数据**（⛔ 不是"页面空着但不报错"）
        _goto(page, "m01")
        m01 = page.evaluate("""() => {
            const rows = [...document.querySelectorAll('#view tbody tr')];
            const cells = rows.map(tr => tr.innerText.replace(/\\s+/g,' ').trim()).slice(0, 3);
            return {
              pjs: PJs.length,
              rows: rows.length,
              empty: document.body.innerText.includes('当前筛选条件下没有项目档案'),
              wiredLabel: document.querySelector('#ttl em').innerText,
              statusSel: [...document.querySelectorAll('#view tbody select[data-act="editStatus"]')]
                            .map(s => s.value).slice(0, 5),
              sample: cells,
            };
        }""")
        print("⑤ m01 =", m01)
        oks = [
            (m01["pjs"] > 0, "PJs 拉到真数据"),
            (m01["rows"] > 0 and not m01["empty"], "列表**真的渲染出行**（状态枚举没转对时会恒空）"),
            ("已接后端" in m01["wiredLabel"], "顶栏说「已接后端真实数据」"),
            (all(v in ("在建", "归档") for v in m01["statusSel"]) and len(m01["statusSel"]) > 0,
             "状态列的 <select> **选中了值**（不是空选）"),
        ]
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m01 自检未通过：" + what)

        # ---- m04 付款计划：结构件在线 ＋ 空库时给**空态**（⛔ 不是"表都没了"）
        _goto(page, "m04")
        m04 = page.evaluate("""() => {
            const pills=[...document.querySelectorAll('#view .pill')].map(x=>x.innerText).join(' | ');
            const m=pills.match(/显示\\s*(\\d+)\\s*条/);
            return {
              plans: PLs.length,
              tables: document.querySelectorAll('#view table').length,
              kpis: document.querySelectorAll('#view .kpi').length,
              rows: document.querySelectorAll('#view tbody tr').length,
              shown: m?Number(m[1]):null,
              wiredLabel: document.querySelector('#ttl em').innerText,
            };
        }""")
        print("⑥ m04 =", m04)
        # ⚠️ `V.m04` **没有空态行**（原型如此）⇒ 不能断言"至少一行"；
        #    改断**筛选条报出的条数 == 数据源条数** —— 这才是"页面真接上了数据源"的可观测证据。
        oks2 = [
            (m04["tables"] >= 1 and m04["kpis"] == 6, "结构件在线（表 ＋ 6 张判定卡）"),
            ("已接后端" in m04["wiredLabel"], "顶栏说「已接后端真实数据」"),
            (m04["shown"] is not None and m04["shown"] == m04["plans"],
             f"筛选条条数 == 数据源条数（{m04['shown']} vs {m04['plans']}）"),
        ]
        for ok, what in oks2:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m04 自检未通过：" + what)

        # ---- m04 手动行（`TAIL-35`）：⭐ 真机验「入口真的能开出草稿行」（**不落库**，验完收起）
        page.click('[data-act="plRowAdd"]')
        # 条件 = **下一步就要读的那个元素**（草稿行的「保存」按钮）—— ⛔ 不是"睡 400 ms 再说"
        page.wait_for_selector('[data-act="plRowSave"]', timeout=8000)
        m04d = page.evaluate("""() => ({
            draft: !!document.querySelector('[data-act="plRowSave"]'),
            setCells: document.querySelectorAll('#view [data-act="plRowSet"]').length,
        })""")
        print("⑥b m04 手动行草稿 =", m04d)
        for ok, what in [
            (m04d["draft"], "⭐ 点「＋ 手动新增计划行」**真的开出草稿行**（接线前只是一句 toast 提示）"),
            (m04d["setCells"] >= 5, f"⭐ 草稿行的可填格已就位（{m04d['setCells']} 格）"),
        ]:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m04 手动行自检未通过：" + what)
        if m04d["draft"]:
            page.click('[data-act="plRowCancel"]')      # ⚠️ 收起草稿 —— **不落库**（写库验证走 curl 那边）
            page.wait_for_selector('[data-act="plRowSave"]', state="detached", timeout=8000)
            print("  ℹ️ 草稿已收起（未落库）")

        # ---- m05 付款流水与欠款：四张 KPI ＋ 三张表；⭐ **KPI 的数必须来自后端**（可观测证据）
        _goto(page, "m05")
        m05 = page.evaluate("""() => {
            const kpis=[...document.querySelectorAll('#view .kpi')].map(x=>x.innerText.replace(/\\s+/g,' '));
            const num=s=>{ const m=String(s).replace(/[^\\d.-]/g,''); return m?Number(m):null; };
            return {
              kpis: kpis.length,
              kpiTotal: kpis.length?num(kpis[0]):null,
              debtTotal: M05.debt?Number(M05.debt.total):null,
              flows: FLs.length, openings: LGs.length,
              tables: document.querySelectorAll('#view table').length,
              wiredLabel: document.querySelector('#ttl em').innerText,
            };
        }""")
        print("⑦ m05 =", m05)
        oks3 = [
            (m05["kpis"] == 4, "四张 KPI（合计 / 辅材 / 机械 / 集采）"),
            (m05["tables"] >= 2, "表在线（按项目欠款 ×2 ＋ 台账 ＋ 流水）"),
            ("已接后端" in m05["wiredLabel"], "顶栏说「已接后端真实数据」"),
            (m05["kpiTotal"] is not None and m05["debtTotal"] is not None
             and abs(m05["kpiTotal"] - m05["debtTotal"]) < 0.01,
             f"⭐ KPI「欠款合计」== 后端 `/api/m05/debt.total`（{m05['kpiTotal']} vs {m05['debtTotal']}）"),
        ]
        for ok, what in oks3:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m05 自检未通过：" + what)

        # ---- ⭐ `#1` 面板**展开 / 收起** round-trip（2026-09-26 补 · 注册表 `PJ_OPEN` 的真机证据）
        # 判词三件（都在**真机**上，⛔ 离线断言看不见）：① 真点「项目」⇒ 面板出现；
        # ② 真点面板**之外** ⇒ 收起（委托层把注册表里所有展开的一起关）；
        # ③ 真点**当前已选中**那个 ⇒ 自动收起（`#1` 新加的行为：面板内选一个就收）。
        # ⚠️ ③ 刻意点**已选中**的那个（`checked`）—— 落库语义不变 ⇒ 不打扰后面几段的取数
        #    （点别的项目会把台账当前项目改掉，m06/m07 那几段读的数就跟着变 ⇒ 那是"自检自己动了数据"）。
        # ⚠️ 用 `.click()`（DOM 原生事件）而不是 `page.mouse`：委托挂在 `document` 上，原生 click
        #    同样**冒泡** ⇒ 走的是同一条委托路径；而它能在一次 `evaluate` 里读完三个状态的中间值。
        pj = page.evaluate("""() => {
            const v = document.querySelector('#view');
            const t = v.querySelector('[data-act="ledPjToggle"]');
            if (!t) return {err: '台账那格的「项目」没有 ledPjToggle'};
            t.click();
            const open = v.querySelectorAll('[data-act="ledPjPick"]').length;
            const picked = [...v.querySelectorAll('[data-act="ledPjPick"]')].find(el => el.checked);
            document.querySelector('#ttl').click();          /* 点面板**之外**（顶栏那行状态） */
            const outside = v.querySelectorAll('[data-act="ledPjPick"]').length;
            let byPick = -1;
            if (picked) { t.click(); picked.click(); byPick = v.querySelectorAll('[data-act="ledPjPick"]').length; }
            return {open: open, outside: outside, byPick: byPick, hasPicked: !!picked};
        }""")
        print("⑦′ 面板 round-trip =", pj)
        oks33 = [
            (not pj.get("err") and pj.get("open", 0) >= 1,
             "真点「项目」⇒ 面板出现（`ledPjToggle` ⇒ `ledPjPick`）" + ("：" + pj["err"] if pj.get("err") else "")),
            (pj.get("outside") == 0, "真点面板**之外** ⇒ 收起（`PJ_OPEN` 注册表全关）"),
            (pj.get("hasPicked") and pj.get("byPick") == 0,
             "真点**已选中**那个 ⇒ 自动收起（`radio` ⇒ 面板自己收）"),
        ]
        for ok, what in oks33:
            print(("  ✅ " if ok else "  ⛔ ") + "⑳′ " + what)
            if not ok:
                errors.append("面板 round-trip 自检未通过：" + what)

        # ---- m08 库存单据与调整单：⭐ **全量行数必须等于后端**（可观测证据；表内渲染随筛选走）
        _goto(page, "m08")
        m08 = page.evaluate("""() => {
            const pill=(document.querySelector('#view .pill')||{}).innerText||'';
            const m=String(pill).match(/(\\d+)\\s*行/);
            return {
              ivs: IVs.length, adjs: ADs.length,
              pill: pill.replace(/\\s+/g,' ').slice(0, 90),
              listed: m ? Number(m[1]) : -1,       /* 筛选条报出的条数 */
              rows: document.querySelectorAll('#view tbody tr').length,
              tables: document.querySelectorAll('#view table').length,
              wiredLabel: document.querySelector('#ttl em').innerText,
              firstDoc: (IVs[0]||{}).docNo||'',
              vsRows: (typeof VS!=='undefined'&&VS)?VS.rows.length:-1,
            };
        }""")
        # ⭐ 虚拟滚动（2026-09-21）：滚到底 ⇒ 合计行必须出现（**只挂窗口 ≠ 丢数据**的可观测证据）
        # ⚠️ 2026-09-25 修（用户报「滚快了下面渲染不出来」）：真容器是**表格外框 `.tw`** ——
        #    `.view` 的 overflow 被 `.tw` 的 max-height 封顶、`scrollTop` 恒 ≈0 ⇒
        #    原先"程序化改 `.view`"是**假动作**（改完窗口根本不该动，却因为监听挂错而"碰巧"过了）。
        #    ⇒ 探针必须滚**真容器**，并让事件真的走一遍（捕获阶段）。
        page.evaluate("""() => {
            const v=document.querySelector('#view');
            const t=v&&v.querySelector('.tw'); const s=(t&&t.scrollHeight>t.clientHeight+1)?t:v;
            s.scrollTop=s.scrollHeight;
            s.dispatchEvent(new Event('scroll'));
        }""")
        # ⚠️⚠️ 自此处起的几处 `wait_for_timeout` **刻意保留、⛔ 不许"顺手统一"成条件等待**（2026-09-26 复核）：
        #    它们量的是「**滚动 / 吸附每个 tick 走多少 px**」—— **时长本身就是测量条件**，
        #    换成条件等待 = 把被测对象换掉（那条判据当场作废）。本文件其余 `wait_for_timeout` 已改为条件等待。
        page.wait_for_timeout(600)
        m08["bottom"] = page.evaluate("""() => {
            const trs=[...document.querySelectorAll('#view tbody tr')];
            const last=trs[trs.length-1]||{};
            return {n:trs.length, txt:(last.innerText||'').replace(/\\s+/g,' ').slice(0,60)};
        }""")
        # ⭐⭐ 2026-09-25 用户报障「库存单据页几乎无法滚动」的**回归护栏**（真机量出来的根因）：
        #    重画时 `$('#view').innerHTML=…` 把 `#view` **整体重建** ⇒ **真容器 `.tw` 跟着被换掉**，
        #    而代码仍把滚动位置还给**已经不挂在 DOM 上的旧节点** ⇒ 每次滚动都被归零
        #    （用户感受 = "滚一下就弹回顶部 / 几乎滚不动"）。
        #    ⚠️ 上面那条「滚到底 ⇒ 合计行在」**抓不到它**：程序化滚到底会命中底部钳制分支 ⇒ 合计行照样出现。
        #    ⇒ 必须**直接量位置**：滚下去之后 `st` 要真的 > 0，且**再滚一格还得动**。
        # ⚠️⚠️ **必须用真滚轮**（`page.mouse.wheel`）：程序化改 `scrollTop` **不算数** ——
        #    2026-09-25 上一版护栏就是程序化的，于是"每滚一下都被重画打断"这个真 bug **照样绿**（假绿）。
        # ⭐⭐ 2026-09-25（`TAIL-94` 重写）：**滚轮断言必须从"非底部"起步**。
        #    上一条已经把「滚到底 ⇒ 合计行在」单独测过了；**贴底时再往下滚本就不该动**（那是正确行为，不是 bug）。
        #    ⚠️ 旧实现"文档总高随实测漂移"会在底部留出多余余量 ⇒ 这三条断言**一直是从假前提上绿过来的**
        #    （总高恒定的重写把它暴露出来）。⇒ 拉回用户的真实手势：**从中段起步往下滚**。
        page.evaluate("""() => {
            const v=document.querySelector('#view');
            const t=v&&v.querySelector('.tw'); const s=(t&&t.scrollHeight>t.clientHeight+1)?t:v;
            s.scrollTop=Math.round(s.scrollHeight*0.25);
            s.dispatchEvent(new Event('scroll'));
        }""")
        page.wait_for_timeout(320)
        box = page.evaluate("""() => { const t=document.querySelector('#view .tw');
            if(!t) return null; const r=t.getBoundingClientRect();
            return {x:r.x+r.width/2, y:r.y+r.height/2}; }""")
        page.mouse.move(box["x"] if box else 640, box["y"] if box else 400)
        # ⚠️ **热身一下**：第一下可能被布局 / 滚动锚定吸收（≠ 被吃掉）⇒ 那一下不计入。
        #    本条断言要抓的是「**每 tick 只剩 ~5px**」那种量级（用户实测过），⛔ 不是抓一次性的首下。
        page.mouse.wheel(0, 300)
        page.wait_for_timeout(320)
        steps = []
        for _ in range(4):
            page.mouse.wheel(0, 300)
            page.wait_for_timeout(250)
            steps.append(page.evaluate("""() => {
                const v=document.querySelector('#view');
                const t=v&&v.querySelector('.tw'); const s=(t&&t.scrollHeight>t.clientHeight+1)?t:v;
                const tr=document.querySelector('#view tbody tr:nth-child(2)');
                return {st:s.scrollTop, first:tr?(tr.innerText||'').replace(/\\s+/g,' ').slice(0,30):''};
            }"""))
        m08["wheel"] = steps
        # ⭐⭐ 2026-09-25 **第二次报障**的护栏：**焦点在筛选框里**时也必须滚得动。
        #    根因 = 焦点护栏判定太宽（`#view` 里任何输入框/下拉框 ⇒ 一律推迟重画）⇒ 点过筛选框后
        #    画面**永久冻结**，而 `st`/滚动条照动 ⇒ 滚轮 / 中键 / 拖滚动条**三种都**表现为"滚不动"。
        #    ⚠️ 必须**复现用户的操作路径**（先点筛选框再滚）—— 前两版护栏都没这一步 ⇒ 假绿两次。
        page.evaluate("""() => { const i=document.querySelector('#view input, #view select'); if(i) i.focus(); }""")
        page.mouse.move(box["x"] if box else 640, box["y"] if box else 400)
        _f = """() => { const tr=document.querySelector('#view tbody tr:nth-child(2)');
            return tr?(tr.innerText||'').replace(/\\s+/g,' ').slice(0,26):''; }"""
        f0 = page.evaluate(_f)
        for _ in range(3):
            page.mouse.wheel(0, 300)
            page.wait_for_timeout(250)
        m08["focus_scroll"] = {"before": f0, "after": page.evaluate(_f)}
        print("⑧ m08 =", {k: v for k, v in m08.items() if k != 'pill'}, "| pill =", m08["pill"])
        oks4 = [
            (m08["tables"] >= 1, "表在线（单据明细总表）"),
            ("已接后端" in m08["wiredLabel"], "顶栏说「已接后端真实数据」"),
            (m08["ivs"] > 0, f"库存单据**全量到手**（{m08['ivs']} 行 —— 后端真数据，不是演示数组）"),
            (m08["vsRows"] == m08["listed"] + 1,
             f"⭐ 虚拟行集 = 筛选条条数 ＋ 合计行（{m08['vsRows']} = {m08['listed']} ＋ 1）"),
            (10 < m08["rows"] < 200,
             f"⭐ 虚拟滚动生效（DOM 只挂窗口 {m08['rows']} 行，≠ 全量 {m08['listed']}）"),
            ("合计" in m08["bottom"]["txt"],
             f"⭐ 滚到底 ⇒ 合计行在（「{m08['bottom']['txt']}」—— 虚拟化不丢数据）"),
            (m08["wheel"][-1]["st"] > m08["wheel"][0]["st"]
             and len({x["first"] for x in m08["wheel"]}) > 1,
             f"⭐⭐ **真滚轮滚得动**（4 下：st {m08['wheel'][0]['st']} → {m08['wheel'][-1]['st']}，"
             f"首行内容换了 {len({x['first'] for x in m08['wheel']})} 种）—— 用的必须是**真手势**"
             "（`mouse.wheel`）；程序化 `scrollTop` 抓不到「重画打断手势」这类 bug"),
            # ⚠️ 门槛 60%：实测"偶发吸收一下"≈25%（4 下走 900px），而本条要抓的是**每 tick 只剩 ~5px**
            #    （≈95% 丢失，用户实测过）⇒ 60% 既足以证伪那种量级，又不误伤噪声。⛔ 别为了变绿而继续放宽。
            (m08["wheel"][-1]["st"] - m08["wheel"][0]["st"] >= 300 * 4 * 0.6,
             f"⭐⭐⭐ **滚轮量没被吃掉**（4 下 × 300px ⇒ 实际走了 "
             f"{m08['wheel'][-1]['st'] - m08['wheel'][0]['st']}px，≥ 60% 才算正常）—— "
             "用户实测过的症状：每 tick 只剩 ~5px（滚 5~6 次才走一行），根因 = 每次滚动都重建 `#view`"),
            (m08["focus_scroll"]["after"] != m08["focus_scroll"]["before"],
             f"⭐⭐⭐ **焦点在筛选框里也滚得动**（先点 `#view` 里的筛选框再滚：首行 "
             f"「{m08['focus_scroll']['before']}」→「{m08['focus_scroll']['after']}」）—— "
             "点过筛选框后画面**永久冻结**（焦点护栏判得太宽）就是这个 bug；⛔ 这条必须走**用户的操作路径**"),
        ]
        for ok, what in oks4:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m08 自检未通过：" + what)

        # ---- m06 过程资料：机械源已接后端 ⇒ ⭐ **`procPj` 必须有值**（证明「加载时求值」的坑已修）
        _goto(page, "m06")
        m06 = page.evaluate("""() => ({
            mach6Wh: Object.keys(MACH6).length,
            ivs: IVs.length,
            procPj: (typeof procPj === 'string') ? procPj : String(procPj),
            pjCands: (typeof PROC_PJS === 'object' && PROC_PJS) ? PROC_PJS.length : -1,
            tabs: document.querySelectorAll('#view .tb2').length,
            tables: document.querySelectorAll('#view table').length,
            mechEntry: !!document.getElementById('mechEntry'),
            wiredLabel: document.querySelector('#ttl em').innerText,
        })""")
        print("⑨ m06 =", m06)
        oks5 = [
            (m06["tables"] >= 1 and m06["tabs"] == 3, "三张表签（表① / 表② / 差异表）＋ 表在线"),
            ("已接后端" in m06["wiredLabel"], "顶栏说「已接后端真实数据」"),
            (m06["ivs"] > 0, f"材料侧取数已通（库存单据 {m06['ivs']} 行）"),
            (bool(m06["procPj"]) and m06["pjCands"] > 0,
             f"⭐ 项目候选已落定（procPj={m06['procPj'][:18]!r} · 候选 {m06['pjCands']} 个）"
             " —— 若仍是「加载时求值」，这里会是空的"),
            (m06["mechEntry"],
             "⭐ `TAIL-38`「录机械费」入口已在页面上（`BIND.m06` 注入 —— 原型没画，§5.2.5 ③ 自行设计）"),
        ]
        for ok, what in oks5:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m06 自检未通过：" + what)

        # ---- m07 收发结存与活动大表：读全量 ＋ 提取 ＋ 大表
        #      ⭐ 可观测证据 = **表内渲染行数 == 后端给出的行数 ＋ 合计行**（同 m08 的口径）
        _goto(page, "m07")
        m07 = page.evaluate("""() => {
            const rows = whRows(fWhYm);
            const tbls = [...document.querySelectorAll('#view table')];
            const first = tbls[0] ? tbls[0].querySelectorAll('tbody tr').length : 0;
            return {
              ym: fWhYm, wh: rows.length, whRows: first,
              big: BIGSET.length, bigRows: bigRows(bjMonth(-1)).length,
              extKinds: Object.keys(EXTM).length,
              manMons: Object.keys(BIGVAL).length,
              matOk: MAT_OK,
              tables: tbls.length,
              wiredLabel: document.querySelector('#ttl em').innerText,
            };
        }""")
        print("⑩ m07 =", m07)
        oks6 = [
            (m07["tables"] >= 3, "三张表在线（收发结存 ＋ 焊材/气体提取 ＋ 活动大表）"),
            ("已接后端" in m07["wiredLabel"], "顶栏说「已接后端真实数据」"),
            (m07["whRows"] == m07["wh"] + 1,
             f"⭐ 收发结存表内渲染 == 后端行数 ＋ 合计行（{m07['whRows']} = {m07['wh']} ＋ 1）"),
            (m07["big"] > 0 and m07["bigRows"] == m07["big"],
             f"⭐ 大表行数 == 后端选题数（{m07['bigRows']} vs {m07['big']}）"
             " —— 若 `BIGSET` 没接后端，这里会是演示的 8 行"),
            (m07["matOk"] is True,
             "⭐ 「主材累计」取数口**已接入**（`TAIL-25` · 后端 `mat_available=True`）⇒ 该列显**真数**而非「—」"),
        ]
        for ok, what in oks6:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m07 自检未通过：" + what)

        # ---- ⭐ 2026-09-18（用户裁定「甲」）提取表「结余」列：列 +1 ｜ 每行一个可编辑格 ｜ 值 == 后端
        #      ⚠️ **本段只读** —— 写路径的真机验证走 `tools/_e2e_m07bal.py`（冒烟脚本不写库、可反复跑）。
        m07b = page.evaluate("""async () => {
            const be = await (await fetch('/api/m07/extract')).json();
            const tbl = [...document.querySelectorAll('#view table')]
                          .find(t => t.dataset.sortKey === 'm07:kinds');
            if (!tbl) return {found: false};
            const ths = [...tbl.querySelectorAll('thead th')].map(x => x.innerText.trim());
            const ins = [...tbl.querySelectorAll('td input[data-act="extBal"]')];
            const bad = [];
            ins.forEach(i => {
              const b = ((be.balances || {})[i.dataset.k] || {})[i.dataset.p];
              const want = (b == null) ? '' : String(Number(b));
              if (String(i.value) !== want) {
                bad.push(i.dataset.k + '|' + i.dataset.p + ': ' + i.value + ' ≠ ' + want);
              }
            });
            return {found: true, ths: ths, n: ins.length, bad: bad,
                    empty: !!tbl.querySelector('tbody td[colspan]')};
        }""")
        print("⑩b m07 结余列 =", m07b)
        oks7 = [
            (bool(m07b.get("found")) and len(m07b.get("ths") or []) == 5
             and "结余" in "".join(m07b.get("ths") or []),
             f"⭐ 「结余」列就位（表头 5 列）：{m07b.get('ths')}"),
            (m07b.get("n", 0) >= 1 or m07b.get("empty"),
             "⭐ 每个数据行都有可编辑的「结余」格（该筛选下没有数据时如实给空态行）"),
            (m07b.get("bad") == [],
             f"⭐ 页面结余格逐格 == 后端 `balances`（未录入 ⇒ 空）：{m07b.get('bad')}"),
        ]
        for ok, what in oks7:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m07 结余列自检未通过：" + what)

        # ---- m09 特殊费用月报表（`MOD-09`）—— 页面的数 == 当场重取后端的数 ＋ 演示容器已消失 ＋
        #      **写路径净零往返**（点「＋ 增加手填项」真落库 ⇒ 点「删除」回到原样），挪 `_shell_m09.py`。
        check_m09(page, errors)

        # ---- m14 规则配置（`MOD-14`）—— 规则条数/类别/来源/卡头 == 后端 ＋ **写路径净零往返**（id 差集）
        #      ＋ ⭐ ⑫c 集采剔除名单卡：加入按钮**真点** ⇒ 空名早退（零残留），挪 `_shell_m14.py`。
        check_m14(page, errors)

        # ---- m07 导出（`TAIL-04`）：**从页面上下文真拉一次 zip**（默认月 ＋ 有数据的月，两态都验）。
        #      ⚠️ 这一段自己七十多行 ⇒ 挪 `_shell_exp.py`：本文件有 **400 行即黄**（`doc_audit` 的 `T5`）；⚠️ 连 `>600` 也只是**黄** —— `[用户·2026-09-21]` 把"红·禁合入"**降级**，只须在 `ops/阈值表.md` 登记"为什么不拆"。
        check_exp(page, errors)

        # ---- ⑭ m01 链路 B「待人工指认」（`TAIL-30`-③）——
        #      ⚠️ 这一段自己一百多行（**真造库样本 ＋ 真点弹窗 ＋ 复原**）⇒ 挪到 `_shell_pend.py`：
        #         本文件有 **400 行即黄**（`doc_audit` 的 `T5`）；⚠️ 连 `>600` 也只是**黄** —— `[用户·2026-09-21]` 把"红·禁合入"**降级**，只须在 `ops/阈值表.md` 登记"为什么不拆"。
        check_pend(page, errors)

        # ---- ⑮ m01 链路 A ③-b「多仓库 ⇒ 选一个建行」（`TAIL-45`）—— 同上，挪 `_shell_arch.py`。
        check_arch(page, errors)

        # ---- ⑯ m02 i8 接入层（`TAIL-27`）—— 两张卡读真执行记录 ＋ 同步确认弹窗（只看不点），挪 `_shell_m02.py`。
        check_m02(page, errors)

        # ---- ⑰ m01 类型列人工覆盖（`TAIL-42`）—— 类型格可点 ＋ 弹窗口径 ＋ 只看不点，挪 `_shell_m01type.py`。
        check_type(page, errors)

        # ---- ⑱ 链路 C「兜底前先查 i8 仓库名单」（`TAIL-39`）—— 入口在 ＋ 二次确认在 ＋ 没查过被拦，挪 `_shell_ownwh.py`。
        check_ownwh(page, errors)

        # ---- ⑲ 看板接真数据（`§19` 批 5）—— 8 项待办 ＋ 三个记账数与后端对齐 ＋ 那句假话已不在，挪 `_shell_home.py`。
        check_home(page, errors)

        # ---- ⑳ 四个暂留件收口（`§19` · 2026-09-21）—— 设置 ＋ 三个历史导入：四页渲染 ＋
        #      **无死控件**（真机版的 `data-act`/`CHG` 守卫）＋ 页内容是后端的，挪 `_shell_legacy.py`。
        check_legacy(page, errors)

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
