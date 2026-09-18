"""前端壳**运行时自检**（真机加载 `/app`，抓 console / page 错误，断言导航 ＋ `m03` ＋ `m01` 渲染）。

⚠️ 这条自检**不进 `pytest`**（它要浏览器 + 活服务）⇒ 属工程自检（`tools/`），
   与 `tools/_verify_auto.py` 同款定位：**真机才能发现的那类问题**用它抓。

⚠️⚠️ **本机两个必踩的坑（2026-09-17 实测，脚本已规避 —— 别改回去）**：
   1. **`wait_until="networkidle"` 永远等不到**（壳里有持续请求）⇒ 脚本会**静默挂死**。
      改用 `load` ＋ **显式的 `wait_for_function`**（等数据到位）。
   2. **`browser.close()` / `sync_playwright()` 退出时会挂在驱动连接上**
      （`Connection closed while reading from the driver`）⇒ 跑完必须 `os._exit()`，
      **不要**走正常关闭路径。⚠️ 症状极像"脚本没输出"：**空输出 ≠ 通过**。

用法：先起服务，再 `python -u tools/_shell_smoke.py`。
"""

from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"
errors: list[str] = []


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        page.on("console", lambda m: errors.append(f"[console.{m.type}] {m.text}")
                if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        page.goto(BASE + "/app", wait_until="load", timeout=45000)
        # ⭐ 等数据到位（⛔ 不用 networkidle，见文件头坑 1）
        page.wait_for_function(
            "() => PJs.length > 0 || NO.length > 0 || BOOT_ERROR", timeout=20000
        )

        nav = page.locator("#nav .sb-i").count()
        print(f"① 侧栏项数 = {nav}")
        print(f"② 顶栏 = {page.locator('#ttl').inner_text()[:70]}")

        # 数据层：证明真拉到后端（空库 ⇒ 0 条也是"真的拉到"）
        print(f"③ NO={page.evaluate('NO.length')} 条 · PJs={page.evaluate('PJs.length')} 条"
              f" · BOOT_ERROR={page.evaluate('BOOT_ERROR')!r}")

        # 切到 m03 并断言结构件（对照 ui_parity 的口径）
        page.click('[data-k="m03"]')
        page.wait_for_timeout(600)
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
        page.click('[data-k="m01"]')
        page.wait_for_timeout(600)
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
        page.click('[data-k="m04"]')
        page.wait_for_timeout(600)
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
        page.wait_for_timeout(400)
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
            page.wait_for_timeout(300)
            print("  ℹ️ 草稿已收起（未落库）")

        # ---- m05 付款流水与欠款：四张 KPI ＋ 三张表；⭐ **KPI 的数必须来自后端**（可观测证据）
        page.click('[data-k="m05"]')
        page.wait_for_timeout(700)
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

        # ---- m08 库存单据与调整单：⭐ **全量行数必须等于后端**（可观测证据；表内渲染随筛选走）
        page.click('[data-k="m08"]')
        page.wait_for_timeout(700)
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
            };
        }""")
        print("⑧ m08 =", m08)
        oks4 = [
            (m08["tables"] >= 1, "表在线（单据明细总表）"),
            ("已接后端" in m08["wiredLabel"], "顶栏说「已接后端真实数据」"),
            (m08["ivs"] > 0, f"库存单据**全量到手**（{m08['ivs']} 行 —— 后端真数据，不是演示数组）"),
            (m08["listed"] >= 0 and m08["rows"] == m08["listed"] + 1,
             f"表内渲染 = 筛选条报出的条数 ＋ 合计行（{m08['rows']} = {m08['listed']} ＋ 1）"),
        ]
        for ok, what in oks4:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m08 自检未通过：" + what)

        # ---- m06 过程资料：机械源已接后端 ⇒ ⭐ **`procPj` 必须有值**（证明「加载时求值」的坑已修）
        page.click('[data-k="m06"]')
        page.wait_for_timeout(700)
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
        page.click('[data-k="m07"]')
        page.wait_for_timeout(800)
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
            (m07["matOk"] is False,
             "⭐ 「主材累计」取数口未接入（后端 `mat_available=False`）⇒ 该列显「—」而非 0"),
        ]
        for ok, what in oks6:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m07 自检未通过：" + what)

        # ---- m09 特殊费用月报表：⭐ 可观测证据 = **页面的数 == 当场重取后端的数** ＋ 演示容器已消失
        #      ⚠️ **只读**：写动作（增/改/删）的真机验证走 curl（见 `TAIL-27` 的收尾记录），
        #         这里**不写库** —— 冒烟脚本要能被反复跑，不留下残留数据。
        page.click('[data-k="m09"]')
        page.wait_for_timeout(800)
        m09 = page.evaluate("""async () => {
            const q = (ym, pj) => '/api/m09/fee?ym=' + encodeURIComponent(ym || '')
              + '&pj=' + encodeURIComponent(pj || '');
            const fetchBe = async (ym, pj) => (await (await fetch(q(ym, pj))).json());
            const tbls = [...document.querySelectorAll('#view table')];
            const tbl = tbls[0] || null;
            const be0 = await fetchBe(awfYm, awfPj);
            const out = {
              ym: awfYm, proj: awfPj,
              pjCands: AWF_PJS.length, beCands: (be0.projects || []).length,
              rows: AWF_ROWS.length, beManuals: (be0.manuals || []).length,
              total: AWF_TOTAL, beTotal: Number(be0.total),
              auto: AWF_AUTO, beAuto: Number(be0.auto && be0.auto.amount),
              demoGone: (typeof AWF === 'undefined'),
              tables: tbls.length,
              tbody: tbl ? tbl.querySelectorAll('tbody tr').length : 0,
              amtCells: tbl ? tbl.querySelectorAll('tbody input[data-act="awfAmt"]').length : 0,
              wiredLabel: document.querySelector('#ttl em').innerText,
            };
            /* ⭐ 换一个**非默认**项目 ⇒ 页面必须跟着后端走（证明"选得到的就取得到"） */
            const other = AWF_PJS[AWF_PJS.length - 1];
            if (other && other !== awfPj) {
              awfPj = other; await reloadM09();
              const be1 = await fetchBe(awfYm, awfPj);
              out.switched = { pj: awfPj, beProj: be1.project, total: AWF_TOTAL, beTotal: Number(be1.total) };
            }
            /* ⭐ 给一个**后端不认**的项目 ⇒ 归一化必须由后端做（壳里不许各写一份兜底） */
            awfPj = '__no_such_project__'; await reloadM09();
            const be2 = await fetchBe(awfYm, '');
            out.bogus = { pj: awfPj, beProj: be2.project };
            if (other) { awfPj = other; await reloadM09(); }
            return out;
        }""")
        print("⑪ m09 =", m09)
        sw = m09.get("switched") or {}
        bg = m09.get("bogus") or {}
        oks7 = [
            (m09["tables"] >= 1 and m09["tbody"] >= 3, "表在线（自动项 ＋ 手填项 ＋ 合计）"),
            ("已接后端" in m09["wiredLabel"], "顶栏说「已接后端真实数据」"),
            (m09["demoGone"], "⭐ 演示容器 `AWF` **真的没了**（`typeof AWF === 'undefined'`）"),
            (m09["pjCands"] > 0 and m09["pjCands"] == m09["beCands"],
             f"⭐ 项目候选 == 后端（{m09['pjCands']} vs {m09['beCands']}）"
             " —— 若仍是「加载时求值」，这里会是 0"),
            (m09["rows"] == m09["beManuals"] and m09["amtCells"] == m09["beManuals"],
             f"⭐ 手填行数 == 后端 `manuals`（{m09['rows']} vs {m09['beManuals']}；表内输入格 {m09['amtCells']}）"),
            (abs((m09["total"] or 0) - m09["beTotal"]) < 0.01
             and abs((m09["auto"] or 0) - m09["beAuto"]) < 0.01,
             f"⭐ 自动项 / 合计 == 后端（自动 {m09['auto']} vs {m09['beAuto']}；"
             f"合计 {m09['total']} vs {m09['beTotal']}）"),
            (bool(sw) and sw.get("pj") == sw.get("beProj")
             and abs((sw.get("total") or 0) - (sw.get("beTotal") or 0)) < 0.01,
             f"⭐ 切到非默认项目后仍与后端一致（{sw.get('pj', '')[:16]!r} "
             f"· 合计 {sw.get('total')} vs {sw.get('beTotal')}）"),
            (bool(bg) and bg.get("pj") == bg.get("beProj") and bool(bg.get("beProj")),
             f"⭐ 后端不认的项目被**后端**归一成候选第一个（{bg.get('pj', '')!r} → {bg.get('beProj', '')[:16]!r}）"),
        ]
        for ok, what in oks7:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m09 自检未通过：" + what)

        # ⭐ 写路径**真机往返**：点「＋ 增加手填项」⇒ 真的多一行；点「删除」⇒ 回到原样。
        #    ⚠️ **净零**（一增一删，先后端都落库过）⇒ 脚本可反复跑、不留残留；
        #       若中途失败，下面的 `after == before` 会当场报 ⛔（不留着不管）。
        m09w = page.evaluate("""async () => {
            const before = AWF_ROWS.length;
            const btn = document.querySelector('#view [data-act="awfAdd"]');
            if (!btn) return { ok: false, why: '找不到「＋ 增加手填项」按钮' };
            btn.click();
            await new Promise(r => setTimeout(r, 1000));
            const added = AWF_ROWS.length;
            const dels = [...document.querySelectorAll('#view tbody [data-act="awfDel"]')];
            if (!dels.length) return { ok: false, why: '新增后表内没出现「删除」按钮', before: before, added: added };
            dels[dels.length - 1].click();
            await new Promise(r => setTimeout(r, 1000));
            const be = await (await fetch('/api/m09/fee?ym=' + encodeURIComponent(awfYm)
              + '&pj=' + encodeURIComponent(awfPj))).json();
            return { ok: true, before: before, added: added, after: AWF_ROWS.length,
                     beManuals: (be.manuals || []).length };
        }""")
        print("⑪b m09 写路径往返 =", m09w)
        oks8 = [
            (bool(m09w.get("ok")), f"⭐ 写路径往返：{m09w.get('why') or '点得动'}"),
            (m09w.get("ok") and m09w.get("added") == m09w.get("before", -1) + 1,
             f"「＋ 增加手填项」**真的落库并回读**（{m09w.get('before')} → {m09w.get('added')} 行）"),
            (m09w.get("ok") and m09w.get("after") == m09w.get("before")
             and m09w.get("beManuals") == m09w.get("before"),
             f"「删除」后**回到原样、无残留**（{m09w.get('after')} 行 · 后端也是 {m09w.get('beManuals')}）"),
        ]
        for ok, what in oks8:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m09 写路径自检未通过：" + what)

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
