"""`MOD-07` 壳接线断言用的**共用常量**（自 `test_wired_m07.py` 拆出 · 2026-09-19）。

**为什么拆**：`test_wired_m07.py` 涨到 **613 行 > 600** —— `tools/audit/doc_audit.py` 的 `T5` 写着「禁合入」。
⇒ 把「后端件常量」提到本件，`test_wired_m07.py` 与 `test_wired_m07_big.py` 共用一份
（⛔ 别各抄一份 —— 那就是"同一件事两遍"）。

⭐⭐ 2026-10-03（`TAIL-219` 批 2）：本件**原先还有两把"剪刀"**（`_body` / `_slice`：`SHELL.find` ＋ 花括号配平）
—— 已**整把删掉**，取片改走壳的语义口径（`tests.shell_src` 转发的 `func_body` / `page_slice`，
定义 = `tools/audit/shell_api.py`）。⇒ 本件现在**只剩常量**。⛔ 别把剪刀写回来。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc  # noqa: F401  ← 两个使用方都要它

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛
ROUTER = (ROOT / "backend" / "app" / "mod07_setl" / "router.py").read_text(encoding="utf-8")
API = (ROOT / "backend" / "app" / "mod07_setl" / "api.py").read_text(encoding="utf-8")
