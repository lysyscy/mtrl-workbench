"""壳侧「**数据导入**」页（`TAIL-75` `B5`）—— 入口 / 四步向导 / ⭐ **无死控件**（离线可验的那半）。

⭐ 为什么要有本件：真机自检（`tools/probe/_shell_legacy.py` 的 ② 「无死控件」）要**起服务 ＋ 浏览器**才跑得起来
   ⇒ 把它的判据做成**离线等价物**：页面上每个 `data-act` 都能解析到 `ACT`、**表单元素**的动作都在 `CHG` 里。
   ⚠️ **只查本页**（`V.imp` 那一段）：整壳扫会撞上别的页的边界情况（例如 `go`/`exp` 走的是委托），
     那些不是本件要管的事 —— 本件只管"新加的这页别漏登记"。
"""

from __future__ import annotations

import re

from tests.acc_plugin import acc
from tests.shell_load_helpers import loaders, page_load
from tests.shell_src import SHELL

#: 本页自己的动作（`ACT.<名>` 必须都在）
PAGE_ACTS = ("impDomain", "impPick", "impParse", "impMap", "impPj", "impPreview", "impCommit",
             "impRollback", "impReset")
#: 其中挂在**表单元素**上的（`<select>` / `<input type=file>`）⇒ 必须进 `CHG`，否则 `change` 被静默丢弃
FORM_ACTS = ("impDomain", "impPick", "impMap", "impPj")


def _imp_region() -> str:
    """`V.imp` 到 `ACT.impRollback` 那一段（本页的全部代码）。"""
    i = SHELL.find("V.imp = ()")
    j = SHELL.find("ACT.impRollback")
    assert i > 0 and j > i, "壳里找不到「数据导入」页（形态变了就同批改本件）"
    return SHELL[i:j]


def _chg_names() -> set[str]:
    """`CHG.push(…)` 里登记过的名字（全部 push 调用合并）。"""
    out: set[str] = set()
    for body in re.findall(r"CHG\.push\(([^)]*)\)", SHELL):
        out |= set(re.findall(r"'([^']+)'", body))
    return out


@acc("ACC-IMP-MAP-001", "001-10")
def test_数据导入页在壳里_四步向导_且无死控件():
    """⭐ 「通用导入面」在壳上真的**有入口、有四步、且控件都登记过**（无死控件）。"""
    # ① 入口：侧栏 ＋ 顶栏标题 ＋ 已接后端标注
    assert re.search(r"\[['\"]imp['\"],\s*['\"]数据导入['\"]", SHELL), "侧栏没有「数据导入」入口"
    assert re.search(r"\bimp:\s*['\"]数据导入['\"]", SHELL), "`TITLE` 里没有这一页"
    assert re.search(r"['\"]imp['\"]\]\)", SHELL) or "'imp'" in SHELL, "`WIRED` 没标这一页"
    # ② 取数路：进页拉"数据导入"那一路，且 LOADERS 有对应函数（⛔ 漏了 ⇒ 页面空白）
    assert page_load().get("imp") == ["数据导入"], page_load().get("imp")
    assert "数据导入" in loaders()
    # ③ 四步向导的四步文案都在（人看得见的流程）
    for step in ("① 选域与文件", "② 列映射", "③ 预览校验", "④ 确认落库"):
        assert step in SHELL, f"四步向导缺一步：{step}"
    # ④ 无死控件（离线等价物）：每个 `data-act` 都能解析到 `ACT`
    acts = set(re.findall(r"\nACT\.(\w+)\s*=", SHELL))
    missing = [a for a in PAGE_ACTS if a not in acts]
    assert not missing, f"这些动作没在 `ACT` 上定义 ⇒ 点了没反应（死控件）：{missing}"
    # ⑤ 表单元素必须进 `CHG`（漏了 ⇒ `change` 被静默丢弃，症状是"选完文件按钮还是灰的"）
    chg = _chg_names()
    not_chg = [a for a in FORM_ACTS if a not in chg]
    assert not not_chg, f"表单动作没进 `CHG` ⇒ change 会被静默丢弃：{not_chg}"
    # ⑥ 页面上**真的用到**了这些动作（⛔ 光在 `ACT` 上定义、模板里没接 = 另一类死代码）。
    #    ⚠️ 两种接法都算：直接写在标签上（`data-act="x"`）或**经共用件传参**（`lgPick(id, 'x', …)`
    #    —— 它内部才拼出 `data-act="${pickAct}"`）⇒ 只认前者会把正常写法误判成"没接"（自测踩到）。
    body = _imp_region()
    for a in PAGE_ACTS:
        assert (f'data-act="{a}"' in body) or (f"'{a}'" in body), \
            f"动作 `{a}` 定义了却没用上（或没接在控件上）"


def _act_body(name: str) -> str:
    """取 `ACT.<name>` 的函数体（到行首 `};` 为止 —— 本页的动作体里没有跨行 `}`）。"""
    i = SHELL.find(f"ACT.{name} =")
    assert i > 0, f"壳里找不到 `ACT.{name}`"
    return SHELL[i:SHELL.index("\n};", i)]


@acc("ACC-IMP-MAP-001", "001-10")
def test_导入回滚后把取数缓存全标脏():
    """⭐ 2026-09-23（`TAIL-78` · 查 `TAIL-75` 落库下游时查出）：**导入/回滚是跨页写 ⇒ 必须全标脏**。

    ⛔ 原先只删「机械 6 列 / 收发结存与大表」两路 —— 那是**旧导入页 `m06imp`（已下架）**单域时代的遗留，
       而 `B5` 起导入已是**通用面**（域由后端 `/api/imp/domains` 列）。
    ⚠️ **漏标的真后果**（实测路径）：`m05_flow` 落库走 `sync_stat_paid`（**重算唯一出口**）⇒
       付款通知书的「统计付款金额」变了 ⇒ m03 的「已付金额」与 m05 的欠款/台账/统计**都变了**；
       而 `LOADED` 记着"拉过了" ⇒ **切回那两页看到的是旧数**（对真数据说旧话）。
    ⛔ 也**不许**改成"补几个字面域名单"：域清单的主人在后端，壳里列一份 = 「加一个域要改两处」。
    """
    for act in ("impCommit", "impRollback"):
        body = _act_body(act)
        assert "LOADED.clear()" in body, \
            f"`{act}` 没有**全标脏** —— 导入/回滚改了别的域的数，漏一路就是界面拿旧数当真"
        assert "LOADED.delete(" not in body, \
            f"`{act}` 退回**部分标脏**了（正是本判据要防的那条路：漏标 ⇒ 切回别页看旧数）"
