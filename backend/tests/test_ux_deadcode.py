"""`TAIL-117` 批次 7「残骸清理」的离线判据。

**本批清的到底是什么**（先把口径分清，⛔ 别把两件事混成一件）：

| 类别 | 例子 | 怎么办 |
|---|---|---|
| **真死码** —— 零引用、且内容与运行数据无关 | `index.html` 那张 6 行「接口清单表」`TASK`（`API-01`…`API-06`：触发方式 / 数据源 / 用途） | **删**（本批干的） |
| **有意保留的留痕** —— 用户 2026-09-20 裁定"原型 / 壳两边同进同退" | `V.m12` 那片 ＋ `df*` 动作 ＋ `dfD` 等辅助件；`*_COLS`「行形状说明」常量 | **当前壳保留的撤项说明**（旧原型与U1已退役；本测试只守正式壳的撤项保护）——依据 `tools/audit/audit_common.py::CANCELLED_KEEP_IN_PROTO_AND_DOCS` |

⭐ 所以本件只钉**第一类**（真死码），并且**同时钉住第二类的边界**（防止下一个人"顺手清干净"）。

⚠️ 判法一律**整串墓碑**（本仓教训：裸词会让注释里的说明也命中 ⇒ 假红）。
"""

from __future__ import annotations

import pathlib

from tests.acc_plugin import acc
from tests.shell_src import SHELL

ROOT = pathlib.Path(__file__).resolve().parents[2]


@acc("ACC-UI-SHELL-001", "001-33")
def test_接口清单表不许回来():
    """⭐ `TASK` 那张表：**零引用** ＋ 内容是**开发视角**（`API-0x` 代号 / 触发方式 / 数据源），
    数据源本就是《说明书》附录 E.1 的文档 ⇒ 需要时查文档，⛔ 别在壳里再抄一份（抄了必静默过期）。

    ⚠️ **能证伪**：把那张表贴回 `index.html` ⇒ 本件必红。
    """
    for tomb in ("const TASK = [",
                 "['API-06','常用项目列表 GetCommonUseList'",
                 "接口清单表（`TASK`）刻意不接"):
        assert tomb not in SHELL, \
            f"已删的「接口清单表」残骸又回来了：{tomb!r} —— ⓵它零引用 ⓶内容是开发视角（守则 §3.1）"


@acc("ACC-UI-SHELL-001", "001-34")
def test_过期话术墓碑():
    """⭐ 本批订正掉的两句**过期注释**（⛔ 别再写回来）：

    ① "仍待清：`V.m12` … ＋ 4 个 `m12*` 接口仍是残骸" —— 那 4 个接口**2026-09-20 夜就删了**；
    ② 同处那句"`doc_audit` 的 `T8` 每次跑批会报黄" —— 页撤之后 `T8` 报的是**复活**，不再报这个。

    ⭐ 本仓口径：「**代码里"教人怎么做"的注释，一旦机制改了就是假说明书**」——
       所以订正过期注释与删代码**同权**（都是本批的活）。
    """
    for tomb in ("4 个 `m12*` 接口仍是残骸", "`doc_audit` 的 `T8` 每次跑批会报**黄**提醒"):
        assert tomb not in SHELL, f"过期话术又回来了：{tomb!r}（它是假说明书）"


@acc("ACC-UI-SHELL-001", "001-35")
def test_有意保留的留痕不许被顺手清掉():
    """⭐ 本批的另一半：**把"别清"这条也钉住** —— 下一个人看到 `V.m12` / `df*` 会觉得是残骸。

    ⚠️ 判法 = 两件都必须在位：① 留痕本身（`V.m12` 那片 ＋ 那几个 `df*` 动作）；
       ② 那段**说明为什么不能清**的注释（指回 `CANCELLED_KEEP_IN_PROTO_AND_DOCS`）。
    ⛔ 只留件、不留理由 ⇒ 下一个人照样会来清。
    """
    assert "V.m12=" in SHELL, "`V.m12` 那片留痕不见了（它是原型切片的对位件，单边删 U1 立刻红）"
    for act in ("dfOk:", "dfAdd:", "dfCancel:"):
        assert act in SHELL, f"`ACT.{act[:-1]}` 不见了 —— 留痕要能**渲染**才算留痕（删了切片按钮会报错）"
    assert "CANCELLED_KEEP_IN_PROTO_AND_DOCS" in SHELL, \
        "「有意保留的留痕」那段理由注释被删了（⛔ 只留件不留理由，下一个人就会来清）"
    # ⭐ 2026-09-28（**用户裁定 `B`** · 审计清单 §六「裁定 5」）：侧栏最左列是**模块编号**（`MOD-xx`）——
    #    它是"**给人看的编号**"（文档 /《说明书》/ 判据件都按它对齐），**不是**黑话 ⇒ ⛔ 别当 §3.1 的场景清掉。
    assert '<span class="c">${c}</span>' in SHELL, \
        "侧栏的「模块编号列」被清掉了 —— 用户 2026-09-28 裁定保留（见审计清单 §六 裁定 5 / 守则 §3.1 例外栏）"
    assert "g.items.map(([k,n,c])" in SHELL, \
        "侧栏渲染不再取 `NAV` 第三列（模块编号）了 ⇒ 改这条要**先问用户**（裁定 5 选的是保留）"


@acc("ACC-UI-SHELL-001", "001-36")
def test_删掉的那张表不是判据要的():
    """⭐ 反向确认：`TASK` 不是任何判据 / 尺子的观测点（删它**不该**动到别的东西）。

    ⚠️ 判法 = `wiring_audit` / `doc_audit` 的登记表里没有 `TASK` 这个名字
       （有的话就说明"删它得同步改尺子登记"，本批的注释也应当写清）。
    """
    for rel in ("tools/audit/audit_common.py", "tools/audit/wiring_audit.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "TASK" not in src, f"{rel} 里引用了 `TASK` —— 删它就得同批改尺子登记（本批没改 ⇒ 说明引错了）"
