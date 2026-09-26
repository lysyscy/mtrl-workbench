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


#: 真上传要造的域（范围栏那条判词要**几个域互为对照** —— 这就是"按键渲染"的真机证明）：
#:   `m06_proc` 声明了 `cutoff_ym`（截止核算月）· `m04_plan` 声明了 `year_month`（本批归属年月）
#:   · `m11_jc` 只给 `projects`（**逐项目**，且 ③ 会给出"配上几条"）。
IMP_DOMAINS = ("m06_proc", "m04_plan", "m11_jc")


def _mk_xlsx(path, domain: str) -> int:
    """造一份**最小可解析**的 xlsx 供真上传用 —— 表头**照该域契约生成**（⛔ 不手抄列名）。返回列数。

    ⚠️ 为什么必须照契约造：`m06_proc` 的契约里**没有机械 6 列**（口径：机械全段手录）⇒
       手抄一份"以为该有的表头"就会造出一份系统**不认**的表，然后误判成"导入坏了"。
    ⚠️ 为什么**在探针里现造**而不是提交一份二进制 fixture：二进制进库 = 又一个"看不见内容"的
       真源（本仓忌）；而现造的成本就是 openpyxl 写两行。
    """
    import importlib
    from datetime import time

    from openpyxl import Workbook

    mod = {"m06_proc": "app.mod06_proc.imp_spec", "m04_plan": "app.mod04_plan.imp_spec",
           "m11_jc": "app.mod11_jc.imp_spec"}[domain]
    fields = list(importlib.import_module(mod).FIELDS)        # ⛔ 契约的主人还是那个模块
    wb = Workbook()
    ws = wb.active
    ws.append([f.label for f in fields])                      # 表头 = 契约标签
    # ⚠️ 数据行**必须带一个"时间格"**：这是 2026-09-26 用户报障的形态（真课表.xlsx 的「上课时间」
    #    那列是时间格 ⇒ 读表给原生 `datetime.time` ⇒ 载具 `json.dumps` 当场炸
    #    「解析失败：TypeError: Object of type time is not JSON serializable」）
    #    ⇒ 真机这趟**带着它跑**，才算真的证到"这类文件导得进来"（⛔ 只给日期/数字的假表证不到）。
    ws.append([("2026-01" if f.key == "ym" else (time(8, 30) if i == 1 else 0))
               for i, f in enumerate(fields)])
    wb.save(str(path))
    return len(fields)


#: 各域**范围栏就绪**的判据（JS 表达式）＝"域上下文真的取回来了"——
#:   · ⛔ 别用"页面文本变了"当条件：**同一个域再选一次**时文本可能一模一样（实测 `m04_plan` 就白等到超时）；
#:   · ⛔ 也别用"下拉的 value 变成目标"：`select_option` 是**同步**改 DOM 值的 ⇒ 会在异步取域上下文
#:     之前就返回（实测：切到 `m04_plan` 却读到 `m06_proc` 的范围栏，三条判词全**假红**）；
#:   · ⚠️ 每个判据必须**只对本域成立**：`m11_jc` 的项目面板与 `m06_proc` 那个长得一样
#:     ⇒ 得再加上"**没有** `#impCut` / `#impYm`"才算认到 m11 那一屏。
_CTX_READY = {
    "m06_proc": "!!document.querySelector('#impCut')",
    "m04_plan": "!!document.querySelector('#impYm')",
    "m11_jc": "!!document.querySelector('[data-act=\"impPjToggle\"]')"
              " && !document.querySelector('#impCut') && !document.querySelector('#impYm')",
}


def _imp_domain(page, domain: str, wait_ready: str = "") -> None:
    """**只切域**（不选文件）—— 用来证「**选完域、还没选文件**就看得到范围栏」。

    `wait_ready` = 该域范围栏就绪的 JS 判据（见 `_CTX_READY`）；给空则只等下拉的 value 对上
    （⚠️ 那只够用在"不读该域范围栏"的地方）。
    """
    if page.eval_on_selector('[data-act="impDomain"]', "el => el.value") == domain:
        return
    page.select_option('[data-act="impDomain"]', domain)
    if wait_ready:
        page.wait_for_function(f"() => {wait_ready}", timeout=8000)
    else:
        page.wait_for_function("d => document.querySelector('[data-act=\"impDomain\"]').value === d",
                               arg=domain, timeout=8000)


def _imp_pick(page, domain: str, fx) -> None:
    """选域 → 上传 → 解析（**全走条件等待**）—— ①′/③′ 共用（⛔ 不复制两遍）。

    ⚠️ 三个等待各自的条件 = "**下一步要读的东西真的在了**"：切域 ⇒ 该域范围栏的控件出现；
    上传 ⇒ 不用等（`set_input_files` 同步触发 change）；解析 ⇒ **② 的映射控件出现**（⚠️ 按 `attached` 判
    —— ② 里"不参与"的列**没有可见下拉**，按 `visible` 判会**假红**，见下面那段的现场记录）。
    ⇒ 成功路径 ~0.5 s（原先是 700 ＋ 500 ＋ 2500 的**纯睡**），且**等不到就超时即红**
       （死等的隐患：超时也是绿的 ⇒ 页面没动时，"② 出来了"的断言会读上一屏的内容）。
    """
    _imp_domain(page, domain, _CTX_READY.get(domain, ""))
    page.set_input_files('[data-act="impPick"]', str(fx))
    page.click('[data-act="impParse"]')          # 「解析并预览」是 `<button>` ⇒ click 委托
    # ⚠️ ② 没出来时**必须把页首那句话打出来**（"解析失败：…"就是它写的）—— 否则只剩一句
    #    `TimeoutError`，病因（多半是这份自检表没被认成该域）全被藏掉。
    try:
        # ⚠️ **必须 `state="attached"`**（2026-09-26 订正）：默认的 `visible` 会漏判 ——
        #    ② 那一屏里**「不参与」的列根本不给可见的下拉**（用户裁定：藏在 `<details>` 折叠里），
        #    而探针造的**自检表**值全是 `0`/时间格 ⇒ 认出来的列极少、**一个可见下行都没有**
        #    ⇒ `visible` 判据**白等到超时**（症状 = 一句 `TimeoutError`，看着像"解析坏了"，其实 ② 早出来了）。
        page.wait_for_selector('[data-act="impMap"]', state="attached", timeout=20000)
    except Exception:                            # noqa: BLE001
        notice = page.evaluate("() => (document.querySelector('#view').innerText || '').slice(0, 260)")
        print(f"  ⛔ ② 列映射没出来（域 {domain}）—— 页首提示：{notice!r}")
        print("  [诊断] ② 的痕迹：", page.evaluate("""() => ({
            card: !!document.querySelector('[data-act="impPreview"]'),
            maps: document.querySelectorAll('[data-act="impMap"]').length,
        })"""))
        raise


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
        # ⭐ **留一张截图**（`[用户·2026-09-26]`：Agent **看不见界面** ⇒ 版式问题（挤/压字/遮挡）
        #    只能靠人眼发现 ⇒ 每改一次版式就留一张图，落到 `artifacts/`（**不是** `.workbuddy/scratch/`，
        #    那里 14 天 TTL）。⚠️ 截图失败**不影响判据**（它只是取证）。
        try:
            shot = Path(__file__).resolve().parents[2] / "artifacts" / "imp_map_2.png"
            page.screenshot(path=str(shot), full_page=True)
            print(f"  📷 已截图 ② 列映射：{shot}")
        except Exception as exc:                              # noqa: BLE001
            print(f"  ⚠️ 截图失败（不影响判据）：{type(exc).__name__}: {exc}")

        # ①″ ⭐⭐ **「范围」栏前移 + 未选项目不能落库**的真机证据（2026-09-26 用户裁定：
        #    「**选文件时就选定项目**」＋「默认值不诱导」）：
        #    `ctxBar`（项目面板 ＋ **本批归属年月** ＋ **截止核算月**）**原先只画在 ③ 预览卡里**
        #    ⇒ 用户**走到最后一步才知道要选项目**；现在画在 **①「选域与文件」**（`legacy.js` 的 `head`）
        #    ⇒ **选完域、还没选文件就该看得见**（这一条只有真机能证）。
        #    ⚠️ 那三处控件此前**从没在"① 那一屏"被真机跑过**：2026-09-26 收尾核这一屏时**当场查出**
        #       导入页 5 处把面板共用件写成了 `IMP.` 的方法（语法合法、点下去才 TypeError，四个闸门全绿）。
        #    判词（**两个域互为对照** —— 这就是"按键渲染"的真机证明）：
        #      ① `m06_proc` **声明了** `cutoff_ym` ⇒ `#impCut` 在、`#impYm` 不在；
        #      ② `m04_plan` **声明了** `year_month` ⇒ `#impYm` 在、`#impCut` 不在（⭐ 用户原话
        #         「截止核算月是干嘛的？」—— 修法就是"只画给声明它的域"，此前只有源码断言看得见）；
        #      ③ `m06_proc` 有 `projects` ⇒ 项目面板在 **且默认不预选**（按钮文案 = `请选择项目`）。
        #    再往下（同一循环里）验 ③ 那一屏：**只读回显**在、**没选项目 ⇒ ④ 置灰**、
        #      真点选一个 ⇒ ④ 变可用，且 `#impCut` **换成所选项目自己的截止月**（真缺陷的修复证据）。
        stage = "① 范围栏（选域即可见 · 项目不预选）"
        # 域 ⇒ (要「截止核算月」, 要「本批归属年月」, 要「项目面板」)
        # ⚠️ 面板**不是每个域都有**：`m04_plan` 的 `options` 只给 `year_month`（付款计划不按项目导）
        #    ⇒ 它**本来就没有**项目面板。⭐ 实测当场打脸第一版判词（"两域都要有面板" ⇒ `m04` 报 `pj=False`）——
        #    那不是壳的错，是**判词把自己以为的设计当成了契约**（⛔ 判据只许照域自己说的写）。
        want = {"m06_proc": (True, False, True), "m04_plan": (False, True, False),
                "m11_jc": (False, False, True)}
        for dm in IMP_DOMAINS:
            want_cut, want_ym, want_pj = want[dm]
            # ⚠️ **必须给就绪判据**（`_CTX_READY`）：`select_option` 是**同步**改 DOM 值的，若只等
            #    "下拉的 value 变成目标"，会**在异步取域上下文之前**就返回 ⇒ 读到的还是**上一屏**
            #    （实测：切到 `m04_plan` 却读到 `m06_proc` 的范围栏，三条判词全假红）。
            _imp_domain(page, dm, _CTX_READY.get(dm, ""))   # ⭐ **只切域**（这一步**还没选文件**）
            got1 = page.evaluate("""() => {
                const v = document.querySelector('#view');
                const t = v.querySelector('[data-act="impPjToggle"]');
                const sp = t ? t.querySelector('span') : null;      /* 第 1 个 span = 选中的项目名（第 2 个是 ▼） */
                return {cut: !!v.querySelector('#impCut'), ym: !!v.querySelector('#impYm'),
                        pj: !!t, label: sp ? (sp.innerText || '').trim() : '',
                        hasFile: !!v.querySelector('[data-act="impPick"]')};
            }""")
            print(f"①″ {dm} 范围栏（切域后 · 未选文件）= {got1}")
            oks1 = [
                (got1["cut"] == want_cut,
                 f"`{dm}` 的「截止核算月」" + ("在（它声明了 `cutoff_ym`）" if want_cut
                                          else "**没画**（它没声明 `cutoff_ym` ⇒ 画了也是填了不生效）")),
                (got1["ym"] == want_ym,
                 f"`{dm}` 的「本批归属年月」" + ("在（它声明了 `year_month`）" if want_ym
                                           else "**没画**（它没声明 `year_month`）")),
                (got1["pj"] == want_pj,
                 f"`{dm}` " + ("的项目面板**在 ①**（它给了 `projects`）" if want_pj
                               else "**没画**项目面板（它没给 `projects`）")),
            ]
            if want_pj:
                oks1.append((got1["label"] == "请选择项目",
                             f"`{dm}` 的项目格**默认不预选**（文案应为「请选择项目」，实为「{got1['label']}」）"
                             " —— 默认值不诱导：⛔ 系统不替用户挑项目"))
            for ok1, what1 in oks1:
                print(("  ✅ " if ok1 else "  ⛔ ") + "⑳″ " + what1)
                if not ok1:
                    errors.append(f"① 范围栏自检未通过（{dm}）：" + what1)

            # ③″ 预览屏：只读回显 ＋ 未选项目 ⇒ ④ 置灰 ＋ 真点选一个 ⇒ 可用 ＋ 截止月跟随项目
            fx = fs / f"imp_smoke_{dm}.xlsx"
            n_cols = _mk_xlsx(fx, dm)
            _imp_pick(page, dm, fx)                         # 选域 → 上传 → 解析（② 出来）
            page.click('[data-act="impPreview"]')           # ② → ③（**只读**：预览阶段不写库）
            # ⚠️ 预览卡没出来时**必须把页首那句话打出来**：`IMP.msg` 在壳的闭包里，真机取不到 ——
            #    而"预览失败：…"正是它写上去的（⛔ 只报一句 `TimeoutError` 等于把病因藏了）。
            try:
                page.wait_for_selector('[data-act="impCommit"]', timeout=20000)   # 预览卡到了（落库按钮只在这）
                ok_card = True
            except Exception:                              # noqa: BLE001
                ok_card = False
            if not ok_card:
                notice = page.evaluate(
                    "() => (document.querySelector('#view').innerText || '').slice(0, 220)")
                print(f"  ⛔ ③″ {dm} 预览卡没出来 —— 页首提示：{notice!r}")
                errors.append(f"③ 预览屏自检未通过（{dm}）：预览卡没出来（页首：{notice[:130]}）")
                continue
            got3 = page.evaluate("""() => {
                const v = document.querySelector('#view');
                const btn = v.querySelector('[data-act="impCommit"]');
                return {echo: (v.innerText || '').includes('本批数据将写入'),
                        echoTxt: ((v.innerText.match(/本批数据将写入[^\\n]{0,90}/) || [''])[0]).trim(),
                        disabled: !!(btn && btn.disabled)};
            }""")
            print(f"③″ {dm} 预览卡 = {got3}（表头 {n_cols} 列）")
            oks3 = [
                (got3["echo"],
                 f"`{dm}` 预览屏有**只读回显**「本批数据将写入…」（{got3['echoTxt']}）"
                 " —— ④ 之前必须能复核范围（守则 §4 防误导）"),
            ]
            if want_pj:
                oks3.append((got3["disabled"],
                             f"`{dm}` **没选项目 ⇒ 「④ 确认落库」置灰**（⛔ 系统不替你挑、"
                             "也不许点了才报错）"))
                # ⭐⭐ ①‴ **「项目」面板不许被宿主卡片裁**（`TAIL-109` · 用户 2026-09-26 报障原话：
                #    「通用导入的项目选择控件，**行数显示不全**」）。
                #    ⭐ 根因（**真机量出来的**）：`.card{...overflow:hidden}` 把面板下沿裁掉 63px ⇒
                #       最下面 2~3 行**既看不见也滚不到**（面板自身 `scrollH≈clientH` —— 不是它自己的滚动问题）。
                #    ⇒ 修法：渲染后把面板提升为 `fixed`（见 `placePops` —— `TAIL-110` 起是**全站通用**机制）。
                #    ⚠️ **CSS 的 overflow 裁剪离线断言看不见**（`test_imp_shell` 只能查"钩子在不在"）
                #       ⇒ 这一条是**唯一能证明"真的没被裁"**的地方：用**点命中**判（几何算法对 fixed 会误判）。
                #    量完**把面板点回去关掉**（下面那步 `got4` 期望的是"面板关着、点一次开"）。
                panel = page.evaluate("""() => {
                    const v = document.querySelector('#view');
                    const t0 = v.querySelector('[data-act="impPjToggle"]');
                    if (!t0) return {err: '没有项目面板'};
                    t0.click();
                    /* ⚠️⚠️ 上面这次 click 会触发 `render()` ⇒ `t0` **已脱离 DOM**（拿旧节点再点 = 什么都不发生
                       ⇒ 面板留在展开态 ⇒ 下面那步"点一次开"反而把它**关掉**，实测报「能开 0 个候选」）。
                       ⇒ 收尾一律**重新查一次**按钮。 */
                    const ins = [...v.querySelectorAll('[data-act="impPjPick"]')];
                    let p = ins[0];
                    while (p && !(p.classList && p.classList.contains('pjpop'))) p = p.parentElement;
                    const close = () => { const t = v.querySelector('[data-act="impPjToggle"]'); if (t) t.click(); };
                    if (!p || !ins.length) { close(); return {err: '面板没开/找不到 .pjpop'}; }
                    const last = ins[ins.length - 1];
                    const lr = last.getBoundingClientRect();
                    const hit = document.elementFromPoint(lr.left + 6, lr.top + lr.height / 2);
                    const out = {n: ins.length, pos: getComputedStyle(p).position,
                                 clientH: p.clientHeight, scrollH: p.scrollHeight,
                                 lastInViewport: lr.bottom <= innerHeight && lr.top >= 0,
                                 lastHittable: !!(hit && p.contains(hit))};
                    close();
                    return out;
                }""")
                print(f"①‴ {dm} 项目面板 = {panel}")
                if dm == "m06_proc":
                    oks3.append((panel.get("pos") == "fixed",
                                 "「项目」面板渲染后**被提升为 `fixed`**（否则被 `.card{overflow:hidden}` 裁掉 "
                                 "—— 用户 2026-09-26 报的「行数显示不全」）"))
                    oks3.append((bool(panel.get("n")) and bool(panel.get("lastHittable"))
                                 and bool(panel.get("lastInViewport")),
                                 f"面板**最后一行也看得见、点得到**（{panel.get('n')} 个候选 · "
                                 f"clientH={panel.get('clientH')} / scrollH={panel.get('scrollH')} "
                                 f"· 点命中在面板内={panel.get('lastHittable')}）"))
                # ⭐ 真点面板选第一个候选 ⇒ ④ 变可用；m06 另验「截止核算月跟着换」
                exp = page.evaluate("""async (dm) => {
                    const d = await (await fetch('/api/imp/' + dm + '/options')).json();
                    const p = (d.projects || [])[0] || '';
                    return {p: p, cut: ((d.cutoffs || {})[p] || '')};
                }""", dm)
                got4 = page.evaluate("""() => {
                    const v = document.querySelector('#view');
                    v.querySelector('[data-act="impPjToggle"]').click();
                    const open = v.querySelectorAll('[data-act="impPjPick"]').length;
                    const r = [...v.querySelectorAll('[data-act="impPjPick"]')][0];
                    if (r) r.click();
                    const btn = v.querySelector('[data-act="impCommit"]');
                    const cut = v.querySelector('#impCut');
                    return {open: open, closed: v.querySelectorAll('[data-act="impPjPick"]').length,
                            disabled: !!(btn && btn.disabled), cut: cut ? cut.value : null};
                }""")
                oks3.append((not got4["disabled"],
                             f"`{dm}` 真点选一个项目 ⇒ 「④ 确认落库」**变可用**"
                             f"（面板真点能开 {got4['open']} 个候选 · 选完自动收 {got4['closed']}）"))
                if dm == "m06_proc" and exp["p"]:
                    oks3.append((got4["cut"] == exp["cut"],
                                 f"`m06_proc` 换项目 ⇒ 「截止核算月」**跟着换**（选 `{exp['p']}` ⇒ "
                                 f"框里 `{got4['cut']}` · 域给的 `cutoffs` 是 `{exp['cut']}`）"
                                 " —— 此前它只在进域那一刻取一次 ⇒ 会把 A 项目的分界写给 B（真缺陷）"))
                # ⭐⭐ `m11_jc`：**选完项目再预览一次** ⇒ ③ 必须报出「配上几条 / 配不上几条」
                #    （`TAIL-106` 用户原话：「能否在选文件时就选定项目、并**立刻显示"匹配上多少"**」）。
                #    ⚠️ 必须先重跑一次预览：上一屏那个数是在**没选项目**时算的（域钩子当时只能回一句提示）。
                if dm == "m11_jc":
                    page.click('[data-act="impPreview"]')
                    try:
                        page.wait_for_function(
                            "() => (document.querySelector('#view').innerText || '')"
                            ".includes('没配上的行')", timeout=20000)
                        ok_pre = True
                    except Exception:                              # noqa: BLE001
                        ok_pre = False
                    txt = page.evaluate("() => document.querySelector('#view').innerText || ''")
                    print(f"③‴ m11_jc 对号预览 = {txt[txt.find('将写入'):][:120]!r}")
                    oks3.append((ok_pre and "配上" in txt and "配不上" in txt,
                                 "`m11_jc` ③ 报出「**配上 / 配不上**」两个数"
                                 "（改动前 ③ 一条对号信息都没有，得等到 ④ 落库才知道）"))
                    oks3.append(("没配上的行" in txt,
                                 "`m11_jc` ③ 把没配上的行**逐条列出来**（含原因）—— ⛔ 不是只丢一个总数"))
            for ok3, what3 in oks3:
                print(("  ✅ " if ok3 else "  ⛔ ") + "⑳′ " + what3)
                if not ok3:
                    errors.append(f"③ 预览屏自检未通过（{dm}）：" + what3)

        # ⚠️ 原「③ 预览（域上下文栏）」那一段**已于 2026-09-26 上移合并进 ①″/③″**
        #    （范围栏从 ③ 挪到了 ① ⇒ 判词必须跟着挪，否则它盯的是一个已经不存在的位置）。

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
