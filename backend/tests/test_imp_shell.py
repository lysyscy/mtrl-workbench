"""壳侧「**数据导入**」页（`TAIL-75` `B5`）—— 入口 / 四步向导 / ⭐ **无死控件**（离线可验的那半）。

⭐ 为什么要有本件：真机自检（`tools/probe/_shell_legacy.py` 的 ② 「无死控件」）要**起服务 ＋ 浏览器**才跑得起来
   ⇒ 把它的判据做成**离线等价物**：页面上每个 `data-act` 都能解析到 `ACT`
     （**表单元素**那半边 ⭐ `#2` 2026-09-26 起不必再"登记"—— `change` 由委托层直呼 `ACT[a]`）。
   ⚠️ **只查本页**（`V.imp` 那一段）：整壳扫会撞上别的页的边界情况（例如 `go`/`exp` 走的是委托），
     那些不是本件要管的事 —— 本件只管"新加的这页别漏登记"。
"""

from __future__ import annotations

import re

from tests.shell_load_helpers import loaders, page_load
from tests.shell_src import SHELL, act_entry, func_body

#: 本页自己的动作（`ACT.<名>` 必须都在）
#: ⚠️ 2026-09-26（`TAIL-103`）：`impPj`（原来挂在自造的 `<select>` 上）**换成共用面板的两个动作** ——
#:    `impPjToggle`（展开/收起）+ `impPjPick`（面板内单选）。理由见 `V.imp` 里 `ctxBar` 那段注释。
PAGE_ACTS = ("impDomain", "impPick", "impParse", "impMap", "impPjToggle", "impPjPick", "impPreview",
             "impCommit", "impRollback", "impReset")
#: ⛔ `#2`（2026-09-26）起**没有 `CHG` 名单了** ⇒ 这里不再需要"哪些动作挂在表单元素上"的清单：
#:    `change` 委托**看见 `data-act` 就跑**（`change` 只可能来自表单元素），漏登记这回事不存在。


def _imp_region() -> str:
    """`impSetDomain` 函数起 → `ACT.impRollback` 动作起那一段（本页的全部代码 —— 含**切域**那段）。

    ⚠️ 起点 2026-09-26 从 `V.imp = ()` 前移到 `impSetDomain`：**域上下文就在这里读**，
       而"壳里不许认域号"这条判据必须把它框进来（起点留在 `V.imp` 会漏掉真出过问题的那一段）。

    ⭐ 2026-10-04（`TAIL-219` 批 2b 余下 ①）：两个锚**不再写壳里的字面**，改成**先从语义窗按名字取**
       （`func_body("impSetDomain")` / `act_entry("impRollback")`）再按位置切 ——
       后者正是新添的 **"`ACT.<名> = …` 赋值式"** 支路（本页族全是这种形态）。
    ⚠️ 它仍是一段"**两个具名之物之间**"的区间：窗里**没有、也不打算有**一个万能的 `between(a,b)`
       （那等于把标记串请进窗里）⇒ 本函数**登记为正当**（不属于要清的剪刀；找不到时上面 `assert` 会喊）。
    """
    i = SHELL.find(func_body("impSetDomain"))
    j = SHELL.find(act_entry("impRollback"))
    assert i > 0 and j > i, "壳里找不到「数据导入」页（形态变了就同批改本件）"
    return SHELL[i:j]


def test_面板三件是全局共用件_不许写成_IMP_的方法():
    """⭐ 2026-09-26 收尾核「③ 预览」屏时查出（**真 bug · 已被本判据挡在离线**）：

    面板三件（`pjIsOpen` / `pjToggle` / `pjClose`）是 `projPanel` 配套的**全局共用件**
    （20 多处调用点都写 `pjToggle('ledPj')` 这种裸名），⛔ **不是 `IMP` 的方法**。

    ⚠️ **为什么四个闸门全绿而它是坏的**：写成 `IMP.pjClose('impPj')` **语法完全合法**
       （调用 `undefined` ⇒ 点下去才 `TypeError`），`X() = Y` 那种形态连 `node --check`/语法哨都放行；
       而 `test_imp_shell` 旧断言只查**名字在不在**（`ACT.impPjToggle` 存在 ✔）。
    ⚠️ **为什么真机也没抓到**：那三处（切域 / 重来 / 选完收起）＋渲染展开态那一处，**只在 ③ 预览卡**上
       才跑到（`ctxBar` 在 `prevCard` 里）—— 而真机自检此前到 ② 列映射为止，**从没走到 ③**。
       ⇐ 这正是"把真机证据补齐"的直接价值：**补齐的过程本身就抓出一个 live bug**。

    ⇒ 判据：壳里⛔ 不许出现 `IMP.pjXxx(` 这种写法（**剥块注释**后查 —— 注释里会**引述**这个坏形态作留痕）。
    """
    code = re.sub(r"/\*.*?\*/", "", SHELL, flags=re.S)     # ⚠️ 剥块注释：引述 ≠ 实现
    for bad in ("IMP.pjIsOpen(", "IMP.pjToggle(", "IMP.pjClose("):
        assert bad not in code, (
            f"壳里出现了 `{bad}` —— 面板三件是**全局共用件**（`projPanel` 配套），"
            "写成 `IMP.` 的方法语法合法、点下去才 TypeError（闸门全都看不见）")


def _imp_code() -> str:
    """本页的**代码**（剥掉块注释）。

    ⚠️ 下面那条判据要在**实现**里找被禁的写法，而注释里会**引述**它（"原来这里写的是 X，改成 Y"）——
       不剥注释 ⇒ 说明性的注释会把判据自己判红（本仓踩过"拿注释当实现"）。
    """
    return re.sub(r"/\*.*?\*/", "", _imp_region(), flags=re.S)


# ⛔ `_chg_names()` 已随 `CHG` 名单一起删（`#2` 2026-09-26）—— 名单没了，它没有主人。


def test_四步条同屏只许一条_且当前步要亮():
    """守则 §5.9（同一屏做优先级）/ §4.4（相似元素不制造歧义）。

    ⚠️ `A8` 逐页（`imp` 数据导入 · 2026-09-29）查出：这条**从来没有机器判据** ——
       用户 2026-09-26 按截图报过「**两条一模一样的四步条**」⇒ 裁定「**只留卡里那条**」，
       修复落在 `V.imp` 的 `return` 那行（⛔ 不再在卡外又画一遍），但**只靠一句注释记着**。
    ⚠️ 同批订正一处**过期注释**：`lgSteps` 原写「三步条 / `at` = 0/1/2」，而 `IMP_STEPS` 是**四项**。
    ⚠️ 能证伪：在 `V.imp` 的 `return` 里再加一次 `lgSteps(IMP_STEPS, IMP.step)`（＝当年那个 bug）
       / 把 `IMP_STEPS` 删掉一项 / 把高亮的 `on`·`dn` 判断去掉 ⇒ 本件必红。
    ⚠️ 真机那半（**屏幕上真的只有一条**、且当前步真的亮着）由 `tools/probe/_shell_legacy.py` 的 ⑳ 段
       看着（它真上传真解析，走完 ①②③）—— ⛔ 同一 claim 不写两份。
    """
    region = _imp_region()                     # `impSetDomain` → `ACT.impRollback`（本页全部代码）
    # ⚠️⚠️ **必须先剥块注释再数**（2026-09-29 实测踩到）：`V.imp` 的 `return` 上面那段注释里
    #    **引述**了那个写法（「卡内的 `head` 里那份是它自己的（`lgSteps(IMP_STEPS, IMP.step)`）」）
    #    ⇒ 直接 `count` 会把**说给读代码的人听的那份**也数进去 ⇒ 恒为 2（本判据当场红成假红）。
    #    同 `test_ux_colors.py` / 本文件 `_act_body` 口径：**判实现，判注释不算**。
    code = re.sub(r"/\*.*?\*/", "", region, flags=re.S)
    assert code.count("lgSteps(") == 1, (
        f"`V.imp` 里画了 {code.count('lgSteps(')} 条步骤条 —— 用户 2026-09-26 报的正是"
        "「两条一模一样的四步条」（只许留卡里那条）")
    assert "const IMP_STEPS = ['① 选域与文件', '② 列映射', '③ 预览校验', '④ 确认写入'];" in SHELL, \
        "四步的文案/步数变了（本页是四步向导 —— 改动要同批核 `IMP.step` 的推进点）"
    assert "i === at ? 'on' : (i < at ? 'dn' : '')" in SHELL, \
        "步骤条不再区分「当前步 `on` / 走过的 `dn`」—— 用户就不知道自己在第几步了"


def test_数据导入页在壳里_四步向导_且无死控件():
    """⭐ 「通用导入面」在壳上真的**有入口、有四步、且控件都登记过**（无死控件）。"""
    # ① 入口：侧栏 ＋ 顶栏标题 ＋ 已接后端标注
    assert re.search(r"\[['\"]imp['\"],\s*['\"]数据导入['\"]", SHELL), "侧栏没有「数据导入」入口"
    assert re.search(r"\bimp:\s*['\"]数据导入['\"]", SHELL), "`TITLE` 里没有这一页"
    assert re.search(r"['\"]imp['\"]\]\)", SHELL) or "'imp'" in SHELL, "`WIRED` 没标这一页"
    # ② 取数路：进页拉"数据导入"那一路，且 LOADERS 有对应函数（⛔ 漏了 ⇒ 页面空白）
    assert page_load().get("imp") == ["数据导入"], page_load().get("imp")
    assert "数据导入" in loaders()
    # ③ 四步向导的四步文案都在（人看得见的流程）
    for step in ("① 选域与文件", "② 列映射", "③ 预览校验", "④ 确认写入"):
        assert step in SHELL, f"四步向导缺一步：{step}"
    # ④ 无死控件（离线等价物）：每个 `data-act` 都能解析到 `ACT`
    acts = set(re.findall(r"\nACT\.(\w+)\s*=", SHELL))
    missing = [a for a in PAGE_ACTS if a not in acts]
    assert not missing, f"这些动作没在 `ACT` 上定义 ⇒ 点了没反应（死控件）：{missing}"
    # ⑤ ⭐ `#2`（2026-09-26）起**不再需要登记**：`change` 委托「看见 `data-act` 就跑」
    #    （`change` 只可能来自表单元素）⇒ 判词换成**结构性两条**：名单不许回来 ＋ 委托不看名单。
    # ⚠️ 只查**真声明**（`const CHG=[`）：壳里还留着**讲历史**的注释（"那份名单已拆"之类），
    #    ⛔ 不能把留痕也算进来 —— 否则就变成"要么删留痕、要么判据假红"
    #    —— 那是说明、不是实现（同"注释里引述被禁写法"那一族坑，本仓已踩过多次）。
    assert "const CHG=[" not in SHELL, \
        "`CHG` 名单又回来了 —— `#2` 已裁定拆掉它（表单类动作不该再靠登记：漏一个就是静默丢弃）"
    assert "CHG.includes(" not in SHELL, \
        "`change` 委托又在过滤名单了 —— 那样「漏登记 ⇒ change 被静默丢弃」会复发"
    assert "if(ACT[a]) ACT[a](t,e);" in SHELL, "`change` 委托不是「不看名单直接跑」（结构变了？）"
    # ⑥ 页面上**真的用到**了这些动作（⛔ 光在 `ACT` 上定义、模板里没接 = 另一类死代码）。
    #    ⚠️ 两种接法都算：直接写在标签上（`data-act="x"`）或**经共用件传参**（`lgPick(id, 'x', …)`
    #    —— 它内部才拼出 `data-act="${pickAct}"`）⇒ 只认前者会把正常写法误判成"没接"（自测踩到）。
    body = _imp_region()
    for a in PAGE_ACTS:
        assert (f'data-act="{a}"' in body) or (f"'{a}'" in body), \
            f"动作 `{a}` 定义了却没用上（或没接在控件上）"


def test_导入回滚后把取数缓存全标脏():
    """⭐ 2026-09-23（`TAIL-78` · 查 `TAIL-75` 落库下游时查出）：**导入/回滚是跨页写 ⇒ 必须全标脏**。

    ⛔ 原先只删「机械 6 列 / 收发结存与大表」两路 —— 那是**旧导入页 `m06imp`（已下架）**单域时代的遗留，
       而 `B5` 起导入已是**通用面**（域由后端 `/api/imp/domains` 列）。
    ⚠️ **漏标的真后果**（实测路径）：`m05_flow` 落库走 `sync_stat_paid`（**重算唯一出口**）⇒
       付款通知书的「统计付款金额」变了 ⇒ m03 的「已付金额」与 m05 的欠款/台账/统计**都变了**；
       而 `LOADED` 记着"拉过了" ⇒ **切回那两页看到的是旧数**（对真数据说旧话）。
    ⛔ 也**不许**改成"补几个字面域名单"：域清单的主人在后端，壳里列一份 = 「加一个域要改两处」。
    """
    for act in ("impCommit", "impRollback"):
        # ⚠️ 剥块注释再查：本动作的注释里**引述**过那个写法（"原先这里手写清空"），不剥就假红。
        # ⭐ 2026-10-04（`TAIL-219` 批 2b 余下 ①）：改走语义窗 `act_entry`（本页族是 `ACT.<名> = …` 赋值式）。
        body = re.sub(r"/\*.*?\*/", "", act_entry(act), flags=re.S)
        # ⭐ `#3`（2026-09-26）**换落点**：判词不变（"导入/回滚改了别的域的数 ⇒ 不许留旧数"），
        #    但**不再要求业务动作自己写 `LOADED.clear()`** —— 那正是"靠自觉"（本仓 `TAIL-78` 就漏标过一路）。
        #    现在标脏的唯一主人 = **写出口**：`API.impCommit` / `API.impRollback` 都是写出口
        #    ⇒ `api.js` 里统一 `markCrossPageStale()`（判据 `test_wired_boot.py` 钉着"只许一处"）。
        assert ("API." + act) in body, \
            f"`{act}` 没走写出口 —— 那样就没有任何东西会全标脏（切回别页看旧数）"
        assert "LOADED.clear()" not in body, \
            f"`{act}` 又自己手写清空了 —— 标脏的唯一主人是写出口，业务动作里再写一遍就是两处口径"


def test_域上下文一律走通用面_壳里零域号分支():
    """⭐ 2026-09-26（用户报障「项目的选择要用通用模块」后收口）：**本页不许认域号**。

    判词：域上下文（候选项目 / 截止核算月 / 归属年月）**只能**来自通用面唯一一条读端点
      `GET /api/imp/{domain}/options`（由域的 `Hooks.options` 给），壳按"域**声明**了哪个键"渲染控件
      ⇒ **加一个域不用动壳**。⛔ 不许出现 `IMP.domain === '…'`（那等于壳里另抄一份"哪个域要什么"）、
      ⛔ 也不许调域专属读端点。

    ⚠️ **能证伪**（本条要防的就是它复发）：把任一处改回 `if (IMP.domain === 'm11_jc') …` ⇒ 本件必红。
       报障时的真实形态 = 集采域那条分支调**域专属端点** `API.m11List()`（`/api/m11/list`），
       而它给的是**对象** ⇒ 壳 `(p && p.key) || String(p)` 把空键的项目渲染成 `[object Object]`
       ⇒ 选中即报「找不到项目（仓库名 '[object Object]'）」。
    """
    code = _imp_code()                     # ⚠️ 剥掉注释再找（注释里会引述被禁的写法）
    assert "IMP.domain ===" not in code.replace(" ", ""), \
        "壳里又出现了域号分支 —— 「哪个域要哪些上下文」的主人是域自己（`Hooks.options`）"
    assert "API.m11List" not in code, \
        "集采域又去调域专属读端点 `/api/m11/list` 了（该走通用面的 `options` 端点）"
    assert "impOptions" in code, "域上下文没走通用面的 `options` 端点 —— 那又从哪来的？"
    # ⭐ 上下文那一栏必须**按域给的键**渲染（⛔ 不许再出现"是 m04 就给年月、否则给项目＋截止月"那种写法）
    assert "IMP.hasCut" in code and "IMP.hasYm" in code and "IMP.hasPj" in code, \
        "控件不是按域声明的键渲染的 —— 那么「截止核算月」又会跑给集采/付款计划（填了不生效）"


def test_范围栏画在第一步_且没选项目不许落库():
    """⭐⭐ 2026-09-26（用户裁定「全部按推荐做」）：**「范围」栏从 ③ 挪到 ①** ＋ **默认不预选项目**。

    用户原话（`TAIL-106`）：「匹配既然凭合同金额／贸易公司合同金额，为什么放到**最后一步**
    （③ 之后才选项目）？能否**在"选文件"时就选定项目**？」
    ⚠️ 报障的实质：`ctxBar` 原先只在 **③ 预览卡** 里渲染 ⇒ 用户**走到最后一步才知道要选项目**，
    而集采那一步**什么都看不出来**（对号在 ④ 才做）。

    ⭐ 同批修的**第二件事（默认值不诱导 · 守则 §4）**：原先 `IMP.wrap = ctx.warehouse ||
    ctx.project_key || IMP.org[0]` = **系统替用户挑好候选里的第一个**；用户没留意就点「④ 确认落库」
    —— `m06` 那一路是**直接写进该项目的"历史段"、且不报错**。⇒ 现在**不预选**，没选就不让落库。

    ⚠️ **能证伪**：把 `${ctxBar}` 搬回 `prevCard`／把 `IMP.org[0]` 加回去／去掉 ④ 的 `needPj` 置灰
        ⇒ 本件必红（真机侧另有一份：`tools/probe/_shell_legacy.py` 的 ①″/③″）。
    """
    code = _imp_code()
    # ⚠️ 锚点必须是**代码**（`_imp_code()` 已经把注释剥掉了）⇒ ⛔ 别拿 `/* ---- ③ … ---- */` 那种段头注释当锚点。
    i_head = code.find("const head = ")
    i_prev = code.find("let prevCard = '';")
    assert i_head > 0 and i_prev > i_head, "「数据导入」页的形态变了（找不到 ① 头卡 / ③ 预览段）"
    assert "${ctxBar}" in code[i_head:i_prev], \
        "「范围」栏（项目 / 归属年月 / 截止核算月）**没画在 ① 选域与文件那一屏** —— 用户又要走到最后才知道要选项目"
    assert "${ctxBar}" not in code[i_prev:], \
        "「范围」栏**又画回 ③ 了** —— 同屏两处一样的控件 = 用户不知道该改哪个（守则 §4 相似元素不制造歧义）"
    assert "${scopeEcho}" in code[i_prev:], \
        "③ 没有只读回显 —— 范围在 ①、落库按钮在 ③，中间隔着两屏 ⇒ 点下去时看不到自己要写哪儿（守则 §4）"
    # 默认不预选：⛔ 不许再拿"候选里的第一个"当默认值
    assert "IMP.org[0]" not in code, \
        "壳里又在拿候选列表的第一个当默认项目了 —— 「系统替你挑了一个项目」正是要堵的那类默认值（守则 §4）"
    assert "IMP.wrap = ''" in code.replace("  ", " "), \
        "`IMP.wrap` 的初值不是空 —— 不预选这条就落不到实处"
    # 没选 ⇒ ④ 置灰（不能点的要置灰并说明原因 · 守则 §5.5）
    # ⚠️ 2026-09-26（`TAIL-108`）：置灰条件从 `needPj` 变成 `needPj || IMP.busy`
    #    （落库期间也要禁用 —— 连点两次会撞批号，见本件末尾那条）——**判词不变**：「没选项目不许点」。
    assert 'data-act="impCommit"${(needPj || IMP.busy) ? ' in code, \
        "「④ 确认落库」没按 `needPj` 置灰 —— 没选项目也能点下去（后端才报错，用户已经白跑一趟）"
    # ⭐⭐ 2026-09-29（**用户真机报障** · 本机预演第 3 步第一次走就撞上）：
    #    「**④ 确认落库是亮的**、点下去**没反应**；**刷新后才是灰的**、而且有提示了」。
    #    ⚠️ 这句话就把根因指出来了 —— **亮/灰两种状态都存在** ⇒ 不是设计如此，是**状态没算对**：
    #      原判据 `IMP.org.length && !IMP.wrap` 把「这个域要不要选项目」**绑在了候选列表上**
    #      ⇒ **候选为空**（库里还没有项目档案 ⇒ `options` 回 `projects: []`；或档案刚同步进来、
    #      本页上下文还是旧的）时 `needPj = false` ⇒ ④ **亮着** ＋ 兜底（**同一个错写法**）**放行**
    #      ⇒ 请求照发 ⇒ **静默失败** ✗（刷新后 `impSetDomain → impLoadCtx` 重取 ⇒ 候选有了 ⇒ 才灰 ✓）。
    #    ⚠️ 而且**不是边缘场景**：**空库 + 首次导初始化数据**正是 `M8` ① 的既定路径
    #      （全新落地到办公室电脑时，项目档案**本来就是空的**，先同步 i8「常用项目列表」才有）。
    #    ⇒ 拦不拦**只看域声明** `IMP.hasPj`（⛔ 不再看候选空不空）；**候选为空只换提示**（给真出路）
    #      ⛔ 不换「拦不拦」。判据 = 本件这四条 ＋ 真机侧 `tools/probe/_shell_legacy.py` 的 ①″/③″。
    #    ⚠️ **能证伪**：把任一处改回 `IMP.org.length`（`needPj` / 兜底 / 范围栏 / ④ 提示）⇒ 本件必红。
    assert "const needPj = IMP.hasPj && !IMP.wrap;" in code, \
        "`needPj` 又绑回候选列表了 —— 候选为空时它变 `false`（④ 亮着、挡不住落库）"
    assert "if (IMP.hasPj && !IMP.wrap) {" in code, \
        "`ACT.impCommit` 的兜底又绑回候选列表了 —— 候选为空时它**整条放行**（正是本次报障的形态）"
    assert "IMP.org.length && !IMP.wrap" not in code, \
        "又拿候选列表当「要不要选项目」的判据了 —— 候选为空 ⇒ 闸门整条失灵（2026-09-29 报障）"
    assert "hasOwnProperty.call(ctx, 'projects')" in code and "IMP.hasPj" in code, \
        "`hasPj` 没从域给的 `projects` 键算出来 —— 那「这个域要不要项目」又从哪知道？"
    # 候选为空 ⇒ 这一格**照样画**（⛔ 不静默少一格）＋ **置灰**（⛔ 不做可点的空面板）＋ **给真出路**
    assert "(IMP.hasPj || IMP.hasYm || IMP.hasCut || IMP.hasMechCut)" in code, \
        "范围栏的渲染条件没跟上 —— 候选为空时用户看不到「有项目这一环」"
    assert 'class="btn" disabled style="min-width:186px" title="库里还没有项目档案' in code, \
        "空候选时那个按钮不是**置灰**的 —— 点开一个空面板 = 假控件（守则 §5.5）"
    assert "「i8 接入层」" in code, \
        "候选为空时没给**真出路**（去「i8 接入层」同步 i8「常用项目列表」）—— 只说「没项目」等于把人堵死"
    assert "库里还没有项目档案" in code, \
        "候选为空时 ④ 那侧没解释「库里还没有项目档案」—— 用户只会看到按钮灰着、不知道去哪"
    assert "const ok = !!(d && d.ok !== false);" in code, \
        "`impLoadCtx` 又把 `ok:false` 静默当成「这个域没有上下文」了 —— 那 `hasPj` 取不到、闸门整条失灵"


def test_本页的项目浮层走通用机制():
    """⭐ 2026-09-26（用户报障「**通用导入的项目选择控件，行数显示不全**」⇒ `TAIL-109` 修、`TAIL-110` 收口）。

    ⚠️ **机制本身（`placePops` 的完整性／"不许再有裸浮层"）由 `test_shell_render.py` 守**
      —— 它是**全站渲染机制**，不是本页的事（⛔ 同一 claim 别写成两份：一处改坏另一处仍会绿）。
      本件只钉**本页**那一半：导入页的「项目」浮层**确实是那套机制的实例**。
    """
    src = re.sub(r"/\*.*?\*/", "", SHELL, flags=re.S)
    assert 'class="fi pjwrap"' in src, \
        "导入页「项目」的**锚**没了 —— 浮层就不会被 `placePops` 提升为 `fixed`，后半截会被卡片裁掉"
    # ⚠️ 2026-09-30（`TAIL-64` `P4-d-b`）：触发按钮**改走统一出口 `PJB`** ⇒ 源码里那个字面
    #    `data-act="impPjToggle"` 变成了**实参** `act:'impPjToggle'`。**判词不变**（"本页那个触发按钮还在"），
    #    落点换成**委托形式**（同 `P4-b` 给 `test_wired_m03_list` 的改法：⛔ 不退回钉字面 ——
    #    那等于宣布以后不许抽通用件）。⭐ 通用件**真的拼出按钮**由 `test_ux_pages.py` 那两条 ＋ 变异守。
    assert "PJB({act:'impPjToggle'" in src, "「项目」浮层的触发按钮不见了"


def test_项目候选与选完之后的名字只走一个出口():
    """⭐⭐ 2026-09-26（用户报障 · 原话：「**候选和选择后显示的不一样**」）。

    ⚠️ 病根：**同一个键在三处各自算名字** —— ① 下拉按钮 `IMP.pjDisp[键] || 键`（域给的 display，
       域没给就退化成**仓库名**）· ③ 只读回显同款 · 候选面板却走 `impPjMeta`（**档案展示名**）
       ⇒ 用户截图里：按钮写「内蒙石灰窑项目」（仓库名），候选里却是「内蒙宜化项目」（展示名）。
    ⇒ 判词：① 按钮 与 ③ 回显**一律**走 `impPjLabel`（＝ `impPjMeta(v).nm`，与候选面板**同一个函数**）；
      ⛔ 壳里**不许**再出现 `IMP.pjDisp[键]` 那种直接取值的写法（那正是"两个主人"的开端）。

    ⚠️ 能证伪：把按钮改回 `IMP.pjDisp[IMP.wrap] || IMP.wrap` ⇒ 本件必红。
    """
    code = _imp_code()
    assert "const impPjLabel" in code, "没有「候选键 → 显示名」的唯一出口（`impPjLabel`）"
    n = code.count("impPjLabel(IMP.wrap)")
    assert n >= 2, (
        f"`impPjLabel(IMP.wrap)` 应同时出现在**① 下拉按钮**与**③ 只读回显**（现在 {n} 处）"
        "—— 少一处就会出现「两处名字不一样」（用户 2026-09-26 报的障）")
    assert "IMP.pjDisp[IMP.wrap]" not in code, (
        "又有人直接拿 `IMP.pjDisp[键]` 当显示名了 —— 它与候选面板的档案展示名**不是一个来源**，"
        "必然再次出现「候选和选完不一样」")


def test_落库结果卡给的是人话_原始键名进技术明细():
    """⭐⭐ 2026-09-26（用户报障 · 原话：「**落库结果可读性比较差**」· 四个域一起改）。

    ⚠️ 病根（截图看得很清楚）：结果卡把**回执的原始键名**（`updated` / `undo_rows` / `message`…）
       当 KPI 标签铺成一排，`message` 那一长句被挤成一根细柱，`project key` 还是**仓库名**。
    ⇒ 判词（五半）：
      ① 人话指标**只画域自报的 `kpis`**（⛔ 不再 `Object.keys(r).filter(scalar)` 那套裸键循环）；
      ② 一句话结果（`message`）**整行**显示；
      ③ **写入项目**从壳自己的状态取（`impPjLabel`）—— ⛔ 不用回执里那个 `project key`（仓库名）；
      ④ 原始回执**一个字不丢**：折进「技术明细」（排查时要看它）；
      ⑤ `**加粗**` 要渲染成 `<b>`（否则满屏星号 —— 截图里那句就写着 `**按合同价匹配上并更新 5 条**`）。
    ⚠️ 能证伪：把裸键循环写回去 / 去掉技术明细 / 把 `message` 塞回 KPI 格 / 去掉 `lgMd` ⇒ 本件必红。
    """
    code = _imp_code()
    assert "Object.keys(r).filter(scalar).map" not in code, (
        "结果卡又把**原始键名**当 KPI 标签铺一排了 —— 用户 2026-09-26 报的「可读性差」就是它")
    assert "Object.entries(r.kpis || {})" in code, "结果卡没画域自报的人话指标（`kpis`）"
    assert "lgMd(r.message)" in code, "一句话结果没整行显示（或没渲染 `**加粗**`）"
    assert "技术明细" in code and "<details" in code, \
        "原始回执没有折进「技术明细」（排查时看不到原始键名与值）"
    assert "写入项目" in code and "impPjLabel(IMP.wrap)" in code, \
        "结果卡没写清「写入哪个项目」（⛔ 也别拿回执里那个仓库名当项目名）"
    src = re.sub(r"/\*.*?\*/", "", SHELL, flags=re.S)
    assert "const lgMd" in src and r"replace(/\*\*(.+?)\*\*/g" in src, \
        "没有 `**加粗**` 的渲染出口（`lgMd`）—— 后端说明文字里的 `**…**` 会原样显示成星号"
    assert "lgMd(b.title" in src and "lgMd(b.note" in src, \
        "域区块的标题 / 说明没走 `lgMd`（那里同样写着一堆 `**…**`）"


def test_不会落库的行要在行上直接标():
    """⭐⭐ 2026-09-26（用户报障 · 原话：「**这些不会落库的行，要在行上直接标**，比如给一个浅色底，
    或者其他明确提示，**这才叫好的前端设计，而不是还要抬头去看文字说明**」；⛔ 通用导入页都要这么做）。

    ⚠️ 病根（截图看得很清楚）：③ 预览表里"哪几行写不进去"此前**只在卡片底下写了一句**
       （「⚠️ 有 7 行不会写入…」）—— 读者得自己把那个"7 行"对上表里**具体哪几行**
       （用户截图里是他拿红框手动框出来的那 4 行）。⇒ 这是"信息在的地方 ≠ 用它的地方"。
    ⇒ 判词（五半，缺一半都不算做到）：
      ① 域**自报逐行名单**：预览回执 `skipped` = `[{row: Excel 行号, why: 人话原因}]`
         （⛔ 不许只给 `total - writable` 这个**差值** —— 差值标不出"哪几行"）；
      ② 壳按 `row` **标在那一行上**（`.skiprow`：浅底 ＋ 左侧警示竖条）；
      ③ **行内**还得有看得见的**文字**标记（行号旁「不写入」）＋ 整行 `title` 挂原因（悬停即见）
         —— ⛔ 只给浅底不行：色弱 / 不看色的人认不出（守则 §4.5 别让人猜状态）；
      ④ 表上方有**图例**（浅底是什么意思），且底部那句改成指向「**已在上表逐行标出**」；
      ⑤ 视觉语言**别另造一套**：与「i8 已撤单行」`.ntvoid` 同源（inset 竖条 ＋ 浅底，颜色走 token）。
    ⚠️ 能证伪：摘掉 `.skiprow` / 去掉行内「不写入」/ 去掉图例 / 把底部那句改回"原因见下面" ⇒ 本件必红。
    ⚠️ "域真给了名单"那半边由 4 个域的 API 测试守（`test_imp_m04/m05/m06/m11_api`）——
       本件只管**壳按名单标**（⛔ 同一 claim 别写成两份）。
    """
    code = _imp_code()                      # ⚠️ 剥掉注释：注释里**引述**了旧写法（引述 ≠ 实现）
    assert "(p.skipped || [])" in code, (
        "③ 预览没读域的**逐行**名单（`skipped`）—— 它手里只有一个总数，标不到行上")
    assert 'class="skiprow' in code and 'title="${tip}"' in code, (
        "被跳过的行没有**行级标记**（`.skiprow` ＋ 把原因挂整行 `title`）—— "
        "用户报障原话：「要在**行上**直接标……而不是还要抬头去看文字说明」")
    assert 'tag t-wn">不写入</span>' in code, (
        "「要你处理」的行缺**行内文字标记**（行号旁的「不写入」标签）—— 只给浅底，色弱的人认不出")
    # ⭐⭐ 2026-09-27（用户报障 · 原话「**请将所有不写入输出的行也进行标注**」· 他截图里红框的是
    #    「小计」「合计」行）：**「本来就跳过」的那类也要标**，而且**不能跟"要处理"长得一样** ——
    #    ⛔ 混成一种颜色/一个词，用户会以为"合计行也要我去改"（守则 §2.8）。
    assert 'tag t-mut">不导入</span>' in code, (
        "「本来就跳过」的行（合计/小计 · 说明 · 空行）缺**自己的行内标记** —— 用户 2026-09-27 "
        "报障的正是「这些行一个标记都没有」")
    assert "skiprow${plain ? ' plain' : ''}" in code and "kind || 'bad'" in code, (
        "两类标记没有分开渲染（`kind=skip` → 灰底 `.plain`；且**缺 `kind` 按 `bad` 走**，"
        "保守：宁可多提醒一句「要处理」，也别把该处理的悄悄归成「不用管」）")
    assert "plegend" in code and "不用你改" in code and "处理说明" in code, \
        "表上方没有**两类图例**（看表的人分不清「要处理」与「本来就跳过」）"
    assert "原因已标在对应行" in code and "lgMd(hit.why)" in code, (
        "底部那句还是只让人去读别处的文字 —— 必须指向「行上**已经标好了**」")
    assert ".dt tbody tr.skiprow{box-shadow:inset 3px 0 0 var(--wn);background:var(--wn-l)}" in SHELL, (
        "`tr.skiprow` 的样式没定义 —— 要**浅底 ＋ 左侧警示竖条**（视觉语言同「i8 已撤单行」`.ntvoid`，"
        "颜色走 token、⛔ 不写死色值）")


def test_截止核算月要写清格式要求():
    """⭐ 2026-09-26（用户报障 · 原话：「**截止核算月的格式要求一下吧**」）。

    ⚠️ 「要求」光写在文档里不算 —— 要**贴在控件旁边**（守则 §5.5：不能做的 / 要怎么填的，当面说清），
      而且**后端也得执行**（`repository.import_snapshot` 归一 ＋ 认不出当场拒；判据在 `test_imp_m06_api`）。
    """
    code = _imp_code()
    assert 'id="impCut"' in code, "「截止核算月」输入框不见了（真机判词钉着它）"
    assert "YYYY-MM" in code, "「截止核算月」旁边没写**格式要求**"
    assert 'placeholder="2025-11"' in code and 'placeholder="2026-09"' in code, \
        "占位里没给一个**示例格式**（占位本身就是最好的示范：用户照着填就不会错）"


def test_落库期间不许重复提交_按钮要禁用():
    """⭐ 2026-09-26（`TAIL-108`）：连点两次「④ 确认落库」会发两次请求 —— 而默认批号到**秒**
    ⇒ 第二次撞批号唯一约束，用户看到 `IntegrityError …重复键违反唯一约束`（**天书**）。

    判词（两半，缺一半都不算）：
      ① **提交期间 `④` 置灰 ＋ 换文案**（守则 §5.5：不能点的要置灰并说明）；
      ② **动作里挡重入**（`IMP.busy` 早退）—— 光置灰挡不住程序化调用 / 回车（同 `impCommit` 的既有兜底）。
    ⚠️ 后端另有一道（`imp_spec._batch_no`：撞了就换号）—— 界面挡不住脚本 / 接口，两道都要。
    """
    code = _imp_code()
    # ⚠️ `const IMP = {…}` 在 `impSetDomain` **之前** ⇒ 不在 `_imp_region()` 的切片里，要查全壳
    assert "busy: false" in re.sub(r"/\*.*?\*/", "", SHELL, flags=re.S), \
        "`IMP` 状态里没有 `busy` —— 落库期间的状态无处可记"
    assert "if (IMP.busy) return;" in code, "`ACT.impCommit` 没挡重入（连点两次会发两次请求）"
    assert "needPj || IMP.busy" in code, "「④ 确认落库」没在落库期间置灰"
    assert "IMP.busy = false" in code, "`busy` 没有复位 —— 一次失败之后 ④ 会**永远点不动**"


def test_本页的项目面板走注册表收起():
    """⭐ 2026-09-26 用户报障「展开待选列表后**无法正常关闭**」⇒ 面板收起必须按**注册表**做。

    报障时的形态：`actions.js` 的「点面板外部自动收起」是**逐个列名字**的（`pjOpen` / `ledPjOpen` / …）——
      ⛔ 它**不会**自动认识新面板 ⇒ 通用导入面换用共用面板时漏登记，面板就只能在"再点一次按钮"
      或"选中一项"时才收（与另外 12 个面板行为不一致 ——《前端设计守则》§4「相似元素不制造歧义」，
      存档 = `docs/guides/frontend-design.md`）。

    ⭐ **`#1`（2026-09-26）后的判词**：那两处（click 收面板 ＋ Esc 收面板）**一律遍历 `PJ_OPEN`**，
      ⛔ 名单式登记**不许再出现**（它就是这个 bug 的根）；本页那块面板也在注册表里（key = `impPj`）。

    ⚠️ **能证伪**：把那段改回"逐个列名字"（或让 `PJ_OPEN` 不被遍历）⇒ 本件必红。
    """
    i = SHELL.find("点面板外部自动收起")
    assert i > 0, "壳里找不到「点面板外部自动收起」那段（形态变了就同批改本件）"
    block = SHELL[i:SHELL.index("});", i)]
    assert "Object.keys(PJ_OPEN)" in block, (
        "「点面板外部收起」不是按注册表遍历的 —— 退回**手写名单**式就是 2026-09-26 用户报障的根"
        "（漏登记一个新面板 ⇒ 点别处收不起来，且没有任何闸门看得见）")
    assert "IMP.pjOpen" not in block, "还留着旧的逐个登记写法（`#1` 已把它收进 `PJ_OPEN`）"
    assert "pjClose('impPj')" in SHELL, \
        "本页「项目」面板的收起没走注册表 `PJ_OPEN`（key 由 `pickAct` 派生：`impPjPick` ⇒ `impPj`）"


def test_预览的行要能对得上号_不许静默截断也不许藏行号():
    """⭐⭐ 2026-09-26（用户报障 · 原话）：「我导入晋江的过程资料时，**第 4 步，显示的行不完整**」。

    ⭐ **报障的实质 = 两处显示毛病叠在一起**（实测那份真文件：数据在 Excel 的 r4~r32，
       而 ④ 落库报的错是「**第 19 行**的核算月认不出」）：
       ① 行号列被 `filter(k => k !== '_row')` **抠掉了** ⇒ 页面上**根本没有行号**可比
          ⇒ 用户看到「第 19 行」却不知道该看哪一行；
       ② 只画 `slice(0, 12)` **却一个字都不说** ⇒ 看着像"系统只读到 12 行"
          （后端其实给 20 条 —— 两条命令还不一致）。
       ⇒ 判词：**行号要画出来**（表头写「行」）、**不许静默截断**（要么全画、要么写明"共几行/显示几行"）、
          并且要写清「行」= **Excel 行号**（与报错同一个数）。

    ⚠️ **能证伪**：把 `_row` 再抠掉 / 再把 `slice(0, 12)` 写回来 / 去掉那句"共几行"⇒ 本件必红。
    """
    code = _imp_code()                      # ⚠️ 剥块注释：本页注释里**引述**了那两个坏形态（引述 ≠ 实现）
    assert "_row" in code and "k === '_row' ? '行'" in code, (
        "③ 预览的行表**没有把行号画出来** —— 落库报错写「第 N 行」，页面上却没有行号可比，"
        "用户只能干瞪眼（2026-09-26 报障的一半）")
    assert "slice(0, 12)" not in code, (
        "③ 预览又在**静默截断**（只画前 12 行）—— 那正是报障的另一半：看着像系统只读到 12 行")
    assert "pnote" in code and "本步读到" in code, (
        "③ 预览没有写清「共几行 / 显示几行」—— 截断（现在由后端 `PREVIEW_ROWS` 管）必须**明说**，"
        "⛔ 不许让用户自己猜")
    assert "Excel 里的行号" in code, (
        "没写清「行」这一列是什么 —— 用户得知道它**就是** Excel 行号、与报错同一个数")


def test_截止核算月要说清它是什么_不是只给一个名字():
    """双截止月只过滤本次导入，不再定义后续手录分界。"""
    code = _imp_code()
    for must in ('id="impCut"', 'id="impMechCut"', '材料截止月', '机械截止月', '及以前', '留空取本批最大核算月'):
        assert must in code, f"导入范围缺少 {must}"
    assert '历史段 / 正式段的分界月' not in code
    assert '之后走 i8' not in code
