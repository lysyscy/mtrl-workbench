"""壳真机自检 · **第 ⑫/⑫b/⑫c 段：m14 规则配置 ＋ 集采剔除名单卡**（`TAIL-96` · 2026-09-25 外移）。

**为什么单独立一个文件**：`tools/probe/_shell_smoke.py` **>400 行即黄**（`doc_audit` 的 `T5`）；
⚠️ 连 `>600` 也只是**黄**（`[用户·2026-09-21]` 降级），只须在 `ops/阈值表.md` 登记"为什么不拆"。
⇒ 与 `_shell_exp.py` / `_shell_pend.py` 等**同款**：由主自检**调一段**（`check(page, errors)`）。

⚠️ **本件刻意不写 `try/except`**：同 `_shell_m09.py` —— 零行为变化优先（原段落内联在 `main()` 里）。

**它验的链条**：① 规则条数 / 类别 / 来源 / 卡头条数 == 后端；② ⭐ 写路径**净零往返**（新增一条探针 ⇒
按 **id 差集**删掉它 ⇒ 回到原样，⛔ 不"删最后一条"免得误删真规则）；③ ⭐ **⑫c 集采剔除名单卡**：
「加入剔除名单」按钮**真点一次** ⇒ 空名必早退（零落库），证明 `data-act` → `ACT.jciAdd` 的**点击链路**通。
"""

from __future__ import annotations


def check(page, errors: list[str]) -> None:
    """⑫/⑫b/⑫c 真机走一遍：**规则配置对账 ＋ 写路径净零往返 ＋ 剔除名单卡点击链路**。"""
    # ---- m14 规则配置：⭐ 可观测证据 = **页面的规则条数 == 当场重取后端的条数**
    #      ＋ 类别下拉与后端同源 ＋ 来源如实显示 ＋ 卡头条数实时算
    #      ⭐ ⑫b **写路径净零往返**：新增一条探针 ⇒ 条数 +1 ⇒ **按 id 差集**删掉它 ⇒ 回到原样。
    #         ⚠️ 净零 ⇒ 可反复跑、库不留残留；用「id 差集」而不是"删最后一条"，
    #            免得删除失败时**误删真规则**。
    page.click('[data-k="m14"]')
    page.wait_for_timeout(800)
    # ⭐ `TAIL-96`：集采剔除名单卡的**点击链路真点一次**（零残留 —— 见设计件 §四）。
    m14j = page.evaluate("""async () => {
        await reloadM14(); render();
        const b = document.querySelector('#view [data-act="jciAdd"]');
        const i = document.querySelector('#jciName');
        if (!b || !i) return {why: '看不到「加入剔除名单」输入行'};
        const n0 = (window.JCI_ALL || []).length;
        i.value = ''; b.click(); await new Promise(r => setTimeout(r, 500));
        return {api: [typeof API.m14JcIgnoreAdd, typeof API.m14JcIgnoreSet], n0: n0,
                n1: (window.JCI_ALL || []).length,
                said: document.body.innerText.includes('项目全名不能为空')};
    }""")
    jok = (m14j.get('api') == ['function', 'function'] and m14j.get('n0') == m14j.get('n1')
           and m14j.get('said'))
    print(("  ✅ " if jok else "  ⛔ ") + f"⑫c 集采剔除名单卡：加入按钮**真点**⇒空名早退"
          f"（名单 {m14j.get('n0')} → {m14j.get('n1')} 条 · 回执={m14j.get('said')}）")
    if not jok:
        errors.append("m14 集采剔除名单卡自检未通过：" + str(m14j))

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
