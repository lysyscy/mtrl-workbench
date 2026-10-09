"""`TAIL-117` 批次 2：**上屏文案里不许出现内部编号 / 开发话术**（守则 §2.5 / §3.1 / §3.3 / §3.6 / §6-1）。

⭐ 本件是**离线的一半**，另一半在真机 `tools/probe/_shell_text.py`（**㉕**：全站 17 屏走一遍，
   扫 DOM 文本与 `title` 属性）。两者分工写在下面，⛔ 别把同一条口径在两处各写一套。

**为什么离线只钉"精确墓碑"、不做通用源码扫查**（这是踩过之后的结论）：
  通用扫查必须分清"字符串字面量 vs 注释 vs 正则字面量 vs HTML 注释"——本件首版手写了个词法状态机，
  **当场被四样东西接连带偏**（`//` ★ 块注释 ★ HTML 注释 `<!-- -->` ★ 正则里的引号 `replace(/[&<>"]/g)`），
  报出 130 多条假阳性（把注释里的 `TAIL-94` 也当成"会显示给用户"）。
  ⇒ ⭐ **改用两条更稳的判法**：① 离线只钉**带上下文、只可能出现在界面上的整串**（如
  `>同步仓库名单（API-05）</button>`）——零假阳性；② "界面上到底有没有内部串"交给**真机**判（读 DOM 文本，
  所见即所得）。⛔ 别再回头写通用词法扫查（"更全面"是假收益，假阳性会让人把判据关掉）。

⚠️ 本件**不判** `§节号`：用户 2026-09-27 裁定 `B` —— 口径说明里**保留**《说明书》节号（"要查才看"的指路牌）。

⭐ **唯一的例外**（2026-10-01 `TAIL-209` 余项 ②）＝ `test_壳源码里不许有双层星号_加粗标记`：
它**是**一次源码扫查，但靶是**一个字面标记**（`**`）而不是"要判语义的内部编号"⇒ 没有判断成分
（为什么它不算"通用词法扫查"、以及为什么不会假阳性，写在**那条自己的 docstring** 里）。
"""

from __future__ import annotations

import re

from tests.acc_plugin import acc
from tests.shell_src import SHELL

#: `(禁用整串, 它是谁 / 为什么不许上屏)` —— ⚠️ 只收**带上下文、只可能出现在界面上**的串
TOMBSTONES: tuple[tuple[str, str], ...] = (
    (">同步仓库名单（API-05）</button>", "按钮上的 i8 接口代号 ⇒ 用户只认得「同步仓库名单」"),
    (">同步常用项目列表（API-06）</button>", "同上"),
    (">导出 Excel（R1）</button>", "按钮上的需求编号 ⇒ 用户只认得「导出 Excel」"),
    ("（API-07 · §4.6 / REQ-R6）", "按钮悬停里的接口/需求/节号三件套"),
    ("（原型演示）", "开发态话术（那条 toast 对用户没意义）"),
    ("模拟今天", "「模拟今天」是开发话术（用户只该看到「付款计划 X 号生效」与今天几号）"),
    ("原型态 · 数据为模拟值", "开发态状态牌 ⇒ 用户 2026-09-27 裁定 `B`：只给**没接通**的页如实标注"),
    ("最致命的陷阱", "给开发的实现铁律（用户不需要知道系统内部怎么防错）"),
    ("全局铁律（§9.8", "整张「实现与验收都按此」的开发者铁律表 ⇒ 不该摆在业务用户面前"),
    ("（TAIL-96）", "卡片副标题里的内部台账编号"),
    ("属 TAIL-04", "导出兜底提示里的内部台账编号"),
    ("strip_trailing_code()", "口径说明里的后端函数名"),
    ("ledSettle()", "说明页里的壳函数名"),
    # ⭐ 批次 0 细读（2026-09-27）：**辩解式口吻**不算「用户为什么需要它」（守则 §1.2）——
    #    `m15` 页脚原来写「为什么只有 2 个账号还要做这一页：不是为了分权限…」⇒ 那是**答给提问者的**，
    #    而用户要看的是「这页能看什么 / 能做什么 / 为什么有用」。
    ("为什么只有 2 个账号还要做这一页", "辩解式口吻（守则 §1.2）⇒ 改成「这页能看什么 / 能做什么」的用户视角"),
    # ⭐ 2026-09-28（`TAIL-124` · 裁定 2 的 `B` 案落地）：`m13` 整页原来是**工程 / 产品台账**
    #    （需求编号当卡头 ＋「一期 Non-goals 汇总（PRD 可直接引用）」＋ 两枚"点了只弹假数据"的演示按钮）。
    #    ⇒ 整页改成用户视角：**这些整串都不许回来**（守则 §1.1 用户需要感知吗 · §3.1 工程清单不上屏 ·
    #    §4.2 状态必须真实 · §5.5 「看着能点」的必须有符合预期的结果）。
    ("一期 Non-goals 汇总（PRD 可直接引用）", "把「我们不做哪些功能」的工程清单摆在用户面前（守则 §1.1 / §3.1）"),
    ("演示导出", "按钮写着「演示」⇒ 那是个**假按钮**（点了只是兜底提示，不会生成文件）"),
    ("演示删除确认框", "同上：弹窗里是**编造**的单号与金额（守则 §4.2）"),
    ("R1 · 全局导出 Excel", "需求编号 `R1` 当卡头（守则 §3.1）"),
    ("R2 · 全局数据删除", "同上（`R2`）"),
    ("R15 · 提醒与督办", "同上（`R15`）"),
    # ⭐ 2026-09-28（`TAIL-131`）：`m13` 的**页名**原叫「跨域能力」（内部叫法 ⇒ 守则 §2.5 用业务术语 /
    #    §3.3 黑话不入界面）—— 该页内容已改成"导出 / 删除 / 附件怎么用"（`TAIL-124`）⇒ **名实不符**：
    #    用户按名字找功能会找错（守则 §4.4）。⇒ 侧栏页名 ＋ 顶栏标题统一成「**导出与删除**」。
    ("['m13','跨域能力'", "侧栏页名又是内部叫法「跨域能力」（跟页里讲的事对不上）"),
    ("m13:'跨域能力'", "顶栏标题又是内部叫法「跨域能力」（同上）"),
    ("待接通（跨域能力）", "删除确认框里给用户的理由写着内部叫法（守则 §2.5：用业务术语）"),
    # ⭐ 2026-09-29（`A2` 逐页 · `TAIL-166`）：**批次 2 漏掉的一个** —— 审计清单 §四 `m03` ④ 点名
    #    「口径说明 13 条正文含 `DEV-P-02/04`、`request_id`、`A17 样本`」三样，前两样清了、
    #    `A17 样本` 一直留在界面上（用户不知道 A17 是什么 = 守则 §3.1 内部编号上屏）。
    ("（结算少于审批额，见 A17 样本）", "口径说明里的**内部样本编号**（用户查不到 A17 是哪个文件）"),
)


@acc("ACC-UI-SHELL-001", "001-11")
def test_上屏文案里这些内部串不许回来():
    """⭐ 逐条钉"这些**整串**不许出现在壳源码里"。

    ⚠️ 每条都是**带上下文的整串**（含 `</button>` / 全角括号＋编号）⇒ **不会误伤注释**
       （注释里写 `API-05` 是对的 —— 那是写给下一个人看的说明）。
    ⚠️ **能证伪**：把任一条改回去（如按钮写回 `同步仓库名单（API-05）`）⇒ 本件必红。
    ⚠️ 抓不到的东西（`DEV-*` / `ENT-*` / `OPEN-*` / 别的 `TAIL-*`）**大量出现在注释里**，
       离线没法可靠区分 ⇒ 那部分交给**真机 ㉕**（扫 DOM 文本，所见即所得）。
    """
    bad = [f"{s!r} —— {why}" for s, why in TOMBSTONES if s in SHELL]
    assert not bad, (
        "这些**内部编号 / 开发话术**又回到界面上来了（守则 §2.5 / §3.1 / §3.3 / §3.6）：\n"
        + "\n".join(bad))


@acc("ACC-UI-SHELL-001", "001-12")
def test_导入页的域自报文案要渲染加粗_不许满屏星号():
    """⭐ 守则 §3.1（技术标记不上屏）· `TAIL-105`（2026-09-28）。

    **事实**：域自报的那几句说明（`note` / `keep_note` / `memory` / `rule_note` / `field_list_hint`）里
    **本来就写着一堆 `**…**`**（= "这段最关键"的标记）；壳侧此前五处**一律 `esc`** ⇒ 用户在导入页看到的是
    **满屏星号**（`lgMd` 早就有了 —— 回执 / 区块 / 结果卡都走它，只有这一页漏在外面）。

    ⚠️ **能证伪**：把任一处改回 `esc(...)`（或删掉那个 `lgMd(...)`）⇒ 本件必红。
    ⚠️ 判法 = **精确整串**（带变量名，不会误伤注释里提到这些字段的地方）。
    """
    for bad in ("esc(sch.note)", "esc(sch.keep_note)", "esc(IMP.memory)",
                "esc(sch.rule_note)", "esc(hint)"):
        assert bad not in SHELL, (
            f"导入页的域自报文案又只 `esc` 了：{bad!r} ⇒ 用户会看到满屏 `**`（守则 §3.1）")
    for good in ("lgMd(sch.note)", "lgMd(sch.keep_note)", "lgMd(IMP.memory)",
                 "lgMd(sch.rule_note)", "lgMd(hint)"):
        assert good in SHELL, f"找不到该走的渲染出口：{good!r}（它被改名 / 被删了？）"


#: ⭐ 说明块（`class="tip"`）的估算字数上限（**剥掉 `${…}` 与标签之后**）——
#:   与真机 ㉖ 的 200 字**同一条线**（同一条口径：守则 §3.4 / §5.9「说明要短」）。
TIP_LIMIT = 200
_TAG = re.compile(r"<[^>]+>")
_JSX = re.compile(r"\$\{[\s\S]{0,600}?\}")
#: ⭐ **折叠区不计**（与真机 ㉖ 的口径一字不差：「上限 200 字 · ⚠️ 折叠区不设上限」）——
#:   ⛔ 别把 `<details>` 里的内容算进"默认展开"的字数里（那样 `m07` 会假红：它块内挂着一个逐列口径）。
_DETAILS = re.compile(r"<details[\s\S]*?</details>")


def _tip_len(s: str) -> int:
    """**渲染后**的估算字数（与真机 ㉖ 逐字同口径）：剥 `${…}` · 剥折叠区 · 剥标签 · 剥 `**` · 空白不计。"""
    return len(re.sub(r"\s+", "", _TAG.sub("", _DETAILS.sub("", _JSX.sub("…", s))).replace("**", "")))


def _tip_blocks() -> list[tuple[str, int, int, str]]:
    """壳里**每一个** `class="tip"` 块 ⇒ `(件名, 行号, 估算字数, 开头 40 字)`。

    ⚠️ 三样都是刻意这么做的：
      ① **边界 = 配对的 `</div>`**（数嵌套）—— ⛔ 不用"到本行末尾"那种近似（会把**后面那块**粘进来 ⇒ 估出假高，
         我在量测阶段就踩过：`m07` 明明压过、却被粘上后一块估成 310 字）；
      ② **剥 `${…}` 与标签** —— 模板里的 JS 表达式**不是给用户读的字**（`${a.map(...)}` 计进去会失真）；
      ③ **逐件读源码**（`part_paths` / `parts_text`）—— 因此报出来的是**件名:行号**，拿着就能改。
    """
    from tools.audit.shell_source import parts_text

    out: list[tuple[str, int, int, str]] = []
    for name, text in parts_text():
        for m in re.finditer(r'<div class="tip', text):
            seg, depth, i = text[m.start():m.start() + 4000], 0, 0
            while i < len(seg):
                op, cl = seg.find("<div", i), seg.find("</div>", i)
                if cl < 0:
                    break
                if 0 <= op < cl:
                    depth += 1
                    i = op + 4
                else:
                    depth -= 1
                    i = cl + 6
                    if depth == 0:
                        seg = seg[:i]
                        break
            txt = re.sub(r"\s+", "", _TAG.sub("", _DETAILS.sub("", _JSX.sub("…", seg))))
            out.append((name, text[:m.start()].count("\n") + 1, len(txt), txt[:40]))
    return out


@acc()
def test_说明块都不超长_弹窗也在内():
    """⭐ `TAIL-209`（2026-10-01）：**说明块的机器眼要罩住弹窗**（守则 §3.4 / §5.9）。

    ⚠️ **为什么必须补这一条**：真机 `㉖`（`tools/probe/_shell_text.py`）的靶是
       `#view .tip`（**页内**）—— 而**弹窗不在 `#view` 里** ⇒ 弹窗那 50 多处说明
       **没有机器眼**（只会越写越长、且**没人会红**）。本仓同族的病犯过多次
       （判据的靶没覆盖到的地方＝"悄悄长回去"）。⇒ 这里补上**离线**这一半。
    ⚠️ **为什么不改真机**：真机要"逐个打开弹窗"才能看到它们 —— 50 多个弹窗按顺序点开，
       既慢又脆（哪一处改了个 data-act，探针就瞎了）⇒ **离线兜住"越写越长"这个主要风险**
       （判分口径：剥掉 `${…}` 与标签后 **> 200 字**）。
    ⚠️ **审视角**（用户 2026-10-01 口径）：本页的读者是**已经清楚业务流程的人**（科室 2 人）
       ⇒ 判"留还是删"只问一句：**这句是"系统特有的行为/后果"（指导），还是"业务常识"（干扰）？**
       ⛔ 业务常识（如"欠款 = 其他支出金额 − 付款"）不必解释；⭐ 系统特有行为
       （"重抓重导不覆盖手录值" / "有非法值则整批不写"）**必须留**。
    ⚠️ 能证伪：把任一说明块写长（> 200 字）⇒ 本件必红。
    """
    over = [f"{n}:{ln} {c} 字 · {head}…" for n, ln, c, head in _tip_blocks() if c > TIP_LIMIT]
    assert not over, (
        f"这些说明块超过 {TIP_LIMIT} 字（剥标签与 `${{…}}` 后的估算）—— 页内的与弹窗的**同一条线**：\n  "
        + "\n  ".join(over))


@acc()
def test_壳源码里不许有双层星号_加粗标记():
    """⭐ `TAIL-209`（2026-10-01 · 余项 ②）：**壳自己拼的 HTML 里不许出现 `**`**（守则 §3.1）。

    **为什么它算"上屏文字"**：`**X**` 在本仓**只有 `lgMd` 会渲染**（`legacy.js`，给**后端自报文案**用）；
    壳自己拼的串走的是**直插** —— `modal({body})`（`base.js` 直接 `innerHTML`）· `toast(msg)`（`innerHTML`）
    · 拼出来的卡片 HTML ⇒ 那些 `**` **原样上屏** = 用户看到满脸星号（守则 §3.1「技术标记不上屏」）。
    实测：壳里曾有 **49 行 / 7 件**（计划 §13.6「修订 13」与审计件 §23 只记了 **6 处** ——
    那是只扫 `class="tip` 块量出来的，漏了块外的：`<span>` / `title` / `placeholder` / `toast` / `esc()` 文案）。

    ⚠️ **为什么这条敢做"源码扫查"**（本件头部刚说过"别再写通用词法扫查"，这不是自相矛盾）：
      ① 靶是**一个字面标记**（`**`），不是"内部编号 / 黑话"那种**要判语义**的东西 ⇒ 没有判断成分；
      ② 剥注释用**共用件** `tools/audit/shell_source.py::strip_comments`（**保留换行** ⇒ 行号不错位 ·
         避开 `https://` · 连 HTML 注释一起剥）—— 它的实际输出验证过：改之前报出的就是那 **49 处真位置**、
         **0 条注释假阳性**（注释里 Markdown 加粗极多，是第一版手写词法机栽跟头的地方）；
      ③ 实测壳里**没有** `a ** b` 这类幂运算（全仓 0 处）⇒ 不必留白名单。
    ⚠️ **能证伪**：往任一壳件里写一个 `**x**`（哪怕只在 `title` 属性里）⇒ 本件必红。
    ⚠️ **真机那一半（㉙）兜不住这些**：它的靶是 `#view` 正文 ⇒ 弹窗、`title` 属性、`toast` 全在它视野外。
    """
    from tools.audit.shell_source import parts_text, strip_comments

    bad = [
        f"{name}:{i}  {line.strip()[:110]}"
        for name, text in parts_text()
        for i, line in enumerate(strip_comments(text, html=name.endswith(".html")).splitlines(), 1)
        if "**" in line
    ]
    assert not bad, (
        "壳源码里出现了 `**`（加粗标记）—— 壳自己拼的 HTML 是**直插上屏**的"
        "（`modal` / `toast` / 卡片串），不会渲染成粗体 ⇒ 用户看到的是满脸星号（守则 §3.1）：\n  "
        + "\n  ".join(bad)
        + "\n⇒ HTML 串改成 `<b>…</b>`；`title=` / `placeholder=` 这类**属性值**、以及走 `esc()` 的文案，"
          "只能**去掉星号**（`<b>` 在那些位置也原样显示）。"
    )


#: ⭐⭐ `TAIL-209`（2026-10-01 · 余项 ②）：**"工程代号"不许出现在用户可见串里**（守则 §2.5 / §3.1）。
#: 形态**只认这几种**（每条都附"为什么它不会误伤"）：
_CODE_SHAPES: tuple[tuple[str, str], ...] = (
    (r"（R\d+）", "需求编号 —— 真例：按钮「从付款域引用（R8）」"),
    (r"（D\d+）", "决策代号 —— 真例：「（决策 D9）」"),
    (r"（决策\s?[A-Z]?\d+", "决策代号（带「决策」二字的写法）—— 真例：「（决策 2）」"),
    (r"DEV-[A-Z]-\d+", "工程决定代号 —— 真例：`DEV-J-01` / `DEV-P-07`"),
    (r"（ENT-\d+）", "实体编号 —— 真例：「发票子表（ENT-07）」"),
    (r"（API-0\d）", "接口代号（**只认带全角括号的** —— 数据表那种 `api:'API-01'` 写法不管）"),
    (r"链路\s?[ABC]", "内部叫法 —— 真例：卡头「待人工建档（链路 A · 多仓库）」"),
)


@acc()
def test_用户可见串里不许出现工程代号():
    """⭐ `TAIL-209`（2026-10-01 · 余项 ②）：**把"工程代号混进用户可见文字"这一类交给机器眼**。

    ⚠️ **为什么必须机器判**：这一类的清理方式经历过**三轮"扫一个面就冒一批"** ——
      弹窗说明块 → 按钮 / 弹窗内 `span` / 卡头 → …… ⛔ 每轮手工捞都只捞到当时那个面，
      漏掉的面**照样上屏且没人会红**（守则 §3.1「技术实现细节不上屏」/ §2.5「用业务术语」）。
      ⇒ 结论：**给它一把机器眼**，而不是继续一轮轮手工扫。

    ⚠️ **为什么这次敢做源码扫查**（与 `**` 那条同理）：靶是**几种可枚举的字面形态**，
      剥注释走**共用件** `tools/audit/shell_source.py::strip_comments`（保留换行 ⇒ 行号不错位）；
      ⛔ 不做"黑话"那种**要判语义**的扫描（本件头部写着：那类假阳性会让人把判据关掉）。

    ⚠️ **为什么不会误伤**（三条，都是实测过的）：
      ① 注释**先被剥掉** —— 壳里 `DEV-*` / `链路 X` / `决策 N` 绝大多数**只活在注释里**（留痕用）；
      ② 数据表那种写法（`{label:'库存单据明细表', api:'API-03'}`）**不带全角括号** ⇒ 不命中
         （`API-0\\d` 那条特意要求全角括号；`MOD-xx` 侧栏编号是**用户 2026-09-28 裁定要留的**，⛔ 不在表里）；
      ③ 壳里**没有** `a ** b` 这类幂运算，也没有别的正当写法会撞上这几种形态（改前实测 0 假阳性）。

    ⚠️ **能证伪**：往任一壳件的**字符串**里写 `（R99）` ⇒ 本件必红（`tools/oneoff/_tail209_mark_proof.py` 证）。
    """
    from tools.audit.shell_source import parts_text, strip_comments

    bad: list[str] = []
    for name, text in parts_text():
        clean = strip_comments(text, html=name.endswith(".html"))
        for i, line in enumerate(clean.splitlines(), 1):
            for pat, why in _CODE_SHAPES:
                if re.search(pat, line):
                    bad.append(f"{name}:{i}  [{why}]  {line.strip()[:100]}")
                    break
    assert not bad, (
        "壳的用户可见文字里出现了**工程代号**（守则 §2.5 / §3.1：用户只认业务说法）：\n  "
        + "\n  ".join(bad)
        + "\n⇒ 直接删掉代号（⛔ 别改判据）；`§节号`（《说明书》节号，2026-09-27 裁定可留）与"
          "侧栏的 `MOD-xx` 编号**不在此列**。"
    )


#: ⭐ 第二轮（2026-10-01 · 审计件 §四 批 9）：**悬停文案也要有上限**。
#: ⚠️ 上限**沿用 ㉖ 的同一个数**（200）⇒ ⛔ 不另立新阈值（守则 §3.4 / §5.9）。
#: 为什么单列：悬停文案是**没有机器眼**的那一面里最大的一块（实测 151 处 · 约 5,108 字），
#:   而它**照样是给用户看的**（鼠标放上去就读）⇒ 不守 = 迟早长回去（同"弹窗没有机器眼"那一族）。
_TITLE_ATTR = re.compile(r'title="([^"$]{20,})"')
_TITLE_JS = re.compile(r"\.title\s*=\s*'([^'$]{20,})'")


@acc()
def test_悬停文案也不超长():
    """⭐ 第二轮（2026-10-01）：**悬停文案（`title`）的机器眼**（守则 §3.4 / §5.9）。

    ⚠️ 为什么补它：第一轮守住了**说明块**（页内 ＋ 弹窗）与**域自报文案**，但**悬停文案没人守** ——
       而它是"没有机器眼的面"里最大的一块（实测 **151 处 · 约 5,108 字**，最长 102 字）。
       它与说明块**同一条口径**：默认不是"展开"的，但鼠标一放就读 ⇒ 太长同样是"同屏塞满"。
    ⚠️ 口径与 ㉖ **逐字一致**：剥 `${…}` 与标签、剥 `**`、空白不计，上限 **200**（⛔ 不另立新数）。
    ⚠️ **能证伪**：把任一 `title="…"` 写成 220 字 ⇒ 本件必红（自证见 `tools/oneoff/_tail209_mark_proof.py`）。
    """
    from tools.audit.shell_source import parts_text, strip_comments

    over: list[str] = []
    for name, text in parts_text():
        for i, line in enumerate(strip_comments(text, html=name.endswith(".html")).splitlines(), 1):
            for m in _TITLE_ATTR.finditer(line):
                txt = _tip_len(m.group(1))
                if txt > TIP_LIMIT:
                    over.append(f"{name}:{i}  {txt} 字  {m.group(1)[:50]}…")
            for m in _TITLE_JS.finditer(line):
                txt = _tip_len(m.group(1))
                if txt > TIP_LIMIT:
                    over.append(f"{name}:{i}  {txt} 字  {m.group(1)[:50]}…")
    assert not over, (
        f"这些**悬停文案**超过 {TIP_LIMIT} 字（剥 `${{…}}` 与标签后的估算，与 ㉖ 同一条线）：\n  "
        + "\n  ".join(over))


#: ⭐ 第二轮（2026-10-01 · 批 9）：**工程侧的名字不许上屏**。
#: 形态（都是"只可能出现在我们自己的文件里"的东西）：
_DOC_SHAPES: tuple[tuple[str, str], ...] = (
    (r"ops[/\\]", "工程侧底账目录（`ops/…` / `ops\\…`）"),
    (r"见\s*ops", "同上（「见 ops …」这种写法）"),
    (r"\.codebuddy", "治理层目录名"),
    (r"artifacts[/\\]", "产物目录名"),
    (r"tools[/\\]", "工具目录名"),
    (r"\.md\b", "内部文档扩展名"),
)


_APP_DIR = __import__("pathlib").Path(__file__).resolve().parents[1] / "app"


def _backend_user_strings() -> list[tuple[str, int, str]]:
    """后端 `app/**/*.py` 里**会拼进回执 / 报错 / 说明**的字符串常量 ⇒ `(件, 行号, 值)`。

    ⚠️ 三条边界（都是**量出来的**，⛔ 别放宽也别无谓收紧）：
      ① **跳过"裸字符串语句"**（module / class / function 的 docstring ＋ **属性 docstring** ＋
         拿字符串当注释的老写法）—— 那些值**无处可去**，不是上屏文字
         （实测：不收这一条，会在 `mod03_notice/service.py` 的 `files:` 属性文档上**假阳一次**）；
      ② **代号被反引号包住 ⇒ 不算** —— 本仓「工程侧笔记」一律用反引号包标识符
         （真例：守卫表 `FORBIDDEN_TEXTS` 的墓碑值「（业务上无此数据，`DEV-R-03`）」—— 那张表本身就是"这些串**不许出现**"）；
         而用户面上写代号**从不加反引号**（清掉的那 9 处无一例外）；
      ③ 注释 **AST 根本看不见** ⇒ 不用管。
    """
    import ast
    out: list[tuple[str, int, str]] = []
    for p in sorted(_APP_DIR.rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        skip: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Constant, ast.JoinedStr)):
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                        skip.add(id(sub))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
                out.append((p.relative_to(_APP_DIR.parent.parent).as_posix(), node.lineno, node.value))
    return out


@acc()
def test_后端的用户可见串里也不许出现工程代号():
    """⭐ `TAIL-211`（2026-10-01）：**把"工程代号混进用户可见文字"这一类也罩住后端**（守则 §2.5 / §3.1）。

    ⚠️ **为什么必须补**：本件上面那几条源码扫查（`**` / 工程代号 / 工程侧文件名）**靶全是壳源码** ——
       而后端**同样**会把串拼上屏（域自报文案 / `MustReportError` / 回执块标题）。
       `TAIL-210` 第 3 批改词那轮当场撞到 **3 例**（`（API-06）` · `链路 A` · `（M5 未开工）`）：
       前两例就在后端 —— **已顺手清掉，但当时没有任何判据兜住** ⇒ 这就是本条的来历。
    ⚠️ **立判据当场又抓出 9 处**（量法 = `tools/oneoff/_text_ctx9.py --codes`）：`（决策 1 兜底）` ·
       `（决策 2：…）`×2 · `（DEV-P-04）` · `（链路 A）` · `（API-05）`×2 · `（R1）` ·
       以及 `report_export/resources.py` 那句给用户看的 `_RETRY` 里写着的 `ops/模板法导出-实测结论.md`
       ＋ 交付面 / 仓内两条路径（清法 = `tools/oneoff/_tail211_codes.py`）。
    ⚠️ **能证伪**：往任一后端**字符串**里写 `（R99）` ⇒ 本件必红（自证见 `tools/oneoff/_tail209_mark_proof.py` 的 `T5`）。
       ⛔ 写进**注释 / docstring**、或把代号**用反引号包住** ⇒ 不红（那两种都是工程侧记法）。
    """
    bad: list[str] = []
    for rel, lineno, v in _backend_user_strings():
        stripped = re.sub(r"`[^`]*`", "", v)          # 反引号段 = 工程侧记号 ⇒ 不算
        for pat, why in _CODE_SHAPES + _DOC_SHAPES:
            if re.search(pat, stripped):
                bad.append(f"{rel}:{lineno}  [{why}]  {stripped[:90]}")
                break
    assert not bad, (
        "**后端**拼给用户的串里出现了**工程代号 / 工程侧文件名**（守则 §2.5 / §3.1）：\n  "
        + "\n  ".join(bad)
        + "\n⇒ 直接删掉它（⛔ 别改判据）；`§节号` 与 `MOD-xx` 编号**不在此列**。"
    )


@acc()
def test_用户可见串里不许出现工程侧文件名():
    """⭐ 第二轮（2026-10-01 · 批 9）：**内部的目录名 / 文档名不许上屏**（守则 §3.1 技术实现细节不上屏）。

    **为什么**：真例（2026-10-01 审计挖出）—— 抓取回执里曾写着
    「先怀疑**幂等**范围（**见 ops 实测结论**）」：`ops/` 是**我们工程侧底账的目录名**、`幂等`是开发术语，
    而整句是**写给排障者的** ⇒ 用户拿到它**不知道该干什么**（守则 §3.7 要求"人话 ＋ 下一步"，它两条都不满足）。
    ⚠️ 靶是**几个只可能属于我们自己的名字**（`ops/` · `.codebuddy` · `artifacts/` · `tools/` · `.md`）⇒
       剥注释后**实测 0 假阳性**（壳里它们只活在注释里）。
    ⚠️ **能证伪**：往任一壳件的字符串里写 `见 ops/README.md` ⇒ 本件必红。
    """
    from tools.audit.shell_source import parts_text, strip_comments

    bad: list[str] = []
    for name, text in parts_text():
        clean = strip_comments(text, html=name.endswith(".html"))
        for i, line in enumerate(clean.splitlines(), 1):
            for pat, why in _DOC_SHAPES:
                if re.search(pat, line):
                    bad.append(f"{name}:{i}  [{why}]  {line.strip()[:100]}")
                    break
    assert not bad, (
        "壳的用户可见文字里出现了**工程侧的文件 / 目录名**（守则 §3.1）：\n  " + "\n  ".join(bad)
        + "\n⇒ 删掉它（要解释就写用户能懂的话 ＋ 下一步，⛔ 别把我们的文件名甩上去）。"
    )


#: ⭐ `TAIL-212`（2026-10-01）：**异常类名 / 原始报错串只许进运行日志**（守则 §3.1 / §3.7）。
#: ⚠️ **唯一例外** = **执行记录**（`error_message=`）—— 它是排障面，判据钉着"失败要留下原因"
#:    （`test_acc_inv_fetch`：`"boom" in rec.error_message`）。
_EXC_TECH = ("type(exc).__name__", "type(e).__name__")
_EXC_ALLOW = ("logger.", "log_exc(", "human_reason(", "error_message=")
_EXC_EXEMPT = {_APP_DIR / "core" / "errors.py"}     # 技术串的**出口**自己（`log_exc` 就写在那儿）


def _cached_source_segment(lines: list[bytes], node) -> str:
    """AST列号按UTF-8字节切片；每件预拆源码，保持get_source_segment语义。"""
    if (getattr(node, 'end_lineno', None) is None or
            getattr(node, 'end_col_offset', None) is None or not hasattr(node, 'lineno')):
        return ""
    a, b = node.lineno - 1, node.end_lineno - 1
    if a == b:
        return lines[a][node.col_offset:node.end_col_offset].decode('utf-8')
    return (lines[a][node.col_offset:] + b''.join(lines[a + 1:b]) +
            lines[b][:node.end_col_offset]).decode('utf-8')


def _exception_class_hits(src: str) -> list[int]:
    """原扫描范围和逐行例外不变，只把重复全源码拆行移出节点循环。"""
    import ast
    lines = src.splitlines()
    tree = ast.parse(src)
    # 只按Python解析器的CR/LF拆行，FF与Unicode分隔符仍留在源码行里。
    source_lines = [m.group().encode('utf-8') for m in re.finditer(r'[^\r\n]*(?:\r\n|\n|\r|$)', src)]
    skip: set[int] = set()
    for node in ast.walk(tree):
        # 裸表达式语句（值**无处可去**）⇒ 与 `_backend_user_strings()` 的第 ① 条同口径，跳过
        # ⚠️ 要连**子孙一起跳** —— 只跳 `node.value` 的话，里面那个 `type(exc).__name__`
        #    节点仍会被 `walk` 单独访问到（2026-10-01 自证 `③″` 当场抓到：假红）。
        if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
            skip.add(id(node))            # ⚠️ 连**语句节点自己**一起跳（`Expr` 的 segment 就是整句）
            for sub in ast.walk(node.value):
                skip.add(id(sub))
    hit: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant):        # 普通字符串 / docstring：值里没有运行期信息
            continue
        if id(node) in skip:
            continue
        seg = _cached_source_segment(source_lines, node)
        if not any(k in seg for k in _EXC_TECH):
            continue
        a = node.lineno
        b = node.end_lineno or a
        span = "\n".join(lines[a - 1:b])
        if any(k in span for k in _EXC_ALLOW):
            continue
        hit.add(a)
    return sorted(hit)


@acc()
def test_用户可见串里不许拼异常原文():
    """⭐⭐ `TAIL-212`（2026-10-01）：**异常类名 / 原始报错串不许拼进用户可见文案**（守则 §3.1 / §3.7）。

    **为什么补**：真例（同日"技术串"收尾一路撞到）—— `mod02_i8/client.py` 把
    「i8 接口 `<路径>` 返回 HTTP `<状态码>`：`<响应原文前 200 字>`」拼进异常**直接上屏**；
    `fetch_task.degrade*` 把 `RuntimeError: …` 拼进回执；`report_export/resources.py` 把模板
    **文件路径 ＋ 两条 SHA256** 塞进报错 ⇒ 用户拿到它**不知道该干什么**（§3.7 要"人话 ＋ 下一步"，它两条都不满足）。
    实测这一类在 `backend/app` 还余 **23 处 / 15 件**（量法 = 搜 `type(exc).__name__`）。

    ⚠️ **判法**（三条都是**刻意**这么定的）：
      ① 走 **AST**（表达式节点的 `get_source_segment`）⇒ **注释与 docstring 天然看不见**
         —— 本件头部那条教训（手写词法状态机被注释带偏、报出 130 多条假阳性）在这儿同样适用；
      ② **逐行白名单**：`logger.` / `log_exc(` / `human_reason(` ＝ 技术串**该去的地方**；
         `error_message=` ＝ **执行记录**（排障面，有判据钉着"要有原因"）；
      ③ 出口件 `app/core/errors.py` 自己豁免（`log_exc` 的实现就在那儿，天经地义）。
    ⚠️ **能证伪**：在任一**非日志、非 `error_message`**的行写 `f"失败：{type(exc).__name__}: {exc}"` ⇒ 本件必红；
       ⛔ 写进**注释 / docstring** ⇒ 不红（自证见 `tools/oneoff/_tail209_mark_proof.py` 的 `T6`）。
    """
    bad: list[str] = []
    for p in sorted(_APP_DIR.rglob("*.py")):
        if p in _EXC_EXEMPT:
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(_APP_DIR.parent.parent).as_posix()
        bad += [f"{rel}:{ln}" for ln in _exception_class_hits(src)]
    assert not bad, (
        "**用户可见的串**里拼了**异常的类名 / 原文**（守则 §3.1 细节不上屏 / §3.7 人话＋下一步）：\n  "
        + "\n  ".join(bad)
        + "\n⇒ 改走 `app/core/errors.py` 的 `human_reason(人话前缀, exc)`"
          "（它返回人话 ＋ 下一步，细节自己记进运行日志）；"
          "⛔ `error_message=`（执行记录）是唯一例外。"
    )


#: ⭐⭐ `TAIL-220`（2026-10-02 · **架构走查候选③**）：**原始异常正文**（`{exc}`）拼进用户可见串 ——
#: 上面那条**只挡类名**（`type(exc).__name__`）⇒ 这一类**落在它射程之外**（＝"有判据 ≠ 这一类被管着"）。
#: ⚠️ **口径（判据的边界，写在这里免得含糊）**：
#:   · **放行** = 该 `except` 的类型是「**我们自己的**」异常（见 `_EXC_OURS`）—— 本仓约定：`AppError` 家族
#:     与 `MoneyError` / **我们主动抛的** `ValueError`，其 `message` **必须是人话**
#:     （`core/errors.py` 头部那句「`message` 会原样呈给用户，务必写清"发生了什么"」）⇒ 把人话再拼一次**不算技术串**；
#:   · **报红** = 该 `except` 是**外来的**（`Exception` / `JSONDecodeError` / `ArithmeticError` / `OSError`…）
#:     ⇒ 原文（英文、带路径 / 行列号）直接甩给用系统的人看，两条都不满足 §3.7。
#:   ⚠️ **已知边界**：`except ValueError` 一律按"我们的"放行 —— 哪天把**库抛的** `ValueError` 拼上屏，
#:     本判据**看不见**（机器判不出"谁抛的"）⇒ 那一层靠 review；
#:     ⛔ 但**别为了堵这个把判据放宽成"一律报红"** —— 会当场假红 8 处人话（2026-10-02 量过，见
#:     `work/10-designs/设计-架构候选3-异常原文-20261002.md`）。
_EXC_OURS = ("MustReportError", "MoneyError", "MRE", "AppError", "NotConfiguredError",
             "ExternalServiceError", "DataConflictError", "DataIntegrityError", "ValueError")
#: 异常惯用变量名（只认这些 —— 免得把别的同名变量算进来）
_EXC_VARS = {"exc", "e", "err", "error", "_exc"}


def _except_map(tree) -> dict:
    """行号 ⇒ `(异常类型名, as 变量名)`；⚠️ **嵌套 `except` 内层赢**（按覆盖范围**从小到大**写入 ⇒ 后写的覆盖先写的）。"""
    import ast

    spans: list[tuple[int, int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        tname = ast.unparse(node.type) if node.type is not None else "Exception"
        start = node.lineno
        end = max((getattr(n, "end_lineno", None) or getattr(n, "lineno", None) or start
                   for n in ast.walk(node)), default=start)
        spans.append((end - start, start, tname, node.name or ""))
    out: dict = {}
    for size, start, tname, var in sorted(spans):
        for ln in range(start, start + size + 1):
            out[ln] = (tname, var)
    return out


@acc()
def test_用户可见串里不许拼异常正文():
    """⭐ `TAIL-220`（2026-10-02）：**原始异常正文**不许拼进用户可见文案（守则 §3.1 / §3.7）。

    **为什么补**：架构走查**候选③** + `TAIL-188` 清点这条线撞出来的 —— 上面那条判据（`TAIL-212`）的靶是
    `type(exc).__name__`（**类名**），而**正文**（`{exc}`）一路没人管。实测（2026-10-02）真该改的有 5 处：
    `import_kit/readers.py` 四处（`xlrd` / `openpyxl` 的库异常）＋ `report_export/setl_export.py`
    （XML 解析异常，**而且那条 `problems` 会跟着报错上屏**）。
    ⚠️ 另有一处是**量法误报**、判据必须放行的：`mod06_proc/router.py` 的 `except ValueError`
    —— `mech_ui.parse_mech_values` 抛的是**我们自己写的人话**（`「辅材」不是数字：'abc'`）。

    ⚠️ **能证伪**：任一处 `except Exception as exc:` 里写 `f"失败：{exc}"` ⇒ 本件必红；
       而写在 `except MustReportError` / `error_message=` 那一行 ⇒ **不红**（自证 = `tools/mut/_归档-20261009/_mut_exctext.py`）。
    """
    import ast
    import re as _re

    bad: list[str] = []
    for p in sorted(_APP_DIR.rglob("*.py")):
        if p in _EXC_EXEMPT:
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        lines = src.splitlines()
        tree = ast.parse(src)
        hof = _except_map(tree)
        skip: set[int] = set()
        for node in ast.walk(tree):
            # 裸表达式语句（值**无处可去**）⇒ 与上面那条同口径，跳过（含子孙）
            if isinstance(node, ast.Expr) and not isinstance(node.value, ast.Constant):
                skip.add(id(node))
                for sub in ast.walk(node.value):
                    skip.add(id(sub))
        for node in ast.walk(tree):
            names: set[str] = set()
            if isinstance(node, ast.JoinedStr):                     # f"…{exc}…"
                for part in node.values:
                    if isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name):
                        names.add(part.value.id)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "format":                 # "…{0}".format(exc)
                names |= {kw.value.id for kw in node.keywords if isinstance(kw.value, ast.Name)}
                names |= {a.id for a in node.args if isinstance(a, ast.Name)}
            names &= _EXC_VARS
            if not names or id(node) in skip:
                continue
            a, b = node.lineno, node.end_lineno or node.lineno
            tname, hvar = hof.get(a, ("", ""))
            if hvar not in names:                 # ⛔ 不是"这个 except 的那个变量"⇒ 不算
                continue
            parts = set(_re.findall(r"[A-Za-z_][A-Za-z_0-9]*", tname))
            if parts and all(x in _EXC_OURS for x in parts):        # 我们自己的异常 ⇒ message 本就是人话
                continue
            span = "\n".join(lines[a - 1:b])                        # ⚠️ 查**整行 span**（与上面那条同口径）
            if any(k in span for k in _EXC_ALLOW):
                continue
            bad.append(f"{p.relative_to(_APP_DIR.parent.parent).as_posix()}:{a}  [except {tname}]")
    assert not bad, (
        "**用户可见的串**里拼了**原始异常正文**（守则 §3.1 细节不上屏 / §3.7 人话＋下一步）：\n  "
        + "\n  ".join(bad)
        + "\n⇒ 改走 `app/core/errors.py` 的 `human_reason(人话前缀, exc, next_step=…)`"
          "（返回人话 ＋ 下一步，细节自己进运行日志）；"
          "\n⚠️ 若这一处的异常**本来就是我们自己抛的人话**（`AppError` 家族 / `MoneyError` / 我们抛的 "
          "`ValueError`）⇒ 它该被放行 —— 那种情形**修判据、别改代码**（见本件 `_EXC_OURS`）。"
    )
