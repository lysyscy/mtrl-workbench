"""`#2` **拆掉 `CHG` 名单**（2026-09-26 用户裁定 A：四面同批）—— 壳 ＋ 原型 ＋ 交付面判据 ＋ 变异靶。

为什么必须四面同批（设计件 §二）：`CHG` 被**交付面**钉着（`demo/_smoke.js` 的 `N6` ＋ 一条 `ck`），
且有**变异靶** `M1` 证明它会红 ⇒ 只改壳/原型 ⇒ `doc_audit --ui` 当场红。

改法：`change` 事件**只可能来自表单元素** ⇒ 名单是纯多余的护栏 ⇒ 委托层直接 `if(ACT[a]) ACT[a](t,e)`。

跑法：`backend\\.venv\\Scripts\\python.exe tools/oneoff/_apply_no_chg.py [--apply]`
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SHELL = REPO / "backend" / "app" / "web" / "shell"
DEMO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo")
PROTO = DEMO / "材料报表自动化工作台-交互原型.html"
SMOKE = DEMO / "_smoke.js"
MUT = REPO / "tools" / "mut" / "_mut_uicheck.py"

OLD_GATE = "if(ACT[a]&&CHG.includes(a)) ACT[a](t,e);"
NEW_GATE = ("/* ⭐ `#2`（2026-09-26）：**没有名单了** —— `change` 事件只可能来自表单元素\n"
            "     （`data-act` 挂在别的东西上根本收不到 change）⇒ 名单是纯多余的护栏，\n"
            "     而它每漏登记一个动作就是一次**静默丢弃**（本仓踩过 `jcAmt` / `jcPartySet` / `themeSet`）。 */\n"
            "  if(ACT[a]) ACT[a](t,e);")
#: ⚠️ `M1` 变异靶就钉在这句标记注释上（把它改坏 = 把名单塞回来 ⇒ `N6′` 必须红）
DECL_MARK = "/* ⛔ `#2`"
NO_CHG_DECL = (DECL_MARK + "（2026-09-26）：那张 **「变更事件白名单」已整份删除** —— 表单类动作**不再需要登记**：\n"
               "   `change` 委托按「事件只来自表单元素」直接跑（见下面那个 `change` 委托）。\n"
               "   ⚠️ 原先 64 个名字的名单 ＋ `legacy.js` 追加 3 个 = 每加一个控件都要人记一次，\n"
               "      漏了就是「选完没反应」的**静默**故障。 */")
PUSH_OLD = "CHG.push('impDomain', 'impPick', 'impMap');"

#: `N6′`：名单没了 ⇒ 判据换成「**名单不许回来**」（⚠️ 只能在运行时可查的东西上判：
#:   沙箱把 `addEventListener` 做成了空实现 ⇒ 委托那段**查不到**，⛔ 不许假装查得到）。
N6_NEW = """guard('N6′｜表单类动作**不再需要登记**（`#2` 2026-09-26）：原型里没有 `CHG` 名单', () => {
  /* ⭐ 判词换了（`#2`）：原先钉的是「凡渲染成表单元素的动作都必须在 `CHG` 里」——
     名单拆掉之后那句就没有主人了；**新的主人 = 委托层**（`change` 看见 `data-act` 就跑，不存在漏登记）。
     ⚠️ 命名空间里 `CHG` 一旦回来 ⇒ 说明又有人把名单加上去了 ⇒ 本条红（`M1` 变异靶证明它会红）。 */
  if (typeof X.CHG !== 'undefined') throw new Error('`CHG` 名单又回来了 —— `#2` 已裁定拆掉它（表单类动作不该再靠登记）');
});"""
CK_DESC_OLD_RE = re.compile(r"'[^']*plRowSet[^']*CHG[^']*'")
CK_DESC_NEW = ("'`plRowSet` 由 `change` 委托承接（`#2` 起不再靠 `CHG` 登记；"
               "表单元素按种类自动跑）'")
CK_EXPR_OLD = "X.CHG.indexOf('plRowSet') >= 0"
CK_EXPR_NEW = "!!X.ACT.plRowSet"

#: `M1` 变异靶：原先打 `CHG` 名单 ⇒ 换靶 = **把名单塞回原型**（N6′ 必须红）
M1_OLD = '''("replace", b"'plRowSet'", b"'plRowSet_MUT'")'''
M1_NEW = '''("replace", b"/* \\xe2\\x9b\\x94 `#2`", b"const CHG=[];\\n/* \\xe2\\x9b\\x94 `#2`")'''


def _one(text: str, old: str, new: str, where: str, *, exactly: int | None = 1) -> tuple[str, int]:
    got = text.count(old)
    if exactly is None:
        assert got <= 1, f"{where}：命中 {got} 处（期望 ≤1）\n  {old[:100]}"
    else:
        assert got == exactly, f"{where}：命中 {got} 处（期望 {exactly}）\n  {old[:100]}"
    return (text.replace(old, new, got), got)


def main(argv: list[str]) -> int:
    mut = {p: p.read_text(encoding="utf-8") for p in (SHELL / "actions.js", SHELL / "legacy.js",
                                                      PROTO, SMOKE, MUT)}

    # ① 壳 ＋ 原型：删名单 ＋ 委托直接跑
    for p in (SHELL / "actions.js", PROTO):
        t = mut[p]
        n = len(re.findall(r"const CHG=\[", t))
        assert n == 1, f"{p.name}：`const CHG=[` 命中 {n} 处（期望 1）"
        t = re.sub(r"const CHG=\[[\s\S]*?\];", NO_CHG_DECL, t, count=1)
        t, _ = _one(t, OLD_GATE, NEW_GATE, f"{p.name}(change 委托)")
        mut[p] = t
    mut[SHELL / "legacy.js"], _ = _one(mut[SHELL / "legacy.js"], PUSH_OLD,
                                       "/* `#2`（2026-09-26）：那行「变更事件白名单」登记已废 —— 表单类动作不再需要登记 */",
                                       "legacy.js(CHG.push)")

    # ② 交付面：`N6` ⇒ `N6′`（整段换：`guard('N6｜` 到该调用的 `});`）＋ 那条 `ck`
    smk = mut[SMOKE]
    i = smk.find("guard('N6｜")
    assert i > 0, "`_smoke.js` 里找不到 `guard('N6｜`（形态变了就同批改本件）"
    j = smk.index("\n});", i)
    smk = smk[:i] + N6_NEW + smk[j + 4:]
    d = CK_DESC_OLD_RE.search(smk)
    assert d, "找不到那条含 `plRowSet`+`CHG` 的描述串"
    smk = smk[:d.start()] + CK_DESC_NEW + smk[d.end():]
    smk, _ = _one(smk, CK_EXPR_OLD, CK_EXPR_NEW, "_smoke.js(ck 断言)")
    mut[SMOKE] = smk

    # ③ 变异靶换靶
    mut[MUT], _ = _one(mut[MUT], M1_OLD, M1_NEW, "_mut_uicheck.py(M1 靶)")

    # ④ 反向断言
    for p in (SHELL / "actions.js", PROTO):
        for bad in ("const CHG=[", "CHG.includes(", "CHG.push("):
            assert bad not in mut[p], f"{p.name}：`{bad}` 还在"
    # ⚠️ 只查**真调用**：legacy.js 的文件头注释里引述过 `CHG.push(…)`（那是说明，不是实现）
    assert "CHG.push('impDomain'" not in mut[SHELL / "legacy.js"]

    if "--apply" not in argv:
        print("dry-run ✅ 断言通过（⛔ 未写盘）：actions.js / legacy.js / 原型 / _smoke.js / _mut_uicheck.py")
        return 0
    for p, t in mut.items():
        p.write_text(t, encoding="utf-8", newline="")
        print(f"✅ 已写盘：{p.name}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv))
