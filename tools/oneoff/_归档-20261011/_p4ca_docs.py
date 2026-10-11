#!/usr/bin/env python
r"""`TAIL-64` **`P4-c-a`** 的同批文档落纸（2026-09-30）。

**改什么**（每处都断言"恰好命中 1 次" —— ⛔ 宁可不改，也不打偏）：
 1. 施工图 `设计-表格筛选配置化-20260924.md` **§8.10**：① 状态行（`尚未开工` → `P4-c-a` 已办）；
    ② 批切法表头那句「双边同步 ＋ `U1` 换号」**作废**（`TAIL-201` 之后没有尺子比原型）；
    ③ `P4-c-a` 行里「出口件要加进 `U5_GROUPS`」**作废**；④ `P4-c-b` 行那句同批订正；
    ⑤ **新增 §8.11**（`P4-c-a` 实况 ＋ ⭐ 那条「JS 模板字面量把 `CRLF` 折成 `LF`」的实测结论）。
 2. 计划 §14.3 的 `TAIL-64` 行：尾句「余 `P4-c`（待用户定裁）/ `P5-c` / `P5-d`」⇒ 换成实况。
 3. 计划 §15 §一 的 `TAIL-64` 行：追加 `P4-c-a` 的落点 / 判据 / 变异 / 桩。
 4. 计划 §13.6（交接材料）**两处"钉住现状"的句子**：`尚未开工` ⇒ 已开工（⚠️ 口令过期**不会红**，
    只会让下个会话**把试点再做一遍**）；另把「已办到 `P4-d-b`」改成「已办到 `P4-c-a`」。

用法：`python tools/oneoff/_p4ca_docs.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DESIGN = ROOT / ".workbuddy" / "work" / "10-designs" / "设计-表格筛选配置化-20260924.md"
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

# ── 施工图 ────────────────────────────────────────────────────────────────
D1_OLD = ("**⏭ 状态**：档已定、切法已给 ⇒ **尚未开工**（要一轮整预算：14 处双边同步 ＋ 换号 ＋ 判据/变异，"
          "量级同 `P3` 那批）。")
D1_NEW = ("**⏭ 状态**：⭐ **`P4-c-a` 试点已办**（2026-09-30 —— 出口 `CALIB` ＋ `V.m13` 一处 · 见 **§8.11**）；"
          "余 **`P4-c-b`（13 块）** 未开工。⚠️ **计量已变**：`TAIL-201` 之后**不再有双边同步 / 换号登记**，"
          "每处只剩「换调用点 ＋ **渲染字节自证** ＋ 判据名单加一行」⇒ 早不是 `P3` 那个量级。")

D2_OLD = "**批切法**（⚠️ 14 块**全在 `V.*` 切片里** ⇒ 每处都要**双边同步** ＋ `U1` 换号登记）："
D2_NEW = ("**批切法**（⚠️ 14 块**全在 `V.*` 切片里** —— ⛔ 但原先那两步「双边同步 ＋ `U1` 换号登记」"
          "**已随 `TAIL-201` 作废**（现在**没有任何尺子比原型**）；每处只需：换调用点 ＋ **渲染字节自证** ＋ "
          "判据名单加一行）：")

D3_OLD = "（⚠️ 出口件要**加进 `U5_GROUPS`**）"
D3_NEW = ("（⚠️ ⛔ 本行原写「出口件要加进 `U5_GROUPS`」—— **那条已随 `TAIL-201` 作废**；"
          "现在改公共件只挂**判据 ＋ 变异**，改完跑 `shell_verify` 看差异）")

D4_OLD = "每批都要 `U1` 换号 ＋ 幽灵登记（同 `P3` 那批的做法）；⛔ **别一次铺**"
D4_NEW = "每批都要**逐块渲染字节自证**（同 `P4-c-a`）；⛔ **别一次铺**"

D5_HEAD = """
### 8.11 ⭐ `P4-c-a` 实况（2026-09-30 · 出口 `CALIB` ＋ 1 处试点）

**出口**（`shell/proj.js`，与 `TBL` / `FBAR` / `PJB` **同件**）：
`CALIB({items:[…]})` ⇒ `<details class="tip"><summary>口径说明 · N 条 <span…>…</span></summary><ul …>…</ul></details>`，
其中 **`N = items.length`**（由构造保证）· `<ul>` 外壳与条目分隔由本件出 · **条目正文逐字留在调用点**。

**试点 = `V.m13`**（挑它的三条理由都是**量出来的**，见 `tools/oneoff/_p4ca_survey.py`）：
14 块里最小的两块是 `m13`/`m14`（各 3 条）· `m14` 旁边那两句被别的判据钉着（`test_ux_colors` / `_mut_a7`）⇒ 绕开 ·
`m13` 的块**没有任何判据钉它的形态** ⇒ 切换面最小。（⚠️ §8.10 说 `TAIL-201` 之后「随便挑一页」——
但「随便」不等于「不看别人钉着谁」。）

| 项 | 值 |
|---|---|
| 行数 | **-1**（`<ul>` 那行进出口了）—— ⚠️ `TAIL-201` 之后**不再有逐行对位** ⇒ 行数变化无代价 |
| 渲染字节 | **逐字节不变**（449 字）—— 自证 = `tools/oneoff/_p4ca_calib.py` 拿 `node` **真渲染**比对 |
| 判据 | `backend/tests/test_ux_numbers.py::test_口径说明块走统一出口_CALIB`（**先查内核再扫调用点**） |
| 变异 | `tools/mut/_mut_uxnum.py` **4 → 7/7**（`M5` 写死条数 / `M6` 又裸写一层 / `M7` 不包条目外壳） |
| 取件桩 | `backend/tests/shell_src.py::calib_kernel()` ／ `with_calib()` |
| 原型 | ⛔ **未动**（`TAIL-201` 起没有任何尺子比原型；「双边同步」已取消） |

⭐⭐ **本批顺手实测出一条会反复用到的硬结论：JS 的模板字面量会把源码里的 `CRLF` 折成 `LF`。**
壳各件虽然**全是 `CRLF`**（`_p4ca_survey.py` 量的），但原块活在模板字面量里 ⇒ 它渲染出来是 `LF`
⇒ 出口里那个换行**必须写 `\\n`**（写 `\\r\\n` 就**差两个字节**）。
⚠️ 这条**只能实测**（拿 `node` 渲一遍比）—— ⛔ 不能靠"读文件行尾"推断（我第一版就是照文件行尾写 `\\r\\n`、当场不等）。

⛔ **还要记住两件**：① 那条「条数一致」判据的**下限**已改成「手抄块 ＋ 已转页 **合起来** ≥ 10」——
否则一路转下去，**全转完那天它会假红**（靶还在，只是换了形态）；
② `_CALIB_DONE` 是**逐页增量名单**，`P4-c-b` 每转一页就往里加一个（判据会跟着管它）。
"""

# ── 计划 §14.3 ───────────────────────────────────────────────────────────
P1_OLD = ("· ⏭ 余 **`P4-c`（口径说明 · 待用户定裁）** 与 **`P5-c`（删页级那条路）/ `P5-d`（行模板 `cols`）**"
          "＋ 小尾巴 `TAIL-196` |")
P1_NEW = ("· ⏭ 余 **`P4-c`（口径说明 · **窄档 14 块**）**：⭐ **2026-09-30 `P4-c-a` 试点已办**"
          "（出口 `CALIB` ＋ `V.m13` 一处 · 渲染字节逐字节自证 · 判据 ＋ 变异 `_mut_uxnum` **7/7**）"
          "⇒ 余 **`P4-c-b`（13 块）**；⚠️ `P5` 一路**已收口**（`P5-d` 收在 2 处 · §7.13）· "
          "⛔ `TAIL-196` 已销号（缓 · 不做） |")

# ── 计划 §15 §一 ─────────────────────────────────────────────────────────
P2_OLD = "⇒ 实况见 **§7.12**） |"
P2_NEW = ("⇒ 实况见 **§7.12**）；⭐⭐ **2026-09-30 `P4-c-a`（试点）已办 ⇒ 口径说明块出口 `CALIB` 落地**"
          "（`shell/proj.js`，与 `TBL`/`FBAR`/`PJB` 同件）：`<details>` 外壳 ＋ 标题 ＋ **算出来的条数** ＋ "
          "`<ul>` ＋ 条目外壳收成一处 ⇒ 「条数 ⇄ 条目」**由构造保证**（前哨抓到的那种「屏幕上写假条数」"
          "**从此不可能**）；试点 `V.m13`（三条理由都是**量出来的**：14 块里最小 · 相邻 `m14` 被别的判据钉着 · "
          "本页块无判据钉形态）；**渲染字节逐字节自证**（`tools/oneoff/_p4ca_calib.py` 拿 `node` 真跑比对 ⇒ "
          "⭐ 顺带实测出 **JS 模板字面量会把源码里的 `CRLF` 折成 `LF`** ⇒ 出口那个换行写 `\\n`）；"
          "行数 **-1**（`<ul>` 那行进出口了）；判据 = `backend/tests/test_ux_numbers.py::"
          "test_口径说明块走统一出口_CALIB`（**先查内核再扫调用点**）＋ 变异 `tools/mut/_mut_uxnum.py` "
          "**4 → 7/7**（`M5` 写死条数 / `M6` 又裸写一层 / `M7` 不包条目外壳）；取件桩 = "
          "`tests/shell_src.py::calib_kernel()`；⇒ 实况见施工图 **§8.11**） |")

# ── 计划 §13.6（交接材料 · 两处"钉住现状"的句子）────────────────────────
P3_OLD = "量测＋批切法见施工图 **§8.10** · **尚未开工**）"
P3_NEW = ("量测＋批切法见施工图 **§8.10** · ⭐ **`P4-c-a` 试点已办**（2026-09-30 · 出口 `CALIB` ＋ `m13` 一处 · "
          "见 §8.11）⇒ **余 `P4-c-b` 13 块**）")

P4_OLD = "量测＋批切法见 §8.10 · **尚未开工**）**"
P4_NEW = ("量测＋批切法见 §8.10 · ⭐ **`P4-c-a` 试点已办**（出口 `CALIB` ＋ `m13` 一处 · §8.11）"
          "⇒ 余 `P4-c-b` 13 块）**")

P5_OLD = "**2026-09-30 已办到 `P4-d-b`**"
P5_NEW = "**2026-09-30 已办到 `P4-c-a`**（口径说明试点 · 施工图 §8.11）"


def rd(p: pathlib.Path) -> tuple[str, str]:
    raw = p.read_text(encoding="utf-8", newline="")
    return raw.replace("\r\n", "\n"), ("\r\n" if "\r\n" in raw else "\n")


def wr(p: pathlib.Path, text: str, nl: str) -> None:
    p.write_text(text if nl == "\n" else text.replace("\n", nl), encoding="utf-8", newline="")


def sub1(text: str, old: str, new: str, what: str) -> str:
    n = text.count(old)
    assert n == 1, f"⛔ {what}：命中 {n} 次（期望 1）—— 锚点过期了？"
    print(f"   ✅ {what}")
    return text.replace(old, new, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    design, nl_d = rd(DESIGN)
    plan, nl_p = rd(PLAN)

    design = sub1(design, D1_OLD, D1_NEW, "施工图 §8.10 状态行")
    design = sub1(design, D2_OLD, D2_NEW, "施工图 §8.10 批切法表头（双边同步作废）")
    design = sub1(design, D3_OLD, D3_NEW, "施工图 §8.10 P4-c-a 行（U5_GROUPS 作废）")
    design = sub1(design, D4_OLD, D4_NEW, "施工图 §8.10 P4-c-b 行")
    design = sub1(design, D1_NEW, D1_NEW + "\n" + D5_HEAD, "施工图 追加 §8.11（紧接 §8.10 状态行）")

    plan = sub1(plan, P1_OLD, P1_NEW, "计划 §14.3 TAIL-64 尾句")
    plan = sub1(plan, P2_OLD, P2_NEW, "计划 §15 §一 TAIL-64 行")
    plan = sub1(plan, P3_OLD, P3_NEW, "计划 §13.6 口令里的 P4-c")
    plan = sub1(plan, P4_OLD, P4_NEW, "计划 §13.6 已确认的下一步里的 P4-c")
    plan = sub1(plan, P5_OLD, P5_NEW, "计划 §13.6 已办到 P4-d-b → P4-c-a")

    assert "**尚未开工**" not in design, "⛔ 施工图里还留着『尚未开工』（口径没订正干净）"
    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    wr(DESIGN, design, nl_d)
    wr(PLAN, plan, nl_p)
    assert rd(DESIGN)[0] == design, "⛔ 施工图写回不一致"
    assert rd(PLAN)[0] == plan, "⛔ 计划写回不一致"
    print("\n✅ 已落盘：施工图（§8.10 订正 ＋ §8.11 新增）＋ 计划（§14.3 / §15 / §13.6 四处）")
    print("⚠️ 接着必跑：`doc_audit.py`（T1–T20）＋ `doc_audit.py --ui`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
