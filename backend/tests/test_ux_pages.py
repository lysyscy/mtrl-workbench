"""壳侧**页级**判据（`P0-b` · 2026-09-28）—— 给「**没有原型可比**」的两页补守卫。

⭐ 为什么单独立一件（审计 §三 债 5 · `docs/archive/designs/设计-前端系统性重构审计-20260928.md`）：
  `imp`（数据导入）与 `set`（系统设置）**不在原型里** ⇒ 既没有 `ui_parity` 的 `U1` 可比（⚠️ 2026-09-30 `TAIL-201`：`U1` 与登记簿**已退场** ⇒ 本句只作留痕）、
  也没有 `U5`「逐字一致」那层兜 ⇒ 它们的安全性**全靠测试与真机**。
  ⚠️ 本仓的教训（`TAIL-123`）：**「判据存在」与「判据被看见」是两件事** —— 一直跑着、
  但没挂进契约面的判据，在四态报表里**等于不存在**（哪天被删也没人知道）。

本件只收 **`set` 页**此前**没有任何判据**盯着的那几条页级口径。
  `imp` 页的页级判据**早已存在**（`tests/test_imp_shell.py`），本轮做的是**登记**（把它们的
  `@acc()` 换成 `@acc("ACC-UI-SHELL-001", …)`）—— ⛔ 不重写、不复制到本件。
"""

from __future__ import annotations

import re

from tests.shell_src import (  # noqa: F401  ← `P4`① 读取点收敛
    SHELL, act_entry, const_items, fbar_kernel, page_slice, pjb_kernel, read_shell, tbl_kernel, with_fbar,
)

#: ⭐ `P1-a`（2026-09-28 · 用户选 `A`）：**展开区的外框/间距只走变体类**，这四条内联整串不许回来。
EXPAND_INLINE_GONE: tuple[str, ...] = (
    'class="fbar" style="border:1px solid var(--bd);border-radius:var(--r)"',
    'class="fbar" style="border:1px solid var(--bd2);border-radius:6px;'
    'margin-bottom:calc(10px * var(--fscale))"',
    'class="fbar" style="margin:0 0 calc(8px * var(--fscale));',
    'class="fbar" style="margin-bottom:calc(6px * var(--fscale));',
)
#: 四个变体类（声明**原样搬**自那 9 处内联 ⇒ 外观逐像素不变）
EXPAND_VARIANTS: tuple[str, ...] = (".fbar.pane{", ".fbar.strip{", ".fbar.strip.mb6{", ".fbar.plate{")


def test_展开区的外框与间距只走变体类_不许再写回内联():
    """⭐ `P1-a`（2026-09-28 · 用户选 `A`）：9 处展开区原先**各写一遍**内联 `style`（外框/间距），
    现收进 **4 个变体类**（声明**原样搬过来**，⛔ 一个值没改 ⇒ 外观逐像素不变）。

    ⚠️ **能证伪两半**：任一处改回内联写法 ⇒ 红；把变体类的定义删掉 ⇒ **也红**
       （删了它 = 那几处展开区的**外框整个消失** —— 只钉"不许有内联"是半个守卫）。
    """
    for bad in EXPAND_INLINE_GONE:
        assert bad not in SHELL, f"展开区又写回内联样式了：{bad!r}（应走 `.fbar` 的变体类）"
    for cls in EXPAND_VARIANTS:
        assert cls in SHELL, f"变体类没了：{cls!r}（那几处展开区会**没有外框**）"


def test_项目选择只走共用面板_不许自造项目下拉():
    """⭐ 守则 **§5.12**（2026-09-28 补 · `P1-c`）：**"选一个项目 / 选一个实体"只走一个出口**
    （共用面板 `projPanel`），⛔ 不许各页自造项目下拉 —— 自造 = 同一个选择长出四种形态（§4.4）。

    ⚠️ **例外只有一条**（弹窗内用原生 `<select>`：弹窗主体是滚动容器、浮层会被裁）——
       它**不在这里判**（那是"按位置放行"，写进来会变成假红）。

    ⚠️ **剥块注释再判**：注释里会**引述**旧写法作留痕（`legacy.js` 那句"它原来是挂在
       `<select data-act="impPj">` 上的"）⇒ 不剥就变成"要么删留痕、要么判据假红"（本仓踩过）。
    """
    code = re.sub(r"/\*.*?\*/", "", SHELL, flags=re.S)
    assert "projPanel(" in code, \
        "项目选择没有走共用面板 `projPanel`（§5.12 的唯一出口）"
    bad = re.findall(r'<select[^>]*data-act="(?:pj[A-Za-z]*|impPj)"', code)
    assert not bad, (
        f"又出现「自造的项目下拉」了：{bad[:3]} —— 守则 §5.12：项目/实体选择只走 `projPanel`"
        "（例外只有「弹窗内」一条：弹窗是滚动容器、浮层会被裁）")


def test_台账导出一次点到位的按钮名要能看出先选项目():
    """⭐ 2026-09-28（用户口径：把 `m06` 那套规矩**同样用到 `m05` 逐月欠款台账的导出**上）：
    ① 卡头按钮点**一次**就该把 ① 那个「项目（可多选）」面板**一起打开**（原先只开展开区，用户还得再找一次那个按钮）；
    ② ⛔ **别拿面板开合态当这个按钮的判据** —— `m05` 的面板挂在**展开区里**（不在按钮上）⇒ **点卡头按钮本身就等于
       "点到浮层外面"**，通用收起逻辑会先关掉面板，此时再按面板状态取反 ⇒ **永远只能开、收不掉**
       （真机 `㉚-④′` 实测抓到：「收起后按钮仍带 `on` —— 状态不真实」）。⚠️ 这与 `m06` **相反**：
       TAIL-265已将MOD06改为同窗选项目，无浮层镜像开关；本条仍只保护MOD05的展开区；
    ③ 按钮名要**一眼看出「要先选项目」**（原先是孤零零的「导出…」，用户报「**不知道去哪里找**」）。

    ⚠️ **能证伪**：删掉 `if(ledExpOn){ PJ_OPEN['ledExpPj']=true; }`（退回"只开展开区"）⇒ 本件必红。
    """
    seg = SHELL[SHELL.index("ledExpToggle:()=>"):]
    seg = seg[:seg.index("render();")]
    assert "if(ledExpOn){ PJ_OPEN['ledExpPj']=true; }" in seg, \
        "卡头按钮没把 ① 那个项目面板一起打开（用户还得再找一次那个按钮）"
    assert "pjIsOpen('ledExpPj')" not in seg, \
        "⛔ 别拿面板开合态当这个按钮的判据 —— 面板在展开区里，点卡头按钮本身就算点到浮层外面 ⇒ 只会「只能开、收不掉」"
    assert "批量导出（先选项目）…" in SHELL, \
        "台账导出的按钮名没写明「要先选项目」（用户报「点掉筛选后不知道去哪里找」）"


def test_m09月度批量录入_入口挂BIND且提交交给后端():
    """TAIL-265：项名取当前页；首月递增为列，提交唯一批量出口，失败不清空。"""
    assert "addBind('m09', function ()" in SHELL and 'data-act="awfBatch"' in SHELL
    body = SHELL[SHELL.index("awfBatch:()=>"):SHELL.index("awfBatchOk:")]
    ok = SHELL[SHELL.index("awfBatchOk:async"):SHELL.index("awfRowAdd:()=>")]
    assert "awfList()" in body, "项名不是当前页数据"
    assert "API.m09Batch(" in ok and re.search(r"r\.ok\s*===\s*false", ok)
    assert "API.m09Amount(" not in ok and "API.m09Name(" not in ok
    assert 'data-act="awfYmCell"' in body and "请选择有效的首个核算月" in ok
    assert "return fail(" in ok and ok.index("return fail(") < ok.index("API.m09Batch("), "无效首月未拦提交"
    assert "ACT.awfYmCell(start);" in ok, "提交前未同步月份标签"
    assert "#awfTbl thead th[data-ym]" in ok and "#awfTbl tbody tr" in ok
    assert "heads.map((head,i)=>" in ok and "values:Object.fromEntries(trs.map(" in ok
    assert 'data-act="awfRowAdd"' in body and 'data-act="awfRowDel"' in body
    add = SHELL[SHELL.index("awfRowAdd:()=>"):SHELL.index("awfRowDel:()=>")]
    assert "ymAdd(last.dataset.ym,1)" in add and "cloneNode(true)" in add
    assert "cell.querySelector('input').value=''" in add, "新增月复制了旧金额"
    assert "data-r=" not in body+ok, "保存仍依赖可能错位的旧行号"

def test_失败文案要给人话原因和下一步():
    """⭐ 2026-09-28（用户口径：「**提醒需要告诉具体原因和解决方法**」· 原话还有一句
    "仍失败请把这一步告诉管理员" —— **管理员就是他自己**，等于没说）：

    壳的"没完成"文案**必须给出可读的原因 ＋ 具体的下一步**；同时仍守既有铁律：
    **原始串（方法 / 全路径 / 状态码）绝不上屏**，只进 `err.tech` ＋ `console.warn`（排障留痕）。

    ⚠️ **能证伪**：把任一出口里的 `errWhyByStatus(` 删掉（退回那句空洞文案）⇒ 本件必红。
    """
    assert "errWhyByStatus" in SHELL, "没有「失败原因分类成人话」的出口"
    for frag in ("登录状态过期", "没有重启", "系统内部出错"):
        assert frag in SHELL, f"失败原因没有覆盖这一类（用户会又看到一句没说原因的话）：{frag}"
    # ⚠️ 只数**出口**（`errHuman` 自己的默认兜底里留着那句是对的 —— 那是"连原因都没有"时的最后一道）
    assert SHELL.count("errWhyByStatus(") >= 4, \
        "有出口没走这个分类（只有「请刷新…告诉管理员」，没有原因和具体下一步）—— 4 个出口都要走"


def _sp_close(head: str, sp: int) -> int:
    """`.sp` 那一段的**闭合下标**（按 `<span` / `</span>` **深度回零** —— 工具区里常嵌着别的 span）。

    ⚠️ 入参 `sp` = `class="sp` 的下标（**已经在外面那层 `<span` 里**）⇒ 起始深度必须是 **1**；
       从 0 起算会把"内层 span 的闭合"当成 `.sp` 收尾 ⇒ **放过真违规**（本件 2026-09-29 收紧时的实测教训）。
    """
    j, depth = sp, 1
    while j < len(head):
        if head.startswith("<span", j):
            depth, j = depth + 1, j + 5
        elif head.startswith("</span>", j):
            depth, j = depth - 1, j + 7
            if depth == 0:
                return j
        else:
            j += 1
    return len(head)


def test_卡头里的按钮都在右侧工具区():
    """⭐ 守则 **§5.13**（2026-09-28 补 · `P1-b`；**2026-09-29 收紧** · `A1`）：**卡头只有一种形态** ——
    `<h4>标题<span class="sp">工具</span></h4>`，卡头的**一切操作与状态都放右侧工具区**，
    ⛔ **不许裸挂在标题后面**（裸挂 = 同一件事长出第二种形态）。

    ⚠️⚠️ **两种不合形态都要抓**（2026-09-29 补的那一种就是**旧版的盲区**）：
      ① `<button>` 出现在 `.sp` **之前**（原来的检查）；
      ② `<button>` 在 `h4` 里、但落在 `.sp` **之外**（工具区已经闭合）—— 实测收紧前有 **2 处**
         长这样（`m05` 付款流水那枚「导出 Excel」· `m15` 账号列表那 3 枚），而旧判据只比
         "第一个 `<button>` 与 `.sp` 的先后" ⇒ **它们一直绿着**（判据比守则条文弱 = 假绿的一种）。
    ⚠️ **能证伪**：把任一卡头里的按钮挪到 `.sp` 外（或挪到标题后）⇒ 本件必红。
    ⚠️ 卡头的 `</h4>` 可能在**好几行之后**（模板字符串里换行）⇒ 取**最多 6 行窗口**，
       ⛔ 别只看一行（本件第一版就是这么漏掉了 `m05`「付款统计」那两枚按钮）。
    """
    lines = SHELL.splitlines()
    bare: list[str] = []
    outside: list[str] = []
    for i, ln in enumerate(lines):
        for m in re.finditer(r"<h4[> ]", ln):
            seg = ln[m.start():] + "\n" + "\n".join(lines[i + 1:i + 6])
            end = seg.find("</h4>")
            head = seg[:end] if end > 0 else seg
            b = head.find("<button")
            if b < 0:
                continue
            spm = re.search(r'class="sp[\s"]', head)   # 工具区可能还带别的类（如 `sp pjwrap`）⇒ ⛔ 别只认 `class="sp"`
            tag = " ".join(head.split())[:70]
            if not spm or spm.start() > b:
                bare.append(tag)
            elif b > _sp_close(head, spm.start()):
                outside.append(tag)
    assert not bare, (
        f"这些卡头的按钮**裸挂在标题后**（应放进右侧工具区 `.sp`，守则 §5.13）：{bare[:3]}")
    assert not outside, (
        f"这些卡头的按钮**在 `.sp` 之外**（`h4` 里、但工具区已闭合 ⇒ 同一件事的第二种形态，守则 §5.13）：{outside[:3]}")


#: `V.set`（系统设置页）那一段的**边界**：下一个**小节横幅注释**（`legacy.js` 里紧随其后那一段）。
#: ⚠️ 起止都用**真锚点**，别用 `\n};` 猜结尾：本页函数体里有多处缩进的 `};`（`scard` / `cardBtn` 闭包），
#:    按列 0 猜会**截错**。⚠️ 也别把锚点写成**已撤项**的名字（`doc_audit` 的 `T8`"已撤项复活"会当场判红 ——
#:    本件第一版就踩了）。形态变了就同批改本件。
# ⭐ 2026-10-03（`TAIL-219` 批 2b）：起止串 `_SET_START`/`_SET_END` **已删** —— 改走 `page_slice("set")`。⛔ 别写回来。


def _set_region() -> str:
    # ⭐ 2026-10-03（`TAIL-219` 批 2b）：改走壳的语义口径（该页 ⇒ `page_slice("set")`）
    return page_slice("set")


def _strip_block_comments(text: str) -> str:
    """剥块注释 —— ⚠️ 注释里会**引述**被禁的旧写法（"原来是 `ACT.setSave`…"）作留痕，
    不剥就会把**说明**当成**实现**判红（本仓踩过"拿注释当实现"）。"""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_系统设置页只保留主题和尺寸操作():
    """TAIL-263：默认设置页移除连接参数说明和变更留痕，实际配置入口仍由下一条守护。"""
    body = _strip_block_comments(_set_region()).split("\n};", 1)[0]
    for removed in ("setSave", "i8 地址与打印版式", "变更留痕", "SET.logs", "SET.tips", "thhex", "thscene"):
        assert removed not in body, f"系统设置页又出现已撤内容：{removed}"
    assert 'aria-label="${esc(p.name)}"' in body, "主题选择缺少无障碍名称"
    assert 'aria-pressed="${on}"' in body, "设置选择缺少当前档位状态"


def test_系统设置页两张卡包含真实选择与预览():
    body = _set_region()
    for card in ("<h4>外观主题", "<h4>界面大小"):
        assert card in body, f"系统设置页少了一张卡：{card}"
    for part in ("${themeCard}", "${scaleCard}", "THEME_PALETTE.map(pcard)", "UI_SCALES.map(scard)",
                 'data-act="themeSet"', 'data-act="uiScaleSet"', "set-theme-preview", "set-scale-preview"):
        assert part in body, f"系统设置缺少真实选择或预览：{part}"


def test_搬走的连接参数入口真的在那边():
    """⭐ 守则 §5.8 的**另一半**：本页不摆 ≠ 功能没了 —— 每个参数都必须在**用它那一页**上找得到。

    `i8 地址` → `m02` 卡头的「i8 连接设置」（`ACT.i8SetOpen`）；
    两个**打印版式 ID** → `m03` 的「打印机设置」弹窗（`pidField('m03PidMat', 'i8_print_id_material')` …）。

    ⚠️ **这一条是离线的一半**：真机 ⑳ 两条验"那些入口真的打得开"；本件验"代码里它们还在被渲染"。
    ⚠️ **能证伪**：删掉任一入口（只留系统设置页那段指路）⇒ 用户被指到一个**不存在的地方** ⇒ 本件必红。
    """
    assert "ACT.i8SetOpen = " in SHELL, "「i8 连接设置」的入口动作不在了（`m02` 卡头那个按钮会变成死控件）"
    assert "i8 连接设置" in SHELL, "「i8 连接设置」这个说法不在了（用户按指路去找会找不到）"
    for probe in ("pidField('m03PidMat', 'i8_print_id_material')",
                  "pidField('m03PidMech', 'i8_print_id_mechanical')"):
        assert probe in SHELL, f"「付款通知书」的打印机弹窗里少了这个字段：{probe!r}"


# ⭐ `TAIL-170`（2026-09-29 · 用户裁定「都按推荐做」）：三件**跨页统一**补齐 ——
#    ⚠️ 逐页各改一处会造出"第四种状态"（同一个动作有的页写、有的页不写）⇒ 只能成批统一，故落在这里。


def test_每个导出按钮都写清了导的是什么():
    """守则 §2.4（要求与后果**提前说**）/ §2.6。

    ⚠️ 逐处按**真实范围**写，⛔ 不套模板：全站 4 处**真导出**（`EXP_ROUTES` 里那四条）写
       「导出当前筛选下看到的这些行」；另 3 处**没有落点**的兜底（`m06` 朴素那份 · `m08` 朴素那份 ·
       已取消的差异清单）**如实写"还没有落点"** —— ⛔ **不许给它们编一个范围**（编了就是假话，
       `EXP_ROUTES` 上一段注释明令禁止"顺手给这些页编一个落点"）。
    """
    # ⚠️ 两道收窄（本判据第一版就是这么假红的，别拆）：
    #    ① **剥块注释** —— `core.js` 里那段说明**引述**了旧写法 `<button … data-act="exp">`（留痕）；
    #    ② 只认**含 `<button`** 的行 —— 否则会撞上 `querySelectorAll('[data-act="exp"]')` 那行。
    exps = [ln for ln in _strip_block_comments(SHELL).split("\n")
            if "<button" in ln and 'data-act="exp"' in ln]
    assert len(exps) >= 7, f"导出按钮只剩 {len(exps)} 处？"
    bad = [ln for ln in exps if "title=" not in ln]
    assert not bad, "这些导出按钮没写清导的是什么：\n      " + "\n      ".join(x.strip()[:130] for x in bad)
    assert "导出当前筛选下看到的这些行" in SHELL, "真导出那几处的范围说明没了"


def test_置灰的按钮都写清了为什么灰():
    """守则 §4.6（看不见的功能不留"点了报错"的入口 · 置灰要说明原因）/ §5.5。

    ⚠️ 只判**模板里字面写的 `disabled`**（`<button … disabled …>`）—— 那才是"用户会看见它灰着"的那一类；
       运行期用 JS 临时置灰的（提交中 / 重入闸）各有各自动作里的守卫，**不在这里判**。
    ⚠️ 能证伪：把任一处的 `title` 摘掉 ⇒ 本件必红。
    """
    bad = [m.group(0) for m in re.finditer(r"<button[^>]*\bdisabled[^>]*>", _strip_block_comments(SHELL))
           if "title=" not in m.group(0)]
    assert not bad, ("这些置灰按钮没说为什么灰（§4.6：灰按钮不给理由）：\n      "
                     + "\n      ".join(x[:140] for x in bad))


def test_勾选表的固定列_表头与数据行同进同退():
    """守则 §4.4（相似元素不制造歧义）/ §5.9（核心操作一眼可见）。

    ⚠️ 实测（`TAIL-170`-③）：3 张勾选表（`m03`/`m04`/`m11`）**表头首格**早有 `.fl`（sticky-left），
       而**数据行首格没有** ⇒ 横向滚动时表头那格**浮着**、行里那颗勾选框滚走了（错位）。
       口径 = **两边都钉**（CSS 里 `tbody tr … .fl` 那几条背景规则本来就是为它写的）⇒ 本判据守"**同进同退**"。
       ⚠️ **订正（2026-09-29 · `A6` 顺手核出）**：此处原写「与 `m07`/`m08` 表首列一致」——**不成立**：
       `m07` 收发结存（`WH_THEAD`）与 `m08` 单据明细（`INV_THEAD`）**都没有 `.fl`**（当年就没做）。
       房内真正钉首列的是 **`m06` 表①②** ＋ 这 **3 张勾选表**；`m07` 月度会大表是 `TAIL-175` 才补的。
       ⇒ 本判据只管**本表内部同进同退**，⛔ 别拿「别的页也这样」当依据（那是把口径建在一句错话上）。
    ⚠️ 能证伪：把任一行首格的 `fl` 摘掉 ⇒ 本件必红。
    """
    for head, row in (
        ('<th class="ctr fl" style="width:34px"><input type="checkbox" class="chk" id="pickAllBox"',
         '<td class="ctr fl"><input type="checkbox" class="chk" data-act="pick"'),
        ('<th class="ctr fl" style="width:34px"><input type="checkbox" class="chk" id="jcAllBox"',
         '<td class="ctr fl"><input type="checkbox" class="chk" data-act="jcPick"'),
    ):
        assert head in SHELL, f"表头首格的 `fl` 没了（它本来就钉着）：{head[:60]}"
        assert row in SHELL, f"数据行首格没跟表头一起钉（横滚会错位）：{row[:60]}"
    # ⚠️ 草稿行 / 合计行也要跟上：否则"新增中"或"合计"那一行横滚时照样错位
    assert "leadCls:'fl'" in SHELL, "合计行首格没钉（`sumRowOf` 的 `leadCls`）"


def test_注入的工具栏走变体类_别在JS里重写静态外观():
    """守则 §5.11（界面大小：**字号与间距都乘 `--fscale`** —— 漏一处，那一处调大时不动 = 半成品相）
    ＋ §5.9（同类形态只留一处出口）。

    ⚠️ `A4`（2026-09-29 逐页 `m06`）实测：`BIND.m06` / `BIND.m09` 那两条**页首注入工具栏**把 `.fbar`
       的声明在 JS 里**又写了一遍**（`border` / `border-radius` / `margin-bottom`），而其中
       `margin-bottom:10px` **漏了 `--fscale`** ⇒ 用户把界面调大时**这一处不跟着变**。
       ⇒ 两者改走**变体类** `.fbar.plate`（声明**逐像素等价**、只差那个倍率 ⇒ 外观不变、缩放修好）。

    ⚠️ 判法取**能证伪的一般式**：`cssText` 里**不许出现静态外观声明**（`border:` 这类该走类）；
       ⛔ **不误伤定位类**的 `cssText`（`position:` / `z-index:` 那种随运行时变的 —— 例：`core.js`
       那条"请改用服务地址打开"的固定横幅，它的定位没法预先写成类）。
    """
    bad = [m.group(0) for m in re.finditer(r"cssText\s*=\s*['\"]([^'\"]*)",
                                          _strip_block_comments(SHELL))
           if "border:" in m.group(1)]
    assert not bad, ("注入的 DOM 在 JS 里重写了静态外观（该走类；⚠️ 大概率也漏了 `--fscale`）：\n      "
                     + "\n      ".join(x[:130] for x in bad))


def test_大表的首列区固定_序号与项目名称两列一起钉():
    """守则 §5.9（核心操作与核心数据一眼可见）/ §4.2（别让人做错事）。

    ⚠️ `TAIL-175`（2026-09-29 用户裁定 `A`）：月度会大表是 **20 列横表**（`min-width:1620px`）——
       往右填手填那 6 列（机械费测算 / 合同价 / 产值累计…，正好落在最右）时，**首列区
       （序号 ＋ 项目名称）会跟着滚走** ⇒ 用户**看不见自己在给哪个项目填**（会填错行）。
       ⇒ 首列区两列挂 `.fl`（sticky-left），**表头 / 数据行 / 合计行同进同退**（与 `001-52` 同一口径）。
    ⚠️ 大表与房内先例（`m06` / `m03` / `m04` / `m11` 都是**一行**表头）**形态不同**，两件事单独钉住：
       ① 只有**表头第 1 行**的前两格是「序号 / 项目名称」（`rowspan="2"`）—— 第 2 行里没有它们；
       ② 合计行首格是 `colspan="2"`（`sumRowOf` 的 `leadSpan:2`）⇒ 它**一格就盖住这两列**，
          ⛔ 别再给它后面那一格挂 `.fl`（那就多钉一列）。
    ⚠️ 第 2 列的偏移（`left`）= 第 1 列的宽，写成静态算式 `calc(39px * var(--fscale))` ——
       真机量过（`tools/oneoff/_a175_measure.py`：1440 / 1920 / 2560 视口 × 1 / 1.4 档**六种组合偏差 0**）；
       **屏幕上是否真的严丝合缝**离线判不了 ⇒ 由真机 **㉜**（`tools/probe/_shell_bigpin.py`）看管。
    ⚠️ 能证伪：摘掉任一处 `fl` / 去掉那条偏移 / 退回 `leadSpan:2` 不给 `leadCls` ⇒ 本件必红（真机 ㉜ 也会红）。
    """
    clean = _strip_block_comments(SHELL)          # ⚠️ 剥块注释：别把"说明里引述的写法"当实现
    assert '<th rowspan="2" class="fl">序号</th><th rowspan="2" class="fl">项目名称</th>' in clean, \
        "大表表头首列区没挂 `.fl`（往右填时看不见自己在给哪个项目填）"
    assert '<td class="fl fc">${ri+1}</td>' in clean and '<td class="fl sm" title="${esc(r.wh)}">' in clean, \
        "大表**数据行**首列区没跟表头一起钉（`001-52` 同口径：横滚时表头浮着、行里那两格滚走）"
    assert re.search(r"sumRowOf\(BIG_THEAD,(?:(?!\}\):'').)*?\{leadSpan:2,\s*leadCls:'fl'(?:,|\})", clean, re.S), \
        "大表**合计行**首格没钉（它是 `colspan=2`，一格就该盖住首列区两列）"
    assert '.dt[data-sort-key="m07:bigtable"] .fl + .fl{left:calc(39px * var(--fscale))}' in clean, \
        ("大表第 2 列没让开首列的宽 —— 要么露缝（露出被滚走的内容）、要么叠住首列的字；"
         "算式真机量过，⛔ 别改成「量出来的那个数」")


def test_空态指路的按钮名必须真实存在():
    """守则 §2.1（空态要交代"为什么空 ＋ 下一步"）/ §4.2（**别让人做错事**：指路指到不存在的地方）。

    ⚠️ `A6`（2026-09-29 逐页 · `m01` 项目档案）实测：那一页的空态指路写着
       「或点右上角「＋ 新增项目」建档」—— 而**那一页（乃至全站）根本没有这个按钮**
       （卡头只有「同步仓库名单」「同步常用项目列表」「导出 Excel」）⇒ 用户按指路去点，**找不到东西、卡住**。
       ⚠️ 同族第 2 例（同一个病）：`A2` 那轮 `m03` 的指路写着「＋ 新增」，而按钮叫「＋ 手动新增通知书」。
    ⚠️ 判法两半：① 指路句里点名的入口**真的存在**（按它的 `data-act` + 标题文案认）；
       ② **那句旧指路整串**不许回来（墓碑）。
       ⛔ 墓碑**不拿「新增项目」四个字**去撞（将来真加了一个叫这名字的按钮 ⇒ 会误红）。
    ⚠️ 能证伪：指路改回旧句、或把两个同步按钮改名 ⇒ 本件必红。
    """
    clean = _strip_block_comments(SHELL)
    assert "或点右上角「同步常用项目列表」「同步仓库名单」" in clean, \
        "`m01` 空态指路没指向**真实入口**（用户按着它找不到东西 ⇒ 卡住）"
    assert 'data-act="syncPj" title="从 i8 拉最新的常用项目列表' in clean, \
        "指路点名的「同步常用项目列表」这个入口不在壳里（指路又指到不存在的地方了）"
    assert 'data-act="syncWh" title="从 i8 拉最新的仓库名单' in clean, \
        "指路点名的「同步仓库名单」这个入口不在壳里（指路又指到不存在的地方了）"
    assert "或点右上角「＋ 新增项目」建档" not in clean, \
        "`m01` 空态那句**指向不存在的按钮**的旧指路又回来了（用户会卡在那儿）"


def test_删除确认里不许把要求句甩给用户():
    """守则 §1.1（不是给使用用户看的 ⇒ 删掉/换成人话）/ §2.5（用业务术语，不用内部话术）
    ＋ §2.4（**后果提前说清**）。

    ⚠️ `A6`（2026-09-29 逐页 · `m01`）实测：删除确认弹窗的第一句 = 「⚠️ 必须**列出删除影响范围**（§7.2）」
       —— 那是《说明书》§7.2 里**写给实现的要求句**，被原样搬上了界面 ⇒ 用户在删除前看到的
       不是"删了会怎样"（他要知道的），而是一句**要求我们（开发）做事**的话。
    ⚠️ 同日**顺藤摸出同族还有两处**（同一句话的变体，都在别的页的删除确认里）：
       `m03` 手动行「⚠️ 删除前**必须列出影响范围**」· `m05` 期初行「⚠️ 删除前**必须列出影响范围**」
       ⇒ ⭐ **判据不能只钉一处**（只钉 `m01` ＝「判据比条文弱」＝ 另一种假绿）⇒ 本件改成**一般式**：
       「`必须列出` 这种**要求句式**一律不许上屏」（⚠️ 先**剥块注释**再判 —— 注释里会引述旧写法作留痕，
       那是本仓踩过三次的老课）。
    ⚠️ 判法两半：① **要求句式**不许上屏（一般式墓碑）；② 删除确认里必须留下**人话的后果**
       （项目删除不可撤销；通知书展示实际message/effects；期初展示金额与欠款后果）。
    ⚠️ 能证伪：任一处改回要求句、或把人话后果删掉 ⇒ 本件必红（反向灵敏度 `_mut_a6.py` 各打一次）。
    """
    clean = _strip_block_comments(SHELL)
    assert "必须列出" not in clean, \
        "界面上又出现**写给实现的要求句**（『必须列出…』）—— 用户要知道的是「删了会怎样」，不是我们的待办"
    project = act_entry('delPj')
    notice = clean[clean.index("ntDel:t=>"):clean.index("ntDelOk:")]
    opening = clean[clean.index("delLg:t=>"):clean.index("delLgOk:")]
    assert '${esc(r.message)}' in project, "项目删除没展示后端真实影响与不可撤销后果"
    assert "${imp.message}" in notice and "imp.effects.map(" in notice, "通知书删除没展示真实影响回执"
    assert "欠款合计" in opening and "重新录入" in opening, "期初删除没有金额后果及重录说明"


def test_点不通的按钮必须置灰而且理由要看得见():
    """守则 §5.5（"看着能点"的点了必须有**符合预期**的结果；不能点的置灰/隐藏 ＋ 说明为什么）
    ＋ §4.6（看不见的功能不留"点了报错"的入口）＋ §2.7（结论贴在被说的对象上）。

    ⚠️ `TAIL-177`（2026-09-29 · `A6` 顺手查出 · 用户裁定 `A`）实测：`m01` 的「删除」原本**点得动** ——
       弹确认框（里面还替用户把影响范围列了一半）→ 点「确认删除」→ 才被告知「删除尚未接通后端」
       ⇒ **一整套流程走完、什么都没发生**（§5.5），而且「确认删除」那枚按钮红着、看着完全能点。
       ⇒ 当时先把「确认删除」置灰，理由写在弹窗里。TAIL-284接通后按后端结论动态启用，仍保护拒删禁用与可见原因。
    ⭐ 为什么"理由**必须上屏**"（`title` 只当补充）：**真机实测**（`tools/oneoff/_a6b_check.py`）——
       置灰按钮的 `matches(':hover')` **仍然成立**（Chrome 允许悬停态，`pointer-events: auto`）
       ⇒ `title` **有**机会弹；⚠️ 但它只对"**鼠标停在按钮上**"的人有效（键盘 Tab / 触屏根本没有悬停）
       ⇒ 所以置灰的理由要**写在屏幕上看得见的地方**（本件钉的就是这一句）。
       ⚠️ 全站那批「置灰写理由」（约 27 处字面 `disabled`）**是否也只挂在 `title` 上**，另立 `TAIL-178` 复核。
    ⚠️ 能证伪：拒删时按钮仍可点、或把可见原因删掉 ⇒ 本件必红。
    """
    project = act_entry('delPj')
    assert "API.pjDeleteImpact(p.id)" in project, "删除必须先读取真实影响"
    assert "r.can_delete?'':'disabled'" in project, "后端不允许删除时必须禁用确认"
    assert '${esc(r.message)}</div>' in project, "拒删原因必须在弹窗正文可见，不能只放title"


def test_集采抓取按钮要写清后果():
    """守则 §2.4（操作后果提前说清）/ §4.4（相似元素不制造歧义 —— 这枚按钮**会顶号**，不是"刷新一下"）。

    ⚠️ `A7` 逐页（`m11` 集采台账 · 2026-09-29）实测：卡头那枚「抓取采购合同信息」**一个字提示都没有**
       （无 `title`），而**同一件事**在别处都写了 —— `m01`「同步仓库名单」写「会登录 i8，需二次确认」·
       `m02` 两个同步同款；而集采抓取**还会顶号**（`D9`：登录会顶掉该账号的其它在线会话 ⇒
       同事正在用 i8 时**不能点**）。⇒ 本批把提示补到按钮上（内容与确认弹窗**同一口径**，⛔ 不新增口径）。
    ⚠️ 本条只判**按钮上的提示在不在、写没写清后果**（离线可判）；"抓取一律人工、没有定时"那条口径
       由 `test_acc_jc_shell.py` 与真机 `_shell_smoke` 看管（⛔ 不复述对方）。
    ⚠️ 能证伪：摘掉 `title`、或把后果那句删掉 ⇒ 本件必红（反向灵敏度 `tools/mut/_归档-20261009/_mut_a7.py` 各打一次）。
    """
    clean = _strip_block_comments(SHELL)
    seg = clean.split('data-act="jcFetch"', 1)
    assert len(seg) == 2, "`m11` 卡头那枚「抓取采购合同信息」不见了"
    head = seg[1].split(">", 1)[0]                      # 该按钮自己的属性区
    assert "title=" in head, \
        "集采抓取按钮**没有提示**（会登录 i8 / 可能顶号 —— 用户点下去才知道）"
    assert "i8" in head and "顶" in head, \
        "抓取按钮的提示没写清**后果**（会登录 i8 ＋ ⚠️ 可能顶掉该账号在线会话）"


def test_集采台账行身份区钉列与隐藏列都按id定位_偏移必须量出来():
    """守则 §5.9（核心数据一眼可见）· §4.2（别让人做错事）。

    ⚠️ `TAIL-180`（`B` 案 · 2026-09-29 **用户裁定**）：`m11` 合同主表 **21 列 · 330 行**（2026-10-11 加「合同编号」后；贸易三列改默认隐藏、仍可切换），而
       **4 个可编辑列**（付款方式 / 备注 / 存档号 / 寄回日期）**正好落在最右** ⇒ 往右滚去填它们时，
       **行身份区**（勾选框 ＋ 序号 ＋ 合同日期 ＋ 材料名）必须留在视野里，否则**看不见自己在给哪条
       合同填**（会填错行）—— 同族 = 月度会大表 `TAIL-175`（那页已按 `A` 案钉好）。
    ⚠️⚠️ **本页不能照抄大表那份静态算式**（真机实测 `tools/oneoff/_a711_measure.py`）：
       `table.dt` 是 `table-layout:auto` ＋ 表头带**排序箭头** ⇒ 列宽**随视口变**
       （「勾选框」列 1440/1920 时 **29px**、**2560 时 34px**）⇒ 静态 `calc(Npx * var(--fscale))`
       在某档视口下必然错位（错位是 `sticky` 的经典失败模式，且**不报错**）。
       ⇒ 本页走「**渲染后按表头实测**设 `left`」，并且**每渲染一次都要重量**
       （`render()` 重建整张表；隐藏 / 显示贸易公司三列还会**改剩下的列宽**）。
    ⚠️ 钉的必须是**连续前缀**（`sticky` 的硬约束）：序号(#1) 与 材料名(#3) 中间隔着 合同日期(#2)
       ⇒ 一并钉上（只钉两头会让 #2 被盖住 / 从缝里露出来）。
    ⭐⭐ 2026-10-11（`TAIL-298`）：**钉哪几列 / 藏哪几列一律按 id 说话**（`JC_PIN_IDS` / `JC_HIDE_IDS` ·
       id = 后端列清单 `domain.JC_COLUMNS` 的 `key`）—— ⛔ 不再是写死的列号：`TAIL-290` 加一列
       「合同编号」时那两处列号都得人肉同步，**漏改不报错**（悄悄藏错列 / 钉错列）。⇒ 本件钉两件：
       ① **每个 id 都在规格里**（写错 ⇒ 当场红，⛔ 不等真机上看出"某列没被藏 / 没被钉"）；
       ② 钉列 id 恰是列清单的**连续前缀**（`sticky` 的硬约束在**身份**这一层同样成立）。
    本件核列身份与连续前缀；实测偏移、显隐、缩放和虚拟窗口的几何后果回test_table_layout.py。
    """
    from app.mod11_jc import domain as D          # noqa: PLC0415 —— 只在本次对账时取「规格」

    keys = [c["key"] for c in D.JC_COLUMNS]
    pin_ids = const_items("JC_PIN_IDS")
    hide_ids = const_items("JC_HIDE_IDS")

    # ① 每个 id 都必须**在规格里真有那一列**（`TAIL-298` 的可证伪点：写错 id ⇒ 静默失效）
    unknown = sorted((set(pin_ids) | set(hide_ids)) - set(keys))
    assert not unknown, (
        "`m11` 屏幕行为表里这些 id 在**后端列清单**（`domain.JC_COLUMNS`）里不存在"
        "（拼错 / 列改名了）：\n  " + "\n  ".join(unknown)
        + "\n  ⇒ id 以 `domain.JC_COLUMNS` 的 `key` 为准（⛔ 别改本件去迁就它）——"
          " 写错的直接后果是那一列**悄悄不藏 / 不钉**，界面上一点提示都没有")
    assert pin_ids, "钉列 id 表空了 —— 行身份区没钉（`sticky` 那件事整个没了）"

    # ② 钉列 = 列清单的**连续前缀**（`sticky` 硬约束：中间不能空一格）
    assert pin_ids == keys[:len(pin_ids)], (
        "钉列必须是列清单的**连续前缀**（`sticky` 的硬约束 —— 中间隔着不钉的一列会露缝 / 被盖住）："
        f"\n  钉列 id = {pin_ids}\n  许可    = {keys[:len(pin_ids)]}")
    assert len(pin_ids) >= 2, (
        f"行身份区只有 {len(pin_ids)} 列 —— 形态变了（用户要的是「勾选框 ＋ 序号 ＋ 合同日期 ＋ 材料名」）")

    # ③ 隐藏那三列 = 「贸易公司」三列（用户 2026-09-20 口径：不常用 ⇒ 默认收起，仍可切换）
    assert set(hide_ids) == {"trade_co", "trade_contract_amt", "trade_inv_sum"}, (
        f"「隐藏贸易公司三列」的 id 集合变了：{hide_ids} —— 改口径要显式改本件")

    clean = _strip_block_comments(SHELL)
    assert "function jcApplyPin()" in clean, \
        "`m11` 行身份区的钉列函数不见了（`jcApplyPin`）—— 往右填那 4 列时看不见在给哪条合同填"
    # 实测偏移、首列0及显隐/resize/虚拟窗口收尾由test_table_layout行为回归验证。
    assert '.dt[data-sort-key="m11:jc"] .fl' not in clean, \
        ("`m11` 的钉列**不许**退回静态 CSS 规则（`.dt[data-sort-key=\"m11:jc\"] .fl{left:…}`）——"
         "实测列宽随视口变，静态值会错位")
    # ④ `TAIL-298`：两处**列号**硬编都退场（隐藏那三列的 `nth-child(9/10/11)` 与钉列的 `[1,2,3]`）
    for fn in ("function jcApplyHide()", "function jcApplyPin()"):
        body = clean.split(fn, 1)[1].split("\nfunction ", 1)[0]
        assert "jcColIndex" in body, f"`{fn}` 没按 id 定位（`jcColIndex`）—— 又写回列号了？"
        assert "nth-child(9)" not in body and "JC_PIN = [1, 2, 3]" not in body, \
            f"`{fn}` 里又出现写死的列号（`TAIL-298` 治的就是「加一列要人肉同步」那件事）"


def test_启动失败横幅不许盖住内容():
    """守则 §4.6（提示与可见性）/ §5.5（点得到）。

    ⚠️ `TAIL-182`（`A` 案 · 2026-09-29 **用户裁定** · 出处 = §13.6 接手核验续记 ＋
       `.codebuddy/memory/2026-09-29.md`）：`core.js::bootErrorBanner()` 那条横幅原是
       **`position:fixed;left:0;right:0;top:0;z-index:9999`** ⇒ **压在页面之上** ⇒ 页首那一带的
       **卡头按钮全都点不着**（真机实测：`#jcTradeBtn` 被它挡住、Playwright 报
       `intercepts pointer events` 连重试 57 次；`elementFromPoint` 拿到的正是它）。
       守则 `§4.6` 的反例原文就是「提示条盖住可点区（本仓真例：`.toast` 吃掉浮层点击）」——
       **同一族**（当年只修了 `.toast`）。
    ⚠️ 改成**进布局流**：插在 `main` 里 `#view` 之前 ＋ `flex:0 0 auto` ⇒ 它**占位**、把内容往下推；
       ⛔ 不能挂 `body`（`html,body{height:100%;overflow:hidden}` ＋ `.app{height:100vh}` ⇒ 会溢出被裁）。
       ⭐ 它**不会滚走**（滚动容器是 `.view`，本横幅是它的**兄弟**）—— 那正是 `A` 案要的形态。
    ⚠️ 能证伪：把 `position:fixed;…;z-index:9999` 加回来、或改回 `document.body.prepend(el)`
       ⇒ 本件必红；**屏幕上到底盖没盖住、点不点得到**由真机 **㉞** 看管
       （`elementFromPoint` ＝ 那枚卡头按钮 · 横幅下缘在卡头之上）。
    """
    clean = _strip_block_comments(SHELL)
    seg = clean.split("function bootErrorBanner()", 1)
    assert len(seg) == 2, "启动失败横幅（`bootErrorBanner`）不见了"
    body = seg[1].split("\nfunction ", 1)[0]
    flat = body.replace(" ", "")
    assert "position:fixed" not in flat and "position:absolute" not in flat, \
        "启动失败横幅又变成**浮层**了 —— 它会压在页首、把卡头按钮的点击全吃掉（`TAIL-182` 的原始症状）"
    assert "insertBefore" in body and "flex:0 0 auto" in body, \
        "横幅必须**进布局流**（插在 `main` 里 `#view` 之前 ＋ `flex:0 0 auto` 占位），⛔ 不是挂到 `body`"


def test_删除分档的界面说法必须与定案一致():
    """守则 §4.2（**状态必须真实**：删了会怎样，界面说法必须与实现/定案一致）/ §2.5（人话）。

    ⚠️ `A6b`（2026-09-29 · 用户「按推荐」）实测两处**页面在说旧口径**（都是"照抄规格"漏下来的）：
       ① `m05` 期初行的删除确认写着「该行按**软删留痕**处理（属核心业务数据）」——
          而 `mod05_flow.repository.delete_opening` 就是 `s.delete(row)`（**真删**、行里根本没有留痕字段），
          《说明书》§9.4 的 2026-09-20 定案也把「**期初**」明确列在**硬删**那一档
          ⇒ 那句话给的是**假的安全感**（用户以为"删了还能恢复"）；
       ② `m14` 的「硬规矩」表第 6 条写着「核心数据删除是『软删 + 留痕』；配置类是真删」——
          那是 §9.4 **改判之前**的"按类别分"说法（定案改成**按「删了能不能复原」分**）。
    ⚠️ 判法两半：① 旧说法**不许回来**（墓碑）；② 必须留下**真实后果**
       （「真的删掉、删了不能恢复」＋「随时可以重新录入」）。
    ⚠️ 能证伪：任一处改回旧说法 ⇒ 本件必红。
    """
    clean = _strip_block_comments(SHELL)
    assert "该行按<b>软删留痕</b>处理" not in clean, \
        "`m05` 期初行又说「软删留痕」了 —— 后端就是真删、§9.4 定案也把期初划在硬删档（假的安全感）"
    assert "核心数据删除是「软删 + 留痕」" not in clean, \
        "`m14` 的「硬规矩」表又用回 §9.4 改判前的「按类别分」说法了"
    assert "删了不能恢复" in clean and "随时可以重新录入" in clean, \
        "期初删除确认必须保留不可恢复的真实后果及重新录入入口"


def test_壳新增的人工指认清单表也走统一出口_TBL():
    """`TAIL-64` A′ · `core.js`：两张**壳新增**的「人工指认」清单表走统一出口 `TBL`。

    ⚠️ **为什么单开一条守它**：这两张表**没有任何 claim 判据**（「人工指认」这套是壳新增的能力，
       原型里没有这两个盒子）⇒ 换 `TBL` 时**别的东西感知不到**（`U1` 只比原型同名 `V.*` 切片，看不见 `core.js`）。
    ⚠️ **同一件里那张「回收站」表 ⛔ 没换**（不是漏了）：它的行是**活的 DOM 节点**
       （`tb.appendChild(tr)` —— 要从别处**原样搬**过来，含恢复按钮），而 `TBL` 是**字符串渲染器**。
    自证 = `tools/mut/_mut_tbl.py` 的 M22／M23 去掉这两处委托 ⇒ 必须红。
    """
    assert "TBL({cls:'cond',head:'<th>项目全名</th><th>待选仓库</th>" in SHELL, \
        "「待选仓库（多仓待人工指认）」那张表没走统一出口 `TBL`（`TAIL-64` A′）"
    assert "TBL({cls:'cond',head:'<th>陌生仓库名</th>" in SHELL, \
        "「陌生仓库名（多命中待指认）」那张表没走统一出口 `TBL`（`TAIL-64` A′）"
    # ⚠️ 反例也钉住：那张 DOM 拼行的回收站表**故意**留在裸 `<table>` —— ⛔ 别"顺手"换掉它
    assert "card.innerHTML = `<h4>回收站 · 已删除账号" in SHELL and "tb.appendChild(tr)" in SHELL, \
        "回收站那张表的「DOM 拼行」形态变了 —— 它换不了 `TBL`（`rows` 是活节点，不是字符串）"


def test_壳新增那四页里的清单表也走统一出口_TBL():
    """`TAIL-64` A′ · `legacy.js`（「**四个暂留件**」= 系统设置 ＋ 三个历史导入页）里的清单表走统一出口 `TBL`。

    ⚠️ **为什么单开一条守**：这四页是**壳新增**（原型里根本没有）⇒ `U1`（只比原型同名 `V.*` 切片）**看不见本件**；
       而这几张表又**没有各自的 claim 判据** ⇒ 换 `TBL` 时**别的东西感知不到**。
    ⚠️⚠️ **本件已「全清」⇒ 现行六张全钉**（2026-09-29：`legacy.js` 里裸 `<table>` 归零，`tools/oneoff/_tbl_scan.py` 可复核）。
       ⛔ 演进史值得记：**先落 3 张时本判据只钉那 3 张** —— 因为"写全部"会让它**下一批一开工就假红**
       （判据不该替别的批管进度）；等本件真做完了，才把七张一次钉齐。
    自证 = `tools/mut/_mut_tbl.py` 的 M24／M25／M26／M27／M28／M29／M30 去掉现行六处委托；M24 保护设置页删项 ⇒ 必须红。
    """
    assert "TBL({cls:'sm',head:'<th style=\"text-align:left\">列名</th>" in SHELL, \
        "「本系统要哪些列」那张对照表没走统一出口 `TBL`（`TAIL-64` A′）"
    assert "TBL({cls:'sm',head:pcols," in SHELL, \
        "「预览」那张表（`pcols` / `prows`）没走统一出口 `TBL`（`TAIL-64` A′）"
    assert "TBL({head:(b.columns || []).map(" in SHELL, \
        "「块」通用渲染件（`lgBlock` 那张表）没走统一出口 `TBL`（`TAIL-64` A′）"
    assert "TBL({cls:'sm',head:'<th style=\"min-width:92px\"></th>'+IMP.cols.map(" in SHELL, \
        "导入页「字段对照」那张大表没走统一出口 `TBL`（`TAIL-64` A′）"
    assert "TBL({cls:'sm',head:'<th>行</th><th>列</th><th>原值</th><th>原因</th>'," in SHELL, \
        "「问题行」那张表没走统一出口 `TBL`（`TAIL-64` A′）"
    assert "TBL({cls:'sm',rows:tech.map(k =>" in SHELL, \
        "「技术细节」（`<details>` 里那张无表头的表）没走统一出口 `TBL`（`TAIL-64` A′）"


def test_弹窗里的选择表与影响行表也走统一出口_TBL():
    """`TAIL-64` A′ · `shell/actions.js`：两张**当时没有判据守**的表也走统一出口 `TBL`。

    ⚠️ **为什么单开一条守**：这两张表**没有各自的 claim 判据**（一张是「选项目上大表」的选择器、
       一张是「删除付款计划行确认」里的影响行清单）⇒ 换 `TBL` 时**别的东西感知不到**。
    ⚠️ 两张都是**刻意不可排**（只出 `data-sort-key`：行序是**用户手工调的** / 影响行清单不需要排序）
       ⇒ 都必须带 `sort:false`（同 `modal:debtPick`）。
    ⚠️ 其中「影响行」那张**是壳独有**的（原型里没有「审查结果」这张表 ⇒ 当年随后端影响范围一起加的）。
    自证 = `tools/mut/_mut_tbl.py` 的 M38（`bigPick` 去委托）/ M39（影响行表去委托）都必须红。
    """
    assert "TBL({cls:'cond',key:'modal:bigPick',sort:false,head:'<th style=\"width:34px\">选</th>" in SHELL, \
        "「选项目上大表」那张选择表没走统一出口 `TBL`，或没声明「刻意不可排」（`sort:false`）—— `TAIL-64` A′"


def test_筛选栏外壳只走统一出口_FBAR():
    """⭐ `TAIL-64` **P4-a**（2026-09-30）：一根筛选栏的**外壳**（`fbar` 那层）走统一出口 `FBAR`。

    ⚠️ **为什么必须有一条守它**：外壳换写法**渲染字节一字不变** ⇒
       · 页面看起来一模一样（人眼看不出）；
       · `U1` 是**原型 ⇄ 壳逐行比** —— 本批是**两侧同批同句**改的 ⇒ 它只会说"一致"，
         **两侧一起写错也一样"一致"**；
       · 真机看到的是**渲染结果**，更看不出源码是怎么拼的。
       ⇒ 只有"把它改坏 ⇒ 本判据必须红"这一条，能证明这处**真的委托出去了、而且内核真把控件拼进了栏里**。
    ⚠️ **本条钉的是 `m01` 那一处"试点"**（`P4-a`：先证明「外壳换写法、控件留在原地」能做到 Δ0）。
       ⭐ **`P4-b` 已把它铺到全站**（2026-09-30）⇒ **"有没有漏网的裸外壳"改由一条扫描式判据看**：
       `test_筛选栏外壳全站都走统一出口`（⛔ 别把 22 处的字面逐个抄进来 —— 那是维护不起的第二份名单）。
    ⚠️ **判法 = 两段拼起来看**（照 `shell_src.with_tbl()` 那套 doctrine）：切片**委托** `FBAR`
       ＋ **内核里**真把 `body` 拼进 `fbar` 那层。⛔ 别退回"切片里必须有 `<div class="fbar">` 字面"
       —— 那等于宣布以后**不许抽通用件**（与 `TAIL-64` 相反）。
    自证 = `tools/mut/_归档-20261009/_mut_fbar.py`：M1 去掉委托 / M2 掏空内核 ⇒ 本判据必须红。
    """
    i = SHELL.find("\nV.m01=()=>{")
    j = SHELL.find("\n};", i) if i >= 0 else -1
    m01 = SHELL[i:j] if i >= 0 and j > i else ""
    assert m01, "壳里找不到 `V.m01` 切片"
    assert "FBAR({body:" in m01, "`m01` 的筛选栏外壳没走统一出口 `FBAR`（`TAIL-64` P4-a）"
    two = with_fbar(m01)
    assert '<div class="fbar' in two, \
        "`FBAR` 内核不再渲染 `fbar` 那一层 ⇒ 筛选栏会**没有外壳**（边框 / 底色 / 换行全丢）"
    assert "'>'+body+'</div>'" in two, \
        "`FBAR` 内核没有把 `body` 拼进栏内 ⇒ **栏里的筛选控件会全部消失**（外壳还在、里面是空的）"
    # ⚠️ 墓碑：本页**不许再裸写**筛选栏外壳。⛔ **先剥块注释再判** —— 注释里会引述旧写法（本仓踩过）。
    assert '<div class="fbar">' not in _strip_block_comments(m01), \
        "`m01` 又写回裸的筛选栏外壳了（应委托 `FBAR`：`TAIL-64` P4-a）"


def test_筛选栏外壳全站都走统一出口():
    """⭐ `TAIL-64` **P4-b**（2026-09-30）：**全站**筛选栏的外壳都收进 `FBAR` —— 壳里**不许再裸写** `class="fbar…"`。

    ⚠️ **为什么这条必须存在**：外壳换写法**渲染字节一字不变** ⇒ `U1`（两侧逐行比）／真机／人眼
       **都看不出**某一处到底换没换 —— 这正是 `P4-a` 那条判据当初要写"⛔ 别把别的页写进来"的原因
       （它钉不了 22 处）。本批铺开之后 ⇒ **一条扫描式判据**就能把漏网的裸外壳当场点出来，
       ⛔ 不用逐页数、也⛔ 不用把 22 处字面抄成第二份名单（那种名单必然漂）。
    ⚠️ **判法**：先**剥块注释**（`FBAR` 自己的说明里就**引述**了 `class="fbar [cls]"` —— 本仓踩过三次），
       再数 `class="fbar` ⇒ 只许**内核那一处**（`'<div class="fbar'+…`）。
    ⚠️ **覆盖面 = 合并后的整支壳**（`index.html` ＋ 全部 `shell/*.js`）—— ⛔ 只看 `index.html` 会**整批漏掉**
       `actions.js` / `legacy.js` / `pages-a.js` / `pages-b.js` 里那 **10 处**（同 `_tbl_scan.py` 的教训）。
    自证 = `tools/mut/_归档-20261009/_mut_fbar.py` 的 `M3`（内核不再出 `fbar` 那层）/ `M4`（又裸写一层外壳）必须红。
    """
    # ⚠️ **顺序有讲究**：先查**内核**（它一旦坏了，下面那个"数出来 = 0"会**误报成"全站没有裸外壳"**）
    assert 'class="fbar' in fbar_kernel(), \
        "`FBAR` 内核不再渲染 `fbar` 那层 ⇒ 筛选栏会**没有外壳**（边框 / 底色 / 换行全丢）"
    code = _strip_block_comments(SHELL)
    n = code.count('class="fbar')
    assert n == 1, (
        f"全站还有 **{n}** 处筛选栏是**裸写**的外壳（`class=\"fbar…\"` 只该出现在 `FBAR` 内核那 1 处）"
        " —— 守则 §5.9「同类形态只留一处出口」：把新写的那几处也换成 `${FBAR({…})}`")


def test_项目选择按钮只走统一出口_PJB():
    """⭐ `TAIL-64` **P4-d-a**（2026-09-30）：`pjwrap` 里**那枚 ▾ 按钮**走统一出口 `PJB`。

    ⚠️ **为什么要有它**：那串样板 —— `style="min-width:Npx;display:inline-flex;align-items:center;
       justify-content:space-between;gap:calc(8px * var(--fscale))"` ＋ 收尾那枚
       `<span class="mut" …>▼</span>` —— 原本**逐处手写**（12 处，`min-width` 实测 **6 种值**），
       而换写法**渲染字节一字不变** ⇒ 人眼 / 真机 / `U1` 都看不出某处到底换没换。
       ⇒ 与 `FBAR` 同族：**只有"改坏了必须红"这一条**能证明它真的委托出去了、内核真拼出了按钮。
    ⚠️ **本条钉的是 `V.m03` 那一处"试点"**（`P4-d-a`）。⭐ **`P4-d-b` 已把它铺到全站 11 处**
       （2026-09-30）⇒ **"有没有漏网的手写按钮"改由一条扫描式判据看**：
       `test_项目选择按钮全站都走统一出口`（⛔ 别把 11 处的字面逐个抄进来 —— 那是维护不起的第二份名单）。
    ⚠️ **判法 = 两段拼起来看**（照 `with_tbl()` / `with_fbar()` 那套 doctrine）：切片**委托** `PJB`
       ＋ **内核里**真拼出那枚按钮（含标签）＋ **不再手写**那串样板。
    自证 = `tools/mut/_归档-20261009/_mut_pjb.py`：去掉委托 / 掏空内核 ⇒ 本判据必须红。
    """
    i = SHELL.find("\nV.m03=()=>{")
    j = SHELL.find("\n};", i) if i >= 0 else -1
    m03 = SHELL[i:j] if i >= 0 and j > i else ""
    assert m03, "壳里找不到 `V.m03` 切片"
    assert "PJB({act:'pjToggle'" in m03, \
        "`m03` 的「项目（可多选）」按钮没走统一出口 `PJB`（`TAIL-64` P4-d）"
    kern = pjb_kernel()
    assert "data-act=" in kern and "▼" in kern, \
        "`PJB` 内核不再出那枚按钮（或丢了 ▼）—— 项目选择控件会**点不开**"
    assert "span>'+label+'</span>" in kern, \
        "`PJB` 内核没有把标签拼进按钮里 ⇒ **按钮上什么都不显示**（外壳还在、里面是空的）"
    # ⚠️ 墓碑：本页**不许再手写**那串按钮样板（⛔ 先剥块注释再判 —— 注释里会引述旧写法）
    assert 'data-act="pjToggle" style="min-width:' not in _strip_block_comments(m03), \
        "`m03` 又写回手写的按钮样板了（应委托 `PJB`：`TAIL-64` P4-d）"


#: 「项目选择按钮」那串样板 `style` 的**固定部分**（`min-width` 的 `N` 是唯一变量）。
#: ⚠️ 拿它当**扫描记号**而不是拿某个 `act` 名 —— `PJB` 的内核里是 `'+w+'px`（**不是数字**）⇒ 扫不着它，
#:    而**手写**的每一处都长这样 ⇒ 一次就能把漏网的都点出来（⛔ 不用抄一份 act 名单）。
_PJB_BOILER = re.compile(
    r'style="min-width:\d+px;display:inline-flex;align-items:center;'
    r'justify-content:space-between;gap:calc\(8px \* var\(--fscale\)\)"')
#: ⛔ **唯一一处例外**：`ui.js` 的 `tmBtn`「**选时间**」按钮 —— 样板**一模一样**、但它是**另一家族**
#:    （⛔ 不是"选项目"；它的标签格还带 `class="fc"`）⇒ `PJB` 那一版**收不了它**。见 `TAIL-196`。
_PJB_EXEMPT = 'data-act="mpToggle"'


def test_项目选择按钮全站都走统一出口():
    """⭐ `TAIL-64` **P4-d-b**（2026-09-30）：**全站**「项目选择按钮」都收进 `PJB` —— 壳里**不许再手写**那串样板。

    ⚠️ **为什么这条必须存在**：换写法**渲染字节一字不变** ⇒ `U1`（原型那侧还是旧形态、无从对位）／真机／人眼
       **都看不出**某一处到底换没换 —— 这正是 `P4-d-a` 那条判据当初要写"⛔ 别把别的页写进来"的原因
       （它钉不了 11 处）。本批铺开之后 ⇒ **一条扫描式判据**就能把漏网的手写按钮当场点出来。
    ⚠️ **判法**：先**剥块注释**（本仓踩过三次"拿注释当实现"），再按**样板 `style` 的固定部分**扫。
    ⚠️ **覆盖面 = 合并后的整支壳**（`index.html` ＋ 全部 `shell/*.js`）—— ⛔ 只看 `index.html` 会**整批漏掉**
       `legacy.js` 那处的「仓库名」按钮（同 `_tbl_scan.py` / `_p4b_survey.py` 的教训）。
    ⚠️ **例外只有一处且写清原因**：`tmBtn`（`ui.js` 的「选时间」按钮）样板同款但**另一家族**，
       见 `_PJB_EXEMPT` 与 `TAIL-196`。⛔ 别顺手把它并进来（那要先给 `PJB` 加 `labelCls` 并**改名**）。
    自证 = `tools/mut/_归档-20261009/_mut_pjb.py`：`M3`（内核不再出那串样式）/ `M4`（又手写一枚）必须红。
    ⚠️ **为什么 `@acc()` 不绑契约点**：本批**渲染字节不变 ⇒ 没有用户可见的变化** —— 为一个"机制"新开契约点口径不合
       （同 `P4-a` / `P4-b` 那两条，以及紧挨着的那条 `.fbar` 变体判据）。
    """
    # ⚠️ **顺序有讲究**：先查**内核**（它一旦坏了，下面那个"扫出来 = 0"会**误报成"全站没有手写按钮"**）
    kern = pjb_kernel()
    assert "gap:calc(8px * var(--fscale))" in kern, \
        "`PJB` 内核不再出那串共用样式 ⇒ 按钮的宽度 / 对齐 / 间距会变（`▼` 也不贴右）"
    assert "span>'+label+'</span>" in kern, \
        "`PJB` 内核没有把标签拼进按钮里 ⇒ **按钮上什么都不显示**（外壳还在、里面是空的）"
    code = _strip_block_comments(SHELL)
    naked: list[str] = []
    for m in _PJB_BOILER.finditer(code):
        line = code[code.rfind("\n", 0, m.start()) + 1: code.find("\n", m.start())]
        if _PJB_EXEMPT not in line:
            naked.append(line.strip()[:90])
    assert not naked, (
        f"全站还有 **{len(naked)}** 处「项目选择按钮」是**手写**的样板（应委托 `PJB`）——"
        "守则 §5.9「同类形态只留一处出口」：把新写的那几处也换成 `${PJB({…})}`：\n  "
        + "\n  ".join(naked[:3])
        + f"\n（⛔ 允许的例外只有 `{_PJB_EXEMPT}` 那一处 · 见 `TAIL-196`）")


#: ⭐ `TAIL-64` `P5-d`：**已转成列定义式的调用点** ⇒ `(表的 `key`, 它那串**手写 `rows:` 的整串**)`。
#: ⚠️ 每转一处就往这里加一行；⛔ **别把"还没转的"写进来**（那会让它们下一批一开工就**假红**）。
#: ⚠️ 旧串必须写**整串**：`modal:ledExp` 与邻近那张表的行模板**前缀同款**、只差一格 —— 只写前缀会**假红**
#:    （本判据首版就栽在这）。
_P5D_DONE: tuple[tuple[str, str], ...] = (
    ("modal:ledExp",
     'rows:pjs.map((k,i)=>`<tr><td class="fc">${i+1}</td><td>${esc(fnOf(k))}</td>'
     '<td class="sm">辅材欠款 / 机械欠款 / 特殊费用月报表</td></tr>`)'),
)


def test_表格件支持列定义式_试点已接上():
    """列定义式仍派生表头/行；逐一保护现行调用者。

    TAIL-265撤掉MOD06文件名预览表，迁移为复选框弹窗；台账文件预览仍走列定义式。
    内核保护与每个现行调用点的委托、手写rows墓碑都保留，不以撤表证明机制通过。
    """
    # ⚠️ **先查内核**：它坏了，下面"试点看着对"也证明不了什么（同 `PJB` 那条的顺序讲究）
    kern = re.sub(r"/\*.*?\*/", "", tbl_kernel(), flags=re.S)
    assert "if(cols){" in kern, \
        "表格件没有**列定义式**那条分支（收了 `cols` 不用 ⇒ 悄悄走回 `rows`，给了 `cols` 的表会**一行不出**）"
    assert "head=cols.map(c=>c.t).join('')" in kern, \
        "列定义式没有从 `cols` 派生**表头** ⇒ 给了 `cols` 的表没有表头（而**不报错**）"
    assert "rows=list.map((x,i)=>'<tr>'+cols.map(c=>c.r(x,i)).join('')+'</tr>')" in kern, \
        "列定义式没有从 `cols` 派生**行** ⇒ 给了 `cols` 的表**一行都不出**"
    src = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", read_shell(), flags=re.S))
    #: ⚠️ 逐处核（**别只核一处**：`P5-d-a` 只算试点，`P5-d-b` 起要逐处守住）：
    #:    ① 那处**真的走了列定义式**（`cols:` ＋ `list:` 就在它 `key` 之后不远处）；
    #:    ② **墓碑**：那处的手写 `rows:` **整串**不许再出现。
    assert _P5D_DONE, "列定义式没有任何现行观测面"
    for key, old_rows in _P5D_DONE:
        if f"key:'{key}'" not in src:
            raise AssertionError(f"`{key}` 那张表不在（改名了？）")
        seg = src[src.index(f"key:'{key}'"):][:320]
        #: ⚠️⚠️ 这条断言的**话术里不能出现花括号对**：它挂在一个 f-string 上 ⇒ `{t,r}` 会被当**表达式求值**
        #:    （实测：变异跑出 `NameError: name 't' is not defined` ⇒ 「看着被抓住」其实是**报错**，不是判据红）。
        assert "cols:[{t:'<th>#</th>'" in seg and "list:" in seg, \
            f"`{key}` 那处没走列定义式（`P5-d` 的形态 = `cols:[…]` ＋ `list:`）"
        assert old_rows not in src, (
            f"`{key}` 那处**又写回手写的 `rows:`** 了 —— 转了白转（`P5-d` 的墓碑）。"
            "⚠️ 更要紧的是「**看着改了、其实没用**」：`cols` 与 `rows` **同时给**时本件是 `cols` 优先")
