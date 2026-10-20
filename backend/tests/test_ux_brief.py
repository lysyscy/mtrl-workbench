"""`TAIL-117` 批次 5：**默认展开的说明块不许铺满一屏**的离线判据（守则 §3.4 · §5.9 · §3.1）。

**守则落点**：§3.4【应当】"与当前任务无关的冗余信息不塞同一屏（塞满 = 找不到重点 ⇒ 走 §5.9 折叠）"
· §5.9【必需】"同屏做优先级排序：核心操作与核心数据一眼可见，次要信息**可折叠**"
· §3.1（技术实现细节不上屏 —— 本批顺手删掉的那句"付款在事务内重算…`request_id` 语义"就是它）。

`§3.4` 的判据原来是 `人眼 · 未挂` ⇒ **本批给它挂上第一道机器判据**（真机 `tools/probe/_shell_text.py` 的 **㉖**：
逐页量"默认展开的 `.tip`"的字数，超 `LONG_LIMIT` 就报）。本件是它的**离线两半**：

  ① **墓碑**：本批删掉的实现话术整串不许回来（§3.1）；
  ② **默认页精简**：按TAIL-263授权删除指定页面说明，保留错误、操作结果与弹窗反馈。

⚠️ **为什么"长度"这件判在真机而不在这里**：离线要量长度就得先分清字符串 / 注释 / 模板插值，
   实测极难不出假阳性（参见 `_shell_text.py` 文件头那条教训）；而"屏幕上到底铺了多长"读 DOM 就是准的。
"""

from __future__ import annotations

import pathlib

from tests.shell_src import SHELL

#: 仓库根（本件在 `backend/tests/` 下）
ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_实现话术墓碑():
    """⭐ 本批从界面上删掉的实现话术，⛔ 不许再回到屏幕上（守则 §3.1）。

    ⚠️ **能证伪**：把任意一句贴回某个 `tip` 里 ⇒ 本件必红。
    """
    for tomb in ("在事务内重算剩余未付金额", "request_id</span> 语义"):
        assert tomb not in SHELL, \
            f"实现细节又上屏了：{tomb!r} —— 那是给开发看的（守则 §3.1），⛔ 别再写进界面文案"


def test_默认页说明按最新用户取舍精简():
    """TAIL-263覆盖旧数量下限；错误/结果与弹窗反馈仍保留。"""
    from tests.shell_src import page_slice
    for key in ['m05','m06','m07','m08','m09','m11','m15']:
        assert '<div class="tip"' not in page_slice(key), key
    assert '待建档清单没取到' in SHELL
    assert '没有保存成功' in SHELL or '保存失败' in SHELL




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
