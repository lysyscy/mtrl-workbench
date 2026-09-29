"""前端壳「付款通知书列表页」（`/m03/notices` · MOD-03）的离线断言 —— `§19` 批 4 **小轮①**。

⭐ 为什么有这个文件：这一页原来走**服务端渲染**（`app/mod03_notice/notice_page.py` 的
`render_notice_page`），页形态断言写在 `tests/test_notice_page.py` 里。旧页删除（授权 `D18`）⇒
**形态那半边改指新壳**（⛔ 判据不删）；实质（口径 / 取数 / 纯函数）仍留原处，待删页那一轮再归位。
⚠️ 其中 `ACC-PAY-LIST-001/001-09`（合计行）与 `001-07`（项目选择器共用件）是**绑定**判据点 ⇒
本文件把它们的**形态半边**接过来，删页时原文件里那半边随之作废、这条 claim 仍有着落 ✓。

⚠️ 与 `test_wired_m03_own.py`（归属）/ `test_wired_m03_print.py`（打印）分开：本文件只守**列表页形态**。
⚠️ 这里**只读壳源码**（`SHELL`）—— 不启动服务、不连库，与其它 `test_wired_*` 同款。
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛

_NT_THEAD_RE = re.compile(r"const NT_THEAD=`([\s\S]*?)`;")


def _nt_region() -> str:
    """本页渲染函数（`ntTb`）的正文 —— 从 `const NT_THEAD=` 到它的 `</div>\\`;` 收尾。

    ⚠️ 断言一律在这个**切片**里找，不到全文里撞 —— 否则 `10:rs=>N2(rs.reduce(` 这种片段
    会被别的表（如库存单据 `ivSums`）的同款写法**假命中**。

    ⚠️⚠️ 2026-09-28（`TAIL-164` · `P2-a` 拆件）：本页的**表头模板 `NT_THEAD`／`ntActCell`／
       `pjPanel`** 已随拆件搬进 `web/shell/proj.js`，而**渲染函数 `V.m03` 按计划 §23 留在
       `index.html`** ⇒ 两者在**合并后的壳**里不再相邻（`read_shell()` 的顺序 = `index.html` …
       `proj.js` …），一段 `find(i) → find(term, i)` 会把收尾找到**下一页**去。
       ⇒ 本函数取**两段并起来**：① 表头模板那一段（`proj.js`）② `V.m03` 切片那一段（`index.html`）。
       ⭐ 判据内容**一字未改**，只换取材方式（本仓既有做法：拆件后判据改指，⛔ 不是不许拆件）。
    """
    i = SHELL.find("const NT_THEAD=")
    assert i >= 0, "壳里找不到 `const NT_THEAD=`"
    j = SHELL.find("`;", i)                    # ⚠️ 收到 `NT_THEAD` **自己**的收尾（⛔ 别用 `</div>\`;` —— 拆件后会跑到别的件里）
    assert j > i, "找不到 `NT_THEAD` 模板的收尾"
    head = SHELL[i:j]
    k = SHELL.find("V.m03=()=>{")
    assert k >= 0, "壳里找不到 `V.m03` 切片"
    e = SHELL.find("</div>`;", k)
    assert e > k, "找不到 `V.m03` 渲染的收尾"
    return head + "\n" + SHELL[k:e]


def _nt_heads() -> list[str]:
    """本表表头（`NT_THEAD`）的**列标签**（勾选列由 `<input>` 渲染 ⇒ 它的标签是空串）。"""
    m = _NT_THEAD_RE.search(SHELL)
    assert m, "壳里找不到 `const NT_THEAD=`"
    raw = re.findall(r"<th[^>]*>([\s\S]*?)</th>", m.group(1))
    return [re.sub(r"<[^>]*>", "", h).strip() for h in raw]


# ---------------------------------------------------------------- 骨架与列


@acc()
def test_壳里列表页骨架齐备且表头18列():
    """旧页：五段骨架（`data-seg=tip/kpis/filter/data`）＋ **18 列**（勾选 + 16 数据 + 操作）。

    新壳同款（换了实现，没换要求）：口径说明（`details.tip`）→ 筛选栏（`.fbar`）→ 数据区
    （`.tw > table.dt`）→ 计数 pill ＋ 空态行；表头 = `NT_THEAD`，**18 列**、末列「操作」。
    ⚠️ 旧页的「指标区」那一段本就**是空的**（MOD-03 这页没有 KPI）⇒ 新壳直接不渲染，不算丢。
    """
    assert '<details class="tip">' in SHELL, "口径说明段没了"
    assert '<div class="fbar">' in SHELL, "筛选栏没了"
    assert '<div class="tw"><table class="dt" data-sort data-sort-key="m03:notices">' in SHELL, \
        "数据区没了（或没声明 data-sort-key）"
    heads = _nt_heads()
    assert len(heads) == 18, f"本表应 18 列（勾选 + 16 数据 + 操作），实得 {len(heads)}：{heads}"
    assert heads[-1] == "操作", f"末列应是「操作」，实得 {heads[-1]!r}"
    assert 'id="pickAllBox"' in SHELL, "勾选列（表头全选）没了"
    # 金额是千分位 2 位（与打印件的「零值留空」故意不同）—— 走全站唯一金额出口 `M()`
    assert "const M=n=>" in SHELL, "金额千分位出口 `M()` 没了"
    assert "(v<0?'-':'')+s.replace(" in SHELL, "千分位格式没了"


@acc()
def test_壳里年月走统一时间控件且单据日期是闭区间():
    """旧页：`name="period"` 用统一控件取值语法（`YYYY-MM`）＋「闭区间」只读显示。
    新壳：`tmBtn(...,{scope:'nt',modes:['月','跨月','年','全部']})` ＋ 只读的闭区间输入框。
    """
    assert "tmBtn('ntMonth',{scope:'nt',val:fNt.month,label:tmLabel(fNt.month)," \
           "modes:['月','跨月','年','全部']})" in SHELL, "单据年月没走统一时间控件（或丢了四档模式）"
    assert "对应单据日期（闭区间）" in SHELL, "「单据日期（闭区间）」这条只读显示没了"
    assert '<input class="inp" readonly style="width:198px" value="${esc(tmRange(fNt.month))}"' in SHELL, \
        "闭区间既要在、又要**只读**、且由区间出口 `tmRange()` 算"


# ---------------------------------------------------------------- 剔除 / 撤单的默认可见性


@acc()
def test_壳里有效行口径与计数三档():
    """旧页：默认视图**隐藏剔除与撤单行**，且右侧 pill 报「有效 N 条 / i8 已撤单 N 条」。

    新壳：有效行 = `ntLive`（非剔除，且「没撤单」或「撤单但有牵涉」——§4.2.7 的细化）；
    pill 报**四档**（显示 / 有效 / 剔除 / i8 已撤单），每档都由同一个口径出口算。
    """
    assert "const ntLive=n=>!n.excl&&(!ntVoid(n)||ntVoidJoint(n));" in SHELL, "有效行口径变了"
    reg = _nt_region()
    assert "显示 <b>${list.length}</b> 条" in reg, "「显示 N 条」计数没了"
    assert "有效 ${NO.filter(n=>ntLive(n)&&inM(n)).length} 条" in reg, "「有效 N 条」计数没了"
    assert "剔除 ${NO.filter(n=>n.excl&&inM(n)).length} 条" in reg, "「剔除 N 条」计数没了"
    assert "i8 已撤单 ${NO.filter(n=>ntVoid(n)&&inM(n)).length} 条" in reg, "「i8 已撤单 N 条」计数没了"


@acc("ACC-PAY-LIST-001", "001-11")
def test_汇总pill把撤单里有牵涉的单独报一档():
    """⭐ 2026-09-28（用户口径：「i8 删除付款通知书情况**非常少非常少**；但是可以做一个**保险**」）：
    常驻那句「i8 已撤单 N 条」看不出**其中有多少条仍有牵涉**（已挂付款流水 / 集采关联）——
    而这一类按 §4.2.7 **仍参与统计**、必须人先撤销付款 / 解绑才会退出。
    ⇒ 汇总 pill 要把它**单独报一档**（含悬停说明与去处），否则"保险"只在抓取回执里出现过一次。

    ⚠️ 能证伪：把 `ntVoidJoint(n)&&inM(n)` 那一档从 pill 里摘掉 ⇒ 本件必红。
    ⚠️ 只**加**一档，⛔ 不动既有四档文案（那四档由 `test_壳里有效行口径与计数三档` 继续守）。
    """
    reg = _nt_region()
    assert "ntVoidJoint(n)&&inM(n)" in reg, "汇总 pill 没给「有牵涉」单独一档"
    assert "条有牵涉" in reg, "「有牵涉」那一档没有看得见的字（用户认不出）"
    assert "仍参与统计" in reg, "没说明它为什么还在统计里（只说数字，用户不知道要不要管）"


@acc()
def test_壳里剔除来源分档不混作一谈():
    """旧页：切「分类 = 剔除」时按来源分档打标签（`人工批量剔除` / `规则命中` / `i8 已撤单`）。
    新壳：来源分档走唯一出口 `exrule`（`exclude_source === 'manual' ? 人工批量剔除 : 规则命中`）
    ＋ 行标签出口 `ntArchTag`；且说明里点明**规则命中任何情况下都不随人工恢复放回**（§4.2.2）。
    """
    assert "exrule: x.exclude_source === 'manual' ? '人工批量剔除' : '规则命中'," in SHELL, \
        "剔除来源分档出口没了"
    assert "const ntArchTag=n=>n.excl?tag('剔除','dg'):" in SHELL, "行标签出口 `ntArchTag` 没了"
    assert "任何情况下都不在此恢复" in SHELL, "「规则命中的剔除此处不恢复」这条口径没讲清"


# ---------------------------------------------------------------- 排序与空态


@acc("ACC-PAY-LIST-001", "001-13")
def test_壳里金额列按数值排序而不是按字符串():
    """旧页：金额列按**数值**排序（按字符串排 `"10,000.00" < "900.00"` 是错的）。
    新壳：`applySorts` 先判**列类型**（`_colType`）再按类型比较（`_cmp`）—— 不是裸字符串比较；
    合计行 / 草稿行走 pin 通道**钉表尾**、不参与排序（也不会被排序卷走）。
    """
    assert "const tp=_colType(vals);" in SHELL, "排序没先判列类型（金额列会按字符串排）"
    assert "_cmp(a.v,b.v,tp,st.d)" in SHELL, "排序没按列类型比较"
    assert "const _num=s=>{const t=String(s).replace(/[,¥%\\s]/g,'');" in SHELL, \
        "千分位 / 货币符没有统一剥离出口（转数会拿到 NaN）"
    assert "if(/\\bdraftrow\\b/.test(openTag)||/合计|总计|小计/.test(_plain(r))||tdc<ths.length) pin.push(r);" in SHELL, \
        "合计行 / 草稿行没走 pin 通道（会被排序卷进数据行里）"


@acc("ACC-PAY-LIST-001", "001-12")
def test_壳里空态行跨列数由表头派生且指出剔除行去哪看():
    """旧页：空态提示行的 `colspan` 由表头列数**派生**，且提示里给出「去哪儿找剔除了的行」。
    新壳同款：走**空态唯一出口** `EMPTYROW(thCount(NT_THEAD), …)`（跨列数由表头派生）＋ pill 里写明「切「分类 = 剔除」查看」。
    """
    assert "EMPTYROW(thCount(NT_THEAD)" in SHELL, "空态行的跨列数不再由表头派生"
    assert "当前筛选条件下没有付款通知书" in SHELL, "空态文案丢了"
    assert "（切「分类 = 剔除」查看）" in SHELL, "空态没告诉用户剔除了的行去哪儿找"


# ---------------------------------------------------------------- 时间口径与数据纯度


@acc()
def test_壳里默认月由后端给且付款域默认当月():
    """§9.2：付款域类表默认 = **当月**（材料报表类才是上月）。

    ① 新壳：默认月取后端给的 `fNt.month` —— ⛔ 前端**不自己算**「上月 / 当月」；
    ② 后端口径（归位前的**实质**）：`default_period("notice")` = 当月 且 ≠ `default_period("process")`。
    ⚠️ 这条是**回归断言** —— 此前把「统一时间控件的调用点标识」（`nt`）当口径键传进
    `default_period()`，于是落到"材料报表类 = 上月"分支 ⇒ 打开页面看到上月。
    """
    from app.core.period import default_period

    assert "tmBtn('ntMonth',{scope:'nt',val:fNt.month," in SHELL, "默认月不是由后端给的"
    assert default_period("notice") == date.today().strftime("%Y-%m"), "付款域默认月不是当月"
    assert default_period("notice") != default_period("process"), "付款域与材料报表类的默认月应当不同"


@acc("ACC-PAY-LIST-001", "001-14")
def test_壳里勾选框与标签由渲染注入而不是数据带的():
    """旧页：`/api/m03/notice-list` 的 items **不含 HTML**（勾选框是页面渲染时才注入的）。
    新壳同款：勾选框（`data-act="pick"`）与行标签（`ntArchTag`）都在**渲染时**拼；
    数据源是纯 JSON 接口 ⇒ 结构与数据分离这条没变。
    """
    assert '<input type="checkbox" class="chk" data-act="pick" data-id="${n.id}"' in SHELL, \
        "勾选框不是渲染时注入的"
    assert "ntArchTag(n)||" in SHELL, "分类列直接吃了数据里的 HTML（行标签应渲染时注入）"
    assert "notices: () => API.get('/api/m03/notice-list?period=')" in SHELL, \
        "数据源不是纯 JSON 接口"


# ---------------------------------------------------------------- 绑定判据点（`ACC-PAY-LIST-001`）


@acc("ACC-PAY-LIST-001", "001-09")
def test_壳里合计行只算非剔除行且无有效行时不给():
    """`ACC-PAY-LIST-001/001-09`（**结构**判据）：表内**合计行** —— 用户口径「求和一律落在表内」。

    ⚠️ 该用例原有 8 点**全是数据口径**、无一条讲页面结构 ⇒ 2026-09-17 补了这条结构判据
    （同一口径不能只做一半：`m04`/`m05`/`m08` 都传了 `summary=`）。

    新壳：`sumRows = list.filter(ntLive)`（**排除剔除行**）⇒ `sumRowOf(NT_THEAD, sumRows, …)`；
    5 个金额列（下标 10…14）**逐列**有合计（与原型 `sumRowOf` 同款）；无有效行（含「分类 = 剔除」
    的全剔除视图）⇒ `sumRows.length` 为 0 ⇒ **走空态行、不给合计**（不给一排 0 冒充"确实是 0"）。
    """
    reg = _nt_region()
    assert "const sumRows=list.filter(ntLive);" in reg, "合计行没排除剔除行"
    assert "sumRowOf(NT_THEAD,sumRows,{" in reg, "合计行不是由共用出口 `sumRowOf` 出的"
    for i in (10, 11, 12, 13, 14):
        assert f"{i}:rs=>N2(rs.reduce(" in reg, f"第 {i} 列（金额列）没有合计"
    assert "当前筛选结果中「非剔除」行的合计 —— 剔除行不计入" in reg, "没讲清「剔除行不计入」"
    assert "(sumRows.length?sumRowOf(NT_THEAD,sumRows,{" in reg, "无有效行时仍会给合计行"


@acc("ACC-PAY-LIST-001", "001-07")
def test_壳里项目选择器走共用件且label只一层():
    """`001-07`（加强）：项目选择器 = **全站共用件**（设计规则 §8.2 复用点：只有一个出口）。

    实测（`tools/audit/ui_parity.py`）曾发现实现里 `pjwrap` **恒为 0**：`m03` 用 `<select multiple>`、
    `m06`/`m07`/`m09` 各写一份 `.pjsel` ⇒ **7 页七个样**。新壳全部收敛到 `projPanel` 一个出口。
    """
    assert "const projPanel=c=>{" in SHELL, "全站共用的项目面板出口 `projPanel` 没了"
    assert "const pjPanel=()=>projPanel({list:PROJ_LIST,selected:()=>fNt.projs," in SHELL, \
        "本页没走共用件（自己又写了一份面板）"
    reg = _nt_region()
    assert '<div class="fi pjwrap"' in reg, "项目选择器没用原型类名（`.fi.pjwrap`）"
    assert reg.count("<label>项目（可多选）</label>") == 1, "label 只该出现一次（套两层就重复）"
    # ⭐ `#1`（2026-09-26）：展开态收进共用件注册表 `PJ_OPEN` ⇒ 判词不变、落点改成 `pjIsOpen(...)`
    #    （⛔ 这一处**不许**退回 `pjOpen` 裸变量 —— 那正是"靠自觉"的形态）。
    assert "${pjIsOpen('pj')?pjPanel():''}" in reg, "没渲染共用件面板（展开态该走 `PJ_OPEN`）"
