"""`tests` 侧取壳源码的**唯一出口**（转发 `tools/shell_source.py` · 性能 `P4`① 读取点收敛）。

**为什么是转发而不是各读各的**：壳要拆成 `web/shell/*.js` 多件（`P4`②）——
若 26 个测试件各自 `pathlib.read_text("index.html")`，拆完就**静默**读不到接线代码。
⇒ 统一从这里取（合并后的全文 = `SHELL`）。

**为什么不做成一个模块**：`tools/` 不在测试进程的 `sys.path` 上（pytest 的 rootdir 是 `backend/`）
⇒ 本件只做一件事：把**仓根**挂进 `sys.path`，再原样转发。
（单测里 `from tests.shell_src import SHELL`，⛔ 别绕过它去读 `index.html`。）
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.shell_source import (  # noqa: E402
    SHELL,
    SHELL_PARTS,
    SHELL_PATH,
    part_paths,
    parts_text,
    read_shell,
)

__all__ = ["SHELL", "SHELL_PARTS", "SHELL_PATH", "part_paths", "parts_text", "read_shell"]
