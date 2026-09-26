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
