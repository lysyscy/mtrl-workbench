"""真机自检**段的注册表**守卫（`TAIL-215` 批 1）—— 「顺序」从"只写在注释里"变成**可判**。

## 它守什么（全是**离线**、秒级；⛔ 不 import playwright、⛔ 不起浏览器）

| # | 守的 | 病（不守会长成什么） |
|---|---|---|
| 1 | **金标清单**：段号与次序 = 一份**独立写死**的清单（39 条） | 「搬着搬着少了一段 / 顺序被换了」**没人看得见** —— 而这正是本仓最贵那族病（判据静默失效） |
| 2 | 段号**不许重复** | 屏幕上两个 ⑳ ⇒ 报错时不知道是哪一段 |
| 3 | 相位**必须成块**（`pre`* → `boot`* → `body`*） | 段被插到"开页之前" ⇒ 它读的全局还不存在 |
| 4 | `last=True` **恰好一条**、且**在表末** | ㉞ 会拦断 ＋ 刷新 ⇒ 它后面再有段 = **那段读到被刷过的状态**（＝假绿） |
| 5 | 每条 `after=["…"]` 的目标**在表里**、且**确实排在本条之前** | 约束指向不存在的段号 ⇒ 那句约束**打了空靶** |
| 6 | 每条 `entry` **都解析得到真函数**（`self:<名>` ⇒ 编排件里有 `def <名>(`；`模块:函数` ⇒ 那件里有那个函数） | 表里写着、函数改名/删了 ⇒ 真机跑到那一段**当场崩**（而不是"悄悄少跑一段"） |
| 7 | 编排件**真的遍历注册表**（`for seg in SEGMENTS` ＋ 有 `_boot`） | "表写了，但没人照它跑" ⇒ 注册表变**装饰品** |
| 8 | 编排件里 ⛔ **不许再有裸 `check_<…>(page, errors)`** | 绕过注册表的**第二套编排** ⇒ 顺序又有了第二个出处 |
| 9 | ⭐ **段代码不许放回编排件**（`entry` 里 ⛔ 无 `"self:…"`、编排件里 ⛔ 无 `def seg_*`） | 批 2 把 15 段搬成"每段一件"了 ⇒ 别哪天又塞回主件（那正是本尾巴要治的病） |

## ⚠️ 为什么金标清单**故意写死**在本件（而不是"从表里生成"）

它要守的正是"表被改动"这件事 —— 跟表同源就**永远判不出来**。
⇒ 改表（加/删/挪段）时**必须同批改下面那张 `_GOLDEN`**，那一刻人会被迫看一眼"少了哪一段 / 换到哪去了"。
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "tools" / "probe"

#: ⭐ **金标清单**：段号与次序（`TAIL-215` 批 1 建档时的真实现状 = **39 段**）
#: ⚠️ 改注册表 ⇒ 同批改这里（⛔ 别"顺手自动跟上" —— 那就失去守卫的意义了）。
_GOLDEN: tuple[str, ...] = (
    "⓪", "㉒",                                              # pre（开页之前）
    "①", "②", "③",                                          # boot（开屏那一屏）
    "④", "⑤", "⑥", "⑥b", "⑦", "⑦′", "⑧", "⑨", "⑩", "⑩b",     # body：内联段
    "⑪", "⑫", "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳", "㉑",
    "㉓", "㉔", "㉕", "㉘", "㉗", "㉚", "㉛", "㉜", "㉝", "㊲", "㉟", "㊱",
    "㉞",                                                    # 收尾（拦断＋刷新 ⇒ 必须最后）
)

_PHASES = ("pre", "boot", "body")


def _registry():
    """**按文件路径**装载注册表（⛔ 不靠 sys.path）—— 它只 import `dataclasses` ⇒ 不拉 playwright。

    ⚠️ 必须**先登记进 `sys.modules`** 再 `exec_module` —— 否则 `@dataclass` 解析**字符串注解**时
       （本件有 `from __future__ import annotations`）会去 `sys.modules` 里找本模块、找不到 ⇒
        `AttributeError: 'NoneType' object has no attribute '__dict__'`（**首跑就踩到**）。
    """
    spec = importlib.util.spec_from_file_location("_shell_segments_under_test",
                                                  PROBE / "_shell_segments.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@acc()
def test_段清单与次序必须等于金标():
    segs = _registry().SEGMENTS
    got = tuple(s.id for s in segs)
    assert got == _GOLDEN, (
        "段的清单/次序与金标不一致 ⇒ 要么**少了一段**（判据静默失效），要么**顺序被换了**。\n"
        f"  金标 {len(_GOLDEN)} 条：{_GOLDEN}\n  实际 {len(got)} 条：{got}\n"
        "  ⚠️ 若这是**有意**改的 ⇒ 同批改本文件的 `_GOLDEN`（并跑 `tools/mut/_mut_segments.py`）。")


@acc()
def test_段号不许重复():
    segs = _registry().SEGMENTS
    ids = [s.id for s in segs]
    dup = sorted({x for x in ids if ids.count(x) > 1})
    assert not dup, f"段号重复：{dup} —— 报错时说不出是哪一段"


@acc()
def test_相位必须成块pre_boot_body():
    segs = _registry().SEGMENTS
    bad = [s.id for s in segs if s.phase not in _PHASES]
    assert not bad, f"相位值不在 {_PHASES} 里：{bad}"
    order = [s.phase for s in segs]
    # 相位**只许前进**（pre→boot→body），⛔ 不许回头
    assert order == sorted(order, key=_PHASES.index), (
        "相位**交错**了（例如 body 里又插了一个 pre）⇒ 那段会读不到它依赖的东西。\n"
        f"  实际：{order}")


@acc()
def test_最后一段恰好一条且在表末():
    """㉞ 会拦断 ＋ 刷新 ⇒ 它后面再有段 = **那段读到被刷过的状态**（＝假绿）。"""
    segs = _registry().SEGMENTS
    lasts = [s.id for s in segs if s.last]
    assert len(lasts) == 1, f"`last=True` 的段有 {len(lasts)} 条（期望恰好 1）：{lasts}"
    assert segs[-1].id == lasts[0], (
        f"标了 `last=True` 的是 {lasts[0]!r}，但它**不在表末**（表末 = {segs[-1].id!r}）"
        " ⇒ 后面那些段会跑在**被拦断/刷新过**的页面上")


@acc()
def test_after_指向的段必须在表里且排在本条之前():
    segs = _registry().SEGMENTS
    pos = {s.id: i for i, s in enumerate(segs)}
    for i, s in enumerate(segs):
        for t in s.after:
            assert t in pos, (f"{s.id} 的 `after` 指向 {t!r}，表里**没有这一段** ⇒ 那句约束打了空靶")
            assert pos[t] < i, (f"{s.id} 声称「必须排在 {t} 之后」，但它其实排在 {t} **之前**"
                                f"（{i} vs {pos[t]}）")


@acc()
def test_每条entry都解析得到真函数():
    """表里写着、函数改名/删了 ⇒ 真机跑到那一段**当场崩**（而不是"悄悄少跑一段"）。"""
    segs = _registry().SEGMENTS
    smoke_src = (PROBE / "_shell_smoke.py").read_text(encoding="utf-8")
    self_defs = set(re.findall(r"^def (seg_\w+)\(page, errors\)", smoke_src, re.M))
    bad: list[str] = []
    for s in segs:
        e = s.entry
        if callable(e):
            continue
        if e.startswith("self:"):
            name = e[5:]
            if name not in self_defs:
                bad.append(f"{s.id}: `{e}` ⇒ 编排件里**没有** `def {name}(page, errors)`"
                           f"（现有：{sorted(self_defs)}）")
            continue
        mod, _, fn = e.partition(":")
        p = PROBE / f"{mod}.py"
        if not p.exists():
            bad.append(f"{s.id}: `{e}` ⇒ 件 `tools/probe/{mod}.py` **不在位**")
        elif not re.search(rf"^def {re.escape(fn)}\(", p.read_text(encoding="utf-8"), re.M):
            bad.append(f"{s.id}: `{e}` ⇒ `{mod}.py` 里**没有** `def {fn}(`")
    assert not bad, "注册表里的 entry 有解析不到的：\n  " + "\n  ".join(bad)


@acc()
def test_段代码不许放回编排件():
    """`TAIL-215` 批 2：**每段一件** ⇒ `entry` 只许是 `模块:函数`（或直接给可调用）。

    ⛔ `"self:…"`（段函数写在 `_shell_smoke.py` 里）那一支已随批 2 撤掉 —— 它等于「把段代码塞回主件」，
       而那正是本尾巴要治的病（主件只该留 引导 ＋ 遍历注册表 ＋ 汇总）。
    """
    src = (PROBE / "_shell_segments.py").read_text(encoding="utf-8")
    assert '"self:' not in src, (
        "注册表里又出现 `self:` 形态的 entry ⇒ ⛔ 段代码别放回 `_shell_smoke.py`，"
        "给它一个 `tools/probe/_shell_*.py`")
    smoke = (PROBE / "_shell_smoke.py").read_text(encoding="utf-8")
    assert re.search(r"^\s*def seg_", smoke, re.M) is None, \
        "编排件里又出现了 `def seg_*`（段代码被塞回主件了）"


@acc()
def test_编排件必须真的遍历注册表():
    """否则注册表只是**装饰品**（"表写了、没人照它跑"）。"""
    smoke_src = (PROBE / "_shell_smoke.py").read_text(encoding="utf-8")
    assert "for seg in SEGMENTS:" in smoke_src, "编排件没遍历 `SEGMENTS` ⇒ 表写了也不跑"
    assert "def _boot(page)" in smoke_src, "编排件里没有 `_boot()`（开页那一步）"


@acc()
def test_编排件里不许再有裸调用():
    """绕过注册表的**第二套编排** ⇒ 顺序又有了第二个出处（本仓最恨的病）。"""
    smoke_src = (PROBE / "_shell_smoke.py").read_text(encoding="utf-8")
    bare = re.findall(r"^\s+check_\w+\(page, errors\)", smoke_src, re.M)
    assert not bare, (
        "编排件里还有**裸调用**（不经注册表）：" + "、".join(x.strip() for x in bare) +
        "\n  ⇒ 把它写进 `tools/probe/_shell_segments.py`，⛔ 别在这里直接调")
