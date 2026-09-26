"""壳真机自检 · **第 ⑳ 段：四个暂留件收口后的壳内四页**（`§19` · 2026-09-21）。

覆盖：`set`（系统设置）· **`imp`（数据导入 · 通用导入面）**。
⚠️ `m08imp`（库存单据导入）已按用户 2026-09-22 裁定**整体删除**（`T8` 守卫）⇒ 不再覆盖。
⚠️ `m06imp`（过程资料历史导入）已随 `B5c` **下架**、⭐ `m05imp`（历史付款导入）已随 `B5b` 第三步
（2026-09-23 用户裁定 `B`）**下架** ⇒ 这两页改验 `imp`（同一页里选 `m06_proc` / `m05_flow` 域）。

**为什么单独立一个文件**：`tools/probe/_shell_smoke.py` 有 **400 行即黄**（`doc_audit` 的 `T5`）；⚠️ 连 `>600` 也只是**黄** —— `[用户·2026-09-21]` 把"红·禁合入"**降级**，只须在 `ops/阈值表.md` 登记"为什么不拆"
⇒ 与 `_shell_home.py` / `_shell_pend.py` 同款，由主自检**调一段**（`check(page, errors)`）。

**它验什么**（三件，都只在真机能看到）：
  ① **四页都渲染得出**、且**没有 console / page 错误**（⛔ 离线断言看不见这类崩）；
  ② ⭐ **无死控件**：页面上渲染出来的每个 `data-act` 都能解析到 `ACT`；**表单元素**（input/select）
     还必须在 `CHG` 里 —— 漏登记 ⇒ `change` 被**静默丢弃**（症状就是"选完文件按钮永远是灰的"）。
     本仓踩过三次（`jcAmt` / `jcPartySet` / `themeSet`）⇒ 这里是它的真机化落点；
  ③ **页面内容确实来自后端**（不是壳里另抄一份）：设置项条数 = `SPECS`；导入页的列契约 / 项目候选 /
     表头清单与各自 `/api/...` 端点一致。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import app.core.models_registry  # noqa: E402, F401

#: 页 → (中文名, 该页必须看得见的几个标志串)
PAGES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("set", "系统设置", ("连接参数", "变更留痕", "与直觉相反")),
    # ⭐ `TAIL-75` `B5`（2026-09-22）：通用导入面 —— 「数据导入」页（域清单 ＋ 四步向导）。
    #    ⚠️ 标志串取**进页就能看见**的（"列映射"要选完文件才有 ⇒ ⛔ 不能当标志）。
    ("imp", "数据导入", ("导入哪个域", "落库前一个字节都不写库")),
)


def _probe(page, key: str, marks: tuple[str, ...] = ()) -> dict:
    """进这一页 → 取「标志串在不在 / 死控件 / 那页自己的数据」三件。"""
    page.click(f'[data-k="{key}"]')
    # ⚠️ 2026-09-26：**死等改条件等待**（原 `wait_for_timeout(900)`）。
    #    ⚠️ 条件**必须带上这一页自己的标志串**（`marks`）—— 实测第一版只等"内容非空"会**跑早**：
    #        `set` 页 7096 B 时长度早就够了，而「与直觉相反」那一段还没渲染 ⇒ 报出
    #        "渲染出来了：缺 ['与直觉相反']"（**假红**，其实是没等够）；`imp` 页同理 ——
    #        域下拉的候选是**异步**取来的，早读到的 `value` 是空串。
    #    ⭐ 条件里放 `marks` 不算"拿判据自己证明自己"：**超时不算过**（这里吞掉超时），
    #       仍由下面那条正式断言判定并报原因 ⇒ 等待只负责"别跑早"，判词一字不动。
    try:
        page.wait_for_function(
            """a => VIEW === a.k && a.m.every(x =>
                   (document.querySelector('#view').innerText || '').includes(x))""",
            arg={"k": key, "m": list(marks)}, timeout=8000)
    except Exception:                                      # noqa: BLE001 —— 没等到就交给正式断言报
        pass
    return page.evaluate("""(key) => {
        const box = document.querySelector('#view');
        const txt = (box.innerText || '');
        const acts = [...box.querySelectorAll('[data-act]')].map(el => ({
            a: el.dataset.act, tag: el.tagName.toLowerCase(),
        }));
        return {
            view: VIEW, len: (box.innerHTML || '').length, txt: txt,
            acts: acts,
            dead: acts.filter(x => typeof ACT[x.a] !== 'function').map(x => x.a),
            /* ⛔ `#2`（2026-09-26）：`CHG` 名单已拆 ⇒ 这里**不再查"有没有登记"**
               —— `change` 委托看见 `data-act` 就跑，"漏登记"这回事不存在。 */
            inputs: box.querySelectorAll('input,select').length,
            rows: box.querySelectorAll('tbody tr').length,
        };
    }""", key)


#: 真上传要造的域（`③ 预览` 那两条判词要**两个域互为对照**，见下面 ③′）：
#:   `m06_proc` 声明了 `cutoff_ym`（截止核算月）· `m04_plan` 声明了 `year_month`（本批归属年月）
IMP_DOMAINS = ("m06_proc", "m04_plan")


def _mk_xlsx(path, domain: str) -> int:
    """造一份**最小可解析**的 xlsx 供真上传用 —— 表头**照该域契约生成**（⛔ 不手抄列名）。返回列数。

    ⚠️ 为什么必须照契约造：`m06_proc` 的契约里**没有机械 6 列**（口径：机械全段手录）⇒
       手抄一份"以为该有的表头"就会造出一份系统**不认**的表，然后误判成"导入坏了"。
    ⚠️ 为什么**在探针里现造**而不是提交一份二进制 fixture：二进制进库 = 又一个"看不见内容"的
       真源（本仓忌）；而现造的成本就是 openpyxl 写两行。
    """
    import importlib

    from openpyxl import Workbook

    mod = {"m06_proc": "app.mod06_proc.imp_spec", "m04_plan": "app.mod04_plan.imp_spec"}[domain]
    fields = list(importlib.import_module(mod).FIELDS)        # ⛔ 契约的主人还是那个模块
    wb = Workbook()
    ws = wb.active
    ws.append([f.label for f in fields])                      # 表头 = 契约标签
    ws.append(["2026-01" if f.key == "ym" else 0 for f in fields])   # 年月给个能认的，其余给 0
    wb.save(str(path))
    return len(fields)


def _imp_pick(page, domain: str, fx) -> None:
    """选域 → 上传 → 解析（**全走条件等待**）—— ①′/③′ 共用（⛔ 不复制两遍）。

    ⚠️ 三个等待各自的条件 = "**下一步要读的东西真的在了**"：切域 ⇒ 页面文本变（壳要重取该域契约）；
    上传 ⇒ 不用等（`set_input_files` 同步触发 change）；解析 ⇒ **② 的映射控件出现**。
    ⇒ 成功路径 ~0.5 s（原先是 700 ＋ 500 ＋ 2500 的**纯睡**），且**等不到就超时即红**
       （死等的隐患：超时也是绿的 ⇒ 页面没动时，"② 出来了"的断言会读上一屏的内容）。
    """
    before = page.evaluate("() => document.querySelector('#view').innerText")
    page.select_option('[data-act="impDomain"]', domain)
    page.wait_for_function("t => document.querySelector('#view').innerText !== t",
                           arg=before, timeout=8000)
    page.set_input_files('[data-act="impPick"]', str(fx))
    page.click('[data-act="impParse"]')          # 「解析并预览」是 `<button>` ⇒ click 委托
    page.wait_for_selector('[data-act="impMap"]', timeout=20000)


def check(page, errors: list[str]) -> None:
    """⑳ 真机走一遍：四页 **渲染 ＋ 无死控件 ＋ 内容是后端的**。"""
    from app.core.app_settings import SPECS

    stage = "开页"
    try:
        for key, name, marks in PAGES:
            stage = name
            got = _probe(page, key, marks)
            miss = [m for m in marks if m not in got["txt"]]
            ok_render = got["view"] == key and got["len"] > 400 and not miss
            print(("  ✅ " if ok_render else "  ⛔ ")
                  + f"⑳ {name}（`{key}`）渲染出来了"
                  + (f"（{got['len']} B）" if ok_render else f"：view={got['view']} 缺 {miss}"))
            if not ok_render:
                errors.append(f"四个暂留件收口自检未通过：{name} 没渲染出来（缺 {miss}）")

            # ② 死控件（本仓最贵的一类"静默"）—— ⚠️ `#2` 起"表单元素是否进 CHG"这半**已废**（名单拆了）
            ok_acts = not got["dead"]
            print(("  ✅ " if ok_acts else "  ⛔ ")
                  + f"⑳ {name} 无死控件（{len(got['acts'])} 个 data-act"
                  + f"，表单元素 {got['inputs']} 个）"
                  + ("" if ok_acts else f"：ACT 里没有 {got['dead']}"))
            if not ok_acts:
                errors.append(f"四个暂留件收口自检未通过：{name} 有死控件（ACT 缺 {got['dead']}）")

        # ②′ ⭐ `#2` 的真机证据（2026-09-26 补 · 用户裁定「拆 `CHG` 名单」后必须证到）：
        #     **表单元素真选一次 ⇒ 页面必须跟着变** —— `CHG` 名单拆掉之后，`select` 的 `change`
        #     全靠 `data-act` 委托跑（`change` 委托看见 `data-act` 就跑）。真机这一下是**唯一的**证明：
        #     拆名单有没有把「选完不生效」这类静默丢事件带回来。
        #     ⚠️ 判词取「**页面文本变了**」（不依赖任何内部变量：`IMP` 在壳的闭包里，真机取不到）。
        #     ⚠️ 同批（2026-09-26）：**死等改条件等待** —— 原先睡 900 ms 再比文本，那样"没变"与
        #        "还没变"**分不开**（把假绿和真红混在一起）；现在**先等文本真变**，超时即红。
        stage = "表单元素真触发"
        # ⚠️ 域候选是**异步**取来的（`/api/imp/domains`）⇒ 先等下拉真的有值，再读
        #    （否则读到空串 ⇒ "域  → m04_plan" 这种没头没尾的报错，看着像壳坏了）。
        page.wait_for_function(
            """() => { const s = document.querySelector('[data-act="impDomain"]');
                       return !!(s && s.options.length && s.value); }""", timeout=8000)
        cur = page.eval_on_selector('[data-act="impDomain"]', "el => el.value")
        opts = page.eval_on_selector('[data-act="impDomain"]',
                                     "el => [...el.options].map(o => o.value).filter(Boolean)")
        other = next((v for v in opts if v != cur), "")
        before = page.evaluate("() => document.querySelector('#view').innerText")
        if not other:
            errors.append("四个暂留件收口自检未通过：导入页只有一个域 ⇒ 验不了「真选一次」")
        else:
            page.select_option('[data-act="impDomain"]', other)
            try:
                # 条件 = 本判词的判据本身（文本变了）⇒ 变了就往下；没变 ⇒ 交给下面报红（带原因）
                page.wait_for_function("t => document.querySelector('#view').innerText !== t",
                                       arg=before, timeout=8000)
                ok_trigger = True
            except Exception:                                  # noqa: BLE001
                ok_trigger = False
            print(("  ✅ " if ok_trigger else "  ⛔ ")
                  + f"⑳ 表单元素真选一次触发了（域 {cur} → {other}，页面{'变了' if ok_trigger else '没变'}）")
            if not ok_trigger:
                errors.append("四个暂留件收口自检未通过：域选择真选一次**页面没变**"
                              "（`change` 事件被静默丢弃 —— `#2` 拆名单拆坏了）")

        # ①′ ⭐ **`② 列映射` 的真机证据**（2026-09-26 补）：**真上传一份表 ⇒ 解析 ⇒ ② 必须出来**。
        #    ⚠️ 这一屏（还有 ③）**只有真上传才有** —— 离线断言、源码断言都看不见它；
        #       而「上传 → 认表头 → 给映射建议」正是这条通用面最核心的一段。
        stage = "真上传并解析"
        fs = Path(__file__).resolve().parents[2] / ".workbuddy" / "scratch"
        dm = IMP_DOMAINS[0]
        fx = fs / f"imp_smoke_{dm}.xlsx"
        n_cols = _mk_xlsx(fx, dm)
        _imp_pick(page, dm, fx)                    # 选域 → 上传 → 解析（全走条件等待）
        got2 = page.evaluate("""() => {
            const v = document.querySelector('#view');
            const sel = [...v.querySelectorAll('[data-act="impMap"]')];
            return {maps: sel.length, n: v.querySelectorAll('table').length,
                    which: (v.innerText.match(/②[^\\n]{0,20}/) || [''])[0],
                    tip: ((v.querySelector('.tip') || {}).innerText || '').slice(0, 90)};
        }""")
        print(f"①′ 真上传解析 = {got2}（表头 {n_cols} 列 · 域 {dm}）")
        ok_parse = got2["maps"] >= 1
        print(("  ✅ " if ok_parse else "  ⛔ ")
              + f"⑳ 真上传一份表 ⇒ 解析出「② 列映射」（{got2['maps']} 个源列 · 表格 {got2['n']} 张）")
        if not ok_parse:
            errors.append("四个暂留件收口自检未通过：真上传后 ② 列映射没出来"
                          f"（表头 {n_cols} 列 · 域 {dm} · 页面提示：{got2.get('tip') or got2.get('which')}）")

        # ③′ ⭐⭐ **`③ 预览` 的真机证据**（2026-09-26 补 · **用户报障的另一半就在这一屏**）：
        #    `ctxBar`（项目面板 ＋ **本批归属年月** ＋ **截止核算月**）**只在 ③ 预览卡**里渲染
        #    （`legacy.js` 的 `${ctxBar}` 在 `prevCard`，就在「④ 确认落库」上面）⇒ ② 及以前看不见它。
        #    ⭐ 它此前**从没被真机跑过**：2026-09-26 收尾核这一屏时，**当场查出**导入页 5 处把面板共用件
        #       写成了 `IMP` 的方法（`IMP.pjClose('impPj')` 那种 —— 语法合法、点下去才 TypeError，
        #       四个闸门全绿）⇒ 这条证据就是为"这一屏"补的。
        #    判词三件（**两个域互为对照** —— 这就是"按键渲染"的真机证明）：
        #      ① `m06_proc` **声明了** `cutoff_ym` ⇒ `#impCut` 在、`#impYm` 不在；
        #      ② `m04_plan` **声明了** `year_month` ⇒ `#impYm` 在、`#impCut` 不在
        #         （⭐ 用户原话「截止核算月是干嘛的？」＋「集采页那个框填了不生效」—— 修法就是
        #          "只画给声明它的域"，此前**只有源码断言**看得见）；
        #      ③ 两个域都要有**项目面板**，且**真点能开、点空白能收**（那一屏上的共用件真在跑）。
        stage = "③ 预览（域上下文栏）"
        # 域 ⇒ (要「截止核算月」, 要「本批归属年月」, 要「项目面板」)
        # ⚠️ 面板**不是每个域都有**：`m04_plan` 的 `options` 只给 `year_month`（付款计划取数不走这一格）
        #    ⇒ 它**本来就没有**项目面板。⭐ 实测当场打脸第一版判词（"两域都要有面板" ⇒ `m04` 报 `pj=False`）——
        #    那不是壳的错，是**判词把自己以为的设计当成了契约**（⛔ 判据只许照域自己说的写）。
        want = {"m06_proc": (True, False, True), "m04_plan": (False, True, False)}
        for dm in IMP_DOMAINS:
            want_cut, want_ym, want_pj = want[dm]
            fx = fs / f"imp_smoke_{dm}.xlsx"
            n_cols = _mk_xlsx(fx, dm)
            _imp_pick(page, dm, fx)                         # 选域 → 上传 → 解析（② 出来）
            page.click('[data-act="impPreview"]')           # ② → ③（**只读**：预览阶段不写库）
            page.wait_for_selector('[data-act="impCommit"]', timeout=20000)   # 预览卡到了（落库按钮只在这）
            got3 = page.evaluate("""() => {
                const v = document.querySelector('#view');
                const t = v.querySelector('[data-act="impPjToggle"]');
                let open = -1, outside = -1;
                if (t) { t.click(); open = v.querySelectorAll('[data-act="impPjPick"]').length;
                         document.querySelector('#ttl').click();
                         outside = v.querySelectorAll('[data-act="impPjPick"]').length; }
                return {cut: !!v.querySelector('#impCut'), ym: !!v.querySelector('#impYm'),
                        pj: !!t, open: open, outside: outside};
            }""")
            print(f"③′ {dm} 预览卡 = {got3}（表头 {n_cols} 列）")
            oks3 = [
                (got3["cut"] == want_cut,
                 f"`{dm}` 的「截止核算月」" + ("在（它声明了 `cutoff_ym`）" if want_cut
                                          else "**没画**（它没声明 `cutoff_ym` ⇒ 画了也是填了不生效）")),
                (got3["ym"] == want_ym,
                 f"`{dm}` 的「本批归属年月」" + ("在（它声明了 `year_month`）" if want_ym
                                           else "**没画**（它没声明 `year_month`）")),
                (got3["pj"] == want_pj and (not want_pj or (got3["open"] >= 1 and got3["outside"] == 0)),
                 f"`{dm}` " + (f"的项目面板真点能开（{got3['open']} 个候选）· 点空白能收（{got3['outside']}）"
                               if want_pj else "**没画**项目面板（它没给 `projects`）")),
            ]
            for ok3, what3 in oks3:
                print(("  ✅ " if ok3 else "  ⛔ ") + "⑳′ " + what3)
                if not ok3:
                    errors.append(f"③ 预览屏自检未通过（{dm}）：" + what3)

        # ③ 内容是后端的（⛔ 壳里另抄一份 = 两处副本必漂）
        stage = "与后端对账"
        got = page.evaluate("""async () => {
            const j = async u => await (await fetch(u)).json();
            const r = {spec: (await j('/api/m14/settings')).items.length,
                       m05: (await j('/api/imp/m05_flow/schema')).fields.length,
                       m06: (await j('/api/imp/m06_proc/schema')).fields.length,
                       m06d: (await j('/api/imp/m06_proc/options')).projects.length};
            return r;
        }""")
        oks = [
            (got["spec"] == len(SPECS), f"设置项条数与 `SPECS` 一致（{got['spec']} = {len(SPECS)}）"),
            # ⚠️ 2026-09-23（`B5b` 第三步 · 用户裁定 `B`）：`/api/m05/import/meta` 已随旧页删除
            #    ⇒ 列契约改从**通用面的域声明**读（判词不变：五列契约就是 A–E，只是出口换成域声明）。
            (got["m05"] == 5, f"付款导入的列契约是 A–E 五列（{got['m05']}）"),
            (got["m06"] >= 1, f"过程资料导入的材料列清单非空（{got['m06']} 列）"),
            (got["m06d"] >= 0, f"过程资料导入的项目候选可读（{got['m06d']} 个）"),
        ]
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + f"⑳ {what}")
            if not ok:
                errors.append("四个暂留件收口自检未通过：" + what)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ⛔ ⑳ 在「{stage}」这一步失败：{type(exc).__name__}: {str(exc)[:160]}")
        errors.append(f"四个暂留件收口自检异常（{stage}）：{type(exc).__name__}")


__all__ = ["check"]
