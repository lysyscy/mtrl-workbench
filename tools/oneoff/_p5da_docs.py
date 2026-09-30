#!/usr/bin/env python
r"""`P5-d-a` 收尾落纸（**同批**）：施工图 §7.11（实况）＋ §7.10 指针 ＋ §六 进度 ＋ 计划 §15 台账 ＋ §13.6 口令。

⚠️ 规矩同 `_p5c_docs.py`：逐处先断言命中数、改完 round-trip 自校验；中文行文里的引号一律用「」。

用法：`python tools/oneoff/_p5da_docs.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
DES = ROOT / ".workbuddy" / "work" / "10-designs" / "设计-表格筛选配置化-20260924.md"
NL = "\r\n"

S711 = """### 7.11 ⭐ `P5-d-a` 实况（2026-09-30 · **列定义式**（`cols:[{t,r}]`）＋ 一处试点）

**试点挑哪一处**（依据 = §7.10 的量测）：`TBL` 46 个调用点里挑 **`actions.js` 的 `modal:procExp`**
（2 列 1 行 · **不在 `V.*` 里 ⇒ 零 `U1` 级联** · **壳独有** ⇒ 调用点那侧不必双边同步）。

**契约**（⚠️ §7.4 草案写的是 `{t,r,s}` —— 那个 `s` **暂时没有用武之地**：列的可排性写在 `t` 的
`<th class="srt">` 上、格的样式写在 `r` 返回的 `<td>` 上 ⇒ **本件只收 `{t, r}` 两个**，
⛔ 别为凑第三个**发明**一个没人读的参）：

| 参 | 含义 |
|---|---|
| `cols:[{t, r}]` | `t` = 表头那一格（**整段 `<th>` HTML**）· `r` = 取值器 `(x, i) =>` 这一格（**整段 `<td>` HTML**） |
| `list:[…]` | 数据行 |
| 派生规则 | 给了 `cols` ⇒ `head = cols.map(c=>c.t).join('')`、`rows = list.map((x,i)=>'<tr>'+cols.map(c=>c.r(x,i)).join('')+'</tr>')` |
| 优先级 | ⚠️ `cols` **优先**：同时再传 `head` / `rows` 会被**静默忽略**（判据专门钉这条 —— 「看着改了、其实没用」） |

**三处改动**：

| # | 改哪 | 说明 |
|---|---|---|
| ① | `TBL` 签名 | 加可选参 `cols=null` · `list=[]`（**默认值保持旧行为** ⇒ 其余 45 处调用点零影响） |
| ② | `TBL` 体内 | 列定义式那段派生（放在 `attr` / `th` 之前） |
| ③ | `modal:procExp` 调用点 | `head:` ＋ `rows:…map(…)` ⇒ `cols:[{t,r},{t,r}]` ＋ `list:pjs` |

⚠️ **①② 是 `U5` 件**（壳 ⇄ 原型**逐段一致**）⇒ **两侧同批同句**（原型改前已备份
`artifacts/delivery-backups/原型-备份-20260930-P5da前.html`）；`ui_parity` 当场复核 **`U5` 登记 44 个全部逐字一致** ✓。
⭐ **自证**（`tools/oneoff/_p5da_cols.py` 的 `_self_check()`）：拿试点那两列的**旧写法 vs 新写法**渲染三组数据
（0 / 1 / 3 个项目）**逐字节比对** ✓；脚本里还用 `node` 核了「壳 ⇄ 原型 `TBL` 段逐字一致」。

**判据／变异同批**：

- 新增 `backend/tests/test_ux_pages.py::test_表格件支持列定义式_试点已接上`（**两段式**：调用点**委托** ＋
  **内核真派生**）。⚠️ 里头那条**墓碑**要钉**试点那一行的整串** —— 只写前缀会撞上邻近的 `modal:ledExp`
  （前缀同款、只多一格），**本判据首版就栽在这**（假红）；
- ⚠️ **同批改了一条「钉源码形态」的老判据**（`test_acc_x_exp.py` 的 `ACC-X-EXP-001/001-03`）：它原先要求
  多项目分支里出现 `pjs.map` ⇒ 试点改列定义式后**必然假红**；按本仓范式改成**两段式**
  （分支**自己** `pjs.map` **或**把数据交给 `list:` ＋ **内核**里真逐项一行），⛔ 不是退回钉字面；
- 变异：`tools/mut/_mut_tbl.py` **39 → 42 靶**（`M40` 内核不派生 / `M41` 去掉 `list:` 交回手写 /
  `M42` **同时**给 `cols` 与手写 `rows:`（后者被静默忽略））⇒ **42/42** ＋ 逐字节复原。

**下一步**：**`P5-d-b`**（那 14 处「纯逐列取值」，先挑 `V.*` 里**两侧本来就逐行对齐**的 ⇒ 换号最小）·
**`P5-d-c`**（17 处带条件 / 派生列 / 嵌套的）· ⏭ 之后才谈「`mechYm` / `awfTbl` 并入 `TBL`」。
"""


def _sub(t: str, old: str, new: str, what: str, n: int = 1) -> str:
    got = t.count(old)
    assert got == n, f"⛔ {what}：锚点命中 {got} 次（期望 {n}）"
    return t.replace(old, new, n)


def patch_des(t: str) -> str:
    # ① §7.10 末尾加一句指针（把"建议"与"实况"连起来）
    t = _sub(t, "     ⭐ 那才是 `TAIL-64` 最初的动机。",
             "     ⭐ 那才是 `TAIL-64` 最初的动机。\n\n"
             "⭐ **2026-09-30 当日：`P5-d-a`（试点）已办** —— 见 **§7.11**（`cols:[{t,r}]` ＋ `list` ＋ "
             "`modal:procExp` 一处试点）。", "§7.10 末尾指针")

    # ② §六 进度行：把 P5 那行补上 P5-d-a
    t = _sub(t, "`P5-c` **删掉页级那条死路**（＋ 三处「认领认错对象」堵漏） | 2026-09-30 |",
             "`P5-c` **删掉页级那条死路**（＋ 三处「认领认错对象」堵漏）· ⭐ `P5-d-a` **列定义式**"
             "（`cols:[{t,r}]` ＋ 一处试点） | 2026-09-30 |", "§六 P5 行")
    t = _sub(t, "⛔ 余 `P5-d`（行模板 `cols` —— 住在 `V.*` 里，**先出量测**）＋ 新尾巴 `TAIL-198` |",
             "⛔ 余 `P5-d-b` / `P5-d-c`（量测见 **§7.10**、试点见 **§7.11**）＋ 新尾巴 `TAIL-198` |",
             "§六 P5 行尾")
    # ③ 末尾追加 §7.11
    assert t.rstrip().endswith("⭐ **2026-09-30 当日：`P5-d-a`（试点）已办** —— 见 **§7.11**"
                               "（`cols:[{t,r}]` ＋ `list` ＋ `modal:procExp` 一处试点）。"), \
        "⛔ 施工图末尾不是刚落的那句指针，先人工看一眼"
    t = t.rstrip("\n") + "\n\n" + S711
    print("   ✅ ① 施工图：§7.10 指针 ＋ §六 进度 ＋ 追加 §7.11")
    return t


def patch_plan(t: str) -> str:
    t = _sub(
        t, "⇒ 实况见施工图 **§7.9**） |",
        "⇒ 实况见施工图 **§7.9**）⭐⭐ **同日 `P5-d-a` 也办了（列定义式）**：给表格件加**可选参**"
        "`cols:[{t,r}]` ＋ `list`（`t` = 表头那一格、`r` = 取值器 `(x,i)=>` 这一格，都是**整段 HTML**；"
        "⚠️ §7.4 草案里的第三个字段 `s` **暂时没有用武之地** ⇒ ⛔ 不为凑数**发明**一个没人读的参）；"
        "**`cols` 优先**（同时再传 `head`/`rows` 会被**静默忽略** —— 判据专门钉这条「看着改了、其实没用」）；"
        "试点挑 `actions.js` 的 `modal:procExp`（**不在 `V.*` 里 ⇒ 零 `U1` 级联** · 壳独有）；"
        "⚠️ `TBL` 是 `U5` 件 ⇒ **壳 ⇄ 原型同批同句**（原型改前已备份 `原型-备份-20260930-P5da前.html`）、"
        "`U5` 复核 44 个全逐字一致；⭐ 自证 = 脚本 `tools/oneoff/_p5da_cols.py` 渲染**旧 vs 新**三组数据"
        "**逐字节比对**；判据 = `test_ux_pages.py::test_表格件支持列定义式_试点已接上`（两段式）＋ "
        "⚠️ 同批改掉一条**钉源码形态**的老判据（`test_acc_x_exp.py` 的 `001-03` 原先要求多项目分支里出现 "
        "`pjs.map` ⇒ 必然假红 ⇒ 改成「自己 `pjs.map` **或**交给 `list:` ＋ 内核真逐项一行」两段式）"
        "＋ 变异 `_mut_tbl.py` **39 → 42/42**（`M40` 内核不派生 / `M41` 去掉 `list:` / `M42` 同时给 "
        "`cols` 与手写 `rows:`）⇒ 实况见施工图 **§7.11**） |",
        "§15 TAIL-64 行尾")
    print("   ✅ ② 计划 §15 · TAIL-64 追加 P5-d-a")

    # 口令：已确认的下一步（P5 块）
    old = ("     ＋ `P5-b` 标记**一律带**（⛔ 不设开关 · §7.8）＋ `P5-c` **删掉页级那条死路**（＋ 三处堵漏 · §7.9）⇒ 余\n"
           "     **`P5-d`（行模板 `cols:[{t,r,s}]` —— ⚠️ 住在 `V.*` 切片里，`U1` 会逐行级联）**；\n")
    new = ("     ＋ `P5-b` 标记**一律带**（⛔ 不设开关 · §7.8）＋ `P5-c` **删掉页级那条死路**（＋ 三处堵漏 · §7.9）\n"
           "     ＋ `P5-d-a` **列定义式**（`cols:[{t,r}]` ＋ 一处试点 · §7.11）⇒ 余\n"
           "     **`P5-d-b` / `P5-d-c`（那 14 处「纯逐列取值」/ 17 处带条件列 —— ⚠️ 先挑 `V.*` 里两侧对齐的）**；\n")
    t = _sub(t, old, new, "口令 已确认的下一步 · P5 块")
    print("   ✅ ③ 口令 · 已确认的下一步（P5 块）")

    t = _sub(t, "**工作区 = 本批未提交**（`P5-c`：壳 1 件 ＋ 判据/探针/变异/量测 ＋ **施工图/台账/交接材料本身**）"
                "· **本地领先远端 0**（`7a5c435` 已 push —— 本批**尚未提交**，⛔ 提交要用户点头）",
             "**工作区 = 本批未提交**（`P5-d-a`：壳 2 件 ＋ **原型（仓外 · 已备份）** ＋ 判据/变异/脚本 ＋ "
             "**施工图/台账/交接材料本身**）· **本地领先远端 0**（`494e2e5` 已 push —— 本批**尚未提交**，"
             "⛔ 提交要用户点头）", "口令 工作区/领先远端")
    print("   ✅ ④ 口令 · 工作区/领先远端")
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    des = DES.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    plan = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    des2, plan2 = patch_des(des), patch_plan(plan)
    assert des2 != des and plan2 != plan, "⛔ 一个字都没改？"
    if not a.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    DES.write_text(des2.replace("\n", NL), encoding="utf-8", newline="")
    PLAN.write_text(plan2.replace("\n", NL), encoding="utf-8", newline="")
    assert DES.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == des2, "⛔ 施工图写回不一致"
    assert PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == plan2, "⛔ 计划写回不一致"
    print("\n✅ 落纸完成（施工图 ＋ 计划）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
