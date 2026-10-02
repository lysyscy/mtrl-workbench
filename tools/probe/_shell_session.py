"""⓪ · 播种会话票（以在用管理员身份）

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations

from _shell_common import session_cookie
from _shell_segments import BASE


def check(page, errors) -> None:
    """⓪ —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ⭐ 先播会话票（见 `_session_cookie` 的注释）—— ⛔ 别删：删了本自检就跑在"未登录"态
    _ck_name, _ck_val = session_cookie()
    page.context.add_cookies([{"name": _ck_name, "value": _ck_val, "url": BASE}])
    print(f"⓪ 已播种会话票（以在用管理员身份）· cookie={_ck_name}")


