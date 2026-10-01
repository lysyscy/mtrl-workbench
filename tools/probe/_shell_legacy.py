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
import app.models_registry  # noqa: E402, F401

#: 页 → (中文名, 该页必须看得见的几个标志串)
PAGES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # ⚠️ 2026-09-27（`TAIL-127` · 用户裁定 **B**「连接参数搬回它起作用的地方」）：标志串随之改 ——
    #    「**与直觉相反**」原先是**本页**的标志串，而那两个「打印版式 ID」已搬进 `m03` 的打印机弹窗
    #    ⇒ 本页改认「**外观主题**」（它现在才是本页的主角），而"反直觉提示还在不在"由下面
    #    `_check_moved` 在**它真正在的地方**（打印机弹窗）证 —— ⛔ 别为了留住旧标志串在本页摆一句空话。
    ("set", "系统设置", ("连接参数", "变更留痕", "外观主题")),
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
    # ⭐ 2026-09-26（用户报障「**这些不会落库的行，要在行上直接标**」）：再补**一行会被本域拒收的** ——
    #    ⚠️ 不补的话，③ 那屏里一行「不写入」都不会出现 ⇒ 真机判词**空转**
    #       （"没有行可标"也能通过 = **假绿**，比没有判词更糟）。
    #    ⚠️ 这一行**照本域自己的拒收口径造**（⛔ 不是随便塞一行凑数）：
    #       `m06_proc` 的核算月写成一串**非标准文本** —— 正是用户 2026-09-26 截图里那份文件被拒的形态。
    #    ⚠️ 只有 `m06_proc` 补：`m04_plan` **没有**「不会落库的行」（项目没配上照样进库）⇒ 真机那趟
    #       顺带证到"**没有就不标**"（⛔ 别为了凑数据硬造一行）。
    if domain == "m06_proc":
        ws.append([("2025年9月（三标）" if f.key == "ym" else 0) for f in fields])
        # ⭐ 2026-09-27（用户报障「**请将所有不写入输出的行也进行标注**」）：再补**尾部合计行** ——
        #    它是「本来就跳过」那一类的真实形态（用户截图里红框的正是「小计」「合计」两行）。
        #    ⚠️ 不补的话，真机判词只能量到「要你处理」那一类 ⇒ 新加的**灰底标记一处都没验证**
        #       （那等于新功能没有真机证据）。
        ws.append(["合计"] + [0] * (len(fields) - 1))
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
        #: ⚠️ 2026-10-01（`TAIL-204` 第 7 步）**换落点**：原 `.workbuddy/scratch` 是**搬家遗留的旧落点** ——
        #:   盘上一直在（被 `.gitignore` 藏着 ⇒ `git status` 看不见），探针这几张 `imp_smoke_*.xlsx`
        #:   就一直在往那儿写；第 7 步把旧落点整棵清掉 ⇒ 改到**唯一的临时区** `work/00-scratch/`。
        fs = Path(__file__).resolve().parents[2] / ".codebuddy" / "work" / "00-scratch"
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
            # ⭐⭐ 2026-09-26（用户报障 · 原话：「**这些不会落库的行，要在行上直接标**，比如给一个浅色底，
            #    或者其他明确提示，这才叫好的前端设计，而不是还要**抬头去看文字说明**」· 通用导入页都这么做）。
            #    ⚠️ 离线（`test_imp_shell::test_不会落库的行要在行上直接标`）只能查"壳里有没有那几行代码"，
            #       **看不见真的有没有标上**（域有没有自报 / 行号对不对得上 / 底色是不是真不一样）
            #       ⇒ 只有这里能量出来（CSS 与按行号匹配都是跑起来才成立的东西）。
            #    量四件：① 被域判「不落库」的行带 `.skiprow`；② 它跟**同一张表里**的普通行**底色不同**；
            #           ③ 行内有「不写入」那枚**文字**标记（色弱的人不靠颜色也能认）；
            #           ④ 图例在 ＋ 底部那句指向「已在上表逐行标出」。
            marks = page.evaluate("""() => {
                const v = document.querySelector('#view');
                const trs = [...v.querySelectorAll('table.dt tbody tr')];
                const has = t => t.classList.contains('skiprow');
                const plain = t => t.classList.contains('plain');
                const bg = t => getComputedStyle(t).backgroundColor;
                const skip = trs.filter(has);
                const skipBad = skip.filter(t => !plain(t));        /* 要你处理（黄） */
                const skipPlain = skip.filter(plain);               /* 本来就跳过（灰） */
                /* ⚠️ 普通行要取**同一张表**里的：图卡里还有"问题清单/域区块"几张表，
                   拿别张表的行来比底色等于比了个无关的东西。 */
                const host = skip.length ? skip[0].closest('table') : null;
                const peers = host ? [...host.querySelectorAll('tbody tr')].filter(t => !has(t)) : [];
                const said = re => Number(((v.innerText || '').match(re) || [0, 0])[1] || 0);
                return {rows: trs.length,
                        bad: skipBad.length, plain: skipPlain.length,
                        badBg: skipBad.length ? bg(skipBad[0]) : null,
                        plainBg: skipPlain.length ? bg(skipPlain[0]) : null,
                        peerBg: peers.length ? bg(peers[0]) : null,
                        taggedBad: skipBad.filter(t => (t.innerText || '').includes('不写入')).length,
                        taggedPlain: skipPlain.filter(t => (t.innerText || '').includes('不导入')).length,
                        tipBad: skipBad.length ? (skipBad[0].getAttribute('title') || '') : '',
                        tipPlain: skipPlain.length ? (skipPlain[0].getAttribute('title') || '') : '',
                        /* ⭐ **卡片上说得出的两个数** —— 判词要拿它们跟**行上真标出来的条数**比
                           （⚠️ 没这一条，"壳根本没标"与"本来就没有行要标"长得一样 ⇒ 判词**空转**：
                              把标行那行代码删掉也照样绿）。 */
                        nSaid: said(/有\\s*(\\d+)\\s*行/),          /* 「有 N 行不会写入」 */
                        nSaidPlain: said(/另有\\s*(\\d+)\\s*行/),    /* 「另有 M 行本来就跳过」 */
                        legend: (v.innerText || '').includes('要你处理')
                                && (v.innerText || '').includes('不用你改'),
                        hint: (v.innerText || '').includes('逐行标出'),
                        /* ⚠️ **表头几列 ⇒ 数据行就得几格**：这一条真抓到过东西 ——
                           被标的那张表题头写着「行｜核算月｜…」（18 格），而数据行只有 17 格
                           （**行号那格根本没画出来**）⇒ 用别的办法量都会说"看着挺好"。 */
                        skipTable: (() => {
                            const tb = skip.length ? skip[0].closest('table') : null;
                            if (!tb) return null;
                            const body = [...tb.querySelectorAll('tbody tr')];
                            return {nHead: tb.querySelectorAll('th').length,
                                    nTd: body.map(x => x.children.length).slice(0, 3),
                                    head: [...tb.querySelectorAll('th')].map(h => h.innerText.trim())
                                                                    .join('|').slice(0, 26)};
                        })()};
            }""")
            print(f"③″ {dm} 行级标记 = {marks}")
            st = marks["skipTable"] or {}
            if st:
                print(f"     · 被标那行的表 = 题头 {st['nHead']} 格 / 数据行 {st['nTd']} 格"
                      f"（{st['head']}…）")
            # ⭐⭐ 2026-09-27（用户报障：「**请将所有不写入输出的行也进行标注**」· 他截图里红框的是
            #    「小计」「合计」行）：**两类都要标、且必须一眼分得开**（守则 §2.8）——
            #    量六件：① 「要你处理」条数 == 卡片说的数；② 「本来就跳过」条数 == 卡片说的数；
            #    ③ 两类各带自己的**行内文字**标记（「不写入」/「不导入」）；
            #    ④ 两类底色都 ≠ 普通行；⑤ ⭐ **两类底色彼此也不同**（混成一种色 = 用户以为
            #    "合计行也要我改"）；⑥ 图例在（说清「要你处理」/「不用你改」）＋ 底部指向"逐行标出"。
            if marks["bad"] or marks["plain"] or marks["nSaid"] or marks["nSaidPlain"]:
                ok = (marks["bad"] == marks["nSaid"]                         # ① 数对得上
                      and marks["plain"] == marks["nSaidPlain"]              # ② 数对得上
                      and marks["taggedBad"] == marks["bad"]                 # ③ 每行有文字标记
                      and marks["taggedPlain"] == marks["plain"]
                      and (not marks["bad"] or marks["badBg"] != marks["peerBg"])      # ④
                      and (not marks["plain"] or marks["plainBg"] != marks["peerBg"])
                      and (not (marks["bad"] and marks["plain"])
                           or marks["badBg"] != marks["plainBg"])                        # ⑤
                      and marks["legend"] and marks["hint"]
                      and bool(st) and st["nHead"] == st["nTd"][0])                  # ⑥ 题头几列＝行几格
                oks3.append((ok,
                             f"`{dm}` 卡片说「不会写入 {marks['nSaid']} 行 · 本来就跳过 "
                             f"{marks['nSaidPlain']} 行」⇒ **表里真标出 {marks['bad']} ＋ "
                             f"{marks['plain']} 行**（文字标记「不写入」{marks['taggedBad']} · "
                             f"「不导入」{marks['taggedPlain']}；底色 要处理 {marks['badBg']} / "
                             f"本来就跳过 {marks['plainBg']} / 普通行 {marks['peerBg']}；"
                             f"题头 {st.get('nHead')} 格·行 {st.get('nTd')} 格）"
                             " —— 用户报障原话：「要在行上直接标……而不是还要抬头去看文字说明」、"
                             "「**请将所有不写入输出的行也进行标注**」"))
            else:
                print(f"  ℹ️ {dm} 这批测试数据里**没有**「不写入的行」⇒ 行级标记无从量起"
                      "（静态判词仍守着「域必自报 ＋ 壳必标」）")
                oks3.append((not marks["legend"] and not marks["hint"],
                             f"`{dm}` 这批数据里**没有**「不写入的行」⇒ 表里**一行都没标**、"
                             "也没有图例（⛔ 别为不存在的状态摆一个说明）"))
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
                    /* ⚠️ "最后一行"只许取**可见**的那些：归档折叠（②）会把归档段 `hidden` 掉，
                       被折起来的行 rect 是 0 ⇒ 拿它判"看得见/点得到"就是**假红**（2026-09-27 前置修正）。 */
                    const vis = ins.filter(x => x.offsetParent !== null);
                    const last = vis[vis.length - 1] || ins[ins.length - 1];
                    const lr = last.getBoundingClientRect();
                    const hit = document.elementFromPoint(lr.left + 6, lr.top + lr.height / 2);
                    const out = {n: ins.length, nVis: vis.length, pos: getComputedStyle(p).position,
                                clientH: p.clientHeight, scrollH: p.scrollHeight,
                                lastInViewport: lr.bottom <= innerHeight && lr.top >= 0,
                                lastHittable: !!(hit && p.contains(hit))};
                    /* ⭐⭐ ①②（2026-09-27 用户裁定）：**搜索框真机验** —— 打字 ⇒ 只切 DOM 显示（不重绘）。
                       判：① 可见候选数**变少**（或本来就只 1 个）② 命中的行**都含**该词
                       ③ 搜不到时给**人话空态**（⛔ 不是一片空白）④ 清空后**恢复**原样。 */
                    const box = p.querySelector('[data-act="pjSearch"]');
                    if (box) {
                        const before = vis.length;
                        const nm = (ins[ins.length - 1].closest('label').dataset.pjMatch || '').split(' ')[0];
                        const word = nm || 'zzz';
                        box.value = word; box.dispatchEvent(new Event('input', {bubbles: true}));
                        const rows = [...v.querySelectorAll('[data-pj-row]')];
                        const shown = rows.filter(r => !r.hidden);
                        const after = shown.filter(r => (r.querySelector('input') || {}).offsetParent !== null).length;
                        const hitOk = shown.every(r => (r.dataset.pjMatch || '').includes(word.toLowerCase()));
                        box.value = 'zzz绝不存在zzz'; box.dispatchEvent(new Event('input', {bubbles: true}));
                        const none = v.querySelector('[data-pj-none]');
                        const noneShown = !!(none && !none.hidden);
                        const noneText = none ? String(none.textContent || '').slice(0, 20) : '';
                        box.value = ''; box.dispatchEvent(new Event('input', {bubbles: true}));
                        const back = [...v.querySelectorAll('[data-act="impPjPick"]')]
                            .filter(x => x.offsetParent !== null).length;
                        out.search = {before: before, word: word, after: after, hitOk: hitOk,
                                      noneShown: noneShown, noneText: noneText, back: back};
                    }
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
                if dm == "m06_proc" and panel.get("search"):
                    sc = panel["search"]
                    oks3.append((bool(sc["word"]) and sc["hitOk"] and sc["after"] <= max(1, sc["before"])
                                 and (sc["after"] < sc["before"] or sc["before"] <= 1),
                                 f"① 项目面板**搜索**（真机）：打「{sc['word']}」⇒ 可见候选 {sc['before']} → "
                                 f"{sc['after']} 行、命中行都含该词（打字**只切 DOM**、不重绘 ⇒ 不丢焦点）"))
                    oks3.append((sc["noneShown"] and "没有匹配" in sc["noneText"] and sc["back"] == sc["before"],
                                 f"① 搜不到时给的是**人话空态**「{sc['noneText']}」、清空后恢复 {sc['back']} 行"
                                 "（⛔ 不是一片空白 —— 那会让用户以为面板坏了）"))
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
                    const all = [...v.querySelectorAll('[data-act="impPjPick"]')];
                    /* ⭐⭐ 2026-09-26（用户报障「**候选和选择后显示的不一样**」）：
                       专门挑一个「**显示名 ≠ 仓库名**」的候选（正是他截图里那种：候选写「内蒙宜化项目」、
                       按钮却写「内蒙石灰窑项目」= 仓库名），点它，再看**按钮上**写的哪个名字。
                       ⛔ 直接取第 0 个候选会**测不出**这个病（那个候选的两个名字可能正好相同）。 */
                    let pick = null, want = '';
                    for (const x of all) {
                        const lb = x.closest('label');
                        const sp = lb ? lb.querySelector('span') : null;
                        const nm = sp ? sp.innerText.trim() : '';
                        if (nm && nm !== String(x.dataset.pj || '')) { pick = x; want = nm; break; }
                    }
                    if (!pick) pick = all[0];
                    if (pick) pick.click();
                    const btn = v.querySelector('[data-act="impPjToggle"]');
                    const shown = btn && btn.querySelector('span') ? btn.querySelector('span').innerText.trim() : '';
                    const commit = v.querySelector('[data-act="impCommit"]');
                    const cut = v.querySelector('#impCut');
                    return {open: open, closed: v.querySelectorAll('[data-act="impPjPick"]').length,
                            disabled: !!(commit && commit.disabled), cut: cut ? cut.value : null,
                            differ: !!want, want: want, shown: shown};
                }""")
                oks3.append((not got4["disabled"],
                             f"`{dm}` 真点选一个项目 ⇒ 「④ 确认落库」**变可用**"
                             f"（面板真点能开 {got4['open']} 个候选 · 选完自动收 {got4['closed']}）"))
                if got4["differ"]:
                    oks3.append((got4["shown"] == got4["want"],
                                 f"`{dm}` **选完按钮上的名字 = 候选里那个名字**"
                                 f"（候选写 `{got4['want']}` ⇒ 选完按钮写 `{got4['shown']}`）"
                                 "—— 用户 2026-09-26 报障：两处显示**不一样**"))
                else:
                    print(f"  ℹ️ {dm} 候选里没有「显示名 ≠ 仓库名」的，跳过「名字一致性」这条真机判词"
                          "（静态判词仍守着「三处只走 impPjLabel」）")
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
            /* ⭐⭐ `TAIL-114`（2026-09-27 用户裁定）：**导入页的候选**必须覆盖
               「**项目档案里有仓库名的每一个项目**」（含**没有任何数据**的）——
               否则"给一个新项目导历史资料"这件事根本做不到（候选里就没有它）。
               ⚠️ 判词**锚在档案上**（不在"后端 vs 页面"的差上）：两处一起变小时，差恒为 0 ⇒ 抓不到回退。
               ⚠️⚠️ **必须先选 `m06_proc` 域**：候选是**跟着域变的**（那一刻可能停在别的域上 ——
                  实测踩到：域停在 `m11_jc` ⇒ 面板候选 17 个，看着像"已经修好了"，其实是另一域的候选）。
               ⚠️ 只在**数据导入页**量（那页才有 `impPjToggle` / `PJs`）⇒ 别的页返回 -1，不判。 */
            const v = document.querySelector('#view');
            const t = v.querySelector('[data-act="impPjToggle"]');
            r.panelN = -1; r.missArch = -1; r.archN = -1; r.dom = '';
            if (t) {
                const sel = v.querySelector('[data-act="impDomain"]');
                const back = sel ? sel.value : '';
                if (sel && sel.value !== 'm06_proc') {
                    sel.value = 'm06_proc';
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                    await new Promise(done => setTimeout(done, 900));     /* 域上下文是**异步**取的 */
                }
                const sel2 = v.querySelector('[data-act="impDomain"]');
                r.dom = sel2 ? sel2.value : '';
                r.m06d = (await j('/api/imp/m06_proc/options')).projects.length;
                const t2 = v.querySelector('[data-act="impPjToggle"]');
                if (t2) {
                    t2.click();
                    const ins = [...v.querySelectorAll('[data-act="impPjPick"]')].map(x => x.dataset.pj);
                    const arch = (typeof PJs === 'object' && PJs)
                        ? PJs.filter(p => p.type !== 'shell' && p.name).map(p => p.name) : [];
                    r.panelN = ins.length;
                    r.archN = arch.length;
                    r.missArch = arch.filter(k => ins.indexOf(k) < 0).length;
                    const b = v.querySelector('[data-act="impPjToggle"]'); if (b) b.click();
                }
                if (sel2 && back && back !== 'm06_proc') {                 /* 量完切回去，⛔ 别影响后面的段 */
                    sel2.value = back;
                    sel2.dispatchEvent(new Event('change', {bubbles: true}));
                }
            }
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
        if got.get("panelN", -1) >= 0:
            oks.append((got["panelN"] == got["m06d"],
                        f"导入页候选 == 后端（{got['panelN']} vs {got['m06d']}）—— "
                        "若仍是「加载时求值 / 口径不一致」，这两个数会不一样"))
            oks.append((got["missArch"] == 0,
                        f"⭐⭐ **导入页候选覆盖了档案里有仓库名的每个项目**（档案 {got['archN']} 个 · "
                        f"面板 {got['panelN']} 个 · ⛔ 缺口 **{got['missArch']}** 个）—— "
                        "缺一个，那个项目的历史资料就永远导不进去（`TAIL-114`）"))
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + f"⑳ {what}")
            if not ok:
                errors.append("四个暂留件收口自检未通过：" + what)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ⛔ ⑳ 在「{stage}」这一步失败：{type(exc).__name__}: {str(exc)[:160]}")
        errors.append(f"四个暂留件收口自检异常（{stage}）：{type(exc).__name__}")

    # ⭐ 2026-09-27（`TAIL-127`）：**两个"搬了家"的连接参数入口**也要真机证到（判据随能力搬家）
    _check_moved(page, errors)

    # ⭐ 2026-09-27（`TAIL-129`）：**界面大小**档真的能改（点了即时生效、不刷新、字号真的变）
    _check_uiscale(page, errors)


def _check_uiscale(page, errors: list[str]) -> None:
    """⭐ `TAIL-129`（2026-09-27 · 用户裁定走**方案 B**）：**界面大小**这一档真的能改。

    ⚠️ 为什么必须真机：方案 B 的效果全在**CSS 变量 `--fscale` 被真的写进 `<html>`** 这一下 ——
       离线只能证"样式里都乘了它""壳里有那段代码"，证不到"点了它真的变"。
    判词四件（**都在同一屏上量**）：
      ① 点另一档 ⇒ `--fscale` 变了；② **页面没刷新**（`VIEW` 不变 —— 刷新会把用户扔回看板）；
      ③ **正文字号真的变了**（`getComputedStyle(body).fontSize`）—— 这才叫"能看清"；
      ④ **复原**（点回原来那一档）并断言回到原值 —— ⚠️ 自检⛔ **不许留残留**（它会写库：
         界面大小是**按用户**存的，跑完必须还原成跑之前那个值）。
    """
    n = 0
    try:
        page.click('[data-k="set"]')
        page.wait_for_selector('#view [data-act="uiScaleSet"]', timeout=8000)
        got0 = page.evaluate("""() => {
            const bs = [...document.querySelectorAll('#view [data-act="uiScaleSet"]')];
            const cur = bs.findIndex(b => b.classList.contains('pri'));   /* 当前那一档带 pri */
            return {n: bs.length, cur: cur, fs: getComputedStyle(document.body).fontSize,
                    sc: getComputedStyle(document.documentElement).getPropertyValue('--fscale').trim()};
        }""")
        n = int(got0["n"])
        if n >= 2 and got0["cur"] >= 0:
            other = 0 if got0["cur"] != 0 else n - 1        # 挑**另一档**（⛔ 不赌档位键字面量）
            page.evaluate("""(i) => document.querySelectorAll('#view [data-act="uiScaleSet"]')[i].click()""",
                          other)
            page.wait_for_function(
                "(v) => getComputedStyle(document.documentElement)"
                ".getPropertyValue('--fscale').trim() !== v", arg=got0["sc"], timeout=8000)
            got1 = page.evaluate("""() => ({
                view: VIEW, fs: getComputedStyle(document.body).fontSize,
                sc: getComputedStyle(document.documentElement).getPropertyValue('--fscale').trim(),
            })""")
            ok = (got1["sc"] != got0["sc"]) and (got1["fs"] != got0["fs"]) and got1["view"] == "set"
            print(("  ✅ " if ok else "  ⛔ ")
                  + f"⑳ 界面大小：{n} 档 · 点另一档 ⇒ `--fscale` {got0['sc']}→{got1['sc']} · "
                    f"正文字号 {got0['fs']}→{got1['fs']} · 页面没刷新（VIEW={got1['view']}）")
            if not ok:
                errors.append("四个暂留件收口自检未通过：改了界面大小档但**字体没变**"
                              f"（或页面被刷新了）—— 实测 {got0} ⇒ {got1}")
            page.evaluate("""(i) => document.querySelectorAll('#view [data-act="uiScaleSet"]')[i].click()""",
                          got0["cur"])                       # ⭐ 复原
            page.wait_for_function(
                "(v) => getComputedStyle(document.documentElement)"
                ".getPropertyValue('--fscale').trim() === v", arg=got0["sc"], timeout=8000)
            back = page.evaluate("() => getComputedStyle(document.documentElement)"
                                 ".getPropertyValue('--fscale').trim()")
            print(("  ✅ " if back == got0["sc"] else "  ⛔ ")
                  + f"⑳ 界面大小：自检已**复原**到跑之前那一档（`--fscale`={back}）")
            if back != got0["sc"]:
                errors.append(f"四个暂留件收口自检未通过：界面大小自检**没复原**（{got0['sc']} → {back}）"
                              " —— 自检不许留残留（这一项是按用户存的）")
        else:
            errors.append(f"四个暂留件收口自检未通过：设置页的「界面大小」档位没画出来"
                          f"（实测 {n} 个档位按钮 · 选中档 {got0['cur']}）")
            print(f"  ⛔ ⑳ 界面大小：档位没画出来（实测 {n} 个）")
    except Exception as exc:                              # noqa: BLE001
        errors.append(f"四个暂留件收口自检异常（界面大小）：{type(exc).__name__}: {str(exc)[:120]}")
        print(f"  ⛔ ⑳ 界面大小：{type(exc).__name__}: {str(exc)[:120]}")


def _check_moved(page, errors: list[str]) -> None:
    """⭐ `TAIL-127`（2026-09-27 · 用户裁定 **B**）：连接参数**搬家后的两个入口**是否真的能用。

    用户原话：「连接参数这个板块说实话可以删掉，因为**不可能有变动**；那系统设置就只剩下主题色了」
    ⇒ 三个参数各自搬回**它起作用的地方**（守则 §5.8「换地方，不是删掉」）：
      · `i8 服务地址`       → 「i8 接入层」（`m02`）卡头的「**i8 连接设置**」（`BIND.m02` 注入）
      · 两个**打印版式 ID** → 「付款通知书」（`m03`）的「**打印机设置**」弹窗（`print-export.js`）

    ⚠️ **为什么这一条必须真机**：`V.set` 那一页现在已经**没有输入框**了 ⇒
       光看源码**证不到"能力还在"**（符号还在、入口没画出来 = 用户找不到）。
       ⭐ 判词里带上「**与直觉相反**」是有意的：那句是**配错版式的唯一提示**，
         它必须**在版式那一格旁边**出现（原先它在系统设置页，搬家后就跟过去）。
    """
    ok1 = ok2 = False
    try:
        page.click('[data-k="m02"]')
        page.wait_for_selector('#view [data-act="i8SetOpen"]', timeout=8000)
        page.click('[data-act="i8SetOpen"]')
        page.wait_for_selector('#m02I8Url', timeout=8000)
        got = page.evaluate("""() => ({
            has: !!document.querySelector('#m02I8Url'),
            txt: document.body.innerText || '',
        })""")
        ok1 = bool(got["has"]) and ("i8" in got["txt"])
        print(("  ✅ " if ok1 else "  ⛔ ")
              + "⑳ i8 服务地址**搬到「i8 接入层」页**了：卡头按钮 ⇒ 弹窗里有那一格（`#m02I8Url`）")
        if not ok1:
            errors.append("四个暂留件收口自检未通过：`m02` 的「i8 连接设置」入口/弹窗没出来"
                          "（连接参数搬家的这一半丢了 ⇒ 用户再也改不了 i8 地址）")
        page.click('[data-act="closeModal"]')
    except Exception as exc:                              # noqa: BLE001
        errors.append(f"四个暂留件收口自检异常（m02 的 i8 连接设置入口）：{type(exc).__name__}: "
                      f"{str(exc)[:120]}")
        print(f"  ⛔ ⑳ m02 i8 连接设置入口：{type(exc).__name__}: {str(exc)[:120]}")

    try:
        page.click('[data-k="m03"]')
        page.wait_for_selector('#view [data-act="m03PrinterOpen"]', timeout=8000)
        page.click('[data-act="m03PrinterOpen"]')
        page.wait_for_selector('#m03PidMat', timeout=8000)
        d = page.evaluate("""() => ({
            a: !!document.querySelector('#m03PidMat'),
            b: !!document.querySelector('#m03PidMech'),
            t: document.body.innerText || '',
        })""")
        need = ("其他支出", "付款通知书", "与直觉相反")
        ok2 = bool(d["a"]) and bool(d["b"]) and all(x in d["t"] for x in need)
        print(("  ✅ " if ok2 else "  ⛔ ")
              + "⑳ 两个**打印版式 ID 搬到打印机弹窗**了：两格在（`#m03PidMat`/`#m03PidMech`）"
              + "＋ 反直觉提示原样在（「与直觉相反 / 其他支出 / 付款通知书」）")
        if not ok2:
            errors.append("四个暂留件收口自检未通过：打印机弹窗里没看到「打印版式」两格"
                          f"（或反直觉提示丢了）—— 实测 {d}")
        page.click('[data-act="closeModal"]')
    except Exception as exc:                              # noqa: BLE001
        errors.append(f"四个暂留件收口自检异常（打印机弹窗里的打印版式）：{type(exc).__name__}: "
                      f"{str(exc)[:120]}")
        print(f"  ⛔ ⑳ m03 打印版式两格：{type(exc).__name__}: {str(exc)[:120]}")


__all__ = ["check"]
