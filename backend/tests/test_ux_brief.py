"""`TAIL-117` 批次 5：**默认展开的说明块不许铺满一屏**的离线判据（守则 §3.4 · §5.9 · §3.1）。

**守则落点**：§3.4【应当】"与当前任务无关的冗余信息不塞同一屏（塞满 = 找不到重点 ⇒ 走 §5.9 折叠）"
· §5.9【必需】"同屏做优先级排序：核心操作与核心数据一眼可见，次要信息**可折叠**"
· §3.1（技术实现细节不上屏 —— 本批顺手删掉的那句"付款在事务内重算…`request_id` 语义"就是它）。

`§3.4` 的判据原来是 `人眼 · 未挂` ⇒ **本批给它挂上第一道机器判据**（真机 `tools/probe/_shell_text.py` 的 **㉖**：
逐页量"默认展开的 `.tip`"的字数，超 `LONG_LIMIT` 就报）。本件是它的**离线两半**：

  ① **墓碑**：本批删掉的实现话术整串不许回来（§3.1）；
  ② **反"删光"**：不许用"把说明都删掉"来过 ㉖ —— 每页该有的「口径说明」折叠出口必须还在（§5.8「换地方，不是删掉」）。

⚠️ **为什么"长度"这件判在真机而不在这里**：离线要量长度就得先分清字符串 / 注释 / 模板插值，
   实测极难不出假阳性（参见 `_shell_text.py` 文件头那条教训）；而"屏幕上到底铺了多长"读 DOM 就是准的。
"""

from __future__ import annotations

import pathlib

from tests.acc_plugin import acc
from tests.shell_src import SHELL

#: 仓库根（本件在 `backend/tests/` 下）
ROOT = pathlib.Path(__file__).resolve().parents[2]


@acc("ACC-UI-SHELL-001", "001-13")
def test_实现话术墓碑():
    """⭐ 本批从界面上删掉的实现话术，⛔ 不许再回到屏幕上（守则 §3.1）。

    ⚠️ **能证伪**：把任意一句贴回某个 `tip` 里 ⇒ 本件必红。
    """
    for tomb in ("在事务内重算剩余未付金额", "request_id</span> 语义"):
        assert tomb not in SHELL, \
            f"实现细节又上屏了：{tomb!r} —— 那是给开发看的（守则 §3.1），⛔ 别再写进界面文案"


@acc("ACC-UI-SHELL-001", "001-14")
def test_折叠出口还在_不许靠删来过关():
    """⭐ 过 ㉖（说明别太长）**只能靠"压短或折起来"**，⛔ 不许靠"把说明删干净"。

    判法：`<details class="tip">`（各页「口径说明 · N 条」那种"要查才看"的档）仍要**成规模地存在**。
    ⚠️ 数量会随页面增减漂 ⇒ 只设**下限**（现为 8 处，留一档余量）。
    ⚠️⚠️ **2026-09-30（`TAIL-64` `P4-c-b`）：口径说明块全站 14 块已收进出口 `CALIB`**
    ⇒ 挂在源码里的那串字面只剩「内核里那一份 ＋ 2 处非口径说明的折叠块」= **3** ⇒ **照旧数会假红**。
    ⛔ **别把下限调低**（那等于承认"说明可以少"）—— **改按意图数**：每个 `CALIB({` 调用点
    渲染出来**还是一条**这种折叠口径说明 ⇒ 字面数 ＋ 调用点数。
    """
    n = SHELL.count('<details class="tip"') + SHELL.count("CALIB({")
    assert n >= 8, \
        f"「要查才看」的折叠口径说明只剩 {n} 处（应 ≥ 8）—— 别用「删光说明」来让 ㉖ 变绿（守则 §5.8）"


@acc("ACC-UI-SHELL-001", "001-15")
def test_真机26号的判据本身还在():
    """⭐ 本条的"长度"判在真机 ⇒ **判据本身**也要有人守着（⛔ 别哪天被顺手删掉，文档还写着"已挂判据"）。

    ⚠️ 判法 = 真机件里必须有阈值常量 `LONG_LIMIT` 与 **㉖** 那一段（结构存在性，⛔ 不判它内部怎么写）。
    """
    src = (ROOT / "tools" / "probe" / "_shell_text.py").read_text(encoding="utf-8")
    assert "LONG_LIMIT" in src, "真机件里没有长度阈值 `LONG_LIMIT` —— ㉖ 的判据被拆掉了？"
    assert "㉖" in src, "真机件里没有 ㉖ 那一段 —— 守则 §3.4 的判据悬空了？"
    # ⭐ 2026-09-28（`TAIL-124` / `TAIL-105`）：**㉙ 页级禁用**（`m13` 的工程台账话术 / `imp` 的 `**`）
    #    同样要有人守着 —— 它只活在真机件里，删掉不会有任何离线判据响。
    assert "㉙" in src and "PAGE_TEXT_RULES" in src, \
        "真机件里没有 ㉙ `/`PAGE_TEXT_RULES` —— `m13`/`imp` 的页级判据悬空了？"


@acc("ACC-UI-SHELL-001", "001-16")
def test_域自报的长文案也要守上限():
    """⭐ `TAIL-105`（2026-09-28）：**㉖ 只看"首屏那个域"**（`imp` 一进来是 `m06_proc`）⇒
    切到别的域（如 `m11_jc`）才露出来的那几句**它量不到** —— 本批实测：`m11` 的 `rule_note`
    曾写到 ~250 字，而**所有尺子全绿**。⇒ 离线在**源头**再钉一道（域自报的每一句都过一遍）。

    ⚠️ 上限**沿用 ㉖ 的同一个数**（200）⇒ ⛔ 不另立一个新阈值（守则 §3.4 / §5.9）。
    ⚠️ 字数按**渲染后**算（`**` 是标记、不计；空白不计）—— 与 ㉖ 量 DOM 的口径对齐。
    ⚠️ **能证伪**：把 `m11` 的 `rule_note` 写回 250 字 ⇒ 本件必红。
    """
    import re

    from app.main import app as _app  # noqa: F401  ← 触发各域登记（`build_router` 期写进 `REGISTRY`）
    from app.import_kit.api import REGISTRY

    upper = 200
    over = []
    for dom, spec in sorted(REGISTRY.items()):
        for fld in ("note", "keep_note", "rule_note", "field_list_hint"):
            txt = re.sub(r"\*\*|\s", "", getattr(spec, fld, "") or "")
            if len(txt) > upper:
                over.append(f"{dom}.{fld} = {len(txt)} 字")
    assert not over, (
        f"域自报文案超过 {upper} 字（守则 §3.4 / §5.9）—— 它默认展开、就铺在 ①/② 步上：{over}")
