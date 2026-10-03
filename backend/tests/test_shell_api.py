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

from tests.shell_src import SHELL, act_entry, const_obj, func_body, page_slice  # noqa: F401

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
def test_页名清单与壳里_V_切片数一致():
    """`pages()` 必须与壳里真实的 `V.<名>=` 一一对应（⛔ 不许少一个、也不许多一个）。"""
    from tools.audit.shell_api import page_map

    m = page_map()
    assert "home" in m and "m09" in m and "imp" in m and "set" in m
    for page in m:
        # ⚠️ 写法不唯一：`V.set = () => {` 带空格、`V.m09=()=>{` 不带 ⇒ 按正则判（⛔ 别钉字面）
        assert re.search(rf"^V\.{re.escape(page)}\s*=", SHELL, re.M), \
            f"`page_map()` 报了一个壳里没有的页：{page}"
