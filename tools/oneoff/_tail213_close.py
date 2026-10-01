"""`TAIL-213` **甲 · 收尾批**：撤 `CALIB` 内核与它那一整套钉子（2026-10-01）。

撤什么（每处都**先断言命中**；⛔ 一处不达标整批不写盘）：
  ① `backend/app/web/shell/proj.js`：`CALIB` 内核 ＋ 它的头注释 ⇒ 换成**墓碑注释**（写清谁拍的板、为什么撤、
     别再长回来、判据在哪）。
  ② `backend/tests/shell_src.py`：`calib_kernel()` ＋ `with_calib()` ＋ `CALIB_PAGES`（已空）＋ `__all__` 里的三条。
  ③ `backend/tests/test_ux_numbers.py`：撤 `test_口径说明块走统一出口_CALIB`（**靶退场 ⇒ 判据同批撤**）；
     把 `test_口径说明的条数必须与实际的条数一致` **改钉新意图** ⇒ `test_口径说明不许再收进折叠块`
     （判法保留：扫「口径说明 · N 条」的手抄形态；意图换新：那条抽屉不许长回来）。
  ④ `tools/mut/_mut_uxnum.py`：撤 `M4` / `M5` / `M7` 三靶（它们的靶串就是 `CALIB` 内核与调用点）——
     ⭐ **本仓规矩：撤判据必须同批撤靶**（留着 = 每次跑都「变异串没找到」）。
  ⑤ `tools/probe/_shell_text.py`：真机 ㉖ 的提示语「…或折进该页已有的「口径说明」」—— 那条出路已经没了。
  ⑥ `backend/tests/test_ux_brief.py`：模块 docstring 里那句「每页该有的「口径说明」折叠出口必须还在」同步改口。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJ = ROOT / "backend" / "app" / "web" / "shell" / "proj.js"
SHELL_SRC = ROOT / "backend" / "tests" / "shell_src.py"
UXNUM = ROOT / "backend" / "tests" / "test_ux_numbers.py"
UXBRIEF = ROOT / "backend" / "tests" / "test_ux_brief.py"
MUT = ROOT / "tools" / "mut" / "_mut_uxnum.py"
PROBE = ROOT / "tools" / "probe" / "_shell_text.py"

PROJ_TOMB = """/* ⚠️⚠️ **2026-10-01（`TAIL-213` 甲）：这里的「口径说明块件」`CALIB` 已整件退场。**
 * 用户拍板（原话）：「**每页折叠的口径说明里的也简化或者删除吧？说实话我一次也没进去看过**」
 * ⇒ 全站 **14 块折叠块（74 条 / 5,828 字）全撤**，改成 **13 段页内默认展开的说明**（各 ≤160 字）：
 *    会做错的后果 ⇒ 留（页内或操作现场的悬停）· 复述《说明书》的规则 ⇒ 删（复述必漂）。
 * ⛔ **别再长回来** —— 守卫 = `tests/test_ux_numbers.py::test_口径说明不许再收进折叠块`。
 * 来历 / 逐批实况 = `work/10-designs/设计-口径说明折叠块-20261001.md`（§七 施工实况）。 */
"""

NEW_JUDGE = '''@acc()
def test_口径说明不许再收进折叠块():
    """⭐⭐ `TAIL-213`（2026-10-01 · 用户拍板「甲」）：**「口径说明」不许再收进折叠块**。

    **为什么**：用户原话「每页折叠的口径说明里的也简化或者删除吧？**说实话我一次也没进去看过**」
    ⇒ 全站 **14 块折叠块（74 条 / 5,828 字）全撤**，改成 **13 段页内默认展开的说明**（各 ≤160 字）。
    ⇒ 本条把那条决定**变成判据**：`口径说明 · N 条` 那种抽屉**一旦长回来就红**。
    ⚠️ 它原先是「那个手抄的 `N` 必须由出口 `CALIB` 算出来」—— 靶（内核 `CALIB`）已随本批退场，
       **判法保留、意图换新**（本仓老课：撤结构要同批把守它的判据换成守新意图的那条）。
    ⚠️ 「说明要**看得见**」那一半由 `test_ux_brief.py::test_折叠出口还在_不许靠删来过关` 守（数页内 `class="tip"`）。
    ⚠️ **唯一允许的例外** = `shell/legacy.js` 里「设置」页那块 `<details>`（它渲染**后端自报**的 §7.8 四条，
       不在本批范围内；它不含「· N 条」那种形态 ⇒ 不会被本条误伤）。
    ⚠️ 能证伪：往任一页写回一块 `<details class="tip"><summary>口径说明 · 3 条…` ⇒ 本件必红。
    """
    txt = re.sub(r"/\\*.*?\\*/", "", SHELL, flags=re.S)     # ⛔ 先剥块注释（注释里会引述旧写法）
    n_lit = len(re.findall(r"<details[^>]*>\\s*<summary>口径说明 · \\d+ 条", txt))
    assert n_lit == 0, (
        f"又有 **{n_lit}** 块把「口径说明」收进了折叠块 —— 用户 2026-10-01 拍板撤掉那个抽屉"
        "（原话「一次也没进去看过」）；要写说明就写**页内默认展开**的一段 "
        "（守则 §5.8：要换地方，不是删掉）")
'''


def cut(text: str, start: str, end: str, new: str, *, lo: int = 20, hi: int = 9000) -> str:
    """把 `[start, end)` 那段整段换成 `new`（`end` 是**保留**的终点标记）。"""
    a = text.index(start)
    b = text.index(end, a)
    assert lo < b - a < hi, f"要切的那段长度 {b - a} 不像（起点/终点选错了？）"
    return text[:a] + new + text[b:]


def main() -> int:
    # ① proj.js：内核 ＋ 头注释 ⇒ 墓碑
    p = PROJ.read_text(encoding="utf-8")
    assert "const CALIB=" in p and p.count("const CALIB=") == 1
    p = cut(p, "/* ⭐ **口径说明块件**", "const thCount=h=>", PROJ_TOMB + "\n")
    # ⚠️ 墓碑注释里**本来就会提到 `CALIB`** ⇒ 查的是"内核还在不在"
    assert "const CALIB=" not in p, "proj.js 里还留着 CALIB 内核"
    PROJ.write_text(p, encoding="utf-8", newline="")

    # ② shell_src.py：两个取件桩 ＋ 名单 ＋ __all__
    s = SHELL_SRC.read_text(encoding="utf-8")
    s = cut(s, "def calib_kernel() -> str:", "def page_seg(page: str) -> str:", "")
    s = s.replace(
        '__all__ = ["CALIB_PAGES", "SHELL", "SHELL_PARTS", "SHELL_PATH", "calib_kernel", "dl_kernel",\n'
        '           "fbar_kernel", "page_seg", "part_paths", "parts_text", "pjb_kernel", "read_shell",\n'
        '           "tbl_kernel", "with_calib", "with_fbar", "with_kernel", "with_pjb", "with_tbl"]',
        '__all__ = ["SHELL", "SHELL_PARTS", "SHELL_PATH", "dl_kernel", "fbar_kernel", "page_seg",\n'
        '           "part_paths", "parts_text", "pjb_kernel", "read_shell", "tbl_kernel",\n'
        '           "with_fbar", "with_kernel", "with_pjb", "with_tbl"]', 1)
    assert "calib_kernel" not in s and "CALIB_PAGES" not in s and "with_calib" not in s, \
        "shell_src.py 里还有 CALIB 那套"
    SHELL_SRC.write_text(s, encoding="utf-8", newline="")

    # ③ test_ux_numbers.py：import ＋ `_CALIB_DONE` ＋ 两条判据 ⇒ 一条新意图判据
    u = UXNUM.read_text(encoding="utf-8")
    u = u.replace(
        "from tests.shell_src import CALIB_PAGES, SHELL, calib_kernel, page_seg",
        "from tests.shell_src import SHELL", 1)
    u = cut(u, "#: ⭐ `TAIL-64` `P4-c`：**口径说明块已收进 `CALIB` 出口的页**",
            "@acc()\ndef test_口径说明的条数必须与实际的条数一致():", "")
    u = cut(u, "def test_口径说明的条数必须与实际的条数一致():",
            "@acc()\ndef test_口径说明块走统一出口_CALIB():", NEW_JUDGE + "\n\n")
    a = u.index("@acc()\ndef test_口径说明块走统一出口_CALIB():")
    u = u[:a].rstrip("\n") + "\n"
    # ⚠️ 新判据的 docstring 里会提到 `CALIB`（讲清楚靶怎么退场的）⇒ 只查**代码引用**
    assert "calib_kernel" not in u and "CALIB_PAGES" not in u and "page_seg" not in u, \
        "test_ux_numbers.py 里还有 calib_kernel / CALIB_PAGES / page_seg 残留"
    UXNUM.write_text(u, encoding="utf-8", newline="")

    # ④ _mut_uxnum.py：撤 M4/M5/M7（靶串就是 CALIB 内核与调用点）
    m = MUT.read_text(encoding="utf-8")
    m = cut(m, "    # ⭐⭐ 2026-09-30（`TAIL-64` **P4-c-a / P4-c-b**）：`CALIB` 出口那几根钉子",
            "]\n\n\ndef run_one", "]\n\n\ndef run_one")
    m = m.replace("六靶（一次只碰一处、改完**立刻按 bytes 复原** ＋ 收尾 MD5）：",
                  "三靶（一次只碰一处、改完**立刻按 bytes 复原** ＋ 收尾 MD5）：", 1)
    m = cut(m, "- ⭐ `M4`（2026-09-30 · `TAIL-64` **P4-c**）",
            "\n跑法：`backend", "⭐ **`M4` / `M5` / `M7` 已于 2026-10-01 撤掉**（随 `TAIL-213` **甲**："
            "`CALIB` 内核整件退场）—— 本仓规矩「**撤判据必须同批撤靶**」，"
            "留着它们每次跑都会「变异串没找到 ⇒ 静默跳过」。\n")
    assert "M4 " not in m and "M5 " not in m and "M7 " not in m, "_mut_uxnum.py 里还有 M4/M5/M7"
    MUT.write_text(m, encoding="utf-8", newline="")

    # ⑤ 真机 ㉖ 的提示语
    pr = PROBE.read_text(encoding="utf-8")
    old = '"—— 压成 1~2 句，或折进该页已有的「口径说明」：\\n"'
    new = '"—— 压成 1~2 句（本系统已不再有折叠的口径说明抽屉，见 `TAIL-213`）：\\n"'
    assert pr.count(old) == 1, "真机 ㉖ 的提示语锚点没命中 1 次"
    PROBE.write_text(pr.replace(old, new, 1), encoding="utf-8", newline="")

    # ⑥ test_ux_brief.py 的模块 docstring
    br = UXBRIEF.read_text(encoding="utf-8")
    oldb = '  ② **反"删光"**：不许用"把说明都删掉"来过 ㉖ —— 每页该有的「口径说明」折叠出口必须还在（§5.8「换地方，不是删掉」）。'
    newb = ('  ② **反"删光"**：不许用"把说明都删掉"来过 ㉖ —— ⭐ 2026-10-01（`TAIL-213` 甲）起改数**页内默认展开**的\n'
            '     说明（折叠那一路已按用户拍板撤掉；§5.8「换地方，不是删掉」）。')
    assert br.count(oldb) == 1, "test_ux_brief docstring 锚点没命中 1 次"
    UXBRIEF.write_text(br.replace(oldb, newb, 1), encoding="utf-8", newline="")

    print("✅ 收尾批：CALIB 内核 ＋ 两个取件桩 ＋ 那条判据 ＋ 变异 M4/M5/M7 ＋ 真机提示语 都已撤/改")
    return 0


if __name__ == "__main__":
    sys.exit(main())
