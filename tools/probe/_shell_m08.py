"""⑧ · m08 库存单据：全量行数 == 后端 ＋ **真滚轮**滚得动

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations

from _shell_common import goto


def check(page, errors) -> None:
    """⑧ —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ---- m08 库存单据与调整单：⭐ **全量行数必须等于后端**（可观测证据；表内渲染随筛选走）
    goto(page, "m08")
    m08 = page.evaluate("""() => {
        const pill=(document.querySelector('#view .pill')||{}).innerText||'';
        const m=String(pill).match(/(\\d+)\\s*行/);
        return {
          ivs: IVs.length, adjs: ADs.length,
          pill: pill.replace(/\\s+/g,' ').slice(0, 90),
          listed: m ? Number(m[1]) : -1,       /* 筛选条报出的条数 */
          rows: document.querySelectorAll('#view tbody tr').length,
          tables: document.querySelectorAll('#view table').length,
          wiredLabel: (document.querySelector('#ttl em')||{}).innerText||'',
          firstDoc: (IVs[0]||{}).docNo||'',
          /* ⭐ `TAIL-64` P5-c（2026-09-30）：原来读的是**页级**实例 `VS` —— 那条路已删 ⇒ 改读
             **表级**实例（`VS_TS`：本页被认领的表；⛔ `VS` 已经不存在了，读它恒得 -1）。 */
          vsRows: (typeof VS_TS!=='undefined' && VS_TS.length)
                  ? Math.max.apply(null, VS_TS.map(x=>x.rows.length)) : -1,
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
        ("未接通" not in m08["wiredLabel"], "接通页的顶栏不挂状态牌（用户裁定 B）"),
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


