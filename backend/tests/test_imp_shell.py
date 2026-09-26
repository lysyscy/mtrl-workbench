"""壳侧「**数据导入**」页（`TAIL-75` `B5`）—— 入口 / 四步向导 / ⭐ **无死控件**（离线可验的那半）。

⭐ 为什么要有本件：真机自检（`tools/probe/_shell_legacy.py` 的 ② 「无死控件」）要**起服务 ＋ 浏览器**才跑得起来
   ⇒ 把它的判据做成**离线等价物**：页面上每个 `data-act` 都能解析到 `ACT`、**表单元素**的动作都在 `CHG` 里。
   ⚠️ **只查本页**（`V.imp` 那一段）：整壳扫会撞上别的页的边界情况（例如 `go`/`exp` 走的是委托），
     那些不是本件要管的事 —— 本件只管"新加的这页别漏登记"。
"""

from __future__ import annotations

import re

from tests.acc_plugin import acc
from tests.shell_load_helpers import loaders, page_load
from tests.shell_src import SHELL

#: 本页自己的动作（`ACT.<名>` 必须都在）
#: ⚠️ 2026-09-26（`TAIL-103`）：`impPj`（原来挂在自造的 `<select>` 上）**换成共用面板的两个动作** ——
#:    `impPjToggle`（展开/收起）+ `impPjPick`（面板内单选）。理由见 `V.imp` 里 `ctxBar` 那段注释。
PAGE_ACTS = ("impDomain", "impPick", "impParse", "impMap", "impPjToggle", "impPjPick", "impPreview",
             "impCommit", "impRollback", "impReset")
#: ⛔ `#2`（2026-09-26）起**没有 `CHG` 名单了** ⇒ 这里不再需要"哪些动作挂在表单元素上"的清单：
#:    `change` 委托**看见 `data-act` 就跑**（`change` 只可能来自表单元素），漏登记这回事不存在。


def _imp_region() -> str:
    """`impSetDomain` 到 `ACT.impRollback` 那一段（本页的全部代码 —— 含**切域**那段）。

    ⚠️ 起点 2026-09-26 从 `V.imp = ()` 前移到 `impSetDomain`：**域上下文就在这里读**，
       而"壳里不许认域号"这条判据必须把它框进来（起点留在 `V.imp` 会漏掉真出过问题的那一段）。
    """
    i = SHELL.find("async function impSetDomain")
    j = SHELL.find("ACT.impRollback")
    assert i > 0 and j > i, "壳里找不到「数据导入」页（形态变了就同批改本件）"
    return SHELL[i:j]


@acc()
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


@acc("ACC-IMP-MAP-001", "001-10")
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
    for step in ("① 选域与文件", "② 列映射", "③ 预览校验", "④ 确认落库"):
        assert step in SHELL, f"四步向导缺一步：{step}"
    # ④ 无死控件（离线等价物）：每个 `data-act` 都能解析到 `ACT`
    acts = set(re.findall(r"\nACT\.(\w+)\s*=", SHELL))
    missing = [a for a in PAGE_ACTS if a not in acts]
    assert not missing, f"这些动作没在 `ACT` 上定义 ⇒ 点了没反应（死控件）：{missing}"
    # ⑤ ⭐ `#2`（2026-09-26）起**不再需要登记**：`change` 委托「看见 `data-act` 就跑」
    #    （`change` 只可能来自表单元素）⇒ 判词换成**结构性两条**：名单不许回来 ＋ 委托不看名单。
    # ⚠️ 只查**真声明**（`const CHG=[`）：`index.html` 的目录注释里引述过「`const CHG=`（漏登记 ⇒ 静默失效）」
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


def _act_body(name: str) -> str:
    """取 `ACT.<name>` 的函数体（到行首 `};` 为止 —— 本页的动作体里没有跨行 `}`）。"""
    i = SHELL.find(f"ACT.{name} =")
    assert i > 0, f"壳里找不到 `ACT.{name}`"
    return SHELL[i:SHELL.index("\n};", i)]


@acc("ACC-IMP-MAP-001", "001-10")
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
        body = re.sub(r"/\*.*?\*/", "", _act_body(act), flags=re.S)
        # ⭐ `#3`（2026-09-26）**换落点**：判词不变（"导入/回滚改了别的域的数 ⇒ 不许留旧数"），
        #    但**不再要求业务动作自己写 `LOADED.clear()`** —— 那正是"靠自觉"（本仓 `TAIL-78` 就漏标过一路）。
        #    现在标脏的唯一主人 = **写出口**：`API.impCommit` / `API.impRollback` 都是写出口
        #    ⇒ `api.js` 里统一 `markCrossPageStale()`（判据 `test_wired_boot.py` 钉着"只许一处"）。
        assert ("API." + act) in body, \
            f"`{act}` 没走写出口 —— 那样就没有任何东西会全标脏（切回别页看旧数）"
        assert "LOADED.clear()" not in body, \
            f"`{act}` 又自己手写清空了 —— 标脏的唯一主人是写出口，业务动作里再写一遍就是两处口径"


@acc("ACC-IMP-MAP-001", "001-10")
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
    assert "IMP.hasCut" in code and "IMP.hasYm" in code, \
        "控件不是按域声明的键渲染的 —— 那么「截止核算月」又会跑给集采/付款计划（填了不生效）"


@acc()
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
    #    （落库期间也要禁用 —— 连点两次会撞批号，见本件末尾那条）——**判词不变**："没选项目不许点"。
    assert 'data-act="impCommit"${(needPj || IMP.busy) ? ' in code, \
        "「④ 确认落库」没按 `needPj` 置灰 —— 没选项目也能点下去（后端才报错，用户已经白跑一趟）"
    assert "IMP.org.length && !IMP.wrap" in code, \
        "`ACT.impCommit` 没有本地兜底拦住「没选项目就落库」（按钮置灰挡不住程序化调用/回车）"


@acc()
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


@acc()
def test_本页的项目面板走注册表收起():
    """⭐ 2026-09-26 用户报障「展开待选列表后**无法正常关闭**」⇒ 面板收起必须按**注册表**做。

    报障时的形态：`actions.js` 的「点面板外部自动收起」是**逐个列名字**的（`pjOpen` / `ledPjOpen` / …）——
      ⛔ 它**不会**自动认识新面板 ⇒ 通用导入面换用共用面板时漏登记，面板就只能在"再点一次按钮"
      或"选中一项"时才收（与另外 12 个面板行为不一致 ——《前端设计守则》§4「相似元素不制造歧义」，
      存档 = `ops/前端设计守则-以使用用户为中心.md`）。

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


@acc()
def test_列映射的去向只许三个词_不许再说认行_且字段清单要列全():
    """⭐⭐ 2026-09-26（用户三点要求）：去向**只许三个词** · ⛔ 不许再说「只用来认行」 ·
    字段清单必须**列全域契约的全部字段**（用户报「缺贸易公司发票金额」的真因就在这）。

    用户原话：「**写台账和进子表为一个意思，合并为写台账**」·「贸易公司名 / 合同日期
    **不写库、也不用来认行**」·「**导入后会怎样**这一行**可读性太差**」。

    ⚠️ **能证伪**：把去向换成别的词 / 把"认行"写回去 / 字段清单漏列 ⇒ 本件必红。
    """
    from app.mod11_jc import excel_parse as P
    from app.mod11_jc import imp_spec

    kinds = {x[2] if len(x) > 2 else "" for x in imp_spec.SPEC.impacts}
    bad = sorted(kinds - {"写台账", "当钥匙", "不参与"})
    assert not bad, f"去向**只许三个词**（写台账 / 当钥匙 / 不参与），出现了：{bad}"
    assert imp_spec.SPEC.impact_kind_of("贸易公司发票金额") == "写台账", (
        "「贸易公司发票金额」的去向必须「写台账」—— 它往发票子表加一张票（用户本次报的就是它）")
    for fld in ("贸易公司", "合同日期", "供应商"):
        assert imp_spec.SPEC.impact_kind_of(fld) == "不参与", (
            f"「{fld}」导入**不用它** ⇒ 去向必须「不参与」（用户 2026-09-26 当场纠正）")
    assert "认行" not in (SHELL + str(imp_spec.SPEC.impacts)), (
        "还留着「只用来认行」—— 导入**不对号用它**（对号只用合同价 / 贸易公司合同价），这话是错的、会误导")
    assert {f.label for f in imp_spec.SPEC.fields} == set(P.FIELD_LABELS.values()), (
        "域字段契约与 `FIELD_LABELS` 不一致 ⇒「本系统要哪些列」那块会漏列（用户报的「缺列」就从这来）")
    for must in ("本系统要哪些列", "写台账", "当钥匙", "不参与", "field_list_hint"):
        assert must in SHELL, f"壳里缺 `{must}` —— 列映射的「去向 / 本系统要哪些列」没渲染出来"
    # ⭐⭐ 用户 2026-09-26：「**不参与的就不要给下拉选项了**」—— 那一格默认只给标签
    assert "k === '不参与'" in SHELL, (
        "「不参与」那一列没有特殊处理 ⇒ 它还会给一个「能点但点了没用」的下拉"
        "（用户明确要求去掉；守则 §5.5「不能点的要置灰或隐藏」）")
    # ⭐ 同轮补的退路（用户选 **B** 案）：标签旁挂一个「改」，**点开才展开**下拉
    #    ⇒ 既"平时不误导"，又"认错了还能纠"（本仓最忌"认错了却没法纠"）
    assert "<details" in SHELL and ">改</span></summary>" in SHELL.replace(" ", ""), (
        "「不参与」的列没有给「改」的退路 —— 认错成合同日期/供应商/贸易公司后就再也改不回去了")
    assert 'data-act="impMap"' in SHELL, "映射下拉不见了（`details` 里的那个也必须在）"


@acc()
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


@acc()
def test_截止核算月要说清它是什么_不是只给一个名字():
    """⭐ 2026-09-26（用户报障）：「**截止核算月填写的意义写的不明确**」。

    原来只有一个 `截止核算月（历史段分界）` ＋ placeholder「留空 ⇒ 取本批最大月」——
    ⛔ 「历史段分界」是**内部黑话**：用户看不出"填了会怎样、不填会怎样"。

    判词：那一格必须用**大白话**说清三件事 —— ①**及以前**按这份表（不再问 i8）②**之后**走 i8 抓取
    ③留空 = 取本批最大月。⚠️ 控件 id 仍是 `#impCut`（真机判词钉着它，⛔ 别改 id）。

    ⚠️ **能证伪**：把那句说明删掉、或退回只有"历史段分界"四个字 ⇒ 本件必红。
    """
    code = _imp_code()
    assert 'id="impCut"' in code, "「截止核算月」输入框不见了（真机判词钉着 `#impCut`）"
    for must in ("历史段 / 正式段的分界月", "及以前", "之后", "留空 = 取本批里最大的核算月"):
        assert must in code, f"「截止核算月」的说明里缺「{must}」—— 用户看不出这一格填了会怎样"
    assert "历史段分界）" not in code, (
        "还留着「（历史段分界）」那种黑话当**唯一**说明 —— 用户 2026-09-26 报的就是「看不懂这一格」")
