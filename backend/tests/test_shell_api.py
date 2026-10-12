"""壳**语义口径**（`tools/audit/shell_api.py`）的判据 —— ⭐ `TAIL-219` 批 1（2026-10-03）。

## 守什么

壳原本只有一坨**纯文本**（`SHELL`）⇒ 13 件各自写"从字符串里按字面剪一段"的剪刀（实测 16 把）。
本批立了一扇**按名字取**的窗（`page_slice` / `func_body` / `act_entry` / `const_obj`）。
⇒ 这里守三件事，**每一件都是"会做错的后果"**：

1. **取得到、且只有一套算法** —— 同一页/同一函数，不许两处各算一遍（那正是病灶）。
2. **认结构** —— 配平要跳过字符串 / 模板串 / 注释 / 正则字面量。
   ⚠️ 只写「数 `{` 与 `}`」会当场瞎：壳里真有大正则（`view.js` 的 `splitRows` / `vsTableHits`），
   还夹着引号 `data-vs="[^"]*"`；注释里也**写着** `const ACT={…}` ⇒ 直接按字面找会找到注释那处。
3. **找不到 / 配不平 ⇒ 必抛** —— ⛔ 绝不静默回空（"空输出 ≠ 通过"是本仓反复踩的坑）。

⚠️ 这些是**工程侧**守卫（窗本身好不好用）⇒ 一律 `@acc()` 空参（不绑"用户看得见的行为"、不涨判据点）。

⚠️ **本条测不了什么**：窗里的内容对不对（比如 `V.m09` 渲染逻辑对不对）—— 那是各页自己的判据；
   这里只保证"**问得出、问得准、问不到会喊**"。
"""

from __future__ import annotations

import pathlib
import re

import pytest

from tests.acc_plugin import acc

from tests.shell_src import (  # noqa: F401
    SHELL, act_entry, api_entry, bind_block, bind_blocks, const_items, const_obj,
    const_src, func_body, page_slice,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: ⛔ 造第二套页切片算法的地方（`ui_parity` / `shell_src` 现已改成**只转发**）——
#: 本判据钉「⛔ 别写回来」：这两件源码里不许再出现"页切片正则"。
_NO_SECOND_ALGO = (ROOT / "tools" / "audit" / "ui_parity.py",
                   ROOT / "backend" / "tests" / "shell_src.py")
_SLICE_RE_DEF = re.compile(r"""re\.compile\(\s*r?["'][^"'\n]*V\\\.[^"'\n]*["']""")


# ── 1 · 取得到 ＋ 只有一套算法 ─────────────────────────────────────────


@acc()
def test_页切片与壳自检的切片算法一致():
    """`ui_parity.slices()` 与语义层的切片**逐页逐字节一致**（说明"唯一算法"真的落地了）。"""
    from tools.audit import shell_api
    from tools.audit.ui_parity import slices

    lines = SHELL.replace("\r\n", "\n").split("\n")
    assert slices(lines) == shell_api.slices_of_lines(lines)


@acc()
def test_页切片与_page_seg_一致():
    """`tests.shell_src.page_seg()` 只是转发 ⇒ 与 `page_slice` 结果必须一字不差。"""
    from tests.shell_src import page_seg

    for page in ("m09", "m05", "m02"):
        assert page_seg(page) == page_slice(page)


@acc()
def test_不许在_ui_parity_与_shell_src_里写回第二套切片算法():
    """⛔ 病根形态：同一件事两处各算一遍。这两件现在**只转发** ⇒ 出现切片正则就是写回来了。"""
    hits = [p.relative_to(ROOT).as_posix() for p in _NO_SECOND_ALGO
            if _SLICE_RE_DEF.search(p.read_text(encoding="utf-8"))]
    assert not hits, (
        f"这些件里又出现了页切片正则：{hits} —— 唯一主人 = `tools/audit/shell_api.py::slices_of_lines`；"
        "本处只许转发（`TAIL-219` 治的就是'同一件事各处剪一遍'）"
    )


# ── 2 · 认结构（字符串 / 模板串 / 注释 / 正则都别骗它）────────────────────

_FAKE_ACT = """/* 件说明里也会写：const ACT={} 这种形态 —— ⛔ 别被它骗走 */
const ACT={
  foo:()=>API.a({x:1}),
  bar:()=>API.b('}'),
  baz:t=>{ const s='}'; return s; },
};
const OTHER=1;
"""


@acc()
def test_取动作条_字符串里的花括号不算结束():
    """`ACT` 里某条的字符串含 `}` ⇒ 绝不能把它当成 `ACT` 对象的收尾。"""
    from tools.audit.shell_api import act_entry as A

    assert A("foo", source=_FAKE_ACT).strip() == "foo:()=>API.a({x:1})"
    assert A("bar", source=_FAKE_ACT).strip() == "bar:()=>API.b('}')"
    assert "return s;" in A("baz", source=_FAKE_ACT)


@acc()
def test_取动作条_注释里的_const_ACT_不算数():
    """⛔ 直接按字面找会命中**注释里**那个 `const ACT={…}`（2026-10-03 实测：配平当场收到 1 个字符）。"""
    from tools.audit.shell_api import act_entry as A

    assert "API.a(" in A("foo", source=_FAKE_ACT)     # 取到的是**真**那条，不是注释


#: ⭐ 注释里**列 0** 也写了一份真定义 ⇒ 定位若不先剥注释，会取到注释里那份（配平收在注释内）。
_FAKE_DOC = """/*
const ACT={
  ghost:()=>BOOM,
};
*/
const ACT={
  real:()=>API.real(),
};
"""


@acc()
def test_取动作条_注释里列0的假定义不算数():
    """⭐ 定位必须走"注释置空后的文本" —— 否则注释里那份假定义会被当成真的（然后报"找不到动作"）。"""
    from tools.audit.shell_api import act_entry as A

    assert A("real", source=_FAKE_DOC).strip() == "real:()=>API.real()"
    with pytest.raises(LookupError):
        A("ghost", source=_FAKE_DOC)                  # 注释里那条**不算存在**


_FAKE_FN = """/* 文档：function g(){…} */
function g(){
  const s='}';
  if(s){ return s; }
}
"""


@acc()
def test_取函数体_认结构():
    """函数体里的字符串含 `}` ⇒ 配平必须跳过它（⛔ 不是"数花括号"）。"""
    from tools.audit.shell_api import func_body as F

    body = F("g", source=_FAKE_FN)
    assert body.startswith("function g(){")
    assert body.endswith("\n}"), f"没取到函数末尾：{body[-40:]!r}"
    assert "if(s){ return s; }" in body


@acc()
def test_取动作条_缩进混用也要取到():
    """⭐ 真壳靶：`ACT` 的成员缩进 **1 与 2 空格混用**（` awfAdd:` / `  zipSfjc:` 并存）。

    ⚠️ 2026-10-03 批 2 **换真实调用点时当场暴露**：只认"2 空格"会漏掉一半的成员
       ⇒ 现按"同层深度"找（⛔ 不按缩进）。本条钉住这个能力，⛔ 别退回钉缩进。
    """
    for name in ("awfAdd", "zipSfjc", "expPivot"):     # 2 空格 / 1 空格 / 1 空格
        e = act_entry(name)
        assert e.strip().startswith(f"{name}:"), f"`{name}` 没取对（缩进混用被漏？）：{e[:60]!r}"


@acc()
def test_取动作条_不命中山层里的同名键():
    """⛔ 成员值里**嵌着**同名键（更深一层）⇒ 不许把它当成 `ACT` 的成员。"""
    from tools.audit.shell_api import act_entry as A

    fake = """const ACT={
  outer:()=>fn({
    dup:1,
  }),
  dup:()=>API.x(),
};
"""
    e = A("dup", source=fake)
    assert "API.x()" in e, f"取到的不是外层那条：{e[:60]!r}"
    assert "inner" not in e and "dup:1" not in e, "命中了山层里的同名键"


@acc()
def test_取动作条_真壳里跨行的成员要取整():
    """⭐ 真壳靶：`awfAdd` 那条动作**跨两行**（第二行是回执文案）⇒ 截在换行就丢一半。"""
    e = act_entry("awfAdd")
    assert "API.m09Add(" in e, "没取到这条动作"
    assert "增加手填项" in e, f"跨行的成员被截断了（只取到第一行？）：{e[:80]!r}"
    assert "API.m09Delete(" not in e, "取多了 —— 吃进了下一条动作"


_FAKE_ASSIGN = """/* 说明里也写一遍：ACT.ghost = 1; —— ⛔ 别被注释骗走 */
ACT.impThing = async () => {
  const s = ';';                 /* 字符串里的分号不算语句结束 */
  return API.impThing({t: 1});
};
const ACT={
  memberThing:()=>API.memberThing(),
};
"""


@acc()
def test_取动作条_赋值式也要取到():
    """⭐ 批 2b 余下 ①：`ACT.<名> = …;` **赋值式**（壳里 12 处 · `legacy.js` 的 i8 与导入两族）。

    ⚠️ 2026-10-04 量出的**第三种形态**（同族前两例：`ACT` 成员缩进 1/2 混用 · 一页两处 `BIND`）——
       `act_entry` 原先只扫对象字面量成员 ⇒ 这一族**整批看不见**（静默报"找不到动作"）。
    """
    e = act_entry("impRollback")
    assert e.startswith("ACT.impRollback ="), f"没取到赋值式那条：{e[:60]!r}"
    assert e.rstrip().endswith(";"), f"没取到语句结尾（截半了？）：{e[-40:]!r}"
    assert "API.impRollback" in e, "取到的不是这条动作"
    # 合成靶：字符串里的 `;` 与注释里的假定义都不许骗它
    f = act_entry("impThing", source=_FAKE_ASSIGN)
    assert "const s = ';';" in f, "赋值式的对象体被截半（字符串里的分号被当成语句结束？）"
    assert "return API.impThing({t: 1});" in f, "没取到对象体末尾"
    with pytest.raises(LookupError):
        act_entry("ghost", source=_FAKE_ASSIGN)      # 注释里那条**不算存在**


@acc()
def test_取动作条_两种形态不唯一就抛():
    """⛔ 同一个名字**成员与赋值式都命中** ⇒ 必须抛（静默挑一种 = 假绿）。"""
    from tools.audit.shell_api import act_entry as A

    fake = "const ACT={\n  dup:()=>API.x(),\n};\nACT.dup = () => API.y();\n"
    with pytest.raises(LookupError):
        A("dup", source=fake)


@acc()
def test_取函数体_真壳里的正则不被当成注释或字符串():
    """⭐ 真壳靶：`splitRows` 里有 `/<(\\/?)(tr|tbody)\\b[^>]*>/gi`；`vsTableHits` 里有夹引号的正则。"""
    body = func_body("splitRows")
    assert "const TAG=/<(\\/?)(tr|tbody)\\b[^>]*>/gi" in body, "含正则的函数体没取对（扫描器被正则骗了）"
    assert "spans.map(" in body, "函数体没取到末尾"
    hits = func_body("vsTableHits")
    assert 'data-vs="[^"]*"' in hits, "夹引号的正则没取对"
    assert hits.count("function ") == 1, f"取多了（吃进了别的声明）：{hits[:80]!r}"


# ── 3 · 找不到 / 配不平 ⇒ 必抛 ────────────────────────────────────────


@acc()
def test_取不到必须抛_不许静默回空():
    """⛔ 四条访问器对**不存在**的名字都必须抛（静默回空 = 看着绿、其实什么都没查）。"""
    for fn in (lambda: page_slice("__nope__"),
               lambda: func_body("__nope__"),
               lambda: act_entry("__nope__"),
               lambda: const_obj("__nope__")):
        with pytest.raises(LookupError):
            fn()


@acc()
def test_取常量表_只认对象字面量():
    """`const EXP_ROUTES = {…}` 取得到（含花括号）；`const WIRED=new Set([…])` **不归它** ⇒ 必抛。"""
    obj = const_obj("EXP_ROUTES")
    assert obj.startswith("{") and obj.endswith("}")
    assert "url:" in obj, "取到的不是那张导出分发对象"
    with pytest.raises(LookupError):
        const_obj("WIRED")


@acc()
def test_取_API_客户端条目_只取这一条():
    """⭐ 批 2b 新增口子：`const API = {…}`（唯一数据出口）里某一条 —— ⛔ 别取到旁边那条。"""
    e = api_entry("pjType")
    assert e.strip().startswith("pjType:") and "API.send(" in e, f"没取对：{e[:60]!r}"
    assert "m02Records" not in e, "取多了 —— 吃进了下一条"


@acc()
def test_取_BIND_块_三种写法都要收():
    """加工登记三种参数形态（箭头 / 函数表达式 / 函数引用）都要收，且只收这一条登记。"""
    b6 = bind_block("m06")
    assert b6.startswith("addBind('m06', function () {"), f"函数表达式那种没取对：{b6[:60]!r}"
    b15 = bind_block("m15")
    assert b15.startswith("addBind('m15', m15Trash);"), f"函数引用那种没取对：{b15[:60]!r}"
    assert "addBind('m06'" not in b15, "m15 那块吃进了下一个 BIND"
    b3 = bind_blocks("m03")
    assert len(b3) == 2, f"`m03` 应当有两块 BIND，实得 {len(b3)}"
    assert any(x.startswith("addBind('m03', ()=>") for x in b3), "箭头那种没取到"
    assert any(x.startswith("addBind('m03', function () {") for x in b3), "函数表达式那块没取到"


@acc()
def test_取_BIND_块_多处命中必须抛():
    """⚠️ 同一页有多块时**静默挑第一处 = 假绿**（实测 `m03`/`m11` 各两处，且第二块是**追加登记**）。"""
    with pytest.raises(LookupError):
        bind_block("m03")
    assert len(bind_blocks("m03")) >= 2


@acc()
def test_取常量整句_多段模板串也取全():
    """⭐ 批 2b 新增口子：`const X = \\`…\\`;` 整句（含**多段拼接** —— `BIG_THEAD` 那种）。"""
    for name in ("NT_THEAD", "AWF_THEAD", "BIG_THEAD"):
        s = const_src(name)
        assert s.startswith(f"const {name}=") or s.startswith(f"const {name} ="), s[:40]
        assert s.rstrip().endswith(";"), f"`{name}` 没取到语句结尾：{s[-40:]!r}"
    assert const_src("BIG_THEAD").count("`") >= 4, "多段模板串拼接没取全（截在第一段了？）"


@acc()
def test_取常量项_数组与_Set_都认():
    """⭐ 批 2b 新增口子：数组 / `new Set([…])` 的字符串项；对象字面量**不归它**（必抛）。"""
    assert set(const_items("LOAD_DEP")) == {"收发结存与大表", "付款域"}
    assert "m03" in const_items("WIRED") and "home" in const_items("WIRED")
    with pytest.raises(LookupError):
        const_items("EXP_ROUTES")          # 对象字面量 ⇒ 没有 `[…]`


@acc()
def test_页名清单与壳里_V_切片数一致():
    """`pages()` 必须与壳里真实的 `V.<名>=` 一一对应（⛔ 不许少一个、也不许多一个）。"""
    from tools.audit.shell_api import page_map

    m = page_map()
    assert "home" in m and "m09" in m and "imp" in m and "set" in m
    for page in m:
        # ⚠️ 写法不唯一：`V.set = () => {` 带空格、`V.m09=()=>{` 不带 ⇒ 按正则判（⛔ 别钉字面）
        assert re.search(rf"^V\.{re.escape(page)}\s*=", SHELL, re.M), \
            f"`page_map()` 报了一个壳里没有的页：{page}"


# ── 4 · ⛔ 不许再自造剪刀（清单**只许变短**）─────────────────────────────


@acc()
def test_壳的语义剪刀清单只许变短():
    """⭐ 批 3（`TAIL-219` 收口）：老账分批还，**新账当场拦**。

    ⚠️ 判词两条，都是"会做错的后果"：
      ① **多了一把** ⇒ 新写的判据又在按字面剪壳文本（换一次壳写法它就静默剪错，而判据看着还绿）；
      ② **少了一把**（白名单里的条目已经不是剪刀）⇒ 换掉了没销号（白名单变"幽灵条目"，
         久而久之没人敢动它 —— 白名单就成了摆设）。
    ⭐ 量法唯一 = `tests/shell_scissors.py`（AST 认**代码** · 注释/docstring 里的字样**不算**）。
    ⛔ 要"消红"只能**走语义窗**或**在 `shell_scissors.ALLOW` 里登记正当并写清理由**。
    """
    from tests.shell_scissors import ALLOW, scan

    found = {f"{rel}::{name}" for rel, name in scan()}
    new = sorted(found - set(ALLOW))
    assert not new, (
        f"新长出自造剪刀：{new} —— 走语义窗 `tools/audit/shell_api.py`（页/函数/动作/常量/BIND/API 条目），"
        "⛔ 别再自己从壳文本里按字面剪；确实该留 ⇒ 在 `tests/shell_scissors.py::ALLOW` 登记并写清理由"
    )
    stale = sorted(set(ALLOW) - found)
    assert not stale, f"白名单里有条目已经不是剪刀了（换掉了就销号）：{stale}"
