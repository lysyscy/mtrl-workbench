"""壳真机自检 · **第 ⑪/⑪b 段：m09 特殊费用月报表**（`TAIL-27` 接线 · 2026-09-25 外移）。

**为什么单独立一个文件**：`tools/probe/_shell_smoke.py` **>400 行即黄**（`doc_audit` 的 `T5`）；
⚠️ 连 `>600` 也只是**黄**（`[用户·2026-09-21]` 把"红·禁合入"降级），只须在 `ops/阈值表.md` 登记"为什么不拆"。
⇒ 与 `_shell_exp.py` / `_shell_pend.py` 等**同款**：由主自检**调一段**（`check(page, errors)`）。

⚠️ **本件刻意不写 `try/except`**：它搬的是原先**内联在 `main()` 里**的段落 ⇒ 异常语义必须**逐字保持**
（抛出去 = 整支崩 ⇒ rc≠0）；"把异常收进 `errors`"是**另一种**失败行为，不叫零行为变化。

**它验的链条**：① 项目候选 / 手填行数 / 自动项 / 合计**逐项 == 当场重取的后端**；
② 演示容器 `AWF` **真的没了**；③ 切到**非默认**项目跟后端走、**后端不认**的项目由后端归一化（壳里不写第二份）；
④ ⭐ **写路径净零往返**：点「＋ 增加手填项」⇒ 真落库并回读 ⇒ 点「删除」⇒ 回到原样、无残留。
"""

from __future__ import annotations


def check(page, errors: list[str]) -> None:
    """⑪/⑪b 真机走一遍：**只读对账 ＋ 写路径净零往返**（⛔ 脚本可反复跑、不留残留）。"""
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
