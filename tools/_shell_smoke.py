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

        # ---- m14 规则配置：⭐ 可观测证据 = **页面的规则条数 == 当场重取后端的条数**
        #      ＋ 类别下拉与后端同源 ＋ 来源如实显示 ＋ 卡头条数实时算
        #      ⭐ ⑫b **写路径净零往返**：新增一条探针 ⇒ 条数 +1 ⇒ **按 id 差集**删掉它 ⇒ 回到原样。
        #         ⚠️ 净零 ⇒ 可反复跑、库不留残留；用「id 差集」而不是"删最后一条"，
        #            免得删除失败时**误删真规则**。
        page.click('[data-k="m14"]')
        page.wait_for_timeout(800)
        m14 = page.evaluate("""async () => {
            const rulesBe = async () => (await (await fetch('/api/m14/rules')).json());
            const be0 = await rulesBe();
            const tbls = [...document.querySelectorAll('#view table')];
            const t = tbls[0] || null;
            const out = {
              rules: RULE_EX.length, beRules: (be0.rules || []).length,
              raw: RULE_RAW.length,
              kinds: RULE_KINDS.length, beKinds: (be0.kinds || []).length,
              kindKeys: RULE_KINDS.map(k => k.kind),
              src: RULE_SRC, beSrc: be0.source_label,
              tbody: t ? t.querySelectorAll('tbody tr').length : 0,
              wiredLabel: document.querySelector('#ttl em').innerText,
              headCount: (document.querySelector('#view h4 b') || {}).innerText || '',
            };
            /* ⭐ 写路径：经**后端**新增一条探针规则 ⇒ 再按 **id 差集**删掉它（净零） */
            const before = new Set((be0.rules || []).map(r => r.id));
            const add = await (await fetch('/api/m14/rules', {method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({kind: 'input_by', values: '__smoke_probe__',
                                    meaning: '冒烟探针（跑完即删）'})})).json();
            const be1 = await rulesBe();
            const fresh = (be1.rules || []).find(r => !before.has(r.id));
            await reloadM14(); render();
            out.addedUi = RULE_EX.length;
            let del = null;
            if (fresh) {
              del = await (await fetch('/api/m14/rules/' + fresh.id, {method: 'DELETE'})).json();
            }
            await reloadM14(); render();
            const be2 = await rulesBe();
            out.add = {ok: add.ok, msg: (add.message || '').slice(0, 70)};
            out.del = del ? {ok: del.ok, msg: (del.message || '').slice(0, 90)} : null;
            out.after = RULE_EX.length;
            out.beAfter = (be2.rules || []).length;
            return out;
        }""")
        print("⑫ m14 =", m14)
        oks9 = [
            ("已接后端" in m14["wiredLabel"], "顶栏说「已接后端真实数据」"),
            (m14["rules"] == m14["beRules"] and m14["rules"] > 0 and m14["raw"] == m14["beRules"],
             f"⭐ 页面的规则条数 == 后端（{m14['rules']} vs {m14['beRules']}）"
             " —— 若 `RULE_EX` 还硬编码，这里就对不上"),
            (m14["tbody"] == m14["beRules"],
             f"表内渲染行数 == 后端条数（{m14['tbody']}）"),
            (m14["kinds"] == m14["beKinds"] and m14["kinds"] > 0
             and "payee" not in m14["kindKeys"],
             f"⭐ 可选类别来自后端、且**不含「收款单位」**（{m14['kinds']} vs {m14['beKinds']}）"),
            (m14["src"] == m14["beSrc"] and bool(m14["src"]),
             f"⭐ 页面如实显示当前值的来源（{m14['src']!r}）"),
            (m14["headCount"] == str(m14["beRules"]),
             f"⭐ 卡头条数**实时算**（卡头 {m14['headCount']!r} vs 后端 {m14['beRules']}）"),
        ]
        for ok, what in oks9:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m14 自检未通过：" + what)

        oks10 = [
            ((m14.get("add") or {}).get("ok") is True,
             f"⭐ 新增**真的落库**：{(m14.get('add') or {}).get('msg')}"),
            (m14.get("addedUi") == m14.get("beRules", -99) + 1,
             f"⭐ 新增后页面条数 +1（{m14.get('rules')} → {m14.get('addedUi')}）—— 证明是全链路不是本地改"),
            ((m14.get("del") or {}).get("ok") is True,
             f"⭐ 探针已删除：{(m14.get('del') or {}).get('msg')}"),
            (m14.get("after") == m14.get("rules") and m14.get("beAfter") == m14.get("rules"),
             f"⭐ 跑完**回到原样、库无残留**（页面 {m14.get('after')} · 后端 {m14.get('beAfter')}"
             f" · 原 {m14.get('rules')}）"),
        ]
        for ok, what in oks10:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("m14 写路径自检未通过：" + what)

        # ---- m07 导出（`TAIL-04`）：⭐ 可观测证据 = **从页面上下文真拉一次 zip**。
        #      ⚠️ 两件事分开验（都是真事实）：
        #        ① **默认月没数据**时（材料报表默认 = 上月，而真机数据可能落在别的月）
        #           ⇒ 必须回**中文原因**、⛔ 不能崩、不能产出空文件；
        #        ② 换到**有数据的月份** ⇒ 必须真拿到 zip，且文件名含**那个月份**。
        exp = page.evaluate("""async () => {
            const label = p => { const [y, m] = p.split('-'); return Number(y) + '年' + Number(m) + '月'; };
            const grab = async p => {
                const r = await fetch('/api/m07/settlement/export?period=' + encodeURIComponent(p));
                const ct = r.headers.get('content-type') || '';
                if (ct.includes('application/json')) {
                    const d = await r.json();
                    return { period: p, json: true, ct: ct, ok: d.ok, message: (d.message || '').slice(0, 90) };
                }
                const b = await r.blob();
                const u8 = new Uint8Array(await b.slice(0, 2).arrayBuffer());
                return { period: p, ct: ct, label: label(p),
                         fn: decodeURIComponent(r.headers.get('x-export-filename') || ''),
                         size: b.size, magic: String.fromCharCode(u8[0], u8[1]),
                         warehouses: pjSort(whRows(p)).length };
            };
            const def = await grab(fWhYm);                 /* ① 默认月（可能就是没数据的那个月） */
            const cands = [];
            for (let i = 0; i <= 3; i++) {
                const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - i);
                cands.push(d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0'));
            }
            let hit = null;
            for (const p of cands) {
                const r = await grab(p);
                if (!r.json) { hit = r; break; }
            }
            return { def: def, hit: hit, tried: cands };
        }""")
        print("⑬ 导出（TAIL-04）= 默认月：", exp.get("def"))
        print("                 有数据的月：", exp.get("hit"))
        d, h = exp.get("def") or {}, exp.get("hit") or {}
        oks11 = [
            (bool(d.get("json")) and d.get("ok") is False and "明细" in (d.get("message") or ""),
             f"① 默认月（{d.get('period')}）没数据时回**中文原因**、不是崩：{(d.get('message') or '')[:40]}…"),
            (bool(h), f"② 近 4 个月里至少有一个月导得出（试过 {exp.get('tried')}）"),
            (bool(h) and h.get("ct") == "application/zip",
             f"② content-type = application/zip（{h.get('ct')}）"),
            (bool(h) and h.get("magic") == "PK",
             "② 内容以 `PK` 开头 ⇒ **真的是 zip**（不是空壳 / 错误页）"),
            (bool(h) and h.get("label") in (h.get("fn") or ""),
             f"⭐ 文件名由后端带出、且含**该月份**：{h.get('fn')}"),
            (bool(h) and h.get("size", 0) > 20000,
             f"② 大小 {h.get('size')} B（应含 {h.get('warehouses')} 个分仓库表 ＋ 总表）"),
        ]
        for ok, what in oks11:
            print(("  ✅ " if ok else "  ⛔ ") + what)
            if not ok:
                errors.append("TAIL-04 导出自检未通过：" + what)

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
