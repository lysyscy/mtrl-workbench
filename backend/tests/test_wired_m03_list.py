"""前端壳「付款通知书列表页」（`/m03/notices` · MOD-03）的离线断言 —— `§19` 批 4 **小轮①**。

⭐ 为什么有这个文件：这一页原来走**服务端渲染**（`app/mod03_notice/notice_page.py` 的
`render_notice_page`），页形态断言写在 `tests/test_notice_page.py` 里。旧页删除（授权 `D18`）⇒
**形态那半边改指新壳**（⛔ 判据不删）；实质（口径 / 取数 / 纯函数）仍留原处，待删页那一轮再归位。
⚠️ 其中 `ACC-PAY-LIST-001/001-09`（合计行）与 `001-07`（项目选择器共用件）是**绑定**判据点 ⇒
本文件把它们的**形态半边**接过来，删页时原文件里那半边随之作废、这条 claim 仍有着落 ✓。

⚠️ 与 `test_wired_m03_own.py`（归属）/ `test_wired_m03_print.py`（打印）分开：本文件只守**列表页形态**。
⚠️ 这里**只读壳源码**（`SHELL`）—— 不启动服务、不连库，与其它 `test_wired_*` 同款。
"""

from __future__ import annotations

import re
import json
import shutil
import subprocess
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

# ⭐ 2026-10-03（`TAIL-219` 批 2b）：`_NT_THEAD_RE`（自写正则）**已删** —— 取句走 `const_src`。⛔ 别写回来。






# ---------------------------------------------------------------- 骨架与列






# ---------------------------------------------------------------- 剔除 / 撤单的默认可见性








# ---------------------------------------------------------------- 集采关联的判据来源



# ---------------------------------------------------------------- 排序与空态








# ---------------------------------------------------------------- 时间口径与数据纯度


def test_通知书默认全部时间且其他付款域默认月不变():
    """用户2026-10-13修订§9.2：通知书列表默认全部，抓取和其他付款域仍当月。"""
    from app.core.period import default_period

    assert default_period("notice") == date.today().strftime("%Y-%m"), "付款域默认月不是当月"
    assert default_period("notice") != default_period("process"), "付款域与材料报表类的默认月应当不同"




# ---------------------------------------------------------------- 绑定判据点（`ACC-PAY-LIST-001`）
